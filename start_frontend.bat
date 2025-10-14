@echo off
setlocal

echo מפעיל את שרת ה-Frontend של מערכת תכנון הפרישה...
echo.

REM בדיקה אם פורט 3000 תפוס ושחרורו
netstat -ano | findstr :3000 > nul
if %errorlevel% equ 0 (
    echo פורט 3000 תפוס, משחרר אותו...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
        taskkill /f /pid %%a
    )
    timeout /t 2 /nobreak > nul
)

cd frontend
echo מפעיל את שרת ה-Vite על פורט 3000...
echo הפרונטאנד יהיה זמין בכתובת: http://localhost:3000
echo.
echo לחץ Ctrl+C לעצירת השרת.
echo.

npm run dev
