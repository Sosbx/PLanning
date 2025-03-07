
from Cython.Build import cythonize
from setuptools import setup, Extension
import os

# Liste des fichiers à compiler
extensions = [
    Extension("core.Generator.Optimizer. __init__", ["core/Generator\Optimizer\ __init__.py"]),
    Extension("core.Generator.Optimizer.backtracking", ["core/Generator\Optimizer\backtracking.py"]),
    Extension("core.Generator.Optimizer.distribution_optimizer", ["core/Generator\Optimizer\distribution_optimizer.py"]),
    Extension("core.Generator.Optimizer.PlanningOptimizer", ["core/Generator\Optimizer\PlanningOptimizer.py"]),
    Extension("core.Generator.Optimizer.weekend_optimizer", ["core/Generator\Optimizer\weekend_optimizer.py"]),
    Extension("core.Generator.Weekday.weekday_gen", ["core/Generator\Weekday\weekday_gen.py"]),
    Extension("core.Generator.Weekend.planning_generator", ["core/Generator\Weekend\planning_generator.py"]),

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
print("\nFichiers qui seront compilés avec Cython:")
for ext in extensions:
    print(f"  - {ext.sources[0]} -> {ext.name}")

print("\nCe script ne compile pas les fichiers, il vérifie seulement la configuration.")
print("Pour compiler les fichiers, utilisez le script build_exe.py après avoir installé les outils de compilation C.")
