@echo off
echo מפעיל את שרת ה-Frontend של מערכת תכנון הפרישה...
echo.

cd frontend\public
python -m http.server 8001

echo.
echo לחץ על כל מקש לסגירה...
pause > nul
