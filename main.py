"""
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

HOW IT WORKS:
  For each question:
    question
      → sql_generator.generate_sql()   (decompose + generate SQL via Claude)
      → executor.execute_query()       (validate + run + retry if needed)
      → print results + log everything

ARCHITECTURE OVERVIEW:
  main.py
    └── sql_generator.py   (Claude API: decompose question → generate SQL)
    └── executor.py        (validate → run SQL → retry on failure)
          └── validator.py (safety check: block DELETE/DROP/etc.)
          └── database.py  (psycopg2 PostgreSQL connection)
          └── sql_generator.fix_sql()  (Claude API: fix broken SQL)
    └── logs/query_log.txt         (every query attempt logged)
    └── logs/evaluation_report.txt (final benchmark report)
"""

import os
import json
import datetime
from sql_generator import generate_sql
from executor import execute_query

LOG_DIR    = os.path.join(os.path.dirname(__file__), "logs")
REPORT_FILE = os.path.join(LOG_DIR, "evaluation_report.txt")
os.makedirs(LOG_DIR, exist_ok=True)


# ─── BENCHMARK QUESTIONS ──────────────────────────────────────────────────────
# These are the 50 questions from Task 2.
# The pipeline will generate SQL for each one automatically.

BENCHMARK_QUESTIONS = [
    # Section A: Simple SELECT
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

    # Section B: JOINs
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

    # Section C: Aggregate / GROUP BY
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

    # Section D: Single-Value Aggregates
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


# ─── SINGLE QUESTION PIPELINE ─────────────────────────────────────────────────

def run_pipeline(question: str) -> dict:
    """
    Runs the full Text-to-SQL pipeline for a single question.

    Steps:
      1. Generate SQL (decompose → generate via Claude)
      2. Execute SQL (validate → run → retry if needed)
      3. Return structured result dict

    Args:
        question: Natural language question string

    Returns:
        dict: Full result record (see executor.execute_query for schema)
    """
    print("\n" + "=" * 70)
    print(f"QUESTION: {question}")
    print("=" * 70)

    # Step 1: Generate SQL using LLM
    try:
        sql, decomposition = generate_sql(question)
    except Exception as e:
        print(f"[MAIN] SQL generation failed: {e}")
        return {
            "question":      question,
            "sql":           "",
            "original_sql":  "",
            "result":        [],
            "status":        "generation_failed",
            "retry_needed":  False,
            "retry_success": False,
            "error":         str(e),
            "row_count":     0,
            "decomposition": {},
        }

    # Step 2: Execute (handles validation + retry internally)
    result = execute_query(question, sql, decomposition)

    # Step 3: Print summary
    status_icon = "SUCCESS" if result["status"] == "success" else "FAILED"
    print(f"\n[RESULT] {status_icon}")
    print(f"  SQL:       {result['sql'][:100]}{'...' if len(result['sql']) > 100 else ''}")
    print(f"  Rows:      {result['row_count']}")
    print(f"  Retry:     {'Yes' if result['retry_needed'] else 'No'}")
    if result["result"]:
        # Show first 3 rows
        print(f"  Sample rows (up to 3):")
        for row in result["result"][:3]:
            print(f"    {dict(row)}")

    return result


# ─── BENCHMARK RUNNER ─────────────────────────────────────────────────────────

def run_benchmark(questions: list[str]) -> list[dict]:
    """
    Runs the pipeline on all benchmark questions.
    Saves full evaluation report to logs/evaluation_report.txt.

    Args:
        questions: List of natural language question strings

    Returns:
        list of result dicts
    """
    print("\n" + "#" * 70)
    print("  TEXT-TO-SQL BENCHMARK EVALUATION")
    print(f"  Total questions: {len(questions)}")
    print(f"  Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 70)

    all_results = []

    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}]", end="")
        result = run_pipeline(question)
        result["question_number"] = i
        all_results.append(result)

    # ── Generate evaluation report ─────────────────────────────────────────────
    save_evaluation_report(all_results)
    print_summary_table(all_results)

    return all_results


# ─── EVALUATION REPORT ────────────────────────────────────────────────────────

