# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

import sys

# Styles adaptés selon le système d'exploitation
if sys.platform == 'win32':
    # Styles optimisés pour Windows
    EDIT_DELETE_BUTTON_STYLE = """
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #c0c0c0;
            border-radius: 3px;
            padding: 5px;
            margin: 2px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
            border-color: #0078d7;
        }
    """

    ACTION_BUTTON_STYLE = """
        QPushButton {
            background-color: #0078d7;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 3px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #006cc1;
        }
    """

    ADD_BUTTON_STYLE = """
        QPushButton {
            background-color: #107c10;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 3px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #0b590b;
        }
    """
else:
    # Styles originaux pour macOS
    EDIT_DELETE_BUTTON_STYLE = """
        QPushButton {
            background-color: #f8f9fa;
            border: 1px solid #e1e4e8;
            border-radius: 4px;
            padding: 4px;
            margin: 2px;
        }
        QPushButton:hover {
            background-color: #e8f0fe;
            border-color: #1a73e8;
        }
    """

    ACTION_BUTTON_STYLE = """
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
    """

    ADD_BUTTON_STYLE = """
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
    """
