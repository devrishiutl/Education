# routers/speaking.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from bson import ObjectId
from utils.jwt import get_current_user

router = APIRouter(prefix="/speaking", tags=["Speaking"])

# Get speaking exercises
@router.get("/exercises")
async def get_exercises():
    exercises = []
    cursor = db.speaking_exercises.find()
    async for e in cursor:
        e["_id"] = str(e["_id"])
        exercises.append(e)
    return exercises

# Submit speaking answer
@router.post("/submit")
async def submit_speaking(exercise_id: str, audio_url: str, user_id: str = Depends(get_current_user)):
    # Example scoring placeholder
    score = 8.0
    feedback = "Good pronunciation"
    await db.speaking_answers.insert_one({
        "user_id": ObjectId(user_id),
        "exercise_id": ObjectId(exercise_id),
        "audio_url": audio_url,
        "score": score,
        "feedback": feedback
    })
    return {"exercise_id": exercise_id, "score": score, "feedback": feedback}
