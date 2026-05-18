@echo off
REM FastAPI Server Startup Script for Windows

echo.
echo ============================================
echo   Text-to-SQL Pipeline - FastAPI Server
echo ============================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
cd /d "%~dp0.."
call .venv\Scripts\activate.bat

cd /d "%~dp0"

REM Check if requirements are installed
echo Checking dependencies...
pip show fastapi > nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Start FastAPI server
echo.
echo Starting FastAPI server on http://localhost:8000...
echo Press Ctrl+C to stop the server.
echo.

uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload

pause
