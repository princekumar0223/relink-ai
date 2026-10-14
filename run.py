import os
import sys
import uvicorn
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.database import init_db

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        
    print("=" * 60)
    print("  RELINK AI -- Multimodal Lost & Found Intelligence System")
    print("=" * 60)
    print(f"[+] Project Root : {PROJECT_ROOT}")
    print(f"[+] Database     : {settings.DATABASE_PATH}")
    print(f"[+] Gemini Status: {'Active (' + settings.GEMINI_MODEL + ')' if settings.GEMINI_API_KEY else 'Offline (Local CV & Geo Active)'}")
    print("=" * 60)
    
    # Initialize DB tables (clean, no dummy seed data)
    init_db()
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    print(f"\n--> Starting Relink AI Web Application at: http://{('127.0.0.1' if host == '0.0.0.0' else host)}:{port}")
    print("    (Production Ready - Listening on all interfaces)\n")
    print("Press CTRL+C to stop the server.\n")
    
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
