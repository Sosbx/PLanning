# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

import sys
import platform
from PyQt6.QtGui import QColor, QGuiApplication, QScreen, QBrush
from PyQt6.QtCore import QOperatingSystemVersion, QSysInfo, Qt, QObject, pyqtSignal

class PlatformHelper:
    """
    Classe utilitaire pour gérer les spécificités des différentes plateformes
    """
    
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
            # Sur Windows, réduire davantage les tailles de police
            return {
                'base_size_factor': 0.8,     # Réduction plus importante (0.8 au lieu de 0.9)
                'header_size_factor': 0.75,  # Réduction plus importante (0.75 au lieu de 0.85)
                'period_size_factor': 0.8,   # Réduction plus importante (0.8 au lieu de 0.9)
                'weekday_size_factor': 0.8   # Réduction plus importante (0.8 au lieu de 0.9)
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
                'base_size_factor': 0.9,    # Légère réduction
                'header_size_factor': 0.85,
                'period_size_factor': 0.9,
                'weekday_size_factor': 0.9
            }
    
    @staticmethod
    def get_platform_color_adjustments():
        """Retourne les ajustements de couleur spécifiques à la plateforme."""
        platform = PlatformHelper.get_platform()
        if platform == 'Windows':
            # Sur Windows, assombrir légèrement les couleurs et augmenter le contraste
            return {
                'color_saturation_factor': 1.1,   # Saturation modérée
                'color_value_factor': 0.9,        # Plus sombre (0.9 au lieu de 1.05)
                'force_explicit_colors': True
            }
        elif platform == 'macOS':
            # Pour macOS, couleurs légèrement moins saturées pour correspondre au style
            return {
                'color_saturation_factor': 0.95,
                'color_value_factor': 1.0,
                'force_explicit_colors': False
            }
        else:
            # Pour Linux et autres plateformes
            return {
                'color_saturation_factor': 1.0,
                'color_value_factor': 1.0,
                'force_explicit_colors': True  # True pour Linux aussi pour garantir la cohérence
            }

    @staticmethod
    def adjust_color_for_platform(color):
        """
        Ajuste une couleur pour la plateforme actuelle avec un meilleur contrôle
        du contraste et de la luminosité.
        """
        # Obtenir les ajustements pour la plateforme actuelle
        adjustments = PlatformHelper.get_platform_color_adjustments()
        
        # Si nous n'avons pas besoin d'ajuster la couleur, la retourner telle quelle
        if (adjustments['color_saturation_factor'] == 1.0 and 
            adjustments['color_value_factor'] == 1.0 and 
            not adjustments['force_explicit_colors']):
            return color
        
        # Convertir en HSV pour des ajustements plus précis
        h, s, v, a = color.getHsvF()
        
        # Ajuster la saturation
        s = min(1.0, s * adjustments['color_saturation_factor'])
        
        # Ajuster la luminosité/valeur
        v = min(1.0, v * adjustments['color_value_factor'])
        
        # Créer une nouvelle couleur avec les paramètres ajustés
        adjusted_color = QColor()
        adjusted_color.setHsvF(h, s, v, a)
        
        # Pour Windows, s'assurer que les couleurs sont suffisamment contrastées
        platform = PlatformHelper.get_platform()
        if platform == 'Windows':
            # Correction spéciale pour la couleur de weekend - assurer qu'elle est grise et non bleue
            # Au lieu d'importer color_system (qui crée une dépendance circulaire),
            # vérifier directement si la couleur correspond à la couleur de weekend (#E2E8F0)
            if color.name().upper() == "#E2E8F0":
                # Forcer une teinte grise pour le weekend
                grey_color = QColor(230, 230, 235)  # Gris légèrement bleuté
                return grey_color
        
        return adjusted_color

    @staticmethod
    def apply_background_color(item, color):
        """
        Applique une couleur de fond à un élément de manière compatible avec toutes les plateformes.
        Version améliorée pour Windows.
        
        Args:
            item: L'élément de tableau (QTableWidgetItem) auquel appliquer la couleur
            color: La couleur à appliquer (QColor)
        """
        if not item:
            return
            
        platform = PlatformHelper.get_platform()
        brush = QBrush(color)
        
        # Sur Windows, appliquer toutes les méthodes possibles
        if platform == 'Windows':
            # Méthode 1: setData avec BackgroundRole (recommandé)
            item.setData(Qt.ItemDataRole.BackgroundRole, brush)
            
            # Méthode 2: setBackground (toujours utiliser)
            item.setBackground(brush)
            
            # Méthode 3: définir un style personnalisé
            style = f"background-color: {color.name()};"
            item.setData(Qt.ItemDataRole.UserRole + 1, style)
            
            # Méthode 4: définir des propriétés pour les styles QSS
            if hasattr(item, 'setProperty'):
                item.setProperty("customBgColor", color.name())
        else:
            # Sur macOS et Linux, utiliser la méthode standard
            item.setBackground(brush)
    
    @staticmethod
    def apply_foreground_color(item, color):
        """
        Applique une couleur de texte à un élément de manière compatible avec toutes les plateformes.
        Version améliorée pour Windows.
        
        Args:
            item: L'élément de tableau (QTableWidgetItem) auquel appliquer la couleur
            color: La couleur à appliquer (QColor)
        """
        if not item:
            return
            
        platform = PlatformHelper.get_platform()
        brush = QBrush(color)
        
        # Sur Windows, appliquer toutes les méthodes possibles
        if platform == 'Windows':
            # Méthode 1: setData avec ForegroundRole (recommandé)
            item.setData(Qt.ItemDataRole.ForegroundRole, brush)
            
            # Méthode 2: setForeground (toujours utiliser)
            item.setForeground(brush)
            
            # Méthode 3: définir un style personnalisé
            style = f"color: {color.name()};"
            current_style = item.data(Qt.ItemDataRole.UserRole + 1) or ""
            item.setData(Qt.ItemDataRole.UserRole + 1, current_style + style)
            
            # Méthode 4: définir des propriétés pour les styles QSS
            if hasattr(item, 'setProperty'):
                item.setProperty("customFgColor", color.name())
        else:
            # Sur macOS et Linux, utiliser la méthode standard
            item.setForeground(brush)
            
    @staticmethod
    def ensure_widget_style_updated(widget):
        """
        S'assure qu'un widget met à jour son style, spécialement important sur Windows.
        
        Args:
            widget: Le widget à mettre à jour
        """
        if PlatformHelper.get_platform() == 'Windows':
            # Forcer la mise à jour du style sur Windows
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

