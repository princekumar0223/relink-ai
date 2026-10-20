import os
import sqlite3
from typing import Generator
from contextlib import contextmanager
from .config import settings

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_POSTGRES = bool(DATABASE_URL)
except ImportError:
    HAS_POSTGRES = False

class PostgresCursorWrapper:
    def __init__(self, raw_cursor):
        self.cur = raw_cursor
        self.lastrowid = None

    def execute(self, sql, params=None):
        # Convert SQLite '?' placeholders to Postgres '%s'
        pg_sql = sql.replace("?", "%s")
        # Handle 'INSERT OR REPLACE' for app_settings
        if "INSERT OR REPLACE INTO app_settings" in pg_sql:
            pg_sql = "INSERT INTO app_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"

        # Check if INSERT without RETURNING id
        is_insert = pg_sql.strip().upper().startswith("INSERT INTO")
        has_returning = "RETURNING" in pg_sql.upper()

        if is_insert and not has_returning and ("INSERT INTO app_settings" not in pg_sql):
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id;"
            if params is not None:
                self.cur.execute(pg_sql, params)
            else:
                self.cur.execute(pg_sql)
            try:
                ret = self.cur.fetchone()
                if ret:
                    self.lastrowid = ret[0]
            except Exception:
                self.lastrowid = None
            return self

        if params is not None:
            self.cur.execute(pg_sql, params)
        else:
            self.cur.execute(pg_sql)
        return self

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    def fetchmany(self, size=None):
        return self.cur.fetchmany(size)

    def __iter__(self):
        return iter(self.cur)

    @property
    def rowcount(self):
        return self.cur.rowcount

class PostgresConnectionWrapper:
    def __init__(self, raw_conn):
        self.conn = raw_conn

    def cursor(self):
        raw_cur = self.conn.cursor(cursor_factory=DictCursor)
        return PostgresCursorWrapper(raw_cur)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

def _get_raw_connection():
    if HAS_POSTGRES and DATABASE_URL:
        raw_conn = psycopg2.connect(DATABASE_URL)
        return PostgresConnectionWrapper(raw_conn)
    else:
        conn = sqlite3.connect(str(settings.DATABASE_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database tables for PostgreSQL or SQLite."""
    conn = _get_raw_connection()
    cursor = conn.cursor()

    if HAS_POSTGRES and DATABASE_URL:
        # PostgreSQL Schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
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
            upi_id TEXT,
            image_path TEXT,
            image_hash TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'matched', 'claimed', 'reunited')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            lost_item_id INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
            found_item_id INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
            visual_score REAL NOT NULL,
            text_score REAL NOT NULL,
            geo_score REAL NOT NULL,
            composite_score REAL NOT NULL,
            distance_meters REAL,
            ai_reasoning TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'verified', 'rejected')),
            email_notified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lost_item_id, found_item_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id SERIAL PRIMARY KEY,
            match_id INTEGER NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
            claimant_name TEXT NOT NULL,
            claimant_contact TEXT NOT NULL,
            secret_verification_answer TEXT,
            proof_details TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            reward_amount REAL DEFAULT 0,
            reward_status TEXT DEFAULT 'none',
            reward_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER,
            match_id INTEGER NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
            sender_name TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            receiver_upi TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'INR',
            message TEXT,
            payment_mode TEXT DEFAULT 'UPI',
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT,
            item_id INTEGER,
            match_id INTEGER,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            match_score REAL,
            status TEXT NOT NULL DEFAULT 'logged',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
    else:
        # SQLite Schema
        cursor.execute("PRAGMA journal_mode=WAL;")
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
            upi_id TEXT,
            image_path TEXT,
            image_hash TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'matched', 'claimed', 'reunited')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

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
            email_notified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lost_item_id) REFERENCES items (id) ON DELETE CASCADE,
            FOREIGN KEY (found_item_id) REFERENCES items (id) ON DELETE CASCADE,
            UNIQUE (lost_item_id, found_item_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            claimant_name TEXT NOT NULL,
            claimant_contact TEXT NOT NULL,
            secret_verification_answer TEXT,
            proof_details TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            reward_amount REAL DEFAULT 0,
            reward_status TEXT DEFAULT 'none',
            reward_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER,
            match_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            receiver_upi TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'INR',
            message TEXT,
            payment_mode TEXT DEFAULT 'UPI',
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT,
            item_id INTEGER,
            match_id INTEGER,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            match_score REAL,
            status TEXT NOT NULL DEFAULT 'logged',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # Safe migrations for existing SQLite databases
        migrations = [
            "ALTER TABLE items ADD COLUMN upi_id TEXT",
            "ALTER TABLE matches ADD COLUMN email_notified INTEGER DEFAULT 0",
            "ALTER TABLE claims ADD COLUMN reward_amount REAL DEFAULT 0",
            "ALTER TABLE claims ADD COLUMN reward_status TEXT DEFAULT 'none'",
            "ALTER TABLE claims ADD COLUMN reward_note TEXT"
        ]
        for stmt in migrations:
            try:
                cursor.execute(stmt)
            except Exception:
                pass

    conn.commit()
    conn.close()

def get_db():
    """Dependency for FastAPI route handlers."""
    conn = _get_raw_connection()
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def db_context():
    """Context manager for background threads / utility scripts."""
    conn = _get_raw_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
