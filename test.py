# app.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_openai import OpenAI
import asyncio
import os
from dotenv import load_dotenv
# routers/auth.py
from fastapi import APIRouter, HTTPException, Depends, Body
from models import UserRegister, UserLogin, OTPVerify, PhoneNumber, VerifyPhone
from database import db
from passlib.hash import bcrypt
import random
from datetime import datetime, timedelta
from utils.jwt import create_access_token, get_current_user
from bson import ObjectId
from fastapi import UploadFile, File
import tempfile
from mistralai import Mistral

router = APIRouter(prefix="/test", tags=["Test"])
load_dotenv()


# Initialize LLM
llm = OpenAI(model="gpt-4o-mini", temperature=0, max_tokens=512)


# -------------------------------
# Sync-style streaming (llm.stream)
# -------------------------------
@router.get("/sync_stream")
def sync_stream():
    def generate():
        for chunk in llm.stream("Write me a 1 verse song about sparkling water."):
            yield chunk
    return StreamingResponse(generate(), media_type="text/plain")


# -------------------------------
# Async streaming (llm.astream)
# -------------------------------
@router.get("/async_stream")
async def async_stream():
    async def generate():
        async for chunk in llm.astream("Write me a 1 verse song about sparkling water."):
            yield chunk
    return StreamingResponse(generate(), media_type="text/plain")

# -------------------------------
# Async event streaming (llm.astream_events)
# -------------------------------
@router.get("/async_event_stream")
async def async_event_stream():
    async def generate():
        idx = 0
        async for event in llm.astream_events(
            "Write me a 1 verse song about goldfish on the moon", version="v1"
        ):
            if event["event"] == "on_llm_stream":
                yield event["data"]["chunk"]
                idx += 1
            if idx >= 50:  # truncate for demo
                yield "\n...Truncated"
                break
    return StreamingResponse(generate(), media_type="text/plain")


# Initialize Mistral client

mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))


def upload_file(file_path: str) -> str:
    """Upload file to Mistral and return signed URL."""
    with open(file_path, "rb") as f:
        uploaded = mistral_client.files.upload(
            file={"file_name": os.path.basename(file_path), "content": f},
            purpose="ocr"
        )
    signed_url = mistral_client.files.get_signed_url(file_id=uploaded.id)
    return signed_url.url

def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image using Mistral OCR."""
    image_url = upload_file(image_path)
    response = mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": image_url},
        include_image_base64=False
    )
    return "\n\n".join(page.markdown for page in response.pages).strip()

@router.post("/ocr-image")
async def ocr_image(file: UploadFile = File(...)):
    """Upload an image and return extracted text"""
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400, detail="Only .jpg/.jpeg/.png supported")

    try:
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
            temp.write(await file.read())
            temp_path = temp.name

        # Extract text
        text = extract_text_from_image(temp_path)
        os.unlink(temp_path)  # cleanup temp file
        return {"filename": file.filename, "text": text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")


from pydantic import BaseModel, create_model, ValidationError
from typing import Any, Dict, List, Type, Optional
from openai import AsyncOpenAI
import json

openai_client = AsyncOpenAI()

# Request model
class DynamicRequest(BaseModel):
    prompt: str
    content: str
    json_format: Optional[Dict[str, Any]] = None

# Helper to create dynamic Pydantic model
# def gen_model(name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
#     fields = {}
#     for k, v in schema.items():
#         if isinstance(v, dict):
#             fields[k] = (gen_model(f"{k}Model", v), ...)
#         elif isinstance(v, list) and v and isinstance(v[0], str):
#             fields[k] = (List[str], ...)
#         elif isinstance(v, int): fields[k] = (int, ...)
#         elif isinstance(v, float): fields[k] = (float, ...)
#         elif isinstance(v, str): fields[k] = (str, ...)
#         else: fields[k] = (Any, ...)
#     return create_model(name, **fields)

def gen_model(name: str, schema: Dict[str, Any]) -> BaseModel:
    fields = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            # recursively create submodel
            sub_model = gen_model(f"{name}_{key.capitalize()}", value)
            fields[key] = (sub_model, ...)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # list of objects
            sub_model = gen_model(f"{name}_{key.capitalize()}", value[0])
            fields[key] = (List[sub_model], ...)
        else:
            # primitive type (int, str, list of str, etc.)
            fields[key] = (type(value), ...)
    return create_model(name, **fields)

# Helper to call LLM
async def call_llm(prompt: str) -> str:
    resp = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return resp.choices[0].message.content

# Helper to validate output
def validate_output(output: str, model: Type[BaseModel]) -> BaseModel:
    data = json.loads(output)
    return model(**data)

# API endpoint
@router.post("/dynamic-verify")
async def dynamic_verify(req: DynamicRequest):
    Model = gen_model("DynamicModel", req.json_format)
    base_prompt = f"{req.prompt}\nContent:\n{req.content}\nReturn strictly in this JSON format:\n{json.dumps(req.json_format, indent=2)}"

    try:
        raw = await call_llm(base_prompt)
        return validate_output(raw, Model).dict()
    except Exception:
        # Retry once with repair
        repair_prompt = f"Fix this JSON to exactly match the schema:\n{json.dumps(req.json_format)}\nInvalid output:\n{raw if 'raw' in locals() else 'N/A'}"
        raw2 = await call_llm(repair_prompt)
        try:
            return validate_output(raw2, Model).dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"JSON validation failed: {e}")
        



