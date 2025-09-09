#!/usr/bin/env python3
"""
Educational Story Generator
Generates engaging stories for teachers to introduce new chapters.
"""

import os
import openai
# from dotenv import load_dotenv
from datetime import datetime
import logging
from config import llm, OPENAI_MODEL, OPENAI_API_KEY
# Load environment variables
# load_dotenv()
logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# API_KEY = os.getenv("OPENAI_API_KEY")
# # OPENAI_MODEL = os.getenv("OPENAI_MODEL")
# if not API_KEY:
#     raise ValueError("OPENAI_API_KEY not found in environment variables.")

# Initialize OpenAI client with modern API
client = openai.OpenAI(api_key=OPENAI_API_KEY)


# Story length mapping
LENGTHS = {
    "short": "2-3 paragraphs (150-200 words)",
    "medium": "4-5 paragraphs (300-400 words)",
    "long": "6-8 paragraphs (500-600 words)"
}

def generate_story(standard, subject, chapter, emotion, story_length="medium", language="English"):
    """Generate an educational story using OpenAI API."""
    
    system_msg = f"You are a creative educational storyteller in {language} within {LENGTHS.get(story_length, LENGTHS['medium'])} words for {standard} {subject} students."
    
    prompt = f"""
    You are an expert educational storyteller skilled at creating {language} immersive, age-appropriate narratives.
    Subject: "{subject}"  
    Topic: "{chapter}"  
    Emotional Tone: {emotion}  
    Language: {language}  
    Target Length: {LENGTHS.get(story_length, LENGTHS['medium'])} words.

    ### Guidelines:
    - The story must logically connect to the topic and convey accurate information (scientific, historical, or moral as applicable).
    - Ensure all facts are correct and age-appropriate.
    - Story should feel as if events are unfolding in front of the reader’s eyes, with vivid sensory details and cinematic narration.
    - Keep it relevant to present-day context (समयसामयिक) where appropriate, while staying true to historical, geographical, moral, factual or scientific accuracy.
    - Show characters exploring, asking questions, making observations, and discovering concepts step by step, rather than jumping to conclusions.
    - Use natural dialogues and engaging tone suitable for {standard}.
    - Story must be complete within {LENGTHS.get(story_length, LENGTHS['medium'])}.
    - End with a clear takeaway or conclusion that reinforces the learning objective.
    - Introduce and explain key terms naturally within the flow of the story.
    - Ensure the story feels complete, coherent, and well-paced within the given length.
    - Present the story in markdown format for readability.
    - Choose the most suitable path—physical, mental, historical, or moral—that best solves the problem and delivers the lesson in the most engaging way.
    """


    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=1200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"
