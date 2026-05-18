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
  python main.py --single "Example question"
  python main.py --benchmark
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
    if result.get('result'):
        print(f"  Sample rows (up to 3):")
        for row in result['result'][:3]:
            print(f"    {row}")
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
    failed = sum(1 for r in results if r["status"] != "success")
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
