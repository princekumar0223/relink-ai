import sys
from pathlib import Path

# Ensure project root is in sys.path for Vercel serverless runtime
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import app

# Export app for Vercel serverless
__all__ = ["app"]