# Classe de notification pour les changements de couleur
class ColorNotifier(QObject):
    """Classe pour notifier les changements de couleur dans le système"""
    color_changed = pyqtSignal(str, QColor)  # Signal émis lorsqu'une couleur change (nom, nouvelle_couleur)
    colors_reset = pyqtSignal()  # Signal émis lorsque toutes les couleurs sont réinitialisées

class ColorSystem(QObject):
    def __init__(self):
        super().__init__()
        # Créer le notificateur de couleur
        self.notifier = ColorNotifier()
        
        # Stocker les couleurs de base (non ajustées)
        self.base_colors = {
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
        self.text_colors = {
            'primary': QColor('#2C3E50'),    # Texte principal
            'secondary': QColor('#505A64'),  # Texte secondaire
            'light': QColor('#FFFFFF'),      # Texte clair
            'dark': QColor('#1A1A1A'),       # Texte foncé
            'disabled': QColor('#A0AEC0')    # Texte désactivé
        }
        
        # Couleurs de conteneur
        self.container_colors = {
            'background': QColor('#FFFFFF'), # Fond de conteneur
            'border': QColor('#CBD5E1'),     # Bordure de conteneur
            'hover': QColor('#E9EEF4'),      # Effet de survol
            'disabled': QColor('#EDF2F7')    # Conteneur désactivé
        }
        
        # Couleurs de tableau
        self.table_colors = {
            'header': QColor('#C6D1E1'),     # En-tête de tableau
            'border': QColor('#B4C2D3'),     # Bordure de tableau
            'hover': QColor('#D8E1ED'),      # Ligne survolée
            'selected': QColor('#B8C7DB'),   # Ligne sélectionnée
            'alternate': QColor('#E2E8F0'),  # Ligne alternée
            'background': QColor('#EDF2F7')  # Fond de tableau
        }
        
        # Couleurs de focus
        self.focus_colors = {
            'outline': QColor('#1A5A96')     # Contour de focus
        }
        
        # Couleurs de desiderata
        self.desiderata_colors = {
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
        self.post_type_colors = {
            'consultation': QColor('#D0E2F3'),  # Bleu pâle pour consultations
            'visite': QColor('#D4EDDA'),        # Vert pâle pour visites
            'garde': QColor('#E2D4ED')          # Violet pâle pour gardes
        }
        
        # Couleurs pour les cartes de la landing page
        self.card_colors = {
            'planning': QColor('#E3F2FD'),
            'personnel': QColor('#E8F5E9'),
            'desiderata': QColor('#FFF8E1'),
            'doctor_planning': QColor('#F3E5F5'),
            'statistics': QColor('#E1F5FE'),
            'comparison': QColor('#E0F2F1'),
            'export': QColor('#F1F8E9')
        }
        
        # Initialiser les couleurs ajustées
        self.colors = {}
        
        # Appliquer les ajustements initiaux
        self._apply_adjustments()
        
        # Sauvegarder les couleurs originales pour pouvoir les restaurer
        self.original_colors = self.colors.copy()
    
    def initialize_standard_colors(self):
        """
        Initialise toutes les couleurs standard du système.
        Cette fonction doit être appelée au démarrage de l'application.
        """
        # S'assurer que toutes les couleurs de désidératas existent
        if 'desiderata' not in self.colors:
            self.colors['desiderata'] = {}
        
        if 'primary' not in self.colors['desiderata']:
            self.colors['desiderata']['primary'] = {}
        
        if 'secondary' not in self.colors['desiderata']:
            self.colors['desiderata']['secondary'] = {}
        
        # Assigner les couleurs par défaut si elles n'existent pas
        if 'normal' not in self.colors['desiderata']['primary']:
            self.colors['desiderata']['primary']['normal'] = QColor('#FFD4D4')  # Rouge clair
        
        if 'weekend' not in self.colors['desiderata']['primary']:
            self.colors['desiderata']['primary']['weekend'] = QColor('#FFA8A8')  # Rouge plus foncé
        
        if 'normal' not in self.colors['desiderata']['secondary']:
            self.colors['desiderata']['secondary']['normal'] = QColor('#D4E4FF')  # Bleu clair
        
        if 'weekend' not in self.colors['desiderata']['secondary']:
            self.colors['desiderata']['secondary']['weekend'] = QColor('#A8C8FF')  # Bleu plus foncé

        
    def _apply_adjustments(self):
        """
        Applique les ajustements de couleur spécifiques à la plateforme à toutes les couleurs.
        Cette méthode est appelée lors de l'initialisation et lorsque les paramètres changent.
        """
        # Appliquer les ajustements aux couleurs de base
        self.colors = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.base_colors.items()}
        
        # Ajouter les dictionnaires de couleurs imbriqués avec ajustements
        self.colors['text'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.text_colors.items()}
        self.colors['container'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.container_colors.items()}
        self.colors['table'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.table_colors.items()}
        self.colors['focus'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.focus_colors.items()}
        self.colors['card'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.card_colors.items()}
        
        # Traiter les couleurs de desiderata (structure imbriquée à deux niveaux)
        self.colors['desiderata'] = {}
        for priority, contexts in self.desiderata_colors.items():
            self.colors['desiderata'][priority] = {}
            for context, color in contexts.items():
                self.colors['desiderata'][priority][context] = PlatformHelper.adjust_color_for_platform(color)
        
        # Ajouter les couleurs des types de postes
        self.colors['post_types'] = {k: PlatformHelper.adjust_color_for_platform(v) for k, v in self.post_type_colors.items()}
        
    def set_color(self, key, color, emit_signal=True):
        """
        Définit une couleur dans le système et émet un signal de changement
        
        Args:
            key (str): Clé de la couleur à modifier (peut être imbriquée avec des points, ex: 'desiderata.primary.normal')
            color (QColor): Nouvelle couleur
            emit_signal (bool): Si True, émet un signal de changement
        """
        # Créer une nouvelle instance de QColor pour éviter les références partagées
        new_color = QColor(color)
        
        if key in self.colors:
            # Cas simple: clé directe
            self.colors[key] = new_color
            
            # Émettre le signal de changement si demandé
            if emit_signal:
                self.notifier.color_changed.emit(key, new_color)
            
            return True
        elif '.' in key:
            # Gestion des clés composées comme "card.planning" ou "desiderata.primary.normal"
            parts = key.split('.')
            
            # Cas avec 2 niveaux (ex: "card.planning")
            if len(parts) == 2:
                main_key, sub_key = parts
                if main_key in self.colors and isinstance(self.colors[main_key], dict) and sub_key in self.colors[main_key]:
                    self.colors[main_key][sub_key] = new_color
                    
                    # Émettre le signal de changement
                    if emit_signal:
                        self.notifier.color_changed.emit(key, new_color)
                    
                    return True
            
            # Cas avec 3 niveaux (ex: "desiderata.primary.normal")
            elif len(parts) == 3:
                main_key, mid_key, sub_key = parts
                if (main_key in self.colors and 
                    isinstance(self.colors[main_key], dict) and 
                    mid_key in self.colors[main_key] and 
                    isinstance(self.colors[main_key][mid_key], dict) and 
                    sub_key in self.colors[main_key][mid_key]):
                    
                    self.colors[main_key][mid_key][sub_key] = new_color
                    
                    # Émettre le signal de changement
                    if emit_signal:
                        self.notifier.color_changed.emit(key, new_color)
                    
                    return True
        
        print(f"Avertissement: Impossible de définir la couleur pour la clé '{key}'")
        return False
        
    def get_color(self, key, context=None, priority=None):
        """
        Récupère une couleur du système avec contexte et priorité optionnels.
        Méthode robuste qui gère les clés manquantes en retournant une couleur par défaut.
        
        Args:
            key (str): Clé principale de la couleur
            context (str, optional): Sous-clé de contexte
            priority (str, optional): Sous-clé de priorité
            
        Returns:
            QColor: La couleur demandée ou une couleur par défaut (#CCCCCC) si non trouvée
        """
        default_color = QColor('#CCCCCC')  # Gris par défaut en cas de clé non trouvée
        
        if context and priority:
            return self.colors.get(key, {}).get(priority, {}).get(context, default_color)
        elif context:
            return self.colors.get(key, {}).get(context, default_color)
        elif key in self.colors:
            return self.colors.get(key, default_color)
        elif '.' in key:
            # Gestion des clés composées comme "card.planning"
            main_key, sub_key = key.split('.', 1)
            return self.colors.get(main_key, {}).get(sub_key, default_color)
        else:
            return default_color
            
    def get_hex_color(self, key, context=None, priority=None):
        """
        Récupère une couleur au format hexadécimal (#RRGGBB)
        """
        color = self.get_color(key, context, priority)
        return color.name()
        
    def get_rgba_color(self, key, context=None, priority=None, alpha=255):
        """
        Récupère une couleur avec canal alpha spécifié
        """
        color = self.get_color(key, context, priority)
        color.setAlpha(alpha)
        return color
    
    def get_post_group_colors(self):
        """Get colors for post groups."""
        return {
            'matin': self.get_color('post_types', 'consultation'),  # Utilise la couleur de consultation (bleu)
            'apresMidi': self.get_color('warning'),                 # Utilise la couleur d'avertissement (jaune-orange)
            'soirNuit': self.get_color('post_types', 'garde')       # Utilise la couleur de garde (violet)
        }
    
    def get_weekend_group_colors(self):
        """Get colors for weekend groups."""
        return {
            'gardes': self.get_color('post_types', 'garde'),         # Violet pâle
            'visites': self.get_color('post_types', 'visite'),       # Vert pâle
            'consultations': self.get_color('post_types', 'consultation') # Bleu pâle
        }
    
    def get_card_color_by_index(self, index):
        """
        Récupère la couleur d'une carte selon son index
        Utile pour la landing page
        """
        card_types = ['planning', 'personnel', 'desiderata', 'doctor_planning', 
                      'statistics', 'comparison', 'export']
        if 0 <= index < len(card_types):
            return self.get_color('card', card_types[index])
        return self.get_color('container', 'background')  # Couleur par défaut
        
    def recalculate_colors(self):
        """
        Recalcule toutes les couleurs avec les paramètres actuels.
        Cette méthode doit être appelée lorsque les paramètres de couleur changent.
        """
        # Sauvegarder les couleurs personnalisées actuelles
        custom_colors = {}
        for key in ['primary', 'secondary', 'weekend', 'weekday']:
            if key in self.colors:
                custom_colors[key] = self.colors[key]
        
        # Réappliquer les ajustements
        self._apply_adjustments()
        
        # Restaurer les couleurs personnalisées
        for key, color in custom_colors.items():
            self.colors[key] = color
        
        # Émettre un signal pour chaque couleur modifiée
        for key in self.colors:
            if isinstance(self.colors[key], dict):
                for subkey, color in self.colors[key].items():
                    if isinstance(color, dict):
                        for subsubkey, subcolor in color.items():
                            self.notifier.color_changed.emit(f"{key}.{subkey}.{subsubkey}", subcolor)
                    else:
                        self.notifier.color_changed.emit(f"{key}.{subkey}", color)
            else:
                self.notifier.color_changed.emit(key, self.colors[key])
    
    def reset_colors(self):
        """Réinitialise toutes les couleurs à leurs valeurs par défaut"""
        # Réappliquer les ajustements aux couleurs de base
        self._apply_adjustments()
        
        # Émettre le signal de réinitialisation
        self.notifier.colors_reset.emit()
        
        # Émettre un signal pour chaque couleur modifiée
        for key in self.colors:
            if isinstance(self.colors[key], dict):
                for subkey, color in self.colors[key].items():
                    if isinstance(color, dict):
                        for subsubkey, subcolor in color.items():
                            self.notifier.color_changed.emit(f"{key}.{subkey}.{subsubkey}", subcolor)
                    else:
                        self.notifier.color_changed.emit(f"{key}.{subkey}", color)
            else:
                self.notifier.color_changed.emit(key, self.colors[key])

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
