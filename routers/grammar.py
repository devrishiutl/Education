# routers/grammar.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from models import GrammarAnswer
from bson import ObjectId
from utils.jwt import get_current_user
from datetime import datetime

router = APIRouter(prefix="/grammar", tags=["Grammar"])

# Get all questions
@router.get("/questions")
async def get_questions(user_id: str = Depends(get_current_user)):
    questions = []
    cursor = db.grammar_questions.find()
    async for q in cursor:
        q["_id"] = str(q["_id"])
        questions.append(q)
    return questions

# Verify answer
@router.post("/verify")
async def verify_answer(answer: GrammarAnswer, user_id: str = Depends(get_current_user)):
    question = await db.grammar_questions.find_one({"_id": ObjectId(answer.question_id)})
    if not question:
        raise HTTPException(404, "Question not found")
    is_correct = question["answer"].lower().strip() == answer.answer.lower().strip()
    # Save user answer
    await db.grammar_answers.insert_one({
        "user_id": ObjectId(user_id),
        "question_id": ObjectId(answer.question_id),
        "answer": answer.answer,
        "is_correct": is_correct
    })

    # ✅ Increment grammar_attempted in dashboard_usage
    await db.dashboard_usage.update_one(
        {"user_id": str(user_id)},
        {"$inc": {"grammar_attempted": 1}, "$set": {"last_active": datetime.utcnow()}}
    )
    return {"question_id": answer.question_id, "correct": is_correct, "correct_answer": question["answer"],"explanation": question["explanation"]}
