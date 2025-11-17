# routers/vocabulary.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from bson import ObjectId
from utils.jwt import get_current_user
from utils.allFunctions import paginate

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary"])


# Get all vocabulary
@router.get("/list")
async def get_vocabulary(
    page: int, page_size: int, user_id: str = Depends(get_current_user)
):
    return await paginate(
        db.vocabulary,
        {},
        {"_id": 0, "word": 1, "meaning": 1, "when_to_use": 1, "example": 1},
        page,
        page_size,
    )
