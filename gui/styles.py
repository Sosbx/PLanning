# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

import sys
import platform
from PyQt6.QtGui import QColor, QGuiApplication, QScreen, QBrush
from PyQt6.QtCore import QOperatingSystemVersion, QSysInfo, Qt

class PlatformHelper:
   
    
    @staticmethod
    def get_platform():
        """Détecte la plateforme actuelle (Windows, macOS, Linux)."""
        if sys.platform.startswith('win'):
            return 'Windows'
        elif sys.platform.startswith('darwin'):
            return 'macOS'
        elif sys.platform.startswith('linux'):
            return 'Linux'
        else:
            return 'Unknown'
    
    @staticmethod
    def get_dpi_scale_factor():
        """Calcule le facteur d'échelle DPI pour l'écran principal."""
        try:
            # Obtenir l'écran principal
            screen = QGuiApplication.primaryScreen()
            if screen:
                # Obtenir le facteur d'échelle logique
                logical_dpi = screen.logicalDotsPerInch()
                # DPI de référence (96 pour Windows, 72 pour macOS)
                reference_dpi = 72.0 if sys.platform.startswith('darwin') else 96.0
                return logical_dpi / reference_dpi
            return 1.0
        except Exception:
            # En cas d'erreur, retourner 1.0 comme valeur par défaut
            return 1.0
    
    @staticmethod
    def get_platform_font_adjustments():
        """Retourne les ajustements de taille de police spécifiques à la plateforme."""
        platform = PlatformHelper.get_platform()
        if platform == 'Windows':
            # Sur Windows, réduire légèrement les tailles de police
            return {
                'base_size_factor': 0.9,
                'header_size_factor': 0.85,
                'period_size_factor': 0.9,
                'weekday_size_factor': 0.9
            }
        elif platform == 'macOS':
            # Sur macOS, utiliser les tailles par défaut
            return {
                'base_size_factor': 1.0,
                'header_size_factor': 1.0,
                'period_size_factor': 1.0,
                'weekday_size_factor': 1.0
            }
        else:
            # Pour Linux et autres plateformes
            return {
                'base_size_factor': 0.95,
                'header_size_factor': 0.9,
                'period_size_factor': 0.95,
                'weekday_size_factor': 0.95
            }
    
    @staticmethod
    def get_platform_color_adjustments():
        """Retourne les ajustements de couleur spécifiques à la plateforme."""
        platform = PlatformHelper.get_platform()
        if platform == 'Windows':
            # Sur Windows, augmenter légèrement la saturation des couleurs
            return {
                'color_saturation_factor': 1.1,
                'force_explicit_colors': True
            }
        else:
            # Pour macOS et autres plateformes
            return {
                'color_saturation_factor': 1.0,
                'force_explicit_colors': False
            }
    
    @staticmethod
    def adjust_color_for_platform(color):
        """Ajuste une couleur pour la plateforme actuelle."""
        adjustments = PlatformHelper.get_platform_color_adjustments()
        
        # Si nous n'avons pas besoin d'ajuster la couleur, la retourner telle quelle
        if adjustments['color_saturation_factor'] == 1.0 and not adjustments['force_explicit_colors']:
            return color
        
        # Convertir en HSL pour ajuster la saturation
        h, s, l, a = color.getHslF()
        
        # Ajuster la saturation
        s = min(1.0, s * adjustments['color_saturation_factor'])
        
        # Créer une nouvelle couleur avec la saturation ajustée
        adjusted_color = QColor()
        adjusted_color.setHslF(h, s, l, a)
        
        return adjusted_color
    
    @staticmethod
    def apply_background_color(item, color):
        """
        Applique une couleur de fond à un élément de manière compatible avec toutes les plateformes.
        
        Args:
            item: L'élément de tableau (QTableWidgetItem) auquel appliquer la couleur
            color: La couleur à appliquer (QColor)
        """
        if not item:
            return
            
        platform = PlatformHelper.get_platform()
        brush = QBrush(color)
        
        # Sur Windows, utiliser setData avec BackgroundRole
        if platform == 'Windows':
            item.setData(Qt.ItemDataRole.BackgroundRole, brush)
        
        # Sur toutes les plateformes, utiliser aussi setBackground pour compatibilité
        item.setBackground(brush)
    
    @staticmethod
    def apply_foreground_color(item, color):
        """
        Applique une couleur de texte à un élément de manière compatible avec toutes les plateformes.
        
        Args:
            item: L'élément de tableau (QTableWidgetItem) auquel appliquer la couleur
            color: La couleur à appliquer (QColor)
        """
        if not item:
            return
            
        platform = PlatformHelper.get_platform()
        brush = QBrush(color)
        
        # Sur Windows, utiliser setData avec ForegroundRole
        if platform == 'Windows':
            item.setData(Qt.ItemDataRole.ForegroundRole, brush)
        
        # Sur toutes les plateformes, utiliser aussi setForeground pour compatibilité
        item.setForeground(brush)

