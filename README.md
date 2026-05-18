# Task 3: Text-to-SQL Pipeline

## Overview

This project implements a Text-to-SQL pipeline using FastAPI and PostgreSQL.
The system:
- Decomposes natural language queries into structured SQL components
- Uses a local rule-based SQL generator for the classicmodels schema
- Validates generated SQL for safety
- Executes SQL against PostgreSQL
- Retries once if execution fails using local SQL repair logic
- Logs every query execution in `logs/query_logs.json`

## Files

- `database.py` — PostgreSQL connection helper
- `sql_generator.py` — Local rule-based SQL generator for the classicmodels schema
- `validator.py` — Safety checks blocking non-SELECT statements
- `executor.py` — Executes SQL, handles retry/fix, and logs results
- `main.py` — CLI runner for single questions and benchmark mode
- `fastapi_app.py` — FastAPI service for HTTP query execution
- `streamlit_app.py` — Optional Streamlit UI for chat-like usage
- `evaluate.py` — Benchmark evaluation script
- `prompts/templates.py` — Schema reference and prompt templates (optional for local generation)
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

3. Set your database connection in `.env`.
4. Test the database connection:

```bash
python database.py
```

## Run locally

### 🌐 FastAPI Web Interface (Recommended)

Start the FastAPI server with the built-in web interface:

```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

Then visit **http://localhost:8000** in your browser.

**Features:**
- 🏠 **Home Page** - Submit natural language questions and get instant SQL + results
- 📊 **Benchmark Results** - View all 50 benchmark questions with success/failure metrics
- 🧩 **Query Decomposition** - See how the system breaks down your question into SQL components
- 📈 **Live Dashboard** - Real-time success rate and execution statistics
- 💾 **Query History** - All executed queries logged and viewable

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
