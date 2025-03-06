# © 2024 HILAL Arkane. Tous droits réservés.
# gui/post_attribution_history_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QPushButton, QLabel, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from datetime import datetime
from gui.styles import color_system, ADD_BUTTON_STYLE, EDIT_DELETE_BUTTON_STYLE

class PostAttributionHistoryDialog(QDialog):
    """
    Dialogue pour afficher l'historique des post-attributions.
    """
    def __init__(self, post_attribution_handler, parent=None):
        super().__init__(parent)
        self.post_attribution_handler = post_attribution_handler
        self.init_ui()
        self.load_history()
    
    def init_ui(self):
        """Initialise l'interface utilisateur."""
        self.setWindowTitle("Historique des Post-Attributions")
        self.resize(800, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Titre
        title_label = QLabel("Historique des Post-Attributions")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Table d'historique
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["Date/Heure", "Action", "Détails"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.history_table)
        
        # Boutons
        button_layout = QHBoxLayout()
        self.clear_button = QPushButton("Effacer l'historique")
        self.clear_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        self.clear_button.clicked.connect(self.clear_history)
        button_layout.addWidget(self.clear_button)
        
        self.close_button = QPushButton("Fermer")
        self.close_button.setStyleSheet(ADD_BUTTON_STYLE)
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def load_history(self):
        """Charge l'historique des post-attributions dans la table."""
        self.history_table.setRowCount(0)
        
        history = self.post_attribution_handler.get_history()
        self.history_table.setRowCount(len(history))
        
        for i, (timestamp, action_type, details) in enumerate(history):
            # Date/Heure
            time_item = QTableWidgetItem(timestamp.strftime("%d/%m/%Y %H:%M"))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(i, 0, time_item)
            
            # Type d'action
            action_item = QTableWidgetItem(action_type)
            action_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if "Suppression" in action_type:
                from gui.styles import PlatformHelper
                PlatformHelper.apply_background_color(action_item, color_system.get_color('danger'))
            else:
                from gui.styles import PlatformHelper
                PlatformHelper.apply_background_color(action_item, color_system.get_color('available'))
            self.history_table.setItem(i, 1, action_item)
            
            # Détails
            details_item = QTableWidgetItem(details)
            self.history_table.setItem(i, 2, details_item)
    
    def clear_history(self):
        """Efface l'historique des post-attributions."""
        reply = QMessageBox.question(
            self,
            "Confirmation",
            "Êtes-vous sûr de vouloir effacer tout l'historique des post-attributions ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.post_attribution_handler.clear_history()
            self.history_table.setRowCount(0)
