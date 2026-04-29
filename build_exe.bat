@echo off
title DICOM Organizer — Build Executable
echo ============================================
echo   Building DICOM Organizer standalone .exe
echo ============================================
echo.

:: Check PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)

:: Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist DICOM_Organizer.spec del DICOM_Organizer.spec

echo Building...
python -m PyInstaller ^
    --name "DICOM_Organizer" ^
    --onefile ^
    --windowed ^
    --icon assets\icons\app_icon.ico ^
    --add-data "requirements.txt;." ^
    --add-data "models;models" ^
    --add-data "assets;assets" ^
    --hidden-import customtkinter ^
    --hidden-import pydicom ^
    --hidden-import pandas ^
    --hidden-import numpy ^
    --hidden-import PIL ^
    --hidden-import matplotlib ^
    --hidden-import sklearn ^
    --hidden-import torch ^
    --hidden-import torchvision ^
    --hidden-import SimpleITK ^
    --hidden-import dicom2nifti ^
    --collect-all customtkinter ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   SUCCESS!
    echo   Executable: dist\DICOM_Organizer.exe
    echo ============================================
) else (
    echo.
    echo [ERROR] Build failed. Check output above.
)

pause
