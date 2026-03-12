@echo off
title IRCTC Tatkal Booker - Setup
color 0A

echo ============================================================
echo     IRCTC TATKAL FAST BOOKER - ONE-TIME SETUP
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.9+ from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [OK] Python found.
echo.

:: Upgrade pip
echo [1/3] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install requirements
echo [2/3] Installing dependencies (this may take 2-3 minutes)...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo [WARN] Some packages may have failed. Trying individually...
    python -m pip install selenium --quiet
    python -m pip install undetected-chromedriver --quiet
    python -m pip install ddddocr --quiet
    python -m pip install Pillow --quiet
    python -m pip install ntplib --quiet
)

echo.
echo [3/3] Verifying installation...
python -c "import selenium; import undetected_chromedriver; import ddddocr; import PIL; import ntplib; print('[OK] All packages installed successfully!')"
if %errorlevel% neq 0 (
    echo [WARN] Some packages could not be verified. Check errors above.
) else (
    echo.
    echo ============================================================
    echo     SETUP COMPLETE!
    echo ============================================================
    echo.
    echo  Next steps:
    echo    1. Edit config.json with your IRCTC details
    echo    2. Run:  python main.py
    echo.
    echo  Or double-click "run_booking.bat" to start!
    echo ============================================================
)

echo.
pause
