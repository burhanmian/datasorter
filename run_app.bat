@echo off
title DICOM Organizer
color 0A

echo ============================================
echo   DICOM Organizer — Starting up...
echo ============================================
echo.

:: Check Python is installed
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Show Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Found: %PYVER%

:: Check if requirements need installing
python -c "import customtkinter" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [INFO] Installing required packages (first-time setup)...
    echo This may take a few minutes — please wait.
    echo.
    python -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Package installation failed.
        echo Please run this command manually:
        echo   pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo [OK] Packages installed successfully.
)

:: Check / download AI model on first run
python -c "import os; exit(0 if os.path.exists('models/body_part_classifier.pth') else 1)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [INFO] Downloading AI body part detection model...
    python download_model.py
)

echo.
echo [OK] Launching DICOM Organizer...
echo.

:: Launch the app
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with an error.
    echo Please check the log files in your destination folder.
    echo.
    pause
)
