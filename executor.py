"""
executor.py
-----------
Executes SQL queries against PostgreSQL.
Handles validation, retry logic, and JSON-based query logging.
"""

import json
import os
import datetime

from database import get_connection
from validator import validate_sql
from sql_generator import fix_sql

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "query_logs.json")

os.makedirs(LOG_DIR, exist_ok=True)


def log_query(entry: dict):
    """Append an execution record to logs/query_logs.json."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry["timestamp"] = timestamp

    records = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []

    records.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"[EXECUTOR] Query logged at {timestamp}")


def run_sql(sql: str) -> tuple[bool, list[dict], str]:
    """Execute SQL against PostgreSQL and return rows or an error message."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)
        cursor.execute(sql)
        rows = cursor.fetchall()
        rows = [dict(row) for row in rows]
        cursor.close()
        conn.close()
        return True, rows, ""
    except Exception as exc:
        error_msg = str(exc)
        print(f"[EXECUTOR] SQL execution error: {error_msg}")
        if conn is not None:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return False, [], error_msg


def execute_query(question: str, sql: str, decomposition: dict) -> dict:
    """Run validation, execution, and one retry for broken SQL."""
    result_record = {
        "question": question,
        "sql": sql,
        "original_sql": sql,
        "result": [],
        "status": "failed",
        "retry_needed": False,
        "retry_success": False,
        "error": "",
        "row_count": 0,
        "decomposition": decomposition,
    }

    is_valid, validation_message = validate_sql(sql)
    if not is_valid:
        result_record["status"] = "blocked"
        result_record["error"] = validation_message
        log_query(result_record)
        return result_record

    print(f"[EXECUTOR] Executing SQL: {sql[:120]}{'...' if len(sql) > 120 else ''}")
    success, rows, error = run_sql(sql)

    if success:
        result_record["result"] = rows
        result_record["status"] = "success"
        result_record["row_count"] = len(rows)
        log_query(result_record)
        return result_record

    result_record["retry_needed"] = True
    result_record["error"] = error
    print(f"[EXECUTOR] First attempt failed. Error: {error}")

    try:
        fixed_sql = fix_sql(question, sql, error)
    except Exception as exc:
        result_record["error"] = f"SQL fix generation failed: {exc}"
        log_query(result_record)
        return result_record

    is_valid_fixed, validation_message_fixed = validate_sql(fixed_sql)
    if not is_valid_fixed:
        result_record["error"] = f"Fixed SQL blocked: {validation_message_fixed}"
        log_query(result_record)
        return result_record

    print(f"[EXECUTOR] Retrying with fixed SQL: {fixed_sql[:120]}{'...' if len(fixed_sql) > 120 else ''}")
    success2, rows2, error2 = run_sql(fixed_sql)
    result_record["sql"] = fixed_sql

    if success2:
        result_record["result"] = rows2
        result_record["status"] = "success"
        result_record["retry_success"] = True
        result_record["row_count"] = len(rows2)
        result_record["error"] = ""
    else:
        result_record["status"] = "failed"
        result_record["error"] = f"Original: {error} | After retry: {error2}"

    log_query(result_record)
    return result_record


if __name__ == "__main__":
    test_question = "Count all customers"
    test_sql = "SELECT COUNT(*) AS total_customers FROM customers;"
    test_decomp = {
        "intent": "Count total customers",
        "tables": ["customers"],
        "columns": ["COUNT(*)"],
        "filters": [],
        "joins": [],
    }

    print("=" * 60)
    print("EXECUTOR TEST")
    print("=" * 60)
    result = execute_query(test_question, test_sql, test_decomp)
    print(json.dumps(result, indent=2, default=str))
