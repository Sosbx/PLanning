# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

# Styles optimisés pour un meilleur contraste sur Windows
# Utilisation de couleurs plus vives et de contrastes renforcés

EDIT_DELETE_BUTTON_STYLE = """
    QPushButton {
        background-color: #ffffff;  /* Blanc pur pour plus de contraste */
        border: 1px solid #c0c4c8;  /* Bordure plus visible */
        border-radius: 4px;
        padding: 4px;
        margin: 2px;
    }
    QPushButton:hover {
        background-color: #e8f0fe;
        border-color: #1a73e8;  /* Bleu plus vif au survol */
    }
"""

ACTION_BUTTON_STYLE = """
    QPushButton {
        background-color: #2b78e4;  /* Bleu plus vif et contrasté */
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #1a73e8;  /* Bleu légèrement plus clair au survol */
    }
"""

ADD_BUTTON_STYLE = """
    QPushButton {
        background-color: #34a853;  /* Vert plus vif et contrasté */
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #1e8e3e;  /* Vert plus foncé au survol */
    }
"""
