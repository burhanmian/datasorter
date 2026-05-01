@echo off
:: ============================================================
::  DICOM Organizer — Build Windows Installer
::  Double-click this file. Output: dist\DICOM_Organizer_Setup.exe
:: ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  ====================================================
echo   DICOM Organizer ^| Building Installer
echo  ====================================================
echo.

:: ── Find Python ───────────────────────────────────────────
set PYTHON=
for %%P in (python python3) do (
    if not defined PYTHON (
        %%P --version >nul 2>&1
        if not errorlevel 1 set PYTHON=%%P
    )
)

if not defined PYTHON (
    echo  ERROR: Python 3.9+ not found in PATH.
    echo  Install from https://python.org  and tick "Add Python to PATH".
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('!PYTHON! --version 2^>^&1') do echo  Found: %%V

:: ── Install PyInstaller ───────────────────────────────────
echo.
echo  [1/3] Installing PyInstaller...
%PYTHON% -m pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo  ERROR: pip install failed.
    pause
    exit /b 1
)
echo  PyInstaller ready.

:: ── Build ─────────────────────────────────────────────────
echo.
echo  [2/3] Building DICOM_Organizer_Setup.exe ...
echo         ^(this takes 1-3 minutes^)
echo.

%PYTHON% -m PyInstaller ^
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
    --hidden-import "winreg" ^
    --collect-all "customtkinter" ^
    --collect-all "tkinterdnd2" ^
    installer_gui.py

if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. See output above.
    pause
    exit /b 1
)

:: ── Done ──────────────────────────────────────────────────
echo.
echo  [3/3] Done!
echo.
if exist "dist\DICOM_Organizer_Setup.exe" (
    echo  ====================================================
    echo   SUCCESS^^!
    echo   dist\DICOM_Organizer_Setup.exe
    echo.
    echo   Send this one file to any Windows user.
    echo   They double-click it  -  done.
    echo  ====================================================
) else (
    echo  ERROR: Output file not found.
    exit /b 1
)
echo.
pause