class ColorSystem:
    def __init__(self):
        # Palette optimisée pour l'accessibilité avec ajustements spécifiques à la plateforme
        # Couleurs de base
        base_colors = {
            'primary': QColor('#1A5A96'),        # Bleu principal
            'secondary': QColor('#505A64'),      # Gris foncé
            'success': QColor('#2E8540'),        # Vert succès
            'danger': QColor('#D73F3F'),         # Rouge alerte
            'warning': QColor('#F39C12'),        # Orange avertissement
            'info': QColor('#3498DB'),           # Bleu info
            'light': QColor('#F5F7FA'),          # Gris très pâle
            'dark': QColor('#2C3E50'),           # Gris très foncé
            'window_background': QColor('#F5F7FA'), # Fond d'application
            'weekend': QColor('#E2E8F0'),        # Fond pour les weekends (gris pâle)
            'weekday': QColor('#FFFFFF'),        # Fond pour les jours de semaine
            'available': QColor('#D4EDDA'),      # Disponibilité
        }
        
        # Couleurs de texte
        text_colors = {
            'primary': QColor('#2C3E50'),    # Texte principal
            'secondary': QColor('#505A64'),  # Texte secondaire
            'light': QColor('#FFFFFF'),      # Texte clair
            'dark': QColor('#1A1A1A'),       # Texte foncé
            'disabled': QColor('#A0AEC0')    # Texte désactivé
        }
        
        # Couleurs de conteneur
        container_colors = {
            'background': QColor('#FFFFFF'), # Fond de conteneur
            'border': QColor('#CBD5E1'),     # Bordure de conteneur
            'hover': QColor('#E9EEF4'),      # Effet de survol
            'disabled': QColor('#EDF2F7')    # Conteneur désactivé
        }
        
        # Couleurs de tableau
        table_colors = {
            'header': QColor('#C6D1E1'),     # En-tête de tableau
            'border': QColor('#B4C2D3'),     # Bordure de tableau
            'hover': QColor('#D8E1ED'),      # Ligne survolée
            'selected': QColor('#B8C7DB'),   # Ligne sélectionnée
            'alternate': QColor('#E2E8F0'),  # Ligne alternée
            'background': QColor('#EDF2F7')  # Fond de tableau
        }
        
        # Couleurs de focus
        focus_colors = {
            'outline': QColor('#1A5A96')     # Contour de focus
        }
        
        # Couleurs de desiderata
        desiderata_colors = {
            'primary': {
                'normal': QColor('#FFD4D4'),  # Rouge clair pour jours normaux
                'weekend': QColor('#FFA8A8')  # Rouge plus foncé pour weekends
            },
            'secondary': {
                'normal': QColor('#D4E4FF'),  # Bleu clair pour jours normaux
                'weekend': QColor('#A8C8FF')  # Bleu plus foncé pour weekends
            }
        }
        
        # Couleurs pour les différents types de postes
        post_type_colors = {
            'consultation': QColor('#D0E2F3'),  # Bleu pâle pour consultations
            'visite': QColor('#D4EDDA'),        # Vert pâle pour visites
            'garde': QColor('#E2D4ED')          # Violet pâle pour gardes
        }
        
        # Appliquer les ajustements de couleur spécifiques à la plateforme
        self.colors = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in base_colors.items()}
        
        # Ajouter les dictionnaires de couleurs imbriqués avec ajustements
        self.colors['text'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in text_colors.items()}
        self.colors['container'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in container_colors.items()}
        self.colors['table'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in table_colors.items()}
        self.colors['focus'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in focus_colors.items()}
        
        # Traiter les couleurs de desiderata (structure imbriquée à deux niveaux)
        self.colors['desiderata'] = {}
        for priority, contexts in desiderata_colors.items():
            self.colors['desiderata'][priority] = {}
            for context, color in contexts.items():
                self.colors['desiderata'][priority][context] = PlatformHelper.adjust_color_for_platform(color)
        
        # Ajouter les couleurs des types de postes
        self.colors['post_types'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in post_type_colors.items()}
        
        # Styles pour les boutons et autres éléments
        self.styles = {
            'button': {
                'primary': """
                    QPushButton {
                        background-color: #1A5A96;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: 500;
                        min-height: 30px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #1467A8;
                    }
                    QPushButton:pressed {
                        background-color: #0E4875;
                    }
                    QPushButton:disabled {
                        background-color: #A0AEC0;
                        color: #E2E8F0;
                    }
                """,
                'success': """
                    QPushButton {
                        background-color: #2E8540;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: 500;
                        min-height: 30px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #267638;
                    }
                    QPushButton:pressed {
                        background-color: #1E622D;
                    }
                    QPushButton:disabled {
                        background-color: #A0AEC0;
                        color: #E2E8F0;
                    }
                """,
                'danger': """
                    QPushButton {
                        background-color: #D73F3F;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: 500;
                        min-height: 30px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #C42F2F;
                    }
                    QPushButton:pressed {
                        background-color: #A42828;
                    }
                    QPushButton:disabled {
                        background-color: #A0AEC0;
                        color: #E2E8F0;
                    }
                """,
                'secondary': """
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #505A64;
                        border: 1px solid #CBD5E1;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: 500;
                        min-height: 30px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #EDF2F7;
                        border-color: #A0AEC0;
                    }
                    QPushButton:pressed {
                        background-color: #E2E8F0;
                        border-color: #718096;
                    }
                    QPushButton:disabled {
                        background-color: #EDF2F7;
                        color: #A0AEC0;
                        border-color: #E2E8F0;
                    }
                """
            },
            'table': {
                'base': """
                    QTableWidget, QTableView {
                        background-color: #EDF2F7;
                        alternate-background-color: #E2E8F0;
                        border: 1px solid #B4C2D3;
                        gridline-color: #B4C2D3;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                        font-size: 14px;
                        color: #2C3E50;
                    }
                    QHeaderView::section {
                        background-color: #C6D1E1;
                        color: #2C3E50;
                        padding: 4px 8px;
                        border: 1px solid #B4C2D3;
                        font-weight: 600;
                    }
                    QTableWidget::item, QTableView::item {
                        padding: 4px;
                        border-bottom: 1px solid #E2E8F0;
                    }
                    QTableWidget::item:hover, QTableView::item:hover {
                        background-color: #D8E1ED;
                    }
                    QTableWidget::item:selected, QTableView::item:selected {
                        background-color: #B8C7DB;
                        color: #2C3E50;
                    }
                """,
                'weekend': """
                    QTableWidget::item[weekend="true"], QTableView::item[weekend="true"] {
                        background-color: #E2E8F0;
                    }
                    QTableWidget::item[weekend="true"]:hover, QTableView::item[weekend="true"]:hover {
                        background-color: #D8E1ED;
                    }
                    QTableWidget::item[weekend="true"]:selected, QTableView::item[weekend="true"]:selected {
                        background-color: #CBD5E1;
                        color: #2C3E50;
                    }
                """
            },
            'combobox': """
                QComboBox {
                    background-color: #FFFFFF;
                    color: #2C3E50;
                    border: 1px solid #CBD5E1;
                    border-radius: 4px;
                    padding: 6px 8px;
                    min-height: 30px;
                    font-size: 14px;
                }
                QComboBox:hover {
                    border-color: #A0AEC0;
                }
                QComboBox:focus {
                    border: 2px solid #1A5A96;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 20px;
                    border-left: none;
                }
                QComboBox QAbstractItemView {
                    border: 1px solid #CBD5E1;
                    background-color: #FFFFFF;
                    selection-background-color: #D0E2F3;
                    selection-color: #2C3E50;
                }
            """,
            'checkbox': """
                QCheckBox {
                    spacing: 8px;
                    color: #2C3E50;
                    font-size: 14px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #FFFFFF;
                }
                QCheckBox::indicator:checked {
                    background-color: #1A5A96;
                    border-color: #1A5A96;
                    image: url(check.png);
                }
                QCheckBox::indicator:hover {
                    border-color: #1A5A96;
                }
            """,
            'tab': """
                QTabWidget::pane {
                    border: 1px solid #CBD5E1;
                    background-color: #FFFFFF;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #E2E8F0;
                    color: #505A64;
                    padding: 10px 16px;
                    border: 1px solid #CBD5E1;
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    min-width: 100px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    font-size: 14px;
                }
                QTabBar::tab:selected {
                    background-color: #1A5A96;
                    color: white;
                    font-weight: 600;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #D0E2F3;
                }
                QTabBar::tab:focus {
                    outline: none;
                    border: 2px solid #1A5A96;
                }
            """
        }
    
    def get_color(self, key, context=None, priority=None):
        """Get a color from the system with optional context and priority."""
        if context and priority:
            return self.colors.get(key, {}).get(priority, {}).get(context)
        elif context:
            return self.colors.get(key, {}).get(context)
        else:
            return self.colors.get(key)
    
    def get_post_group_colors(self):
        """Get colors for post groups."""
        return {
            'matin': QColor('#D0E2F3'),      # Bleu pâle
            'apresMidi': QColor('#F8D57E'),  # Jaune-orange
            'soirNuit': QColor('#E2D4ED')    # Violet pâle
        }
    
    def get_weekend_group_colors(self):
        """Get colors for weekend groups."""
        return {
            'gardes': QColor('#E2D4ED'),     # Violet pâle
            'visites': QColor('#D4EDDA'),    # Vert pâle
            'consultations': QColor('#D0E2F3') # Bleu pâle
        }
        
    def get_scaled_font_size(self, base_size=14, scale_factor=1.0):
        """
        Calcule une taille de police adaptative.
        Args:
            base_size: Taille de base en pixels
            scale_factor: Facteur d'échelle (1.0 = normal)
        Returns:
            Taille de police adaptée
        """
        return int(base_size * scale_factor)

