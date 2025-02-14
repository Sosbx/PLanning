# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Chemin vers le dossier du projet (à adapter selon l'environnement)
project_path = os.path.abspath(os.path.dirname(__file__))

# Liste des icônes spécifiques
icon_files = [
    ('icons/comparaison.png', 'icons'),
    ('icons/desiderata.png', 'icons'),
    ('icons/doctor_planning.png', 'icons'),
    ('icons/export.png', 'icons'),
    ('icons/personnel.png', 'icons'),
    ('icons/planning.png', 'icons'),
    ('icons/statistics.png', 'icons'),
]

# Ajout du splash screen
splash_file = ('icons/logo_SOSplanning.png', 'icons')

# Collecter tous les fichiers .pyd (modules Cython compilés pour Windows)
binaries = []
for root, dirs, files in os.walk(project_path):
    for file in files:
        if file.endswith('.pyd'):
            source = os.path.join(root, file)
            dest = os.path.relpath(root, project_path)
            binaries.append((source, dest))

a = Analysis(
    ['main.py'],
    pathex=[project_path],
    binaries=binaries,
    datas=icon_files + [splash_file],
    hiddenimports=[
        'numpy',
        'pandas',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
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
    name='Planificateur SOS Médecins',
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
    icon=os.path.join(project_path, 'icons', 'logo_SOSplanning.png'),
)
