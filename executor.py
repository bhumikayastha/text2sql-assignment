"""
executor.py
-----------
Executes SQL queries against PostgreSQL.
Handles errors, retries once if execution fails,
and logs every query execution to logs/query_log.txt

HOW TO USE:
    from executor import execute_query
    result = execute_query(question, sql, decomposition)
"""

import os
import json
import datetime
from database import get_connection
from validator import validate_sql
from sql_generator import fix_sql

# ─── LOG FILE PATH ────────────────────────────────────────────────────────────
LOG_DIR  = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "query_log.txt")

# Make sure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)


# ─── LOGGING FUNCTION ─────────────────────────────────────────────────────────

def log_query(entry: dict):
    """
    Appends a query execution record to logs/query_log.txt.

    Each entry is written as formatted JSON followed by a separator line.
    This makes the log easy to read and parse later.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry["timestamp"] = timestamp

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, indent=2, default=str))
        f.write("\n" + "-" * 60 + "\n")

    print(f"[EXECUTOR] Query logged at {timestamp}")


# ─── RUN SQL AGAINST DATABASE ─────────────────────────────────────────────────

def run_sql(sql: str) -> tuple[bool, list, str]:
    """
    Runs a single SQL query against the PostgreSQL database.

    Args:
        sql: The SQL query string to execute

    Returns:
        tuple: (success: bool, rows: list, error: str)
               - success = True if query ran without error
               - rows    = list of result rows (list of dicts)
               - error   = empty string if success, error message if failed

    Example:
        ok, rows, err = run_sql("SELECT COUNT(*) FROM customers;")
        # ok=True, rows=[{"count": 122}], err=""
    """
    try:
        conn = get_connection()
        # Use RealDictCursor so each row is a dict {column: value}
        cursor = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)

        cursor.execute(sql)
        rows = cursor.fetchall()

        # Convert from RealDictRow to plain dict for JSON serialization
        rows = [dict(row) for row in rows]

        cursor.close()
        conn.close()
        return True, rows, ""

    except Exception as e:
        error_msg = str(e)
        print(f"[EXECUTOR] SQL execution error: {error_msg}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False, [], error_msg


# ─── MAIN EXECUTE FUNCTION (WITH RETRY) ───────────────────────────────────────

def execute_query(question: str, sql: str, decomposition: dict) -> dict:
    """
    Full execution pipeline with validation and one retry attempt.

    Steps:
      1. Validate SQL for safety (no DELETE/DROP/etc.)
      2. Run the SQL query
      3. If it fails → fix the SQL using the error → retry once
      4. Log everything
      5. Return a structured result dict

    Args:
        question:      Original natural language question
        sql:           Generated SQL query string
        decomposition: The structured decomposition dict from sql_generator

    Returns:
        dict with keys:
          - question:       original question
          - sql:            the SQL that was run (may be fixed version)
          - original_sql:   the first SQL attempt
          - result:         list of result rows
          - status:         "success" | "failed" | "blocked"
          - retry_needed:   True if a retry was attempted
          - retry_success:  True if retry fixed the problem
          - error:          error message if failed
          - row_count:      number of rows returned
          - decomposition:  the structured decomposition used

    Example return:
        {
            "question": "How many customers are from the USA?",
            "sql": "SELECT COUNT(customerNumber) FROM customers WHERE country = 'USA';",
            "original_sql": "SELECT COUNT(customerNumber) FROM customers WHERE country = 'USA';",
            "result": [{"count": 36}],
            "status": "success",
            "retry_needed": False,
            "retry_success": False,
            "error": "",
            "row_count": 1,
            "decomposition": {...}
        }
    """

    result_record = {
        "question":      question,
        "sql":           sql,
        "original_sql":  sql,
        "result":        [],
        "status":        "failed",
        "retry_needed":  False,
        "retry_success": False,
        "error":         "",
        "row_count":     0,
        "decomposition": decomposition,
    }

    # ── Step 1: Validate SQL safety ────────────────────────────────────────────
    is_valid, validation_message = validate_sql(sql)
    if not is_valid:
        print(f"[EXECUTOR] SQL BLOCKED: {validation_message}")
        result_record["status"] = "blocked"
        result_record["error"]  = validation_message
        log_query(result_record)
        return result_record

    print(f"[EXECUTOR] Executing SQL: {sql[:100]}{'...' if len(sql) > 100 else ''}")

    # ── Step 2: First attempt ──────────────────────────────────────────────────
    success, rows, error = run_sql(sql)

    if success:
        result_record["result"]    = rows
        result_record["status"]    = "success"
        result_record["row_count"] = len(rows)
        print(f"[EXECUTOR] SUCCESS - {len(rows)} row(s) returned.")
        log_query(result_record)
        return result_record

    # ── Step 3: First attempt failed → retry once ─────────────────────────────
    print(f"[EXECUTOR] First attempt FAILED. Error: {error}")
    print(f"[EXECUTOR] Attempting retry with SQL fix...")
    result_record["retry_needed"] = True
    result_record["error"]        = error

    # Ask LLM to fix the broken SQL
    try:
        fixed_sql = fix_sql(question, sql, error)
    except Exception as e:
        print(f"[EXECUTOR] Could not generate fixed SQL: {e}")
        result_record["status"] = "failed"
        log_query(result_record)
        return result_record

    # Validate the fixed SQL too
    is_valid_fixed, fix_validation_msg = validate_sql(fixed_sql)
    if not is_valid_fixed:
        print(f"[EXECUTOR] Fixed SQL also blocked: {fix_validation_msg}")
        result_record["status"] = "failed"
        result_record["error"]  = f"Original: {error} | Fixed SQL blocked: {fix_validation_msg}"
        log_query(result_record)
        return result_record

    # ── Step 4: Execute the fixed SQL ──────────────────────────────────────────
    print(f"[EXECUTOR] Retrying with fixed SQL: {fixed_sql[:100]}")
    success2, rows2, error2 = run_sql(fixed_sql)

    result_record["sql"] = fixed_sql   # update to show the fixed version

    if success2:
        result_record["result"]        = rows2
        result_record["status"]        = "success"
        result_record["retry_success"] = True
        result_record["row_count"]     = len(rows2)
        result_record["error"]         = ""
        print(f"[EXECUTOR] RETRY SUCCESS - {len(rows2)} row(s) returned.")
    else:
        result_record["status"] = "failed"
        result_record["error"]  = f"Original: {error} | After retry: {error2}"
        print(f"[EXECUTOR] RETRY also FAILED: {error2}")

    log_query(result_record)
    return result_record


# ─── QUICK TEST ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test with a hardcoded SQL (no LLM needed for this test)
    test_question = "Count all customers"
    test_sql      = "SELECT COUNT(*) AS total_customers FROM customers;"
    test_decomp   = {
        "intent": "Count total customers",
        "tables": ["customers"],
        "columns": ["COUNT(*)"],
        "filters": [],
        "joins": []
    }

    print("=" * 60)
    print("EXECUTOR TEST")
    print("=" * 60)
    result = execute_query(test_question, test_sql, test_decomp)
    print("\nResult:")
    print(json.dumps(result, indent=2, default=str))
