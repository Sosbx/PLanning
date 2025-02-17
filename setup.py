from setuptools import setup, find_packages
from Cython.Build import cythonize
import os
import time

# Liste des modules à compiler avec Cython
core_modules = [
    # Core Generators
    "core/Generator/Optimizer/backtracking.py",
    "core/Generator/Optimizer/distribution_optimizer.py",
    "core/Generator/Optimizer/PlanningOptimizer.py",
    "core/Generator/Optimizer/weekend_optimizer.py",
    "core/Generator/Weekday/weekday_gen.py",
    "core/Generator/Weekend/planning_generator.py",
    
    # Core Analyzers
    "core/Analyzer/pre_analyzer.py",
    "core/Analyzer/availability_matrix.py",
    "core/Analyzer/combinations_analyzer.py",
    
    # Core Constants and Models
    "core/Constantes/constraints.py",
    "core/Constantes/custom_post.py",
    "core/Constantes/models.py",
    "core/Constantes/day_type.py",
    "core/Constantes/QuotasTracking.py",
    
    # Main entry point
    "main.py"
]

# Compiler directives pour Cython avec protection renforcée
compiler_directives = {
    'language_level': "3",
    'boundscheck': False,
    'wraparound': False,
    'initializedcheck': False,
    'nonecheck': False,
    'cdivision': True,
    'embedsignature': False,  # Supprime les signatures Python
    'annotation_typing': False,  # Supprime les informations de type
    'binding': False,  # Désactive la génération de code de binding
    'optimize.use_switch': True,  # Utilise les switch statements C
    'optimize.inline_defnode_calls': True,  # Inline les appels de fonctions
    'remove_docstrings': True,  # Supprime les docstrings
    'profile': False,  # Désactive le profiling
}

# Configuration de l'obfuscation
import random
import string

def generate_random_name(length=8):
    return ''.join(random.choices(string.ascii_letters, k=length))

# Renomme les modules de manière aléatoire
obfuscated_modules = [(module, generate_random_name()) for module in core_modules]

setup(
    name='PlanificateurSOSMedecins',
    version='1.0.0',
    packages=find_packages(),
    ext_modules=cythonize(
        [module for module, _ in obfuscated_modules],
        compiler_directives=compiler_directives,
        compile_time_env={
            "CYTHON_RELEASE": True,
            "OBFUSCATED": True,
            "BUILD_TIME": str(int(time.time())),
        }
    ),
    # Inclure les fichiers non-Python nécessaires
    package_data={
        '': ['*.png', '*.json', '*.txt', '*.pkl'],
    },
    # Dépendances requises
    install_requires=[
        'PyQt5',
        'numpy',
        'pandas',
        'pyinstaller',
    ],
)
