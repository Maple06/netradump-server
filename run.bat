@echo off
echo ================================
echo     Starting Flask Server & Steer
echo ================================
echo.

start "Flask" python app.py
timeout /t 1 >nul
start "Steer" python Steer.py

pause