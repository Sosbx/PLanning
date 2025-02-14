from setuptools import setup, find_packages
from Cython.Build import cythonize
import os

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

# Compiler directives pour Cython
compiler_directives = {
    'language_level': "3",
    'boundscheck': False,  # Désactive les vérifications de limites pour de meilleures performances
    'wraparound': False,   # Désactive le wrapping négatif des indices
    'initializedcheck': False,  # Désactive les vérifications d'initialisation
    'nonecheck': False,    # Désactive les vérifications de None
    'cdivision': True,     # Utilise la division C au lieu de la division Python
}

setup(
    name='PlanificateurSOSMedecins',
    version='1.0.0',
    packages=find_packages(),
    ext_modules=cythonize(
        core_modules,
        compiler_directives=compiler_directives,
        # Compile en mode release pour de meilleures performances et protection
        compile_time_env={"CYTHON_RELEASE": True}
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
