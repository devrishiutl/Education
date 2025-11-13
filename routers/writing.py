# routers/writing.py
from fastapi import APIRouter, HTTPException, Depends, Query
from database import db
from models import WritingAnswer, WritingTopicIn
from bson import ObjectId
from datetime import datetime
from utils.jwt import get_current_user
import uuid
from utils.allFunctions import paginate
from typing import List
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

client = AsyncOpenAI()


class Feedback(BaseModel):
    strengths: List[str]
    areas_for_improvement: List[str]


class Evaluation(BaseModel):
    overall_score: int
    feedback: Feedback
    example_answer: str


router = APIRouter(prefix="/writing", tags=["Writing"])


# Get writing topics
@router.get("/topics")
async def get_topics(
    page: int,
    page_size: int,
    aiDecide: bool = Query(False),
    level_beginner: Optional[str] = Query(None, alias="level.beginner"),
    level_intermediate: Optional[str] = Query(None, alias="level.intermediate"),
    level_advanced: Optional[str] = Query(None, alias="level.advanced"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user_id: Optional[str] = Depends(get_current_user),
):
    try:
        # ───────────────────────────────────────────────
        # AI Decide Logic (Adaptive Writing Topic Selection)
        # ───────────────────────────────────────────────
        if aiDecide:
            if not user_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "message": "User authentication required for AI-based topic selection."
                    },
                )

            # Fetch all previous writing submissions by user
            submissions = await db.writing_evaluations.find(
                {"user_id": user_id},
                {"_id": 0, "topic_id": 1, "evaluation_data.overall_score": 1},
            ).to_list(None)

            if not submissions:
                # If no submissions → start with beginner easy topic
                topic = await db.writing_topics.aggregate(
                    [
                        {"$match": {"level": "beginner", "difficulty": "easy"}},
                        {"$sample": {"size": 1}},
                        {"$project": {"_id": 0, "standard": 0, "created_at": 0}},
                    ]
                ).to_list(1)
                return topic[0] if topic else []

            # Map topic_id → (level, difficulty)
            topics = await db.writing_topics.find(
                {},
                {"topic_id": 1, "level": 1, "difficulty": 1, "_id": 0},
            ).to_list(None)
            topic_level_map = {
                t["topic_id"]: (t["level"], t["difficulty"]) for t in topics
            }

            # Calculate average scores by level
            level_scores = {"beginner": [], "intermediate": [], "advanced": []}
            for s in submissions:
                tid = s["topic_id"]
                if tid in topic_level_map:
                    level, _ = topic_level_map[tid]
                    level_scores[level].append(
                        s.get("evaluation_data", {}).get("score", 0)
                    )

            avg_scores = {
                level: (sum(scores) / len(scores) if scores else 0)
                for level, scores in level_scores.items()
            }

            # Adaptive logic: pick next level and difficulty based on performance
            if avg_scores["beginner"] < 70:
                next_level = "beginner"
                next_difficulty = "easy"
            elif avg_scores["intermediate"] < 70:
                next_level = "intermediate"
                next_difficulty = "medium"
            else:
                next_level = "advanced"
                next_difficulty = "hard"

            # Optionally restrict by category (if provided)
            match_stage = {"level": next_level, "difficulty": next_difficulty}
            if category:
                match_stage["category"] = category

            # Pick one random writing topic from target level/difficulty
            topic = await db.writing_topics.aggregate(
                [
                    {"$match": match_stage},
                    {"$sample": {"size": 1}},
                    {"$project": {"_id": 0, "standard": 0, "created_at": 0}},
                ]
            ).to_list(1)

            return topic[0] if topic else []

        # ───────────────────────────────────────────────
        # Default Manual Filters + Pagination
        # ───────────────────────────────────────────────
        query = {}
        conditions = []  # List to hold all filter conditions
        # Parse comma-separated level-difficulty combinations
        level_filters = []

        if level_beginner:
            difficulties = [
                d.lower().strip() for d in level_beginner.split(",")
            ]  # Convert to lowercase and trim
            level_filters.append(
                {"level": "beginner", "difficulty": {"$in": difficulties}}
            )

        if level_intermediate:
            difficulties = [
                d.lower().strip() for d in level_intermediate.split(",")
            ]  # Convert to lowercase and trim
            level_filters.append(
                {"level": "intermediate", "difficulty": {"$in": difficulties}}
            )

        if level_advanced:
            difficulties = [
                d.lower().strip() for d in level_advanced.split(",")
            ]  # Convert to lowercase and trim
            level_filters.append(
                {"level": "advanced", "difficulty": {"$in": difficulties}}
            )

        # Add level filters to conditions
        if level_filters:
            if len(level_filters) == 1:
                # Single level - add directly to conditions
                conditions.append(level_filters[0])
            else:
                # Multiple levels - use OR within levels, but AND with other filters
                conditions.append({"$or": level_filters})

        # Parse comma-separated status
        if status:
            status_list = [
                s.strip() for s in status.split(",")
            ]  # Clean up status values
            # Only proceed if we have a user_id for status filtering
            if user_id:
                topic_ids_solved = set()
                solved = db.writing_evaluations.find(
                    {"user_id": user_id}, {"topic_id": 1}
                )
                topic_ids_solved = {doc["topic_id"] async for doc in solved}

                status_conditions = []
                has_solved = "solved" in status_list
                has_unsolved = "unsolved" in status_list

                # Handle status combinations
                if has_solved and has_unsolved:
                    # Show all topics (no topic_id filter needed)
                    pass
                elif has_solved:
                    if topic_ids_solved:
                        status_conditions.append(
                            {"topic_id": {"$in": list(topic_ids_solved)}}
                        )
                    else:
                        # No solved topics and only solved filter requested
                        return empty_response(page, page_size)
                elif has_unsolved:
                    if topic_ids_solved:
                        status_conditions.append(
                            {"topic_id": {"$nin": list(topic_ids_solved)}}
                        )
                    # If no solved topics, all are unsolved (no filter needed)

                # Add status conditions to main conditions
                if status_conditions:
                    if len(status_conditions) == 1:
                        conditions.append(status_conditions[0])
                    else:
                        conditions.append({"$or": status_conditions})
            else:
                # If no user_id but status filter is provided, we can't determine solved status
                # So we ignore status filter for anonymous users
                pass

        # Parse comma-separated category
        if category:
            categories = [
                c.strip() for c in category.split(",")
            ]  # Clean up category values
            if len(categories) == 1:
                conditions.append({"category": categories[0]})
            else:
                conditions.append({"category": {"$in": categories}})

        # Build final query with AND relationship
        if conditions:
            if len(conditions) == 1:
                query = conditions[0]
            else:
                query["$and"] = conditions

        # Get paginated topics
        data = await paginate(
            db.writing_topics,
            query,
            {
                "_id": 0,
                "standard": 0,
                "created_at": 0,
            },
            page,
            page_size,
        )

        return data

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Server Error: {str(e)}"},
        )


