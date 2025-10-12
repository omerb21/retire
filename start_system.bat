@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo               מערכת תכנון פרישה - הפעלת המערכת
echo ================================================================
echo.

REM בדיקה אם venv קיים ופעיל
if exist "venv\Scripts\activate.bat" (
    echo הפעלת הסביבה הוירטואלית...
    call venv\Scripts\activate
) else (
    echo ממשיך ללא venv...
)

REM בדיקה אם פורט 8005 תפוס ושחרורו
echo בודק אם פורט 8005 תפוס...
netstat -ano | findstr :8005 > nul
if %errorlevel% equ 0 (
    echo פורט 8005 תפוס, משחרר אותו...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8005') do (
        echo מנסה לסגור תהליך %%a...
        taskkill /f /pid %%a >nul 2>&1
        if !errorlevel! equ 0 (
            echo תהליך %%a נסגר בהצלחה.
        ) else (
            echo לא ניתן לסגור תהליך %%a. ייתכן שתצטרך לסגור אותו ידנית.
        )
    )
    timeout /t 2 /nobreak > nul
)

REM בדיקה אם פורט 3000 תפוס ושחרורו
echo בודק אם פורט 3000 תפוס...
netstat -ano | findstr :3000 > nul
if %errorlevel% equ 0 (
    echo פורט 3000 תפוס, משחרר אותו...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
        echo מנסה לסגור תהליך %%a...
        taskkill /f /pid %%a >nul 2>&1
        if !errorlevel! equ 0 (
            echo תהליך %%a נסגר בהצלחה.
        ) else (
            echo לא ניתן לסגור תהליך %%a. ייתכן שתצטרך לסגור אותו ידנית.
        )
    )
    timeout /t 2 /nobreak > nul
)

echo.
echo ================================================================
echo                       הפעלת שרת ה-API
echo ================================================================
echo.

REM הפעלת השרת הראשי ברקע
echo מפעיל את שרת ה-API בפורט 8005...
start "API Server" cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload"

REM המתנה קצרה לוודא שהשרת עלה
echo ממתין לעליית השרת...
timeout /t 5 /nobreak > nul

REM בדיקה שהשרת עלה בהצלחה
echo בודק שהשרת פעיל...
curl -s http://localhost:8005/api/v1/health > nul
if %errorlevel% equ 0 (
    echo ✓ שרת ה-API פעיל בהצלחה!
) else (
    echo ! שגיאה: לא ניתן להתחבר לשרת ה-API. בודק שוב...
    timeout /t 5 /nobreak > nul
    curl -s http://localhost:8005/api/v1/health > nul
    if %errorlevel% equ 0 (
        echo ✓ שרת ה-API פעיל בהצלחה!
    ) else (
        echo ! שגיאה: לא ניתן להתחבר לשרת ה-API. נסה להפעיל את השרת ידנית.
    )
)

echo.
echo ================================================================
echo                     הפעלת ממשק המשתמש
echo ================================================================
echo.

REM עבור לתיקיית הפרונטאנד והפעל את השרת
echo מפעיל את ממשק המשתמש בפורט 3000...
cd frontend
start "Frontend Server" cmd /c "npm run dev"

REM המתנה קצרה לוודא שהפרונטאנד עלה
echo ממתין לעליית ממשק המשתמש...
timeout /t 5 /nobreak > nul

echo.
echo ================================================================
echo                       המערכת פעילה!
echo ================================================================
echo.
echo ממשק המשתמש זמין בכתובת: http://localhost:3000
echo Backend: http://localhost:8005
echo תיעוד ה-API זמין בכתובת: http://localhost:8005/docs
echo.
echo לסגירת המערכת, סגור את חלונות ה-CMD שנפתחו או לחץ Ctrl+C בכל אחד מהם.
echo.

REM חזרה לתיקייה הראשית
cd ..

REM פתיחת הדפדפן עם הממשק
echo פותח את ממשק המשתמש בדפדפן...
start http://localhost:3000

echo.
echo לחץ על מקש כלשהו לסגירת חלון זה...
pause > nul
