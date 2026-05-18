"""
database.py
-----------
PostgreSQL connection helper using environment variables.

The module uses DATABASE_URL when available, or falls back to
individual PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD settings.
"""

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DEFAULT_DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", 5432)),
    "dbname": os.getenv("PGDATABASE", "classicmodels"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres"),
}


def get_connection():
    """Return a fresh PostgreSQL connection."""
    try:
        if DATABASE_URL:
            return psycopg2.connect(DATABASE_URL)
        return psycopg2.connect(**DEFAULT_DB_CONFIG)
    except psycopg2.OperationalError as exc:
        print(f"[DATABASE] Connection error: {exc}")
        raise


def test_connection():
    """Run a simple test query to verify PostgreSQL connectivity."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print("[DATABASE] Connected successfully!")
        print(f"[DATABASE] PostgreSQL version: {version[0]}")
        cursor.close()
        conn.close()
    except Exception as exc:
        print(f"[DATABASE] Connection failed: {exc}")


if __name__ == "__main__":
    test_connection()
