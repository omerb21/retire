@echo off
echo מפעיל את מערכת תכנון הפרישה...
echo.

REM הפעלת הסביבה הוירטואלית
call venv\Scripts\activate

REM הפעלת השרת הראשי
echo השרת עולה...
echo האפליקציה תהיה זמינה בכתובת: http://localhost:8005
echo תיעוד ה-API זמין בכתובת: http://localhost:8005/docs
echo.
echo לחץ Ctrl+C לעצירת השרת.
echo.

python simple_server.py
