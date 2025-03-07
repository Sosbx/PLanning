# © 2024 HILAL Arkane. Tous droits réservés.
# gui/Interface/Settings/settings_applier.py

from PyQt6.QtWidgets import QApplication, QWidget, QTableWidget
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import QObject, Qt, pyqtSignal

from gui.styles import color_system, PlatformHelper
from gui.Interface.Settings.settings_manager import SettingsManager

class SettingsApplier(QObject):
    """
    Classe responsable d'appliquer les paramètres utilisateur à l'application.
    Modifie l'apparence de l'interface utilisateur en fonction des préférences.
    """
    # Signal émis lorsque les paramètres sont appliqués
    settings_applied = pyqtSignal(dict)
    
    def __init__(self, app, settings_manager=None, parent=None):
        """
        Initialise l'appliqueur de paramètres.
        
        Args:
            app: L'instance QApplication
            settings_manager: L'instance de SettingsManager
            parent: Le widget parent
        """
        super().__init__(parent)
        self.app = app
        self.settings_manager = settings_manager or SettingsManager()
        
        # Connecter le signal de changement de paramètres
        self.settings_manager.settings_changed.connect(self.apply_settings)
        
        # Garder une trace des paramètres actuels
        self.current_settings = self.settings_manager.get_all_settings()
        
    def apply_settings(self, settings=None):
        """
        Applique les paramètres à l'interface utilisateur.
        
        Args:
            settings: Les paramètres à appliquer (utilise les paramètres actuels si None)
        """
        if settings is None:
            settings = self.settings_manager.get_all_settings()
            
        # Sauvegarder les paramètres actuels
        self.current_settings = settings
            
        print("Applying settings:", settings)  # Debug info
            
        # Récupérer les paramètres
        ui_settings = settings.get('ui', {})
        table_settings = settings.get('tables', {})
        color_settings = settings.get('custom_colors', {})
        advanced_settings = settings.get('advanced_colors', {})
        
        # 1. Appliquer les facteurs aux paramètres de PlatformHelper
        self._apply_platform_adjustments(ui_settings)
        
        # 2. Appliquer les couleurs personnalisées si activées
        if color_settings.get('enabled', False):
            self._apply_custom_colors(color_settings)
            
        # 3. Appliquer les couleurs avancées si activées
        if advanced_settings.get('enabled', False):
            self._apply_advanced_colors(advanced_settings)
            
        # 4. Appliquer les paramètres de police globaux
        self._apply_font_settings(ui_settings)
        
        # 5. Appliquer les paramètres spécifiques aux tableaux (stockés pour utilisation ultérieure)
        self._store_table_settings(table_settings)
        
        # 6. Forcer la mise à jour de l'interface
        self._refresh_ui()
        
        # 7. Émettre le signal que les paramètres ont été appliqués
        self.settings_applied.emit(settings)
        
        print("Settings applied successfully")  # Debug info
    
    def _apply_platform_adjustments(self, ui_settings):
        """
        Applique les facteurs d'ajustement aux paramètres de plateforme.
        Modifie directement les valeurs retournées par PlatformHelper et force
        le recalcul des couleurs existantes.
        """
        # Créer une méthode de remplacement pour get_platform_color_adjustments
        original_color_adjustments = PlatformHelper.get_platform_color_adjustments
        
        def custom_color_adjustments():
            # Obtenir les ajustements de base de la plateforme
            adjustments = original_color_adjustments()
            
            # Appliquer les facteurs personnalisés
            adjustments['color_saturation_factor'] *= ui_settings.get('saturation_factor', 1.0)
            adjustments['color_value_factor'] *= ui_settings.get('brightness_factor', 1.0)
            
            # Ajouter le facteur de contraste (non présent par défaut)
            adjustments['color_contrast_factor'] = ui_settings.get('contrast_factor', 1.0)
            
            return adjustments
        
        # Remplacer temporairement la méthode
        PlatformHelper.get_platform_color_adjustments = staticmethod(custom_color_adjustments)
        
        # Créer une méthode de remplacement pour adjust_color_for_platform
        original_adjust_color = PlatformHelper.adjust_color_for_platform
        
        def custom_adjust_color(color):
            # Obtenir les ajustements de couleur
            adjustments = PlatformHelper.get_platform_color_adjustments()
            
            # Récupérer le facteur de contraste
            contrast_factor = adjustments.get('color_contrast_factor', 1.0)
            
            # Ajuster la couleur avec la méthode d'origine
            adjusted_color = original_adjust_color(color)
            
            # Appliquer le contraste avec limites de sécurité
            if contrast_factor != 1.0:
                h, s, l, a = adjusted_color.getHslF()
                
                # Limiter le facteur de contraste pour éviter les valeurs extrêmes
                safe_contrast = min(1.5, max(0.5, contrast_factor))
                
                # Le contraste modifie la distance entre la luminosité et 0.5
                if l > 0.5:
                    # Couleurs claires deviennent plus claires (avec limite)
                    l = 0.5 + (l - 0.5) * safe_contrast
                    # Plafonner à 0.95 pour éviter le blanc pur
                    l = min(0.95, l)
                else:
                    # Couleurs sombres deviennent plus sombres (avec limite)
                    l = 0.5 - (0.5 - l) * safe_contrast
                    # Limiter à 0.05 pour éviter le noir pur
                    l = max(0.05, l)
                
                # Limiter la luminosité entre 0 et 1
                l = max(0.0, min(1.0, l))
                
                # Créer la couleur contrastée
                adjusted_color.setHslF(h, s, l, a)
            
            return adjusted_color
        
        # Remplacer temporairement la méthode
        PlatformHelper.adjust_color_for_platform = staticmethod(custom_adjust_color)
        
        # Forcer le recalcul de toutes les couleurs existantes
        color_system.recalculate_colors()
    
    def _apply_custom_colors(self, color_settings):
        """
        Applique les couleurs personnalisées au système de couleurs 
        et force leur mise à jour dans les composants.
        """
        print("Applying custom colors:", color_settings)  # Debug
        
        # Utiliser la classe ColorSystem pour modifier les couleurs
        from gui.styles import color_system
        
        # Sauvegarde des couleurs originales si nécessaire
        if not hasattr(self, 'original_colors'):
            self.original_colors = {
                'primary': color_system.colors.get('primary', QColor('#1A5A96')),
                'secondary': color_system.colors.get('secondary', QColor('#505A64')),
                'weekend': color_system.colors.get('weekend', QColor('#E2E8F0')),
                'weekday': color_system.colors.get('weekday', QColor('#FFFFFF'))
            }
        
        # Appliquer les couleurs personnalisées ou restaurer les originales
        for color_name in ['primary', 'secondary', 'weekend', 'weekday']:
            color_hex = color_settings.get(color_name, '')
            if color_settings.get('enabled', False) and color_hex:
                # Appliquer la couleur personnalisée en utilisant la méthode set_color
                # qui émet un signal de changement
                print(f"Setting {color_name} to {color_hex}")
                new_color = QColor(color_hex)
                color_system.set_color(color_name, new_color)
            else:
                # Restaurer la couleur originale
                if hasattr(self, 'original_colors') and color_name in self.original_colors:
                    color_system.set_color(color_name, self.original_colors[color_name])
        
        # Mise à jour des couleurs dans tous les tableaux
        self._update_all_table_colors()
        
    def _apply_advanced_colors(self, advanced_settings):
        """
        Applique les couleurs avancées spécifiques pour les désidératas, 
        statistiques et autres éléments spécialisés.
        """
        print("Applying advanced colors:", advanced_settings)  # Debug
        
        from gui.styles import color_system
        
        # Sauvegarde des couleurs avancées originales si nécessaire
        if not hasattr(self, 'original_advanced_colors'):
            self.original_advanced_colors = {
                # Couleurs des désidératas
                'desiderata_primary_normal': color_system.colors.get('desiderata', {}).get('primary', {}).get('normal', QColor('#FFD4D4')),
                'desiderata_primary_weekend': color_system.colors.get('desiderata', {}).get('primary', {}).get('weekend', QColor('#FFA8A8')),
                'desiderata_secondary_normal': color_system.colors.get('desiderata', {}).get('secondary', {}).get('normal', QColor('#D4E4FF')),
                'desiderata_secondary_weekend': color_system.colors.get('desiderata', {}).get('secondary', {}).get('weekend', QColor('#A8C8FF')),
                
                # Couleurs des types de postes
                'post_type_consultation': color_system.colors.get('post_types', {}).get('consultation', QColor('#D0E2F3')),
                'post_type_visite': color_system.colors.get('post_types', {}).get('visite', QColor('#D4EDDA')),
                'post_type_garde': color_system.colors.get('post_types', {}).get('garde', QColor('#E2D4ED')),
                
                # Couleurs des statistiques
                'stats_under_min': QColor('#28a745'),  # Vert pour les valeurs sous le minimum
                'stats_over_max': QColor('#dc3545')  # Rouge pour les valeurs au-dessus du maximum
            }
        
        if advanced_settings.get('enabled', False):
            # Appliquer les couleurs des désidératas en utilisant set_color pour émettre les signaux
            if 'desiderata_primary_normal' in advanced_settings:
                color = QColor(advanced_settings['desiderata_primary_normal'])
                color_system.set_color('desiderata.primary.normal', color)
                
            if 'desiderata_primary_weekend' in advanced_settings:
                color = QColor(advanced_settings['desiderata_primary_weekend'])
                color_system.set_color('desiderata.primary.weekend', color)
                
            if 'desiderata_secondary_normal' in advanced_settings:
                color = QColor(advanced_settings['desiderata_secondary_normal'])
                color_system.set_color('desiderata.secondary.normal', color)
                
            if 'desiderata_secondary_weekend' in advanced_settings:
                color = QColor(advanced_settings['desiderata_secondary_weekend'])
                color_system.set_color('desiderata.secondary.weekend', color)
            
            # Appliquer les couleurs des types de postes en utilisant set_color
            if 'post_type_consultation' in advanced_settings:
                color = QColor(advanced_settings['post_type_consultation'])
                color_system.set_color('post_types.consultation', color)
                
            if 'post_type_visite' in advanced_settings:
                color = QColor(advanced_settings['post_type_visite'])
                color_system.set_color('post_types.visite', color)
                
            if 'post_type_garde' in advanced_settings:
                color = QColor(advanced_settings['post_type_garde'])
                color_system.set_color('post_types.garde', color)
            
            # Stocker les couleurs des statistiques pour les intervalles
            # Ces couleurs sont utilisées pour colorer les cellules des tableaux de statistiques
            # en fonction des intervalles min/max
            if 'stats_under_min' in advanced_settings:
                self.stats_under_min_color = QColor(advanced_settings['stats_under_min'])
            else:
                self.stats_under_min_color = self.original_advanced_colors['stats_under_min']
                
            if 'stats_over_max' in advanced_settings:
                self.stats_over_max_color = QColor(advanced_settings['stats_over_max'])
            else:
                self.stats_over_max_color = self.original_advanced_colors['stats_over_max']
        else:
            # Restaurer les couleurs originales en utilisant set_color pour émettre les signaux
            if hasattr(self, 'original_advanced_colors'):
                # Restaurer les couleurs des désidératas
                color_system.set_color('desiderata.primary.normal', self.original_advanced_colors['desiderata_primary_normal'])
                color_system.set_color('desiderata.primary.weekend', self.original_advanced_colors['desiderata_primary_weekend'])
                color_system.set_color('desiderata.secondary.normal', self.original_advanced_colors['desiderata_secondary_normal'])
                color_system.set_color('desiderata.secondary.weekend', self.original_advanced_colors['desiderata_secondary_weekend'])
                
                # Restaurer les couleurs des types de postes
                color_system.set_color('post_types.consultation', self.original_advanced_colors['post_type_consultation'])
                color_system.set_color('post_types.visite', self.original_advanced_colors['post_type_visite'])
                color_system.set_color('post_types.garde', self.original_advanced_colors['post_type_garde'])
                
                # Restaurer les couleurs des statistiques
                self.stats_under_min_color = self.original_advanced_colors['stats_under_min']
                self.stats_over_max_color = self.original_advanced_colors['stats_over_max']
        
        # Mettre à jour les couleurs dans les composants de désidératas
        self._update_all_desiderata_components()
        
        # Mettre à jour les couleurs dans les composants de statistiques
        self._update_all_stats_components()

    def _update_all_stats_components(self):
        """
        Met à jour les couleurs dans tous les composants de statistiques
        """
        # Rechercher tous les composants de statistiques
        from gui.Repartition.stats_view import StatsView
        
        for stats_view in self.app.findChildren(StatsView):
            try:
                # Mettre à jour les couleurs des intervalles
                if hasattr(self, 'stats_under_min_color') and hasattr(self, 'stats_over_max_color'):
                    # Définir les couleurs d'intervalle
                    stats_view.interval_colors = {
                        'under_min': self.stats_under_min_color,  # Sous le minimum (vert)
                        'over_max': self.stats_over_max_color   # Au-dessus du maximum (rouge)
                    }
                    
                    # Forcer la mise à jour des tableaux
                    if hasattr(stats_view, 'update_stats'):
                        stats_view.update_stats()
                    else:
                        # Forcer la mise à jour des tableaux individuellement
                        for table in [stats_view.stats_table, stats_view.weekend_stats_table, 
                                    stats_view.detailed_stats_table, stats_view.weekly_stats_table, 
                                    stats_view.weekday_group_stats_table]:
                            if table:
                                table.update()
                
            except Exception as e:
                print(f"Error updating stats view: {str(e)}")
                import traceback
                print(traceback.format_exc())

    def _update_all_desiderata_components(self):
        """
        Met à jour les couleurs dans tous les composants de désidératas
        """
        # Rechercher tous les calendriers de désidératas
        from gui.Desiderata.desiderata_management import DesiderataCalendarWidget
        
        for calendar in self.app.findChildren(DesiderataCalendarWidget):
            try:
                # Mettre à jour les couleurs dans le calendrier
                desiderata_colors = {
                    'base': {
                        'normal': color_system.colors['weekday'],
                        'weekend': color_system.colors['weekend']
                    },
                    'primary': {
                        'normal': color_system.colors['desiderata']['primary']['normal'],
                        'weekend': color_system.colors['desiderata']['primary']['weekend']
                    },
                    'secondary': {
                        'normal': color_system.colors['desiderata']['secondary']['normal'],
                        'weekend': color_system.colors['desiderata']['secondary']['weekend']
                    }
                }
                calendar.set_colors(desiderata_colors)
                
                # Forcer le redessinage du calendrier
                calendar.store_selections()
                calendar.populate_days()
                calendar.restore_selections()
                calendar.update()
                
            except Exception as e:
                print(f"Error updating desiderata calendar: {str(e)}")

    def _update_all_table_colors(self):
        """Met à jour les couleurs dans tous les tableaux de l'application"""
        from gui.components.planning_table_component import PlanningTableComponent
        
        # Obtenir les couleurs standardisées
        standard_colors = PlanningTableComponent.get_standard_colors()
        
        # Appliquer à tous les tableaux
        for table in self.app.findChildren(PlanningTableComponent):
            try:
                print(f"Updating colors for table: {table.objectName()}")
                
                # Stocker la sélection actuelle si possible
                if hasattr(table, 'store_selections'):
                    table.store_selections()
                
                # Appliquer les nouvelles couleurs
                table.set_colors(standard_colors)
                
                # Repeupler le tableau si possible
                if hasattr(table, 'populate_days'):
                    table.populate_days()
                
                # Restaurer la sélection si possible
                if hasattr(table, 'restore_selections'):
                    table.restore_selections()
                
                # Forcer la mise à jour du tableau
                table.update()
                
            except Exception as e:
                print(f"Error updating table colors: {str(e)}")


    
    def _apply_font_settings(self, ui_settings):
        """
        Applique les paramètres de police à l'application.
        """
        font_size_factor = ui_settings.get('font_size_factor', 1.0)
        print(f"Applying font size factor: {font_size_factor}")  # Debug info
        
        # Obtenir la police actuelle de l'application
        current_font = self.app.font()
        
        # Calculer la nouvelle taille (s'assurer qu'elle est différente)
        base_size = 9  # Taille de base typique
        new_size = max(8, int(base_size * font_size_factor))
        print(f"Changing font size from {current_font.pointSize()} to {new_size}")
        
        # Créer et appliquer la nouvelle police
        new_font = QFont(current_font)
        new_font.setPointSize(new_size)
        self.app.setFont(new_font)
        
        # Cette partie est cruciale - appliquer la police à tous les widgets existants
        for widget in self.app.allWidgets():
            # Ne pas appliquer aux widgets qui ont déjà une police personnalisée
            if not widget.property("customFont"):
                widget_font = widget.font()
                widget_font.setPointSize(new_size)
                widget.setFont(widget_font)
            
            # Force update des tableaux
            if isinstance(widget, QTableWidget):
                # Forcer une mise à jour des dimensions
                widget.resizeColumnsToContents()
                widget.resizeRowsToContents()
        
        print(f"Font size updated to {new_size}")  # Debug info
    
    def _store_table_settings(self, table_settings):
        """
        Stocke les paramètres des tableaux pour utilisation ultérieure.
        """
        # Ces paramètres seront utilisés par PlanningTableComponent
        self.table_font_size_factor = table_settings.get('font_size_factor', 1.0)
        self.row_height_factor = table_settings.get('row_height_factor', 1.0)
        self.column_width_factor = table_settings.get('column_width_factor', 1.0)
    
    def _refresh_ui(self):
        """
        Force la mise à jour complète de l'interface utilisateur.
        """
        print("Starting UI refresh...")  # Debug info
        
        # 1. Forcer la mise à jour du style global
        self.app.style().unpolish(self.app)
        self.app.style().polish(self.app)
        
        # 2. Mettre à jour la palette de l'application
        from gui.styles import color_system
        palette = self.app.palette()
        palette.setColor(QPalette.ColorRole.Window, color_system.get_color('window_background'))
        palette.setColor(QPalette.ColorRole.WindowText, color_system.get_color('text', 'primary'))
        palette.setColor(QPalette.ColorRole.Base, color_system.get_color('weekday'))
        palette.setColor(QPalette.ColorRole.AlternateBase, color_system.get_color('weekend'))
        palette.setColor(QPalette.ColorRole.ToolTipBase, color_system.get_color('dark'))
        palette.setColor(QPalette.ColorRole.ToolTipText, color_system.get_color('light'))
        palette.setColor(QPalette.ColorRole.Text, color_system.get_color('text', 'primary'))
        palette.setColor(QPalette.ColorRole.Button, color_system.get_color('container', 'background'))
        palette.setColor(QPalette.ColorRole.ButtonText, color_system.get_color('text', 'primary'))
        palette.setColor(QPalette.ColorRole.Highlight, color_system.get_color('primary'))
        palette.setColor(QPalette.ColorRole.HighlightedText, color_system.get_color('text', 'light'))
        self.app.setPalette(palette)
        
        # 3. Synchroniser les couleurs de tous les tableaux
        from gui.components.planning_table_component import PlanningTableComponent
        if hasattr(PlanningTableComponent, 'sync_colors_with_system'):
            PlanningTableComponent.sync_colors_with_system()
        
        # 4. Mettre à jour les couleurs dans les composants de désidératas
        self._update_all_desiderata_components()
        
        # 5. Mettre à jour les couleurs dans tous les tableaux
        self._update_all_table_colors()
        
        # 6. Mettre à jour les couleurs dans les composants de statistiques
        self._update_all_stats_components()
        
        # 7. Parcourir tous les widgets de niveau supérieur
        for widget in self.app.topLevelWidgets():
            # Forcer la mise à jour de ce widget
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
            
            # Mettre à jour récursivement tous les enfants
            self._update_widget_recursive(widget)
        
        # 8. Forcer le rafraîchissement de tous les widgets
        for widget in self.app.allWidgets():
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
            
            # Forcer la mise à jour des dimensions pour les tableaux
            if isinstance(widget, QTableWidget):
                widget.resizeColumnsToContents()
                widget.resizeRowsToContents()
        
        # 9. Envoyer un événement ApplicationLayoutChanged pour forcer une mise à jour globale
        for window in self.app.topLevelWidgets():
            from PyQt6.QtCore import QEvent
            custom_event = QEvent(QEvent.Type.LayoutRequest)
            self.app.sendEvent(window, custom_event)
        
        print("UI refresh completed")  # Debug info
    
    def _update_widget_recursive(self, widget):
        """
        Met à jour récursivement un widget et tous ses enfants.
        """
        # Mettre à jour le style
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
        
        # Mettre à jour tous les enfants
        for child in widget.children():
            if isinstance(child, QWidget):
                self._update_widget_recursive(child)
    
    def get_table_settings(self):
        """
        Retourne les paramètres des tableaux.
        Utilisée par PlanningTableComponent pour ajuster ses dimensions.
        
        Returns:
            dict: Les paramètres des tableaux
        """
        return {
            'font_size_factor': getattr(self, 'table_font_size_factor', 1.0),
            'row_height_factor': getattr(self, 'row_height_factor', 1.0),
            'column_width_factor': getattr(self, 'column_width_factor', 1.0)
        }
        
    def get_advanced_color(self, category, name, default=None):
        """
        Récupère une couleur avancée des paramètres
        
        Args:
            category: Catégorie de la couleur (desiderata, post_type, stats)
            name: Nom de la couleur
            default: Valeur par défaut si non trouvée
            
        Returns:
            QColor: La couleur demandée ou la valeur par défaut
        """
        advanced_settings = self.current_settings.get('advanced_colors', {})
        color_name = f"{category}_{name}"
        
        if not advanced_settings.get('enabled', False):
            # Utiliser les couleurs par défaut du système
            if category == 'desiderata':
                if name == 'primary_normal':
                    return color_system.colors['desiderata']['primary']['normal']
                elif name == 'primary_weekend':
                    return color_system.colors['desiderata']['primary']['weekend']
                elif name == 'secondary_normal':
                    return color_system.colors['desiderata']['secondary']['normal']
                elif name == 'secondary_weekend':
                    return color_system.colors['desiderata']['secondary']['weekend']
            elif category == 'post_type':
                return color_system.colors.get('post_types', {}).get(name, QColor(default) if default else QColor("#CCCCCC"))
            elif category == 'stats':
                # Utiliser les couleurs d'intervalle stockées
                if name == 'under_min' and hasattr(self, 'stats_under_min_color'):
                    return self.stats_under_min_color
                elif name == 'over_max' and hasattr(self, 'stats_over_max_color'):
                    return self.stats_over_max_color
                else:
                    defaults = {
                        'under_min': QColor('#28a745'),
                        'over_max': QColor('#dc3545')
                    }
                    return defaults.get(name, QColor(default) if default else QColor("#CCCCCC"))
        else:
            # Utiliser les couleurs personnalisées
            if color_name in advanced_settings:
                return QColor(advanced_settings[color_name])
        
        # Retourner la valeur par défaut
        return QColor(default) if default else QColor("#CCCCCC")
