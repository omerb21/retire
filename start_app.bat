@echo off
echo מפעיל את מערכת תכנון הפרישה...
echo.

REM הפעלת הסביבה הוירטואלית
call venv\Scripts\activate

REM הפעלת האפליקציה המינימלית
echo האפליקציה תהיה זמינה בכתובת: http://localhost:8000
echo תיעוד ה-API זמין בכתובת: http://localhost:8000/docs
echo.
echo לחץ Ctrl+C לעצירת האפליקציה.
echo.

uvicorn minimal_app:app --host 0.0.0.0 --port 8000
