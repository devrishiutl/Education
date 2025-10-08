# routers/writing.py
from fastapi import APIRouter, HTTPException, Depends, Query
from database import db
from models import WritingAnswer, WritingTopicIn
from bson import ObjectId
from datetime import datetime
from utils.jwt import get_current_user
import uuid
from utils.allFunctions import AllFunctions
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
    score: int
    feedback: Feedback
    example_answer: str


router = APIRouter(prefix="/writing", tags=["Writing"])


# Get writing topics
@router.get("/topics")
async def get_topics(
    page: int,
    page_size: int,
    level_beginner: Optional[str] = Query(None, alias="level.beginner"),
    level_intermediate: Optional[str] = Query(None, alias="level.intermediate"),
    level_advanced: Optional[str] = Query(None, alias="level.advanced"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user_id: Optional[str] = Depends(get_current_user),
):
    try:
        # Build base query with AND relationship
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
        data = await AllFunctions().paginate(
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

        # Add solved status field if user is logged in
        if user_id:
            # Reuse the solved topics we already fetched, or fetch if not available
            if "topic_ids_solved" not in locals():
                topic_ids_solved = set()
                solved = db.writing_evaluations.find(
                    {"user_id": user_id}, {"topic_id": 1}
                )
                topic_ids_solved = {doc["topic_id"] async for doc in solved}

            for topic in data["results"]:
                topic_id = topic.get("topic_id")
                topic["solved"] = topic_id in topic_ids_solved
        else:
            # For anonymous users, mark all as unsolved
            for topic in data["results"]:
                topic["solved"] = False

        return data

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

        ## Check if topic is solved by this user
        solved = await db.writing_evaluations.find_one(
            {"user_id": user_id, "topic_id": topic_id},
            {"evaluation_data": 1},  # projection
        )

        topic["solved"] = bool(solved)
        topic["evaluation_data"] = solved.get("evaluation_data") if solved else None

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
You are an English writing evaluator.
The topic details are:
Category: {topic.get('category', 'N/A')}
Title: {topic.get('title', 'N/A')}
Description: {topic.get('description', 'N/A')}
Standard: {topic.get('standard', 'N/A')}
Difficulty: {topic.get('difficulty', 'N/A')}
Audience: {topic.get('audience', 'N/A')}
Guidelines: {topic.get('guidelines', 'None')}

Student's answer:
{answer.your_answer}

Tasks:
1. Score the answer from 0 to 10 based on relevance, clarity, grammar, structure, and adherence to guidelines.
2. Give feedback with two lists:
   - strengths: list of 3 positive points
   - areas_for_improvement: list of 3 improvement points
3. Provide a well-written example answer.

Return JSON in this structure:
{{
  "score": 0-10,
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
            "score": evaluation.score,
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
