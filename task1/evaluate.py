import psycopg2
import pandas as pd
import time
import json

# ── Database connection ──────────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="classicmodels",
        user="postgres",
        password="postgres"    # replace with your actual password
    )


# ── Metric 1: Exact Match ────────────────────────────────────────────────
def exact_match(predicted_sql: str, ground_truth_sql: str) -> bool:
    pred  = " ".join(predicted_sql.lower().split())
    truth = " ".join(ground_truth_sql.lower().split())
    return pred == truth


# ── Metric 2: Execution Success ──────────────────────────────────────────
def execution_success(pred_sql: str, conn) -> bool:
    try:
        cursor = conn.cursor()
        cursor.execute(pred_sql)
        cursor.fetchall()
        conn.rollback()
        return True
    except Exception as e:
        conn.rollback()
        return False


# ── Metric 3: Execution Accuracy ─────────────────────────────────────────
def execution_accuracy(pred_sql: str, truth_sql: str, conn) -> bool:
    try:
        pred_df  = pd.read_sql(pred_sql,  conn)
        truth_df = pd.read_sql(truth_sql, conn)

        # Sort both so row order does not matter
        pred_df  = pred_df.sort_values(
            by=pred_df.columns.tolist()
        ).reset_index(drop=True)
        truth_df = truth_df.sort_values(
            by=truth_df.columns.tolist()
        ).reset_index(drop=True)

        return pred_df.equals(truth_df)
    except Exception:
        return False


# ── Metric 4: Execution Time ─────────────────────────────────────────────
def measure_execution_time(sql: str, conn) -> float:
    start = time.time()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cursor.fetchall()
        conn.rollback()
    except Exception:
        conn.rollback()
    return round((time.time() - start) * 1000, 2)   # milliseconds


# ── Main evaluation runner ────────────────────────────────────────────────
def evaluate_all(benchmark: list[dict]) -> list[dict]:
    """
    benchmark: list of dicts with keys:
        - question_id  (int)
        - question     (str)
        - ground_truth (str)
        - predicted    (str)   ← agent output goes here in Tasks 3 & 4
    """
    conn    = get_connection()
    results = []

    for item in benchmark:
        pred  = item["predicted"]
        truth = item["ground_truth"]

        result = {
            "question_id":        item["question_id"],
            "question":           item["question"],
            "ground_truth_sql":   truth,
            "predicted_sql":      pred,
            "exact_match":        exact_match(pred, truth),
            "execution_success":  execution_success(pred, conn),
            "execution_accuracy": execution_accuracy(pred, truth, conn),
            "execution_time_ms":  measure_execution_time(pred, conn),
        }
        results.append(result)
        print(f"Q{item['question_id']:02d} | EM={result['exact_match']} | "
              f"ES={result['execution_success']} | "
              f"EA={result['execution_accuracy']} | "
              f"{result['execution_time_ms']}ms")

    conn.close()
    return results


def print_summary(results: list[dict]) -> None:
    total = len(results)
    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    print(f"Total questions:       {total}")
    print(f"Exact Match Rate:      {sum(r['exact_match'] for r in results)}/{total}")
    print(f"Execution Success:     {sum(r['execution_success'] for r in results)}/{total}")
    print(f"Execution Accuracy:    {sum(r['execution_accuracy'] for r in results)}/{total}")
    avg_time = sum(r['execution_time_ms'] for r in results) / total
    print(f"Avg Execution Time:    {avg_time:.1f}ms")
    print("="*50)


# ── Run a quick self-test using ground truth as both input and output ─────
if __name__ == "__main__":

    # Load your 50 ground truth queries here
    # For now, testing with 3 sample queries
    sample_benchmark = [
        {
            "question_id": 41,
            "question": "Total number of customers",
            "ground_truth": 'SELECT COUNT(*) AS "totalCustomers" FROM customers;',
            "predicted":    'SELECT COUNT(*) AS "totalCustomers" FROM customers;',
        },
        {
            "question_id": 42,
            "question": "Total number of products",
            "ground_truth": 'SELECT COUNT(*) AS "totalProducts" FROM products;',
            "predicted":    'SELECT COUNT(*) AS "totalProducts" FROM products;',
        },
        {
            "question_id": 43,
            "question": "Total revenue from payments",
            "ground_truth": 'SELECT ROUND(SUM("amount"), 2) AS "totalRevenue" FROM payments;',
            "predicted":    'SELECT ROUND(SUM("amount"), 2) AS "totalRevenue" FROM payments;',
        },
    ]

    results = evaluate_all(sample_benchmark)
    print_summary(results)

    # Save results to JSON
    with open("task1\\evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to task1\\evaluation_results.json")