@echo off
title IRCTC Tatkal Booking
color 0E
cd /d "%~dp0"

echo ============================================================
echo     IRCTC TATKAL FAST BOOKER - Starting...
echo ============================================================
echo.
echo  [TIP] Use "python main.py --now" for instant booking
echo        (skips tatkal countdown timer)
echo.
echo ============================================================
echo.

python main.py

echo.
pause