class StyleConstants:
    """Constants for styling the application."""
    
    # Facteur d'échelle global basé sur la plateforme et la résolution
    PLATFORM = PlatformHelper.get_platform()
    DPI_SCALE = PlatformHelper.get_dpi_scale_factor()
    FONT_ADJUSTMENTS = PlatformHelper.get_platform_font_adjustments()
    
    # Facteur d'échelle combiné (plateforme + résolution)
    SCALE_FACTOR = DPI_SCALE
    
    # Espacement proportionnel à l'échelle
    SPACING = {
        'xxs': int(4 * SCALE_FACTOR),   # Extra extra small
        'xs': int(8 * SCALE_FACTOR),    # Extra small
        'sm': int(12 * SCALE_FACTOR),   # Small
        'md': int(16 * SCALE_FACTOR),   # Medium
        'lg': int(24 * SCALE_FACTOR),   # Large
        'xl': int(32 * SCALE_FACTOR),   # Extra large
        'xxl': int(48 * SCALE_FACTOR)   # Extra extra large
    }
    
    # Rayons de bordure proportionnels à l'échelle
    BORDER_RADIUS = {
        'xs': int(2 * SCALE_FACTOR),    # Extra small
        'sm': int(4 * SCALE_FACTOR),    # Small
        'md': int(6 * SCALE_FACTOR),    # Medium
        'lg': int(8 * SCALE_FACTOR),    # Large
        'xl': int(12 * SCALE_FACTOR)    # Extra large
    }
    
    # Polices adaptatives
    FONT = {
        'family': {
            'primary': '"Segoe UI", Roboto, Helvetica, Arial, sans-serif' if PLATFORM == 'Windows' else '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
            'secondary': '"Segoe UI", Arial, sans-serif'
        },
        'size': {
            'xs': f"{int(12 * SCALE_FACTOR * FONT_ADJUSTMENTS['base_size_factor'])}px",   # Extra small
            'sm': f"{int(14 * SCALE_FACTOR * FONT_ADJUSTMENTS['base_size_factor'])}px",   # Small
            'md': f"{int(16 * SCALE_FACTOR * FONT_ADJUSTMENTS['base_size_factor'])}px",   # Medium
            'lg': f"{int(18 * SCALE_FACTOR * FONT_ADJUSTMENTS['header_size_factor'])}px",   # Large
            'xl': f"{int(22 * SCALE_FACTOR * FONT_ADJUSTMENTS['header_size_factor'])}px"    # Extra large
        },
        'weight': {
            'light': 300,
            'regular': 400,
            'medium': 500,
            'bold': 600,
            'extra_bold': 700
        }
    }
    
    # Durées d'animation
    ANIMATION = {
        'fast': 150,    # Fast transitions
        'normal': 300,  # Normal transitions
        'slow': 500     # Slow transitions
    }
    
    # Ombres pour effet de profondeur
    SHADOWS = {
        'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
    }
    
    # Dimensions minimales des contrôles pour garantir l'accessibilité tactile
    CONTROL_SIZES = {
        'sm': {
            'height': int(24 * SCALE_FACTOR),
            'padding_h': int(8 * SCALE_FACTOR),
            'padding_v': int(4 * SCALE_FACTOR),
            'font_size': int(12 * SCALE_FACTOR)
        },
        'md': {
            'height': int(32 * SCALE_FACTOR),
            'padding_h': int(12 * SCALE_FACTOR),
            'padding_v': int(6 * SCALE_FACTOR),
            'font_size': int(14 * SCALE_FACTOR)
        },
        'lg': {
            'height': int(40 * SCALE_FACTOR),
            'padding_h': int(16 * SCALE_FACTOR),
            'padding_v': int(8 * SCALE_FACTOR),
            'font_size': int(16 * SCALE_FACTOR)
        }
    }
    
    # Dimensions de grille responsive
    GRID = {
        'columns': 12,
        'gutter': int(16 * SCALE_FACTOR),
        'margin': int(24 * SCALE_FACTOR)
    }

