@echo off
:: ============================================================
::  DICOM Organizer — Build Windows Installer
::  Run this once on a Windows machine with Python installed.
::  Output: dist\DICOM_Organizer_Setup.exe  (~15 MB)
:: ============================================================
setlocal

echo.
echo  ====================================================
echo   DICOM Organizer — Building Windows Installer
echo  ====================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.9+ and add it to PATH.
    pause
    exit /b 1
)

:: Install / upgrade PyInstaller
echo  [1/3] Installing PyInstaller...
python -m pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo  ERROR: Could not install PyInstaller.
    pause
    exit /b 1
)

echo  [2/3] Building DICOM_Organizer_Setup.exe...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "DICOM_Organizer_Setup" ^
    --add-data "gui;gui" ^
    --add-data "core;core" ^
    --add-data "utils;utils" ^
    --add-data "models;models" ^
    --add-data "main.py;." ^
    --add-data "download_model.py;." ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "tkinter.filedialog" ^
    --hidden-import "tkinter.messagebox" ^
    installer_gui.py

if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo  [3/3] Done!
echo.
if exist "dist\DICOM_Organizer_Setup.exe" (
    echo  ====================================================
    echo   SUCCESS!
    echo   Installer: dist\DICOM_Organizer_Setup.exe
    echo.
    echo   Distribute this single file to users.
    echo   Double-click to install DICOM Organizer.
    echo  ====================================================
) else (
    echo  ERROR: Expected output file not found.
)
echo.
pause
