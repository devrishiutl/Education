# models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from pydantic_core import core_schema

class PhoneNumber:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()  # treat as string for OpenAPI
        )

    @classmethod
    def validate(cls, v):
         # Try to convert to int (in case it's str like "9876543210")
        try:
            v1 = int(v)
        except (TypeError, ValueError):
            raise ValueError("Phone number must be an integer")

        if not (1000000000 <= v1 <= 9999999999):
            raise ValueError("Phone number must be exactly 10 digits")

        return v

class VerifyPhone(BaseModel):
    phone: PhoneNumber

class UserRegister(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: PhoneNumber
    password: str
    standard: str
    school: str
    city: str
    state: str

class OTPVerify(BaseModel):
    phone: Optional[PhoneNumber] = None
    otp: str

class UserLogin(BaseModel):
    phone_or_email: str
    password: str

class EditProfile(BaseModel):
    name: Optional[str]
    phone_or_email: Optional[str]

class GrammarAnswer(BaseModel):
    question_id: str
    answer: str

class ReadingAnswer(BaseModel):
    story_id: str
    answers: List[GrammarAnswer]  # same format

class WritingAnswer(BaseModel):
    topic_id: str
    answer_text: str

class WritingTopicIn(BaseModel):
    category: str = Field(..., description="Category e.g. letter/article/notice")
    title: str = Field(..., description="Title of the writing topic")
    context: str = Field(..., description="Detailed context for writing")
    standard: int = Field(..., description="Grade/standard")