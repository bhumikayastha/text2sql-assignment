# Task 3: Text-to-SQL Pipeline
### Agentic Text-to-SQL System — FastAPI + PostgreSQL

---

## Overview

This project implements a **Text-to-SQL pipeline** that:
- Takes a natural language question as input
- Decomposes it into structured components (Intent, Tables, Columns, Filters, Joins)
- Generates a PostgreSQL SELECT query automatically
- Executes the query against the `classicmodels` database
- Handles errors and retries automatically (max 1 retry)
- Returns structured JSON output and logs every execution

---

## Project Structure

```
task3_project/
├── database.py              # PostgreSQL connection (psycopg2)
├── validator.py             # SQL safety checker (blocks DELETE/DROP/etc.)
├── sql_generator.py         # Rule-based decomposer + SQL builder
├── executor.py              # Query runner with retry logic + logging
├── main.py                  # Benchmark runner + single question mode
├── requirements.txt         # Python dependencies
├── sample_outputs/
│   └── generated_sql_outputs.txt   # All 50 generated SQL queries
└── logs/
    ├── query_log.txt              # Every query execution logged (JSON)
    └── evaluation_report.txt      # Full benchmark evaluation report
```

---

## Pipeline Architecture

```
Natural Language Question
        |
        v
[sql_generator.py]  ← Rule-Based (no API key needed)
  1. detect_tables()    — find which DB tables are needed
  2. detect_agg()       — detect COUNT / SUM / AVG / MAX / MIN
  3. detect_group_by()  — detect GROUP BY from "per X" patterns
  4. detect_filter()    — detect WHERE conditions
  5. build_columns()    — build SELECT list with quoted camelCase columns
  6. build_sql()        — assemble full SQL with JOINs
        |
        v
[validator.py]      ← Safety gate (blocks all non-SELECT queries)
        |
        v
[executor.py]       ← Run SQL → on failure → fix → retry once
        |
        v
[logs/]             ← Every attempt logged with timestamp + result
```

---

## Setup & Usage

### 1. Install dependency
```bash
pip install psycopg2-binary
```

### 2. Configure database (edit `database.py`)
```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "classicmodels",
    "user":     "postgres",
    "password": "your_password",
}
```

### 3. Test connection
```bash
python database.py
```

### 4. Run a single question
```bash
python main.py --single How many customers are from Germany
```

### 5. Run full 50-question benchmark
```bash
python main.py
```

---

## Example Output

```
QUESTION: How many customers are from Germany
[SQL_GENERATOR] Intent:   Get single COUNT value from customers
[SQL_GENERATOR] Tables:   ['customers']
[SQL_GENERATOR] Columns:  COUNT("customerNumber") AS total_customers
[SQL_GENERATOR] Filter:   country = 'Germany'
[SQL_GENERATOR] SQL:      SELECT COUNT("customerNumber") AS total_customers
                           FROM customers c WHERE country = 'Germany';
[EXECUTOR] SUCCESS - 1 row(s) returned.
Result: [{"total_customers": 13}]
```

---

## Design Decisions

| Decision | Reason |
|---|---|
| Rule-based (no LLM API) | Works offline, no API key, deterministic |
| Double-quoted column names | PostgreSQL is case-sensitive with camelCase |
| Two-step: decompose then build | Mirrors Task 2 structured thinking |
| Max 1 retry | Prevents infinite loops |
| Validator before every execution | Safety first — database never sees unsafe SQL |
| JSON structured output | Easy to evaluate, log, and compare |

---

## Evaluation Results

| Metric | Result |
|---|---|
| Total questions | 50 |
| Successful executions | 45 (90%) |
| Fixed after retry | 3 |
| Blocked (unsafe SQL) | 2 |
| Query generation latency | < 1ms (rule-based) |

---

## Safety Rules

Only `SELECT` queries are allowed. The validator **blocks** all of:
`DELETE` · `DROP` · `UPDATE` · `INSERT` · `TRUNCATE` · `ALTER` · `CREATE`

Blocked queries are logged but never sent to the database.

---

## Technologies Used

- **Python 3.11+**
- **PostgreSQL 16** (classicmodels database)
- **psycopg2** (PostgreSQL adapter)
- **Rule-based NLP** (keyword detection, no external libraries)
