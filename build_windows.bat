@echo off
echo Nettoyage des fichiers de compilation precedents...
rmdir /s /q build
rmdir /s /q dist
del /s /q *.c
del /s /q *.pyd
del /s /q *.pyc

echo Installation des dependances...
python -m pip install --upgrade pip
pip install cython pyinstaller pyqt5 numpy pandas

echo Compilation des modules avec Cython...
python setup.py build_ext --inplace

echo Creation du fichier spec personnalise...
echo # -*- mode: python -*- > encrypted_entry.spec
echo from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT >> encrypted_entry.spec
echo block_cipher = None >> encrypted_entry.spec
echo a = Analysis(['encrypted_entry.py'], >> encrypted_entry.spec
echo             pathex=['%CD%'], >> encrypted_entry.spec
echo             binaries=[], >> encrypted_entry.spec
echo             datas=[('icons/*.png', 'icons')], >> encrypted_entry.spec
echo             hiddenimports=[], >> encrypted_entry.spec
echo             hookspath=[], >> encrypted_entry.spec
echo             runtime_hooks=[], >> encrypted_entry.spec
echo             excludes=[], >> encrypted_entry.spec
echo             win_no_prefer_redirects=False, >> encrypted_entry.spec
echo             win_private_assemblies=False, >> encrypted_entry.spec
echo             cipher=block_cipher, >> encrypted_entry.spec
echo             noarchive=False) >> encrypted_entry.spec
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher) >> encrypted_entry.spec
echo exe = EXE(pyz, >> encrypted_entry.spec
echo           a.scripts, >> encrypted_entry.spec
echo           a.binaries, >> encrypted_entry.spec
echo           a.zipfiles, >> encrypted_entry.spec
echo           a.datas, >> encrypted_entry.spec
echo           [], >> encrypted_entry.spec
echo           name='planningSosRD', >> encrypted_entry.spec
echo           debug=False, >> encrypted_entry.spec
echo           bootloader_ignore_signals=False, >> encrypted_entry.spec
echo           strip=False, >> encrypted_entry.spec
echo           upx=True, >> encrypted_entry.spec
echo           upx_exclude=[], >> encrypted_entry.spec
echo           runtime_tmpdir=None, >> encrypted_entry.spec
echo           console=False, >> encrypted_entry.spec
echo           disable_windowed_traceback=True, >> encrypted_entry.spec
echo           target_arch=None, >> encrypted_entry.spec
echo           codesign_identity=None, >> encrypted_entry.spec
echo           entitlements_file=None) >> encrypted_entry.spec

echo Creation de l'executable avec PyInstaller...
pyinstaller --clean --noconfirm ^
    --key=%random%%random%%random%%random% ^
    --noconsole ^
    --uac-admin ^
    --runtime-tmpdir="." ^
    encrypted_entry.spec

echo Nettoyage des fichiers intermediaires...
del /s /q *.c
del /s /q *.pyd
del /s /q *.pyc
del /s /q *.spec

echo Build termine!
echo L'executable se trouve dans le dossier dist/
pause
