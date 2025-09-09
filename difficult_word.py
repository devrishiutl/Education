import os
import json
from typing import Dict
from fastapi import FastAPI, UploadFile, HTTPException
# from mistralai import Mistral
from trustcall import create_extractor
from langchain_openai import ChatOpenAI
# from dotenv import load_dotenv
import uvicorn
from pydantic import BaseModel, Field
import fitz
import logging
from typing import List, Dict
import re
import uuid
from config import llm
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------------
# Load environment variables
# -------------------------
# # load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# if not OPENAI_API_KEY:
#     raise ValueError("OPENAI_API_KEY is missing in .env")

# -------------------------
# Pydantic Schema for Validation
# -------------------------
class WordEntry(BaseModel):
    id: str = Field(..., description="The unique identifier for the word entry")
    standard: int = Field(..., description="The grade level this word is suitable for")
    word: str = Field(..., description="The vocabulary word")
    meaning: str = Field(..., description="The meaning of the word in simple terms")
    when_to_use: str = Field(..., description="Guidance on when and how to use this word appropriately")
    example: List[str] = Field(
        ..., description="At least 10 example sentences showing how the word is used", min_items=10
    )

class WordsResponse(BaseModel):
    words: List[WordEntry] = Field(
        ..., description="List of extracted word entries", min_items=1
    )


# # Wrap OpenAI in LangChain’s ChatOpenAI
# llm = ChatOpenAI(
#     api_key=OPENAI_API_KEY,
#     model=OPENAI_MODEL,
#     temperature=0.3
# )

# Create extractor with new schema
extractor = create_extractor(
    llm,
    tools=[WordEntry],
    tool_choice="WordEntry"
)

def extract_difficult_words(text: str, standard: int = 1) -> WordsResponse:
# def extract_difficult_words(text: str, grade: int = 1) -> list[str]:
    """
    Step 1: Extract ALL difficult words from text for a given grade.
    """
    system_msg = (
        f"List all words in the text that would be difficult for Grade {standard} students. "
        "Return only a clean JSON list of words, no explanations."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": text}
    ]

    result = llm.invoke(messages)
    raw = result.content.strip()

    # 🚀 clean markdown fences if present
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()

    try:
        return json.loads(raw)
    except:
        return [w.strip().strip('"') for w in raw.strip("[]").split(",") if w.strip()]


def expand_word_entries(words: List[str], standard: int) -> dict:
    """
    Expand each word into structured entries for the given grade.
    Each entry gets a unique UUID4 as 'id'.
    Returns a JSON-serializable dict compatible with FastAPI.
    """
    word_entries: List[WordEntry] = []

    for word in words:
        prompt = (
            f"For Grade {standard}, create an entry for the word '{word}' with:\n"
            "- meaning\n- when_to_use\n- exactly 10 example sentences"
        )
        messages = [{"role": "user", "content": prompt}]
        result = extractor.invoke({"messages": messages})
        responses = result.get("responses")

        if isinstance(responses, list):
            for r in responses:
                entry_dict = r.model_dump() if isinstance(r, WordEntry) else r
                if not isinstance(entry_dict, dict):
                    logger.warning(f"Unexpected list item type: {type(r)}")
                    continue
                entry_dict["id"] = str(uuid.uuid4())
                word_entries.append(WordEntry(**entry_dict))

        elif isinstance(responses, dict):
            responses["id"] = str(uuid.uuid4())
            word_entries.append(WordEntry(**responses))

        elif isinstance(responses, WordEntry):
            entry_dict = responses.model_dump()
            entry_dict["id"] = str(uuid.uuid4())
            word_entries.append(WordEntry(**entry_dict))

        else:
            logger.warning(f"Unexpected response type: {type(responses)}")

    # Wrap in WordsResponse before returning
    words_model = WordsResponse(words=word_entries)
    return words_model.model_dump()

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using PyMuPDF"""
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise
    return text
