# routers/reading.py
from fastapi import APIRouter, HTTPException, Depends, Query
from database import db
from models import ReadingAnswer, ReadingEvaluation, AudioSegment
from bson import ObjectId
from utils.jwt import get_current_user
from utils.allFunctions import AllFunctions
from typing import List, Optional
from fastapi.responses import JSONResponse
import math
import re

router = APIRouter(prefix="/reading", tags=["Reading"])


@router.get("/passages")
async def get_passages_list(
    page: int,
    page_size: int,
    level_beginner: Optional[str] = Query(None, alias="level.beginner"),
    level_intermediate: Optional[str] = Query(None, alias="level.intermediate"),
    level_advanced: Optional[str] = Query(None, alias="level.advanced"),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Depends(get_current_user),
):
    try:
        # Build base query with AND relationship
        query = {}
        conditions = []  # List to hold all filter conditions
        # Parse comma-separated level-difficulty combinations
        level_filters = []

        if level_beginner:
            difficulties = [
                d.lower().strip() for d in level_beginner.split(",")
            ]  # Convert to lowercase and trim
            level_filters.append(
                {"level": "beginner", "difficulty": {"$in": difficulties}}
            )

        if level_intermediate:
            difficulties = [
                d.lower().strip() for d in level_intermediate.split(",")
            ]  # Convert to lowercase and trim
            level_filters.append(
                {"level": "intermediate", "difficulty": {"$in": difficulties}}
            )

        if level_advanced:
            difficulties = [
                d.lower().strip() for d in level_advanced.split(",")
            ]  # Convert to lowercase and trim
            level_filters.append(
                {"level": "advanced", "difficulty": {"$in": difficulties}}
            )

        # Add level filters to conditions
        if level_filters:
            if len(level_filters) == 1:
                # Single level - add directly to conditions
                conditions.append(level_filters[0])
            else:
                # Multiple levels - use OR within levels, but AND with other filters
                conditions.append({"$or": level_filters})

        # Parse comma-separated status
        if status:
            status_list = [
                s.strip() for s in status.split(",")
            ]  # Clean up status values
            # Only proceed if we have a user_id for status filtering
            if user_id:
                passage_ids_solved = set()
                solved = db.reading_evaluations.find(
                    {"user_id": ObjectId(user_id)}, {"passage_id": 1}
                )
                passage_ids_solved = {doc["passage_id"] async for doc in solved}

                status_conditions = []
                has_solved = "solved" in status_list
                has_unsolved = "unsolved" in status_list

                # Handle status combinations
                if has_solved and has_unsolved:
                    # Show all passages (no passage_id filter needed)
                    pass
                elif has_solved:
                    if passage_ids_solved:
                        status_conditions.append(
                            {"passage_id": {"$in": list(passage_ids_solved)}}
                        )
                    else:
                        # No solved passages and only solved filter requested
                        return empty_response(page, page_size)
                elif has_unsolved:
                    if passage_ids_solved:
                        status_conditions.append(
                            {"passage_id": {"$nin": list(passage_ids_solved)}}
                        )
                    # If no solved passages, all are unsolved (no filter needed)

                # Add status conditions to main conditions
                if status_conditions:
                    if len(status_conditions) == 1:
                        conditions.append(status_conditions[0])
                    else:
                        conditions.append({"$or": status_conditions})
            else:
                # If no user_id but status filter is provided, we can't determine solved status
                # So we ignore status filter for anonymous users
                pass

        # Build final query with AND relationship
        if conditions:
            if len(conditions) == 1:
                query = conditions[0]
            else:
                query["$and"] = conditions

        # Get paginated passages
        data = await AllFunctions().paginate(
            db.reading_passages,
            query,
            {
                "_id": 0,
                "questions": 0,
                "standard": 0,
                "created_at": 0,
            },
            page,
            page_size,
        )

        # Add solved status field if user is logged in
        if user_id:
            # Reuse the solved passages we already fetched, or fetch if not available
            if "passage_ids_solved" not in locals():
                passage_ids_solved = set()
                solved = db.reading_evaluations.find(
                    {"user_id": ObjectId(user_id)}, {"passage_id": 1}
                )
                passage_ids_solved = {doc["passage_id"] async for doc in solved}

            for passage in data["results"]:
                passage_id = passage.get("passage_id")
                passage["solved"] = passage_id in passage_ids_solved
                passage["passage"] = passage["passage"][:300] + "...."
        else:
            # For anonymous users, mark all as unsolved
            for passage in data["results"]:
                passage["solved"] = False
                passage["passage"] = passage["passage"][:300] + "...."

        return data

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Server Error: {str(e)}"},
        )


@router.get("/passages/{passage_id}")
async def get_passages(passage_id: str, user_id: str = Depends(get_current_user)):
    try:
        # Fetch passage (only one expected per passage_id)
        passage = await db.reading_passages.find_one(
            {"passage_id": passage_id},
            {"_id": 0, "questions": 0, "standard": 0, "created_at": 0},
        )
        if not passage:
            return JSONResponse(
                status_code=404,
                content={"message": "Passage not found"},
            )

        # Check if passage is solved by this user
        solved = await db.reading_evaluations.find_one(
            {"user_id": ObjectId(user_id), "passage_id": passage_id},
            {"evaluation_data": 1},  # projection
        )

        passage["solved"] = bool(solved)
        passage["evaluation_data"] = solved.get("evaluation_data") if solved else None

        return passage

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"},
        )


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

        # Generate section-wise feedback
        feedback = generate_section_feedback(
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
                "consistency": f"Pacing variation: {consistency_result['consistency']:.3f}s",
            },
            "feedback": feedback,
        }

    except Exception as e:
        return get_empty_evaluation_result(f"Evaluation error: {str(e)}")


