@echo off
echo Nettoyage des fichiers de compilation precedents...
rmdir /s /q build
rmdir /s /q dist
del /s /q *.c
del /s /q *.pyd

echo Installation des dependances...
python -m pip install --upgrade pip
pip install cython pyinstaller pyqt5 numpy pandas

echo Compilation des modules avec Cython...
python setup.py build_ext --inplace

echo Creation de l'executable avec PyInstaller...
pyinstaller main.spec --clean --noconfirm

echo Build termine!
echo L'executable se trouve dans le dossier dist/
pause
