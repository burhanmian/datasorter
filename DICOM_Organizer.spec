# -*- mode: python ; coding: utf-8 -*-
# DICOM Organizer — PyInstaller spec for a one-folder portable build.
# Build with:  python -m PyInstaller DICOM_Organizer.spec --noconfirm
# Output:      dist/DICOM_Organizer/DICOM_Organizer.exe  (portable folder)

import os

block_cipher = None

# Paths are relative to the spec file location (repo root)
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        (os.path.join('assets', 'icons', 'app_icon.ico'), os.path.join('assets', 'icons')),
        (os.path.join('assets'), 'assets'),
        (os.path.join('models'), 'models'),
        ('requirements.txt', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'pydicom',
        'pandas',
        'numpy',
        'PIL',
        'matplotlib',
        'sklearn',
        'scipy',
        'tqdm',
        'tkinterdnd2',
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
    [],
    exclude_binaries=True,
    name='DICOM_Organizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'icons', 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DICOM_Organizer',
)
