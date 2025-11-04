@echo off
title הפעלת שרתי המערכת

:: עצירת שרתים קיימים
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1

:: הפעלת שרת Backend
start "Backend Server" cmd /k "cd /d c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire && python -m uvicorn app.main:app --reload --port 8005"

:: המתנה קצרה להפעלת השרת
timeout /t 5 >nul

:: הפעלת שרת Frontend
start "Frontend Server" cmd /k "cd /d c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend && npm run dev"

echo.
echo ✅ השרתים הופעלו בהצלחה!
echo - Backend: http://localhost:8005
echo - Frontend: http://localhost:3000
echo.
pause