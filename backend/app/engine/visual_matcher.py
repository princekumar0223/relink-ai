import json
import re
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from google import genai
from ..utils.image_helpers import hash_similarity, compute_color_histogram, color_similarity
from ..config import settings

class VisualMatcher:
    """
    Evaluates visual similarity between two item images.
    Uses Google Gemini 3.8 Flash Multimodal Vision when configured,
    and perceptual hash (dHash) + HSV color histogram when offline.
    """
    
    @staticmethod
    def _get_full_image_path(rel_path: Optional[str]) -> Optional[Path]:
        if not rel_path:
            return None
        # Handle multiple comma-separated image paths
        first_path = rel_path.split(",")[0].strip()
        clean = first_path.lstrip("/")
        full_path = settings.PROJECT_ROOT / clean
        if full_path.exists():
            return full_path
        return None

    @classmethod
    def local_match(
        cls,
        image_path1: Optional[str], hash1: Optional[str],
        image_path2: Optional[str], hash2: Optional[str]
    ) -> Tuple[float, str]:
        """Local perceptual hash & color histogram matching."""
        if not image_path1 or not image_path2:
            return 0.5, "One or both items have no image uploaded; using neutral visual baseline (50%)."
        
        # dHash similarity
        dhash_sim = hash_similarity(hash1 or "", hash2 or "")
        
        # Color histogram similarity
        p1 = cls._get_full_image_path(image_path1)
        p2 = cls._get_full_image_path(image_path2)
        
        col_sim = 0.5
        if p1 and p2:
            try:
                img1 = Image.open(p1)
                img2 = Image.open(p2)
                hist1 = compute_color_histogram(img1)
                hist2 = compute_color_histogram(img2)
                col_sim = color_similarity(hist1, hist2)
            except Exception:
                pass
                
        # Combined local score
        score = dhash_sim * 0.6 + col_sim * 0.4
        explanation = (
            f"Local CV Analysis: Structural feature similarity {int(dhash_sim * 100)}%, "
            f"Color palette similarity {int(col_sim * 100)}%."
        )
        return round(score, 4), explanation

    @classmethod
    def gemini_match(
        cls,
        image_path1: str,
        image_path2: str,
        api_key: str
    ) -> Tuple[float, str]:
        """Multimodal image comparison using Gemini 3.8 Flash."""
        try:
            p1 = cls._get_full_image_path(image_path1)
            p2 = cls._get_full_image_path(image_path2)
            
            if not p1 or not p2:
                return 0.5, "Image file not found on disk."
                
            img1 = Image.open(p1)
            img2 = Image.open(p2)
            
            client = genai.Client(api_key=api_key)
            prompt = """Analyze these two images. Image 1 is a reported LOST item, Image 2 is a reported FOUND item.
Evaluate if these two images could show the exact same object or identical model.
Inspect:
1. Object type, silhouette, model, shape.
2. Color, texture, material.
3. Identifying marks, wear, scratches, stickers, logos, attachments.

Return ONLY a JSON object in this exact format:
{
  "visual_similarity": 0.88,
  "visual_reasoning": "Both photos display a dark grey HP Pavilion laptop with identical stickers and keyboard wear."
}
visual_similarity must be between 0.0 and 1.0."""

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[prompt, img1, img2]
            )
            
            raw = (response.text or "").strip()
            if "```" in raw:
                raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
            data = json.loads(raw)
            score = float(data.get("visual_similarity", 0.5))
            reasoning = str(data.get("visual_reasoning", "Gemini vision analysis completed."))
            return round(max(0.0, min(1.0, score)), 4), reasoning
            
        except Exception as e:
            return cls.local_match(image_path1, None, image_path2, None)

    @classmethod
    def match(
        cls,
        image_path1: Optional[str], hash1: Optional[str],
        image_path2: Optional[str], hash2: Optional[str],
        api_key: Optional[str] = None
    ) -> Tuple[float, str]:
        active_key = api_key or settings.GEMINI_API_KEY
        if active_key and image_path1 and image_path2:
            return cls.gemini_match(image_path1, image_path2, active_key)
        return cls.local_match(image_path1, hash1, image_path2, hash2)
