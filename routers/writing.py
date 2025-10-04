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
    difficulty: Optional[List[str]] = Query(None),
    level: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    user_id: Optional[str] = Depends(get_current_user),
):
    try:
        # Build base query
        query = {}

        # Helper to handle list-based filters
        def build_array_query(field_name: str, values: Optional[List[str]]):
            if values:
                query[field_name] = values[0] if len(values) == 1 else {"$in": values}

        build_array_query("difficulty", difficulty)
        build_array_query("level", level)
        build_array_query("category", category)

        topic_ids_solved = set()

        # Fetch user's solved topics if logged in
        if user_id:
            solved = db.writing_evaluations.find({"user_id": user_id}, {"topic_id": 1})
            topic_ids_solved = {doc["topic_id"] async for doc in solved}

            # Handle "status" filtering safely
            if status and len(status) == 1:
                status_value = status[0]

                if status_value == "solved":
                    if not topic_ids_solved:
                        return empty_response(page, page_size)
                    query["topic_id"] = {"$in": list(topic_ids_solved)}

                elif status_value == "unsolved":
                    # Faster MongoDB-side filtering using $nin
                    if topic_ids_solved:
                        query["topic_id"] = {"$nin": list(topic_ids_solved)}

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

        # Add solved status field
        for topic in data["results"]:
            topic_id = topic.get("topic_id")
            topic["solved"] = bool(user_id and topic_id in topic_ids_solved)

        return data

    except Exception as e:
        # Catch-all error handling
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
        "standard": topic.standard,
        "difficulty": topic.difficulty,
        "audience": topic.audience,
        "guidelines": topic.guidelines,
        "created_at": datetime.utcnow(),
    }

    result = await db.writing_topics.insert_one(topic_doc)
    topic_doc["_id"] = str(result.inserted_id)  # return string for JSON
    return topic_doc


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
