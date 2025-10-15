@echo off
echo ========================================
echo Starting Frontend Server on Port 3000
echo ========================================

REM Kill any existing Node processes on port 3000
echo Stopping existing servers on port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo Killing process %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Starting new server...
npm run dev

pause