@router.get("/topics/submissions")
async def get_submissions(user_id: str = Depends(get_current_user)):
    try:
        # Fetch all submissions by user
        submissions = (
            await db.writing_evaluations.find(
                {"user_id": user_id}, {"_id": 0, "user_id": 0, "transcription": 0}
            )
            .sort("submitted_at", -1)
            .to_list(None)
        )

        if not submissions:
            return []

        # Extract all topic_ids from submissions
        topics_ids = [s["topic_id"] for s in submissions]

        # Fetch passage details for these passage_ids
        topics = await db.writing_topics.find(
            {"topic_id": {"$in": topics_ids}},
            {"_id": 0, "topic_id": 1, "title": 1},
        ).to_list(None)

        # Create a quick lookup map: {topic_id: title}
        topic_map = {t["topic_id"]: t["title"] for t in topics}

        # Append title to each submission
        for sub in submissions:
            sub["title"] = topic_map.get(sub["topic_id"], "Unknown Title")

        return submissions

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Server Error: {str(e)}"},
        )


@router.post("/topics")
async def add_topic(topic: WritingTopicIn):
    topic_doc = {
        "topic_id": str(uuid.uuid4()),  # generate UUID
        "category": topic.category,
        "title": topic.title,
        "description": topic.description,
        "difficulty": topic.difficulty,
        "level": topic.level,
        "guidelines": topic.guidelines,
        "created_at": datetime.utcnow(),
    }

    result = await db.writing_topics.insert_one(topic_doc)
    return {**topic_doc, "_id": str(result.inserted_id)}


