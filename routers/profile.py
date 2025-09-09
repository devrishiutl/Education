# routers/profile.py
from fastapi import APIRouter, HTTPException, Depends
from models import EditProfile
from database import db
from bson import ObjectId
from datetime import datetime
from utils.jwt import get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("")
async def get_profile(user_id: str = Depends(get_current_user)):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(404, "User not found")
    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)
    return user

@router.put("")
async def edit_profile(profile: EditProfile, user_id: str = Depends(get_current_user)):
    update_data = {k: v for k, v in profile.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    result = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    if result.modified_count == 0:
        raise HTTPException(400, "Nothing to update")
    return {"message": "Profile updated successfully"}
