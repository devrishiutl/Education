# routers/dashboard.py
from fastapi import APIRouter, HTTPException, Depends
from database import db
from bson import ObjectId
from utils.jwt import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Get usage stats
@router.get("")
async def get_dashboard(user_id: str = Depends(get_current_user)):
    stats = await db.dashboard_usage.find_one({"user_id": str(user_id)})
    # if not stats:
    #     # Initialize if not exists
    #     stats_doc = {
    #         "user_id": ObjectId(user_id),
    #         "vocabulary_attempted": 0,
    #         "grammar_attempted": 0,
    #         "reading_attempted": 0,
    #         "writing_attempted": 0,
    #         "speaking_attempted": 0
    #     }
    #     await db.dashboard_usage.insert_one(stats_doc)
    #     return stats_doc
    stats["_id"] = str(stats["_id"])
    # stats["user_id"] = str(stats["user_id"])
    return stats

# # Update usage
# @router.put("/{user_id}")
# async def update_dashboard(vocabulary: int = 0, grammar: int = 0, reading: int = 0, writing: int = 0, speaking: int = 0,user_id: str = Depends(get_current_user)):
#     result = await db.dashboard_usage.update_one(
#         {"user_id": ObjectId(user_id)},
#         {"$inc": {
#             "vocabulary_attempted": vocabulary,
#             "grammar_attempted": grammar,
#             "reading_attempted": reading,
#             "writing_attempted": writing,
#             "speaking_attempted": speaking
#         }}
#     )
#     if result.matched_count == 0:
#         raise HTTPException(404, "User dashboard not found")
#     return {"message": "Dashboard updated successfully"}
