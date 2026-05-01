#!/bin/bash
# ============================================================
#  DICOM Organizer — Build Linux/macOS Setup binary
#  Run this once. Output: dist/DICOM_Organizer_Setup
#
#  How the setup binary works:
#    1. User places DICOM_Organizer_Setup in any folder.
#    2. Run it — installer GUI opens.
#    3. Default install path = same folder as the binary.
#    4. Installer creates a venv, installs packages, then launches
#       DICOM Organizer which asks where to sort DICOM files.
# ============================================================

set -e

echo ""
echo "  ===================================================="
echo "   DICOM Organizer — Building Setup binary"
echo "  ===================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: python3 not found. Install Python 3.9+ first."
    exit 1
fi

# Install PyInstaller
echo "  [1/3] Installing PyInstaller..."
python3 -m pip install pyinstaller --quiet --upgrade

# Clean previous artefacts
rm -rf build
rm -f dist/DICOM_Organizer_Setup

echo "  [2/3] Building DICOM_Organizer_Setup..."
echo ""

python3 -m PyInstaller DICOM_Organizer_Setup.spec --noconfirm --clean

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
    echo "   They place it in any folder and run it."
    echo "   Everything installs in that same folder."
    echo "  ===================================================="
else
    echo "  ERROR: Expected output file not found."
    exit 1
fi
