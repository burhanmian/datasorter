@echo off
:: ============================================================
::  DICOM Organizer — Main Launcher
::  Double-click this file to install and start the application
:: ============================================================

:: Use PowerShell to launch bootstrapper.py without a console window.
:: PowerShell is built into every Windows 10/11 machine.

powershell -WindowStyle Hidden -ExecutionPolicy Bypass -Command ^
  "$dir = Split-Path -Parent '%~f0';" ^
  "$bs  = Join-Path $dir 'bootstrapper.py';" ^
  "if (-not (Test-Path $bs)) {" ^
  "  Add-Type -AN System.Windows.Forms;" ^
  "  [System.Windows.Forms.MessageBox]::Show(" ^
  "    'bootstrapper.py not found. Make sure all DICOM Organizer files are in the same folder as this .bat file.'," ^
  "    'DICOM Organizer','OK','Error');" ^
  "  exit 1 }" ^
  "try {" ^
  "  $py = (Get-Command python -ErrorAction Stop).Source;" ^
  "  $pw = Join-Path (Split-Path $py) 'pythonw.exe';" ^
  "  $exe = if (Test-Path $pw) { $pw } else { $py };" ^
  "  Start-Process -FilePath $exe -ArgumentList $bs -WindowStyle Hidden" ^
  "} catch {" ^
  "  Add-Type -AN System.Windows.Forms;" ^
  "  [System.Windows.Forms.MessageBox]::Show(" ^
  "    'Python 3.10 or newer is required.`n`nDownload from:  https://www.python.org/downloads/`n`nIMPORTANT: tick  ''Add Python to PATH''  during installation.'," ^
  "    'DICOM Organizer — Python Required','OK','Warning');" ^
  "  Start-Process 'https://www.python.org/downloads/';" ^
  "  exit 1 }"

:: If PowerShell itself failed (very old system), fall back to visible console
if %ERRORLEVEL% NEQ 0 (
    python --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo Python not found. Download from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    start "" python "%~dp0bootstrapper.py"
)
