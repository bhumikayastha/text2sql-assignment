# FastAPI Web Interface Guide

## Quick Start

### 1. Start the FastAPI Server

**Using PowerShell (Recommended for Windows):**
```powershell
cd 'd:\AIF week3\task3_project'
& .\run_fastapi.ps1
```

**Or run directly:**
```powershell
$env:DATABASE_URL='postgresql://postgres:example@localhost:5432/classicmodels'
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

**Using Command Prompt (Batch file):**
```cmd
cd d:\AIF week3\task3_project
run_fastapi.bat
```

### 2. Open in Browser

Once the server is running, open your browser and navigate to:
- **Home Page:** http://localhost:8000
- **Benchmark Results:** http://localhost:8000/benchmark

## Features

### 🏠 Home Page (http://localhost:8000)

The home page provides:
- **Query Input Form** - Type your natural language question
- **Example Queries** - Quick reference of sample questions
- **Instant Execution** - Click "Generate & Execute SQL" to see results

**Example questions:**
- "Show all orders placed by customers in Germany"
- "What is the total revenue from payments?"
- "How many products are in each product line?"
- "List all customers with their total order amounts"
- "Show employees grouped by office"

### 📊 Results Page

After submitting a query, you'll see:

1. **Your Question** - The original question you asked
2. **Status Badge** - Shows SUCCESS, FAILED, or BLOCKED
3. **Generated SQL** - The actual SQL query that was generated and executed
4. **Query Decomposition** - Detailed breakdown showing:
   - **Intent** - What the system understood from your question
   - **Tables** - Which database tables are involved
   - **Columns** - Which columns are being selected
   - **Filters** - WHERE clause conditions
   - **Joins** - How tables are connected
5. **Query Results** - Data table with all results from the database

### 📈 Benchmark Results (http://localhost:8000/benchmark)

The benchmark page displays:

1. **Summary Metrics** (4 cards):
   - Total Questions - How many benchmark questions were run
   - Successful - Number of queries that executed successfully
   - Failed - Number of queries that failed
   - Success Rate - Percentage of successful queries

2. **Full Report** - Complete text report from `logs/evaluation_report.txt`

3. **Query Execution Log** - Detailed log of all executed queries showing:
   - Question text
   - Execution status (SUCCESS, FAILED)
   - Generated SQL
   - Row count and any errors

## API Endpoints

### REST API (for programmatic access)

**Health Check:**
```bash
GET http://localhost:8000/health
```

**Submit Query (JSON API):**
```bash
POST http://localhost:8000/api/query
Content-Type: application/json

{
  "question": "Show all orders placed by customers in Germany"
}
```

**Get Benchmark Data:**
```bash
GET http://localhost:8000/api/benchmark
```

**Submit Query (Web Form):**
```bash
POST http://localhost:8000/query
```

## Files and Structure

```
task3_project/
├── fastapi_app.py              # Main FastAPI application
├── run_fastapi.ps1             # PowerShell startup script
├── run_fastapi.bat             # Batch file startup script
├── templates/
│   ├── base.html              # Base layout template
│   ├── index.html             # Home page
│   ├── results.html           # Query results page
│   └── benchmark.html         # Benchmark results page
├── static/                    # CSS/JS assets (created automatically)
├── logs/
│   ├── query_logs.json        # All executed queries
│   └── evaluation_report.txt  # Benchmark summary report
└── database.py                # Database connection
```

## Troubleshooting

### Server won't start

**Problem:** `Address already in use`
- **Solution:** The port 8000 is already in use. Either:
  - Stop other FastAPI instances
  - Change the port: `uvicorn fastapi_app:app --port 8001`

### Database connection error

**Problem:** `could not translate host name "db" to address`
- **Solution:** Make sure `.env` has `DATABASE_URL=postgresql://postgres:example@localhost:5432/classicmodels`
- Check that PostgreSQL is running: `python database.py`

### No results returned

**Problem:** Query executes but returns 0 rows
- **Solution:** 
  - The query may be syntactically correct but semantically empty
  - Check the generated SQL and verify it matches your intent
  - Review the decomposition to see how the system interpreted your question

### Browser shows template not found error

**Problem:** `Template "index.html" not found`
- **Solution:** Make sure you're running from the `task3_project` directory
- Verify that the `templates/` folder exists with all .html files

## Performance Notes

- **First query** may take 1-2 seconds (database connection warming up)
- **Subsequent queries** execute in 200-500ms
- **Benchmark** with all 50 questions takes about 30-60 seconds depending on system

## Server Management

**Stop the server:** Press `Ctrl+C` in the terminal

**View server logs:** All requests are logged to the terminal output

**Background execution:** To run in background (Windows):
```powershell
Start-Process pwsh -ArgumentList "-NoExit -Command cd 'd:\AIF week3\task3_project'; & .\run_fastapi.ps1"
```

## Next Steps

1. ✅ Start the server using one of the startup scripts
2. ✅ Open http://localhost:8000 in your browser
3. ✅ Try submitting a natural language question
4. ✅ Review the generated SQL and results
5. ✅ Check benchmark results at http://localhost:8000/benchmark
6. ✅ Use the API endpoints for programmatic access

## Support

For issues or questions:
1. Check the PostgreSQL connection: `python database.py`
2. Review logs in `logs/query_logs.json`
3. Check the terminal output from the FastAPI server for error messages
