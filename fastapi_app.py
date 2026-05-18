from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import json
import os
from pathlib import Path
from sql_generator import generate_sql
from executor import execute_query

# Setup directories
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Create directories if they don't exist
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Text-to-SQL Pipeline",
    description="Prompt-chaining Text-to-SQL service with PostgreSQL execution and retry logic.",
    version="1.0.0",
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Disable template cache to avoid Jinja2 cache key issues on some environments
try:
    templates.env.cache = {}
except Exception:
    pass

class QueryRequest(BaseModel):
    question: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    tpl = templates.env.get_template("index.html")
    content = tpl.render(request=request)
    return HTMLResponse(content)

@app.get("/benchmark", response_class=HTMLResponse)
async def benchmark_page(request: Request):
    try:
        with open(BASE_DIR / "logs" / "evaluation_report.txt", "r") as f:
            report = f.read()
    except:
        report = "Benchmark report not available yet. Run `python main.py --benchmark` to generate it."

    tpl = templates.env.get_template("benchmark.html")
    content = tpl.render(request=request, report=report)
    return HTMLResponse(content)

@app.get("/api/benchmark", response_class=JSONResponse)
async def get_benchmark_data():
    try:
        with open(BASE_DIR / "logs" / "query_logs.json", "r") as f:
            logs = json.load(f)
        
        # Calculate summary metrics
        total = len(logs)
        successful = sum(1 for log in logs if log.get("status") == "success")
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0
        
        return {
            "total_questions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 1),
            "logs": logs
        }
    except FileNotFoundError:
        return {
            "error": "Benchmark data not found. Run `python main.py --benchmark` first.",
            "total_questions": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0,
            "logs": []
        }

@app.post("/api/query")
async def run_query(request: QueryRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    try:
        sql, decomposition = generate_sql(question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SQL generation failed: {exc}")

    result = execute_query(question, sql, decomposition)
    return result

@app.post("/query", response_class=HTMLResponse)
async def run_query_web(request: Request):
    form_data = await request.form()
    question = form_data.get("question", "").strip()
    
    if not question:
        tpl = templates.env.get_template("index.html")
        content = tpl.render(request=request, error="Question must not be empty.")
        return HTMLResponse(content)

    try:
        sql, decomposition = generate_sql(question)
        result = execute_query(question, sql, decomposition)
        
        tpl = templates.env.get_template("results.html")
        content = tpl.render(
            request=request,
            question=question,
            sql=result.get("sql", ""),
            status=result.get("status", ""),
            rows=result.get("result", []),
            row_count=result.get("row_count", 0),
            error=result.get("error", ""),
            decomposition=decomposition,
        )
        return HTMLResponse(content)
    except Exception as exc:
        tpl = templates.env.get_template("index.html")
        content = tpl.render(request=request, error=f"Error: {str(exc)}")
        return HTMLResponse(content)
