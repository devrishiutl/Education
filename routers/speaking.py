# routers/speaking.py
from fastapi import APIRouter, Depends, Query
from database import db
from models import (
    SpeakingTopic,
    SpeakingVerificationRequest,
    SpeakingLLMEvaluation,
)
from datetime import datetime
from utils.jwt import get_current_user
import uuid
from utils.allFunctions import AllFunctions
from typing import Optional
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

# Initialize OpenAI client
client = AsyncOpenAI()

router = APIRouter(prefix="/speaking", tags=["Speaking"])


# Get writing topics
@router.get("/topics")
async def get_topics(
    page: int,
    page_size: int,
    level_beginner: Optional[str] = Query(None, alias="level.beginner"),
    level_intermediate: Optional[str] = Query(None, alias="level.intermediate"),
    level_advanced: Optional[str] = Query(None, alias="level.advanced"),
    status: Optional[str] = Query(None),
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
                solved = db.speaking_evaluations.find(
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

        # Build final query with AND relationship
        if conditions:
            if len(conditions) == 1:
                query = conditions[0]
            else:
                query["$and"] = conditions

        # Get paginated topics
        data = await AllFunctions().paginate(
            db.speaking_topics,
            query,
            {
                "_id": 0,
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


@router.post("/topics")
async def add_topic(topic: SpeakingTopic):
    topic_doc = {
        "topic_id": str(uuid.uuid4()),  # generate UUID
        "title": topic.title,
        "description": topic.description,
        "difficulty": topic.difficulty,
        "level": topic.level,
        "created_at": datetime.utcnow(),
    }

    result = await db.speaking_topics.insert_one(topic_doc)
    return {**topic_doc, "_id": str(result.inserted_id)}


@router.get("/topics/submissions")
async def get_submissions(user_id: str = Depends(get_current_user)):
    try:
        # Fetch all submissions by user
        submissions = await db.speaking_evaluations.find(
            {"user_id": user_id}, {"_id": 0, "user_id": 0, "transcription": 0}
        ).to_list(None)

        if not submissions:
            return []

        # Extract all topic_ids from submissions
        topics_ids = [s["topic_id"] for s in submissions]

        # Fetch passage details for these passage_ids
        topics = await db.speaking_topics.find(
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


# Get speaking topics
@router.get("/topics/{topic_id}")
async def get_topic(topic_id: str, user_id: str = Depends(get_current_user)):
    try:
        # Fetch topic (only one expected per topic_id)
        topic = await db.speaking_topics.find_one(
            {"topic_id": topic_id},
            {"_id": 0, "created_at": 0},
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
async def verify_speaking(
    request: SpeakingVerificationRequest, user_id: str = Depends(get_current_user)
):
    """
    Evaluate speaking skills based on transcription data using LLM
    """
    try:
        # Verify topic exists
        topic = await db.speaking_topics.find_one(
            {"topic_id": request.topic_id}, {"_id": 0, "created_at": 0}
        )

        if not topic:
            return JSONResponse(status_code=404, content={"message": "Topic not found"})

        # Combine transcription text
        full_text = " ".join([segment.text for segment in request.transcription])

        # Calculate speaking metrics
        total_time = max([segment.endTime for segment in request.transcription]) - min(
            [segment.startTime for segment in request.transcription]
        )
        word_count = len(full_text.split())
        wpm = (word_count / total_time) * 60 if total_time > 0 else 0

        # Build LLM evaluation prompt
        prompt = f"""
You are an expert English speaking skills evaluator. Evaluate the student's speaking performance based on the transcription data.

Topic Details:
Title: {topic.get('title', 'N/A')}
Description: {topic.get('description', 'N/A')}
Level: {topic.get('level', 'N/A')}
Difficulty: {topic.get('difficulty', 'N/A')}

Student's Spoken Response:
"{full_text}"

Speaking Metrics:
- Words per minute: {wpm:.1f}
- Total speaking time: {total_time:.1f} seconds
- Word count: {word_count}

Evaluation Criteria:
1. Fluency (0-10): Speaking pace, rhythm, natural flow, pauses
2. Pronunciation (0-10): Clarity, accuracy of sounds, word stress
3. Content Relevance (0-10): How well the response addresses the topic
4. Overall Score (0-10): Overall speaking performance

Tasks:
1. Score each criterion from 0 to 10
2. Provide detailed feedback explaining the scores
3. List 3 strengths and 3 areas for improvement
4. Provide an example response for this topic

Return JSON in this exact structure:
{{
  "fluency_score": 0-10,
  "pronunciation_score": 0-10,
  "content_relevance_score": 0-10,
  "overall_score": 0-10,
  "feedback": {{
    "strengths": ["strength1", "strength2", "strength3"],
    "areas_for_improvement": ["improvement1", "improvement2", "improvement3"]
  }},
  "detailed_feedback": "Detailed explanation of the evaluation...",
  "example_response": "Example response for this topic..."
}}
"""

        # Call OpenAI model
        llm_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        # Parse response safely
        try:
            content = llm_response.choices[0].message.content
            evaluation = SpeakingLLMEvaluation.parse_raw(content)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"message": "Invalid response format from evaluator."},
            )

        # Store evaluation in database
        evaluation_doc = {
            "user_id": user_id,
            "topic_id": request.topic_id,
            "evaluation_data": evaluation.dict(),
            "transcription": [segment.dict() for segment in request.transcription],
            "submitted_at": datetime.utcnow(),
        }

        await db.speaking_evaluations.insert_one(evaluation_doc)

        return evaluation

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred during evaluation: {str(e)}"},
        )


def empty_response(page: int, page_size: int) -> dict:
    """Return empty paginated response"""
    return {
        "results": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }
