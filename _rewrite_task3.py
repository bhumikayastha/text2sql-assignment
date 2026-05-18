from pathlib import Path

files = {
    'executor.py': '''"""
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
''',
    'sql_generator.py': '''"""
sql_generator.py
----------------
Handles the three-step LLM prompt chain for SQL decomposition, generation, and fixing.
"""

import json
import os
import re
from typing import Tuple

import openai
from dotenv import load_dotenv
from prompts.templates import (
    DECOMPOSE_PROMPT,
    GENERATE_SQL_PROMPT,
    FIX_SQL_PROMPT,
    SCHEMA_CONTEXT,
)

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOKENS = 800
TEMPERATURE = 0.0


class SQLGenerationError(Exception):
    pass


def llm_call(messages, max_tokens=MAX_TOKENS):
    if not openai.api_key:
        raise SQLGenerationError("OPENAI_API_KEY is not configured in the environment.")

    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content.strip()
    return content


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise SQLGenerationError("LLM response did not contain a valid JSON object.")
    payload = cleaned[start:end + 1]
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SQLGenerationError(f"Failed to parse JSON from LLM response: {exc}\nResponse: {payload}")


def extract_sql(text: str) -> str:
    cleaned = text.strip()
    if "```sql" in cleaned.lower():
        content = re.split(r"```sql", cleaned, flags=re.IGNORECASE)[1]
        cleaned = content.split("```", 1)[0].strip()
    if not cleaned.upper().startswith("SELECT"):
        match = re.search(r"(SELECT[\s\S]+?;)", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
    if not cleaned.endswith(";"):
        cleaned += ";"
    if not cleaned.upper().startswith("SELECT"):
        raise SQLGenerationError("LLM produced a non-SELECT query.")
    return cleaned


def decompose_question(question: str) -> dict:
    prompt = DECOMPOSE_PROMPT.strip()
    messages = [
        {"role": "system", "content": "You are a SQL decomposition assistant."},
        {"role": "user", "content": f"{prompt}\n\nQuestion: {question}"},
    ]
    response = llm_call(messages)
    payload = extract_json(response)

    normalized = {
        "intent": payload.get("Intent") or payload.get("intent") or "",
        "tables": payload.get("Tables") or payload.get("tables") or [],
        "columns": payload.get("Columns") or payload.get("columns") or [],
        "filters": payload.get("Filters") or payload.get("filters") or [],
        "joins": payload.get("Joins") or payload.get("joins") or [],
    }

    if not normalized["tables"]:
        raise SQLGenerationError("Decomposition did not include any tables.")
    return normalized


def generate_query(question: str, decomposition: dict) -> str:
    decomposition_json = json.dumps(decomposition, indent=2)
    prompt = GENERATE_SQL_PROMPT.format(
        schema=SCHEMA_CONTEXT,
        decomposition=decomposition_json,
    )
    messages = [
        {"role": "system", "content": "You are a PostgreSQL SQL generation assistant."},
        {"role": "user", "content": prompt},
    ]
    response = llm_call(messages)
    return extract_sql(response)


def generate_sql(question: str) -> Tuple[str, dict]:
    decomposition = decompose_question(question)
    sql = generate_query(question, decomposition)
    return sql, decomposition


def fix_sql(question: str, sql: str, error_message: str) -> str:
    prompt = FIX_SQL_PROMPT.format(question=question, sql=sql, error=error_message)
    messages = [
        {"role": "system", "content": "You are an expert PostgreSQL fixer. Fix broken SELECT statements."},
        {"role": "user", "content": prompt},
    ]
    response = llm_call(messages)
    fixed_sql = extract_sql(response)
    return fixed_sql


if __name__ == "__main__":
    questions = [
        "Show all orders placed by customers in Germany",
        "Count customers per country",
        "Get employees with office city",
        "Total revenue from payments",
    ]
    for question in questions:
        print("Question:", question)
        sql, decomp = generate_sql(question)
        print("SQL:", sql)
        print("Decomposition:", decomp)
        print("" + "-" * 80 + "\n")
''',
    'main.py': '''"""
main.py
-------
The main entry point for the Text-to-SQL pipeline.

This file:
  1. Runs the full pipeline on a set of benchmark questions
  2. Prints results to console
  3. Saves a full evaluation report to logs/evaluation_report.txt
  4. Prints a summary table at the end

USAGE:
  python main.py
"""

import os
import json
import datetime
import argparse
from sql_generator import generate_sql
from executor import execute_query

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
REPORT_FILE = os.path.join(LOG_DIR, "evaluation_report.txt")

os.makedirs(LOG_DIR, exist_ok=True)

BENCHMARK_QUESTIONS = [
    "List all products",
    "Get all customers",
    "Show all orders",
    "List all employees",
    "Get all offices",
    "Show all product lines",
    "List all payments",
    "Get product names and prices",
    "Get customer names and cities",
    "List employee first and last names",
    "Get all order dates",
    "Show product vendor list",
    "Get all product codes",
    "List all countries from offices",
    "Show all order statuses",
    "Get all payment amounts",
    "List all job titles",
    "Get customer phone numbers",
    "Show product MSRP values",
    "List order numbers",
    "Get orders with customer names",
    "Get employees with office city",
    "Get payments with customer names",
    "Get order details with product names",
    "Get products with product line description",
    "Get customers with sales rep names",
    "Get orders with customer city",
    "Get employees and their manager",
    "Get orderdetails with product vendor",
    "Get payments with customer country",
    "Count customers per country",
    "Total payments per customer",
    "Number of orders per status",
    "Products per product line",
    "Employees per office",
    "Total stock per product vendor",
    "Average buy price per product line",
    "Orders per customer",
    "Max MSRP per product line",
    "Min buy price per vendor",
    "Total number of customers",
    "Total number of products",
    "Total revenue from payments",
    "Average product price",
    "Max payment amount",
    "Min payment amount",
    "Count total orders",
    "Total quantity in stock",
    "Average MSRP",
    "Number of employees",
]


def run_pipeline(question: str) -> dict:
    print("\n" + "=" * 70)
    print(f"QUESTION: {question}")
    print("=" * 70)

    try:
        sql, decomposition = generate_sql(question)
    except Exception as exc:
        print(f"[MAIN] SQL generation failed: {exc}")
        return {
            "question": question,
            "sql": "",
            "original_sql": "",
            "result": [],
            "status": "generation_failed",
            "retry_needed": False,
            "retry_success": False,
            "error": str(exc),
            "row_count": 0,
            "decomposition": {},
        }

    result = execute_query(question, sql, decomposition)
    print(f"\n[RESULT] {'SUCCESS' if result['status'] == 'success' else 'FAILED'}")
    print(f"  SQL:       {result['sql'][:100]}{'...' if len(result['sql']) > 100 else ''}")
    print(f"  Rows:      {result['row_count']}")
    print(f"  Retry:     {'Yes' if result['retry_needed'] else 'No'}")
    return result


def run_benchmark(questions: list[str]) -> list[dict]:
    print("\n" + "#" * 70)
    print("  TEXT-TO-SQL BENCHMARK EVALUATION")
    print(f"  Total questions: {len(questions)}")
    print(f"  Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 70)

    results = []
    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}]", end="")
        result = run_pipeline(question)
        result["question_number"] = i
        results.append(result)

    save_evaluation_report(results)
    print_summary_table(results)
    return results


def save_evaluation_report(results: list[dict]):
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    blocked = sum(1 for r in results if r["status"] == "blocked")
    gen_failed = sum(1 for r in results if r["status"] == "generation_failed")
    retried = sum(1 for r in results if r["retry_needed"])
    retry_fixed = sum(1 for r in results if r["retry_success"])

    success_rate = (success / total * 100) if total else 0
    retry_fix_rate = (retry_fixed / retried * 100) if retried else 0

    lines = [
        "=" * 70,
        "  TEXT-TO-SQL SYSTEM - EVALUATION REPORT",
        f"  Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 70,
        "",
        "PIPELINE ARCHITECTURE:",
        "  Natural Language Question",
        "    -> sql_generator.py  (LLM prompt chaining)",
        "    -> validator.py      (block unsafe SQL)",
        "    -> executor.py       (run query, retry once)",
        "    -> database.py       (PostgreSQL connection)",
        "",
        "SUMMARY METRICS",
        "-" * 70,
        f"  Total questions evaluated:   {total}",
        f"  Successful executions:       {success}",
        f"  Failed executions:           {failed}",
        f"  Blocked (unsafe SQL):        {blocked}",
        f"  Generation failures:         {gen_failed}",
        f"  Retries attempted:           {retried}",
        f"  Fixed after retry:           {retry_fixed}",
        f"  SQL Execution Success Rate:  {success_rate:.1f}%",
        f"  Retry Fix Rate:              {retry_fix_rate:.1f}%",
        "",
        "PER-QUESTION RESULTS",
        "-" * 70,
    ]

    for r in results:
        lines.append(f"Q{r.get('question_number','?')}: {r['question']}")
        lines.append(f"  Status: {r['status']}")
        lines.append(f"  SQL: {r['sql']}")
        lines.append(f"  Rows: {r['row_count']}")
        lines.append("")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[MAIN] Evaluation report saved to: {REPORT_FILE}")


def print_summary_table(results: list[dict]):
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] not in ("success",))
    retried = sum(1 for r in results if r["retry_needed"])
    retry_fixed = sum(1 for r in results if r["retry_success"])
    success_rate = (success / total * 100) if total else 0

    print("\n\n" + "=" * 70)
    print("  BENCHMARK COMPLETE - SUMMARY")
    print("=" * 70)
    print(f"  Total questions:      {total}")
    print(f"  Successful:           {success}  ({success_rate:.1f}%)")
    print(f"  Failed:               {failed}")
    print(f"  Retries attempted:    {retried}")
    print(f"  Fixed after retry:    {retry_fixed}")
    print("=" * 70)
    print(f"\n  Full report: logs/evaluation_report.txt")
    print(f"  Query log:   logs/query_logs.json\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Text-to-SQL pipeline.")
    parser.add_argument("--single", type=str, help="Run one natural language question.")
    parser.add_argument("--benchmark", action="store_true", help="Run the full benchmark set.")
    args = parser.parse_args()

    if args.single:
        run_pipeline(args.single)
    else:
        run_benchmark(BENCHMARK_QUESTIONS)
''',
    'README.md': '''# Task 3: Text-to-SQL Pipeline

## Overview

This project implements a prompt-chaining Text-to-SQL pipeline using FastAPI and PostgreSQL.
The system:
- Decomposes natural language queries into structured SQL components
- Uses LLM prompt chaining to generate PostgreSQL `SELECT` statements
- Validates generated SQL for safety
- Executes SQL against PostgreSQL
- Retries once if execution fails using LLM-driven fixes
- Logs every query execution in `logs/query_logs.json`

## Files

- `database.py` — PostgreSQL connection helper
- `sql_generator.py` — LLM prompt chain for decomposition, generation, and fix
- `validator.py` — Safety checks blocking non-SELECT statements
- `executor.py` — Executes SQL, handles retry/fix, and logs results
- `main.py` — CLI runner for single questions and benchmark mode
- `fastapi_app.py` — FastAPI service for HTTP query execution
- `streamlit_app.py` — Optional Streamlit UI for chat-like usage
- `evaluate.py` — Benchmark evaluation script
- `prompts/templates.py` — SQL prompts and schema context for the LLM
- `docker-compose.yml` — PostgreSQL + app service for containerized deployment
- `Dockerfile` — Builds the Python app container
- `.env.example` — Example environment variables
- `logs/query_logs.json` — JSON file used for execution logging

## Setup

1. Copy `.env.example` to `.env`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your OpenAI API key and database connection in `.env`.
4. Test the database connection:

```bash
python database.py
```

## Run locally

### FastAPI

```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8501
```

### Streamlit UI

```bash
streamlit run streamlit_app.py
```

### Run one question

```bash
python main.py --single "Show all orders placed by customers in Germany"
```

### Run benchmark

```bash
python main.py --benchmark
```

### Run evaluation script

```bash
python evaluate.py
```

## Docker

```bash
docker compose up --build
```

Then visit `http://localhost:8501` for the FastAPI service.

## Notes

- Only `SELECT` queries are permitted.
- The system blocks `DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, and `TRUNCATE`.
- Maximum one retry is allowed for failed SQL executions.
''',
    'requirements.txt': '''fastapi>=0.111.0
uvicorn[standard]>=0.23.0
openai>=1.0.0
python-dotenv>=1.0.0
psycopg2-binary>=2.9.9
streamlit>=1.25.0
''',
}

root = Path(__file__).parent
for name, content in files.items():
    path = root / name
    path.write_text(content, encoding='utf-8')
    print(f'Wrote {path}')
'''}

root = Path('d:/AIF week3/task3_project')
for name, content in files.items():
    (root / name).write_text(content, encoding='utf-8')
    print(f'Wrote {root / name}')
