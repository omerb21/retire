@echo off
echo ========================================
echo Checking for running servers
echo ========================================

echo.
echo Backend (Port 8005):
echo --------------------
netstat -ano | findstr :8005 | findstr LISTENING
if %errorlevel% equ 0 (
    echo WARNING: Backend server(s) found running!
) else (
    echo OK: No backend servers running
)

echo.
echo Frontend (Port 3000):
echo --------------------
netstat -ano | findstr :3000 | findstr LISTENING
if %errorlevel% equ 0 (
    echo WARNING: Frontend server(s) found running!
) else (
    echo OK: No frontend servers running
)

echo.
echo ========================================
echo Done
echo ========================================
pause
