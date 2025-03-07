from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
from Cython.Distutils import build_ext
import os
import sys

# Determine the extensions to compile with Cython
def get_extensions():
    extensions = []
    
    # Explicitly list the files to compile
    files_to_compile = [
        'core/Generator/Optimizer/backtracking.py',
        'core/Generator/Optimizer/distribution_optimizer.py',
        'core/Generator/Optimizer/PlanningOptimizer.py',
        'core/Generator/Optimizer/weekend_optimizer.py',
        'core/Generator/Weekday/weekday_gen.py',
        'core/Generator/Weekend/planning_generator.py',
    ]
    
    for file_path in files_to_compile:
        # Normalize path
        normalized_path = file_path.replace('\\', '/')
        # Create module path
        module_path = normalized_path.replace('/', '.').replace('.py', '')
        
        # Create an Extension object for each Python file
        extensions.append(
            Extension(
                module_path,
                [normalized_path],
                extra_compile_args=['/O2'] if sys.platform == 'win32' else ['-O2'],
                extra_link_args=[],
            )
        )
    
    return extensions

# Cython compiler directives for maximum obfuscation
cython_directives = {
    'language_level': 3,
    'embedsignature': False,
    'emit_code_comments': False,
    # 'docstrings': False,  # Removed as it might not be supported in this Cython version
    'binding': False,
    'boundscheck': False,
    'wraparound': False,
    'cdivision': True,
    'nonecheck': False,
    # 'annotation_typing': False,  # Removed as it might not be supported in this Cython version
}

setup(
    name="Planning4",
    version="4.0",
    packages=find_packages(),
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives=cython_directives,
        annotate=False,  # Don't generate HTML annotation files
    ),
    cmdclass={'build_ext': build_ext},
    include_package_data=True,
    package_data={
        '': ['*.png', '*.ico', '*.jpg', '*.jpeg', '*.gif'],
    },
)
