@echo off
setlocal

echo מפעיל את מערכת תכנון הפרישה המלאה...
echo.

REM בדיקה אם פורט 8005 תפוס ושחרורו
netstat -ano | findstr :8005 > nul
if %errorlevel% equ 0 (
    echo פורט 8005 תפוס, משחרר אותו...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8005') do (
        taskkill /f /pid %%a
    )
    timeout /t 2 /nobreak > nul
)

REM בדיקה אם פורט 8000 תפוס ושחרורו
netstat -ano | findstr :8000 > nul
if %errorlevel% equ 0 (
    echo פורט 8000 תפוס, משחרר אותו...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
        taskkill /f /pid %%a
    )
    timeout /t 2 /nobreak > nul
)

REM בדיקה אם פורט 3000 תפוס ושחרורו
netstat -ano | findstr :3000 > nul
if %errorlevel% equ 0 (
    echo פורט 3000 תפוס, משחרר אותו...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
        taskkill /f /pid %%a
    )
    timeout /t 2 /nobreak > nul
)

echo הפעלת שרת ה-Backend...
start cmd /k "start_app.bat"

echo הפעלת שרת ה-Frontend...
start cmd /k "start_frontend.bat"

echo.
echo המערכת הופעלה בהצלחה!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