# Initialize color system
color_system = ColorSystem()

# Global styles - Adapté pour la compatibilité Windows
GLOBAL_STYLE = f"""
    QWidget {{
        font-family: {StyleConstants.FONT['family']['primary']};
        font-size: {StyleConstants.FONT['size']['sm']};
        color: #2C3E50;
        background-color: #F5F7FA;
    }}
    
    QPushButton {{
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        border: 1px solid #CBD5E1;
        background-color: #FFFFFF;
        min-height: {StyleConstants.CONTROL_SIZES['md']['height']}px;
    }}
    
    QPushButton:hover {{
        background-color: #EDF2F7;
        border-color: #A0AEC0;
    }}
    
    QPushButton:pressed {{
        background-color: #E2E8F0;
        border-color: #718096;
    }}
    
    QPushButton:disabled {{
        background-color: #EDF2F7;
        color: #A0AEC0;
        border-color: #E2E8F0;
    }}
    
    QLineEdit, QTextEdit {{
        padding: {StyleConstants.SPACING['xs']}px;
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        background-color: #FFFFFF;
        min-height: {StyleConstants.CONTROL_SIZES['md']['height']}px;
    }}
    
    QLineEdit:hover, QTextEdit:hover {{
        border-color: #A0AEC0;
    }}
    
    QLineEdit:focus, QTextEdit:focus {{
        border: 2px solid #1A5A96;
        outline: none;
    }}

    QSpinBox, QDateEdit, QTimeEdit {{
        padding: {StyleConstants.SPACING['xs']}px;
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        background-color: #FFFFFF;
        min-height: {StyleConstants.CONTROL_SIZES['md']['height']}px;
    }}

    QSpinBox:hover, QDateEdit:hover, QTimeEdit:hover {{
        border-color: #A0AEC0;
    }}

    QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {{
        border: 2px solid #1A5A96;
        outline: none;
    }}
    
    QSpinBox::up-button, QDateEdit::up-button, QTimeEdit::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: {StyleConstants.CONTROL_SIZES['md']['height'] // 2}px;
        border-left: 1px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
        border-top-right-radius: {StyleConstants.BORDER_RADIUS['xs']}px;
        background-color: #F5F7FA;
    }}
    
    QSpinBox::down-button, QDateEdit::down-button, QTimeEdit::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: {StyleConstants.CONTROL_SIZES['md']['height'] // 2}px;
        border-left: 1px solid #CBD5E1;
        border-top-right-radius: 0;
        border-bottom-right-radius: {StyleConstants.BORDER_RADIUS['xs']}px;
        background-color: #F5F7FA;
    }}

    QTableView, QTableWidget {{
        background-color: #EDF2F7;
        alternate-background-color: #E2E8F0;
        selection-background-color: #B8C7DB;
        selection-color: #2C3E50;
        border: 1px solid #B4C2D3;
        gridline-color: #B4C2D3;
    }}

    QHeaderView::section {{
        background-color: #C6D1E1;
        color: #2C3E50;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
        border: 1px solid #B4C2D3;
        font-weight: {StyleConstants.FONT['weight']['bold']};
    }}

    QTableView::item:hover, QTableWidget::item:hover {{
        background-color: #D8E1ED;
    }}
    
    QScrollBar:vertical {{
        border: none;
        background-color: #E2E8F0;
        width: {StyleConstants.SPACING['md']}px;
        margin: 0px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: #A0AEC0;
        min-height: {StyleConstants.SPACING['xl']}px;
        border-radius: {StyleConstants.SPACING['xs']}px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: #718096;
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        border: none;
        background-color: #E2E8F0;
        height: {StyleConstants.SPACING['md']}px;
        margin: 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: #A0AEC0;
        min-width: {StyleConstants.SPACING['xl']}px;
        border-radius: {StyleConstants.SPACING['xs']}px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: #718096;
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    QToolTip {{
        background-color: #2C3E50;
        color: white;
        border: none;
        padding: {StyleConstants.SPACING['xs']}px;
        opacity: 225;
    }}
    
    QGroupBox {{
        font-weight: bold;
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        margin-top: {StyleConstants.SPACING['xl']}px;
        padding-top: {StyleConstants.SPACING['xl']}px;
        background-color: #FFFFFF;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: {StyleConstants.SPACING['xs']}px;
        background-color: #FFFFFF;
        color: #1A5A96;
    }}
    
    /* Styles pour les écrans de haute résolution */
    @media (min-resolution: 120dpi) {{
        QWidget {{
            font-size: {int(int(StyleConstants.FONT['size']['sm'][:-2]) * 1.2)}px;
        }}
        QPushButton {{
            min-height: {int(StyleConstants.CONTROL_SIZES['md']['height'] * 1.2)}px;
            padding: {int(StyleConstants.SPACING['xs'] * 1.2)}px {int(StyleConstants.SPACING['md'] * 1.2)}px;
        }}
    }}
     """

