# routers/reading.py
from fastapi import APIRouter, HTTPException, Depends, Query
from database import db
from models import ReadingAnswer, ReadingEvaluation, AudioSegment
from bson import ObjectId
from utils.jwt import get_current_user
from utils.allFunctions import AllFunctions
from typing import List, Optional
import math
import re

router = APIRouter(prefix="/reading", tags=["Reading"])


@router.get("/passages")
async def get_passages_list(
    page: int,
    page_size: int,
    difficulty: Optional[List[str]] = Query(None),
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
    story = await db.reading_passages.find_one({"passage_id": answer.story_id})
    if not story:
        raise HTTPException(404, "Story not found")
    results = []
    for ans in answer.answers:
        question = next(
            (q for q in story["questions"] if str(q["question_id"]) == ans.question_id),
            None,
        )
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


# Evaluate reading skills from audio data
@router.post("/evaluate-reading")
async def evaluate_reading_skills(
    evaluation: ReadingEvaluation, user_id: str = Depends(get_current_user)
):
    """
    Evaluate reading skills based on audio data and passage content
    Returns score out of 10 with detailed breakdown
    """
    # Get the passage
    passage = await db.reading_passages.find_one({"passage_id": evaluation.passage_id})
    if not passage:
        raise HTTPException(404, "Passage not found")

    # Evaluate reading skills
    result = await evaluate_reading_skills_internal(passage, evaluation.audio_data)

    # Save evaluation result
    await db.reading_evaluations.insert_one(
        {
            "user_id": ObjectId(user_id),
            "passage_id": evaluation.passage_id,
            "evaluation_data": result,
            "audio_segments": [segment.dict() for segment in evaluation.audio_data],
        }
    )

    return result


async def evaluate_reading_skills_internal(passage, audio_data):
    """
    Internal function to evaluate reading skills
    """
    # Input validation
    if not audio_data or len(audio_data) == 0:
        return get_empty_evaluation_result("No audio data provided")

    # Filter out empty segments and validate timestamps
    valid_segments = []
    for segment in audio_data:
        if hasattr(segment, "dict"):
            segment_data = segment.dict()
        else:
            segment_data = segment

        if segment_data["text"] and segment_data["text"].strip():
            # Validate timestamps
            if (
                segment_data["endTime"] > segment_data["startTime"]
                and segment_data["startTime"] >= 0
            ):
                valid_segments.append(segment_data)

    if len(valid_segments) == 0:
        return get_empty_evaluation_result("No valid audio segments")

    try:
        # 1. Accuracy Evaluation (40% - 4 points)
        accuracy_result = evaluate_accuracy(passage["passage"], valid_segments)

        # 2. Fluency Evaluation (40% - 4 points)
        fluency_result = evaluate_fluency(valid_segments)

        # 3. consistency (20% - 2 points)
        consistency_result = evaluate_consistency(valid_segments)

        # Calculate total score out of 10
        total_score = (
            accuracy_result["score"]
            + fluency_result["score"]
            + consistency_result["score"]
        )

        # Generate feedback
        feedback = generate_feedback(
            accuracy_result, fluency_result, consistency_result, total_score
        )

        return {
            "score": round(total_score, 1),
            "scoreBreakdown": {
                "accuracy": round(accuracy_result["score"], 1),
                "fluency": round(fluency_result["score"], 1),
                "consistency": round(consistency_result["score"], 1),
            },
            "detailedMetrics": {
                "accuracy": f"{accuracy_result['correct_words']}/{accuracy_result['total_words']} words correct ({accuracy_result['accuracy_percentage']:.1f}%)",
                "fluency": f"{fluency_result['words_per_minute']:.0f} words per minute",
                "consistency": f"Pacing variation: {consistency_result['consistency']:.3f}s",  # New metric
            },
            "feedback": feedback,
            "level": get_performance_level(total_score),
        }

    except Exception as e:
        return get_empty_evaluation_result(f"Evaluation error: {str(e)}")


def get_empty_evaluation_result(message):
    """Return empty result for error cases"""
    return {
        "score": 0.0,
        "scoreBreakdown": {"accuracy": 0.0, "fluency": 0.0, "pronunciation": 0.0},
        "detailedMetrics": {
            "accuracy": "0/0 words correct (0%)",
            "fluency": "0 words per minute",
            "consistency": "Pacing variation: 0s",
        },
        "feedback": [message],
        "level": "Needs Practice",
    }


def evaluate_accuracy(passage_text, audio_data):
    """Evaluate reading accuracy (4 points)"""
    try:
        passage_words = re.sub(r"[.,!?]", "", passage_text.lower()).split()
        user_words = []

        for segment in audio_data:
            # Convert AudioSegment Pydantic model to dict if needed
            if hasattr(segment, "dict"):
                segment_data = segment.dict()
            else:
                segment_data = segment

            words = re.sub(r"[.,!?]", "", segment_data["text"].lower()).split()
            user_words.extend(words)

        user_words = [word for word in user_words if word]

        correct_words = 0
        total_words = len(passage_words)

        for i in range(min(len(passage_words), len(user_words))):
            if passage_words[i] == user_words[i]:
                correct_words += 1

        accuracy_percentage = (
            (correct_words / total_words) * 100 if total_words > 0 else 0
        )

        # Convert to 4-point scale
        accuracy_score = (accuracy_percentage / 100) * 4

        return {
            "score": min(4, accuracy_score),
            "accuracy_percentage": accuracy_percentage,
            "correct_words": correct_words,
            "total_words": total_words,
        }
    except Exception as e:
        return {
            "score": 0,
            "accuracy_percentage": 0,
            "correct_words": 0,
            "total_words": 0,
        }


def evaluate_fluency(audio_data):
    """Evaluate reading fluency (4 points)"""
    if len(audio_data) < 2:
        return {"score": 0, "words_per_minute": 0, "average_pause": 0}

    try:
        segments = []
        for segment in audio_data:
            if hasattr(segment, "dict"):
                segment_data = segment.dict()
            else:
                segment_data = segment

            if segment_data["text"].strip():
                segments.append(segment_data)

        if len(segments) < 2:
            return {"score": 0, "words_per_minute": 0, "average_pause": 0}

        # Calculate words per minute (2 points)
        total_duration = sum([seg["endTime"] - seg["startTime"] for seg in segments])

        # Validate duration
        if total_duration <= 0:
            return {"score": 0, "words_per_minute": 0, "average_pause": 0}

        total_words = sum(len(seg["text"].split()) for seg in segments)
        words_per_minute = (total_words / total_duration) * 60

        # WPM scoring with more realistic ranges
        if 80 <= words_per_minute <= 120:
            wpm_score = 2  # Perfect range for English learners
        elif 60 <= words_per_minute < 80:
            wpm_score = 1.5  # Good but slightly slow
        elif 120 < words_per_minute <= 150:
            wpm_score = 1.5  # Good but slightly fast
        elif 50 <= words_per_minute < 60:
            wpm_score = 1  # Slow
        elif 150 < words_per_minute <= 180:
            wpm_score = 1  # Fast
        else:
            wpm_score = 0.5  # Too slow or too fast

        # Analyze pauses (2 points)
        pauses = []
        for i in range(1, len(segments)):
            pause = segments[i]["startTime"] - segments[i - 1]["endTime"]
            if pause > 0:  # Only count actual pauses
                pauses.append(pause)

        avg_pause = sum(pauses) / len(pauses) if pauses else 0

        # More nuanced pause scoring
        if avg_pause <= 0.3:
            pause_score = 2  # Excellent flow (natural speech)
        elif avg_pause <= 0.6:
            pause_score = 1.5  # Good flow
        elif avg_pause <= 1.0:
            pause_score = 1  # Average
        elif avg_pause <= 1.5:
            pause_score = 0.5  # Many pauses
        else:
            pause_score = 0.2  # Excessive pausing

        return {
            "score": wpm_score + pause_score,
            "words_per_minute": words_per_minute,
            "average_pause": avg_pause,
            "wpm_score": wpm_score,
            "pause_score": pause_score,
        }

    except Exception as e:
        return {"score": 0, "words_per_minute": 0, "average_pause": 0}


def evaluate_consistency(audio_data):
    """Evaluate consistency (2 points)"""
    segments = []
    for segment in audio_data:
        if hasattr(segment, "dict"):
            segment_data = segment.dict()
        else:
            segment_data = segment

        if segment_data["text"].strip():
            segments.append(segment_data)

    if not segments:
        return {"score": 0, "consistency": 0}

    try:
        # Analyze speech consistency (2 point)
        durations = [seg["endTime"] - seg["startTime"] for seg in segments]
        avg_duration = sum(durations) / len(durations)

        # Calculate STANDARD DEVIATION (not variance)
        squared_diffs = sum((dur - avg_duration) ** 2 for dur in durations)
        standard_deviation = math.sqrt(squared_diffs / len(durations))

        # Score based on standard deviation (out of 2 points)
        if standard_deviation < 0.3:
            consistency_score = 2  # Very consistent
        elif standard_deviation < 0.6:
            consistency_score = 1.4  # Consistent
        elif standard_deviation < 1.0:
            consistency_score = 0.8  # Somewhat consistent
        else:
            consistency_score = 0.4  # Inconsistent

        return {
            "score": min(2, consistency_score),
            "consistency": standard_deviation,
        }

    except Exception as e:
        return {"score": 0, "consistency": 0}


def generate_feedback(accuracy, fluency, consistency, total_score):
    """Generate personalized feedback"""
    feedback = []

    # Accuracy feedback
    if accuracy["score"] >= 3.5:
        feedback.append("Excellent word accuracy! You read almost all words correctly.")
    elif accuracy["score"] >= 2.5:
        feedback.append(
            "Good word accuracy. Practice difficult words to improve further."
        )
    else:
        feedback.append(
            "Focus on reading words accurately. Practice reading slowly and clearly."
        )

    # Fluency feedback
    if fluency["wpm_score"] >= 1.5 and fluency["pause_score"] >= 1.5:
        feedback.append("Great fluency! Your reading pace and flow are excellent.")
    elif fluency["words_per_minute"] < 80:
        feedback.append(
            "Try to read a bit faster. Aim for a more natural speaking pace."
        )
    elif fluency["words_per_minute"] > 150:
        feedback.append("Good speed, but try to slow down slightly for better clarity.")
    elif fluency["average_pause"] > 1.0:
        feedback.append("Work on reducing pauses between phrases for better flow.")

    # consistency feedback
    if consistency["score"] >= 1.5:
        feedback.append("Good speech consistency and confidence!")
    else:
        feedback.append("Work on speaking more consistently.")

    # Overall encouragement
    if total_score >= 8:
        feedback.append("Outstanding reading performance! Keep up the great work!")
    elif total_score >= 6:
        feedback.append("Good job! With regular practice, you'll continue to improve.")
    else:
        feedback.append(
            "Keep practicing regularly. Focus on one area at a time for steady improvement."
        )

    return feedback


def get_performance_level(score):
    """Get performance level based on score"""
    if score >= 9:
        return "Excellent"
    elif score >= 7.5:
        return "Very Good"
    elif score >= 6:
        return "Good"
    elif score >= 4.5:
        return "Satisfactory"
    else:
        return "Needs Practice"
