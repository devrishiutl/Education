import os
import uuid
import logging
from typing import List, Dict

from fastapi import FastAPI, HTTPException
# from fastapi.concurrency import run_in_threadpool
from fastapi import Body
from pydantic import BaseModel, Field
from pymongo import MongoClient
from mongodb_client import MongoDBClient
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, MONGO_URI
from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# -------------------------
# Logging
# -------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------------
# Mongo Setup

# mongodb_client = MongoClient(MONGO_URI)
# db = mongodb_client["Education"]
# collection = db["grammar_questions"]
# -------------------------
# LLM Setup
# -------------------------

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY missing in environment")

llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL, temperature=0.3)


class CurriculumEntry(BaseModel):
    standard: int
    topics: List[str]
    question_type: List[str]
    level: List[str]
# -------------------------
# Pydantic Schema
# -------------------------
class GrammarQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    standard: int
    topic: str
    question_type: str
    level: str
    question: str
    options: List[str] = []
    answer: str
    explanation: str


# -------------------------
# LangGraph State
# -------------------------
class State(dict):
    standard: int
    topic: str
    question_type: str
    level: str
    questions: List[Dict]


# -------------------------
# LangGraph Nodes
# -------------------------
def build_prompt(state: State) -> str:
    return f"""
Generate 10 {state['question_type']} grammar questions
for Standard {state['standard']} students.
Topic: {state['topic']}
Difficulty: {state['level']}

Return JSON list with keys: question, options, answer, explanation.
If options not required, return empty list [].
"""


def generate(state: State):
    prompt = build_prompt(state)    
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}   # ✅ Force valid JSON response
    )
    content = response.choices[0].message.content.strip()

    import json
    # response = llm.invoke([{"role": "user", "content": prompt}])
    # content = response.content.strip()

    # 🔹 Remove markdown code fences if present
    if content.startswith("```"):
        content = content.strip("`")
        # Sometimes it's "```json\n...\n```"
        if content.lower().startswith("json"):
            content = content[4:].strip()

    try:
        # questions = json.loads(content)
        data = json.loads(content)
        questions = data["questions"] if isinstance(data, dict) and "questions" in data else data

    except Exception as e:
        logger.error(f"Failed to parse response as JSON. Raw content:\n{response.content}")
        raise

    state["questions"] = questions
    return state


# def save_to_mongo(state: State):
#     records = []
#     for q in state["questions"]:
#         record = GrammarQuestion(
#             standard=state["standard"],
#             topic=state["topic"],
#             question_type=state["question_type"],
#             level=state["level"],
#             question=q.get("question"),
#             options=q.get("options", []),
#             answer=q.get("answer"),
#             explanation=q.get("explanation"),
#         ).dict()
#         records.append(record)

def save_to_mongo(state: State):
    records = []
    for q in state["questions"]:
        record = {
            "id": str(uuid.uuid4()),
            "standard": state["standard"],
            "topic": state["topic"],
            "question_type": state["question_type"],
            "level": state["level"],
            "question": q.get("question"),
            "options": q.get("options", []),
            "answer": q.get("answer"),
            "explanation": q.get("explanation"),
        }
        records.append(record)

    if records:
        from main import app
        app.state.mongodb_client.insert_documents("grammar_questions", records)

    return state  # Only return state for LangGraph



# -------------------------
# Build Graph
# -------------------------
graph = StateGraph(State)
graph.add_node("generate", generate)
graph.add_node("save", save_to_mongo)

graph.set_entry_point("generate")
graph.add_edge("generate", "save")
graph.add_edge("save", END)

app_graph = graph.compile()

# -------------------------
# FastAPI App
# -------------------------