# Style pour les arbres (QTreeWidget)
TREE_STYLE = f"""
    QTreeWidget {{
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        padding: {StyleConstants.SPACING['xs']}px;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QTreeWidget::item {{
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
        min-height: {StyleConstants.CONTROL_SIZES['sm']['height']}px;
    }}
    
    QTreeWidget::item:hover {{
        background-color: #E9EEF4;
    }}
    
    QTreeWidget::item:selected {{
        background-color: #D0E2F3;
        color: #2C3E50;
    }}
    
    QTreeWidget::branch:has-siblings:!adjoins-item {{
        border-image: url(vline.png) 0;
    }}
    
    QTreeWidget::branch:has-siblings:adjoins-item {{
        border-image: url(branch-more.png) 0;
    }}
    
    QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {{
        border-image: url(branch-end.png) 0;
    }}
    
    QTreeWidget::branch:has-children:!has-siblings:closed,
    QTreeWidget::branch:closed:has-children:has-siblings {{
        border-image: none;
        image: url(branch-closed.png);
    }}
    
    QTreeWidget::branch:open:has-children:!has-siblings,
    QTreeWidget::branch:open:has-children:has-siblings {{
        border-image: none;
        image: url(branch-open.png);
    }}
"""

# Style pour les splitters (séparateurs redimensionnables)
SPLITTER_STYLE = f"""
    QSplitter::handle {{
        background-color: #CBD5E1;
    }}
    
    QSplitter::handle:horizontal {{
        width: {StyleConstants.SPACING['xs']}px;
    }}
    
    QSplitter::handle:vertical {{
        height: {StyleConstants.SPACING['xs']}px;
    }}
    
    QSplitter::handle:hover {{
        background-color: #1A5A96;
    }}
"""

