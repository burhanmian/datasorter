@echo off
:: ============================================================
::  DICOM Organizer — Build Windows Setup EXE
::  Run this once on a Windows machine with Python installed.
::  Output: dist\DICOM_Organizer_Setup.exe
::
::  How the setup EXE works:
::    1. User places DICOM_Organizer_Setup.exe in any folder.
::    2. Double-click — installer GUI opens.
::    3. Default install path = same folder as the EXE (everything
::       stays together in one place).
::    4. Installer creates a venv, installs packages, then launches
::       DICOM Organizer which asks where to sort DICOM files.
:: ============================================================
setlocal

echo.
echo  ====================================================
echo   DICOM Organizer — Building Setup EXE
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

:: Clean previous artefacts
if exist build rmdir /s /q build
if exist "dist\DICOM_Organizer_Setup.exe" del /f "dist\DICOM_Organizer_Setup.exe"

echo  [2/3] Building DICOM_Organizer_Setup.exe...
echo.

python -m PyInstaller DICOM_Organizer_Setup.spec --noconfirm --clean

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
    echo   They place it in any folder and double-click.
    echo   Everything installs in that same folder.
    echo  ====================================================
) else (
    echo  ERROR: Expected output file not found.
)
echo.
pause
