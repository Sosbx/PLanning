# © 2024 HILAL Arkane. Tous droits réservés.
# .gui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QMessageBox, QMenu
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QIcon, QAction, QFont

from PyQt6.QtCore import pyqtSignal
from ..Gestion.personnel_management import PersonnelManagementWidget
from .planning_view import PlanningViewWidget
from ..Desiderata.desiderata_management import DesiderataManagementWidget
from ..Gestion.post_configuration import PostConfigurationWidget
from core.Constantes.data_persistence import DataPersistence
from ..Repartition.stats_view import StatsView
from ..Attributions.doctor_planning_view import DoctorPlanningView
from ..Echanges.planning_comparison_view import PlanningComparisonView
from ..Repartition.detached_stats_window import DetachedStatsWindow
from .planning_management import PlanningManagementWidget
from core.utils import resource_path
from ..styles import color_system, GLOBAL_STYLE, ACTION_BUTTON_STYLE, StyleConstants
from core.Constantes.constraints import PlanningConstraints
from core.post_attribution_handler import PostAttributionHandler
from gui.Attributions.post_attribution_history_dialog import PostAttributionHistoryDialog
from gui.Interface.Settings.settings_view import SettingsDialog
from gui.Interface.Settings.settings_manager import SettingsManager
from gui.Interface.Settings.settings_applier import SettingsApplier

