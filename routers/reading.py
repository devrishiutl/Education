# routers/reading.py
from fastapi import APIRouter, HTTPException, Depends, Query
from database import db
from models import ReadingAnswer
from bson import ObjectId
from utils.jwt import get_current_user
from utils.allFunctions import AllFunctions
from typing import List, Optional

router = APIRouter(prefix="/reading", tags=["Reading"])

# Get stories
# @router.get("/stories/list")
# async def get_stories_list():
#     stories = []
#     cursor = db.reading_passages.find()
#     async for s in cursor:
#         s["_id"] = str(s["_id"])
#         for q in s["questions"]:
#             q["question_id"] = str(q["question_id"])
#         stories.append(s)
#     return stories

# @router.get("/stories")
# async def get_stories_list():
#     stories = []
#     cursor = db.reading_passages.find({}, {"_id": 0, "passage_id": 1, "standard": 1, "title": 1, "difficulty": 1, "passage": 1})
#     async for s in cursor:
#         s["passage"] = s["passage"][:300]+"...."
#         stories.append(s)
#     return stories


@router.get("/passages")
async def get_passages_list(
    page: int,
    page_size: int,
    difficulty: Optional[List[str]] = Query(None),  # multi-select
    level: Optional[List[str]] = Query(None),
):
    # Build dynamic query for MongoDB
    query = {}

    if difficulty:
        if len(difficulty) == 1:
            query["difficulty"] = difficulty[0]  # single value
        else:
            query["difficulty"] = {"$in": difficulty}  # multiple values

    if level:
        if len(level) == 1:
            query["level"] = level[0]
        else:
            query["level"] = {"$in": level}

    data = await AllFunctions().paginate(
        db.reading_passages,
        query,
        {"_id": 0, "questions": 0, "standard": 0, "created_at": 0},
        page,
        page_size,
    )

    # modify passage preview
    for s in data["results"]:
        s["passage"] = s["passage"][:300] + "...."

    return data


@router.get("/stories/{passage_id}")
async def get_stories(passage_id: str):
    stories = []
    cursor = db.reading_passages.find({"passage_id": passage_id})
    async for s in cursor:
        s["_id"] = str(s["_id"])
        for q in s["questions"]:
            del q["answer"]
            del q["explanation"]
        stories.append(s)
    return stories


# Verify reading answers
@router.post("/verify")
async def verify_reading(
    answer: ReadingAnswer, user_id: str = Depends(get_current_user)
):
    # story = await db.reading_passages.find_one({"_id": ObjectId(answer.story_id)})
    story = await db.reading_passages.find_one({"passage_id": answer.story_id})
    if not story:
        raise HTTPException(404, "Story not found")
    results = []
    for ans in answer.answers:
        question = next(
            (q for q in story["questions"] if str(q["question_id"]) == ans.question_id),
            None,
        )
        # if AllFunctions().get_similarity_score(question["answer"], ans.answer) > 0.75:
        #     is_correct = True
        # else:
        #     is_correct = False
        is_correct = (
            question
            and question["answer"].lower().strip() == ans.answer.lower().strip()
        )
        results.append(
            {
                "question_id": ans.question_id,
                "correct": is_correct,
                "question": question["question"],
                "your_answer": ans.answer,
                "correct_answer": question["answer"],
                "explanation": question["explanation"],
            }
        )

    # Save user answers
    await db.reading_answers.insert_one(
        {
            "user_id": ObjectId(user_id),
            "story_id": answer.story_id,
            "answers": [
                {
                    "question_id": r["question_id"],
                    "correct": r["correct"],
                    "your_answer": r["your_answer"],
                }
                for r in results
            ],
        }
    )
    return results


from pydantic import BaseModel
from typing import List, Tuple


class TimestampedChunk(BaseModel):
    text: str
    timestamp: float  # could be end_time of the chunk


class SpeechTestInput(BaseModel):
    story_id: str
    reference_text: str
    reader_chunks: List[TimestampedChunk]  # frontend sends chunked text with timestamp


class SpeechScore(BaseModel):
    pronunciation_score: float
    fluency_score: float
    punctuation_score: float


class SpeechTestResult(BaseModel):
    score: SpeechScore


# Constants
DELTA = 0.3
BETA = 0.2
EXPECTED_GAP = 0.5


# Pronunciation: check word-by-word accuracy
def calculate_pronunciation(chunks, reference_text):
    ref_words = reference_text.strip().split()
    spoken_words = []
    for chunk in chunks:
        spoken_words.extend(chunk.text.strip().split())
    correct = sum(1 for s, r in zip(spoken_words, ref_words) if s.lower() == r.lower())
    return correct / len(ref_words) if ref_words else 0.0


# Fluency: timing difference between chunks
def calculate_fluency(chunks):
    if len(chunks) < 2:
        return 1.0
    total_deviation = 0
    for i in range(len(chunks) - 1):
        gap = chunks[i + 1].timestamp - chunks[i].timestamp
        deviation = max(0, abs(gap - EXPECTED_GAP) - DELTA)
        total_deviation += deviation
    total_expected = (len(chunks) - 1) * EXPECTED_GAP
    return max(0.0, 1 - total_deviation / total_expected)


# Punctuation: check pauses at punctuation positions
def calculate_punctuation(chunks, reference_text):
    punct_positions = [i for i, c in enumerate(reference_text) if c in ".!?,"]
    if not punct_positions:
        return 1.0
    correct_pauses = 0
    # map chunks to words sequentially
    word_idx = 0
    chunk_idx = 0
    ref_words = reference_text.strip().split()
    while chunk_idx < len(chunks) and word_idx < len(ref_words):
        chunk_words = chunks[chunk_idx].text.strip().split()
        for i, w in enumerate(chunk_words):
            if word_idx in punct_positions:
                # check pause before next chunk
                if chunk_idx + 1 < len(chunks):
                    gap = chunks[chunk_idx + 1].timestamp - chunks[chunk_idx].timestamp
                    if gap >= DELTA + BETA:
                        correct_pauses += 1
            word_idx += 1
        chunk_idx += 1
    return correct_pauses / len(punct_positions)


@router.post("/evaluate_chunks", response_model=SpeechTestResult)
async def evaluate_speech_chunks(
    data: SpeechTestInput, user_id: str = Depends(get_current_user)
):
    pronunciation = calculate_pronunciation(data.reader_chunks, data.reference_text)
    fluency = calculate_fluency(data.reader_chunks)
    punctuation = calculate_punctuation(data.reader_chunks, data.reference_text)

    return {
        "score": {
            "pronunciation_score": round(pronunciation, 2),
            "fluency_score": round(fluency, 2),
            "punctuation_score": round(punctuation, 2),
        }
    }
