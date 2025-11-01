# routers/dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from database import db
from utils.jwt import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/submission-count")
async def get_submission_counts(user_id: str = Depends(get_current_user)):
    try:
        reading_count = await db.reading_evaluations.count_documents(
            {"user_id": user_id}
        )
        writing_count = await db.writing_evaluations.count_documents(
            {"user_id": user_id}
        )
        speaking_count = await db.speaking_evaluations.count_documents(
            {"user_id": user_id}
        )

        return {
            "reading": reading_count,
            "writing": writing_count,
            "speaking": speaking_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")