import logging
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    # Signal pour retourner à la page d'accuei
     # Ajouter un signal pour indiquer le retour à la landing page
    return_to_landing = pyqtSignal()
    def __init__(self, doctors, cats, post_configuration, pre_attributions=None):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.pre_attributions = pre_attributions or {}
        self.data_persistence = DataPersistence()
        self.detached_stats_window = None
        self.planning_constraints = PlanningConstraints()
        self.planning = None  # Sera initialisé lors de la création du planning
        
        # Initialiser le gestionnaire de post-attribution
        self.post_attribution_handler = PostAttributionHandler(self)
        
        # Application du style global
        self.setStyleSheet(GLOBAL_STYLE)
        
        self.init_ui()
        self.planning_tab.dates_changed.connect(self.on_planning_dates_changed)

    def init_ui(self):
        self.setWindowTitle('Planificateur SOS Médecins')
        self.setGeometry(100, 100, 1200, 800)

        self.tab_widget = QTabWidget()
        self.tab_widget.setIconSize(QSize(32, 32))
        self.setCentralWidget(self.tab_widget)
        
        # Initialiser le gestionnaire de post-attribution
        self.post_attribution_handler = PostAttributionHandler(self)
        
        # Création du menu et de la barre d'outils
        self.create_menu_bar()
        self.create_toolbar()
        
        # Ajouter l'onglet Accueil (icône maison) en premier avec une icône plus petite
        home_widget = QWidget()  # Widget vide pour l'onglet Accueil
        self.home_index = self.tab_widget.addTab(home_widget, self.create_tab_icon("icons/home.png", size=24), "")
        
        
        # Style des onglets avec les nouvelles constantes
        self.tab_widget.setStyleSheet(f"""
            QTabBar::tab:first {{
                min-width: 50px;  /* Largeur minimale réduite pour l'onglet accueil */
                max-width: 50px;  /* Largeur maximale réduite pour l'onglet accueil */
            }}
            QTabWidget::pane {{
                border: 1px solid {color_system.colors['container']['border'].name()};
                background-color: {color_system.colors['container']['background'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
            }}
            QTabBar::tab {{
                background-color: {color_system.colors['table']['header'].name()};
                color: {color_system.colors['text']['primary'].name()};
                padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-bottom: none;
                border-top-left-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                border-top-right-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                min-width: 100px;
                font-family: {StyleConstants.FONT['family']['primary']};
                font-size: {StyleConstants.FONT['size']['md']};
            }}
            QTabBar::tab:selected {{
                background-color: {color_system.colors['primary'].name()};
                color: {color_system.colors['text']['light'].name()};
                font-weight: {StyleConstants.FONT['weight']['medium']};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {color_system.colors['table']['hover'].name()};
            }}
            QTabBar::tab:focus {{
                outline: none;
                border: 2px solid {color_system.colors['focus']['outline'].name()};
            }}
        """)

        # Connecter le changement d'onglet à la fonction de retour à l'accueil
        self.tab_widget.currentChanged.connect(self.handle_tab_change)
        
        # Initialisation des onglets
        self._init_personnel_tab()
        self._init_desiderata_tab()
        self._init_planning_tab()
        self._init_doctor_planning_tab()
        self.create_menu_bar()
        self._init_stats_tab()
        self._init_comparison_tab()
        self._init_export_tab()

    def _init_planning_tab(self):
        """Initialise l'onglet Planning"""
        self.planning_tab = PlanningViewWidget(self.doctors, self.cats, 
                                            self.post_configuration, self,
                                            pre_attributions=self.pre_attributions)
        self.planning = self.planning_tab.planning  # Récupérer l'instance de Planning
        
        self.tab_widget.addTab(self.planning_tab, 
                            self.create_tab_icon("icons/planning.png"), "Planning")

    def handle_tab_change(self, index):
        """Gère le changement d'onglet"""
        # Si l'onglet Accueil est sélectionné, retourner à la landing page
        if index == self.home_index:
            # Réinitialiser l'index à un autre onglet pour éviter de rester sur l'onglet Accueil
            self.tab_widget.setCurrentIndex(1)  # Sélectionner le deuxième onglet
            # Retourner à la landing page
            self.return_to_landing_page()

    # Méthode pour le retour à la landing page
    def return_to_landing_page(self):
        """Émet le signal pour retourner à la landing page"""
        print("Retour à la landing page demandé")
        self.return_to_landing.emit()
    def _init_personnel_tab(self):
        """Initialise l'onglet Gestion du personnel"""
        self.personnel_tab = PersonnelManagementWidget(self.doctors, self.cats,
                                                     self.post_configuration, self)
        self.tab_widget.addTab(self.personnel_tab,
                             self.create_tab_icon("icons/personnel.png"), 
                             "Gestion du personnel")

    def create_tab_icon(self, icon_path, size=32):
        """Crée une icône pour un onglet"""
        return QIcon(resource_path(icon_path))

    def detach_stats(self):
        """Détache la vue des statistiques"""
        if not self.detached_stats_window:
            self.tab_widget.removeTab(self.stats_index)
            self.detached_stats_window = DetachedStatsWindow(self)
            self.detached_stats_window.show()
            self.update_stats_view()

    def reattach_stats(self):
        """Rattache la vue des statistiques"""
        if self.detached_stats_window:
            self.detached_stats_window.close()
            self.detached_stats_window = None
            
            # Recréation du conteneur des stats
            stats_container = QWidget()
            stats_layout = QVBoxLayout(stats_container)
            stats_layout.setContentsMargins(
                StyleConstants.SPACING['md'],
                StyleConstants.SPACING['md'],
                StyleConstants.SPACING['md'],
                StyleConstants.SPACING['md']
            )
            stats_layout.setSpacing(StyleConstants.SPACING['md'])
            
            stats_layout.addWidget(self.stats_tab)
            
            # Bouton de détachement
            detach_button = QPushButton("Détacher les statistiques")
            detach_button.setStyleSheet(ACTION_BUTTON_STYLE)
            detach_button.clicked.connect(self.detach_stats)
            detach_button.setMinimumHeight(StyleConstants.SPACING['xl'])
            stats_layout.addWidget(detach_button, 0, Qt.AlignmentFlag.AlignRight)
            
            self.stats_index = self.tab_widget.insertTab(self.stats_index, 
                                                        stats_container,
                                                        "Statistiques")
            self.tab_widget.setCurrentIndex(self.stats_index)
            self.update_stats_view()

    def update_data(self):
        """Met à jour toutes les données de l'application"""
        self.personnel_tab.update_tables()
        self.planning_tab.update_data(self.doctors, self.cats, 
                                    self.post_configuration)
        
        if hasattr(self.planning_tab, 'planning') and self.planning_tab.planning:
            self.planning = self.planning_tab.planning  # Mettre à jour l'instance de Planning
            start_date = self.planning.start_date
            end_date = self.planning.end_date
            
            # Mettre à jour les dates dans PlanningViewWidget
            self.planning_tab.start_date.setDate(QDate(start_date))
            self.planning_tab.end_date.setDate(QDate(end_date))
            
            # Mettre à jour les dates dans DesiderataManagementWidget
            self.desiderata_tab.sync_dates_from_planning(start_date, end_date)
            
            self.update_stats_view()
            self.comparison_view.planning = self.planning_tab.planning
            self.comparison_view.update_comparison(preserve_selection=True)
            
            self.doctor_planning_view.main_window = self  # Assurer que main_window est défini
            self.doctor_planning_view.planning = self.planning_tab.planning
            self.doctor_planning_view.update_table()
        else:
            # Réinitialiser les vues si aucun planning n'est chargé
            self.stats_tab.clear_stats()
            self.comparison_view.reset_view()
            self.doctor_planning_view.clear_view()

        self.desiderata_tab.update_stats()
        self.personnel_tab.post_config_tab.update_configuration(self.post_configuration)

    def save_data(self):
        """Sauvegarde les données"""
        self.data_persistence.save_data(self.doctors, self.cats, 
                                      self.post_configuration)
        self.planning_management_tab.update_planning_list()

    def _init_desiderata_tab(self):
        """Initialise l'onglet Gestion des desiderata"""
        # Use default dates since planning tab isn't initialized yet
        default_start = QDate.currentDate()
        default_end = default_start.addMonths(6)
        
        self.desiderata_tab = DesiderataManagementWidget(
            self.doctors, 
            self.cats, 
            default_start.toPyDate(),
            default_end.toPyDate(),
            self
        )
        self.tab_widget.addTab(
            self.desiderata_tab,
            self.create_tab_icon("icons/desiderata.png"),
            "Gestion des desiderata"
        )

    def _init_doctor_planning_tab(self):
        """Initialise l'onglet Planning par médecin"""
        self.doctor_planning_view = DoctorPlanningView(None, self.doctors, self.cats)
        
        # Ajouter cette ligne pour définir la référence vers main_window
        self.doctor_planning_view.main_window = self
        
        self.tab_widget.addTab(
            self.doctor_planning_view,
            self.create_tab_icon("icons/doctor_planning.png"),
            "Planning par médecin"
        )
        
    def load_post_attributions(self):
        """Charge les post-attributions après la génération du planning."""
        if self.planning and hasattr(self, 'post_attribution_handler'):
            self.post_attribution_handler.load_post_attributions()

    def _init_stats_tab(self):
        """Initialise l'onglet Statistiques"""
        self.stats_tab = StatsView(doctors=self.doctors, cats=self.cats)
        self.stats_tab.set_parent_window(self)
        
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md']
        )
        stats_layout.setSpacing(StyleConstants.SPACING['md'])
        
        stats_layout.addWidget(self.stats_tab)
        
        detach_button = QPushButton("Détacher les statistiques")
        detach_button.setStyleSheet(ACTION_BUTTON_STYLE)
        detach_button.clicked.connect(self.detach_stats)
        detach_button.setMinimumHeight(StyleConstants.SPACING['xl'])
        stats_layout.addWidget(detach_button, 0, Qt.AlignmentFlag.AlignRight)
        
        self.stats_index = self.tab_widget.addTab(
            stats_container,
            self.create_tab_icon("icons/statistics.png"),
            "Statistiques"
        )

    def _init_comparison_tab(self):
        """Initialise l'onglet Comparaison des plannings"""
        self.comparison_view = PlanningComparisonView(None, self.doctors, self.cats, self)
        self.tab_widget.addTab(
            self.comparison_view,
            self.create_tab_icon("icons/comparaison.png"),
            "Echanges"
        )

    def _init_export_tab(self):
        """Initialise l'onglet Exporter"""
        self.planning_management_tab = PlanningManagementWidget(self)
        self.tab_widget.addTab(
            self.planning_management_tab,
            self.create_tab_icon("icons/export.png"),
            "Exporter"
        )

    def on_planning_dates_changed(self, start_date, end_date):
        self.desiderata_tab.sync_dates_from_planning(start_date, end_date)

    def closeEvent(self, event):
        # Sauvegarder les données principales
        self.data_persistence.save_data(self.doctors, self.cats, self.post_configuration)
        
        # Sauvegarder les pré-attributions si elles existent
        if hasattr(self.planning_tab, 'pre_attribution_widget'):
            pre_attributions = self.planning_tab.pre_attribution_widget.pre_attributions
            try:
                self.data_persistence.save_pre_attributions(pre_attributions)
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde des pré-attributions: {e}")
        
        # Sauvegarder les post-attributions
        if hasattr(self, 'post_attribution_handler'):
            try:
                self.post_attribution_handler.load_post_attributions()
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde des post-attributions: {e}")
        
        event.accept()
        
    def create_menu_bar(self):
        """Crée la barre de menu principale"""
        menu_bar = self.menuBar()
        
        # Menu Fichier
        file_menu = menu_bar.addMenu("&Fichier")
        
        # Action Enregistrer données
        save_data_action = QAction("&Enregistrer données", self)
        save_data_action.setShortcut("Ctrl+S")
        save_data_action.triggered.connect(self.save_data)
        file_menu.addAction(save_data_action)
        
        file_menu.addSeparator()
        
        # Action Exporter Planning
        export_action = QAction("&Exporter planning", self)
        export_action.setShortcut("Ctrl+E")
        # Connecter à une méthode d'export si elle existe
        if hasattr(self, 'export_planning'):
            export_action.triggered.connect(self.export_planning)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Action Quitter
        exit_action = QAction("&Quitter", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Édition
        edit_menu = menu_bar.addMenu("&Édition")
        
        # Action Préférences
        preferences_action = QAction("&Paramètres d'affichage...", self)
        preferences_action.setShortcut("Ctrl+P")
        preferences_action.triggered.connect(self.show_settings_dialog)
        edit_menu.addAction(preferences_action)
        
        # Menu Aide
        help_menu = menu_bar.addMenu("&Aide")
        
        # Action À propos
        about_action = QAction("À &propos", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        """Affiche une boîte de dialogue 'À propos'"""
        QMessageBox.about(self, "À propos de MedHora",
                        "MedHora - Planification médicale\n\n"
                        "© 2024 HILAL Arkane. Tous droits réservés.\n\n"
                        "Version 1.0")

    def create_toolbar(self):
        """Crée la barre d'outils principale"""
        # Créer la barre d'outils
        toolbar = self.addToolBar("Barre d'outils principale")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        
        # Ajouter un bouton pour retourner à la landing page si le signal existe
        if hasattr(self, 'return_to_landing'):
            home_action = QAction("Accueil", self)
            home_action.triggered.connect(self.on_return_to_landing)
            toolbar.addAction(home_action)
        
        # Bouton Paramètres
        settings_action = QAction("Paramètres d'affichage", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        toolbar.addAction(settings_action)
        
        # Ajouter un séparateur
        toolbar.addSeparator()

    def on_return_to_landing(self):
        """Fonction pour retourner à la landing page"""
        if hasattr(self, 'return_to_landing'):
            self.return_to_landing.emit()

    def show_settings_dialog(self):
        """Affiche la boîte de dialogue des paramètres"""
        # Vérifier si le gestionnaire de paramètres est disponible
        if not hasattr(self, 'settings_manager'):
            self.settings_manager = SettingsManager()
        
        if not hasattr(self, 'settings_dialog') or self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self.settings_manager, self)
            self.settings_dialog.settings_applied.connect(self.refresh_widgets_after_settings)
        
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def on_settings_applied(self):
        """Gère l'application des nouveaux paramètres à tous les composants du logiciel"""
        print("MainWindow: Settings applied signal received")  # Debug
        
        # 1. Obtenir les paramètres actuels
        settings = self.settings_manager.get_all_settings()
        table_settings = settings.get('tables', {})
        
        # 2. Extraire les facteurs d'ajustement
        font_factor = table_settings.get('font_size_factor', 1.0)
        row_factor = table_settings.get('row_height_factor', 1.0)
        col_factor = table_settings.get('column_width_factor', 1.0)
        
        print(f"Applying table settings: font={font_factor}, row={row_factor}, col={col_factor}")
        
        # 3. Mettre à jour tous les composants PlanningTableComponent dans l'application
        self._update_all_planning_tables(font_factor, row_factor, col_factor)
        
        # 4. Forcer la mise à jour de l'interface
        self.repaint()
        
        print("MainWindow: Settings propagated to all components")

    def _update_all_planning_tables(self, font_factor, row_factor, col_factor):
        """Met à jour toutes les instances de PlanningTableComponent dans l'application"""
        # Planning principal
        if hasattr(self, 'planning_tab') and hasattr(self.planning_tab, 'table'):
            print("Updating planning_tab.table")
            self._update_table(self.planning_tab.table, font_factor, row_factor, col_factor)
        
        # Vue par médecin
        if hasattr(self, 'doctor_planning_view') and hasattr(self.doctor_planning_view, 'table'):
            print("Updating doctor_planning_view.table")
            self._update_table(self.doctor_planning_view.table, font_factor, row_factor, col_factor)
        
        # Vue de comparaison
        if hasattr(self, 'planning_comparison_view'):
            if hasattr(self.planning_comparison_view, 'table1'):
                print("Updating planning_comparison_view.table1")
                self._update_table(self.planning_comparison_view.table1, font_factor, row_factor, col_factor)
            if hasattr(self.planning_comparison_view, 'table2'):
                print("Updating planning_comparison_view.table2")
                self._update_table(self.planning_comparison_view.table2, font_factor, row_factor, col_factor)
        
        # Rechercher récursivement d'autres tableaux
        from gui.components.planning_table_component import PlanningTableComponent
        for table in self.findChildren(PlanningTableComponent):
            print(f"Found additional table: {table.objectName()}")
            self._update_table(table, font_factor, row_factor, col_factor)

    def _update_table(self, table, font_factor, row_factor, col_factor):
        """Met à jour un tableau spécifique avec les nouveaux paramètres"""
        try:
            # 1. Mettre à jour les tailles de police
            base_size = int(12 * font_factor)
            header_size = int(14 * font_factor)
            weekday_size = int(10 * font_factor)
            
            table.set_font_settings(
                base_size=base_size,
                header_size=header_size,
                weekday_size=weekday_size
            )
            
            # 2. Mettre à jour les hauteurs de ligne
            min_height = int(table.min_row_height * row_factor)
            max_height = int(table.max_row_height * row_factor)
            table.set_min_row_height(min_height)
            table.set_max_row_height(max_height)
            
            # 3. Mettre à jour les largeurs de colonne
            min_day = int(table.min_col_widths["day"] * col_factor)
            min_weekday = int(table.min_col_widths["weekday"] * col_factor)
            min_period = int(table.min_col_widths["period"] * col_factor)
            
            max_day = int(table.max_col_widths["day"] * col_factor)
            max_weekday = int(table.max_col_widths["weekday"] * col_factor)
            max_period = int(table.max_col_widths["period"] * col_factor)
            
            table.set_min_column_widths(
                day_width=min_day,
                weekday_width=min_weekday,
                period_width=min_period
            )
            
            table.set_max_column_widths(
                day_width=max_day,
                weekday_width=max_weekday,
                period_width=max_period
            )
            
            # 4. Réoptimiser les dimensions
            table.optimize_dimensions()
            
            print(f"Table updated with font={base_size}, rows={min_height}-{max_height}, cols={min_day}/{min_weekday}/{min_period}")
        except Exception as e:
            print(f"Error updating table: {str(e)}")
        
    def show_post_attribution_history(self):
        """Affiche l'historique des post-attributions"""
        dialog = PostAttributionHistoryDialog(self.post_attribution_handler, self)
        dialog.exec()


    def save_post_configuration(self, new_post_configuration):
        """Sauvegarde la configuration des postes sans mettre à jour le planning"""
        try:
            self.post_configuration = new_post_configuration
            self.personnel_tab.post_config_tab.update_configuration(new_post_configuration)
            self.data_persistence.save_data(self.doctors, self.cats, self.post_configuration)
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de la configuration : {e}", exc_info=True)
            return False

    def update_planning_with_configuration(self):
        """Met à jour le planning avec la configuration actuelle"""
        try:
            self.planning_tab.update_post_configuration(self.post_configuration)
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour du planning : {e}", exc_info=True)
            return False

    def update_stats_view(self):
        if self.detached_stats_window:
            self.detached_stats_window.update_stats()
        else:
            self.stats_tab.update_stats(self.planning_tab.planning, self.doctors, self.cats)

    def reset_all_views(self):
        # Réinitialiser la vue de comparaison
        self.comparison_view.reset_view()
        
        # Réinitialiser la vue des statistiques
        self.stats_tab.clear_stats()
        
        # Réinitialiser la vue du planning par médecin
        self.doctor_planning_view.clear_view()
        
        # Créer un planning vide
        from core.Constantes.models import Planning
        from datetime import date
        today = date.today()
        self.planning = Planning(today, today)
        
        # Mettre à jour les autres vues si nécessaire
        self.update_data()

    def refresh_widgets_after_settings(self):
        """
        Met à jour tous les widgets après un changement de paramètres.
        Cette méthode est appelée quand les paramètres sont modifiés.
        """
        print("Rafraîchissement des widgets après changement de paramètres")
        
        # 1. Mise à jour des paramètres de tableau
        settings = self.settings_manager.get_all_settings()
        table_settings = settings.get('tables', {})
        
        # Extraire les facteurs d'ajustement
        font_factor = table_settings.get('font_size_factor', 1.0)
        row_factor = table_settings.get('row_height_factor', 1.0)
        col_factor = table_settings.get('column_width_factor', 1.0)
        
        # Mettre à jour tous les tableaux
        self._update_all_planning_tables(font_factor, row_factor, col_factor)
        
        # 2. Mettre à jour les désidératas si l'onglet existe
        if hasattr(self, 'desiderata_tab') and self.desiderata_tab:
            # Forcer une mise à jour du calendrier des désidératas
            self.desiderata_tab.update_calendar()
            self.desiderata_tab.update_stats()
            
        # 3. Mettre à jour le planning principal si l'onglet existe
        if hasattr(self, 'planning_tab') and self.planning_tab:
            # Forcer une mise à jour du calendrier de planning
            if hasattr(self.planning_tab, 'refresh_planning'):
                self.planning_tab.refresh_planning()
                
        # 4. Mettre à jour la vue par médecin si l'onglet existe
        if hasattr(self, 'doctor_planning_view') and self.doctor_planning_view:
            self.doctor_planning_view.update_table()
            
        # 5. Mettre à jour la vue de comparaison si l'onglet existe
        if hasattr(self, 'comparison_view') and self.comparison_view:
            self.comparison_view.update_comparison(preserve_selection=True)
            
        # 6. Mettre à jour les statistiques si l'onglet existe
        if hasattr(self, 'stats_tab') and self.stats_tab:
            self.update_stats_view()
        
        # 7. Mettre à jour toute l'interface pour refléter les nouvelles couleurs
        from gui.styles import color_system, PlatformHelper
        
        # Forcer la mise à jour de tous les widgets visibles
        for widget in self.findChildren(QWidget):
            if widget.isVisible():
                PlatformHelper.ensure_widget_style_updated(widget)
        
        # Forcer une mise à jour visuelle de la fenêtre entière
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()