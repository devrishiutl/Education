# routers/auth.py
from fastapi import APIRouter, HTTPException, Depends, Body
from models import UserRegister, UserLogin, OTPVerify, PhoneNumber, VerifyPhone
from database import db
from passlib.hash import bcrypt
import random
from datetime import datetime, timedelta
from utils.jwt import create_access_token, get_current_user
from bson import ObjectId
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/auth", tags=["Auth"])


# Register
@router.post("/register")
async def verify_phone(phone: VerifyPhone):
    existing = await db.users.find_one({"phone": phone.phone})
    if existing:
        return JSONResponse(
            status_code=400,
            content={"message": "User already exists"},
        )
    otp = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    existing = await db.otps.find_one({"phone": phone.phone})
    if existing:
        await db.otps.update_one(
            {"phone": phone.phone},
            {"$set": {"otp": otp, "expires_at": expires_at, "verified": False}},
        )
    else:
        await db.otps.insert_one(
            {
                "phone": phone.phone,
                "otp": otp,
                "expires_at": expires_at,
                "verified": False,
            }
        )
    return {
        "message": f"OTP sent to {phone.phone}",
        "otp": otp,
    }  # remove otp in production


# Register
@router.post("/verify-phone")
async def register(user: UserRegister, otp: OTPVerify):
    record = await db.otps.find_one({"phone": user.phone, "verified": False})
    if not record:
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid OTP"},
        )
    if record["expires_at"] < datetime.utcnow():
        return JSONResponse(
            status_code=400,
            content={"message": "OTP expired"},
        )
    await db.otps.update_one({"_id": record["_id"]}, {"$set": {"verified": True}})
    await db.users.update_one(
        {"phone": user.phone}, {"$set": {"is_phone_verified": True}}
    )

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
    await db.dashboard_usage.insert_one(
        {
            "user_id": user_id,
            "vocabulary_attempted": 0,
            "grammar_attempted": 0,
            "reading_attempted": 0,
            "writing_attempted": 0,
            "speaking_attempted": 0,
            "last_active": datetime.utcnow(),
        }
    )
    token = create_access_token(str(result.inserted_id))
    del user_dict["password_hash"]
    del user_dict["_id"]
    return {
        "message": "User registered successfully",
        "token": token,
        "user": user_dict,
    }


# Login
@router.post("/login")
async def login(user: UserLogin):
    # existing = await db.users.find_one({"email": user.email})
    existing = await db.users.find_one(
        {
            "$or": [
                {"email": {"$eq": user.phone_or_email, "$nin": [None, ""]}},
                {"phone": {"$eq": user.phone_or_email, "$nin": [None, ""]}},
            ]
        }
    )
    if not existing or not bcrypt.verify(user.password, existing["password_hash"]):
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid credentials"},
        )

    # ✅ Create JWT token
    token = create_access_token(str(existing["_id"]))
    del existing["password_hash"]
    del existing["_id"]
    return {"message": "Login successful", "token": token, "user": existing}


# Send OTP
@router.post("/send-otp")
async def send_otp(phone: VerifyPhone):
    user = await db.users.find_one({"phone": phone.phone})
    if not user:
        return JSONResponse(
            status_code=400,
            content={"message": "User not found"},
        )
    otp = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    # await db.otps.insert_one({"phone": phone.phone, "otp": otp, "expires_at": expires_at, "verified": False})
    await db.otps.update_one(
        {"phone": phone.phone},
        {"$set": {"otp": otp, "expires_at": expires_at, "verified": False}},
    )
    return {
        "message": f"OTP sent to {phone.phone}",
        "otp": otp,
    }  # remove otp in production


# Confirm OTP
@router.post("/confirm-otp")
async def confirm_otp(data: OTPVerify):
    record = await db.otps.find_one({"phone": data.phone, "verified": False})
    if not record:
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid OTP"},
        )
    if record["expires_at"] < datetime.utcnow():
        return JSONResponse(
            status_code=400,
            content={"message": "OTP expired"},
        )
    await db.otps.update_one({"_id": record["_id"]}, {"$set": {"verified": True}})
    await db.users.update_one(
        {"phone": data.phone}, {"$set": {"is_phone_verified": True}}
    )
    user = await db.users.find_one({"phone": data.phone})
    token = create_access_token(str(user["_id"]))
    return {"message": "OTP verified successfully", "token": token}


@router.post("/update-password")
async def update_password(phone: str = Body(...), password: str = Body(...)):
    user = await db.users.find_one({"phone": phone})
    if not user:
        return JSONResponse(
            status_code=400,
            content={"message": "User not found"},
        )
    hashed_password = bcrypt.hash(password)
    await db.users.update_one(
        {"phone": phone}, {"$set": {"password_hash": hashed_password}}
    )
    return {"message": "Password updated successfully"}
