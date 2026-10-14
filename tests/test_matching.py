import sys
import unittest
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.utils.geo_helpers import haversine_distance, calculate_geo_score, format_distance
from backend.app.utils.image_helpers import compute_dhash, hash_similarity
from backend.app.engine.text_matcher import TextMatcher
from backend.app.engine.geo_matcher import GeoMatcher
from backend.app.engine.hybrid_matcher import HybridMatcher
from backend.app.database import init_db, db_context

class TestRelinkMatchingEngine(unittest.TestCase):

    def test_haversine_distance(self):
        # Known points: Connaught Place Inner Circle points
        lat1, lon1 = 28.6315, 77.2167
        lat2, lon2 = 28.6320, 77.2170
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        # Distance should be roughly 60-80 meters
        self.assertGreater(dist, 40)
        self.assertLess(dist, 120)
        
        # Far points: Delhi to Airport (~15-18 km)
        lat_airport, lon_airport = 28.5562, 77.1000
        dist_airport = haversine_distance(lat1, lon1, lat_airport, lon_airport)
        self.assertGreater(dist_airport, 12000)

    def test_calculate_geo_score(self):
        # Within 150m should be 1.0 (100%)
        score_close = calculate_geo_score(80.0)
        self.assertEqual(score_close, 1.0)
        
        # 1 km away should be between 0.80 and 0.95
        score_1km = calculate_geo_score(1000.0)
        self.assertGreaterEqual(score_1km, 0.75)
        self.assertLessEqual(score_1km, 0.95)
        
        # 25 km away should be significantly lower
        score_25km = calculate_geo_score(25000.0)
        self.assertLess(score_25km, 0.30)

    def test_text_matcher_local(self):
        # Compatible electronics item
        score_high, expl_high = TextMatcher.local_match(
            title1="Apple MacBook Air M2",
            desc1="Space grey laptop with cat sticker on lid",
            cat1="electronics",
            brand1="Apple",
            color1="Space Grey",
            title2="Found MacBook Air",
            desc2="Apple laptop space grey with sticker",
            cat2="electronics",
            brand2="Apple",
            color2="Space Grey"
        )
        self.assertGreaterEqual(score_high, 0.75)
        
        # Incompatible categories (Laptop vs Dog)
        score_low, expl_low = TextMatcher.local_match(
            title1="MacBook Pro",
            desc1="Laptop computer",
            cat1="electronics",
            brand1="Apple",
            color1="Silver",
            title2="Lost Golden Retriever",
            desc2="Friendly pet dog with red collar",
            cat2="pets",
            brand2=None,
            color2="Golden"
        )
        self.assertLess(score_low, 0.35)

    def test_image_hashing(self):
        # Create two identical test images
        img1 = Image.new("RGB", (200, 200), color=(100, 150, 200))
        img2 = Image.new("RGB", (200, 200), color=(100, 150, 200))
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        
        # Identical images must yield 100% hash similarity
        self.assertEqual(h1, h2)
        self.assertEqual(hash_similarity(h1, h2), 1.0)

    def test_hybrid_composite_evaluation(self):
        lost = {
            "id": 1,
            "type": "lost",
            "title": "MacBook Air",
            "description": "Space grey Apple laptop with Octocat sticker",
            "category": "electronics",
            "primary_color": "Space Grey",
            "brand": "Apple",
            "latitude": 28.6315,
            "longitude": 77.2167,
            "location_name": "Library 2nd Floor",
            "image_path": None,
            "image_hash": None
        }
        
        found_near = {
            "id": 2,
            "type": "found",
            "title": "MacBook Air Laptop",
            "description": "Apple space grey laptop found on table",
            "category": "electronics",
            "primary_color": "Space Grey",
            "brand": "Apple",
            "latitude": 28.6320,
            "longitude": 77.2170,
            "location_name": "Library Security Desk",
            "image_path": None,
            "image_hash": None
        }
        
        result = HybridMatcher.evaluate_pair(lost, found_near)
        self.assertGreaterEqual(result["composite_score"], 0.70)
        self.assertIn("Location Proximity", result["ai_reasoning"])
        self.assertIn("Description & Category", result["ai_reasoning"])

if __name__ == "__main__":
    unittest.main()
