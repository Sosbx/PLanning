# © 2024 HILAL Arkane. Tous droits réservés.
# gui/pre_attribution_view.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                           QTableWidget, QTableWidgetItem, QLabel, QSplitter,
                           QHeaderView, QMenu, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from datetime import date, datetime, timedelta
from workalendar.europe import France
from core.Constantes.models import PostManager, Doctor, PostConfig, TimeSlot, Planning, DayPlanning
from .styles import color_system, ADD_BUTTON_STYLE, EDIT_DELETE_BUTTON_STYLE

class PreAttributionWidget(QWidget):
    """Widget principal pour la vue de pré-attribution"""
    
    def __init__(self, doctors, cats, start_date, end_date, main_window):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.start_date = start_date
        self.end_date = end_date
        self.main_window = main_window
        self.cal = France()
        # Charger les pré-attributions existantes
        self.pre_attributions = self.main_window.data_persistence.load_pre_attributions() or {}
        self.custom_posts = self.main_window.data_persistence.load_custom_posts()
        self.init_ui()
        
        # Refresh custom posts when they change
        if hasattr(self.main_window, 'personnel_tab'):
            self.main_window.personnel_tab.post_config_tab.custom_posts_updated.connect(self.refresh_custom_posts)
            
        # Connect desiderata updates
        if hasattr(self.main_window, 'desiderata_tab'):
            self.main_window.desiderata_tab.desiderata_updated.connect(self.update_display_for_current_person)
            
        # Initialize display for first person if any
        if len(self.doctors + self.cats) > 0:
            self.person_selector.setCurrentIndex(0)

    def refresh_custom_posts(self):
        """Refresh custom posts and update UI"""
        self.custom_posts = self.main_window.data_persistence.load_custom_posts()
        current_person = self.get_current_person()
        if current_person:
            self.planning_table.update_display(current_person)
            self.post_list.update_for_person(current_person)

    def init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)

        # Sélecteur de personnes
        self.person_selector = QComboBox()
        layout.addWidget(self.person_selector)

        # Création du splitter principal horizontal
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tableau de planning
        self.planning_table = PreAttributionTable(self.start_date, self.end_date, self)
        main_splitter.addWidget(self.planning_table)

        # Création du conteneur droit avec splitter vertical
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Liste des postes disponibles (en haut)
        self.post_list = AvailablePostList(self)
        right_layout.addWidget(self.post_list, stretch=1)
        
        # Historique des actions (en bas)
        self.history_widget = AttributionHistoryWidget(self)
        right_layout.addWidget(self.history_widget, stretch=1)

        main_splitter.addWidget(right_container)
        main_splitter.setSizes([700, 300])
        layout.addWidget(main_splitter)
        
        # Boutons de contrôle
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Sauvegarder")
        self.save_button.clicked.connect(self.save_pre_attributions)
        self.save_button.setStyleSheet(ADD_BUTTON_STYLE)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("Réinitialiser")
        self.reset_button.clicked.connect(self.reset_pre_attributions)
        self.reset_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        button_layout.addWidget(self.reset_button)
        
        layout.addLayout(button_layout)

        # Connecter le signal de clic sur cellule
        self.planning_table.cell_clicked.connect(self.on_cell_clicked)
        
        # Connect person selector signal after all widgets are created
        self.person_selector.currentIndexChanged.connect(self.on_person_changed)
        
        # Initialize person selector after all connections
        self.update_person_selector()

    def on_cell_clicked(self, date, period):
        """Gère le clic sur une cellule du tableau"""
        current_person = self.get_current_person()
        if current_person:
            self.post_list.update_for_period(date, period, current_person)

    def update_display_for_current_person(self):
        """Update the display when desiderata are modified"""
        current_person = self.get_current_person()
        if current_person:
            self.planning_table.update_display(current_person)
            
    def update_person_selector(self):
        """Met à jour la liste des personnes dans le sélecteur"""
        # Stocker la personne actuellement sélectionnée
        current_person_name = self.person_selector.currentText()
        
        self.person_selector.clear()
        sorted_doctors = sorted(self.doctors, key=lambda x: x.name.lower())
        sorted_cats = sorted(self.cats, key=lambda x: x.name.lower())
        
        for doctor in sorted_doctors:
            self.person_selector.addItem(doctor.name)
        
        if sorted_cats:
            self.person_selector.insertSeparator(len(sorted_doctors))
        
        for cat in sorted_cats:
            self.person_selector.addItem(cat.name)
            
        # Restaurer la sélection précédente si possible
        if current_person_name:
            index = self.person_selector.findText(current_person_name)
            if index >= 0:
                self.person_selector.setCurrentIndex(index)
                # Force update display for the current person
                current_person = self.get_current_person()
                if current_person:
                    self.planning_table.update_display(current_person)

    def on_person_changed(self):
        """Gère le changement de personne sélectionnée"""
        current_person = self.get_current_person()
        if current_person:
            self.planning_table.update_display(current_person)
            self.post_list.update_for_person(current_person)

    def get_current_person(self):
        """Retourne la personne actuellement sélectionnée"""
        name = self.person_selector.currentText()
        return next((p for p in self.doctors + self.cats if p.name == name), None)
        
    def save_pre_attributions(self):
        """Sauvegarde les pré-attributions actuelles"""
        try:
            self.main_window.data_persistence.save_pre_attributions(self.pre_attributions)
            QMessageBox.information(self, "Succès", "Les pré-attributions ont été sauvegardées avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde des pré-attributions : {str(e)}")
    
    def reset_pre_attributions(self):
        """Réinitialise toutes les pré-attributions"""
        reply = QMessageBox.question(
            self,
            "Confirmation",
            "Êtes-vous sûr de vouloir effacer toutes les pré-attributions ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.pre_attributions.clear()
            current_person = self.get_current_person()
            if current_person:
                self.planning_table.update_display(current_person)
                self.post_list.update_for_person(current_person)
            self.history_widget.clear_history()
            QMessageBox.information(self, "Succès", "Toutes les pré-attributions ont été effacées.")
    
    def update_dates(self, start_date, end_date):
        """Met à jour les dates et rafraîchit l'affichage"""
        self.start_date = start_date
        self.end_date = end_date
        self.planning_table.update_dates(start_date, end_date)
        
        # Update current person's display if any
        current_person = self.get_current_person()
        if current_person:
            self.planning_table.update_display(current_person)

class AvailablePostList(QTableWidget):
    """Liste des postes disponibles pour la période sélectionnée"""

    def __init__(self, pre_attribution_widget=None):
        super().__init__()
        self.pre_attribution_widget = pre_attribution_widget
        self.init_ui()

    def get_post_config(self, date, post_type):
        """Obtient la configuration d'un poste pour une date donnée"""
        # Déterminer le type de jour
        cal = France()
        is_weekend = date.weekday() >= 5
        is_holiday = cal.is_holiday(date)
        is_bridge = False
        if not (is_weekend or is_holiday):
            prev_day = date - timedelta(days=1)
            next_day = date + timedelta(days=1)
            prev_is_off = prev_day.weekday() >= 5 or cal.is_holiday(prev_day)
            next_is_off = next_day.weekday() >= 5 or cal.is_holiday(next_day)
            is_bridge = prev_is_off and next_is_off

        if date.weekday() == 5:  # Samedi
            day_type = "saturday"
        elif date.weekday() == 6 or is_holiday or is_bridge:  # Dimanche, férié ou pont
            day_type = "sunday_holiday"
        else:
            day_type = "weekday"

        # Toujours utiliser la configuration des médecins
        post_configuration = self.pre_attribution_widget.main_window.post_configuration
        if day_type == "weekday":
            config = post_configuration.weekday
        elif day_type == "saturday":
            config = post_configuration.saturday
        else:
            config = post_configuration.sunday_holiday

        return config.get(post_type, PostConfig())

    def init_ui(self):
        """Initialise l'interface de la liste des postes"""
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Poste", "Statut"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(25)
        
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: """ + color_system.colors['table']['border'].name() + """;
                border: 1px solid """ + color_system.colors['container']['border'].name() + """;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid """ + color_system.colors['table']['border'].name() + """;
            }
            QTableWidget::item:selected {
                background-color: """ + color_system.colors['table']['selected'].name() + """;
            }
        """)

    def update_for_period(self, date, period, person):
        """Met à jour la liste des postes disponibles pour une période donnée"""
        self.clear()
        self.setHorizontalHeaderLabels(["Poste", "Statut"])
        self.setRowCount(0)

        available_posts = self.get_available_posts(date, period, person)
        
        # Pour chaque type de poste, obtenir le quota et les attributions
        for post_type, is_attributed in available_posts.items():
            # Obtenir le quota configuré
            post_config = self.get_post_config(date, post_type)
            max_count = post_config.total if post_config else 0
            
            # Vérifier si c'est un poste personnalisé
            if post_type in self.pre_attribution_widget.custom_posts:
                custom_post = self.pre_attribution_widget.custom_posts[post_type]
                if custom_post.preserve_in_planning:
                    # Si le poste doit être préservé, permettre l'attribution illimitée
                    max_count = 1
                elif custom_post.force_zero_count:
                    # Si le poste force un quota de 0, utiliser ce quota
                    max_count = 1
                else:
                    # Sinon utiliser le quota configuré
                    if max_count == 0:
                        max_count = 1
            else:
                # Pour les postes standard, si le quota est 0, afficher une seule ligne
                if max_count == 0:
                    max_count = 1
            
            # Obtenir les attributions existantes pour ce poste
            attributions = []
            for person_name, person_attributions in self.pre_attribution_widget.pre_attributions.items():
                if (date, period) in person_attributions and person_attributions[(date, period)] == post_type:
                    attributions.append(person_name)
            
            # Vérifier si c'est un poste personnalisé
            is_custom_post = post_type in self.pre_attribution_widget.custom_posts
            is_force_zero = is_custom_post and self.pre_attribution_widget.custom_posts[post_type].force_zero_count

            if is_custom_post:
                # Pour les postes personnalisés, afficher les attributions existantes
                row = self.rowCount()
                self.insertRow(row)
                
                # Colonne du type de poste
                post_item = QTableWidgetItem(post_type)
                post_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, 0, post_item)
                
                # Colonne du statut
                if attributions:
                    # Poste attribué à un ou plusieurs médecins
                    status = "Attribué à : " + ", ".join(attributions)
                    color = QColor('#E6D4B8')  # Couleur différente pour les attributions multiples
                else:
                    # Poste disponible
                    status = "Disponible"
                    color = QColor('#D1E6D6')
                
                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setBackground(QBrush(color))
                self.setItem(row, 1, status_item)

                # Si c'est un poste avec force_zero_count, toujours ajouter une ligne disponible
                if is_force_zero and not is_attributed:
                    row = self.rowCount()
                    self.insertRow(row)
                    
                    post_item = QTableWidgetItem(post_type)
                    post_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.setItem(row, 0, post_item)
                    
                    status_item = QTableWidgetItem("Disponible")
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_item.setBackground(QBrush(QColor('#D1E6D6')))
                    self.setItem(row, 1, status_item)
            else:
                # Pour les postes standards, afficher une ligne par quota
                for i in range(max_count):
                    row = self.rowCount()
                    self.insertRow(row)
                    
                    # Colonne du type de poste
                    post_item = QTableWidgetItem(post_type)
                    post_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.setItem(row, 0, post_item)
                    
                    # Colonne du statut
                    if i < len(attributions):
                        # Poste attribué
                        status = f"Attribué à {attributions[i]}"
                        color = QColor('#C28E8E')
                    else:
                        # Poste disponible
                        status = "Disponible"
                        color = QColor('#D1E6D6')
                    
                    status_item = QTableWidgetItem(status)
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_item.setBackground(QBrush(color))
                    self.setItem(row, 1, status_item)

    def get_available_posts(self, date, period, person):
        """Retourne les postes disponibles pour une période donnée"""
        available_posts = {}
        
        # Déterminer le type de jour
        cal = France()
        is_weekend = date.weekday() >= 5
        is_holiday = cal.is_holiday(date)
        
        # Check for bridge days
        is_bridge = False
        if not (is_weekend or is_holiday):
            prev_day = date - timedelta(days=1)
            next_day = date + timedelta(days=1)
            prev_is_off = prev_day.weekday() >= 5 or cal.is_holiday(prev_day)
            next_is_off = next_day.weekday() >= 5 or cal.is_holiday(next_day)
            is_bridge = prev_is_off and next_is_off
        
        # Determine day type
        if date.weekday() == 5:  # Samedi
            day_type = "saturday"
        elif date.weekday() == 6 or is_holiday or is_bridge:  # Dimanche, férié ou pont
            day_type = "sunday_holiday"
        else:
            day_type = "weekday"
            
        # Toujours utiliser la configuration des médecins pour l'affichage
        post_configuration = self.pre_attribution_widget.main_window.post_configuration
        post_config = post_configuration.get_config_for_day_type(day_type)

        # Filtrer les postes selon la période
        post_manager = PostManager()
        
        # Add standard posts
        for post_type, config in post_config.items():
            post_details = post_manager.get_post_details(post_type, day_type)
            
            if post_details:
                post_start_hour = post_details['start_time'].hour
                if period == 1 and 7 <= post_start_hour < 13 and post_type != "CT":  # Matin (sauf CT)
                    is_attributed = self.is_post_attributed(date, period, post_type)
                    available_posts[post_type] = is_attributed
                elif period == 2 and (
                    (13 <= post_start_hour < 18) or  # Après-midi normal
                    post_type == "CT"  # CT toujours en après-midi
                ):
                    is_attributed = self.is_post_attributed(date, period, post_type)
                    available_posts[post_type] = is_attributed
                elif period == 3 and (post_start_hour >= 18 or post_start_hour < 7):  # Soir/Nuit
                    is_attributed = self.is_post_attributed(date, period, post_type)
                    available_posts[post_type] = is_attributed
        
        # Add all custom posts from custom_posts
        if self.pre_attribution_widget.custom_posts:
            for name, custom_post in self.pre_attribution_widget.custom_posts.items():
                # Check if the post is compatible with the person type and has a valid count
                is_compatible = False
                if hasattr(person, 'half_parts'):  # Doctor
                    if custom_post.assignment_type in ['doctors', 'both']:
                        is_compatible = True
                else:  # CAT
                    if custom_post.assignment_type in ['cats', 'both']:
                        is_compatible = True

                # Check if the post is compatible with the day type
                if is_compatible and day_type in custom_post.day_types:
                    post_start_hour = custom_post.start_time.hour
                    if period == 1 and 7 <= post_start_hour < 13:  # Matin
                        is_attributed = self.is_post_attributed(date, period, name)
                        available_posts[name] = is_attributed
                    elif period == 2 and 13 <= post_start_hour < 18:  # Après-midi
                        is_attributed = self.is_post_attributed(date, period, name)
                        available_posts[name] = is_attributed
                    elif period == 3 and (post_start_hour >= 18 or post_start_hour < 7):  # Soir/Nuit
                        is_attributed = self.is_post_attributed(date, period, name)
                        available_posts[name] = is_attributed

        return available_posts
    
    def is_post_attributed(self, date, period, post_type):
        """Vérifie si un poste est déjà attribué en tenant compte du nombre maximum d'attributions"""
        # Compter le nombre d'attributions existantes pour ce poste
        attribution_count = 0
        for person_attributions in self.pre_attribution_widget.pre_attributions.values():
            if (date, period) in person_attributions:
                if person_attributions[(date, period)] == post_type:
                    attribution_count += 1

        # Déterminer le type de jour
        cal = France()
        is_weekend = date.weekday() >= 5
        is_holiday = cal.is_holiday(date)
        is_bridge = False
        if not (is_weekend or is_holiday):
            prev_day = date - timedelta(days=1)
            next_day = date + timedelta(days=1)
            prev_is_off = prev_day.weekday() >= 5 or cal.is_holiday(prev_day)
            next_is_off = next_day.weekday() >= 5 or cal.is_holiday(next_day)
            is_bridge = prev_is_off and next_is_off

        if date.weekday() == 5:  # Samedi
            day_type = "saturday"
        elif date.weekday() == 6 or is_holiday or is_bridge:  # Dimanche, férié ou pont
            day_type = "sunday_holiday"
        else:
            day_type = "weekday"

        # Vérifier si c'est un poste personnalisé
        if post_type in self.pre_attribution_widget.custom_posts:
            custom_post = self.pre_attribution_widget.custom_posts[post_type]
            
            # Si le poste doit être préservé ou a un quota forcé à 0, permettre l'attribution
            if custom_post.preserve_in_planning or custom_post.force_zero_count:
                return False
            
            # Pour les autres postes personnalisés, utiliser la configuration des médecins
            post_configuration = self.pre_attribution_widget.main_window.post_configuration
            if day_type == "weekday":
                config = post_configuration.weekday
            elif day_type == "saturday":
                config = post_configuration.saturday
            else:
                config = post_configuration.sunday_holiday
            
            max_count = config.get(post_type, PostConfig()).total
        else:
            # Pour les postes standards, utiliser la configuration des médecins
            post_configuration = self.pre_attribution_widget.main_window.post_configuration
            post_config = post_configuration.get_config_for_day_type(day_type)
            max_count = post_config.get(post_type, PostConfig()).total

        # Si le quota est 0, permettre des attributions illimitées
        if max_count == 0:
            return False
        
        # Sinon, vérifier si le nombre d'attributions a atteint le quota
        return attribution_count >= max_count

    def update_for_person(self, person):
        """Met à jour la liste en fonction de la personne sélectionnée"""
        self.clear()
        self.setHorizontalHeaderLabels(["Poste", "Statut"])
        self.setRowCount(0)
