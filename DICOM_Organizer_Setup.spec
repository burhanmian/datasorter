# -*- mode: python ; coding: utf-8 -*-
# DICOM Organizer — Setup EXE spec (single-file installer).
# Build with:  python -m PyInstaller DICOM_Organizer_Setup.spec --noconfirm
# Output:      dist/DICOM_Organizer_Setup.exe
#
# How it works:
#   1. User places DICOM_Organizer_Setup.exe in any folder they choose.
#   2. They double-click it — the installer GUI opens.
#   3. The default install path is the folder containing the EXE, so the app,
#      its virtual-env, and all data land right next to the installer.
#   4. After installation the installer launches DICOM_Organizer (main.py) which
#      presents the sorting wizard asking for source / destination folders.

import os

block_cipher = None

_ico = os.path.join('assets', 'icons', 'app_icon.ico')
_icon = [_ico] if os.path.isfile(_ico) else []

a = Analysis(
    ['installer_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Bundle the entire application source so the installer can copy it
        # into the install directory at runtime.
        ('gui',               'gui'),
        ('core',              'core'),
        ('utils',             'utils'),
        ('models',            'models'),
        ('assets',            'assets'),
        ('main.py',           '.'),
        ('download_model.py', '.'),
        ('requirements.txt',  '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DICOM_Organizer_Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
