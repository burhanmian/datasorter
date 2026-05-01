@echo off
:: ============================================================
::  DICOM Organizer — Repeatable Windows build script
::  Creates a virtual environment, installs all dependencies,
::  and produces a portable one-folder build under dist\.
::
::  Usage:  build_windows.bat
::  Output: dist\DICOM_Organizer\DICOM_Organizer.exe
:: ============================================================
setlocal ENABLEDELAYEDEXPANSION
title DICOM Organizer — Windows Build

echo.
echo  ====================================================
echo   DICOM Organizer — Windows Build
echo  ====================================================
echo.

:: ── 1. Check Python ─────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found.
    echo  Install Python 3.10+ from https://www.python.org/downloads/
    echo  and make sure to tick "Add Python to PATH".
    pause
    exit /b 1
)
for /f "tokens=*" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo  Found: %PYVER%
echo.

:: ── 2. Create / reuse virtual environment ───────────────
set VENV_DIR=.venv
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo  [1/4] Creating virtual environment in %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo  [1/4] Reusing existing virtual environment in %VENV_DIR%
)

:: Activate the venv for subsequent commands
call "%VENV_DIR%\Scripts\activate.bat"

:: ── 3. Install / upgrade pip, then requirements ─────────
echo  [2/4] Installing requirements...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install requirements.
    pause
    exit /b 1
)

:: ── 4. Install PyInstaller inside the venv ──────────────
echo  [3/4] Installing PyInstaller...
python -m pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo  ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

:: ── 5. Clean previous artefacts ─────────────────────────
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

:: ── 6. Build portable one-folder distribution ───────────
echo  [4/4] Building portable one-folder dist...
echo.
python -m PyInstaller DICOM_Organizer.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo  ERROR: PyInstaller build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo  ====================================================
echo   SUCCESS!
echo   Portable folder: dist\DICOM_Organizer\
echo   Executable:      dist\DICOM_Organizer\DICOM_Organizer.exe
echo.
echo   Copy the entire dist\DICOM_Organizer\ folder to any
echo   Windows 10/11 machine and run DICOM_Organizer.exe.
echo   No Python installation required on the target machine.
echo  ====================================================
echo.
pause
