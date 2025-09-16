# routers/writing.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from models import WritingAnswer, WritingTopicIn
from bson import ObjectId
from datetime import datetime
from utils.jwt import get_current_user
import uuid


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
        "context": topic.context,
        "standard": topic.standard,
        "created_at": datetime.utcnow()
    }

    result = await db.writing_topics.insert_one(topic_doc)
    topic_doc["_id"] = str(result.inserted_id)  # return string for JSON
    return topic_doc

# Submit writing
@router.post("/verify")
async def submit_writing(answer: WritingAnswer, user_id: str = Depends(get_current_user)):
    # Example: simple scoring
    score = min(len(answer.answer_text.split()) / 10, 10)  # 10 points max
    feedback = "Good job" if score > 5 else "Needs improvement"
    await db.writing_answers.insert_one({
        "user_id": user_id,
        "topic_id": answer.topic_id,
        "answer_text": answer.answer_text,
        "score": score,
        "feedback": feedback,
        "submitted_at": datetime.utcnow()
    })
    return {"topic_id": answer.topic_id, "score": score, "feedback": feedback}


