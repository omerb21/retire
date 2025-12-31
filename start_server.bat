@echo off
title Retire - Start Servers (venv311)

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%venv311\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Error: venv311 not found at: %PYTHON_EXE%
  echo Create it with: py -3.11 -m venv venv311
  pause
  exit /b 1
)

"%PYTHON_EXE%" -m pip show uvicorn >nul 2>&1
if errorlevel 1 (
  echo Error: uvicorn is not installed in venv311.
  echo Install dependencies with:
  echo   "%PYTHON_EXE%" -m pip install -r requirements.txt
  pause
  exit /b 1
)
@echo off
title הפעלת שרתי המערכת

:: עצירת שרתים קיימים
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
start "Backend Server" /D "%PROJECT_ROOT%" "%PYTHON_EXE%" -m uvicorn app.main:app --reload --port 8005

timeout /t 3 >nul

if exist "%PROJECT_ROOT%frontend\package.json" (
  start "Frontend Server" /D "%PROJECT_ROOT%frontend" npm run dev
) else (
  echo Frontend folder not found, skipping frontend start.
)

echo.
echo Servers started.
echo - Backend: http://localhost:8005
echo - Frontend: http://localhost:3000
echo.
pause