class PreAttributionTable(QTableWidget):
    """Tableau pour afficher et gérer les pré-attributions"""

    cell_clicked = pyqtSignal(date, int)  # (date, période)

    def __init__(self, start_date, end_date, pre_attribution_widget):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.cal = France()
        self.pre_attribution_widget = pre_attribution_widget
        self.init_ui()
        self.create_calendar()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def init_ui(self):
        """Initialise l'interface du tableau"""
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        # Connecter uniquement le double-clic
        self.cellDoubleClicked.connect(self.handle_cell_double_click)
        
        # Connecter le clic simple pour mettre à jour la liste des postes
        self.cellClicked.connect(self.handle_cell_click)

    def handle_cell_click(self, row, col):
        """Gère le clic simple sur une cellule"""
        base_col = (col // 5) * 5
        
        if col in [base_col + 2, base_col + 3, base_col + 4]:
            period = col - base_col - 1  # 2->1 (M), 3->2 (AM), 4->3 (S)
            date = self.get_date_from_cell(row, col)
            if date:
                self.cell_clicked.emit(date, period)

    def handle_cell_double_click(self, row, col):
        """Gère le double-clic sur une cellule"""
        base_col = (col // 5) * 5  # Trouve le début du groupe de colonnes pour ce mois
        
        # Déterminer la période en fonction de la colonne relative
        period_mapping = {
            base_col + 2: 1,  # Matin
            base_col + 3: 2,  # Après-midi
            base_col + 4: 3   # Soir
        }
        
        if col in period_mapping:
            date = self.get_date_from_cell(row, col)
            period = period_mapping[col]
            
            if date and self.can_attribute(date, period):
                self.show_attribution_menu(date, period, row, col)

    def check_constraints(self, date, period, slot):
        """Vérifie les contraintes et retourne une liste des violations"""
        current_person = self.pre_attribution_widget.get_current_person()
        if not current_person:
            return []

        constraints = self.pre_attribution_widget.main_window.planning_constraints
        planning = self.pre_attribution_widget.main_window.planning

        violations = []
        
        # Vérifier les desiderata
        for des in current_person.desiderata:
            if des.start_date <= date <= des.end_date and des.period == period:
                violations.append("Un desiderata existe pour cette période")
                break

        # Vérifier le nombre maximum de postes par jour (peut fonctionner sans planning)
        if not constraints.check_max_posts_per_day(current_person, date, slot, planning or Planning(date, date)):
            violations.append("Dépasse le maximum de 2 postes par jour")

        # Si nous avons un planning valide, vérifier les autres contraintes
        if planning:
            # Vérifier les contraintes de nuit consécutives
            if not constraints.check_consecutive_night_shifts(current_person, date, slot, planning):
                violations.append("Dépasse la limite de 4 nuits consécutives")

            # Vérifier les contraintes de jours consécutifs
            if not constraints.check_consecutive_working_days(current_person, date, slot, planning):
                violations.append("Dépasse la limite de 6 jours consécutifs")

            # Vérifier les contraintes de matin après nuit
            if not constraints.check_morning_after_night_shifts(current_person, date, slot, planning):
                violations.append("Poste du matin après un poste de nuit")

            # Vérifier les contraintes NL
            if not constraints.check_nl_constraint(current_person, date, slot, planning):
                violations.append("Violation des règles NL (pas de poste le même jour/lendemain)")

            # Vérifier les contraintes NM
            if not constraints.check_nm_constraint(current_person, date, slot, planning):
                violations.append("Violation des règles NM")

            # Vérifier les contraintes NM/NA
            if not constraints.check_nm_na_constraint(current_person, date, slot, planning):
                violations.append("Violation des règles NM/NA")

        return violations

    def can_attribute(self, date, period):
        """Vérifie si on peut attribuer un poste à cette date et période"""
        current_person = self.pre_attribution_widget.get_current_person()
        if not current_person:
            return False
                
        return True

    def show_attribution_menu(self, date, period, row, col):
        """Affiche le menu d'attribution des postes"""
        current_person = self.pre_attribution_widget.get_current_person()
        menu = QMenu(self)
        
        available_posts = self.pre_attribution_widget.post_list.get_available_posts(
            date, period, current_person
        )
        
        for post, is_attributed in available_posts.items():
            if not is_attributed:
                action = menu.addAction(post)
                action.triggered.connect(
                    lambda checked, d=date, p=period, post_type=post: 
                    self.confirm_and_assign_post(d, p, post_type)
                )
        
        if menu.actions():
            menu.exec(self.mapToGlobal(self.viewport().mapToParent(
                self.visualRect(self.model().index(row, col)).center()
            )))

    
    def _check_all_constraints(self, current_person, date, new_slot, temp_planning):
        """
        Vérifie toutes les contraintes et retourne la liste des violations.
        Utilise les méthodes existantes de constraints.py
        """
        warnings = []
        constraints = self.pre_attribution_widget.main_window.planning_constraints
        
        # 1. Vérification des desiderata
        for des in current_person.desiderata:
            if des.start_date <= date <= des.end_date:
                priority = getattr(des, 'priority', 'primary')
                warnings.append(f"- Violation d'un desiderata {priority}")
        
        # 2. Utilisation directe des méthodes de constraints.py
        if not constraints.check_nl_constraint(current_person, date, new_slot, temp_planning):
            warnings.append("- Violation des règles NL")
            
        if not constraints.check_nm_constraint(current_person, date, new_slot, temp_planning):
            warnings.append("- Violation des règles NM")
            
        if not constraints.check_nm_na_constraint(current_person, date, new_slot, temp_planning):
            warnings.append("- Violation des règles NM/NA")
            
        if not constraints.check_morning_after_night_shifts(current_person, date, new_slot, temp_planning):
            warnings.append("- Violation des règles de repos après poste de nuit")
            
        if not constraints.check_consecutive_night_shifts(current_person, date, new_slot, temp_planning):
            warnings.append("- Violation des règles de nuits consécutives")
            
        if not constraints.check_consecutive_working_days(current_person, date, new_slot, temp_planning):
            warnings.append("- Violation des règles de jours consécutifs")
            
        return warnings

    def confirm_and_assign_post(self, date, period, post_type):
        """Vérifie les contraintes et confirme la pré-attribution si nécessaire"""
        current_person = self.pre_attribution_widget.get_current_person()
        if not current_person:
            return

        # Créer le TimeSlot pour la nouvelle pré-attribution
        new_slot = self._create_timeslot_for_post(post_type, date)
        if not new_slot:
            QMessageBox.warning(
                self,
                "Erreur",
                f"Configuration introuvable pour le poste {post_type}"
            )
            return

        # Vérifier uniquement les chevauchements avec les pré-attributions existantes
        if not self._check_pre_attribution_overlap(date, new_slot, current_person):
            QMessageBox.warning(
                self,
                "Attribution impossible",
                "Ce poste chevauche une autre pré-attribution existante."
            )
            return

        # Créer un planning temporaire incluant toutes les pré-attributions
        temp_planning = self._create_temp_planning_with_pre_attributions(date)
        warnings = self._check_all_constraints(current_person, date, new_slot, temp_planning)

        # Si des violations sont détectées, demander confirmation
        if warnings:
            warning_text = "Cette pré-attribution viole les contraintes suivantes :\n\n"
            warning_text += "\n".join(warnings)
            warning_text += "\n\nVoulez-vous continuer quand même ?"
            
            reply = QMessageBox.question(
                self,
                "Confirmation de violation de contraintes",
                warning_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return

        # Procéder à l'attribution
        self.assign_post(date, period, post_type)

    def _has_pre_attributed_nl(self, person, date):
        """Vérifie si une NL est pré-attribuée pour une date donnée"""
        attributions = self.pre_attribution_widget.pre_attributions.get(person.name, {})
        for (attr_date, _), post_type in attributions.items():
            if attr_date == date and post_type == "NL":
                return True
        return False

    def _create_temp_planning_with_pre_attributions(self, current_date):
        """Crée un planning temporaire incluant toutes les pré-attributions"""
        # Créer un planning qui couvre une semaine avant et après
        start_date = current_date - timedelta(days=7)
        end_date = current_date + timedelta(days=7)
        temp_planning = Planning(start_date, end_date)
        
        # Initialiser les jours
        current = start_date
        while current <= end_date:
            day = DayPlanning(date=current, slots=[])
            temp_planning.days.append(day)
            current += timedelta(days=1)
        
        # Ajouter toutes les pré-attributions existantes
        for person_name, attributions in self.pre_attribution_widget.pre_attributions.items():
            for (date, period), post_type in attributions.items():
                if start_date <= date <= end_date:
                    slot = self._create_timeslot_for_post(post_type, date)
                    if slot:
                        slot.assignee = person_name
                        day = temp_planning.get_day(date)
                        if day:
                            day.slots.append(slot)
        
        return temp_planning

    def _check_pre_attribution_overlap(self, date, new_slot, current_person):
        """Vérifie uniquement les chevauchements avec d'autres pré-attributions"""
        attributions = self.pre_attribution_widget.pre_attributions.get(current_person.name, {})
        
        for (other_date, other_period), other_post in attributions.items():
            if other_date == date:  # Ne vérifier que le même jour
                other_slot = self._create_timeslot_for_post(other_post, other_date)
                if other_slot and self._slots_overlap(new_slot, other_slot):
                    return False
        return True

    def _create_timeslot_for_post(self, post_type, date):
        """Crée un TimeSlot pour un type de poste donné"""
        day_type = "weekday"
        if date.weekday() == 5:
            day_type = "saturday"
        elif date.weekday() == 6 or self.cal.is_holiday(date):
            day_type = "sunday_holiday"
        elif self.is_bridge_day(date):
            day_type = "sunday_holiday"

        if post_type in self.pre_attribution_widget.custom_posts:
            custom_post = self.pre_attribution_widget.custom_posts[post_type]
            return TimeSlot(
                start_time=datetime.combine(date, custom_post.start_time),
                end_time=datetime.combine(date, custom_post.end_time),
                site="Custom",
                slot_type="Custom",
                abbreviation=post_type
            )
        else:
            post_manager = PostManager()
            post_details = post_manager.get_post_details(post_type, day_type)
            if post_details:
                return TimeSlot(
                    start_time=datetime.combine(date, post_details['start_time']),
                    end_time=datetime.combine(date, post_details['end_time']),
                    site=post_details['site'],
                    slot_type="Standard",
                    abbreviation=post_type
                )
        return None

    def _slots_overlap(self, slot1, slot2):
        """Vérifie si deux slots se chevauchent"""
        return (slot1.start_time < slot2.end_time and 
                slot1.end_time > slot2.start_time)
        
        
    def is_bridge_day(self, date):
        """Vérifie si une date est un jour de pont"""
        if date.weekday() >= 5 or self.cal.is_holiday(date):
            return False
            
        prev_day = date - timedelta(days=1)
        next_day = date + timedelta(days=1)
        prev_is_off = prev_day.weekday() >= 5 or self.cal.is_holiday(prev_day)
        next_is_off = next_day.weekday() >= 5 or self.cal.is_holiday(next_day)
        
        return prev_is_off and next_is_off

    def show_context_menu(self, position):
        """Affiche le menu contextuel pour la suppression d'une attribution"""
        item = self.itemAt(position)
        if not item:
            return
            
        row = self.row(item)
        col = self.column(item)
        
        date = self.get_date_from_cell(row, col)
        if not date:
            return
            
        base_col = (col // 5) * 5
        if col not in [base_col + 2, base_col + 3, base_col + 4]:
            return
            
        period = col - base_col - 1
        current_person = self.pre_attribution_widget.get_current_person()
        
        if not current_person:
            return
            
        # Vérifier si une attribution existe pour cette cellule
        attributions = self.pre_attribution_widget.pre_attributions.get(current_person.name, {})
        if (date, period) in attributions:
            menu = QMenu(self)
            delete_action = menu.addAction("Supprimer l'attribution")
            action = menu.exec(self.mapToGlobal(position))
            
            if action == delete_action:
                self.delete_attribution(date, period, current_person)

    def assign_post(self, date, period, post_type):
        """Attribue un poste à une cellule"""
        current_person = self.pre_attribution_widget.get_current_person()
        if current_person:
            if current_person.name not in self.pre_attribution_widget.pre_attributions:
                self.pre_attribution_widget.pre_attributions[current_person.name] = {}
            
            # Stocker l'attribution
            self.pre_attribution_widget.pre_attributions[current_person.name][(date, period)] = post_type
            
            # Ajouter l'action à l'historique
            details = f"{current_person.name} - {post_type} - {date.strftime('%d/%m/%Y')} - Période {period}"
            self.pre_attribution_widget.history_widget.add_action("Attribution", details)
            
            # Mettre à jour l'affichage
            self.update_display(current_person)
            self.pre_attribution_widget.post_list.update_for_period(date, period, current_person)

    def delete_attribution(self, date, period, person):
        """Supprime une attribution existante"""
        if person.name in self.pre_attribution_widget.pre_attributions:
            attributions = self.pre_attribution_widget.pre_attributions[person.name]
            if (date, period) in attributions:
                # Récupérer le type de poste avant de le supprimer
                post_type = attributions[(date, period)]
                
                del attributions[(date, period)]
                if not attributions:
                    del self.pre_attribution_widget.pre_attributions[person.name]
                
                # Ajouter l'action à l'historique
                details = f"{person.name} - {post_type} - {date.strftime('%d/%m/%Y')} - Période {period}"
                self.pre_attribution_widget.history_widget.add_action("Suppression", details)
                
                # Mettre à jour l'affichage
                self.update_display(person)
                self.pre_attribution_widget.post_list.update_for_period(date, period, person)

    def create_calendar(self):
        """Crée la structure du calendrier"""
        self.clear()
        days_abbr = ["L", "M", "M", "J", "V", "S", "D"]
        months = (self.end_date.year - self.start_date.year) * 12 + self.end_date.month - self.start_date.month + 1

        total_columns = 5 * months  # 5 colonnes par mois (Jour, Mois, M, AM, S)
        self.setColumnCount(total_columns)
        self.setRowCount(31)

        current_date = self.start_date
        for i in range(months):
            base_col = i * 5
            month_name = current_date.strftime("%b")
            self.setHorizontalHeaderItem(base_col, QTableWidgetItem("Jour"))
            self.setHorizontalHeaderItem(base_col + 1, QTableWidgetItem(month_name))
            self.setHorizontalHeaderItem(base_col + 2, QTableWidgetItem("M"))
            self.setHorizontalHeaderItem(base_col + 3, QTableWidgetItem("AM"))
            self.setHorizontalHeaderItem(base_col + 4, QTableWidgetItem("S"))
            current_date += timedelta(days=32)
            current_date = current_date.replace(day=1)

        # Réduire la hauteur des lignes et la largeur des colonnes
        for row in range(self.rowCount()):
            self.setRowHeight(row, int(self.rowHeight(row) * 4/6))
        for col in range(self.columnCount()):
            self.setColumnWidth(col, int(self.columnWidth(col) * 3/5))

        self.fill_calendar()

    def update_dates(self, start_date, end_date):
        """Met à jour les dates et rafraîchit l'affichage"""
        self.start_date = start_date
        self.end_date = end_date
        self.create_calendar()
        current_person = self.pre_attribution_widget.get_current_person()
        if current_person:
            self.update_display(current_person)

    def fill_calendar(self):
        """Remplit le calendrier avec les dates"""
        current_date = self.start_date
        while current_date <= self.end_date:
            row = current_date.day - 1
            month_col = (current_date.year - self.start_date.year) * 12 + current_date.month - self.start_date.month
            base_col = month_col * 5

            is_weekend = current_date.weekday() >= 5
            is_holiday = self.cal.is_holiday(current_date)
            
            # Check for bridge days
            is_bridge = False
            if not (is_weekend or is_holiday):
                # Check if it's between a holiday and a weekend
                prev_day = current_date - timedelta(days=1)
                next_day = current_date + timedelta(days=1)
                
                prev_is_off = prev_day.weekday() >= 5 or self.cal.is_holiday(prev_day)
                next_is_off = next_day.weekday() >= 5 or self.cal.is_holiday(next_day)
                
                is_bridge = prev_is_off and next_is_off
            
            background_color = color_system.get_color('weekend') if (is_weekend or is_holiday or is_bridge) else color_system.get_color('weekday')

            # Colonne jour
            day_item = QTableWidgetItem(str(current_date.day))
            day_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            day_item.setBackground(QBrush(background_color))
            self.setItem(row, base_col, day_item)

            # Colonne jour de la semaine
            weekday_item = QTableWidgetItem(["L", "M", "M", "J", "V", "S", "D"][current_date.weekday()])
            weekday_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            weekday_item.setForeground(QBrush(color_system.get_color('text', 'secondary')))
            weekday_item.setBackground(QBrush(background_color))
            self.setItem(row, base_col + 1, weekday_item)

            # Colonnes périodes (M, AM, S)
            for i in range(3):
                item = QTableWidgetItem()
                item.setBackground(QBrush(background_color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, base_col + 2 + i, item)

            current_date += timedelta(days=1)

    def get_date_from_cell(self, row, col):
        """Retourne la date correspondant à une cellule"""
        try:
            month_col = col // 5
            year = self.start_date.year + (self.start_date.month + month_col - 1) // 12
            month = (self.start_date.month + month_col - 1) % 12 + 1
            return date(year, month, row + 1)
        except ValueError:
            return None

    def update_display(self, person):
        """Met à jour l'affichage pour la personne sélectionnée"""
        # Réinitialiser l'affichage avec le calendrier de base
        self.fill_calendar()
        
        if not person:
            return
            
        # Affichage des desiderata en premier pour qu'ils soient toujours visibles
        for desiderata in person.desiderata:
            current_date = desiderata.start_date
            while current_date <= desiderata.end_date:
                row = current_date.day - 1
                month_col = (current_date.year - self.start_date.year) * 12 + current_date.month - self.start_date.month
                base_col = month_col * 5
                
                period_col = {1: 2, 2: 3, 3: 4}  # Mapping période -> colonne relative
                col = base_col + period_col[desiderata.period]
                item = self.item(row, col)
                if item:
                    # Déterminer si c'est un weekend ou férié
                    is_weekend = current_date.weekday() >= 5
                    is_holiday = self.cal.is_holiday(current_date)
                    is_bridge = False
                    if not (is_weekend or is_holiday):
                        prev_day = current_date - timedelta(days=1)
                        next_day = current_date + timedelta(days=1)
                        prev_is_off = prev_day.weekday() >= 5 or self.cal.is_holiday(prev_day)
                        next_is_off = next_day.weekday() >= 5 or self.cal.is_holiday(next_day)
                        is_bridge = prev_is_off and next_is_off
                    
                    is_special_day = is_weekend or is_holiday or is_bridge
                    priority = getattr(desiderata, 'priority', 'primary')
                    
                    # Obtenir la couleur du système de couleurs
                    if priority == 'primary':
                        color = color_system.colors['desiderata']['primary']['weekend' if is_special_day else 'normal']
                    else:  # secondary
                        color = color_system.colors['desiderata']['secondary']['weekend' if is_special_day else 'normal']
                    
                    # Vérifier que la couleur est bien un QColor
                    if isinstance(color, QColor):
                        item.setBackground(QBrush(color))
                    else:
                        # Fallback sur une couleur par défaut si la couleur n'est pas valide
                        fallback_color = QColor('#E2E8F0')
                        item.setBackground(QBrush(fallback_color))
                
                current_date += timedelta(days=1)

        # Affichage des pré-attributions par dessus les desiderata
        attributions = self.pre_attribution_widget.pre_attributions.get(person.name, {})
        for (d, p), post in attributions.items():
            row = d.day - 1
            month_col = (d.year - self.start_date.year) * 12 + d.month - self.start_date.month
            base_col = month_col * 5
            period_col = {1: 2, 2: 3, 3: 4}  # Mapping période -> colonne relative
            col = base_col + period_col[p]
            
            item = self.item(row, col)
            if item:
                item.setText(post)
                # Utiliser la méthode get_color du système de couleurs
                available_color = color_system.get_color('available')
                text_color = color_system.get_color('text', 'primary')
                if available_color:
                    item.setBackground(QBrush(available_color))
                    if text_color:
                        item.setForeground(QBrush(text_color))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Utiliser une police en gras pour les pré-attributions
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    # Fallback sur des couleurs par défaut
                    item.setBackground(QBrush(QColor('#D1E6D6')))
                    item.setForeground(QBrush(QColor('#2D3748')))


class AttributionHistoryWidget(QTableWidget):
    """Widget pour afficher l'historique des attributions"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pre_attribution_widget = parent
        self.history = []  # Liste des actions [(timestamp, type, details)]
        self.init_ui()

    def init_ui(self):
        """Initialise l'interface de l'historique"""
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Date/Heure", "Action", "Détails"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: """ + color_system.colors['table']['border'].name() + """;
                border: 1px solid """ + color_system.colors['container']['border'].name() + """;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid """ + color_system.colors['table']['border'].name() + """;
            }
            QTableWidget::item:selected {
                background-color: """ + color_system.colors['table']['selected'].name() + """;
            }
        """)

    def add_action(self, action_type, details):
        """Ajoute une action à l'historique
        
        Args:
            action_type (str): Type d'action ('Attribution' ou 'Suppression')
            details (str): Détails de l'action
        """
        # Ajouter l'action à l'historique
        timestamp = datetime.now()
        self.history.append((timestamp, action_type, details))
        
        # Ajouter une nouvelle ligne au début du tableau
        row = 0
        self.insertRow(row)
        
        # Timestamp
        time_item = QTableWidgetItem(timestamp.strftime("%d/%m %H:%M"))
        self.setItem(row, 0, time_item)
        
        # Type d'action avec code couleur
        action_item = QTableWidgetItem(action_type)
        if action_type == "Suppression":
            color = color_system.colors['danger']
        else:
            color = color_system.colors['available']
        
        if isinstance(color, QColor):
            action_item.setBackground(QBrush(color))
        else:
            # Fallback sur une couleur par défaut
            action_item.setBackground(QBrush(QColor('#C28E8E' if action_type == "Suppression" else '#D1E6D6')))
        self.setItem(row, 1, action_item)
        
        # Détails de l'action
        details_item = QTableWidgetItem(details)
        self.setItem(row, 2, details_item)
        
        # Limiter l'historique aux 50 dernières actions
        if self.rowCount() > 50:
            self.removeRow(self.rowCount() - 1)
            self.history = self.history[:50]
        
        self.resizeColumnsToContents()

    def clear_history(self):
        """Efface l'historique"""
        self.history.clear()
        self.setRowCount(0)
