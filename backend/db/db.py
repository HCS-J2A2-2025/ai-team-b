# backend/db/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    """
    Return a PostgreSQL connection.
    Priority:
      1. DATABASE_URL (recommended)
      2. Individual env vars (Docker/local fallback)
    """
    dsn = os.getenv("DATABASE_URL")

    if dsn:
        return psycopg2.connect(dsn, cursor_factory=RealDictCursor)

    # ---- fallback for Docker / local dev ----
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "appdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "postgres"),
        cursor_factory=RealDictCursor,
    )
