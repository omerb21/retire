@echo off
REM Start backend server FRESH without reload
REM This ensures the latest code is loaded

echo ========================================
echo Starting Backend Server on Port 8005
echo ========================================
echo.

REM Kill any existing processes on port 8005
echo Stopping existing servers on port 8005...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8005') do (
    taskkill /PID %%a /F 2>nul
)

echo.
echo Starting new server WITHOUT --reload...
echo (This ensures fresh code loading)
echo.

cd /d "%~dp0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8005

pause
