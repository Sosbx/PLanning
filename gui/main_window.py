# © 2024 HILAL Arkane. Tous droits réservés.
# .gui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QIcon
from .personnel_management import PersonnelManagementWidget
from .planning_view import PlanningViewWidget
from .desiderata_management import DesiderataManagementWidget
from .post_configuration import PostConfigurationWidget
from core.Constantes.data_persistence import DataPersistence
from .stats_view import StatsView
from .doctor_planning_view import DoctorPlanningView
from .planning_comparison_view import PlanningComparisonView
from .detached_stats_window import DetachedStatsWindow
from .planning_management import PlanningManagementWidget
from core.utils import resource_path
from .styles import color_system, GLOBAL_STYLE, ACTION_BUTTON_STYLE, StyleConstants

class MainWindow(QMainWindow):
    def __init__(self, doctors, cats, post_configuration):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.data_persistence = DataPersistence()
        self.detached_stats_window = None
        
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

        # Style des onglets avec les nouvelles constantes
        self.tab_widget.setStyleSheet(f"""
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
                transition: background-color {StyleConstants.ANIMATION['fast']}ms;
            }}
            QTabBar::tab:focus {{
                outline: none;
                border: 2px solid {color_system.colors['focus']['outline'].name()};
            }}
        """)

        # Initialisation des onglets
        self._init_planning_tab()
        self._init_personnel_tab()
        self._init_desiderata_tab()
        self._init_doctor_planning_tab()
        self._init_stats_tab()
        self._init_comparison_tab()
        self._init_export_tab()

    def _init_planning_tab(self):
        """Initialise l'onglet Planning"""
        self.planning_tab = PlanningViewWidget(self.doctors, self.cats, 
                                             self.post_configuration, self)
        self.tab_widget.addTab(self.planning_tab, 
                             self.create_tab_icon("icons/planning.png"), "Planning")

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
            # [Code de mise à jour du planning...]
            pass

    def save_data(self):
        """Sauvegarde les données"""
        self.data_persistence.save_data(self.doctors, self.cats, 
                                      self.post_configuration)
        self.planning_management_tab.update_planning_list()

    def _init_desiderata_tab(self):
        """Initialise l'onglet Gestion des desiderata"""
        self.desiderata_tab = DesiderataManagementWidget(
            self.doctors, 
            self.cats, 
            self.planning_tab.start_date.date().toPyDate(),
            self.planning_tab.end_date.date().toPyDate(),
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
        self.tab_widget.addTab(
            self.doctor_planning_view,
            self.create_tab_icon("icons/doctor_planning.png"),
            "Planning par médecin"
        )

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
            "Comparaison des plannings"
        )

    def _init_export_tab(self):
        """Initialise l'onglet Exporter"""
        self.planning_management_tab = PlanningManagementWidget(self)
        self.tab_widget.addTab(
            self.planning_management_tab,
            self.create_tab_icon("icons/export.png"),
            "Exporter"
        )

    def create_tab_icon(self, icon_path, size=32):
        return QIcon(resource_path(icon_path))

    def on_planning_dates_changed(self, start_date, end_date):
        self.desiderata_tab.sync_dates_from_planning(start_date, end_date)

    def closeEvent(self, event):
        self.data_persistence.save_data(self.doctors, self.cats, self.post_configuration)
        event.accept()

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

    def update_data(self):
        self.personnel_tab.update_tables()
        self.planning_tab.update_data(self.doctors, self.cats, self.post_configuration)
        
        if hasattr(self.planning_tab, 'planning') and self.planning_tab.planning:
            start_date = self.planning_tab.planning.start_date
            end_date = self.planning_tab.planning.end_date
            
            # Mettre à jour les dates dans PlanningViewWidget
            self.planning_tab.start_date.setDate(QDate(start_date))
            self.planning_tab.end_date.setDate(QDate(end_date))
            
            # Mettre à jour les dates dans DesiderataManagementWidget
            self.desiderata_tab.sync_dates_from_planning(start_date, end_date)
            
            self.update_stats_view()
            self.comparison_view.planning = self.planning_tab.planning
            self.comparison_view.update_comparison(preserve_selection=True)
            self.doctor_planning_view.planning = self.planning_tab.planning
            self.doctor_planning_view.update_table()
        else:
            # Réinitialiser les vues si aucun planning n'est chargé
            self.stats_tab.clear_stats()
            self.comparison_view.reset_view()
            self.doctor_planning_view.clear_view()

        self.desiderata_tab.update_stats()
        self.personnel_tab.post_config_tab.update_configuration(self.post_configuration)

    def update_stats_view(self):
        if self.detached_stats_window:
            self.detached_stats_window.update_stats()
        else:
            self.stats_tab.update_stats(self.planning_tab.planning, self.doctors, self.cats)

    def save_data(self):
        self.data_persistence.save_data(self.doctors, self.cats, self.post_configuration)
        self.planning_management_tab.update_planning_list()

    def detach_stats(self):
        if not self.detached_stats_window:
            self.tab_widget.removeTab(self.stats_index)
            self.detached_stats_window = DetachedStatsWindow(self)
            self.detached_stats_window.show()
            # Assurez-vous que les statistiques sont à jour lors du détachement
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
            
            self.stats_index = self.tab_widget.insertTab(
                self.stats_index,
                stats_container,
                self.create_tab_icon("icons/statistics.png"),
                "Statistiques"
            )
            self.tab_widget.setCurrentIndex(self.stats_index)
            self.update_stats_view()

    def reset_all_views(self):
        # Réinitialiser la vue de comparaison
        self.comparison_view.reset_view()
        
        # Réinitialiser la vue des statistiques
        self.stats_tab.clear_stats()
        
        # Réinitialiser la vue du planning par médecin
        self.doctor_planning_view.clear_view()
        
        # Mettre à jour les autres vues si nécessaire
        self.update_data()
