import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

class Settings(BaseModel):
    PROJECT_NAME: str = "Relink AI"
    VERSION: str = "1.0.0"
    PROJECT_ROOT: Path = PROJECT_ROOT
    
    # Storage (Uses /tmp on Vercel serverless to support ephemeral write access)
    DATA_DIR: Path = Path("/tmp/data") if os.getenv("VERCEL") else (PROJECT_ROOT / "data")
    UPLOADS_DIR: Path = Path("/tmp/uploads") if os.getenv("VERCEL") else (PROJECT_ROOT / "uploads")
    DATABASE_PATH: Path = Path("/tmp/relink.db") if os.getenv("VERCEL") else (PROJECT_ROOT / "data" / "relink.db")
    
    # Gemini AI configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    
    # Matching Engine Weights (Sum should equal 1.0)
    WEIGHT_VISUAL: float = 0.40
    WEIGHT_TEXT: float = 0.35
    WEIGHT_GEO: float = 0.25
    
    # Thresholds
    MATCH_ALERT_THRESHOLD: float = 0.65  # 65% triggers high confidence match
    CANDIDATE_THRESHOLD: float = 0.40    # 40% triggers candidate display
    
    # Geospatial decay settings (in meters)
    GEO_PERFECT_DISTANCE_M: float = 150.0      # <= 150m is 100% geo match
    GEO_MAX_RADIUS_M: float = 25000.0          # 25 km max consideration range

settings = Settings()

# Ensure directories exist
try:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
