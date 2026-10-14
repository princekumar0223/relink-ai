import json
import re
from typing import Optional
from fastapi import APIRouter, Form, HTTPException, Depends
from google import genai
import sqlite3
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])

@router.get("/status")
def get_ai_status():
    has_key = bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY.strip()) > 5)
    return {
        "gemini_active": has_key,
        "model": settings.GEMINI_MODEL,
        "fallback_mode": "Local CV & Heuristic NLP active" if not has_key else "Full Gemini Multimodal Active"
    }

@router.post("/config")
def update_gemini_key(api_key: str = Form(...), db: sqlite3.Connection = Depends(get_db)):
    clean_key = api_key.strip()
    # Test key with a quick ping
    try:
        client = genai.Client(api_key=clean_key)
        test_res = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents="Ping test. Respond with 'PONG'."
        )
        # If successful, save to runtime settings and database
        settings.GEMINI_API_KEY = clean_key
        cursor = db.cursor()
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('gemini_api_key', ?)", (clean_key,))
        db.commit()
        return {
            "status": "success",
            "message": "Gemini API key verified and saved successfully!",
            "model_reply": test_res.text
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to verify Gemini API key: {str(e)}")


@router.post("/generate-claim-questions")
def generate_claim_questions(
    lost_description: str = Form(...),
    found_description: str = Form(...),
    category: str = Form(...)
):
    """
    Generates intelligent anti-fraud ownership challenge questions.
    """
    if settings.GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = f"""For a lost & found verification:
Lost Item Description: {lost_description}
Found Item Description: {found_description}
Category: {category}

Generate 2 distinct, highly specific verification challenge questions that ONLY the true owner would know,
without revealing the secret answers. (e.g. Asking what sticker is on the back, lock screen wallpaper, secret compartment contents, scratches, etc.)

Return ONLY a JSON array of strings:
[
  "What specific sticker or mark is visible on the bottom/back of the item?",
  "What is the exact color or brand of the accessory inside the pouch?"
]"""
            res = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt
            )
            raw = (res.text or "").strip()
            if "```" in raw:
                raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
            questions = json.loads(raw)
            if isinstance(questions, list) and len(questions) >= 2:
                return {"questions": questions[:2]}
        except Exception:
            pass

    # Heuristic fallback questions based on category
    fallback_map = {
        "bottles": [
            "Are there any specific stickers, scratches, dents, or brand engravings on the body or base?",
            "What color or mechanism is the bottle cap/lid or carrying loop/strap?"
        ],
        "electronics": [
            "What is the lock screen wallpaper or device serial/model code?",
            "Are there any specific scratches, stickers, or protective case features?"
        ],
        "bags": [
            "What specific items or unique personal belongings are in the front zipper pocket?",
            "What brand or color is the inner lining or keychain attached to the strap?"
        ],
        "wallets": [
            "Which specific cards or unique photo/receipt is placed in the interior compartment?",
            "What is the exact currency denomination or coin inside?"
        ],
        "keys": [
            "How many keys are on the ring and what does the main keychain look like?",
            "Is there a grocery rewards tag, car fob brand, or engraving on any key?"
        ]
    }
    return {
        "questions": fallback_map.get(
            category.lower(),
            [
                "Describe any unique scratches, markings, or distinguishing features not in the public post.",
                "Can you provide proof of purchase, serial number, or an older photograph with the item?"
            ]
        )
    }
