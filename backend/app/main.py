import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import settings, PROJECT_ROOT
from .database import init_db, db_context
from .routers import items, matches, ai, claims

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multimodal Lost & Found Intelligence System with Image, Description, and Location Matching"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    # Check if a Gemini API key was previously saved in DB settings
    with db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = 'gemini_api_key'")
        row = cursor.fetchone()
        if row and row["value"]:
            settings.GEMINI_API_KEY = row["value"]

# Include API Routers
app.include_router(items.router)
app.include_router(matches.router)
app.include_router(ai.router)
app.include_router(claims.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "gemini_active": bool(settings.GEMINI_API_KEY)
    }

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")

# Frontend Static Files
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="assets")

@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Relink AI backend is running. Frontend index.html not found."}
