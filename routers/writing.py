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
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Depends(get_current_user),
):
    # Build base query
    query = {}

    # Helper function for array fields
    def build_array_query(field_name, values):
        if values:
            query[field_name] = values[0] if len(values) == 1 else {"$in": values}

    build_array_query("difficulty", difficulty)
    build_array_query("level", level)

    data = await AllFunctions().paginate(
        db.writing_topics,
        query,
        {"_id": 0, "standard": 0, "audience": 0, "created_at": 0},
        page,
        page_size,
    )
    return data


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
    # 🔍 Find the topic
    topic = await db.writing_topics.find_one({"topic_id": answer.topic_id})
    if not topic:
        return JSONResponse(
            status_code=404,
            content={"message": "Topic not found"},
        )

    # 🧠 Prompt
    prompt = f"""
You are an English writing evaluator.  
The topic details are:
Category: {topic['category']}
Title: {topic['title']}
Description: {topic['description']}
Standard: {topic['standard']}
Difficulty: {topic['difficulty']}
Audience: {topic['audience']}
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

    llm_response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    try:
        evaluation = Evaluation.parse_raw(llm_response.choices[0].message.content)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"},
        )

    evaluation_data = {
        "your_answer": answer.your_answer,
        "score": evaluation.score,
        "feedback": evaluation.feedback.dict(),
        "example_answer": evaluation.example_answer,
    }

    # 💾 Save in DB with required format
    record = {
        "user_id": user_id,
        "topic_id": answer.topic_id,
        "evaluation_data": evaluation_data,
        "submitted_at": datetime.utcnow(),
    }

    await db.writing_evaluations.insert_one(record)

    return evaluation_data