# Style pour les boutons radio
RADIO_BUTTON_STYLE = f"""
    QRadioButton {{
        spacing: {StyleConstants.SPACING['xs']}px;
        color: #2C3E50;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QRadioButton::indicator {{
        width: {StyleConstants.SPACING['md']}px;
        height: {StyleConstants.SPACING['md']}px;
        border: 1px solid #CBD5E1;
        border-radius: {int(StyleConstants.SPACING['md'] / 2)}px;
    }}
    
    QRadioButton::indicator:unchecked {{
        background-color: #FFFFFF;
    }}
    
    QRadioButton::indicator:checked {{
        background-color: #1A5A96;
        border-color: #1A5A96;
        image: url(radio_checked.png);
    }}
    
    QRadioButton::indicator:hover {{
        border-color: #1A5A96;
    }}
"""

# Style pour les listes (QListWidget)
LIST_STYLE = f"""
    QListWidget {{
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        padding: {StyleConstants.SPACING['xs']}px;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QListWidget::item {{
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['xs']}px;
        min-height: {StyleConstants.CONTROL_SIZES['sm']['height']}px;
    }}
    
    QListWidget::item:hover {{
        background-color: #E9EEF4;
    }}
    
    QListWidget::item:selected {{
        background-color: #D0E2F3;
        color: #2C3E50;
    }}
"""

