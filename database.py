"""
database.py
-----------
Handles the PostgreSQL database connection.
Uses psycopg2 to connect to the classicmodels database.

HOW TO USE:
    from database import get_connection
    conn = get_connection()
"""

import psycopg2
import psycopg2.extras

# ─── DATABASE CONFIGURATION ───────────────────────────────────────────────────
# Change these values to match YOUR PostgreSQL setup.
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "classicmodels",   # Your database name
    "user":     "postgres",        # Your PostgreSQL username
    "password": "your_password",   # Your PostgreSQL password
}


def get_connection():
    """
    Opens and returns a new PostgreSQL connection.
    Call this each time you need a fresh connection.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"[DATABASE ERROR] Could not connect to database: {e}")
        raise


def test_connection():
    """
    Quick test to check if the database connection works.
    Run this file directly: python database.py
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"[DATABASE] Connected successfully!")
        print(f"[DATABASE] PostgreSQL version: {version[0]}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DATABASE] Connection failed: {e}")


# Run test when file is executed directly
if __name__ == "__main__":
    test_connection()
