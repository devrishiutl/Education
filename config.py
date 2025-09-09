import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()  # Load env variables once
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing in .env")

llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model=OPENAI_MODEL,
    temperature=0.3
)