
# Task 3: Text-to-SQL Pipeline
## Agentic Text-to-SQL System (FastAPI + PostgreSQL)

---

## PROJECT STRUCTURE

```
task3_project/
├── database.py        # PostgreSQL connection
├── validator.py       # SQL safety checker (blocks DELETE/DROP/etc.)
├── sql_generator.py   # Claude API: decomposes question + generates SQL
├── executor.py        # Runs SQL, handles retry on failure, logs everything
├── main.py            # Entry point: runs full benchmark or single question
├── requirements.txt   # Python dependencies
├── logs/
│   ├── query_log.txt          # Every query attempt logged here
│   └── evaluation_report.txt  # Full benchmark report saved here
└── README.txt         # This file
```

---

## SETUP STEPS

### Step 1: Install Python dependency
Open PowerShell or Command Prompt and run:

```
pip install psycopg2-binary
```

### Step 2: Configure database connection
Open `database.py` and edit the DB_CONFIG section:

```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "classicmodels",   # your DB name
    "user":     "postgres",        # your username
    "password": "your_password",   # your password
}
```

### Step 3: Test database connection
```
python database.py
```
You should see: "Connected successfully!"

### Step 4: Test the validator (no DB needed)
```
python validator.py
```

### Step 5: Run the full benchmark
```
python main.py
```

### Step 6: Run a single question (for testing)
```
python main.py --single How many customers are from the USA?
```

---

## HOW THE PIPELINE WORKS

```
Natural Language Question
        |
        v
[sql_generator.py]
  Step 1: Call Claude API - decompose question into:
          { intent, tables, columns, filters, joins }
  Step 2: Call Claude API - generate SQL from decomposition
        |
        v
[validator.py]
  Check: Is it a SELECT? No DELETE/DROP/UPDATE/INSERT?
  If blocked -> return error immediately
        |
        v
[executor.py]
  Attempt 1: Run SQL against PostgreSQL
  If success -> return results
  If failure -> 
        |
        v
[sql_generator.fix_sql()]
  Call Claude API with: original question + broken SQL + error message
  Claude returns: fixed SQL
        |
        v
[executor.py]
  Attempt 2 (retry): Run fixed SQL
  Log result (success or final failure)
        |
        v
[main.py]
  Collect all results
  Save evaluation_report.txt
  Print summary table
```

---

## OUTPUT FILES

### logs/query_log.txt
Every query attempt is logged here in JSON format:
```json
{
  "question": "...",
  "sql": "...",
  "status": "success",
  "retry_needed": false,
  "row_count": 5,
  "timestamp": "2025-01-01 12:00:00"
}
```

### logs/evaluation_report.txt
Full benchmark report with:
- Summary metrics (success rate, retry rate)
- Per-question table
- Full SQL and results for each question

---

## DESIGN DECISIONS

1. **Two-step prompting**: First decompose (intent/tables/columns/filters/joins),
   then generate SQL. This matches the Task 2 structured thinking approach.

2. **LLM choice**: Claude (claude-sonnet-4-20250514) - accessed via the
   Anthropic API without requiring an API key (handled by environment).

3. **Safety first**: validator.py blocks ALL non-SELECT queries before
   they ever reach the database.

4. **Retry logic**: On failure, the error message is sent back to Claude
   for self-correction. Maximum 1 retry to prevent infinite loops.

5. **Structured output**: Every result is a consistent JSON-compatible dict,
   making it easy to evaluate and compare results.

6. **Full logging**: Every query attempt (success or failure) is logged
   with timestamp, SQL used, result rows, and error messages.
