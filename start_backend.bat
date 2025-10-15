@echo off
echo ========================================
echo Starting Backend Server on Port 8005
echo ========================================

REM Kill any existing Python processes on port 8005
echo Stopping existing servers on port 8005...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8005 ^| findstr LISTENING') do (
    echo Killing process %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Starting new server...
uvicorn app.main:app --reload --port 8005 --host 0.0.0.0

pause
