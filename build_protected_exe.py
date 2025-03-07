#!/usr/bin/env python
# -*- coding: utf-8 -*-
# © 2024 HILAL Arkane. Tous droits réservés.

"""
Script d'automatisation pour la création d'un exécutable protégé par Cython.
Ce script:
1. Vérifie et installe les dépendances nécessaires
2. Compile les modules Python en C avec Cython (focus sur le dossier Generator)
3. Crée un exécutable autonome avec PyInstaller
"""

import os
import sys
import subprocess
import shutil
import platform
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
    
    required_packages = ['cython', 'pyinstaller']
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
    
    # Liste des fichiers à compiler
    files_to_compile = [
        'core/Generator/Optimizer/backtracking.py',
        'core/Generator/Optimizer/distribution_optimizer.py',
        'core/Generator/Optimizer/PlanningOptimizer.py',
        'core/Generator/Optimizer/weekend_optimizer.py',
        'core/Generator/Weekday/weekday_gen.py',
        'core/Generator/Weekend/planning_generator.py',
    ]
    
    # Normaliser les chemins selon le système d'exploitation
    normalized_files = []
    for file_path in files_to_compile:
        if platform.system() == 'Windows':
            normalized_path = file_path.replace('/', '\\')
        else:
            normalized_path = file_path.replace('\\', '/')
        normalized_files.append(normalized_path)
    
    # Compiler chaque fichier
    success_count = 0
    for file_path in normalized_files:
        print_step(f"Compilation de {file_path}...")
        
        try:
            # Commande pour compiler avec Cython
            cmd = [
                sys.executable, 
                "-m", "cython", 
                "--embed",  # Créer un fichier C autonome
                "-3",       # Python 3
                "-o", file_path.replace('.py', '.c'),  # Fichier de sortie
                file_path   # Fichier d'entrée
            ]
            
            # Ajouter des options d'optimisation
            cmd.extend([
                "-X", "boundscheck=False",
                "-X", "wraparound=False",
                "-X", "cdivision=True",
                "-X", "nonecheck=False",
                "-X", "embedsignature=False",
                "-X", "binding=False"
            ])
            
            # Exécuter la commande
            subprocess.check_call(cmd)
            print_success(f"Compilation réussie: {file_path}")
            success_count += 1
        except subprocess.CalledProcessError as e:
            print_error(f"Erreur lors de la compilation de {file_path}: {e}")
    
    # Afficher le résultat
    if success_count == len(normalized_files):
        print_success(f"{success_count}/{len(normalized_files)} fichiers compilés")
        return True
    else:
        print_warning(f"{success_count}/{len(normalized_files)} fichiers compilés")
        print_warning("Certains fichiers n'ont pas pu être compilés")
        return False

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
        return False
    else:
        print_success("Tous les fichiers C sont présents")
        return True

def prepare_obfuscated_directory():
    """Prépare le dossier pour les fichiers obfusqués."""
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
        return False

def create_executable():
    """Crée un exécutable autonome avec PyInstaller."""
    print_step("Création de l'exécutable avec PyInstaller...")
    
    # Dossier contenant les fichiers obfusqués
    obfuscated_dir = 'obfuscated'
    
    # Vérifier que le dossier existe
    if not os.path.exists(obfuscated_dir):
        print_error(f"Le dossier {obfuscated_dir} n'existe pas")
        return False
    
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
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur lors de la création de l'exécutable: {e}")
        return False

def main():
    """Fonction principale."""
    print_header("CRÉATION D'UN EXÉCUTABLE PROTÉGÉ PAR CYTHON")
    
    # Vérifier les dépendances
    check_dependencies()
    
    # Vérifier les outils de compilation
    check_build_tools()
    
    # Compiler avec Cython
    if not compile_with_cython():
        print_error("Erreur lors de la compilation avec Cython")
        sys.exit(1)
    
    # Vérifier les fichiers C
    if not check_c_files():
        print_error("Fichiers C manquants")
        sys.exit(1)
    
    # Préparer le dossier obfuscated
    if not prepare_obfuscated_directory():
        print_error("Erreur lors de la préparation du dossier obfuscated")
        sys.exit(1)
    
    # Créer l'exécutable
    if not create_executable():
        print_error("Erreur lors de la création de l'exécutable")
        sys.exit(1)
    
    print_header("PROCESSUS TERMINÉ AVEC SUCCÈS")
    print_success("L'exécutable se trouve dans le dossier 'dist'")
    print_success("Pour recréer l'exécutable à l'avenir, il suffit de réexécuter ce script")

if __name__ == "__main__":
    main()
