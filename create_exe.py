#!/usr/bin/env python
# -*- coding: utf-8 -*-
# © 2024 HILAL Arkane. Tous droits réservés.

"""
Script pour créer un exécutable à partir des fichiers compilés avec Cython.
Ce script:
1. Vérifie que les fichiers C existent
2. Applique une obfuscation supplémentaire avec pyarmor
3. Crée un exécutable autonome avec PyInstaller
"""

import os
import sys
import subprocess
import shutil
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
    
    required_packages = ['pyinstaller', 'pyarmor']
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

def check_c_files():
    """Vérifie que les fichiers C existent."""
    print_step("Vérification des fichiers C...")
    
    c_files = [
        'core/Generator/Optimizer/backtracking.c',
        'core/Generator/Optimizer/distribution_optimizer.c',
        'core/Generator/Optimizer/PlanningOptimizer.c',
        'core/Generator/Optimizer/weekend_optimizer.c',
        'core/Generator/Weekday/weekday_gen.c',
        'core/Generator/Weekend/planning_generator.c',
    ]
    
    missing_files = []
    for file_path in c_files:
        normalized_path = file_path.replace('/', os.path.sep)
        if not os.path.exists(normalized_path):
            missing_files.append(normalized_path)
    
    if missing_files:
        print_error(f"Fichiers C manquants: {', '.join(missing_files)}")
        print_error("Veuillez exécuter compile_cython.py d'abord")
        sys.exit(1)
    else:
        print_success("Tous les fichiers C sont présents")

def prepare_obfuscated_directory():
    """Prépare le dossier pour les fichiers obfusqués sans utiliser pyarmor."""
    print_step("Préparation du dossier obfuscated...")
    
    # Créer un dossier pour les fichiers obfusqués
    obfuscated_dir = 'obfuscated'
    if os.path.exists(obfuscated_dir):
        shutil.rmtree(obfuscated_dir)
    os.makedirs(obfuscated_dir)
    
    try:
        # Copier main.py
        shutil.copy2('main.py', os.path.join(obfuscated_dir, 'main.py'))
        print_success("main.py copié")
        
        # Copier les fichiers .c (compilés par Cython) dans le dossier obfuscated
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.c') and 'Generator' in root:
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
                shutil.copy2(module, os.path.join(obfuscated_dir, module))
        
        # Copier les dossiers nécessaires
        for folder in ['core', 'gui', 'utils', 'icons']:
            if os.path.exists(folder):
                # Pour le dossier core, exclure Generator qui est déjà copié via les fichiers .c
                if folder == 'core':
                    # Créer le dossier core
                    os.makedirs(os.path.join(obfuscated_dir, folder), exist_ok=True)
                    # Copier __init__.py
                    if os.path.exists(os.path.join(folder, '__init__.py')):
                        shutil.copy2(
                            os.path.join(folder, '__init__.py'),
                            os.path.join(obfuscated_dir, folder, '__init__.py')
                        )
                    # Copier les sous-dossiers sauf Generator
                    for subfolder in os.listdir(folder):
                        subfolder_path = os.path.join(folder, subfolder)
                        if subfolder != 'Generator' and os.path.isdir(subfolder_path):
                            shutil.copytree(
                                subfolder_path,
                                os.path.join(obfuscated_dir, folder, subfolder)
                            )
                else:
                    # Copier le dossier entier
                    shutil.copytree(
                        folder,
                        os.path.join(obfuscated_dir, folder)
                    )
        
        print_success("Préparation terminée avec succès")
        return True
    except Exception as e:
        print_error(f"Erreur lors de la préparation: {e}")
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
        # Utiliser le module Python directement
        subprocess.check_call([sys.executable, '-m', 'PyInstaller', 'Planning4.spec', '--clean'])
        print_success("Exécutable créé avec succès")
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur lors de la création de l'exécutable: {e}")
        sys.exit(1)

def main():
    """Fonction principale."""
    print_header("CRÉATION D'UN EXÉCUTABLE PROTÉGÉ")
    
    # Vérifier les dépendances
    check_dependencies()
    
    # Vérifier les fichiers C
    check_c_files()
    
    # Préparer le dossier obfuscated
    prepare_obfuscated_directory()
    
    # Créer l'exécutable
    create_executable()
    
    print_header("PROCESSUS TERMINÉ AVEC SUCCÈS")
    print_success("L'exécutable se trouve dans le dossier 'dist'")

if __name__ == "__main__":
    main()
