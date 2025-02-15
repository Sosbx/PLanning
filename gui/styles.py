# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

import sys
from PyQt6.QtGui import QColor

class ColorSystem:
    """Système de couleurs adaptatif selon le système d'exploitation"""
    def _get_window_background_color(self):
        """Couleur de fond globale pour les fenêtres"""
        return QColor(225, 230, 235) if self.is_windows else QColor(235, 238, 242)  # Bleu légèrement plus foncé pour meilleur contraste

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
        return QColor(215, 225, 235) if self.is_windows else QColor(225, 235, 245)  # Bleu-gris clair pour les weekends

    def _get_weekday_color(self):
        """Couleur de fond pour les jours de semaine"""
        return QColor(240, 242, 245)  # Blanc-gris légèrement plus foncé pour meilleur contraste

    def _get_weekend_desiderata_color(self):
        """Couleur pour les desiderata en weekend"""
        return QColor(255, 80, 80) if self.is_windows else QColor(255, 100, 100)  # Rouge plus foncé pour meilleur contraste

    def _get_normal_desiderata_color(self):
        """Couleur pour les desiderata en semaine"""
        return QColor(255, 120, 120) if self.is_windows else QColor(255, 140, 140)  # Rouge plus foncé pour meilleur contraste

    def _get_weekend_secondary_color(self):
        """Couleur pour les desiderata secondaires en weekend"""
        return QColor(80, 140, 255) if self.is_windows else QColor(100, 160, 255)  # Bleu plus foncé pour meilleur contraste

    def _get_normal_secondary_color(self):
        """Couleur pour les desiderata secondaires en semaine"""
        return QColor(120, 180, 255) if self.is_windows else QColor(140, 200, 255)  # Bleu plus foncé pour meilleur contraste

    def _get_available_color(self):
        """Couleur pour indiquer la disponibilité"""
        return QColor(120, 255, 120) if self.is_windows else QColor(140, 255, 140)  # Vert plus foncé pour meilleur contraste

    def _get_grid_color(self):
        """Couleur des lignes de la grille"""
        return QColor(180, 190, 200) if self.is_windows else QColor(200, 210, 220)  # Bleu-gris pour la grille

    def _get_text_color(self):
        """Couleur du texte"""
        return QColor(30, 35, 40)  # Gris très foncé pour une meilleure lisibilité

    def get_cat_background(self):
        """Couleur de fond pour les CAT"""
        return QColor('#C8DCC9') if self.is_windows else QColor('#E8F5E9')  # Plus foncé sur Windows

    def get_half_time_background(self):
        """Couleur de fond pour les médecins mi-temps"""
        return QColor('#D8D9DC') if self.is_windows else QColor('#F3F4F6')  # Plus foncé sur Windows

    def get_unassigned_background(self):
        """Couleur de fond pour les postes non attribués"""
        return QColor('#DBDBDB') if self.is_windows else QColor('#F5F5F5')  # Plus foncé sur Windows

    def get_total_row_background(self):
        """Couleur de fond pour la ligne des totaux"""
        return QColor('#D0D0D0') if self.is_windows else QColor('#EEEEEE')  # Plus foncé sur Windows

    def get_interval_colors(self):
        """Couleurs pour les intervalles de valeurs"""
        if self.is_windows:
            return {
                'below_min': QColor(100, 255, 100, 255),  # Vert beaucoup plus vif pour Windows
                'above_max': QColor(255, 100, 100, 255),  # Rouge beaucoup plus vif pour Windows
                'within_range': QColor(245, 248, 255)  # Légèrement bleuté
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
                'matin': QColor(130, 180, 255, 255),      # Bleu encore plus vif
                'apresMidi': QColor(255, 160, 100, 255),  # Orange encore plus vif
                'soirNuit': QColor(180, 140, 255, 255)    # Violet encore plus vif
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
                'gardes': QColor(130, 180, 255, 255),      # Bleu plus contrasté
                'visites': QColor(255, 160, 100, 255),     # Orange plus contrasté
                'consultations': QColor(180, 140, 255, 255) # Violet plus contrasté
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
                    "bg": "#e8f0f8",
                    "border": "#c0d0e0",
                    "hover": "#d8e5f0"
                },
                "action": {
                    "bg": "#2c5282",
                    "hover": "#1a365d"
                },
                "add": {
                    "bg": "#2b6cb0",
                    "hover": "#2c5282"
                }
            }
        else:
            return {
                "edit": {
                    "bg": "#f0f5fa",
                    "border": "#d0e0f0",
                    "hover": "#e0eaf5"
                },
                "action": {
                    "bg": "#3182ce",
                    "hover": "#2b6cb0"
                },
                "add": {
                    "bg": "#3182ce",
                    "hover": "#2b6cb0"
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
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 10pt;
}}

QLabel {{
    color: {color_system.colors['text'].name()};
    font-size: 10pt;
}}

QTableWidget {{
    gridline-color: {color_system.colors['grid'].name()};
    font-size: 9pt;
}}

QHeaderView::section {{
    background-color: #e5e9f0;
    color: {color_system.colors['text'].name()};
    font-weight: bold;
    padding: 4px;
    border: 1px solid {color_system.colors['grid'].name()};
}}

QTabWidget::pane {{
    border: 1px solid #c0d0e0;
    background-color: {color_system.colors['window_background'].name()};
}}

QTabBar::tab {{
    background-color: #d8e0e8;
    color: {color_system.colors['text'].name()};
    border: 1px solid #b0c0d0;
    padding: 6px 12px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {color_system.colors['window_background'].name()};
    border-bottom: none;
}}
"""

# Styles des boutons utilisant le système de couleurs
EDIT_DELETE_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['button']['edit']['bg']};
        border: 1px solid {color_system.colors['button']['edit']['border']};
        border-radius: 3px;
        padding: 6px 12px;
        margin: 2px;
        color: #2d3748;
        font-weight: 500;
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
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 10pt;
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
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 10pt;
    }}
    QPushButton:hover {{
        background-color: {color_system.colors['button']['add']['hover']};
    }}
"""
