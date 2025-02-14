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
from .styles import color_system, GLOBAL_STYLE


class MainWindow(QMainWindow):
    def __init__(self, doctors, cats, post_configuration):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.data_persistence = DataPersistence()
        self.detached_stats_window = None
        
        # Apply global style
        self.setStyleSheet(GLOBAL_STYLE)
        
        self.init_ui()
        self.planning_tab.dates_changed.connect(self.on_planning_dates_changed)

    def init_ui(self):
        self.setWindowTitle('Planificateur SOS Médecins')
        self.setGeometry(100, 100, 1200, 800)

        self.tab_widget = QTabWidget()
        self.tab_widget.setIconSize(QSize(32, 32))  # Définir la taille des icônes pour tous les onglets
        self.setCentralWidget(self.tab_widget)

        # Onglet Planning (créé en premier pour pouvoir accéder aux dates)
        self.planning_tab = PlanningViewWidget(self.doctors, self.cats, self.post_configuration, self)
        
        # Onglet Gestion du personnel
        self.personnel_tab = PersonnelManagementWidget(self.doctors, self.cats, self.post_configuration, self)
        self.tab_widget.addTab(self.personnel_tab, self.create_tab_icon("icons/personnel.png"), "Gestion du personnel")
        
        # Connect custom posts updates
        self.personnel_tab.post_config_tab.custom_posts_updated.connect(self.planning_tab.refresh_custom_posts)

        # Onglet Gestion des desiderata
        self.desiderata_tab = DesiderataManagementWidget(self.doctors, self.cats, self.planning_tab.start_date.date().toPyDate(), self.planning_tab.end_date.date().toPyDate(), self)
        self.tab_widget.addTab(self.desiderata_tab, self.create_tab_icon("icons/desiderata.png"), "Gestion des desiderata")

        # Ajout de l'onglet Planning
        self.tab_widget.addTab(self.planning_tab, self.create_tab_icon("icons/planning.png"), "Planning")

        # Onglet Planning par médecin
        self.doctor_planning_view = DoctorPlanningView(None, self.doctors, self.cats)
        self.tab_widget.addTab(self.doctor_planning_view, self.create_tab_icon("icons/doctor_planning.png"), "Planning par médecin")

        # Onglet Statistiques
        self.stats_tab = StatsView(doctors=self.doctors, cats=self.cats)
        self.stats_tab.set_parent_window(self)  # Définir la référence parent
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.addWidget(self.stats_tab)
       
        detach_button = QPushButton("Détacher les statistiques")
        detach_button.clicked.connect(self.detach_stats)
        stats_layout.addWidget(detach_button)
        
        self.stats_index = self.tab_widget.addTab(stats_container, self.create_tab_icon("icons/statistics.png"), "Statistiques")

        # Onglet Comparaison des plannings
        self.comparison_view = PlanningComparisonView(None, self.doctors, self.cats, self)
        self.tab_widget.addTab(self.comparison_view, self.create_tab_icon("icons/comparaison.png"), "Comparaison des plannings")

        # Onglet Exporter
        self.planning_management_tab = PlanningManagementWidget(self)
        self.tab_widget.addTab(self.planning_management_tab, self.create_tab_icon("icons/export.png"), "Exporter")

        # Mettre à jour les dates dans PostConfigurationWidget
        start_date = self.planning_tab.start_date.date().toPyDate()
        end_date = self.planning_tab.end_date.date().toPyDate()
        self.personnel_tab.post_config_tab.update_dates(start_date, end_date)

        self.planning_tab.dates_changed.connect(self.on_planning_dates_changed)

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
        if self.detached_stats_window:
            self.detached_stats_window.close()
            self.detached_stats_window = None
            stats_container = QWidget()
            stats_layout = QVBoxLayout(stats_container)
            detach_button = QPushButton("Détacher les statistiques")
            detach_button.clicked.connect(self.detach_stats)
            stats_layout.addWidget(detach_button)
            stats_layout.addWidget(self.stats_tab)
            self.stats_index = self.tab_widget.insertTab(self.stats_index, stats_container, "Statistiques")
            self.tab_widget.setCurrentIndex(self.stats_index)
            # Assurez-vous que les statistiques sont à jour lors du rattachement
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
