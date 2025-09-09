# routers/auth.py
from fastapi import APIRouter, HTTPException
from models import UserRegister, UserLogin, OTPVerify
from database import db
from passlib.hash import bcrypt
import random
from datetime import datetime, timedelta
from utils.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])

# Register
@router.post("/register")
async def register(user: UserRegister):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(400, "User already exists")
    hashed_password = bcrypt.hash(user.password)
    user_dict = user.dict()
    user_dict["password_hash"] = hashed_password
    user_dict.pop("password")
    user_dict["is_phone_verified"] = False
    user_dict["is_email_verified"] = False
    user_dict["created_at"] = datetime.utcnow()
    user_dict["updated_at"] = datetime.utcnow()
    result = await db.users.insert_one(user_dict)

    user_id = str(result.inserted_id)
    await db.dashboard_usage.insert_one({
    "user_id": user_id, 
    "vocabulary_attempted": 0,
    "grammar_attempted": 0,
    "reading_attempted": 0,
    "writing_attempted": 0,
    "speaking_attempted": 0,
    "last_active": datetime.utcnow()
})
    return {"message": "User registered successfully"}

# Login
@router.post("/login")
async def login(user: UserLogin):
    existing = await db.users.find_one({"email": user.email})
    if not existing or not bcrypt.verify(user.password, existing["password_hash"]):
        raise HTTPException(400, "Invalid credentials")
    
    # ✅ Create JWT token
    token = create_access_token(str(existing["_id"]))
    
    return {
        "message": "Login successful",
        "user_id": str(existing["_id"]),
        "access_token": token,
        "token_type": "bearer"
    }

# Send OTP
@router.post("/send-otp")
async def send_otp(email: str):
    otp = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    await db.otps.insert_one({"email": email, "otp": otp, "expires_at": expires_at, "verified": False})
    return {"message": f"OTP sent to {email}", "otp": otp}  # remove otp in production

# Confirm OTP
@router.post("/confirm-otp")
async def confirm_otp(data: OTPVerify):
    record = await db.otps.find_one({"email": data.email, "otp": data.otp, "verified": False})
    if not record:
        raise HTTPException(400, "Invalid OTP")
    if record["expires_at"] < datetime.utcnow():
        raise HTTPException(400, "OTP expired")
    await db.otps.update_one({"_id": record["_id"]}, {"$set": {"verified": True}})
    await db.users.update_one({"email": data.email}, {"$set": {"is_email_verified": True}})
    return {"message": "OTP verified successfully"}
