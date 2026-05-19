"""
validator.py
------------
Validates SQL queries for safety before execution.

Rules:
  - Only SELECT queries are allowed
  - DELETE / DROP / UPDATE / INSERT / TRUNCATE are blocked
  - Multiple statements (semicolon tricks) are blocked
  - Empty queries are blocked

HOW TO USE:
    from validator import validate_sql
    is_safe, message = validate_sql("SELECT * FROM customers")
"""

import re


# ─── BLOCKED SQL KEYWORDS ─────────────────────────────────────────────────────
BLOCKED_KEYWORDS = [
    "DELETE",
    "DROP",
    "UPDATE",
    "INSERT",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "REPLACE",
    "MERGE",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "REVOKE",
]


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validates a SQL query for safety.

    Args:
        sql (str): The SQL query string to validate.

    Returns:
        tuple: (is_valid: bool, message: str)
               If valid  → (True,  "SQL is valid.")
               If invalid → (False, reason why it failed)

    Example:
        >>> validate_sql("SELECT * FROM customers")
        (True, "SQL is valid.")

        >>> validate_sql("DELETE FROM customers")
        (False, "Blocked keyword detected: DELETE")
    """

    # 1. Check for empty query
    if not sql or not sql.strip():
        return False, "SQL query is empty."

    # 2. Normalize: uppercase for keyword matching, strip whitespace
    sql_upper = sql.strip().upper()

    # 3. Check that query starts with SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed. Query must start with SELECT."

    # 4. Check for blocked keywords (as whole words, not substrings)
    for keyword in BLOCKED_KEYWORDS:
        # Use word boundary regex to avoid false positives (e.g. 'CREATED' matching 'CREATE')
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Blocked keyword detected: {keyword}. Only SELECT is allowed."

    # 5. Block multiple statements (SQL injection via semicolons)
    # Strip trailing semicolon, then check if another semicolon remains
    sql_stripped = sql.strip().rstrip(";")
    if ";" in sql_stripped:
        return False, "Multiple SQL statements detected. Only one SELECT is allowed per query."

    # 6. Block SQL comments (-- or /* */) which could be used to bypass checks
    if "--" in sql or "/*" in sql or "*/" in sql:
        return False, "SQL comments are not allowed in queries."

    # All checks passed
    return True, "SQL is valid."


def print_validation_result(sql: str):
    """Helper to print a formatted validation result."""
    is_valid, message = validate_sql(sql)
    status = "VALID" if is_valid else "BLOCKED"
    print(f"[VALIDATOR] [{status}] {message}")
    print(f"            Query: {sql[:80]}{'...' if len(sql) > 80 else ''}")
    return is_valid, message


# ─── QUICK TEST ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        "SELECT * FROM customers",
        "SELECT COUNT(*) FROM orders WHERE status = 'Shipped'",
        "DELETE FROM customers WHERE customerNumber = 1",
        "DROP TABLE orders",
        "UPDATE customers SET city = 'Paris'",
        "INSERT INTO customers VALUES (1, 'Test')",
        "SELECT * FROM customers; DROP TABLE customers",
        "",
        "SELECT * FROM customers -- comment",
    ]

    print("=" * 60)
    print("VALIDATOR TEST RESULTS")
    print("=" * 60)
    for sql in test_cases:
        print_validation_result(sql)
        print()