# Get writing topics
@router.get("/topics/{topic_id}")
async def get_topic(topic_id: str, user_id: str = Depends(get_current_user)):
    try:
        # Fetch topic (only one expected per topic_id)
        topic = await db.writing_topics.find_one(
            {"topic_id": topic_id},
            {"_id": 0, "standard": 0, "audience": 0, "created_at": 0},
        )
        if not topic:
            return JSONResponse(
                status_code=404,
                content={"message": "Topic not found"},
            )

        return topic

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"},
        )


@router.post("/verify")
async def submit_writing(
    answer: WritingAnswer, user_id: str = Depends(get_current_user)
):
    try:
        # 🔍 1. Fetch the topic
        topic = await db.writing_topics.find_one({"topic_id": answer.topic_id})
        if not topic:
            return JSONResponse(
                status_code=404,
                content={"message": "Topic not found"},
            )

        # 🧠 2. Build the LLM evaluation prompt
        prompt = f"""
You are a strict English writing evaluator. Evaluate the student's writing answer based on the topic requirements.

Topic details:
Category: {topic.get('category', 'N/A')}
Title: {topic.get('title', 'N/A')}
Description: {topic.get('description', 'N/A')}
Standard: {topic.get('standard', 'N/A')}
Difficulty: {topic.get('difficulty', 'N/A')}
Audience: {topic.get('audience', 'N/A')}
Guidelines: {topic.get('guidelines', 'None')}

Student's answer:
{answer.your_answer}

CRITICAL SCORING GUIDELINES:
- Incomplete answers (only greetings, single sentences, or fragments) MUST score 0-2
- Answers that don't address the topic at all MUST score 0-1
- Very short answers (less than 50 words) that don't fully address the topic should score 0-3
- Answers lacking proper structure, body paragraphs, or conclusion should score 0-4
- Only award scores 5+ if the answer genuinely attempts to address the topic with substance

Score from 0-10 based on:
1. **Completeness** (30%): Does it fully address the topic? Is it substantive enough?
2. **Relevance** (25%): Does it stay on topic and address the requirements?
3. **Structure** (20%): Does it have proper introduction, body, and conclusion?
4. **Clarity & Grammar** (15%): Is it well-written with correct grammar?
5. **Adherence to Guidelines** (10%): Does it follow the provided guidelines?

Tasks:
1. Assign an overall_score (0-10) following the CRITICAL SCORING GUIDELINES above
2. Provide feedback with:
   - strengths: list of 3 positive points (or note what's missing if answer is incomplete)
   - areas_for_improvement: list of 3 specific improvement points
3. Write a well-structured example answer that properly addresses the topic

IMPORTANT: Be strict. A greeting alone or minimal text is NOT a complete answer and deserves 0-2 points.

Return ONLY valid JSON in this exact structure:
{{
  "overall_score": 0-10,
  "feedback": {{
    "strengths": ["...","...","..."],
    "areas_for_improvement": ["...","...","..."]
  }},
  "example_answer": "..."
}}
"""

        # ⚙️ 3. Call OpenAI model
        llm_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        # 🧾 4. Parse response safely
        try:
            content = llm_response.choices[0].message.content
            evaluation = Evaluation.parse_raw(content)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Invalid response format from evaluator.",
                },
            )

        # 🗃️ 5. Prepare evaluation data
        evaluation_data = {
            "your_answer": answer.your_answer,
            "overall_score": evaluation.overall_score,
            "feedback": evaluation.feedback.dict(),
            "example_answer": evaluation.example_answer,
        }

        # 💾 6. Save evaluation in DB
        record = {
            "user_id": user_id,
            "topic_id": answer.topic_id,
            "evaluation_data": evaluation_data,
            "submitted_at": datetime.utcnow(),
        }

        await db.writing_evaluations.insert_one(record)

        # ✅ 7. Return structured response
        return evaluation_data

    except Exception as e:
        # 🛑 Catch-all for unexpected issues
        return JSONResponse(
            status_code=500,
            content={"message": f"Server error: {str(e)}"},
        )


def empty_response(page: int, page_size: int) -> dict:
    """Return empty paginated response"""
    return {
        "results": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }
