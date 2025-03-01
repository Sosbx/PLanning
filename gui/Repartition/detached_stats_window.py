
# © 2024 HILAL Arkane. Tous droits réservés.
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt
from .stats_view import StatsView
from ..styles import ACTION_BUTTON_STYLE

class DetachedStatsWindow(QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Statistiques détachées")
        # Create a container widget with layout
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create stats view
        self.stats_view = StatsView(planning=main_window.planning_tab.planning, 
                                  doctors=main_window.doctors, 
                                  cats=main_window.cats)
        layout.addWidget(self.stats_view)
        
        # Create and style detach button
        detach_button = QPushButton("Détacher les statistiques")
        detach_button.setStyleSheet(ACTION_BUTTON_STYLE)
        detach_button.setMinimumHeight(35)
        detach_button.clicked.connect(self.close)
        layout.addWidget(detach_button, 0, Qt.AlignmentFlag.AlignRight)
        
        self.setCentralWidget(container)
        self.setGeometry(200, 200, 800, 600)

    def closeEvent(self, event):
        self.main_window.reattach_stats()
        event.accept()

    def update_stats(self):
        if hasattr(self.main_window.planning_tab, 'planning'):
            self.stats_view.update_stats(self.main_window.planning_tab.planning,
                                         self.main_window.doctors,
                                         self.main_window.cats)
