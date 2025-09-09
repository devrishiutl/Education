# models.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str]

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class EditProfile(BaseModel):
    name: Optional[str]
    phone: Optional[str]

class GrammarAnswer(BaseModel):
    question_id: str
    answer: str

class ReadingAnswer(BaseModel):
    story_id: str
    answers: List[GrammarAnswer]  # same format

class WritingAnswer(BaseModel):
    topic_id: str
    answer_text: str