# Style pour les messages d'information/statut
STATUS_BAR_STYLE = f"""
    QStatusBar {{
        background-color: #F5F7FA;
        color: #2C3E50;
        border-top: 1px solid #CBD5E1;
        font-size: {StyleConstants.FONT['size']['sm']};
        min-height: {StyleConstants.CONTROL_SIZES['sm']['height']}px;
    }}
"""

# Style pour les éléments de formulaire (layout de formulaire)
FORM_LAYOUT_STYLE = f"""
    QFormLayout {{
        spacing: {StyleConstants.SPACING['md']}px;
    }}
    
    QFormLayout QLabel {{
        font-weight: {StyleConstants.FONT['weight']['medium']};
        min-width: {StyleConstants.SPACING['xxl'] * 3}px;
    }}
    
    QFormLayout QLineEdit, QFormLayout QTextEdit, QFormLayout QComboBox, 
    QFormLayout QSpinBox, QFormLayout QDateEdit, QFormLayout QTimeEdit {{
        min-width: {StyleConstants.SPACING['xxl'] * 6}px;
    }}
"""

# Style pour les menus
MENU_STYLE = f"""
    QMenuBar {{
        background-color: #F5F7FA;
        color: #2C3E50;
        border-bottom: 1px solid #CBD5E1;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QMenuBar::item {{
        spacing: {StyleConstants.SPACING['sm']}px;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
        background: transparent;
    }}
    
    QMenuBar::item:selected {{
        background: #D0E2F3;
        border-radius: {StyleConstants.BORDER_RADIUS['xs']}px;
    }}
    
    QMenuBar::item:pressed {{
        background: #A9CCE3;
        border-radius: {StyleConstants.BORDER_RADIUS['xs']}px;
    }}
    
    QMenu {{
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        padding: {StyleConstants.SPACING['xs']}px 0;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QMenu::item {{
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['xl']}px;
        padding-right: {StyleConstants.SPACING['xxl']}px;
    }}
    
    QMenu::item:selected {{
        background-color: #D0E2F3;
    }}
    
    QMenu::separator {{
        height: 1px;
        background-color: #CBD5E1;
        margin: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
    }}
    
    QStatusBar::item {{
        border: none;
    }}
"""

# Style pour la barre de progression
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        background-color: #EDF2F7;
        text-align: center;
        min-height: {StyleConstants.CONTROL_SIZES['sm']['height']}px;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QProgressBar::chunk {{
        background-color: #1A5A96;
        border-radius: {int(StyleConstants.BORDER_RADIUS['xs'] * 1.5)}px;
    }}
"""

# Styles pour les messages d'alerte (succès, erreur, info)
ALERT_STYLES = {
    'success': f"""
        QFrame {{
            background-color: #D4EDDA;
            color: #155724;
            border: 1px solid #C3E6CB;
            border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
            padding: {StyleConstants.SPACING['sm']}px;
            font-size: {StyleConstants.FONT['size']['sm']};
        }}
    """,
    'error': f"""
        QFrame {{
            background-color: #F8D7DA;
            color: #721C24;
            border: 1px solid #F5C6CB;
            border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
            padding: {StyleConstants.SPACING['sm']}px;
            font-size: {StyleConstants.FONT['size']['sm']};
        }}
    """,
    'warning': f"""
        QFrame {{
            background-color: #FFF3CD;
            color: #856404;
            border: 1px solid #FFEEBA;
            border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
            padding: {StyleConstants.SPACING['sm']}px;
            font-size: {StyleConstants.FONT['size']['sm']};
        }}
    """,
    'info': f"""
        QFrame {{
            background-color: #D1ECF1;
            color: #0C5460;
            border: 1px solid #BEE5EB;
            border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
            padding: {StyleConstants.SPACING['sm']}px;
            font-size: {StyleConstants.FONT['size']['sm']};
        }}
    """
}

# Style spécifique pour les tableaux de desiderata
DESIDERATA_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: #EDF2F7;
        alternate-background-color: #E2E8F0;
        border: 1px solid #B4C2D3;
        gridline-color: #B4C2D3;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QHeaderView::section {{
        background-color: #C6D1E1;
        color: #2C3E50;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
        border: 1px solid #B4C2D3;
        font-weight: {StyleConstants.FONT['weight']['bold']};
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QTableWidget::item[primary="true"][weekend="false"] {{
        background-color: #FFD4D4;
    }}
    
    QTableWidget::item[primary="true"][weekend="true"] {{
        background-color: #FFA8A8;
    }}
    
    QTableWidget::item[secondary="true"][weekend="false"] {{
        background-color: #D4E4FF;
    }}
    
    QTableWidget::item[secondary="true"][weekend="true"] {{
        background-color: #A8C8FF;
    }}
    
    QTableWidget::item[disabled="true"] {{
        background-color: #E2E8F0;
        color: #A0AEC0;
    }}
    
    QTableWidget::item:selected[primary="true"] {{
        background-color: #F5B7B1;
        color: #2C3E50;
    }}
    
    QTableWidget::item:selected[secondary="true"] {{
        background-color: #A9CCE3;
        color: #2C3E50;
    }}
    
    QTableWidget::item:hover[primary="true"] {{
        background-color: #F8BBB6;
    }}
    
    QTableWidget::item:hover[secondary="true"] {{
        background-color: #AED6F1;
    }}
"""

