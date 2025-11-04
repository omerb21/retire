@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo 🛡️  SAFE SERVER START - Killing existing processes first
echo ============================================================
echo.


REM Kill all Python processes
echo 🔍 Killing any existing Python processes...
taskkill /F /IM python.exe >nul 2>&1
if errorlevel 1 (
    echo ⚠️  No Python processes found (or already killed)
) else (
    echo ✅ Python processes killed
)

REM Wait for processes to die
echo ⏳ Waiting 3 seconds for cleanup...
timeout /t 3 /nobreak

REM Activate virtual environment
echo.
echo 📦 Activating virtual environment...
call venv\Scripts\activate

REM Start the server with safe startup script
echo.
echo ============================================================
echo 🚀 Starting server on port 8005...
echo ============================================================
echo.
echo 📍 API Documentation: http://localhost:8005/docs
echo 📍 Health Check: http://localhost:8005/health
echo.
echo ⏹️  Press Ctrl+C to stop the server
echo.
echo הפעלת שרת ה-Frontend...
start cmd /k "start_frontend.bat"

python scripts\safe_server_start.py

