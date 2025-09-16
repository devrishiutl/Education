# routers/writing.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from models import WritingAnswer, WritingTopicIn
from bson import ObjectId
from datetime import datetime
from utils.jwt import get_current_user
import uuid
import json


router = APIRouter(prefix="/writing", tags=["Writing"])

# Get writing topics
@router.get("/topics")
async def get_topics():
    topics = []
    cursor = db.writing_topics.find()
    async for t in cursor:
        t["_id"] = str(t["_id"])
        topics.append(t)
    return topics

@router.post("/topics")
async def add_topic(topic: WritingTopicIn):
    topic_doc = {
        "topic_id": str(uuid.uuid4()),  # generate UUID
        "category": topic.category,
        "title": topic.title,
        "description": topic.description,
        "standard": topic.standard,
        "difficulty": topic.difficulty,
        "guidelines": topic.guidelines,
        "created_at": datetime.utcnow()
    }

    result = await db.writing_topics.insert_one(topic_doc)
    topic_doc["_id"] = str(result.inserted_id)  # return string for JSON
    return topic_doc

# Submit writing
# @router.post("/verify")
# async def submit_writing(answer: WritingAnswer, user_id: str = Depends(get_current_user)):
#     # Example: simple scoring
#     score = min(len(answer.your_answer.split()) / 10, 10)  # 10 points max
#     feedback = "Good job" if score > 5 else "Needs improvement"
#     await db.writing_answers.insert_one({
#         "user_id": user_id,
#         "topic_id": answer.topic_id,
#         "your_answer": answer.your_answer,
#         "score": score,
#         "feedback": feedback,
#         "submitted_at": datetime.utcnow()
#     })
#     return {"topic_id": answer.topic_id, "score": score, "feedback": feedback}


from openai import AsyncOpenAI

client = AsyncOpenAI()

@router.post("/verify")
async def submit_writing(answer: WritingAnswer, user_id: str = Depends(get_current_user)):
    # 🔍 Find the topic
    topic = await db.writing_topics.find_one({"topic_id": answer.topic_id})
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # 🧠 Use LLM for scoring + feedback
    prompt = f"""
You are an English writing evaluator.  
The topic details are:
Category: {topic['category']}
Title: {topic['title']}
Description: {topic['description']}
Standard: {topic['standard']}
Difficulty: {topic['difficulty']}
Guidelines: {topic.get('guidelines', 'None')}

Student's answer:
{answer.your_answer}

Tasks:
1. Score the answer from 0 to 10 based on relevance, clarity, grammar, structure, and adherence to guidelines.  
2. Give feedback highlighting strengths and areas for improvement.  
3. Provide a well-written example answer for this topic.
Return JSON with keys: score, feedback, example_answer.
"""

    llm_response = await client.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-4o" if you want best quality
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )

    evaluation = llm_response.choices[0].message.content
    evaluation = json.loads(evaluation)  # parse JSON


    # 💾 Save to DB
    await db.writing_answers.insert_one({
        "user_id": user_id,
        "topic_id": answer.topic_id,
        "your_answer": answer.your_answer,
        "score": evaluation["score"],
        "feedback": evaluation["feedback"],
        "example_answer": evaluation["example_answer"],
        "submitted_at": datetime.utcnow()
    })

    return evaluation



