# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

# Couleurs optimisées pour la compatibilité cross-platform
# Utilisation de couleurs plus douces et de l'opacité pour une meilleure cohérence

EDIT_DELETE_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(248, 249, 250, 0.95);  /* Légèrement transparent pour adoucir */
        border: 1px solid rgba(225, 228, 232, 0.9);
        border-radius: 4px;
        padding: 4px;
        margin: 2px;
    }
    QPushButton:hover {
        background-color: rgba(232, 240, 254, 0.9);  /* Plus doux sur Windows */
        border-color: rgba(26, 115, 232, 0.8);
    }
"""

ACTION_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(52, 152, 219, 0.9);  /* Bleu plus doux */
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: rgba(41, 128, 185, 0.9);  /* Version plus sombre adoucie */
    }
"""

ADD_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(76, 175, 80, 0.9);  /* Vert plus doux */
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: rgba(69, 160, 73, 0.9);  /* Version plus sombre adoucie */
    }
"""
