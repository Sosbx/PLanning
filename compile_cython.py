#!/usr/bin/env python
# -*- coding: utf-8 -*-
# © 2024 HILAL Arkane. Tous droits réservés.

"""
Script simplifié pour compiler les fichiers Python en C avec Cython.
"""

import os
import sys
import subprocess
import platform

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

def compile_file(file_path):
    """Compile un fichier Python en C avec Cython."""
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
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Erreur lors de la compilation de {file_path}: {e}")
        return False

def main():
    """Fonction principale."""
    print_header("COMPILATION AVEC CYTHON")
    
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
        if compile_file(file_path):
            success_count += 1
    
    # Afficher le résultat
    if success_count == len(normalized_files):
        print_header("COMPILATION TERMINÉE AVEC SUCCÈS")
        print_success(f"{success_count}/{len(normalized_files)} fichiers compilés")
    else:
        print_header("COMPILATION TERMINÉE AVEC DES ERREURS")
        print_warning(f"{success_count}/{len(normalized_files)} fichiers compilés")
        print_warning("Certains fichiers n'ont pas pu être compilés")

if __name__ == "__main__":
    main()
