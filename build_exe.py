#!/usr/bin/env python
# -*- coding: utf-8 -*-
# © 2024 HILAL Arkane. Tous droits réservés.

"""
Script d'automatisation pour la création d'un exécutable protégé par Cython.
Ce script:
1. Vérifie et installe les dépendances nécessaires
2. Compile les modules Python en C avec Cython
3. Applique une obfuscation supplémentaire avec pyarmor
4. Crée un exécutable autonome avec PyInstaller
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path
import importlib.util

# Couleurs pour les messages dans le terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(message):
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")

def print_step(message):
    print(f"{Colors.BLUE}{Colors.BOLD}[ÉTAPE] {message}{Colors.ENDC}")

def print_success(message):
    print(f"{Colors.GREEN}{Colors.BOLD}[SUCCÈS] {message}{Colors.ENDC}")

def print_warning(message):
    print(f"{Colors.WARNING}{Colors.BOLD}[ATTENTION] {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.FAIL}{Colors.BOLD}[ERREUR] {message}{Colors.ENDC}")

def check_dependencies():
    """Vérifie et installe les dépendances nécessaires."""
    print_step("Vérification des dépendances...")
    
    required_packages = ['cython', 'pyinstaller', 'pyarmor']
    missing_packages = []
    
    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(package)
    
    if missing_packages:
        print_warning(f"Packages manquants: {', '.join(missing_packages)}")
        print_step("Installation des packages manquants...")
        
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print_success("Packages installés avec succès")
        except subprocess.CalledProcessError as e:
            print_error(f"Erreur lors de l'installation des packages: {e}")
            sys.exit(1)
    else:
        print_success("Toutes les dépendances sont installées")

def check_build_tools():
    """Vérifie si les outils de compilation C sont installés."""
    print_step("Vérification des outils de compilation C...")
    
    if platform.system() == 'Windows':
        # Chemins communs d'installation de Visual C++ Build Tools
        common_paths = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC",
        ]
        
        # Vérifier si cl.exe (MSVC) est disponible dans le PATH
        try:
            result = subprocess.run(['cl'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print_success("Microsoft Visual C++ Build Tools est installé et dans le PATH")
            return True
        except FileNotFoundError:
            # Vérifier si cl.exe existe dans les chemins communs
            cl_found = False
            for base_path in common_paths:
                if os.path.exists(base_path):
                    # Chercher cl.exe dans les sous-dossiers
                    for root, dirs, files in os.walk(base_path):
                        if "cl.exe" in files:
                            cl_path = os.path.join(root, "cl.exe")
                            print_success(f"Microsoft Visual C++ Build Tools trouvé à: {cl_path}")
                            print_warning("Les outils ne sont pas dans le PATH, mais seront utilisés par Python")
                            cl_found = True
                            break
                    if cl_found:
                        break
            
            if cl_found:
                return True
            else:
                print_warning("Microsoft Visual C++ Build Tools n'est pas installé ou n'est pas détectable")
                print_warning("Veuillez installer Microsoft Visual C++ Build Tools depuis:")
                print_warning("https://visualstudio.microsoft.com/visual-cpp-build-tools/")
                response = input("Voulez-vous continuer quand même? (y/n): ")
                if response.lower() != 'y':
                    sys.exit(1)
                return False
    else:
        # Vérifier si gcc est disponible sur Linux/Mac
        try:
            result = subprocess.run(['gcc', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print_success("GCC est installé")
            return True
        except FileNotFoundError:
            print_warning("GCC n'est pas installé ou n'est pas dans le PATH")
            print_warning("Veuillez installer GCC via votre gestionnaire de paquets")
            response = input("Voulez-vous continuer quand même? (y/n): ")
            if response.lower() != 'y':
                sys.exit(1)
            return False

def compile_with_cython():
    """Compile les modules Python en C avec Cython."""
    print_step("Compilation avec Cython...")
    
    # Nettoyer les fichiers de build précédents
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    # Exécuter la compilation
    try:
        subprocess.check_call([sys.executable, 'setup.py', 'build_ext', '--inplace'])
        print_success("Compilation Cython terminée avec succès")
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur lors de la compilation Cython: {e}")
        sys.exit(1)

def obfuscate_with_pyarmor():
    """Applique une obfuscation supplémentaire avec pyarmor."""
    print_step("Obfuscation avec pyarmor...")
    
    # Créer un dossier pour les fichiers obfusqués
    obfuscated_dir = 'obfuscated'
    if os.path.exists(obfuscated_dir):
        shutil.rmtree(obfuscated_dir)
    os.makedirs(obfuscated_dir)
    
    # Obfusquer les fichiers Python restants (non compilés avec Cython)
    try:
        # Obfusquer main.py
        subprocess.check_call([
            'pyarmor', 'obfuscate', 
            '--output', obfuscated_dir,
            'main.py'
        ])
        
        # Copier les fichiers .so/.pyd (compilés par Cython) dans le dossier obfuscated
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.so') or file.endswith('.pyd'):
                    src_path = os.path.join(root, file)
                    # Créer le dossier de destination s'il n'existe pas
                    dest_dir = os.path.join(obfuscated_dir, os.path.dirname(src_path))
                    os.makedirs(dest_dir, exist_ok=True)
                    # Copier le fichier
                    dest_path = os.path.join(obfuscated_dir, src_path)
                    shutil.copy2(src_path, dest_path)
        
        # Copier les autres fichiers Python nécessaires
        for module in ['logger_config.py']:
            if os.path.exists(module):
                subprocess.check_call([
                    'pyarmor', 'obfuscate',
                    '--output', obfuscated_dir,
                    module
                ])
        
        # Copier les dossiers nécessaires (sauf Generator qui est déjà compilé)
        for folder in ['core', 'gui', 'utils', 'icons']:
            if os.path.exists(folder):
                # Exclure le dossier Generator qui est déjà compilé
                if folder == 'core':
                    for subfolder in os.listdir(folder):
                        if subfolder != 'Generator' and os.path.isdir(os.path.join(folder, subfolder)):
                            subprocess.check_call([
                                'pyarmor', 'obfuscate',
                                '--output', os.path.join(obfuscated_dir, folder),
                                '--recursive',
                                os.path.join(folder, subfolder)
                            ])
                else:
                    subprocess.check_call([
                        'pyarmor', 'obfuscate',
                        '--output', os.path.join(obfuscated_dir, folder),
                        '--recursive',
                        folder
                    ])
        
        print_success("Obfuscation terminée avec succès")
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur lors de l'obfuscation: {e}")
        sys.exit(1)

def create_executable():
    """Crée un exécutable autonome avec PyInstaller."""
    print_step("Création de l'exécutable avec PyInstaller...")
    
    # Dossier contenant les fichiers obfusqués
    obfuscated_dir = 'obfuscated'
    
    # Vérifier que le dossier existe
    if not os.path.exists(obfuscated_dir):
        print_error(f"Le dossier {obfuscated_dir} n'existe pas")
        sys.exit(1)
    
    # Créer le fichier spec pour PyInstaller
    spec_content = f"""
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    [os.path.join('{obfuscated_dir}', 'main.py')],
    pathex=['{obfuscated_dir}'],
    binaries=[],
    datas=[
        ('{obfuscated_dir}/icons', 'icons'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
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
    name='Planning4',
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
    icon='{obfuscated_dir}/icons/logo_SOSplanning.png' if os.path.exists('{obfuscated_dir}/icons/logo_SOSplanning.png') else None,
)
"""
    
    # Écrire le fichier spec
    with open('Planning4.spec', 'w') as f:
        f.write(spec_content)
    
    # Exécuter PyInstaller
    try:
        subprocess.check_call(['pyinstaller', 'Planning4.spec', '--clean'])
        print_success("Exécutable créé avec succès")
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur lors de la création de l'exécutable: {e}")
        sys.exit(1)

def main():
    """Fonction principale."""
    print_header("CRÉATION D'UN EXÉCUTABLE PROTÉGÉ PAR CYTHON")
    
    # Vérifier les dépendances
    check_dependencies()
    
    # Vérifier les outils de compilation
    check_build_tools()
    
    # Compiler avec Cython
    compile_with_cython()
    
    # Obfusquer avec pyarmor
    obfuscate_with_pyarmor()
    
    # Créer l'exécutable
    create_executable()
    
    print_header("PROCESSUS TERMINÉ AVEC SUCCÈS")
    print_success("L'exécutable se trouve dans le dossier 'dist'")

if __name__ == "__main__":
    main()
