@echo off
setlocal

echo מפעיל את מערכת תכנון הפרישה...
echo.

REM בדיקה אם venv קיים ופעיל
if exist "venv\Scripts\activate.bat" (
    echo הפעלת הסביבה הוירטואלית...
    call venv\Scripts\activate
) else (
    echo ממשיך ללא venv...
)

REM הפעלת השרת הראשי
echo השרת עולה...
echo האפליקציה תהיה זמינה בכתובת: http://localhost:8005
echo תיעוד ה-API זמין בכתובת: http://localhost:8005/docs
echo.
echo לחץ Ctrl+C לעצירת השרת.
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

python -m uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
