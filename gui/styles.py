# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

import sys
from PyQt6.QtGui import QColor

class ColorSystem:
    """Système de couleurs adaptatif selon le système d'exploitation"""
    def _get_window_background_color(self):
        """Couleur de fond globale pour les fenêtres"""
        return QColor(235, 240, 245) if self.is_windows else QColor(240, 242, 245)  # Gris-bleu plus prononcé sur Windows

    def __init__(self):
        self.is_windows = sys.platform == 'win32'
        
        # Couleurs de base
        self.colors = {
            "window_background": self._get_window_background_color(),
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
        return QColor(200, 210, 220) if self.is_windows else QColor(220, 220, 220)  # Plus bleuté et contrasté sur Windows

    def _get_weekday_color(self):
        """Couleur de fond pour les jours de semaine"""
        return QColor(250, 252, 255) if self.is_windows else QColor(255, 255, 255)  # Légèrement bleuté sur Windows

    def _get_weekend_desiderata_color(self):
        """Couleur pour les desiderata en weekend"""
        return QColor(255, 120, 120) if self.is_windows else QColor(255, 150, 150)  # Rouge plus vif sur Windows

    def _get_normal_desiderata_color(self):
        """Couleur pour les desiderata en semaine"""
        return QColor(255, 160, 160) if self.is_windows else QColor(255, 200, 200)  # Rouge plus vif sur Windows

    def _get_weekend_secondary_color(self):
        """Couleur pour les desiderata secondaires en weekend"""
        return QColor(120, 160, 255) if self.is_windows else QColor(150, 200, 255)  # Bleu plus vif sur Windows

    def _get_normal_secondary_color(self):
        """Couleur pour les desiderata secondaires en semaine"""
        return QColor(160, 200, 255) if self.is_windows else QColor(200, 230, 255)  # Bleu plus vif sur Windows

    def _get_available_color(self):
        """Couleur pour indiquer la disponibilité"""
        return QColor(120, 255, 120) if self.is_windows else QColor(150, 255, 150)  # Vert plus vif sur Windows

    def _get_grid_color(self):
        """Couleur des lignes de la grille"""
        return QColor(160, 160, 160) if self.is_windows else QColor(200, 200, 200)  # Plus foncé sur Windows

    def _get_text_color(self):
        """Couleur du texte"""
        return QColor(40, 40, 40) if self.is_windows else QColor(100, 100, 100)  # Noir plus prononcé sur Windows

    def get_cat_background(self):
        """Couleur de fond pour les CAT"""
        return QColor('#D8ECD9') if self.is_windows else QColor('#E8F5E9')  # Plus foncé sur Windows

    def get_half_time_background(self):
        """Couleur de fond pour les médecins mi-temps"""
        return QColor('#E8E9EC') if self.is_windows else QColor('#F3F4F6')  # Plus foncé sur Windows

    def get_unassigned_background(self):
        """Couleur de fond pour les postes non attribués"""
        return QColor('#EBEBEB') if self.is_windows else QColor('#F5F5F5')  # Plus foncé sur Windows

    def get_total_row_background(self):
        """Couleur de fond pour la ligne des totaux"""
        return QColor('#E0E0E0') if self.is_windows else QColor('#EEEEEE')  # Plus foncé sur Windows

    def get_interval_colors(self):
        """Couleurs pour les intervalles de valeurs"""
        if self.is_windows:
            return {
                'below_min': QColor(180, 255, 180, 255),  # Vert encore plus vif pour Windows
                'above_max': QColor(255, 180, 180, 255),  # Rouge encore plus vif pour Windows
                'within_range': QColor(250, 252, 255)  # Légèrement bleuté
            }
        else:
            return {
                'below_min': QColor('#E8F5E9'),  # Vert clair pour macOS
                'above_max': QColor('#FFEBEE'),  # Rouge clair pour macOS
                'within_range': QColor(255, 255, 255)  # Blanc
            }

    def get_post_group_colors(self):
        """Couleurs pour les groupes de postes"""
        if self.is_windows:
            return {
                'matin': QColor(160, 200, 255, 255),      # Bleu encore plus vif
                'apresMidi': QColor(255, 180, 130, 255),  # Orange encore plus vif
                'soirNuit': QColor(200, 160, 255, 255)    # Violet encore plus vif
            }
        else:
            return {
                'matin': QColor('#E3F2FD'),      # Bleu clair
                'apresMidi': QColor('#FFF3E0'),  # Orange clair
                'soirNuit': QColor('#EDE7F6')    # Violet clair
            }

    def get_weekend_group_colors(self):
        """Couleurs pour les groupes de weekend"""
        if self.is_windows:
            return {
                'gardes': QColor(160, 200, 255, 255),      # Bleu encore plus vif
                'visites': QColor(255, 180, 130, 255),     # Orange encore plus vif
                'consultations': QColor(200, 160, 255, 255) # Violet encore plus vif
            }
        else:
            return {
                'gardes': QColor('#E3F2FD'),      # Bleu clair
                'visites': QColor('#FFF3E0'),     # Orange clair
                'consultations': QColor('#EDE7F6') # Violet clair
            }

    def _get_button_colors(self):
        """Couleurs pour les différents types de boutons"""
        if self.is_windows:
            return {
                "edit": {
                    "bg": "#d8d8d8",
                    "border": "#b8b8b8",
                    "hover": "#c8c8c8"
                },
                "action": {
                    "bg": "#4c6d89",
                    "hover": "#3a5a76"
                },
                "add": {
                    "bg": "#0a6c0a",
                    "hover": "#085708"
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

# Style global de l'application
GLOBAL_STYLE = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {color_system.colors['window_background'].name()};
}}
"""

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
