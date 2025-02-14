# © 2024 HILAL Arkane. Tous droits réservés.
from PyQt6.QtWidgets import QMainWindow
from .stats_view import StatsView

class DetachedStatsWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Statistiques détachées")
        self.stats_view = StatsView(planning=main_window.planning_tab.planning, 
                                    doctors=main_window.doctors, 
                                    cats=main_window.cats)
        self.setCentralWidget(self.stats_view)
        self.setGeometry(200, 200, 800, 600)

    def closeEvent(self, event):
        self.main_window.reattach_stats()
        event.accept()

    def update_stats(self):
        if hasattr(self.main_window.planning_tab, 'planning'):
            self.stats_view.update_stats(self.main_window.planning_tab.planning,
                                         self.main_window.doctors,
                                         self.main_window.cats)