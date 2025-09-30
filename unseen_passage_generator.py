#!/usr/bin/env python3
"""
Unseen Passage Generator
Generates reading comprehension passages with 5 questions (with answers & explanations).
"""

import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------------
# OpenAI Client
# -------------------------
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY missing in environment")

openai_client = OpenAI(api_key=OPENAI_API_KEY)


# -------------------------
# Pydantic Schemas
# -------------------------
class PassageRequest(BaseModel):
    standard: int
    title: str
    level: str
    difficulty: str
    length: str = "medium"  # short | medium | long


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question: str
    options: List[str] = []
    answer: str
    explanation: str


# class PassageRecord(BaseModel):
#     id: str = Field(default_factory=lambda: str(uuid.uuid4()))
#     standard: int
#     topic: str
#     difficulty: str
#     passage: str
#     questions: List[Question]
#     created_at: datetime = Field(default_factory=datetime.utcnow)


# -------------------------
# Prompt Builder
# -------------------------
def build_passage_prompt(
    standard: int, topic: str, level: str, difficulty: str, length: str
) -> str:
    return f"""
You are an expert educational content creator.  
Generate ONE unseen reading comprehension passage for Standard {standard} students.  

Topic: {topic}  
Level: {level}  
Difficulty: {difficulty}  
Length: {length} (about 250–350 words).  

The passage text must be written in **Markdown** format.  
**Do not include a title or heading** at the top of the passage.  
You may include bold, italics, or bullet points if appropriate.  

Then create exactly 5 comprehension questions.  
Question types must include:  
1. Factual (answer directly in text)  
2. Inference (requires reasoning)  
3. Vocabulary-in-context (define/explain a word from passage)  
4. Main idea / summary  
5. Critical thinking / opinion  

### Output JSON Format (STRICT)
{{
  "passage": "Markdown formatted passage text here (without any title)",
  "questions": [
    {{
      "question": "What ...?",
      "options": ["Option A", "Option B", "Option C", "Option D"],  # [] if open-ended
      "answer": "Correct option text or short answer",
      "explanation": "Brief explanation why this is correct"
    }},
    ...
  ]
}}

- Ensure each question has exactly one correct `answer`.  
- Keep `options` realistic if multiple-choice.  
- All answers must be factually consistent with the passage.  
- The `passage` field must **retain Markdown formatting** when displayed.
"""


# -------------------------
# LangGraph State
# -------------------------
class State(dict):
    standard: int
    title: str
    level: str
    difficulty: str
    length: str
    passage_data: Dict


# -------------------------
# Generator Node
# -------------------------
def generate_passage(state: State):
    prompt = build_passage_prompt(
        state["standard"],
        state["title"],
        state["level"],
        state["difficulty"],
        state["length"],
    )

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content.strip()

    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to parse response as JSON. Raw content:\n{content}")
        raise

    if "questions" not in data or len(data["questions"]) != 5:
        raise ValueError("Invalid response: Expected exactly 5 questions")

    state["passage_data"] = data
    return state


# -------------------------
# Save to Mongo
# -------------------------
def save_to_mongo(state: State):
    data = state["passage_data"]

    record = {
        "passage_id": str(uuid.uuid4()),
        "standard": state["standard"],
        "title": state["title"],
        "level": state["level"],
        "difficulty": state["difficulty"],
        "passage": data["passage"],
        "questions": [
            {
                "question_id": str(uuid.uuid4()),
                "question": q["question"],
                "options": q.get("options", []),
                "answer": q["answer"],
                "explanation": q.get("explanation", ""),
            }
            for q in data["questions"]
        ],
        "created_at": datetime.utcnow(),
    }

    from main import app

    app.state.mongodb_client.insert_documents("reading_passages", [record])

    return state
    # return record


# -------------------------
# Build LangGraph
# -------------------------
graph = StateGraph(State)
graph.add_node("generate", generate_passage)
graph.add_node("save", save_to_mongo)

graph.set_entry_point("generate")
graph.add_edge("generate", "save")
graph.add_edge("save", END)

app_graph = graph.compile()


# -------------------------
# FastAPI App
# -------------------------
# app = FastAPI()


# @app.post("/generate_passage")
# async def generate_passage_endpoint(request: PassageRequest):
#     try:
#         state = {
#             "standard": request.standard,
#             "topic": request.topic,
#             "difficulty": request.difficulty,
#             "length": request.length
#         }
#         result = await app_graph.ainvoke(state)
#         return {"status": "success", "data": result["passage_data"]}
#     except Exception as e:
#         logger.error(str(e))
#         raise HTTPException(status_code=500, detail=str(e))
