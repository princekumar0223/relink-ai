import math
import re
from typing import Tuple

EARTH_RADIUS_METERS = 6371000.0

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two GPS points in meters
    using the Haversine formula.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    
    # Clip to avoid float precision domain error in asin
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c

def calculate_geo_score(distance_meters: float, perfect_distance: float = 150.0, max_radius: float = 25000.0) -> float:
    """
    Computes a normalized proximity score [0.0, 1.0] from distance in meters.
    - <= 150m: 1.0 (exact nearby location)
    - 150m - 1000m: 0.90 - 1.0 (immediate neighborhood / walking radius)
    - 1km - 5km: 0.70 - 0.90 (same city district / transit corridor)
    - 5km - 25km: 0.20 - 0.70 (same metropolitan region)
    - > 25km: smooth exponential drop towards 0.0
    """
    if distance_meters <= perfect_distance:
        return 1.0
    
    if distance_meters > max_radius * 2:
        return 0.0
    
    # Half-life exponential decay model
    # Half life at 3 km (3000m), so at 3km score is ~0.50
    k = 0.000231  # -ln(0.5) / 3000
    effective_dist = distance_meters - perfect_distance
    score = math.exp(-k * effective_dist)
    return round(max(0.0, min(1.0, score)), 4)

def format_distance(distance_meters: float) -> str:
    """Format distance into human-readable string."""
    if distance_meters < 1000:
        return f"{int(round(distance_meters))} m"
    else:
        km = distance_meters / 1000.0
        return f"{km:.2f} km"

def landmark_similarity(text1: str, text2: str) -> float:
    """
    Computes lexical similarity between two landmark/location descriptions.
    Useful when items are found in the same building/station (e.g. 'Metro Gate 2' vs 'Metro Gate 3').
    """
    if not text1 or not text2:
        return 0.0
    
    clean1 = set(re.findall(r'\b\w+\b', text1.lower()))
    clean2 = set(re.findall(r'\b\w+\b', text2.lower()))
    
    if not clean1 or not clean2:
        return 0.0
    
    intersection = clean1.intersection(clean2)
    union = clean1.union(clean2)
    
    return len(intersection) / len(union)
