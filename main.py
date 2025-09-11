from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()  # Load env variables once
import logging
import os
from logging.handlers import RotatingFileHandler
from story_generator import generate_story
import uvicorn
from pdf2image import convert_from_path
import tempfile
from difficult_word import extract_difficult_words, extract_text_from_pdf, expand_word_entries
from fastapi import UploadFile, Form
from typing import List
from mongodb_client import MongoDBClient
from contextlib import asynccontextmanager
from grammar_question_answer import app_graph, CurriculumEntry
from fastapi import Body
from routers import auth, profile, dashboard, vocabulary, grammar, reading, writing, speaking
# from routes import router

from fastapi import FastAPI
# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/story_generator.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
    ]
)
logging.getLogger().handlers[0].setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongodb_client = MongoDBClient()
    try:
        yield
    finally:
        app.state.mongodb_client.close_connection()

app = FastAPI(lifespan=lifespan)
# app.include_router(router)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StoryGeneratorRequest(BaseModel):
    standard: str
    subject: str
    chapter: str
    emotion: str
    story_length: str
    language: str


# mongodb_client = MongoDBClient()  # created once

# @app.on_event("shutdown")
# def shutdown_db_client():
#     print("Closing MongoDB connection...")
#     mongodb_client.close_connection()  # close on app shutdown


# ==================== STORY GENERATOR ENDPOINTS ====================

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(dashboard.router)
app.include_router(vocabulary.router)
app.include_router(grammar.router)
app.include_router(reading.router)
app.include_router(writing.router)
app.include_router(speaking.router)

@app.post("/api/education/story-generator")
async def story_generator(request: StoryGeneratorRequest):
    """Generate a story based on the request"""
    try:
        result = generate_story(request.standard, request.subject, request.chapter, request.emotion, request.story_length, request.language)
        return result
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating story: {str(e)}")


@app.post("/api/education/word-meaning-generator")
async def word_meaning(
    files: List[UploadFile],
    standard: int = Form(...)
) -> dict:
    """Extract text from PDF and generate educational flashcards using PyMuPDF"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    pdf_file = files[0]

    if not pdf_file.filename or not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    file_content = await pdf_file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
        temp_pdf.write(file_content)
        temp_pdf.flush()
        pdf_path = temp_pdf.name

    extracted_text = extract_text_from_pdf(pdf_path)

    try:
        os.unlink(pdf_path)
    except Exception:
        pass

    # 🔹 Step 1: Extract words
    words = extract_difficult_words(extracted_text, standard=standard)
    print(words)

    # 🔹 Step 2: Expand into structured entries
    flashcards = expand_word_entries(words, standard)

    app.state.mongodb_client.insert_documents("vocabulary", flashcards["words"])
    # app.state.mongodb_client.insert_flashcards(flashcards)
    # app.state.mongodb_client.collection.insert_many(flashcards["words"])


    for word in flashcards["words"]:
        word.pop("_id", None)

    return flashcards

@app.post("/api/education/grammar-question-answer-generator")
async def generate_all(curriculum: List[CurriculumEntry] = Body(...)):
    try:
        for entry in curriculum:  # ✅ entry is now CurriculumEntry
            for topic in entry.topics:
                for q_type in entry.question_type:
                    for lvl in entry.level:
                        state = {
                            "standard": entry.standard,
                            "topic": topic,
                            "question_type": q_type,
                            "level": lvl,
                        }
                        print(state)
                        state = app_graph.invoke(state)
                        # app.state.mongodb_client.insert_documents("grammar_questions", state["questions"])
                        # # app.state.mongodb_client.collection.insert_many(records)
                        print("================================================")

        return {"status": "success", "message": "Questions generated and stored in MongoDB"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate grammar questions: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
