import re
import json
from typing import Tuple, Optional
from google import genai
from ..config import settings

class TextMatcher:
    """
    Evaluates semantic and categorical similarity between lost and found item descriptions.
    Uses Google Gemini 3.8 Flash when configured, with a robust local NLP fallback.
    """
    
    COMPATIBLE_CATEGORIES = {
        "electronics": ["gadget", "device", "laptop", "phone", "audio", "camera", "tablet"],
        "bags": ["backpack", "purse", "wallet", "handbag", "luggage", "briefcase"],
        "wallets": ["bags", "accessories", "purse", "cardholder"],
        "documents": ["id", "passport", "card", "license", "papers"],
        "keys": ["keychain", "access card", "fob"],
        "clothing": ["jacket", "apparel", "shoes", "hat", "scarf", "coat"],
        "jewelry": ["watch", "ring", "necklace", "bracelet", "accessories"],
        "pets": ["dog", "cat", "animal", "bird"],
        "bottles": ["bottle", "flask", "sipper", "thermos", "tumbler", "water bottle", "hydro flask", "milton"]
    }
    
    @staticmethod
    def _clean_tokens(text: str) -> set:
        if not text:
            return set()
        words = re.findall(r'\b[a-zA-Z0-9]{2,}\b', text.lower())
        stopwords = {
            "the", "and", "with", "for", "that", "this", "from", "item", "was",
            "found", "lost", "near", "about", "color", "some", "have", "here"
        }
        return set(w for w in words if w not in stopwords)
    
    @classmethod
    def _category_score(cls, cat1: str, cat2: str) -> float:
        c1 = (cat1 or "").strip().lower()
        c2 = (cat2 or "").strip().lower()
        if not c1 or not c2:
            return 0.5
        if c1 == c2:
            return 1.0
        
        # Check compatibility matrix
        for main_cat, alts in cls.COMPATIBLE_CATEGORIES.items():
            if (c1 == main_cat and c2 in alts) or (c2 == main_cat and c1 in alts):
                return 0.75
            if c1 in alts and c2 in alts:
                return 0.85
                
        return 0.1  # Significant penalty if categories are completely unrelated
    
    @classmethod
    def local_match(
        cls,
        title1: str, desc1: str, cat1: str, brand1: Optional[str], color1: Optional[str],
        title2: str, desc2: str, cat2: str, brand2: Optional[str], color2: Optional[str]
    ) -> Tuple[float, str]:
        """Local NLP fallback matching algorithm."""
        cat_sim = cls._category_score(cat1, cat2)
        
        tokens1 = cls._clean_tokens(f"{title1} {desc1}")
        tokens2 = cls._clean_tokens(f"{title2} {desc2}")
        
        if tokens1 and tokens2:
            intersection = tokens1.intersection(tokens2)
            union = tokens1.union(tokens2)
            token_sim = len(intersection) / len(union)
        else:
            token_sim = 0.0
            
        # Brand match
        b1 = (brand1 or "").strip().lower()
        b2 = (brand2 or "").strip().lower()
        if b1 and b2:
            brand_sim = 1.0 if (b1 in b2 or b2 in b1) else 0.0
        else:
            brand_sim = 0.5  # Neutral if brand unspecified
            
        # Color match
        col1 = (color1 or "").strip().lower()
        col2 = (color2 or "").strip().lower()
        if col1 and col2:
            color_sim = 1.0 if (col1 in col2 or col2 in col1) else 0.2
        else:
            color_sim = 0.5  # Neutral if color unspecified
            
        # Weighted local text score
        score = (
            cat_sim * 0.35 +
            token_sim * 0.35 +
            brand_sim * 0.15 +
            color_sim * 0.15
        )
        
        explanation = (
            f"Category alignment: {int(cat_sim * 100)}%, keyword overlap: {int(token_sim * 100)}%. "
            f"Brand: '{b1 or 'N/A'}' vs '{b2 or 'N/A'}', Color: '{col1 or 'N/A'}' vs '{col2 or 'N/A'}."
        )
        return round(score, 4), explanation

    @classmethod
    def gemini_match(
        cls,
        title1: str, desc1: str, cat1: str, brand1: Optional[str], color1: Optional[str],
        title2: str, desc2: str, cat2: str, brand2: Optional[str], color2: Optional[str],
        api_key: str
    ) -> Tuple[float, str]:
        """Deep semantic comparison using Gemini 3.8 Flash."""
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""You are an expert AI lost-and-found matcher. Compare these two items:
ITEM 1 (Lost):
- Title: {title1}
- Category: {cat1}
- Brand: {brand1 or 'Unknown'}
- Color: {color1 or 'Unknown'}
- Description: {desc1}

ITEM 2 (Found):
- Title: {title2}
- Category: {cat2}
- Brand: {brand2 or 'Unknown'}
- Color: {color2 or 'Unknown'}
- Description: {desc2}

Respond ONLY with a valid JSON object in this exact format:
{{
  "similarity_score": 0.85,
  "reasoning": "Both items describe a space grey Dell laptop with identical serial markings or stickers."
}}
Ensure similarity_score is a float between 0.0 and 1.0."""

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt
            )
            raw = (response.text or "").strip()
            # Clean markdown fences if any
            if "```" in raw:
                raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
            data = json.loads(raw)
            score = float(data.get("similarity_score", 0.5))
            reasoning = str(data.get("reasoning", "Gemini semantic comparison completed."))
            return round(max(0.0, min(1.0, score)), 4), reasoning
        except Exception as e:
            # Fallback to local matching if API call fails or times out
            score, explanation = cls.local_match(
                title1, desc1, cat1, brand1, color1,
                title2, desc2, cat2, brand2, color2
            )
            return score, f"{explanation} (Local fallback, Gemini offline: {str(e)[:50]})"

    @classmethod
    def match(
        cls,
        title1: str, desc1: str, cat1: str, brand1: Optional[str], color1: Optional[str],
        title2: str, desc2: str, cat2: str, brand2: Optional[str], color2: Optional[str],
        api_key: Optional[str] = None
    ) -> Tuple[float, str]:
        active_key = api_key or settings.GEMINI_API_KEY
        if active_key:
            return cls.gemini_match(
                title1, desc1, cat1, brand1, color1,
                title2, desc2, cat2, brand2, color2,
                active_key
            )
        return cls.local_match(
            title1, desc1, cat1, brand1, color1,
            title2, desc2, cat2, brand2, color2
        )
