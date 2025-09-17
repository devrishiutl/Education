# routers/vocabulary.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from bson import ObjectId
from utils.jwt import get_current_user
from utils.allFunctions import AllFunctions

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary"])

# Get all vocabulary
@router.get("/")
async def get_vocabulary(page: int, page_size: int, user_id: str = Depends(get_current_user)):
    vocab = []
    return await AllFunctions().paginate(
        db.vocabulary,
        {},
        {"_id": 0, "word": 1, "meaning": 1, "where_to_use": 1, "example": 1},
        page,
        page_size
    )

# # Get all vocabulary
# @router.get("/")
# async def get_vocabulary(user_id: str = Depends(get_current_user)):
#     vocab = []
#     cursor = db.vocabulary.find()
#     async for v in cursor:
#         v["_id"] = str(v["_id"])
#         vocab.append(v)
#     return vocab

# # Add new word
# @router.post("/")
# async def add_word(word: str, meaning: str, example: str = "", level: str = "beginner"):
#     doc = {"word": word, "meaning": meaning, "example": example, "level": level, "users_attempted": []}
#     await db.vocabulary.insert_one(doc)
#     return {"message": "Word added successfully"}

# # Mark word as learned for user
# @router.put("/learn/{word_id}")
# async def mark_learned(word_id: str, user_id: str = Depends(get_current_user)):
#     word = await db.vocabulary.find_one({"_id": ObjectId(word_id)})
#     if not word:
#         raise HTTPException(404, "Word not found")
#     updated_users = [u for u in word.get("users_attempted", []) if str(u["user_id"]) != user_id]
#     updated_users.append({"user_id": ObjectId(user_id), "status": "learned"})
#     await db.vocabulary.update_one({"_id": ObjectId(word_id)}, {"$set": {"users_attempted": updated_users}})
#     return {"message": "Marked as learned"}
