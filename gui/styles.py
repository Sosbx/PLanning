# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

import sys
from PyQt6.QtGui import QColor

class ColorSystem:
    """Système de couleurs adaptatif selon le système d'exploitation"""
    def __init__(self):
        self.is_windows = sys.platform == 'win32'
        
        # Couleurs de base
        self.colors = {
            "weekend": self._get_weekend_color(),
            "weekday": self._get_weekday_color(),
            "desiderata": {
                "primary": {
                    "weekend": self._get_weekend_desiderata_color(),
                    "normal": self._get_normal_desiderata_color()
                },
                "secondary": {
                    "weekend": self._get_weekend_secondary_color(),
                    "normal": self._get_normal_secondary_color()
                }
            },
            "available": self._get_available_color(),
            "grid": self._get_grid_color(),
            "text": self._get_text_color(),
            "button": self._get_button_colors()
        }

    def _get_weekend_color(self):
        """Couleur de fond pour les weekends"""
        return QColor(200, 200, 200, 255) if self.is_windows else QColor(220, 220, 220, 255)

    def _get_weekday_color(self):
        """Couleur de fond pour les jours de semaine"""
        return QColor(255, 255, 255, 255)

    def _get_weekend_desiderata_color(self):
        """Couleur pour les desiderata en weekend"""
        return QColor(255, 130, 130, 255) if self.is_windows else QColor(255, 150, 150, 255)

    def _get_normal_desiderata_color(self):
        """Couleur pour les desiderata en semaine"""
        return QColor(255, 180, 180, 255) if self.is_windows else QColor(255, 200, 200, 255)

    def _get_weekend_secondary_color(self):
        """Couleur pour les desiderata secondaires en weekend"""
        return QColor(130, 180, 255, 255) if self.is_windows else QColor(150, 200, 255, 255)

    def _get_normal_secondary_color(self):
        """Couleur pour les desiderata secondaires en semaine"""
        return QColor(180, 220, 255, 255) if self.is_windows else QColor(200, 230, 255, 255)

    def _get_available_color(self):
        """Couleur pour indiquer la disponibilité"""
        return QColor(150, 255, 150, 255)

    def _get_grid_color(self):
        """Couleur des lignes de la grille"""
        return QColor(180, 180, 180, 255) if self.is_windows else QColor(200, 200, 200, 255)

    def _get_text_color(self):
        """Couleur du texte"""
        return QColor(60, 60, 60, 255) if self.is_windows else QColor(100, 100, 100, 255)

    def _get_button_colors(self):
        """Couleurs pour les différents types de boutons"""
        if self.is_windows:
            return {
                "edit": {
                    "bg": "#e0e0e0",
                    "border": "#b0b0b0",
                    "hover": "#d0d0d0"
                },
                "action": {
                    "bg": "#0078d7",
                    "hover": "#006cc1"
                },
                "add": {
                    "bg": "#107c10",
                    "hover": "#0b590b"
                }
            }
        else:
            return {
                "edit": {
                    "bg": "#fff5f5",
                    "border": "#ffe8e8",
                    "hover": "#fff0f0"
                },
                "action": {
                    "bg": "#5c7d99",
                    "hover": "#4a6a86"
                },
                "add": {
                    "bg": "#4CAF50",
                    "hover": "#45a049"
                }
            }

    def get_color(self, color_type, context=None, priority=None):
        """
        Obtient la couleur appropriée selon le contexte.
        
        Args:
            color_type (str): Type de couleur ('weekend', 'weekday', 'desiderata', etc.)
            context (str, optional): Contexte ('weekend' ou 'normal')
            priority (str, optional): Priorité pour les desiderata ('primary' ou 'secondary')
        """
        if color_type == 'desiderata':
            if not context or not priority:
                raise ValueError("Context and priority required for desiderata colors")
            return self.colors["desiderata"][priority][context]
            
        return self.colors.get(color_type, self.colors["weekday"])

# Initialisation du système de couleurs
color_system = ColorSystem()

# Styles des boutons utilisant le système de couleurs
EDIT_DELETE_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['button']['edit']['bg']};
        border: 1px solid {color_system.colors['button']['edit']['border']};
        border-radius: 3px;
        padding: 5px;
        margin: 2px;
        color: #333333;
    }}
    QPushButton:hover {{
        background-color: {color_system.colors['button']['edit']['hover']};
        border-color: {color_system.colors['button']['action']['bg']};
    }}
"""

ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['button']['action']['bg']};
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 3px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {color_system.colors['button']['action']['hover']};
    }}
"""

ADD_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['button']['add']['bg']};
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 3px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {color_system.colors['button']['add']['hover']};
    }}
"""
