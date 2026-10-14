import sqlite3
from typing import Generator
from contextlib import contextmanager
from .config import settings

def init_db():
    """Initialize database tables with WAL mode for performance."""
    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    # Items Table (Lost & Found)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK(type IN ('lost', 'found')),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        primary_color TEXT,
        brand TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        location_name TEXT NOT NULL,
        date_occurred TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        contact_email TEXT NOT NULL,
        contact_phone TEXT,
        custody_location TEXT,
        image_path TEXT,
        image_hash TEXT,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'matched', 'claimed', 'reunited')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Matches Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lost_item_id INTEGER NOT NULL,
        found_item_id INTEGER NOT NULL,
        visual_score REAL NOT NULL,
        text_score REAL NOT NULL,
        geo_score REAL NOT NULL,
        composite_score REAL NOT NULL,
        distance_meters REAL,
        ai_reasoning TEXT,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'verified', 'rejected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lost_item_id) REFERENCES items (id) ON DELETE CASCADE,
        FOREIGN KEY (found_item_id) REFERENCES items (id) ON DELETE CASCADE,
        UNIQUE (lost_item_id, found_item_id)
    );
    """)
    
    # Claims Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        claimant_name TEXT NOT NULL,
        claimant_contact TEXT NOT NULL,
        secret_verification_answer TEXT,
        proof_details TEXT,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (match_id) REFERENCES matches (id) ON DELETE CASCADE
    );
    """)
    
    # App Settings / Metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    
    conn.commit()
    conn.close()

def get_db():
    """Get database connection with row factory configured."""
    conn = sqlite3.connect(str(settings.DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def db_context():
    """Context manager for standalone database operations."""
    conn = sqlite3.connect(str(settings.DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
