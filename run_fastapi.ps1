# FastAPI Server Startup Script for PowerShell

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Text-to-SQL Pipeline - FastAPI Server" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
Set-Location $PSScriptRoot\..
& .\.venv\Scripts\Activate.ps1
Set-Location $PSScriptRoot

# Check if requirements are installed
Write-Host "Checking dependencies..." -ForegroundColor Green
pip show fastapi > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Check if PostgreSQL is running
Write-Host "Checking PostgreSQL connection..." -ForegroundColor Green
$env:DATABASE_URL = 'postgresql://postgres:example@localhost:5432/classicmodels'

python -c "
from database import test_connection
test_connection()
" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ PostgreSQL is running and accessible" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: Could not connect to PostgreSQL" -ForegroundColor Yellow
    Write-Host "  Make sure PostgreSQL service is running" -ForegroundColor Yellow
}

# Start FastAPI server
Write-Host ""
Write-Host "Starting FastAPI server..." -ForegroundColor Cyan
Write-Host "🌐 Open your browser: http://localhost:8000" -ForegroundColor Green
Write-Host "📊 Benchmark Results: http://localhost:8000/benchmark" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload

Read-Host "Press Enter to exit"