# Style pour les fenêtres modales/dialogues
DIALOG_STYLE = f"""
    QDialog {{
        background-color: #F5F7FA;
        border: 1px solid #CBD5E1;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
    }}
    
    QDialog QLabel {{
        color: #2C3E50;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QDialog QPushButton {{
        min-width: {StyleConstants.SPACING['xxl']}px;
    }}
    
    QDialog QLineEdit, QDialog QTextEdit, QDialog QComboBox {{
        min-width: {int(StyleConstants.SPACING['xxl'] * 5)}px;
    }}
"""

# Style pour les boutons d'action secondaire
SECONDARY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: #FFFFFF;
        color: #505A64;
        border: 1px solid #CBD5E1;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        font-weight: {StyleConstants.FONT['weight']['medium']};
        min-height: {StyleConstants.CONTROL_SIZES['md']['height']}px;
        font-size: {StyleConstants.FONT['size']['sm']};
    }}
    
    QPushButton:hover {{
        background-color: #EDF2F7;
        border-color: #A0AEC0;
    }}
    
    QPushButton:pressed {{
        background-color: #E2E8F0;
        border-color: #718096;
    }}
    
    QPushButton:disabled {{
        background-color: #EDF2F7;
        color: #A0AEC0;
        border-color: #E2E8F0;
    }}
"""

# Style pour les labels de titre
TITLE_LABEL_STYLE = f"""
    QLabel {{
        color: #1A5A96;
        font-size: {StyleConstants.FONT['size']['lg']};
        font-weight: {StyleConstants.FONT['weight']['bold']};
        padding: {StyleConstants.SPACING['xs']}px 0;
    }}
"""

# Style pour les boutons d'icône
ICON_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: transparent;
        border: none;
        padding: {StyleConstants.SPACING['xs']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
    }}
    
    QPushButton:hover {{
        background-color: #EDF2F7;
    }}
    
    QPushButton:pressed {{
        background-color: #E2E8F0;
    }}
    
    QPushButton:disabled {{
        opacity: 0.5;
    }}
"""

# Edit/Delete button style (danger actions)
EDIT_DELETE_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: #FFFFFF;
        color: #D73F3F;
        border: 1px solid #D73F3F;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
        min-height: 30px;
        font-size: 14px;
    }}
    
    QPushButton:hover {{
        background-color: rgba(215, 63, 63, 0.1);
    }}
    
    QPushButton:pressed {{
        background-color: rgba(215, 63, 63, 0.2);
    }}
    
    QPushButton:disabled {{
        background-color: #FFFFFF;
        color: #A0AEC0;
        border-color: #A0AEC0;
    }}
"""

# Action button style (primary actions)
ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: #1A5A96;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
        min-height: 30px;
        font-size: 14px;
    }}
    
    QPushButton:hover {{
        background-color: #1467A8;
    }}
    
    QPushButton:pressed {{
        background-color: #0E4875;
    }}
    
    QPushButton:disabled {{
        background-color: #A0AEC0;
        color: white;
        opacity: 0.7;
    }}
"""

# Add button style (success actions)
ADD_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: #2E8540;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
        min-height: 30px;
        font-size: 14px;
    }}
    
    QPushButton:hover {{
        background-color: #267638;
    }}
    
    QPushButton:pressed {{
        background-color: #1E622D;
    }}
    
    QPushButton:disabled {{
        background-color: #A0AEC0;
        color: white;
        opacity: 0.7;
    }}
"""