import os, base64, mimetypes
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/test1", tags=["Test1"])
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {MISTRAL_API_KEY}"}

def is_url(s): return bool(urlparse(s).scheme and urlparse(s).netloc)
def is_file(s): return Path(s).is_file()
def file_to_data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{mime};base64,{b64}"

@router.post("/ocr/from-link")
async def ocr_from_link(url_or_path: str = Query(..., description="URL or local file path")):
    if is_url(url_or_path):
        doc_type = "document_url" if url_or_path.lower().endswith((".pdf", ".docx", ".pptx")) else "image_url"
        document = {doc_type: url_or_path, "type": doc_type}
    elif is_file(url_or_path):
        doc_type = "document_url" if url_or_path.lower().endswith((".pdf", ".docx", ".pptx")) else "image_url"
        document = {doc_type: file_to_data_uri(url_or_path), "type": doc_type}
    else:
        raise HTTPException(400, "Invalid URL or file path")

    payload = {"model": "mistral-ocr-latest", "document": document, "include_image_base64": True}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{MISTRAL_BASE_URL}/ocr", headers=HEADERS, json=payload)
            resp.raise_for_status()
            pages = resp.json().get("pages", [])
            text = "\n\n".join(p.get("markdown", "") for p in pages)
            return {"input": url_or_path, "input_type": "url" if is_url(url_or_path) else "local_file", "text": text}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
