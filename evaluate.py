import json
import os
import datetime
from main import run_pipeline

BENCHMARK_DATASET = [
    {
        "question": "List all products",
        "expected_sql": "SELECT \"productCode\", \"productName\", \"buyPrice\" FROM products;"
    },
    {
        "question": "Get all customers",
        "expected_sql": "SELECT \"customerNumber\", \"customerName\", city FROM customers;"
    },
    {
        "question": "Show all orders placed by customers in Germany",
        "expected_sql": "SELECT o.\"orderNumber\", c.\"customerName\" FROM orders o JOIN customers c ON o.\"customerNumber\" = c.\"customerNumber\" WHERE c.country = 'Germany';"
    },
    {
        "question": "Count customers per country",
        "expected_sql": "SELECT country, COUNT(\"customerNumber\") AS total FROM customers GROUP BY country;"
    },
    {
        "question": "Get employees with office city",
        "expected_sql": "SELECT e.\"firstName\", e.\"lastName\", of.city FROM employees e JOIN offices of ON e.\"officeCode\" = of.\"officeCode\";"
    },
]

EVALUATION_REPORT_PATH = os.path.join(os.path.dirname(__file__), "logs", "evaluation_report.txt")


def normalize_sql(sql: str) -> str:
    return " ".join(sql.strip().lower().replace("\n", " ").split())


def run_evaluation(dataset: list[dict]) -> list[dict]:
    results = []
    for item in dataset:
        question = item["question"]
        expected_sql = item.get("expected_sql")
        record = run_pipeline(question)
        record["expected_sql"] = expected_sql
        record["executed_successfully"] = record["status"] == "success"
        record["correct_sql"] = (
            normalize_sql(record["sql"]) == normalize_sql(expected_sql)
            if expected_sql else None
        )
        record["retry_needed"] = record["retry_needed"]
        record["final_status"] = record["status"]
        results.append(record)
    return results


def save_report(results: list[dict]):
    total = len(results)
    success = sum(1 for r in results if r["executed_successfully"])
    retry_needed = sum(1 for r in results if r["retry_needed"])
    retry_success = sum(1 for r in results if r["retry_success"])
    failed = total - success

    lines = ["=" * 80, "TEXT-TO-SQL EVALUATION REPORT", f"Generated: {datetime.datetime.now()}", "=" * 80, ""]
    lines.append(f"Total questions: {total}")
    lines.append(f"SQL execution success rate: {success}/{total} ({success / total * 100:.1f}%)")
    lines.append(f"Retry needed: {retry_needed}")
    lines.append(f"Retry success: {retry_success}")
    lines.append(f"Total failed queries: {failed}")
    lines.append("")
    lines.append("Per question results:")
    for idx, row in enumerate(results, 1):
        lines.append(f"{idx}. {row['question']}")
        lines.append(f"   Generated SQL: {row['sql']}")
        lines.append(f"   Executed successfully: {row['executed_successfully']}")
        lines.append(f"   Correct SQL: {row['correct_sql']}")
        lines.append(f"   Retry needed: {row['retry_needed']}")
        lines.append(f"   Final status: {row['final_status']}")
        lines.append("")

    os.makedirs(os.path.dirname(EVALUATION_REPORT_PATH), exist_ok=True)
    with open(EVALUATION_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("Evaluation report saved to:", EVALUATION_REPORT_PATH)


if __name__ == "__main__":
    results = run_evaluation(BENCHMARK_DATASET)
    save_report(results)
