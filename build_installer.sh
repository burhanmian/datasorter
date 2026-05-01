#!/bin/bash
# ============================================================
#  DICOM Organizer — Build Linux/macOS Installer
#  Run this once. Output: dist/DICOM_Organizer_Setup (~20 MB)
# ============================================================

set -e

echo ""
echo "  ===================================================="
echo "   DICOM Organizer — Building Installer"
echo "  ===================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: python3 not found. Install Python 3.9+ first."
    exit 1
fi

# Install PyInstaller
echo "  [1/3] Installing PyInstaller..."
pip3 install pyinstaller --quiet --upgrade

echo "  [2/3] Building DICOM_Organizer_Setup..."
echo ""

pyinstaller \
    --onefile \
    --windowed \
    --name "DICOM_Organizer_Setup" \
    --add-data "gui:gui" \
    --add-data "core:core" \
    --add-data "utils:utils" \
    --add-data "models:models" \
    --add-data "main.py:." \
    --add-data "download_model.py:." \
    --hidden-import "tkinter" \
    --hidden-import "tkinter.ttk" \
    --hidden-import "tkinter.filedialog" \
    --hidden-import "tkinter.messagebox" \
    installer_gui.py

echo ""
echo "  [3/3] Done!"
echo ""

if [ -f "dist/DICOM_Organizer_Setup" ]; then
    chmod +x "dist/DICOM_Organizer_Setup"
    echo "  ===================================================="
    echo "   SUCCESS!"
    echo "   Installer: dist/DICOM_Organizer_Setup"
    echo ""
    echo "   Distribute this single file to users."
    echo "   Run it to install DICOM Organizer."
    echo "  ===================================================="
else
    echo "  ERROR: Expected output file not found."
    exit 1
fi
