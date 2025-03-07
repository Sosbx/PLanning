# Planning4 - Exécutable Protégé par Cython

Ce projet contient des scripts pour créer un exécutable protégé par Cython à partir du code source de Planning4.

## Prérequis

- Python 3.6 ou supérieur
- Microsoft Visual C++ Build Tools (Windows) ou GCC (Linux/Mac)

## Installation des outils de compilation C

### Windows

1. Téléchargez et installez Microsoft Visual C++ Build Tools depuis:
   https://visualstudio.microsoft.com/visual-cpp-build-tools/

2. Lors de l'installation, sélectionnez "Développement Desktop en C++" pour installer les outils nécessaires.

### Linux

```bash
sudo apt-get update
sudo apt-get install build-essential
```

### macOS

```bash
xcode-select --install
```

## Scripts disponibles

### 1. `check_cython_setup.py`

Ce script vérifie que Cython est correctement installé et configuré sans nécessiter les outils de compilation C.

```bash
python check_cython_setup.py
```

### 2. `compile_cython.py`

Ce script compile les fichiers Python en C avec Cython, en se concentrant sur le dossier Generator.

```bash
python compile_cython.py
```

### 3. `create_exe.py`

Ce script crée un exécutable à partir des fichiers C compilés.

```bash
python create_exe.py
```

### 4. `build_protected_exe.py`

Ce script combine les étapes de compilation et de création d'exécutable en un seul script.

```bash
python build_protected_exe.py
```

## Processus de création de l'exécutable

1. **Vérification des dépendances**
   - Cython
   - PyInstaller

2. **Vérification des outils de compilation C**
   - Microsoft Visual C++ Build Tools (Windows)
   - GCC (Linux/Mac)

3. **Compilation avec Cython**
   - Compilation des fichiers Python en C
   - Application des directives d'optimisation

4. **Préparation des fichiers**
   - Copie des fichiers C compilés
   - Copie des autres fichiers nécessaires

5. **Création de l'exécutable**
   - Utilisation de PyInstaller pour créer un exécutable autonome

## Résultat

L'exécutable final se trouve dans le dossier `dist`.

## Notes

- Les fichiers C compilés sont obfusqués par nature, ce qui rend difficile la rétro-ingénierie.
- L'exécutable final est autonome et ne nécessite pas d'installation de Python.
