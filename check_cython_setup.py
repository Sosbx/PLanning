#!/usr/bin/env python
# -*- coding: utf-8 -*-
# © 2024 HILAL Arkane. Tous droits réservés.

"""
Script de vérification pour tester la configuration Cython.
Ce script:
1. Vérifie si Cython est installé
2. Analyse le dossier Generator pour vérifier la compatibilité avec Cython
3. Génère un rapport de compatibilité sans effectuer la compilation complète
"""

import os
import sys
import importlib.util
import subprocess
from pathlib import Path

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

def check_cython():
    """Vérifie si Cython est installé."""
    print_step("Vérification de Cython...")
    
    if importlib.util.find_spec('Cython') is None:
        print_warning("Cython n'est pas installé")
        print_step("Installation de Cython...")
        
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'cython'])
            print_success("Cython installé avec succès")
        except subprocess.CalledProcessError as e:
            print_error(f"Erreur lors de l'installation de Cython: {e}")
            sys.exit(1)
    else:
        print_success("Cython est installé")

def analyze_generator_folder():
    """Analyse le dossier Generator pour vérifier la compatibilité avec Cython."""
    print_step("Analyse du dossier Generator...")
    
    generator_dir = 'core/Generator'
    if not os.path.exists(generator_dir):
        print_error(f"Le dossier {generator_dir} n'existe pas")
        sys.exit(1)
    
    python_files = []
    for root, dirs, files in os.walk(generator_dir):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                python_files.append(os.path.join(root, file))
    
    if not python_files:
        print_warning(f"Aucun fichier Python trouvé dans {generator_dir}")
        sys.exit(1)
    
    print_success(f"{len(python_files)} fichiers Python trouvés dans {generator_dir}")
    
    # Vérifier les imports problématiques pour Cython
    problematic_imports = []
    for file_path in python_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                content = f.read()
                
                # Vérifier les imports dynamiques
                if 'importlib' in content or '__import__' in content:
                    problematic_imports.append((file_path, "Import dynamique détecté"))
                
                # Vérifier les imports circulaires
                if 'from . import' in content:
                    problematic_imports.append((file_path, "Import circulaire potentiel"))
                
                # Vérifier les imports relatifs complexes
                if 'from ..' in content:
                    problematic_imports.append((file_path, "Import relatif complexe"))
                
            except UnicodeDecodeError:
                print_warning(f"Impossible de lire {file_path} en UTF-8")
    
    if problematic_imports:
        print_warning("Imports potentiellement problématiques pour Cython détectés:")
        for file_path, reason in problematic_imports:
            print(f"  - {file_path}: {reason}")
    else:
        print_success("Aucun import problématique détecté")
    
    return python_files

def generate_cython_test_file(python_files):
    """Génère un fichier de test pour Cython."""
    print_step("Génération d'un fichier de test pour Cython...")
    
    test_file = 'cython_test.py'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("""
from Cython.Build import cythonize
from setuptools import setup, Extension
import os

# Liste des fichiers à compiler
extensions = [
""")
        for file_path in python_files:
            module_path = file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            f.write(f'    Extension("{module_path}", ["{file_path}"]),\n')
        
        f.write("""
]

# Directives Cython pour l'obfuscation
cython_directives = {
    'language_level': 3,
    'embedsignature': False,
    'emit_code_comments': False,
    'docstrings': False,
    'binding': False,
    'boundscheck': False,
    'wraparound': False,
    'cdivision': True,
    'nonecheck': False,
    'annotation_typing': False,
}

# Afficher les fichiers qui seront compilés
print("\\nFichiers qui seront compilés avec Cython:")
for ext in extensions:
    print(f"  - {ext.sources[0]} -> {ext.name}")

print("\\nCe script ne compile pas les fichiers, il vérifie seulement la configuration.")
print("Pour compiler les fichiers, utilisez le script build_exe.py après avoir installé les outils de compilation C.")
""")
    
    print_success(f"Fichier de test généré: {test_file}")
    print_success("Vous pouvez examiner ce fichier pour voir quels modules seront compilés")

def main():
    """Fonction principale."""
    print_header("VÉRIFICATION DE LA CONFIGURATION CYTHON")
    
    # Vérifier Cython
    check_cython()
    
    # Analyser le dossier Generator
    python_files = analyze_generator_folder()
    
    # Générer un fichier de test
    generate_cython_test_file(python_files)
    
    print_header("VÉRIFICATION TERMINÉE")
    print_success("La configuration semble correcte pour la compilation avec Cython")
    print_success("Veuillez installer Microsoft Visual C++ Build Tools avant d'exécuter build_exe.py")
    print_success("Lien: https://visualstudio.microsoft.com/visual-cpp-build-tools/")

if __name__ == "__main__":
    main()
