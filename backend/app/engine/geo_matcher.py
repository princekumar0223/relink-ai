from typing import Tuple
from ..utils.geo_helpers import haversine_distance, calculate_geo_score, format_distance, landmark_similarity
from ..config import settings

class GeoMatcher:
    """
    Evaluates geospatial proximity between lost and found items.
    Combines coordinate distance decay with landmark/venue name similarity.
    """
    
    @staticmethod
    def match(
        lat1: float, lon1: float, loc_name1: str,
        lat2: float, lon2: float, loc_name2: str
    ) -> Tuple[float, float, str]:
        """
        Returns:
            - geo_score: float in [0.0, 1.0]
            - distance_meters: float
            - explanation: human-readable analysis string
        """
        dist_m = haversine_distance(lat1, lon1, lat2, lon2)
        coord_score = calculate_geo_score(
            dist_m,
            perfect_distance=settings.GEO_PERFECT_DISTANCE_M,
            max_radius=settings.GEO_MAX_RADIUS_M
        )
        
        # Check text landmark similarity
        name_sim = landmark_similarity(loc_name1, loc_name2)
        
        # If coordinates are moderately close and landmark matches well, boost score
        if dist_m < 5000 and name_sim > 0.4:
            geo_score = min(1.0, coord_score * 0.8 + name_sim * 0.2)
        else:
            geo_score = coord_score
            
        dist_str = format_distance(dist_m)
        
        if dist_m <= 150:
            explanation = f"Very high proximity ({dist_str}). Items reported at virtually the exact same location ('{loc_name1}' vs '{loc_name2}')."
        elif dist_m <= 1000:
            explanation = f"Close proximity ({dist_str}). Both within walking distance in the same zone ('{loc_name1}' vs '{loc_name2}')."
        elif dist_m <= 5000:
            explanation = f"Moderate proximity ({dist_str}). Located in the same district/neighborhood."
        elif dist_m <= 25000:
            explanation = f"Wider regional distance ({dist_str}). Same metropolitan area."
        else:
            explanation = f"Far distance ({dist_str}). Unlikely to be geographically connected unless moved."
            
        return round(geo_score, 4), round(dist_m, 2), explanation
