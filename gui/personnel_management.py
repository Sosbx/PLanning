# © 2024 HILAL Arkane. Tous droits réservés.
# gui/personnel_management.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
                             QFormLayout, QLineEdit, QSpinBox, QMessageBox, QSizePolicy,
                             QLabel, QFrame, QTableWidget, QTableWidgetItem, QDialog, QGridLayout,
                             QGroupBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QIcon
from core.Constantes.models import Doctor, CAT, ALL_POST_TYPES, Desiderata
from core.Constantes.data_persistence import DataPersistence
from .post_configuration import PostConfigurationWidget
from .styles import EDIT_DELETE_BUTTON_STYLE, ADD_BUTTON_STYLE, ACTION_BUTTON_STYLE


class PersonnelManagementWidget(QWidget):
    def __init__(self, doctors, cats, post_configuration, main_window):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.main_window = main_window
        self.data_persistence = DataPersistence()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f6fa;
            }
            QFrame {
                background-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ddd;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)
        
        tab_widget = QTabWidget()
        
        # Onglet des médecins
        doctors_tab = QWidget()
        doctors_layout = QVBoxLayout(doctors_tab)
        doctors_layout.setSpacing(4)
        doctors_layout.setContentsMargins(4, 4, 4, 4)

        # En-tête avec statistiques
        header_container = QWidget()
        header_container.setFixedHeight(20)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        doctors_title = QLabel("Gestion des Médecins")
        doctors_title.setStyleSheet("""
            font-size: 11px;
            font-weight: bold;
            color: #2c3e50;
            padding: 0;
            margin: 0;
            background: none;
        """)
        header_layout.addWidget(doctors_title)
        
        self.doctors_stats = QLabel()
        self.doctors_stats.setStyleSheet("""
            color: #7f8c8d;
            font-style: italic;
            padding: 0 4px;
            margin: 0;
            background-color: #f8f9fa;
            border-radius: 2px;
            font-size: 11px;
        """)
        header_layout.addWidget(self.doctors_stats)
        header_layout.addStretch()
        
        doctors_layout.addWidget(header_container)

        # Conteneur des médecins
        doctors_container = QFrame()
        doctors_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        doctors_container_layout = QVBoxLayout(doctors_container)
        doctors_container_layout.setSpacing(4)
        doctors_container_layout.setContentsMargins(4, 4, 4, 4)
        
        grid_container = QWidget()
        self.doctors_grid = QGridLayout(grid_container)
        self.doctors_grid.setSpacing(4)
        self.doctors_grid.setContentsMargins(2, 2, 2, 2)
        doctors_container_layout.addWidget(grid_container)
        
        doctors_layout.addWidget(doctors_container)

        # Bouton d'ajout
        add_doctor_button = QPushButton("Ajouter un médecin")
        add_doctor_button.setIcon(QIcon("icons/ajouter.png"))
        add_doctor_button.clicked.connect(lambda: self.add_personnel("Médecin"))
        add_doctor_button.setStyleSheet(ADD_BUTTON_STYLE)
        doctors_layout.addWidget(add_doctor_button)

        tab_widget.addTab(doctors_tab, "Médecins")

        # Onglet des CAT
        cats_tab = QWidget()
        cats_layout = QVBoxLayout(cats_tab)
        cats_layout.setSpacing(4)
        cats_layout.setContentsMargins(4, 4, 4, 4)

        # En-tête avec statistiques
        cats_header_container = QWidget()
        cats_header_container.setFixedHeight(20)
        cats_header_layout = QHBoxLayout(cats_header_container)
        cats_header_layout.setContentsMargins(0, 0, 0, 0)
        cats_header_layout.setSpacing(4)
        
        cats_title = QLabel("Gestion des CAT")
        cats_title.setStyleSheet("""
            font-size: 11px;
            font-weight: bold;
            color: #2c3e50;
            padding: 0;
            margin: 0;
            background: none;
        """)
        cats_header_layout.addWidget(cats_title)
        
        self.cats_stats = QLabel()
        self.cats_stats.setStyleSheet("""
            color: #7f8c8d;
            font-style: italic;
            padding: 0 4px;
            margin: 0;
            background-color: #f8f9fa;
            border-radius: 2px;
            font-size: 11px;
        """)
        cats_header_layout.addWidget(self.cats_stats)
        cats_header_layout.addStretch()
        
        cats_layout.addWidget(cats_header_container)
        
        # Conteneur des CAT
        cats_container = QFrame()
        cats_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        
        cats_container_layout = QVBoxLayout(cats_container)
        cats_container_layout.setSpacing(4)
        cats_container_layout.setContentsMargins(4, 4, 4, 4)
        
        self.cats_grid = QWidget()
        cats_container_layout.addWidget(self.cats_grid)
        cats_layout.addWidget(cats_container)
        
        # Bouton d'ajout
        add_cat_button = QPushButton("Ajouter un CAT")
        add_cat_button.setIcon(QIcon("icons/ajouter.png"))
        add_cat_button.clicked.connect(lambda: self.add_personnel("CAT"))
        add_cat_button.setStyleSheet(ADD_BUTTON_STYLE)
        cats_layout.addWidget(add_cat_button)
        
        tab_widget.addTab(cats_tab, "CAT")

        # Onglet configuration des postes
        self.post_config_tab = PostConfigurationWidget(self.post_configuration, self.main_window)
        tab_widget.addTab(self.post_config_tab, "Configuration des postes")

        layout.addWidget(tab_widget)
        self.update_tables()

    def update_tables(self):
        self.update_doctors_table()
        self.update_cats_table()

    def update_doctors_table(self):
        for i in reversed(range(self.doctors_grid.count())): 
            self.doctors_grid.itemAt(i).widget().setParent(None)

        sorted_doctors = sorted(self.doctors, key=lambda x: x.name.lower())
        
        # Mise à jour des statistiques
        total_doctors = len(sorted_doctors)
        half_parts_count = sum(1 for d in sorted_doctors if d.half_parts == 1)
        self.doctors_stats.setText(f"{total_doctors} médecins • {half_parts_count} en demi-parts")

        num_columns = 3
        num_rows = (len(sorted_doctors) + num_columns - 1) // num_columns

        for index, doctor in enumerate(sorted_doctors):
            # Calcul des positions pour un remplissage de haut en bas
            col = index // num_rows
            row = index % num_rows
            grid_col = col * 2  # Multiplié par 2 car chaque cellule occupe 2 colonnes

            doctor_frame = QFrame()
            doctor_frame.setStyleSheet("""
                QFrame {
                    border: 1px solid #e1e4e8;
                    background-color: white;
                    border-radius: 3px;
                    padding: 3px;
                }
                QFrame:hover {
                    border-color: #3498db;
                    background-color: #f8f9fa;
                }
            """)
            
            if doctor.half_parts == 1:
                doctor_frame.setStyleSheet("""
                    QFrame {
                        border: 1px solid #e1e4e8;
                        background-color: #fff8dc;
                        border-radius: 3px;
                        padding: 3px;
                    }
                    QFrame:hover {
                        border-color: #3498db;
                        background-color: #fff3c4;
                    }
                """)
            
            doctor_layout = QHBoxLayout(doctor_frame)
            doctor_layout.setContentsMargins(3, 3, 3, 3)
            doctor_layout.setSpacing(4)

            # Numéro
            number_label = QLabel(f"{index + 1}.")
            number_label.setStyleSheet("""
                color: #7f8c8d;
                font-weight: bold;
                min-width: 16px;
                font-size: 11px;
            """)
            number_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            doctor_layout.addWidget(number_label)

            # Nom
            name_label = QLabel(doctor.name)
            name_label.setStyleSheet("""
                font-size: 11px;
                font-weight: bold;
                color: #2c3e50;
            """)
            doctor_layout.addWidget(name_label)

            # Demi-parts avec icône
            if doctor.half_parts == 1:
                half_parts_label = QLabel("½")
                half_parts_label.setStyleSheet("""
                    background-color: #ffd700;
                    color: #000;
                    padding: 1px 3px;
                    border-radius: 2px;
                    font-weight: bold;
                    font-size: 9px;
                """)
                doctor_layout.addWidget(half_parts_label)

            doctor_layout.addStretch()

            # Boutons d'action
            edit_button = QPushButton()
            edit_button.setIcon(QIcon("icons/edition.png"))
            edit_button.setIconSize(QSize(14, 14))
            edit_button.setFixedSize(20, 20)
            edit_button.setToolTip("Modifier")
            edit_button.clicked.connect(lambda _, p=doctor: self.edit_personnel(p))
            edit_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
            
            delete_button = QPushButton()
            delete_button.setIcon(QIcon("icons/supprimer.png"))
            delete_button.setIconSize(QSize(14, 14))
            delete_button.setFixedSize(20, 20)
            delete_button.setToolTip("Supprimer")
            delete_button.clicked.connect(lambda _, p=doctor: self.delete_personnel(p))
            delete_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
            
            doctor_layout.addWidget(edit_button)
            doctor_layout.addWidget(delete_button)

            self.doctors_grid.addWidget(doctor_frame, row, grid_col, 1, 2)

        for i in range(6):  # Ajuster pour 3 colonnes
            self.doctors_grid.setColumnStretch(i, 1)
            
    def update_cats_table(self):
        if self.cats_grid.layout():
            QWidget().setLayout(self.cats_grid.layout())

        cats_layout = QVBoxLayout(self.cats_grid)
        cats_layout.setSpacing(4)
        cats_layout.setContentsMargins(2, 2, 2, 2)

        sorted_cats = sorted(self.cats, key=lambda x: x.name.lower())
        
        # Mise à jour des statistiques
        self.cats_stats.setText(f"{len(sorted_cats)} CAT")

        for index, cat in enumerate(sorted_cats):
            cat_frame = QFrame()
            cat_frame.setStyleSheet("""
                QFrame {
                    border: 1px solid #e1e4e8;
                    background-color: white;
                    border-radius: 3px;
                    padding: 3px;
                }
                QFrame:hover {
                    border-color: #3498db;
                    background-color: #f8f9fa;
                }
            """)
            
            cat_layout = QHBoxLayout(cat_frame)
            cat_layout.setContentsMargins(3, 3, 3, 3)
            cat_layout.setSpacing(4)

            # Numéro
            number_label = QLabel(f"{index + 1}.")
            number_label.setStyleSheet("""
                color: #7f8c8d;
                font-weight: bold;
                min-width: 16px;
                font-size: 11px;
            """)
            number_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cat_layout.addWidget(number_label)

            # Nom
            name_label = QLabel(cat.name)
            name_label.setStyleSheet("""
                font-size: 11px;
                font-weight: bold;
                color: #2c3e50;
            """)
            cat_layout.addWidget(name_label)

            cat_layout.addStretch()

            # Boutons d'action
            edit_button = QPushButton()
            edit_button.setIcon(QIcon("icons/edition.png"))
            edit_button.setIconSize(QSize(14, 14))
            edit_button.setFixedSize(20, 20)
            edit_button.setToolTip("Modifier")
            edit_button.clicked.connect(lambda _, c=cat: self.edit_personnel(c))
            edit_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
            
            delete_button = QPushButton()
            delete_button.setIcon(QIcon("icons/supprimer.png"))
            delete_button.setIconSize(QSize(14, 14))
            delete_button.setFixedSize(20, 20)
            delete_button.setToolTip("Supprimer")
            delete_button.clicked.connect(lambda _, c=cat: self.delete_personnel(c))
            delete_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
            
            cat_layout.addWidget(edit_button)
            cat_layout.addWidget(delete_button)

            cats_layout.addWidget(cat_frame)

        cats_layout.addStretch()

    def add_personnel(self, personnel_type):
        if personnel_type == "Médecin":
            dialog = PersonnelDialog(self, personnel_type=personnel_type)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                name, _, half_parts = dialog.get_personnel_info()
                self.doctors.append(Doctor(name, half_parts))
        else:  # CAT
            dialog = CATDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                name = dialog.get_cat_info()
                new_cat = CAT(name)
                self.cats.append(new_cat)
        self.update_tables()
        self.save_data()

    def delete_personnel(self, person):
        confirm = QMessageBox.question(
            self, 
            "Confirmer la suppression",
            f"Êtes-vous sûr de vouloir supprimer {person.name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            if isinstance(person, Doctor):
                self.doctors.remove(person)
            else:
                self.cats.remove(person)
            self.update_tables()
            self.save_data()

    def edit_personnel(self, person):
        if isinstance(person, Doctor):
            dialog = PersonnelDialog(self, person)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                name, _, half_parts = dialog.get_personnel_info()
                person.name = name
                person.half_parts = half_parts
        else:  # CAT
            dialog = CATDialog(self, person)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                name = dialog.get_cat_info()
                person.name = name
        self.update_tables()
        self.save_data()

    def save_data(self):
        if hasattr(self, 'data_persistence'):
            self.data_persistence.save_data(self.doctors, self.cats, self.post_configuration)
            QMessageBox.information(self, "Succès", "Les modifications ont été enregistrées avec succès")
        else:
            QMessageBox.warning(self, "Attention", "Aucun mécanisme de persistance des données n'est configuré")


class PersonnelDialog(QDialog):
    def __init__(self, parent=None, person=None, personnel_type=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter/Modifier personnel")
        self.person = person
        self.personnel_type = personnel_type if person is None else ("Médecin" if isinstance(person, Doctor) else "CAT")
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 0.5em;
                padding: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 6px;
                padding: 0 3px;
                color: #2d3436;
                font-weight: bold;
            }
            QLabel {
                color: #2d3436;
            }
            QLineEdit, QSpinBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 4px;
                min-width: 180px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #3498db;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
                min-width: 80px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # Groupe d'informations
        info_group = QGroupBox("Informations")
        form_layout = QFormLayout(info_group)
        form_layout.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Entrez le nom")
        form_layout.addRow("Nom:", self.name_input)

        if self.personnel_type == "Médecin":
            self.half_parts_input = QSpinBox()
            self.half_parts_input.setRange(1, 2)
            self.half_parts_input.setPrefix("  ")
            self.half_parts_input.setSuffix(" parts")
            form_layout.addRow("Parts:", self.half_parts_input)

        layout.addWidget(info_group)

        # Boutons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(6)
        
        save_button = QPushButton("Enregistrer")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        
        cancel_button = QPushButton("Annuler")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        layout.addWidget(button_container)

        if self.person:
            self.name_input.setText(self.person.name)
            if isinstance(self.person, Doctor):
                self.half_parts_input.setValue(self.person.half_parts)

    def get_personnel_info(self):
        half_parts = self.half_parts_input.value() if self.personnel_type == "Médecin" else 0
        return self.name_input.text(), self.personnel_type, half_parts


class CATDialog(QDialog):
    def __init__(self, parent=None, cat=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter/Modifier CAT")
        self.cat = cat
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 0.5em;
                padding: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 6px;
                padding: 0 3px;
                color: #2d3436;
                font-weight: bold;
            }
            QLabel {
                color: #2d3436;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 4px;
                min-width: 180px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
                min-width: 80px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # Groupe d'informations
        info_group = QGroupBox("Informations")
        form_layout = QFormLayout(info_group)
        form_layout.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Entrez le nom")
        form_layout.addRow("Nom:", self.name_input)

        layout.addWidget(info_group)

        # Boutons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(6)
        
        save_button = QPushButton("Enregistrer")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        
        cancel_button = QPushButton("Annuler")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        layout.addWidget(button_container)

        if self.cat:
            self.name_input.setText(self.cat.name)

    def get_cat_info(self):
        return self.name_input.text()