def get_empty_evaluation_result(message):
    """Return empty result for error cases"""
    return {
        "score": 0.0,
        "scoreBreakdown": {"accuracy": 0.0, "fluency": 0.0, "consistency": 0.0},
        "detailedMetrics": {
            "accuracy": "0/0 words correct (0%)",
            "fluency": "0 words per minute",
            "consistency": "Pacing variation: 0s",
        },
        "feedback": {
            "accuracy": [message],
            "fluency": [message],
            "consistency": [message],
            "overall": [message],
        },
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


def generate_section_feedback(accuracy, fluency, consistency, total_score):
    """Generate section-wise personalized feedback"""

    feedback = {"accuracy": [], "fluency": [], "consistency": [], "overall": []}

    # Accuracy feedback
    if accuracy["score"] >= 3.5:
        feedback["accuracy"].append(
            "🎯 Excellent word accuracy! You read almost all words correctly."
        )
        feedback["accuracy"].append(
            "Your pronunciation of individual words is very clear and precise."
        )
    elif accuracy["score"] >= 2.5:
        feedback["accuracy"].append(
            "✅ Good word accuracy. You read most words correctly."
        )
        feedback["accuracy"].append(
            "Practice a few difficult words to reach excellence."
        )
    elif accuracy["score"] >= 1.5:
        feedback["accuracy"].append(
            "📝 Fair accuracy. Focus on reading each word carefully."
        )
        feedback["accuracy"].append(
            "Try reading slowly and paying attention to each word's pronunciation."
        )
    else:
        feedback["accuracy"].append("🔍 Needs improvement in word accuracy.")
        feedback["accuracy"].append(
            "Practice reading slowly and clearly, focusing on one word at a time."
        )

    # Fluency feedback
    if fluency["score"] >= 3.5:
        feedback["fluency"].append(
            "🚀 Excellent fluency! Your reading pace is perfect."
        )
        feedback["fluency"].append(
            "You maintain a natural flow with appropriate pauses."
        )
    elif fluency["score"] >= 2.5:
        if fluency["words_per_minute"] < 80:
            feedback["fluency"].append(
                "📊 Good fluency, but try to increase your reading speed slightly."
            )
            feedback["fluency"].append(
                "Aim for 80-120 words per minute for natural speech."
            )
        elif fluency["words_per_minute"] > 150:
            feedback["fluency"].append(
                "📊 Good fluency, but try to slow down slightly for better clarity."
            )
            feedback["fluency"].append(
                "A more moderate pace will improve comprehension."
            )
        else:
            feedback["fluency"].append("📊 Good fluency with reasonable pace and flow.")
    elif fluency["score"] >= 1.5:
        feedback["fluency"].append("⏱️ Your reading pace needs improvement.")
        if fluency["average_pause"] > 1.0:
            feedback["fluency"].append("Work on reducing long pauses between phrases.")
        feedback["fluency"].append("Practice reading aloud regularly to build fluency.")
    else:
        feedback["fluency"].append("💤 Fluency needs significant improvement.")
        feedback["fluency"].append(
            "Focus on reading in phrases rather than word-by-word."
        )

    # Consistency feedback
    if consistency["score"] >= 1.5:
        feedback["consistency"].append("🎵 Excellent pacing consistency!")
        feedback["consistency"].append(
            "You maintain a steady, rhythmic pace throughout your reading."
        )
    elif consistency["score"] >= 1.0:
        feedback["consistency"].append("📈 Good pacing consistency.")
        feedback["consistency"].append(
            "Try to make your speech rhythm more even across all words."
        )
    elif consistency["score"] >= 0.5:
        feedback["consistency"].append("⚖️ Some inconsistency in pacing detected.")
        feedback["consistency"].append(
            "Avoid rushing through some words and dragging others."
        )
        feedback["consistency"].append(
            "Practice with a metronome to develop steady rhythm."
        )
    else:
        feedback["consistency"].append("🔄 Pacing is very inconsistent.")
        feedback["consistency"].append("Focus on speaking at a more consistent speed.")
        feedback["consistency"].append("Record yourself and listen for uneven pacing.")

    # Overall encouragement
    if total_score >= 8:
        feedback["overall"].append("🏆 Outstanding reading performance!")
        feedback["overall"].append(
            "You demonstrate excellent reading skills across all areas."
        )
    elif total_score >= 6:
        feedback["overall"].append("👍 Good job! Solid reading performance.")
        feedback["overall"].append("With regular practice, you'll continue to improve.")
    elif total_score >= 4:
        feedback["overall"].append("💪 Making good progress!")
        feedback["overall"].append(
            "Focus on one area at a time for steady improvement."
        )
    else:
        feedback["overall"].append("🌱 Keep practicing regularly!")
        feedback["overall"].append("Reading aloud daily will help build your skills.")

    return feedback


def empty_response(page: int, page_size: int) -> dict:
    """Return empty paginated response"""
    return {
        "results": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }
