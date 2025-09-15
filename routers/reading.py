# routers/reading.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from models import ReadingAnswer
from bson import ObjectId
from utils.jwt import get_current_user
from utils.allFunctions import AllFunctions
router = APIRouter(prefix="/reading", tags=["Reading"])

# Get stories
@router.get("/stories")
async def get_stories():
    stories = []
    cursor = db.reading_passages.find()
    async for s in cursor:
        s["_id"] = str(s["_id"])
        for q in s["questions"]:
            q["question_id"] = str(q["question_id"])
        stories.append(s)
    return stories

# Verify reading answers
@router.post("/verify")
async def verify_reading(answer: ReadingAnswer, user_id: str = Depends(get_current_user)):
    # story = await db.reading_passages.find_one({"_id": ObjectId(answer.story_id)})
    story = await db.reading_passages.find_one({"passage_id": answer.story_id})
    if not story:
        raise HTTPException(404, "Story not found")
    results = []
    for ans in answer.answers:
        question = next((q for q in story["questions"] if str(q["question_id"]) == ans.question_id), None)
        # if AllFunctions().get_similarity_score(question["answer"], ans.answer) > 0.75:
        #     is_correct = True
        # else:
        #     is_correct = False
        is_correct = question and question["answer"] == ans.answer
        results.append({"question_id": ans.question_id, "correct": is_correct})
    # Save user answers
    await db.reading_answers.insert_one({
        "user_id": ObjectId(user_id),
        # "story_id": ObjectId(answer.story_id),
        "story_id": answer.story_id,
        "answers": results
    })
    return results