def save_evaluation_report(results: list[dict]):
    """
    Saves a detailed evaluation report to logs/evaluation_report.txt.
    Includes: metrics, per-question results, full SQL and outputs.
    """
    total       = len(results)
    success     = sum(1 for r in results if r["status"] == "success")
    failed      = sum(1 for r in results if r["status"] == "failed")
    blocked     = sum(1 for r in results if r["status"] == "blocked")
    gen_failed  = sum(1 for r in results if r["status"] == "generation_failed")
    retried     = sum(1 for r in results if r["retry_needed"])
    retry_fixed = sum(1 for r in results if r["retry_success"])

    success_rate = (success / total * 100) if total > 0 else 0
    retry_fix_rate = (retry_fixed / retried * 100) if retried > 0 else 0

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("=" * 70)
    lines.append("  TEXT-TO-SQL SYSTEM - EVALUATION REPORT")
    lines.append(f"  Generated: {now}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("PIPELINE ARCHITECTURE:")
    lines.append("  Natural Language Question")
    lines.append("    -> sql_generator.py  (Claude API: decompose + generate SQL)")
    lines.append("    -> validator.py      (block unsafe SQL: DELETE/DROP/etc.)")
    lines.append("    -> executor.py       (run query, retry once on failure)")
    lines.append("    -> database.py       (psycopg2 PostgreSQL connection)")
    lines.append("")
    lines.append("DESIGN DECISIONS:")
    lines.append("  - Used Claude (claude-sonnet-4-20250514) for SQL generation")
    lines.append("  - Two-step prompting: decompose first, then generate SQL")
    lines.append("  - Safety validation blocks all non-SELECT queries")
    lines.append("  - On failure: LLM re-generates SQL using the error message")
    lines.append("  - Maximum 1 retry per query")
    lines.append("  - All queries logged to logs/query_log.txt")
    lines.append("")
    lines.append("-" * 70)
    lines.append("SUMMARY METRICS")
    lines.append("-" * 70)
    lines.append(f"  Total questions evaluated:   {total}")
    lines.append(f"  Successful executions:       {success}")
    lines.append(f"  Failed executions:           {failed}")
    lines.append(f"  Blocked (unsafe SQL):        {blocked}")
    lines.append(f"  Generation failures:         {gen_failed}")
    lines.append(f"  Retries attempted:           {retried}")
    lines.append(f"  Fixed after retry:           {retry_fixed}")
    lines.append(f"  SQL Execution Success Rate:  {success_rate:.1f}%")
    lines.append(f"  Retry Fix Rate:              {retry_fix_rate:.1f}%")
    lines.append("")
    lines.append("-" * 70)
    lines.append("PER-QUESTION RESULTS")
    lines.append("-" * 70)
    lines.append(
        f"{'#':<4} {'Question':<42} {'SQL Generated':<14} {'Executed':<10} "
        f"{'Rows':<6} {'Retry':<7} {'Status'}"
    )
    lines.append("-" * 70)

    for r in results:
        qnum     = str(r.get("question_number", "?"))
        q        = r["question"][:40] + ("..." if len(r["question"]) > 40 else "")
        sql_gen  = "Yes" if r["sql"] else "No"
        executed = "Yes" if r["status"] in ("success", "failed") else "No"
        rows     = str(r["row_count"])
        retry    = "Yes" if r["retry_needed"] else "No"
        status   = r["status"].upper()

        lines.append(
            f"{qnum:<4} {q:<42} {sql_gen:<14} {executed:<10} {rows:<6} {retry:<7} {status}"
        )

    lines.append("")
    lines.append("-" * 70)
    lines.append("DETAILED RESULTS (SQL + OUTPUT)")
    lines.append("-" * 70)

    for r in results:
        lines.append(f"\nQ{r.get('question_number','?')}: {r['question']}")
        lines.append(f"  Status:  {r['status'].upper()}")
        lines.append(f"  SQL:     {r['sql']}")
        if r.get("retry_needed"):
            lines.append(f"  Orig SQL:{r.get('original_sql','')}")
            lines.append(f"  Error:   {r.get('error','')[:120]}")
        lines.append(f"  Rows:    {r['row_count']}")
        if r["result"]:
            lines.append(f"  Sample:  {str(r['result'][:2])}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[MAIN] Evaluation report saved to: {REPORT_FILE}")


# ─── SUMMARY TABLE PRINTER ────────────────────────────────────────────────────

def print_summary_table(results: list[dict]):
    """Prints a clean summary table to the console after benchmark run."""
    total       = len(results)
    success     = sum(1 for r in results if r["status"] == "success")
    failed      = sum(1 for r in results if r["status"] in ("failed", "blocked", "generation_failed"))
    retried     = sum(1 for r in results if r["retry_needed"])
    retry_fixed = sum(1 for r in results if r["retry_success"])
    success_rate = (success / total * 100) if total > 0 else 0

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
    print(f"  Query log:   logs/query_log.txt\n")


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Run with a single test question (quick test)
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        question = " ".join(sys.argv[2:]) or "How many customers are from the USA?"
        result = run_pipeline(question)
        print("\nFull result JSON:")
        print(json.dumps(result, indent=2, default=str))

    # Run full benchmark (default)
    else:
        run_benchmark(BENCHMARK_QUESTIONS)
