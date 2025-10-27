@echo off
REM Restart server with clean cache
echo ========================================
echo Restarting Server with Clean Cache
echo ========================================
echo.

REM Kill all Python processes on port 8005
echo Stopping all servers on port 8005...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8005') do (
    taskkill /PID %%a /F 2>nul
)

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Clear Python cache
echo.
echo Clearing Python cache...
python clear_cache.py

REM Wait a moment
timeout /t 1 /nobreak >nul

REM Start server
echo.
echo Starting server...
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8005

pause
