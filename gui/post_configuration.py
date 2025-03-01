# © 2024 HILAL Arkane. Tous droits réservés.
# gui/post_configuration.py
from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
                            QTimeEdit, QLineEdit, QCheckBox, QGroupBox,
                            QTableWidget, QTableWidgetItem, QLabel, QSpinBox, QDateEdit, 
                            QHeaderView, QComboBox, QDialog, QFormLayout, QDialogButtonBox, 
                            QMessageBox, QRadioButton, QButtonGroup,QCalendarWidget, QScrollArea)
from datetime import datetime, time, date, timedelta
from PyQt6.QtCore import Qt, QDate, QTime, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QIcon, QFont
from datetime import time  # Ajout de l'import correct pour time
from core.Constantes.models import DailyPostConfiguration, PostConfig, SpecificPostConfig, ALL_POST_TYPES, PostManager, TimeSlot
from core.Constantes.custom_post import CustomPost
from typing import List, Dict, Optional, TYPE_CHECKING, Union
from .styles import EDIT_DELETE_BUTTON_STYLE, ACTION_BUTTON_STYLE, ADD_BUTTON_STYLE
from workalendar.europe import France
from core.Constantes.day_type import DayType
import logging

logger = logging.getLogger(__name__)


class CustomSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class SpecificConfigDialog(QDialog):
    def __init__(self, parent, start_date, end_date, default_weekday_config, default_saturday_config, 
                default_sunday_config, existing_config=None):
        """Initialise la boîte de dialogue de configuration spécifique"""
        super().__init__(parent)
        self.start_date = start_date
        self.end_date = end_date
        self.default_weekday_config = default_weekday_config
        self.default_saturday_config = default_saturday_config
        self.default_sunday_config = default_sunday_config
        self.existing_config = existing_config
        self.result = None
        
        self.setWindowTitle("Configuration Spécifique")
        self.setMinimumWidth(600)
        
        self.init_ui()
        
        # Initialiser en fonction de la configuration existante
        if existing_config:
            # Définir les dates
            self.start_date_edit.setDate(QDate(existing_config.start_date))
            self.end_date_edit.setDate(QDate(existing_config.end_date))
            
            # Définir le type de jour
            if existing_config.apply_to == "Semaine":
                self.day_type_group.button(1).setChecked(True)
            elif existing_config.apply_to == "Samedi":
                self.day_type_group.button(2).setChecked(True)
            else:  # "Dimanche/Férié"
                self.day_type_group.button(3).setChecked(True)
        
        # Mettre à jour la table (cela prendra en compte le type de jour et la configuration existante)
        self.update_table()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 1em;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2d3436;
                font-weight: bold;
            }
            QLabel {
                color: #2d3436;
            }
            QDateEdit, QRadioButton {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                min-width: 120px;
            }
            QDateEdit:hover, QRadioButton:hover {
                border-color: #3498db;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        # Date inputs dans un GroupBox
        dates_group = QGroupBox("Période")
        form = QFormLayout(dates_group)
        
        self.start_date_edit = QDateEdit(self.start_date if not self.existing_config else self.existing_config.start_date)
        self.end_date_edit = QDateEdit(self.end_date if not self.existing_config else self.existing_config.end_date)
        
        form.addRow("Date de début:", self.start_date_edit)
        form.addRow("Date de fin:", self.end_date_edit)
        
        layout.addWidget(dates_group)

        # Day type selection dans un GroupBox
        day_type_group = QGroupBox("Type de jours")
        day_type_layout = QHBoxLayout(day_type_group)
        
        self.day_type_mapping = {
            1: "Semaine",
            2: "Samedi",
            3: "Dimanche/Férié"
        }

        self.day_type_group = QButtonGroup(self)
        weekday_radio = QRadioButton("Jours de semaine")
        saturday_radio = QRadioButton("Samedis")
        sunday_radio = QRadioButton("Dimanches/Fériés")
        
        self.day_type_group.addButton(weekday_radio, 1)
        self.day_type_group.addButton(saturday_radio, 2)
        self.day_type_group.addButton(sunday_radio, 3)

        day_type_layout.addWidget(weekday_radio)
        day_type_layout.addWidget(saturday_radio)
        day_type_layout.addWidget(sunday_radio)
        
        layout.addWidget(day_type_group)

        # Posts table dans un GroupBox
        posts_group = QGroupBox("Configuration des postes")
        posts_layout = QVBoxLayout(posts_group)
        
        self.post_table = QTableWidget()
        self.post_table.setColumnCount(2)
        self.post_table.setHorizontalHeaderLabels(["Type de poste", "Nombre"])
        self.post_table.verticalHeader().setVisible(False)
        self.post_table.setStyleSheet("""
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
                font-weight: bold;
                color: #2d3436;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f2f5;
            }
            QTableWidget::item:hover {
                background-color: #f8f9fa;
            }
        """)
        posts_layout.addWidget(self.post_table)
        
        layout.addWidget(posts_group)

        # Boutons dans un conteneur avec style
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        
        ok_button = QPushButton("Valider")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        
        cancel_button = QPushButton("Annuler")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addWidget(button_container)

        self.day_type_group.buttonClicked.connect(self.update_table)
        weekday_radio.setChecked(True)
        self.update_table()

    def update_table(self):
        """Met à jour la table en fonction du type de jour sélectionné"""
        self.post_table.setRowCount(0)
        day_type_id = self.day_type_group.checkedId()
        
        # Sélectionner la configuration par défaut en fonction du type de jour
        if day_type_id == 1:
            default_config = self.default_weekday_config
        elif day_type_id == 2:
            default_config = self.default_saturday_config
        else:
            default_config = self.default_sunday_config
        
        from core.Constantes.models import ALL_POST_TYPES
        
        for post_type in ALL_POST_TYPES:
            row = self.post_table.rowCount()
            self.post_table.insertRow(row)
            
            # Cellule pour le type de poste
            name_item = QTableWidgetItem(post_type)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.post_table.setItem(row, 0, name_item)
            
            # Spinbox pour la valeur
            spinbox = QSpinBox()
            spinbox.setRange(0, 20)
            
            # Style amélioré pour le spinbox
            spinbox.setStyleSheet("""
                QSpinBox {
                    min-height: 30px;
                    min-width: 80px;
                    padding: 5px;
                    font-size: 14px;
                    font-weight: bold;
                    background-color: white;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    width: 20px;
                    height: 15px;
                    border-radius: 2px;
                    background-color: #f0f0f0;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background-color: #e0e0e0;
                }
            """)
            
            # Initialiser avec la valeur de la configuration existante si disponible
            # sinon utiliser la valeur par défaut
            if self.existing_config and post_type in self.existing_config.post_counts:
                spinbox.setValue(self.existing_config.post_counts[post_type])
            else:
                # Utiliser la valeur par défaut du type de jour
                default_value = default_config.get(post_type, None)
                default_total = 0 if default_value is None else default_value.total
                spinbox.setValue(default_total)
            
            self.post_table.setCellWidget(row, 1, spinbox)
        
        # Optimiser la largeur des colonnes
        self.post_table.setColumnWidth(0, 150)  # Type de poste
        self.post_table.setColumnWidth(1, 100)  # Nombre

    
    
    def validate_dates_and_type(self, date, day_type) -> bool:
        """
        Valide la configuration spécifique en permettant la modification forcée
        du type de jour. Retourne toujours True pour permettre la modification,
        mais ajoute un avertissement si le type configuré ne correspond pas au
        type réel du jour.
        
        Args:
            date: Date à valider
            day_type: Type de jour configuré
            
        Returns:
            bool: True pour permettre la configuration
        """
        cal = France()
        real_day_type = DayType.get_day_type(date, cal)
        
        type_mapping = {
            "Semaine": "weekday",
            "Samedi": "saturday",
            "Dimanche/Férié": "sunday_holiday"
        }
        
        config_type = type_mapping.get(self.day_type_mapping[self.day_type_group.checkedId()])
        
        if config_type != real_day_type:
            # Simple avertissement sans bloquer la configuration
            logger.warning(
                f"Attention : Configuration de type {config_type} "
                f"appliquée sur un jour de type {real_day_type} ({date})"
            )
            
            # Afficher un message d'avertissement à l'utilisateur
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Avertissement")
            msg.setText(
                f"Vous appliquez une configuration de type {config_type} "
                f"sur un jour de type {real_day_type}.\n\n"
                f"La configuration sera appliquée, mais cela pourrait "
                f"créer des incohérences dans le planning."
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

        return True  # Permettre la configuration dans tous les cas

    def accept(self):
        """Valide la boîte de dialogue et récupère les résultats"""
        # Vérifier que les dates sont valides
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        
        if start_date > end_date:
            QMessageBox.warning(
                self,
                "Dates invalides",
                "La date de début doit être antérieure ou égale à la date de fin."
            )
            return
        
        # Récupérer le type de jour
        day_type_id = self.day_type_group.checkedId()
        if day_type_id == 1:
            day_type = "Semaine"
        elif day_type_id == 2:
            day_type = "Samedi"
        else:
            day_type = "Dimanche/Férié"
        
        # Récupérer les valeurs des postes
        post_counts = {}
        for row in range(self.post_table.rowCount()):
            post_type = self.post_table.item(row, 0).text()
            spinbox = self.post_table.cellWidget(row, 1)
            value = spinbox.value()
            
            # Récupérer la valeur par défaut
            if day_type_id == 1:
                default_config = self.default_weekday_config
            elif day_type_id == 2:
                default_config = self.default_saturday_config
            else:
                default_config = self.default_sunday_config
                
            default_value = default_config.get(post_type, None)
            default_total = 0 if default_value is None else default_value.total
            
            # Ajouter uniquement si la valeur est différente de la valeur par défaut
            if value != default_total:
                post_counts[post_type] = value
        
        # Créer l'objet SpecificPostConfig
        self.result = SpecificPostConfig(
            start_date=start_date,
            end_date=end_date,
            apply_to=day_type,
            post_counts=post_counts
        )
        
        # Accepter la boîte de dialogue
        super().accept()
    def get_result(self) -> Optional[SpecificPostConfig]:
        """Accesseur pour récupérer la configuration créée"""
        return getattr(self, 'config_result', None)

        
class SpecificConfigWidget(QWidget):
    def __init__(self, post_configuration, planning_start_date, planning_end_date, main_window):
        super().__init__()
        self.post_configuration = post_configuration
        self.planning_start_date = planning_start_date
        self.planning_end_date = planning_end_date
        self.main_window = main_window
        self.init_ui()
        # Mettre à jour immédiatement la table après l'initialisation
        self.update_table()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Style global du widget
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f6fa;
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                gridline-color: #f0f2f5;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f2f5;
            }
            QTableWidget::item:hover {
                background-color: #f8f9fa;
            }
            QTableWidget::item:selected {
                background-color: #e8f0fe;
                color: #2d3436;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
                font-weight: bold;
                color: #2d3436;
            }
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ddd;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #d8d8d8;
            }
            QPushButton#addButton {
                background-color: #4CAF50;
                color: white;
                border: none;
            }
            QPushButton#addButton:hover {
                background-color: #45a049;
            }
            QPushButton#deleteButton {
                background-color: #f44336;
                color: white;
                border: none;
            }
            QPushButton#deleteButton:hover {
                background-color: #da190b;
            }
            QPushButton#viewCalendarButton {
                background-color: #3498db;
                color: white;
                border: none;
            }
            QPushButton#viewCalendarButton:hover {
                background-color: #2980b9;
            }
            QPushButton#harmonizeButton {
                background-color: #9b59b6;
                color: white;
                border: none;
            }
            QPushButton#harmonizeButton:hover {
                background-color: #8e44ad;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 1em;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2d3436;
                font-weight: bold;
            }
        """)

        # En-tête avec titre et stats
        header_layout = QHBoxLayout()
        title = QLabel("Configurations spécifiques")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            padding: 12px 0;
            margin-bottom: 8px;
        """)
        header_layout.addWidget(title)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            color: #7f8c8d;
            font-style: italic;
            padding: 4px 8px;
            background-color: #f8f9fa;
            border-radius: 4px;
        """)
        header_layout.addWidget(self.stats_label)
        header_layout.addStretch()
        
        # Boutons outils
        tools_layout = QHBoxLayout()
        
        # Bouton d'harmonisation
        harmonize_button = QPushButton("Harmoniser les configurations")
        harmonize_button.setObjectName("harmonizeButton")
        harmonize_button.setIcon(QIcon("icons/harmonize.png"))
        harmonize_button.clicked.connect(self.show_harmonization_dialog)
        tools_layout.addWidget(harmonize_button)
        
        # Bouton de visualisation calendaire
        view_calendar_button = QPushButton("Visualisation Calendaire")
        view_calendar_button.setObjectName("viewCalendarButton")
        view_calendar_button.setIcon(QIcon("icons/calendar.png"))
        view_calendar_button.clicked.connect(self.show_calendar_view)
        tools_layout.addWidget(view_calendar_button)
        
        tools_layout.addStretch()
        header_layout.addLayout(tools_layout)

        layout.addLayout(header_layout)

        # Table des configurations avec dimensions ajustées
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Période", "Type de jour", "Modifications", "Actions"
        ])
        
        # Ajustement des dimensions de la table
        self.table.verticalHeader().setVisible(False)  # Cache les numéros de lignes
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # Ajuste la hauteur au contenu
        
        # Configuration des colonnes
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Période
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # Type de jour
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Modifications
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Actions
        
        # Définition des largeurs fixes
        self.table.setColumnWidth(0, 200)  # Période
        self.table.setColumnWidth(1, 150)  # Type de jour
        self.table.setColumnWidth(3, 120)  # Actions
        
        layout.addWidget(self.table)

        # Boutons d'action
        button_layout = QHBoxLayout()
        add_button = QPushButton("Ajouter une configuration")
        add_button.setObjectName("addButton")
        add_button.setIcon(QIcon("icons/ajouter.png"))
        add_button.clicked.connect(self.add_specific_config)
        add_button.setStyleSheet(ADD_BUTTON_STYLE)

        save_button = QPushButton("Enregistrer les modifications")
        save_button.clicked.connect(self.save_specific_config)
        save_button.setStyleSheet(ACTION_BUTTON_STYLE)

        button_layout.addWidget(add_button)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

    def show_harmonization_dialog(self):
        """Affiche le dialogue d'harmonisation des configurations."""
        from .harmonization_dialog import HarmonizationDialog
        
        try:
            dialog = HarmonizationDialog(self.post_configuration, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Si des modifications ont été apportées, mettre à jour la table
                self.update_table()
        except Exception as e:
            logger.error(f"Erreur lors de l'affichage du dialogue d'harmonisation: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'affichage du dialogue d'harmonisation:\n{str(e)}"
            )

    def update_table(self):
        """Met à jour la table avec les configurations spécifiques regroupées"""
        # Vérifier si des configurations spécifiques existent
        if not hasattr(self.post_configuration, 'specific_configs'):
            self.post_configuration.specific_configs = []
            
        # Trier et regrouper les configurations
        grouped_configs = self._group_consecutive_configs(self.post_configuration.specific_configs)
        
        # Mise à jour des stats
        total_days = sum(len(group) for group in grouped_configs)
        self.stats_label.setText(f"{total_days} jours configurés")
        
        # Mise à jour de la table
        self.table.setRowCount(len(grouped_configs))
        
        for row, group in enumerate(grouped_configs):
            # Période
            date_cell = QWidget()
            date_layout = QHBoxLayout(date_cell)
            date_layout.setContentsMargins(5, 2, 5, 2)
            
            if len(group) == 1:
                date_text = group[0].start_date.strftime("%d %b %Y")
            else:
                date_text = f"{group[0].start_date.strftime('%d %b')} → {group[-1].end_date.strftime('%d %b %Y')}"
            
            date_label = QLabel(date_text)
            date_layout.addWidget(date_label)
            self.table.setCellWidget(row, 0, date_cell)
            
            # Type de jour avec icône
            type_cell = QWidget()
            type_layout = QHBoxLayout(type_cell)
            type_layout.setContentsMargins(5, 2, 5, 2)
            
            type_icon = QLabel()
            if group[0].apply_to == "Semaine":
                type_icon.setPixmap(QIcon("icons/semaine.png").pixmap(16, 16))
            elif group[0].apply_to == "Samedi":
                type_icon.setPixmap(QIcon("icons/weekend.png").pixmap(16, 16))
            else:
                type_icon.setPixmap(QIcon("icons/ferie.png").pixmap(16, 16))
                
            type_layout.addWidget(type_icon)
            type_layout.addWidget(QLabel(group[0].apply_to))
            self.table.setCellWidget(row, 1, type_cell)
            
            # Modifications avec mise en forme
            differences = self._get_config_differences(group[0])
            mods_cell = self._create_modifications_widget(differences)
            self.table.setCellWidget(row, 2, mods_cell)
            
            # Actions
            actions = self._create_actions_widget(row, group)
            self.table.setCellWidget(row, 3, actions)

    def _create_date_cell(self, group):
        """Crée une cellule de date avec dimensions appropriées"""
        date_cell = QWidget()
        date_layout = QHBoxLayout(date_cell)
        date_layout.setContentsMargins(8, 4, 8, 4)
        date_layout.setSpacing(8)
        
        if len(group) == 1:
            date_text = group[0].start_date.strftime("%d %b %Y")
        else:
            date_text = f"{group[0].start_date.strftime('%d %b')} → {group[-1].end_date.strftime('%d %b %Y')}"
        
        date_label = QLabel(date_text)
        date_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-weight: bold;
            }
        """)
        date_layout.addWidget(date_label)
        date_layout.addStretch()
        
        return date_cell

    def _create_type_cell(self, apply_to):
        """Crée une cellule de type de jour avec dimensions appropriées"""
        type_cell = QWidget()
        type_layout = QHBoxLayout(type_cell)
        type_layout.setContentsMargins(8, 4, 8, 4)
        type_layout.setSpacing(8)
        
        # Icône plus grande
        type_icon = QLabel()
        icon_size = QSize(24, 24)
        if apply_to == "Semaine":
            pixmap = QIcon("icons/semaine.png").pixmap(icon_size)
        elif apply_to == "Samedi":
            pixmap = QIcon("icons/weekend.png").pixmap(icon_size)
        else:
            pixmap = QIcon("icons/ferie.png").pixmap(icon_size)
        type_icon.setPixmap(pixmap)
        type_icon.setFixedSize(icon_size)
        
        type_layout.addWidget(type_icon)
        
        type_label = QLabel(apply_to)
        type_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
            }
        """)
        type_layout.addWidget(type_label)
        type_layout.addStretch()
        
        return type_cell

    def _create_modifications_widget(self, differences):
        """Crée un widget de modifications avec une meilleure visualisation des changements"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        if not differences:
            no_changes = QLabel("Aucune modification")
            no_changes.setStyleSheet("""
                QLabel {
                    color: #7f8c8d;
                    font-style: italic;
                    padding: 4px;
                }
            """)
            layout.addWidget(no_changes)
            layout.addStretch()
            return widget

        for post_type, values in differences.items():
            mod_widget = QWidget()
            mod_widget.setMinimumHeight(70)
            mod_layout = QVBoxLayout(mod_widget)
            mod_layout.setContentsMargins(4, 4, 4, 4)
            mod_layout.setSpacing(4)
            
            # Badge du type de poste
            post_label = QLabel(post_type)
            post_label.setMinimumHeight(28)
            post_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f0fe;
                    color: #1a73e8;
                    padding: 4px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
            
            # Affichage des valeurs avec style adapté au changement
            change = values['new'] - values['base']
            if change > 0:
                color = "#27ae60"  # Vert pour augmentation
                change_text = f"+{change}"
            elif change < 0:
                color = "#e74c3c"  # Rouge pour diminution
                change_text = str(change)
            else:
                color = "#7f8c8d"  # Gris pour pas de changement
                change_text = "0"

            value_label = QLabel(f"{values['base']} → {values['new']} ({change_text})")
            value_label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    font-weight: bold;
                    padding: 4px;
                    text-align: center;
                }}
            """)
            
            mod_layout.addWidget(post_label, alignment=Qt.AlignmentFlag.AlignCenter)
            mod_layout.addWidget(value_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            layout.addWidget(mod_widget)

        layout.addStretch()
        return widget

    def _create_actions_widget(self, row, group):
        """Crée un widget d'actions avec dimensions appropriées"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Boutons plus grands
        edit_button = QPushButton()
        edit_button.setIcon(QIcon("icons/edition.png"))
        edit_button.setIconSize(QSize(20, 20))
        edit_button.setFixedSize(32, 32)
        edit_button.setToolTip("Modifier")
        edit_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        edit_button.clicked.connect(lambda: self._edit_group(row, group))
        
        delete_button = QPushButton()
        delete_button.setIcon(QIcon("icons/supprimer.png"))
        delete_button.setIconSize(QSize(20, 20))
        delete_button.setFixedSize(32, 32)
        delete_button.setToolTip("Supprimer")
        delete_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        delete_button.clicked.connect(lambda: self._delete_group(row, group))
        
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        layout.addStretch()
        
        return widget

    def _group_consecutive_configs(self, configs):
        """Regroupe les configurations consécutives avec les mêmes paramètres"""
        if not configs:
            return []
            
        # Trier les configurations par date
        sorted_configs = sorted(configs, key=lambda x: x.start_date)
        
        groups = []
        current_group = [sorted_configs[0]]
        
        for config in sorted_configs[1:]:
            prev_config = current_group[-1]
            
            # Vérifier si les configurations peuvent être groupées
            if (prev_config.end_date + timedelta(days=1) == config.start_date and
                prev_config.apply_to == config.apply_to and
                prev_config.post_counts == config.post_counts):
                current_group.append(config)
            else:
                groups.append(current_group)
                current_group = [config]
        
        groups.append(current_group)
        return groups

    def _get_config_differences(self, config):
        """Compare avec la configuration de base et détecte toutes les différences"""
        differences = {}
        
        # Sélectionner la configuration de base appropriée
        if config.apply_to == "Semaine":
            base_config = self.post_configuration.weekday
        elif config.apply_to == "Samedi":
            base_config = self.post_configuration.saturday
        else:  # Dimanche/Férié
            base_config = self.post_configuration.sunday_holiday
        
        # 1. Vérifier tous les postes de la base
        for post_type in ALL_POST_TYPES:
            base_count = base_config.get(post_type, PostConfig()).total
            new_count = config.post_counts.get(post_type, 0)  # Si non présent, considérer comme 0

            if base_count != new_count:
                differences[post_type] = {
                    'base': base_count,
                    'new': new_count
                }
                logger.debug(f"Différence trouvée pour {post_type}: {base_count} -> {new_count}")
        
        # 2. Vérifier également les postes personnalisés
        for post_type in config.post_counts.keys():
            if post_type not in ALL_POST_TYPES:
                base_count = base_config.get(post_type, PostConfig()).total
                new_count = config.post_counts.get(post_type, 0)
                
                if base_count != new_count:
                    differences[post_type] = {
                        'base': base_count,
                        'new': new_count
                    }
                    logger.debug(f"Différence trouvée pour poste personnalisé {post_type}: {base_count} -> {new_count}")
        
        return differences
    
    def show_calendar_view(self):
        """Affiche la vue calendaire des configurations spécifiques"""
        from .calendar_view import CalendarView
        
        try:
            calendar_dialog = CalendarView(
                self.post_configuration,
                self,
                self.planning_start_date,
                self.planning_end_date
            )
            
            # Exécuter la boîte de dialogue de façon modale
            result = calendar_dialog.exec()
            
            # Si des modifications ont été apportées, mettre à jour la table
            if result == QDialog.DialogCode.Accepted:
                self.update_table()
            else:
                # Même si Annuler est cliqué, des modifications ont pu être apportées
                # donc on met à jour quand même
                self.update_table()
                
        except Exception as e:
            logger.error(f"Erreur lors de l'affichage de la vue calendaire: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'affichage de la vue calendaire:\n{str(e)}"
            )

    def _format_modifications(self, differences):
        """Formate les modifications pour l'affichage dans la table"""
        if not differences:
            return "Aucune modification"
            
        mods = []
        for post_type, values in differences.items():
            mods.append(f"{post_type}: {values['base']}→{values['new']}")
        
        return ", ".join(mods)

    def _format_tooltip(self, differences):
        """Crée un tooltip détaillé des modifications"""
        if not differences:
            return "Aucune modification par rapport à la configuration de base"
            
        lines = ["Modifications détaillées :"]
        for post_type, values in differences.items():
            lines.append(f"{post_type}:")
            lines.append(f"  - Configuration de base : {values['base']}")
            lines.append(f"  - Nouvelle configuration : {values['new']}")
            
        return "\n".join(lines)

    def _edit_group(self, row, group):
        """Édite un groupe de configurations avec amélioration de la sélection de date"""
        # Créer une liste de toutes les dates du groupe
        all_dates = []
        for config in group:
            current_date = config.start_date
            while current_date <= config.end_date:
                all_dates.append(current_date)
                current_date += timedelta(days=1)

        # Trier les dates et prendre la première comme date d'édition
        if all_dates:
            all_dates.sort()
            edit_date = all_dates[0]
        else:
            edit_date = None

        # Créer le dialogue avec les dates, la configuration et la date d'édition
        dialog = AddConfigDialog(
            self,
            self.post_configuration,
            existing_config=group[0],  # Configuration modèle
            existing_dates=all_dates,  # Toutes les dates du groupe
            edit_date=edit_date       # Date à éditer pour positionnement du calendrier
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Supprimer les anciennes configurations
            for config in group:
                self.post_configuration.remove_specific_config(config)
            
            # Ajouter les nouvelles
            for new_config in dialog.config_results:
                self.post_configuration.add_specific_config(new_config)
                
            self.update_table()

    def _delete_group(self, row, group):
        """Supprime un groupe de configurations"""
        message = "Êtes-vous sûr de vouloir supprimer cette configuration ?"
        if len(group) > 1:
            message = f"Êtes-vous sûr de vouloir supprimer ces {len(group)} configurations ?"
        
        reply = QMessageBox.question(
            self,
            "Confirmation",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for config in group:
                self.post_configuration.remove_specific_config(config)
            self.update_table()

    def add_specific_config(self):
        """Ajoute une nouvelle configuration spécifique"""
        dialog = AddConfigDialog(self, self.post_configuration)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Ajouter chaque configuration créée par le dialogue
            for new_config in dialog.config_results:
                self.post_configuration.add_specific_config(new_config)
            self.update_table()

    def save_specific_config(self):
        """Sauvegarde toutes les configurations spécifiques"""
        try:
            # Utiliser la nouvelle méthode de sauvegarde sans mise à jour du planning
            self.main_window.save_post_configuration(self.post_configuration)
            self.main_window.save_data()
            QMessageBox.information(self, "Succès", 
                                  "Configurations spécifiques sauvegardées avec succès")
            
            # Message indiquant que le planning n'est pas automatiquement mis à jour
            QMessageBox.information(self, "Information", 
                "La configuration a été sauvegardée. Pour appliquer ces changements, \n"
                "vous devrez générer manuellement un nouveau planning.")
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", 
                               f"Erreur lors de la sauvegarde : {str(e)}")
            logger.error(f"Erreur sauvegarde config spécifique: {e}", 
                        exc_info=True)
            
            
            
class DragSelectCalendar(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_dates = set()
        
        # Configuration visuelle
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        
        # Connecter directement le signal clicked
        self.clicked.connect(self.on_date_clicked)

    def on_date_clicked(self, qdate):
        """Gère la sélection/désélection d'une date"""
        date = qdate.toPyDate()
        
        # Toggle la sélection
        if date in self.selected_dates:
            self.selected_dates.remove(date)
        else:
            self.selected_dates.add(date)
        
        self.updateCells()

    def paintCell(self, painter, rect, date):
        """Affiche les cellules du calendrier"""
        super().paintCell(painter, rect, date)
        
        py_date = date.toPyDate()
        if py_date in self.selected_dates:
            # Dessiner le fond bleu pour les dates sélectionnées
            painter.fillRect(rect, QColor(173, 216, 230, 180))
            
            # Redessiner le texte pour qu'il soit bien visible
            text = str(date.day())
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def getSelectedDates(self):
        """Retourne la liste des dates sélectionnées"""
        return sorted(list(self.selected_dates))

    def clearSelection(self):
        """Efface toutes les sélections"""
        self.selected_dates.clear()
        self.updateCells()

class AddConfigDialog(QDialog):
    def __init__(self, parent=None, post_configuration=None, existing_config=None, existing_dates=None, edit_date=None):
        super().__init__(parent)
        self.post_configuration = post_configuration
        self.existing_config = existing_config
        self.existing_dates = existing_dates or []
        self.edit_date = edit_date  # Nouvelle propriété pour stocker la date à éditer
        self.config_results = []
        
        # Configuration de la fenêtre
        self.setWindowTitle("Configuration des postes spécifiques")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
            QGroupBox {
                border: 2px solid #e1e4e8;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2d3436;
            }
            QLabel {
                color: #2d3436;
                font-size: 13px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2475a8;
            }
            QPushButton#cancelButton {
                background-color: #e74c3c;
            }
            QPushButton#cancelButton:hover {
                background-color: #c0392b;
            }
            QComboBox {
                background-color: white;
                border: 2px solid #e1e4e8;
                border-radius: 4px;
                padding: 5px;
                min-width: 100px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QSpinBox {
                background-color: white;
                border: 2px solid #e1e4e8;
                border-radius: 4px;
                padding: 5px;
            }
            QSpinBox:hover {
                border-color: #3498db;
            }
            QTableWidget {
                border: 2px solid #e1e4e8;
                border-radius: 4px;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
                font-weight: bold;
                color: #2d3436;
            }
        """)
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)
        
        # ==== Panneau gauche (Calendrier) ====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        calendar_group = QGroupBox("Sélection des jours")
        calendar_layout = QVBoxLayout(calendar_group)
        
        # En-tête avec stats et information sur le jour en cours d'édition
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        
        self.selection_label = QLabel("0 jours sélectionnés")
        self.selection_label.setStyleSheet("color: #3498db; font-weight: bold;")
        stats_layout.addWidget(self.selection_label)
        
        # Ajouter une information sur le jour en cours d'édition si disponible
        if self.edit_date:
            cal = France()  # Calendrier français pour détecter les jours fériés
            day_type = self.get_day_type_label(self.edit_date, cal)
            edit_info = QLabel(f"Édition du {self.edit_date.strftime('%d/%m/%Y')} ({day_type})")
            edit_info.setStyleSheet("color: #e74c3c; font-weight: bold; margin-left: 20px;")
            stats_layout.addWidget(edit_info)
        
        stats_layout.addStretch()
        calendar_layout.addWidget(stats_widget)
        
        # Calendrier amélioré
        self.calendar = ImprovedDragSelectCalendar(self.edit_date)
        self.calendar.selectionChanged.connect(self.update_selection_count)
        calendar_layout.addWidget(self.calendar)
        
        # Si on a des dates existantes ou une date d'édition, les pré-sélectionner
        if self.existing_dates:
            for date in self.existing_dates:
                self.calendar.selected_dates.add(date)
            self.calendar.updateCells()
        elif self.edit_date:
            # Si c'est une édition d'une date spécifique
            self.calendar.selected_dates.add(self.edit_date)
            self.calendar.updateCells()
        
        self.update_selection_count()
        
        # Instructions
        instructions = QLabel(
            "• Cliquez sur les dates à configurer\n"
            "• Les dates sélectionnées apparaissent en bleu\n"
            "• Configurations existantes en vert"
        )
        instructions.setStyleSheet("color: #7f8c8d; font-style: italic;")
        calendar_layout.addWidget(instructions)
        
        left_layout.addWidget(calendar_group)
        
        # ==== Panneau droit (Configuration) ====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Configuration du type de jour
        day_type_group = QGroupBox("Type de jour")
        day_type_layout = QVBoxLayout(day_type_group)
        self.day_type_combo = QComboBox()
        self.day_type_combo.addItems(["Semaine", "Samedi", "Dimanche/Férié"])
        
        # Si on a une date d'édition, sélectionner automatiquement le bon type de jour
        if self.edit_date:
            day_type = self.get_day_type(self.edit_date)
            index = self.day_type_combo.findText(day_type)
            if index >= 0:
                self.day_type_combo.setCurrentIndex(index)
        # Sinon, si on édite une configuration existante, sélectionner le bon type de jour
        elif self.existing_config:
            index = self.day_type_combo.findText(self.existing_config.apply_to)
            if index >= 0:
                self.day_type_combo.setCurrentIndex(index)
        
        self.day_type_combo.currentIndexChanged.connect(self.on_day_type_changed)
        day_type_layout.addWidget(self.day_type_combo)
        
        right_layout.addWidget(day_type_group)
        
        # Configuration des postes
        posts_group = QGroupBox("Configuration des postes")
        self.posts_layout = QGridLayout(posts_group)
        self.init_posts_grid()
        
        right_layout.addWidget(posts_group)
        
        # Boutons d'action
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        apply_button = QPushButton("Appliquer")
        apply_button.setFixedWidth(120)
        apply_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Annuler")
        cancel_button.setObjectName("cancelButton")
        cancel_button.setFixedWidth(120)
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(apply_button)
        buttons_layout.addWidget(cancel_button)
        right_layout.addLayout(buttons_layout)
        
        # Ajout des panneaux au layout principal
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)

    def get_day_type(self, date_obj):
        """Détermine le type de jour (Semaine, Samedi, Dimanche/Férié) en fonction de la date"""
        cal = France()  # Calendrier français pour détecter les jours fériés
        
        # Jour férié ou pont -> Dimanche/Férié
        if cal.is_holiday(date_obj) or DayType.is_bridge_day(date_obj, cal):
            return "Dimanche/Férié"
        # Samedi -> Samedi
        elif date_obj.weekday() == 5:  # 5 = samedi
            return "Samedi"
        # Dimanche -> Dimanche/Férié
        elif date_obj.weekday() == 6:  # 6 = dimanche
            return "Dimanche/Férié"
        # Jour de semaine -> Semaine
        else:
            return "Semaine"
    
    def get_day_type_label(self, date_obj, cal=None):
        """Retourne un libellé plus détaillé du type de jour pour l'affichage"""
        if cal is None:
            cal = France()
            
        if cal.is_holiday(date_obj):
            return "Jour férié"
        elif DayType.is_bridge_day(date_obj, cal):
            return "Jour de pont"
        elif date_obj.weekday() == 5:
            return "Samedi"
        elif date_obj.weekday() == 6:
            return "Dimanche"
        else:
            return f"Jour de semaine ({['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi'][date_obj.weekday()]})"

    def update_selection_count(self):
        """Met à jour le compteur de dates sélectionnées"""
        count = len(self.calendar.selected_dates)
        self.selection_label.setText(f"{count} jour{'s' if count > 1 else ''} sélectionné{'s' if count > 1 else ''}")
        
    def on_day_type_changed(self, index):
        """Met à jour les valeurs par défaut selon le type de jour"""
        day_type = self.day_type_combo.currentText()
        default_config = None

        if day_type == "Semaine":
            default_config = self.post_configuration.weekday
        elif day_type == "Samedi":
            default_config = self.post_configuration.saturday
        else:  # Dimanche/Férié
            default_config = self.post_configuration.sunday_holiday

        if default_config:
            for post_type, spinbox in self.post_spinboxes.items():
                spinbox.setValue(default_config.get(post_type, PostConfig()).total)
    def init_posts_grid(self):
        """Initialise la grille des postes en colonnes avec des spinboxes améliorées"""
        POSTS_PER_COLUMN = 6
        COLUMNS = 4
        
        # En-têtes
        header_style = "font-weight: bold; color: #2c3e50; padding: 5px; font-size: 14px;"
        for col in range(COLUMNS):
            header = QLabel("Type de poste")
            header.setStyleSheet(header_style)
            self.posts_layout.addWidget(header, 0, col * 2)
            
            header = QLabel("Nombre")
            header.setStyleSheet(header_style)
            self.posts_layout.addWidget(header, 0, col * 2 + 1)

        # Initialisation des spinboxes
        self.post_spinboxes = {}
        all_posts = ALL_POST_TYPES.copy()
        
        spinbox_style = """
            QSpinBox {
                min-height: 30px;
                min-width: 80px;
                padding: 5px;
                font-size: 14px;
                font-weight: bold;
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                height: 15px;
                border-radius: 2px;
                background-color: #f0f0f0;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #e0e0e0;
            }
        """
        
        for index, post_type in enumerate(all_posts):
            col = (index // POSTS_PER_COLUMN) * 2
            row = (index % POSTS_PER_COLUMN) + 1
            
            # Label du poste avec fond coloré
            post_widget = QWidget()
            post_layout = QHBoxLayout(post_widget)
            post_layout.setContentsMargins(5, 2, 5, 2)
            
            post_label = QLabel(post_type)
            post_label.setStyleSheet("""
                padding: 3px 8px;
                background-color: #f0f2f5;
                border-radius: 3px;
                color: #2c3e50;
                font-size: 14px;
                font-weight: bold;
            """)
            post_layout.addWidget(post_label)
            
            self.posts_layout.addWidget(post_widget, row, col)
            
            # SpinBox avec style moderne et taille augmentée
            spinbox = CustomSpinBox()
            spinbox.setRange(0, 20)
            spinbox.setStyleSheet(spinbox_style)
            
            # Si on édite une configuration existante, utiliser les valeurs existantes
            if self.existing_config and post_type in self.existing_config.post_counts:
                spinbox.setValue(self.existing_config.post_counts[post_type])
            else:
                # Sinon, utiliser les valeurs par défaut selon le type de jour
                day_type = self.day_type_combo.currentText()
                if day_type == "Semaine":
                    default_config = self.post_configuration.weekday
                elif day_type == "Samedi":
                    default_config = self.post_configuration.saturday
                else:  # Dimanche/Férié
                    default_config = self.post_configuration.sunday_holiday
                spinbox.setValue(default_config.get(post_type, PostConfig()).total)
            
            self.post_spinboxes[post_type] = spinbox
            self.posts_layout.addWidget(spinbox, row, col + 1)
        
        # Ajuster l'espacement
        self.posts_layout.setHorizontalSpacing(15)
        self.posts_layout.setVerticalSpacing(10)

    def update_selection_count(self):
        """Met à jour le compteur de dates sélectionnées"""
        count = len(self.calendar.selected_dates)
        self.selection_label.setText(f"{count} jour{'s' if count > 1 else ''} sélectionné{'s' if count > 1 else ''}")
        
    def on_day_type_changed(self, index):
        """Met à jour les valeurs par défaut selon le type de jour"""
        day_type = self.day_type_combo.currentText()
        default_config = None

        if day_type == "Semaine":
            default_config = self.post_configuration.weekday
        elif day_type == "Samedi":
            default_config = self.post_configuration.saturday
        else:  # Dimanche/Férié
            default_config = self.post_configuration.sunday_holiday

        if default_config:
            for post_type, spinbox in self.post_spinboxes.items():
                spinbox.setValue(default_config.get(post_type, PostConfig()).total)

    def get_config(self):
        """Récupère la configuration actuelle"""
        selected_dates = self.calendar.getSelectedDates()
        if not selected_dates:
            return None
            
        # Un seul dictionnaire de configuration avec tous les paramètres
        return {
            'apply_to': self.day_type_combo.currentText(),
            'post_counts': {
                post_type: spinbox.value()
                for post_type, spinbox in self.post_spinboxes.items()
                if spinbox.value() > 0
            }
        }

    def accept(self):
        """Valide et accepte les configurations"""
        selected_dates = self.calendar.getSelectedDates()
        if not selected_dates:
            QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez sélectionner au moins une date dans le calendrier"
            )
            return

        # Récupérer la configuration
        config = self.get_config()
        if not config or not config['post_counts']:
            QMessageBox.warning(
                self, 
                "Attention", 
                "Veuillez configurer au moins un poste"
            )
            return

        # Créer les configurations pour chaque date
        self.config_results = []
        for date in selected_dates:
            specific_config = SpecificPostConfig(
                start_date=date,
                end_date=date,
                apply_to=config['apply_to'],
                post_counts=config['post_counts'].copy()
            )
            self.config_results.append(specific_config)

        super().accept()
        
        
        
class ImprovedDragSelectCalendar(DragSelectCalendar):
    """Version améliorée du calendrier avec surlignage du jour en cours d'édition"""
    
    def __init__(self, edit_date=None, parent=None):
        super().__init__(parent)
        self.edit_date = edit_date
        self.cal_france = France()  # Calendrier français pour détecter les jours fériés
        
        # Si une date d'édition est fournie, régler le calendrier sur le mois correspondant
        if edit_date:
            self.setSelectedDate(QDate(edit_date.year, edit_date.month, edit_date.day))
    
    def paintCell(self, painter, rect, date):
        """Affiche les cellules du calendrier avec des indicateurs visuels améliorés"""
        # Récupérer la date Python
        py_date = date.toPyDate()
        
        # Définir la couleur de fond en fonction du type de jour
        if self.cal_france.is_holiday(py_date):
            # Jour férié
            background_color = QColor(252, 228, 236)  # Rose clair
        elif DayType.is_bridge_day(py_date, self.cal_france):
            # Jour de pont
            background_color = QColor(255, 243, 224)  # Orange clair
        elif date.dayOfWeek() == 7:  # 7 = dimanche dans Qt
            # Dimanche
            background_color = QColor(243, 229, 245)  # Violet clair
        elif date.dayOfWeek() == 6:  # 6 = samedi dans Qt
            # Samedi
            background_color = QColor(232, 237, 245)  # Bleu clair
        else:
            # Jour normal
            background_color = QColor(255, 255, 255)  # Blanc
        
        # Remplir le fond
        painter.fillRect(rect, background_color)
        
        # Si c'est une date sélectionnée, ajouter une surcouche bleue semi-transparente
        if py_date in self.selected_dates:
            painter.fillRect(rect, QColor(173, 216, 230, 180))
        
        # Si c'est la date en cours d'édition, ajouter une bordure plus visible
        if self.edit_date and py_date == self.edit_date:
            pen = painter.pen()
            painter.setPen(QColor(52, 152, 219))  # Bleu
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            painter.setPen(pen)
        
        # Dessiner le texte (jour)
        text = str(date.day())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        
        
class PostConfigurationWidget(QWidget):
    custom_posts_updated = pyqtSignal()  # Signal for custom posts updates
    
    # Ajoutez sync_scroll comme méthode statique pour la lisibilité
    @staticmethod
    def sync_scroll(tables):
        if not tables:
            return

        main_scrollbar = tables[0].verticalScrollBar()

        def update_scroll():
            for table in tables[1:]:
                table.verticalScrollBar().setValue(main_scrollbar.value())

        main_scrollbar.valueChanged.connect(update_scroll)

        for table in tables[1:]:
            table.verticalScrollBar().valueChanged.connect(lambda val: main_scrollbar.setValue(val))

    def __init__(self, post_configuration, main_window):
        super().__init__()
        self.post_configuration = post_configuration
        self.main_window = main_window
        self.config_tables = {}
        self.custom_posts = {}
        self.load_custom_posts()
        self.clean_invalid_custom_posts()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        tab_widget = QTabWidget()

        
        # Onglet pour les médecins
        doctors_tab = QWidget()
        doctors_layout = QVBoxLayout(doctors_tab)
        doctors_config = self.create_config_tab(
            [("Semaine", self.post_configuration.weekday),
            ("Samedi", self.post_configuration.saturday),
            ("Dimanche/Férié", self.post_configuration.sunday_holiday)],
            "Médecins"
        )
        doctors_layout.addWidget(doctors_config)
        
        # Boutons en ligne pour les médecins avec style harmonisé
        doctors_button_layout = QHBoxLayout()
        
        add_custom_post_button = QPushButton("Ajouter un poste")
        add_custom_post_button.setObjectName("addButton")
        add_custom_post_button.setIcon(QIcon("icons/ajouter.png"))
        add_custom_post_button.clicked.connect(self.add_custom_post)
        add_custom_post_button.setStyleSheet(ADD_BUTTON_STYLE)
        
        save_doctors_button = QPushButton("Enregistrer la configuration des médecins")
        save_doctors_button.setStyleSheet(ACTION_BUTTON_STYLE)
        save_doctors_button.clicked.connect(lambda: self.save_configuration("Médecin"))
        
        doctors_button_layout.addWidget(add_custom_post_button)
        doctors_button_layout.addStretch()
        doctors_button_layout.addWidget(save_doctors_button)
        doctors_layout.addLayout(doctors_button_layout)
        
        tab_widget.addTab(doctors_tab, "Postes Médecins")

        # Onglet pour les CAT
        cats_tab = QWidget()
        cats_layout = QVBoxLayout(cats_tab)
        cats_config = self.create_config_tab(
            [("CAT_Semaine", self.post_configuration.cat_weekday),
            ("CAT_Samedi", self.post_configuration.cat_saturday),
            ("CAT_Dimanche/férié", self.post_configuration.cat_sunday_holiday)],
            "CAT"
        )
        cats_layout.addWidget(cats_config)
        
        # Bouton de sauvegarde pour les CAT avec style harmonisé
        cats_button_layout = QHBoxLayout()
        save_cats_button = QPushButton("Enregistrer la configuration des CAT")
        save_cats_button.setStyleSheet(ACTION_BUTTON_STYLE)
        save_cats_button.clicked.connect(lambda: self.save_configuration("CAT"))
        cats_button_layout.addStretch()
        cats_button_layout.addWidget(save_cats_button)
        cats_layout.addLayout(cats_button_layout)
        
        tab_widget.addTab(cats_tab, "Postes CAT")
        
        # Après avoir ajouté les tableaux au dictionnaire config_tables
        self.sync_scroll([
            self.config_tables["Semaine"],
            self.config_tables["Samedi"],
            self.config_tables["Dimanche/Férié"],
            self.config_tables["CAT_Semaine"],
            self.config_tables["CAT_Samedi"],
            self.config_tables["CAT_Dimanche/férié"]
        ])
        
        # Modification de l'initialisation de SpecificConfigWidget
        self.specific_config_tab = SpecificConfigWidget(
            self.post_configuration,
            self.start_date if hasattr(self, 'start_date') else None,
            self.end_date if hasattr(self, 'end_date') else None,
            self.main_window  # Passage de la référence main_window
        )
        tab_widget.addTab(self.specific_config_tab, "Jours spécifiques")
        
        layout.addWidget(tab_widget)

    def update_dates(self, start_date, end_date):
        self.specific_config_tab.planning_start_date = start_date
        self.specific_config_tab.planning_end_date = end_date
        self.specific_config_tab.update_table()


    def create_config_tab(self, configs, title):
        """Crée un nouvel onglet de configuration"""
        tab = QWidget()
        tab_layout = QHBoxLayout(tab)
        
        for day_type, config in configs:
            column_layout = QVBoxLayout()
            column_layout.addWidget(QLabel(day_type))
            table = self.create_config_table(config, day_type)
            column_layout.addWidget(table)
            tab_layout.addLayout(column_layout)
        
        return tab
    
    def create_config_table(self, config, day_type):
        """Crée une nouvelle table de configuration"""
        table = QTableWidget(self)
        table.setObjectName(day_type)
        table.setColumnCount(3)  # Retour à 3 colonnes
        table.setHorizontalHeaderLabels(["Type de poste", "Nombre total", "Actions"])

        all_posts = self.get_posts_for_day_type(day_type)
        table.setRowCount(len(all_posts))
        
        for row, post_type in enumerate(all_posts):
            # Nom du poste
            name_item = QTableWidgetItem(post_type)
            if post_type in self.custom_posts:
                name_item.setBackground(QBrush(self.custom_posts[post_type].color))
                
            # Pour NL dans la config CAT en semaine, modifier le texte
            if post_type == "NL" and "CAT" in day_type and "Semaine" in day_type:
                name_item.setText("NL/NLv")
                
            table.setItem(row, 0, name_item)
            
            # Création du widget pour la colonne "Nombre total"
            if post_type == "NL" and "CAT" in day_type and "Semaine" in day_type:
                # Créer un widget conteneur pour les deux spinbox
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(2, 2, 2, 2)
                layout.setSpacing(2)
                
                # Spinbox pour NL
                nl_spinbox = CustomSpinBox()
                nl_spinbox.setRange(0, 20)
                nl_spinbox.setValue(config.get(post_type, PostConfig()).total)
                nl_spinbox.setFixedWidth(50)  # Réduire la largeur
                
                # Spinbox pour NLv
                nlv_spinbox = CustomSpinBox()
                nlv_spinbox.setRange(0, 20)
                nlv_spinbox.setValue(config.get("NLv", PostConfig()).total)
                nlv_spinbox.setFixedWidth(50)  # Réduire la largeur
                
                layout.addWidget(nl_spinbox)
                layout.addWidget(nlv_spinbox)
                
                table.setCellWidget(row, 1, container)
            else:
                # SpinBox normal pour les autres postes
                spinbox = CustomSpinBox()
                spinbox.setRange(0, 20)
                spinbox.setValue(config.get(post_type, PostConfig()).total)
                table.setCellWidget(row, 1, spinbox)

            # Pour les postes personnalisés uniquement
            if post_type in self.custom_posts:
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                edit_button = QPushButton()
                edit_button.setIcon(QIcon("icons/edition.png"))
                edit_button.setIconSize(QSize(20, 20))
                edit_button.setFixedSize(32, 32)
                edit_button.setToolTip("Modifier le poste personnalisé")
                edit_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)

                delete_button = QPushButton()
                delete_button.setIcon(QIcon("icons/supprimer.png"))
                delete_button.setIconSize(QSize(20, 20))
                delete_button.setFixedSize(32, 32)
                delete_button.setToolTip("Supprimer le poste personnalisé")
                delete_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
                
                edit_button.clicked.connect(lambda _, p=post_type: self.edit_custom_post(p))
                delete_button.clicked.connect(lambda _, p=post_type: self.remove_custom_post(p))
                
                actions_layout.addWidget(edit_button)
                actions_layout.addWidget(delete_button)
                table.setCellWidget(row, 2, actions_widget)
            else:
                empty_widget = QWidget()
                table.setCellWidget(row, 2, empty_widget)

        # Ajuster l'affichage de la table
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 140)
        
        self.config_tables[day_type] = table
        return table
    
    def get_posts_for_day_type(self, day_type: str) -> list:
        """Obtient tous les postes (standards + personnalisés) pour un type de jour"""
        logger.debug(f"Récupération des postes pour {day_type}")
        
        day_type_mapping = {
            "Semaine": "weekday",
            "Samedi": "saturday",
            "Dimanche/Férié": "sunday_holiday",
            "CAT_Semaine": "weekday",
            "CAT_Samedi": "saturday",
            "CAT_Dimanche/férié": "sunday_holiday"
        }

        all_posts = list(ALL_POST_TYPES)
        real_day_type = day_type_mapping.get(day_type)
        is_cat = day_type.startswith("CAT_")

        # Debug logs
        logger.debug(f"Posts standard : {all_posts}")
        logger.debug(f"Posts personnalisés disponibles : {list(self.custom_posts.keys())}")

        if real_day_type:
            for name, post in self.custom_posts.items():
                logger.debug(f"Vérification du poste {name}:")
                logger.debug(f"- Types de jour: {post.day_types}")
                logger.debug(f"- Type d'assignation: {post.assignment_type}")
                
                if real_day_type in post.day_types:
                    is_eligible = False
                    if is_cat and post.assignment_type in ['cats', 'both']:
                        logger.debug(f"- Éligible pour CAT")
                        is_eligible = True
                    elif not is_cat and post.assignment_type in ['doctors', 'both']:
                        logger.debug(f"- Éligible pour médecins")
                        is_eligible = True
                    
                    if is_eligible and name not in all_posts:
                        all_posts.append(name)
                        logger.debug(f"- Poste {name} ajouté à la liste")

        logger.debug(f"Liste finale pour {day_type}: {all_posts}")
        return all_posts
    def add_custom_post(self):
        """Ajoute un nouveau poste personnalisé"""
        dialog = NewPostDialog(self, existing_posts=self.custom_posts,
                            statistic_groups=self.define_statistic_groups())
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_post = dialog.get_post()
            if new_post:
                logger.info(f"Nouveau poste créé : {new_post.name}")
                logger.debug(f"- Types de jour: {new_post.day_types}")
                logger.debug(f"- Type d'assignation: {new_post.assignment_type}")
                
                # Ajouter aux custom posts
                self.custom_posts[new_post.name] = new_post
                logger.debug(f"Poste ajouté au dictionnaire custom_posts")
                
                # Ajouter aux configurations appropriées
                for day_type in new_post.day_types:
                    if new_post.assignment_type in ["Médecin", "Les deux"]:
                        config = getattr(self.post_configuration, day_type)
                        config[new_post.name] = PostConfig(total=1)
                        logger.debug(f"Ajouté à la configuration {day_type} des médecins")
                    
                    if new_post.assignment_type in ["CAT", "Les deux"]:
                        cat_config = getattr(self.post_configuration, f"cat_{day_type}")
                        cat_config[new_post.name] = PostConfig(total=1)
                        logger.debug(f"Ajouté à la configuration {day_type} des CAT")
                
                # Sauvegarder et mettre à jour
                self.save_custom_posts()
                logger.debug("Custom posts sauvegardés")
                
                # Mise à jour des tables
                for day_type, table in self.config_tables.items():
                    logger.debug(f"Mise à jour de la table {day_type}")
                    self.refresh_table(table, day_type)
                
                # Émettre le signal
                self.custom_posts_updated.emit()
                
                logger.info(f"Poste {new_post.name} ajouté avec succès")
                QMessageBox.information(self, "Succès", f"Le poste {new_post.name} a été ajouté avec succès")
                
    def get_action_button_style(self):
        return """
            QPushButton {
                background-color: #f8f8f8;
                color: #333;
                border: 1px solid #ddd;
                padding: 3px 8px;
                font-size: 11px;
                border-radius: 2px;
                margin: 1px;
                max-width: 60px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """
        
    def _update_config_tables(self):
        """Met à jour les tables de configuration avec tous les postes"""
        configs = [
            ("Semaine", self.post_configuration.weekday),
            ("Samedi", self.post_configuration.saturday),
            ("Dimanche/Férié", self.post_configuration.sunday_holiday),
            ("CAT_Semaine", self.post_configuration.cat_weekday),
            ("CAT_Samedi", self.post_configuration.cat_saturday),
            ("CAT_Dimanche/férié", self.post_configuration.cat_sunday_holiday)
        ]

        for day_type, config in configs:
            table = self.config_tables.get(day_type)
            if table:
                # Sauvegarder la position du scroll actuelle
                current_scroll = table.verticalScrollBar().value()
                
                # Récupérer tous les postes pour ce type de jour
                all_posts = self.get_posts_for_day_type(day_type)
                
                # Mettre à jour la table
                table.setRowCount(0)  # Effacer d'abord la table
                table.setRowCount(len(all_posts))
                table.setColumnCount(3)
                table.setHorizontalHeaderLabels(["Type de poste", "Nombre total", "Actions"])
                
                for row, post_type in enumerate(all_posts):
                    # Création et ajout du nom du poste
                    name_item = QTableWidgetItem(post_type)
                    if post_type in self.custom_posts:
                        name_item.setBackground(QBrush(self.custom_posts[post_type].color))
                    table.setItem(row, 0, name_item)
                    
                    # SpinBox pour le nombre
                    spinbox = CustomSpinBox()
                    spinbox.setRange(0, 20)
                    spinbox.setValue(config.get(post_type, PostConfig()).total)
                    table.setCellWidget(row, 1, spinbox)
                    
                    # Ajouter les boutons d'action pour les postes personnalisés
                    if post_type in self.custom_posts:
                        actions_widget = QWidget()
                        actions_layout = QHBoxLayout(actions_widget)
                        actions_layout.setContentsMargins(2, 2, 2, 2)
                        actions_layout.setSpacing(4)
                        
                        edit_button = QPushButton()
                        edit_button.setIcon(QIcon("icons/edition.png"))
                        edit_button.setToolTip("Modifier le poste personnalisé")
                        edit_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)

                        delete_button = QPushButton()
                        delete_button.setIcon(QIcon("icons/supprimer.png"))
                        delete_button.setToolTip("Supprimer le poste personnalisé")
                        delete_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
                        
                        edit_button.clicked.connect(lambda _, p=post_type: self.edit_custom_post(p))
                        delete_button.clicked.connect(lambda _, p=post_type: self.remove_custom_post(p))
                        
                        actions_layout.addWidget(edit_button)
                        actions_layout.addWidget(delete_button)
                        
                        actions_widget.setLayout(actions_layout)
                        table.setCellWidget(row, 2, actions_widget)
                    else:
                        # Pour les postes standards, on met une cellule vide
                        empty_widget = QWidget()
                        table.setCellWidget(row, 2, empty_widget)
                
                # Restaurer la position du scroll
                table.verticalScrollBar().setValue(current_scroll)
                
                # Ajuster la taille des colonnes
                table.resizeColumnsToContents()
                
                # Optimiser la largeur des colonnes
                header = table.horizontalHeader()
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
                header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
                header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
                
                # Définir une largeur minimale pour la colonne des actions
                table.setColumnWidth(2, 140)
            else:
                print(f"Table non trouvée pour {day_type}")
    
    
    def add_post_to_configurations(self, post):
        """Ajoute un nouveau poste à toutes les configurations appropriées"""
        # Pour les médecins
        if post.assignment_type in ['doctors', 'both']:
            for day_type in post.day_types:
                config = getattr(self.post_configuration, day_type)
                config[post.name] = PostConfig(total=1)
        
        # Pour les CAT
        if post.assignment_type in ['cats', 'both']:
            for day_type in post.day_types:
                config = getattr(self.post_configuration, f'cat_{day_type}')
                config[post.name] = PostConfig(total=1)
                
    def remove_custom_post(self, post_name: str):
        """Supprime un poste personnalisé"""
        if post_name in self.custom_posts:
            confirm = QMessageBox.question(
                self,
                "Confirmation",
                f"Êtes-vous sûr de vouloir supprimer le poste {post_name} ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if confirm == QMessageBox.StandardButton.Yes:
                # Supprimer le poste de la configuration
                post = self.custom_posts[post_name]
                for day_type in post.day_types:
                    if post.assignment_type in ["Médecin", "Les deux"]:
                        if day_type == "weekday":
                            self.post_configuration.weekday.pop(post_name, None)
                        elif day_type == "saturday":
                            self.post_configuration.saturday.pop(post_name, None)
                        elif day_type == "sunday_holiday":
                            self.post_configuration.sunday_holiday.pop(post_name, None)
                    
                    if post.assignment_type in ["CAT", "Les deux"]:
                        if day_type == "weekday":
                            self.post_configuration.cat_weekday.pop(post_name, None)
                        elif day_type == "saturday":
                            self.post_configuration.cat_saturday.pop(post_name, None)
                        elif day_type == "sunday_holiday":
                            self.post_configuration.cat_sunday_holiday.pop(post_name, None)
                
                del self.custom_posts[post_name]
                self.save_custom_posts()
                self.update_all_tables()
                self.custom_posts_updated.emit()
                QMessageBox.information(self, "Succès", f"Le poste {post_name} a été supprimé")

    def save_custom_posts(self):
        """Sauvegarde les postes personnalisés"""
        print("Sauvegarde des postes personnalisés :")  # Debug
        for name, post in self.custom_posts.items():
            print(f"- {name}: {post.day_types}, {post.assignment_type}")  # Debug
        custom_posts_data = {name: post.to_dict() for name, post in self.custom_posts.items()}
        self.main_window.data_persistence.save_custom_posts(custom_posts_data)

    def load_custom_posts(self):
        """Charge les postes personnalisés depuis la persistance"""
        try:
            custom_posts_data = self.main_window.data_persistence.load_custom_posts()
            if custom_posts_data:
                self.custom_posts = {}
                for name, data in custom_posts_data.items():
                    try:
                        if isinstance(data, dict):
                            self.custom_posts[name] = CustomPost.from_dict(data)
                        else:
                            self.custom_posts[name] = data
                        logger.info(f"Poste personnalisé chargé: {name}")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement du poste {name}: {e}")
            self.update_all_tables()
        except Exception as e:
            logger.error(f"Erreur lors du chargement des postes personnalisés: {e}")

    def refresh_custom_posts(self):
        """Rafraîchit la liste des postes personnalisés"""
        new_custom_posts = self.main_window.data_persistence.load_custom_posts()
        if new_custom_posts:
            has_changes = False
            # Vérifier les modifications
            for name, data in new_custom_posts.items():
                if name not in self.custom_posts:
                    try:
                        if isinstance(data, dict):
                            self.custom_posts[name] = CustomPost.from_dict(data)
                        else:
                            self.custom_posts[name] = data
                        has_changes = True
                        logger.info(f"Nouveau poste personnalisé détecté: {name}")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement du poste {name}: {e}")
            
            # Vérifier les suppressions
            for name in list(self.custom_posts.keys()):
                if name not in new_custom_posts:
                    del self.custom_posts[name]
                    has_changes = True
                    logger.info(f"Poste personnalisé supprimé: {name}")
            
            if has_changes:
                self.update_all_tables()
        
    def update_table(self, table: QTableWidget, day_type: str):
        """Met à jour une table spécifique avec les postes standards et personnalisés"""
        current_scroll_position = table.verticalScrollBar().value()
        
        # Récupérer la configuration appropriée
        if "CAT" in day_type:
            config = getattr(self.post_configuration, f"cat_{day_type.lower().replace('cat_', '')}", {})
            assignation_filter = ["CAT", "Les deux"]
        else:
            config = getattr(self.post_configuration, day_type.lower(), {})
            assignation_filter = ["Médecin", "Les deux"]

        # Récupérer tous les postes (standards + personnalisés)
        all_posts = list(ALL_POST_TYPES)
        custom_posts_for_type = [
            post for post in self.custom_posts.values()
            if (day_type.lower().replace("cat_", "") in post.day_types and 
                post.assignment_type in assignation_filter)
        ]
        all_posts.extend([post.name for post in custom_posts_for_type])
        
        # Mettre à jour la table
        table.setRowCount(len(all_posts))
        
        for row, post_type in enumerate(all_posts):
            # Nom du poste
            name_item = QTableWidgetItem(post_type)
            table.setItem(row, 0, name_item)
            
            # Colorer les postes personnalisés
            if post_type in [p.name for p in custom_posts_for_type]:
                custom_post = next(p for p in custom_posts_for_type if p.name == post_type)
                name_item.setBackground(QBrush(custom_post.color))
            
            # SpinBox pour le nombre
            spinbox = CustomSpinBox()
            spinbox.setRange(0, 20)
            spinbox.setValue(config.get(post_type, PostConfig()).total)
            table.setCellWidget(row, 1, spinbox)

        # Restaurer la position du scroll
        table.verticalScrollBar().setValue(current_scroll_position)
        table.resizeColumnsToContents()
        
    def update_all_tables(self):
        """Met à jour toutes les tables de configuration"""
        # Mettre à jour les tables des médecins
        for day_type in ["Semaine", "Samedi", "Dimanche/Férié"]:
            table = self.config_tables.get(day_type)
            if table:
                self.refresh_table(table, day_type)

        # Mettre à jour les tables des CAT
        for day_type in ["CAT_Semaine", "CAT_Samedi", "CAT_Dimanche/férié"]:
            table = self.config_tables.get(day_type)
            if table:
                self.refresh_table(table, day_type)


    def refresh_table(self, table: QTableWidget, day_type: str):
        """Rafraîchit une table spécifique"""
        current_scroll = table.verticalScrollBar().value()
        
        # Obtenir tous les postes pour ce type de jour
        all_posts = self.get_posts_for_day_type(day_type)
        
        # Mise à jour de la table
        table.setRowCount(len(all_posts))
        
        # Obtenir la configuration appropriée
        config_mapping = {
            "Semaine": self.post_configuration.weekday,
            "Samedi": self.post_configuration.saturday,
            "Dimanche/Férié": self.post_configuration.sunday_holiday,
            "CAT_Semaine": self.post_configuration.cat_weekday,
            "CAT_Samedi": self.post_configuration.cat_saturday,
            "CAT_Dimanche/férié": self.post_configuration.cat_sunday_holiday
        }
        config = config_mapping.get(day_type, {})

        for row, post_type in enumerate(all_posts):
            # Nom du poste
            name_item = QTableWidgetItem(post_type)
            if post_type in self.custom_posts:
                custom_post = self.custom_posts[post_type]
                name_item.setBackground(QBrush(custom_post.color))
                # Ajouter les boutons d'action
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                edit_button = QPushButton()
                edit_button.setIcon(QIcon("icons/edition.png"))
                edit_button.setIconSize(QSize(20, 20))
                edit_button.setFixedSize(32, 32)
                edit_button.setToolTip("Modifier le poste personnalisé")
                edit_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)

                delete_button = QPushButton()
                delete_button.setIcon(QIcon("icons/supprimer.png"))
                delete_button.setIconSize(QSize(20, 20))
                delete_button.setFixedSize(32, 32)
                delete_button.setToolTip("Supprimer le poste personnalisé")
                delete_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
                
                edit_button.clicked.connect(lambda _, n=post_type: self.edit_custom_post(n))
                delete_button.clicked.connect(lambda _, n=post_type: self.remove_custom_post(n))
                
                actions_layout.addWidget(edit_button)
                actions_layout.addWidget(delete_button)
                
                table.setCellWidget(row, 2, actions_widget)
            
            table.setItem(row, 0, name_item)
            
            # Spinbox pour le nombre
            spinbox = CustomSpinBox()
            spinbox.setRange(0, 20)
            spinbox.setValue(config.get(post_type, PostConfig()).total)
            table.setCellWidget(row, 1, spinbox)

        # Restaurer le scroll
        table.verticalScrollBar().setValue(current_scroll)
        table.resizeColumnsToContents()
    
    def save_configuration(self, config_type):
        """Sauvegarde la configuration en préservant explicitement les valeurs nulles"""
        if config_type == "Médecin":
            configs = [
                ("Semaine", self.post_configuration.weekday),
                ("Samedi", self.post_configuration.saturday),
                ("Dimanche/Férié", self.post_configuration.sunday_holiday)
            ]
        elif config_type == "CAT":
            configs = [
                ("CAT_Semaine", self.post_configuration.cat_weekday),
                ("CAT_Samedi", self.post_configuration.cat_saturday),
                ("CAT_Dimanche/férié", self.post_configuration.cat_sunday_holiday)
            ]
        else:
            return

        for day_type, config in configs:
            table = self.config_tables.get(day_type)
            if table:
                # Réinitialiser la configuration pour ce type de jour
                config.clear()
                
                # Parcourir toutes les lignes et sauvegarder TOUTES les valeurs
                for row in range(table.rowCount()):
                    post_type = table.item(row, 0).text()
                    cell_widget = table.cellWidget(row, 1)
                    
                    if isinstance(cell_widget, QWidget) and cell_widget.layout() and cell_widget.layout().count() == 2:
                        # Cas spécial NL/NLv
                        nl_spinbox = cell_widget.layout().itemAt(0).widget()
                        nlv_spinbox = cell_widget.layout().itemAt(1).widget()
                        if post_type == "NL/NLv":
                            config["NL"] = PostConfig(total=nl_spinbox.value())
                            config["NLv"] = PostConfig(total=nlv_spinbox.value())
                    else:
                        # Sauvegarder la valeur, même si elle est nulle
                        config[post_type] = PostConfig(total=cell_widget.value())

        try:
            # Sauvegarder la configuration complète
            self.main_window.save_post_configuration(self.post_configuration)
            self.main_window.save_data()
            QMessageBox.information(self, "Succès", 
                                f"Configuration des {config_type} sauvegardée")
            
            QMessageBox.information(self, "Information", 
                "La configuration a été sauvegardée. Pour appliquer ces changements, \n"
                "vous devrez générer manuellement un nouveau planning.")
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", 
                            f"Erreur lors de la sauvegarde : {str(e)}")
            logger.error(f"Erreur sauvegarde config spécifique: {e}", 
                        exc_info=True)


    def update_configuration(self, new_post_configuration):
        self.post_configuration = new_post_configuration
        for day_type, config in [
            ("Semaine", self.post_configuration.weekday),
            ("Samedi", self.post_configuration.saturday),
            ("Dimanche/Férié", self.post_configuration.sunday_holiday),
            ("CAT_Semaine", self.post_configuration.cat_weekday),
            ("CAT_Samedi", self.post_configuration.cat_saturday),
            ("CAT_Dimanche/férié", self.post_configuration.cat_sunday_holiday)
        ]:
            table = self.config_tables.get(day_type)
            if table:
                for row in range(table.rowCount()):
                    post_type = table.item(row, 0).text()
                    cell_widget = table.cellWidget(row, 1)
                    
                    # Vérifier si c'est le widget spécial NL/NLv
                    if isinstance(cell_widget, QWidget) and cell_widget.layout() and cell_widget.layout().count() == 2:
                        nl_spinbox = cell_widget.layout().itemAt(0).widget()
                        nlv_spinbox = cell_widget.layout().itemAt(1).widget()
                        nl_spinbox.setValue(config.get("NL", PostConfig()).total)
                        nlv_spinbox.setValue(config.get("NLv", PostConfig()).total)
                    else:
                        if post_type == "NL/NLv":
                            post_type = "NL"
                        if isinstance(cell_widget, QSpinBox):
                            cell_widget.setValue(config.get(post_type, PostConfig()).total)
    
    def update_custom_posts_list(self):
        """Met à jour la liste des postes personnalisés"""
        self.custom_posts_list.setRowCount(len(self.custom_posts))
        
        for row, (name, post) in enumerate(self.custom_posts.items()):
            # Nom
            self.custom_posts_list.setItem(row, 0, QTableWidgetItem(name))
            
            # Horaires
            horaires = f"{post.start_time.strftime('%H:%M')} - {post.end_time.strftime('%H:%M')}"
            self.custom_posts_list.setItem(row, 1, QTableWidgetItem(horaires))
            
            # Types de jour
            types_jour = ", ".join(post.day_types)
            self.custom_posts_list.setItem(row, 2, QTableWidgetItem(types_jour))
            
            # Assignation
            self.custom_posts_list.setItem(row, 3, QTableWidgetItem(post.assignment_type))
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            edit_button = QPushButton()
            edit_button.setIcon(QIcon("icons/edition.png"))
            edit_button.setToolTip("Modifier le poste personnalisé")

            delete_button = QPushButton()
            delete_button.setIcon(QIcon("icons/supprimer.png"))
            delete_button.setToolTip("Supprimer le poste personnalisé")
            
            edit_button.clicked.connect(lambda _, n=name: self.edit_custom_post(n))
            delete_button.clicked.connect(lambda _, n=name: self.remove_custom_post(n))
            
            actions_layout.addWidget(edit_button)
            actions_layout.addWidget(delete_button)
            self.custom_posts_list.setCellWidget(row, 4, actions_widget)
        
        self.custom_posts_list.resizeColumnsToContents()

    def define_statistic_groups(self):
        """
        Définit tous les groupes de postes possibles pour le menu déroulant.
        Cette méthode est utilisée par PostConfigurationWidget et NewPostDialog.
        """
        # Groupes Weekend
        weekend_groups = [
            ("Consultations Samedi", [
                "CmS",  # Consultation matin samedi
            ]),
            ("Consultations Dimanche/Férié", [
                "CmD",  # Consultation matin dimanche/férié
            ]),
            ("Consultations Weekend/Férié", [
                "CaSD",  # Consultation après-midi samedi + dimanche/férié
                "CsSD",  # Consultation soir samedi + dimanche/férié
            ]),
            ("Visites Samedi", [
                "VmS",  # Visites matin samedi
            ]),
            ("Visites Dimanche/Férié", [
                "VmD",  # Visites matin dimanche/férié
            ]),
            ("Visites Weekend/Férié", [
                "VaSD",  # Visites après-midi samedi + dimanche/férié
            ]),
            ("Gardes Weekend/Férié", [
                "NAMw",  # NA + NM weekends/férié
                "NLw",   # NL Weekend/férié + vendredi
            ])
        ]

        # Groupes Semaine
        weekday_groups = [
            ("Consultations Semaine", [
                "XmM",  # Consultation matin à partir de 7h
                "XM",   # Consultation matin à partir de 9h
                "XA",   # Consultation après-midi
                "XS",   # Consultation soir
            ]),
            ("Visites Semaine", [
                "Vm",   # Visites matin
                "VA"    # Visites après-midi
            ]),
            ("Gardes Semaine", [
                "NMC"   # NM + NC + NA de la semaine
            ])
        ]

        return {
            "Aucun": None,
            "Weekend": weekend_groups,
            "Semaine": weekday_groups
        }

    def edit_custom_post(self, post_name: str):
        """Modifie un poste personnalisé existant"""
        if post_name in self.custom_posts:
            dialog = NewPostDialog(
                self,
                existing_posts=self.custom_posts,
                statistic_groups=self.define_statistic_groups(),  # Utilisez define_statistic_groups ici
                post_to_edit=self.custom_posts[post_name]
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                edited_post = dialog.get_post()
                if edited_post:
                    # Supprimer l'ancienne configuration
                    old_post = self.custom_posts[post_name]
                    self.remove_post_from_config(old_post)
                    
                    # Ajouter la nouvelle configuration
                    self.custom_posts[edited_post.name] = edited_post
                    self.add_post_to_config(edited_post)
                    
                    self.save_custom_posts()
                    self.update_all_tables()
                    QMessageBox.information(self, "Succès", f"Le poste {edited_post.name} a été modifié avec succès")

    def remove_post_from_config(self, post):
        """Supprime un poste de la configuration"""
        for day_type in post.day_types:
            if post.assignment_type in ["Médecin", "Les deux"]:
                if day_type == "weekday":
                    self.post_configuration.weekday.pop(post.name, None)
                elif day_type == "saturday":
                    self.post_configuration.saturday.pop(post.name, None)
                elif day_type == "sunday_holiday":
                    self.post_configuration.sunday_holiday.pop(post.name, None)

            if post.assignment_type in ["CAT", "Les deux"]:
                if day_type == "weekday":
                    self.post_configuration.cat_weekday.pop(post.name, None)
                elif day_type == "saturday":
                    self.post_configuration.cat_saturday.pop(post.name, None)
                elif day_type == "sunday_holiday":
                    self.post_configuration.cat_sunday_holiday.pop(post.name, None)

    def add_post_to_config(self, post):
        """Ajoute un poste à la configuration"""
        for day_type in post.day_types:
            if post.assignment_type in ["Médecin", "Les deux"]:
                if day_type == "weekday":
                    self.post_configuration.weekday[post.name] = PostConfig(total=1)
                elif day_type == "saturday":
                    self.post_configuration.saturday[post.name] = PostConfig(total=1)
                elif day_type == "sunday_holiday":
                    self.post_configuration.sunday_holiday[post.name] = PostConfig(total=1)

            if post.assignment_type in ["CAT", "Les deux"]:
                if day_type == "weekday":
                    self.post_configuration.cat_weekday[post.name] = PostConfig(total=1)
                elif day_type == "saturday":
                    self.post_configuration.cat_saturday[post.name] = PostConfig(total=1)
                elif day_type == "sunday_holiday":
                    self.post_configuration.cat_sunday_holiday[post.name] = PostConfig(total=1)
              
              
    def clean_invalid_custom_posts(self):
        """Nettoie les postes personnalisés invalides"""
        invalid_posts = []
        
        # Identifier les postes invalides
        for name, post in self.custom_posts.items():
            if post.assignment_type not in ['doctors', 'cats', 'both']:
                logger.debug(f"Poste invalide trouvé: {name} avec assignment_type: {post.assignment_type}")
                invalid_posts.append(name)
                
            # Vérifier aussi la validité des types de jour
            for day_type in post.day_types:
                if day_type not in ['weekday', 'saturday', 'sunday_holiday']:
                    logger.debug(f"Poste avec type de jour invalide: {name} avec day_type: {day_type}")
                    if name not in invalid_posts:
                        invalid_posts.append(name)

        # Supprimer les postes invalides
        for name in invalid_posts:
            logger.info(f"Suppression du poste invalide: {name}")
            del self.custom_posts[name]
            
            # Supprimer des configurations
            for config in [self.post_configuration.weekday, 
                        self.post_configuration.saturday, 
                        self.post_configuration.sunday_holiday,
                        self.post_configuration.cat_weekday,
                        self.post_configuration.cat_saturday,
                        self.post_configuration.cat_sunday_holiday]:
                if name in config:
                    del config[name]

        # Sauvegarder les modifications
        if invalid_posts:
            self.save_custom_posts()
            self.update_all_tables()
            logger.info(f"Nettoyage terminé. Postes supprimés: {invalid_posts}")
            
          
class NewPostDialog(QDialog):
    def __init__(self, parent=None, existing_posts=None, statistic_groups=None, post_to_edit=None):
        super().__init__(parent)
        self.existing_posts = existing_posts or {}
        self.custom_post = post_to_edit
        self.statistic_groups = statistic_groups
        self.post_manager = PostManager()  # Ajout du PostManager ici
        self.init_ui()
        if post_to_edit:
            self.load_post_data(post_to_edit)

    def init_ui(self):
        self.setWindowTitle("Nouveau Poste")
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 1em;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2d3436;
                font-weight: bold;
            }
            QLabel {
                color: #2d3436;
            }
            QLineEdit, QTimeEdit, QComboBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                min-width: 120px;
            }
            QLineEdit:focus, QTimeEdit:focus, QComboBox:focus {
                border-color: #3498db;
            }
            QCheckBox {
                color: #2d3436;
                padding: 5px;
            }
            QCheckBox:hover {
                background-color: #f0f2f5;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Container principal avec grille
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(15)
        grid_layout.setContentsMargins(20, 20, 20, 20)

        # Colonne 1: Informations essentielles
        # Nom du poste
        name_label = QLabel("Nom du poste:")
        name_label.setStyleSheet("font-weight: bold;")
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(4)
        self.name_input.setPlaceholderText("2-4 caractères")
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                min-width: 150px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        grid_layout.addWidget(name_label, 0, 0)
        grid_layout.addWidget(self.name_input, 0, 1)

        # Horaires
        time_label = QLabel("Horaires:")
        time_label.setStyleSheet("font-weight: bold;")
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(10)
        
        self.start_time = QTimeEdit()
        self.end_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.end_time.setDisplayFormat("HH:mm")
        
        for time_edit in [self.start_time, self.end_time]:
            time_edit.setStyleSheet("""
                QTimeEdit {
                    padding: 6px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    min-width: 100px;
                }
                QTimeEdit:focus {
                    border-color: #3498db;
                }
            """)
        
        time_layout.addWidget(QLabel("De:"))
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(QLabel("À:"))
        time_layout.addWidget(self.end_time)
        time_layout.addStretch()
        
        grid_layout.addWidget(time_label, 1, 0)
        grid_layout.addWidget(time_widget, 1, 1)

        # Types de jour
        days_label = QLabel("Types de jour:")
        days_label.setStyleSheet("font-weight: bold;")
        days_widget = QWidget()
        days_layout = QHBoxLayout(days_widget)
        days_layout.setContentsMargins(0, 0, 0, 0)
        days_layout.setSpacing(15)
        
        self.weekday_check = QCheckBox("Semaine")
        self.saturday_check = QCheckBox("Samedi")
        self.sunday_check = QCheckBox("Dimanche/Férié")
        
        for checkbox in [self.weekday_check, self.saturday_check, self.sunday_check]:
            checkbox.setStyleSheet("""
                QCheckBox {
                    padding: 6px 10px;
                    border-radius: 4px;
                }
                QCheckBox:hover {
                    background-color: #f0f2f5;
                }
                QCheckBox:checked {
                    background-color: #e8f0fe;
                    color: #1a73e8;
                }
            """)
            days_layout.addWidget(checkbox)
        days_layout.addStretch()
        
        grid_layout.addWidget(days_label, 2, 0)
        grid_layout.addWidget(days_widget, 2, 1)

        # Type d'assignation
        assignment_label = QLabel("Type d'assignation:")
        assignment_label.setStyleSheet("font-weight: bold;")
        self.assignment_combo = QComboBox()
        self.assignment_combo.addItems(["Médecin", "CAT", "Les deux"])
        self.assignment_combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
        """)
        grid_layout.addWidget(assignment_label, 3, 0)
        grid_layout.addWidget(self.assignment_combo, 3, 1)

        # Groupe statistique
        stats_label = QLabel("Groupe statistique:")
        stats_label.setStyleSheet("font-weight: bold;")
        self.stats_combo = QComboBox()
        self.stats_combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
        """)
        grid_layout.addWidget(stats_label, 4, 0)
        grid_layout.addWidget(self.stats_combo, 4, 1)

        # Configuration du ComboBox statistique
        self.stats_combo.addItem("Aucun")
        self.stats_combo.insertSeparator(self.stats_combo.count())
        self.stats_combo.addItem("--- WEEKEND ---")
        
        for category, subgroups in self.statistic_groups["Weekend"]:
            self.stats_combo.insertSeparator(self.stats_combo.count())
            self.stats_combo.addItem(category)
            for group in subgroups:
                self.stats_combo.addItem("    " + group)
        
        self.stats_combo.insertSeparator(self.stats_combo.count())
        self.stats_combo.addItem("--- SEMAINE ---")
        
        for category, subgroups in self.statistic_groups["Semaine"]:
            self.stats_combo.insertSeparator(self.stats_combo.count())
            self.stats_combo.addItem(category)
            for group in subgroups:
                self.stats_combo.addItem("    " + group)

        # Désactiver les séparateurs et en-têtes
        model = self.stats_combo.model()
        for i in range(self.stats_combo.count()):
            text = self.stats_combo.itemText(i)
            if "---" in text or not text.startswith("    "):
                item = model.item(i)
                if item:
                    item.setEnabled(False)

        # Ajouter le container principal au layout
        main_layout.addWidget(container)

        # Combinaisons possibles
        combinations_group = QGroupBox("Combinaisons possibles")
        combinations_layout = QVBoxLayout(combinations_group)
        
        # En-tête avec explication
        explanation = QLabel("Les postes disponibles pour la combinaison seront affichés en fonction des horaires compatibles")
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; font-style: italic;")
        combinations_layout.addWidget(explanation)
        
        # Grille de checkboxes
        grid_widget = QWidget()
        grid_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        combinations_grid = QGridLayout(grid_widget)
        combinations_grid.setSpacing(10)
        
        self.combination_widgets = {}
        all_posts = list(ALL_POST_TYPES) + [post.name for post in self.existing_posts.values()]
        
        COLUMNS = 4
        for index, post_name in enumerate(all_posts):
            checkbox = QCheckBox(post_name)
            checkbox.setStyleSheet("""
                QCheckBox {
                    padding: 3px 6px;
                    border-radius: 3px;
                    margin: 1px;
                }
                QCheckBox:hover {
                    background-color: #f0f2f5;
                }
                QCheckBox:checked {
                    background-color: #e8f0fe;
                }
            """)
            checkbox.hide()
            self.combination_widgets[post_name] = checkbox
            
            row = index // COLUMNS
            col = index % COLUMNS
            combinations_grid.addWidget(checkbox, row, col)
        
        combinations_layout.addWidget(grid_widget)
        main_layout.addWidget(combinations_group)

        # Boutons d'action
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 20, 0, 0)
        
        save_button = QPushButton("Enregistrer")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        
        cancel_button = QPushButton("Annuler")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        save_button.clicked.connect(self.validate_and_save)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        main_layout.addWidget(button_container)
        
        # Connecter les changements d'horaires à la mise à jour des combinaisons
        self.start_time.timeChanged.connect(self.update_available_combinations)
        self.end_time.timeChanged.connect(self.update_available_combinations)

    def get_post_period(self, start_time: time, end_time: time) -> int:
        """
        Détermine la période d'un créneau horaire
        0: Matin (7h-13h)
        1: Après-midi (13h-18h)
        2: Soir (18h-7h)
        """
        print(f"Analyse du créneau : {start_time} - {end_time}")
        
        if end_time < start_time:
            hours_range = list(range(start_time.hour, 24)) + list(range(0, end_time.hour + 1))
        else:
            hours_range = list(range(start_time.hour, end_time.hour + 1))
        
        print(f"Heures à analyser : {hours_range}")
        
        morning_hours = sum(1 for h in hours_range if 7 <= (h % 24) < 13)
        afternoon_hours = sum(1 for h in hours_range if 13 <= (h % 24) < 18)
        evening_hours = sum(1 for h in hours_range if (h % 24) >= 18 or (h % 24) < 7)
        
        print(f"Heures du matin : {morning_hours}")
        print(f"Heures de l'après-midi : {afternoon_hours}")
        print(f"Heures du soir : {evening_hours}")
        
        max_hours = max(morning_hours, afternoon_hours, evening_hours)
        
        if max_hours == morning_hours:
            print("Assigné à la période du matin")
            return 0
        elif max_hours == afternoon_hours:
            print("Assigné à la période de l'après-midi")
            return 1
        else:
            print("Assigné à la période du soir")
            return 2

    def update_available_combinations(self):
        """Met à jour dynamiquement les postes disponibles pour la combinaison"""
        start_time = self.start_time.time().toPyTime()
        end_time = self.end_time.time().toPyTime()

        if start_time >= end_time and not end_time.hour < 7:  # Permettre les créneaux qui traversent minuit
            return

        # Déterminer la période du nouveau poste
        new_post_period = self.get_post_period(start_time, end_time)

        for post_name, widget in self.combination_widgets.items():
            is_compatible = False
            
            if post_name in ALL_POST_TYPES:
                # Obtenir les horaires des postes standards
                post_details = self.post_manager.get_post_details(post_name, "weekday")
                if post_details:
                    post_start = post_details['start_time']
                    post_end = post_details['end_time']
                    
                    # Vérifier la compatibilité horaire
                    if not (start_time < post_end and end_time > post_start):
                        # Vérifier la période du poste standard
                        standard_post_period = self.get_post_period(post_start, post_end)
                        # Les périodes doivent être différentes pour être compatibles
                        is_compatible = new_post_period != standard_post_period
                        
            elif post_name in self.existing_posts:
                # Vérifier la compatibilité avec les postes personnalisés existants
                custom_post = self.existing_posts[post_name]
                if not (start_time < custom_post.end_time and end_time > custom_post.start_time):
                    existing_post_period = self.get_post_period(custom_post.start_time, custom_post.end_time)
                    is_compatible = new_post_period != existing_post_period

            # Montrer ou cacher le checkbox selon la compatibilité
            widget.setVisible(is_compatible)
            if not is_compatible and widget.isChecked():
                widget.setChecked(False)

    def load_post_data(self, post):
        """Charge les données d'un poste existant pour l'édition"""
        self.name_input.setText(post.name)
        self.start_time.setTime(QTime(post.start_time.hour, post.start_time.minute))
        self.end_time.setTime(QTime(post.end_time.hour, post.end_time.minute))
        
        # Types de jour
        self.weekday_check.setChecked("weekday" in post.day_types)
        self.saturday_check.setChecked("saturday" in post.day_types)
        self.sunday_check.setChecked("sunday_holiday" in post.day_types)
        
        # Assignation
        index = self.assignment_combo.findText(post.assignment_type.title())
        if index >= 0:
            self.assignment_combo.setCurrentIndex(index)
            
        # Sélectionner le bon groupe statistique
        if post.statistic_group:
            for i in range(self.stats_combo.count()):
                if self.stats_combo.itemText(i).strip() == post.statistic_group:
                    self.stats_combo.setCurrentIndex(i)
                    break
                
        # Combinaisons
        for post_name, combo_name in post.possible_combinations.items():
            if post_name in self.combination_widgets:
                self.combination_widgets[post_name].setChecked(True)

    def validate_and_save(self):
        try:
            # Validation du nom
            name = self.name_input.text().upper()
            if not name:
                raise ValueError("Le nom du poste est requis")
            if len(name) < 2 or len(name) > 4:
                raise ValueError("Le nom du poste doit contenir entre 2 et 4 caractères")

            # Validation des horaires
            start_time = self.start_time.time().toPyTime()
            end_time = self.end_time.time().toPyTime()
            if start_time >= end_time:
                raise ValueError("L'heure de début doit être antérieure à l'heure de fin")
            
            # Validation des types de jour
            day_types = set()
            if self.weekday_check.isChecked():
                day_types.add("weekday")
            if self.saturday_check.isChecked():
                day_types.add("saturday")
            if self.sunday_check.isChecked():
                day_types.add("sunday_holiday")
            
            if not day_types:
                raise ValueError("Au moins un type de jour doit être sélectionné")

            # Récupération des combinaisons
            combinations = {}
            for post_name, checkbox in self.combination_widgets.items():
                if checkbox.isChecked():
                    # Le nom de la combinaison est automatiquement générée
                    # en concaténant les noms des postes dans l'ordre
                    combo_name = name + post_name
                    combinations[post_name] = combo_name

            # Création du CustomPost
                self.custom_post = CustomPost(
                name=name,
                start_time=start_time,
                end_time=end_time,
                day_types=day_types,
                assignment_type=self.assignment_combo.currentText(),  # Plus besoin de .lower()
                possible_combinations=combinations,
                statistic_group=None if self.stats_combo.currentText() == "Aucun" else self.stats_combo.currentText()
            )

            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Erreur de validation", str(e))

    def get_post(self) -> Optional[CustomPost]:
        """
        Convertit le type d'assignation en valeur correcte pour le CustomPost
        """
        assignment_mapping = {
            "Médecin": "doctors",
            "CAT": "cats",
            "Les deux": "both"
        }

        # Nettoyer le groupe statistique sélectionné (enlever les espaces et vérifier si c'est un vrai groupe)
        selected_group = self.stats_combo.currentText().strip()
        if selected_group == "Aucun" or not selected_group.startswith("    "):
            statistic_group = None
        else:
            statistic_group = selected_group.strip()  # Enlever les espaces de début
            
        if hasattr(self, 'custom_post'):
            # Convertir le type d'assignation
            assignment = assignment_mapping.get(self.custom_post.assignment_type)
            if assignment:
                self.custom_post.assignment_type = assignment
            return self.custom_post
        return None
