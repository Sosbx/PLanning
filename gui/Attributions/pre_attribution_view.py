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
from ..styles import color_system, ADD_BUTTON_STYLE, EDIT_DELETE_BUTTON_STYLE
from ..components.planning_table_component import PlanningTableComponent

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
        
        # Charger les pré-attributions existantes et l'historique
        result = self.main_window.data_persistence.load_pre_attributions(load_history=True)
        if isinstance(result, tuple):
            self.pre_attributions, self.history = result
        else:
            self.pre_attributions = result
            self.history = []
        
        # S'assurer que pre_attributions est un dictionnaire et non un tuple
        if isinstance(self.pre_attributions, tuple):
            self.pre_attributions, _ = self.pre_attributions
        
        # S'assurer que pre_attributions est initialisé comme un dictionnaire vide si None
        self.pre_attributions = self.pre_attributions or {}
        
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

    def _get_pre_attributions(self):
        """Récupère les pré-attributions de manière sécurisée"""
        if hasattr(self, 'pre_attributions'):
            if isinstance(self.pre_attributions, tuple):
                pre_attributions, _ = self.pre_attributions
                return pre_attributions or {}
            return self.pre_attributions or {}
        return {}
    
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
        """Sauvegarde les pré-attributions actuelles et leur historique"""
        try:
            # Récupérer les pré-attributions de manière sécurisée
            pre_attributions = self._get_pre_attributions()
            
            # Récupérer l'historique
            history = self.history_widget.history if hasattr(self.history_widget, 'history') else []
            
            # Sauvegarder les données
            self.main_window.data_persistence.save_pre_attributions(
                pre_attributions,
                history
            )
            
            # Rafraîchir l'affichage après la sauvegarde
            if hasattr(self, 'history_widget'):
                self.history_widget.refresh_display()
                
            QMessageBox.information(self, "Succès", "Les pré-attributions ont été sauvegardées avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde des pré-attributions : {str(e)}")

    def refresh_custom_posts(self):
        """Actualise les postes personnalisés et met à jour l'affichage"""
        # Recharger les postes personnalisés depuis la persistance des données
        self.custom_posts = self.main_window.data_persistence.load_custom_posts()
        
        # Mettre à jour l'affichage pour la personne actuellement sélectionnée
        current_person = self.get_current_person()
        if current_person:
            # Mettre à jour le tableau de planning
            self.planning_table.update_display(current_person)
            
            # Mettre à jour la liste des postes disponibles
            self.post_list.update_for_person(current_person)
            
        # Journaliser l'actualisation des postes personnalisés
        print("Postes personnalisés actualisés dans l'onglet de pré-attribution")
    
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
            # Réinitialiser les pré-attributions avec un dictionnaire vide
            self.pre_attributions = {}
            
            # Mettre à jour l'affichage
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

    def _get_pre_attributions(self):
        """Récupère les pré-attributions de manière sécurisée"""
        if hasattr(self, 'pre_attributions'):
            if isinstance(self.pre_attributions, tuple):
                pre_attributions, _ = self.pre_attributions
                return pre_attributions or {}
            return self.pre_attributions or {}
        return {}


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
            for person_name, person_attributions in self._get_pre_attributions().items():
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
        
        # Afficher un message de débogage pour voir quelle période est passée
        print(f"get_available_posts pour la date {date} et la période {period}")
        
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
                print(f"Post {post_type} - Heure de début: {post_start_hour}h")
                
                # Afficher les postes en fonction de la période sélectionnée
                # Période 1 = Matin (7h-13h)
                # Période 2 = Après-midi (13h-18h)
                # Période 3 = Soir/Nuit (18h-7h)
                if period == 1 and 7 <= post_start_hour < 13 and post_type != "CT":  # Matin (sauf CT)
                    print(f"  -> Ajout du poste {post_type} pour le matin")
                    is_attributed = self.is_post_attributed(date, period, post_type)
                    available_posts[post_type] = is_attributed
                elif period == 2 and (
                    (13 <= post_start_hour < 18) or  # Après-midi normal
                    post_type == "CT"  # CT toujours en après-midi
                ):
                    print(f"  -> Ajout du poste {post_type} pour l'après-midi")
                    is_attributed = self.is_post_attributed(date, period, post_type)
                    available_posts[post_type] = is_attributed
                elif period == 3 and (post_start_hour >= 18 or post_start_hour < 7):  # Soir/Nuit
                    print(f"  -> Ajout du poste {post_type} pour le soir/nuit")
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
        for person_attributions in self._get_pre_attributions().values():
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
class PreAttributionTable(PlanningTableComponent):
    """Tableau pour afficher et gérer les pré-attributions"""

    def __init__(self, start_date, end_date, pre_attribution_widget):
        super().__init__()
        self.cal = France()
        self.pre_attribution_widget = pre_attribution_widget
        self.setup_planning_dates(start_date, end_date)
        self.populate_days()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Connecter le double-clic
        self.cellDoubleClicked.connect(self.handle_cell_double_click)
        
        # Connecter le clic simple pour mettre à jour la liste des postes
        self.cellClicked.connect(self.handle_cell_click)

    def handle_cell_click(self, row, col):
        """Gère le clic simple sur une cellule"""
        # Calculer le début du groupe de colonnes pour ce mois
        # Chaque mois a 4 colonnes: J, M, AM, S
        # La colonne 0 est la colonne des jours du mois
        if col == 0:  # Colonne des jours du mois
            return
            
        # Calculer l'index du mois (0, 1, 2, ...)
        month_idx = (col - 1) // 4
        
        # Calculer la colonne de base pour ce mois
        base_col = month_idx * 4 + 1
        
        # Déterminer la période en fonction de la colonne relative
        if col in [base_col + 1, base_col + 2, base_col + 3]:  # M, AM, S
            period = col - base_col  # 1->1 (M), 2->2 (AM), 3->3 (S)
            date = self.get_date_from_cell(row, col)
            if date:
                self.cell_clicked.emit(date, period)

    def handle_cell_double_click(self, row, col):
        """Gère le double-clic sur une cellule"""
        # Calculer le début du groupe de colonnes pour ce mois
        # Chaque mois a 4 colonnes: J, M, AM, S
        # La colonne 0 est la colonne des jours du mois
        if col == 0:  # Colonne des jours du mois
            return
            
        # Calculer l'index du mois (0, 1, 2, ...)
        month_idx = (col - 1) // 4
        
        # Calculer la colonne de base pour ce mois
        base_col = month_idx * 4 + 1
        
        # Déterminer la période en fonction de la colonne relative
        if col in [base_col + 1, base_col + 2, base_col + 3]:  # M, AM, S
            period = col - base_col  # 1->1 (M), 2->2 (AM), 3->3 (S)
            date = self.get_date_from_cell(row, col)
            
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
        
        # Vérifier les desiderata - CORRECTION: vérifier uniquement la période concernée
        for des in current_person.desiderata:
            # Vérifier si le desiderata s'applique à cette date ET à cette période précise
            if des.start_date <= date <= des.end_date and des.period == period:
                priority = getattr(des, 'priority', 'primary')
                violations.append(f"Un desiderata {priority} existe pour cette période")
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
                violations.append("Entorse aux règles NL (pas de poste le même jour/lendemain)")


            # Vérifier les contraintes NM/NA
            if not constraints.check_nm_na_constraint(current_person, date, slot, planning):
                violations.append("Entorse aux règles NM/NA")

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
        
        # Afficher un message de débogage pour voir quelle période est passée
        print(f"Affichage du menu pour la date {date} et la période {period}")
        
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
        
        # 1. Vérification des desiderata - CORRECTION: vérifier par période
        for des in current_person.desiderata:
            # Extraire la période à partir du nouveau slot
            new_slot_period = self._get_period_from_slot(new_slot)
            
            if des.start_date <= date <= des.end_date and des.period == new_slot_period:
                priority = getattr(des, 'priority', 'primary')
                warnings.append(f"- Non respect d'un desiderata {priority}")
        
        # 2. Utilisation directe des méthodes de constraints.py
        if not constraints.check_nl_constraint(current_person, date, new_slot, temp_planning):
            warnings.append("- Entorse aux règles NL")
            
        if not constraints.check_nm_na_constraint(current_person, date, new_slot, temp_planning):
            warnings.append("- Entorse aux règles NM/NA")
            
        if not constraints.check_morning_after_night_shifts(current_person, date, new_slot, temp_planning):
            warnings.append("- Entorse aux règles de repos après poste de nuit")
            
        if not constraints.check_consecutive_night_shifts(current_person, date, new_slot, temp_planning):
            warnings.append("- Entorse aux règles de nuits consécutives")
            
        if not constraints.check_consecutive_working_days(current_person, date, new_slot, temp_planning):
            warnings.append("- Entorse aux règles de jours consécutifs")
            
        return warnings

    def _get_pre_attributions(self):
        """Récupère les pré-attributions de manière sécurisée"""
        pre_attributions = self.pre_attribution_widget.pre_attributions
        
        # Si pre_attributions est un tuple, extraire le dictionnaire
        if isinstance(pre_attributions, tuple):
            pre_attributions, _ = pre_attributions
        
        # S'assurer que pre_attributions est un dictionnaire
        if pre_attributions is None:
            pre_attributions = {}
            
        return pre_attributions

    # Nouvelle méthode à ajouter pour déterminer la période à partir d'un slot
    def _get_period_from_slot(self, slot):
        """
        Détermine la période (1, 2 ou 3) d'un TimeSlot en fonction de son heure de début.
        1 = Matin (7h-13h)
        2 = Après-midi (13h-18h)
        3 = Soir/Nuit (18h-7h)
        """
        start_hour = slot.start_time.hour
        
        if 7 <= start_hour < 13:
            return 1  # Matin
        elif 13 <= start_hour < 18:
            return 2  # Après-midi
        else:
            return 3  # Soir/Nuit

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
        
        # Indiquer explicitement qu'il s'agit d'une pré-attribution pour la vérification des contraintes
        warnings = []
        
        # Vérifier d'abord le nombre maximum de postes par jour
        day = temp_planning.get_day(date)
        count_posts = 0
        if day:
            for s in day.slots:
                if s.assignee == current_person.name:
                    count_posts += 1
                    
        if count_posts >= 2:
            warnings.append("- Dépasse le maximum de 2 postes par jour")
        
        # Vérifier les autres contraintes uniquement si la limite de postes est respectée
        if not warnings:
            warnings = self._check_all_constraints(current_person, date, new_slot, temp_planning)

        # Si des violations sont détectées, demander confirmation
        if warnings:
            warning_text = "Cette pré-attribution ne respecte pas les contraintes suivantes :\n\n"
            warning_text += "\n".join(warnings)
            warning_text += "\n\nVoulez-vous continuer quand même ?"
            
            reply = QMessageBox.question(
                self,
                "Confirmation d'entorse aux contraintes",
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
        
        # Ajouter toutes les pré-attributions existantes en utilisant _get_pre_attributions
        pre_attributions = self._get_pre_attributions()
        
        for person_name, attributions in pre_attributions.items():
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
        # Utiliser la méthode sécurisée _get_pre_attributions
        attributions = self._get_pre_attributions().get(current_person.name, {})
        
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
            
        # Calculer le début du groupe de colonnes pour ce mois
        # Chaque mois a 4 colonnes: J, M, AM, S
        # La colonne 0 est la colonne des jours du mois
        if col == 0:  # Colonne des jours du mois
            return
            
        # Calculer l'index du mois (0, 1, 2, ...)
        month_idx = (col - 1) // 4
        
        # Calculer la colonne de base pour ce mois
        base_col = month_idx * 4 + 1
        
        # Déterminer la période en fonction de la colonne relative
        if col not in [base_col + 1, base_col + 2, base_col + 3]:  # M, AM, S
            return
            
        period = col - base_col  # 1->1 (M), 2->2 (AM), 3->3 (S)
        current_person = self.pre_attribution_widget.get_current_person()
        
        if not current_person:
            return
            
        # Vérifier si une attribution existe pour cette cellule en utilisant _get_pre_attributions
        pre_attributions = self._get_pre_attributions()
        attributions = pre_attributions.get(current_person.name, {})
        
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
            # Utiliser _get_pre_attributions pour récupérer et modifier de manière sécurisée
            pre_attributions = self._get_pre_attributions()
            
            if current_person.name not in pre_attributions:
                pre_attributions[current_person.name] = {}
            
            # Stocker l'attribution
            pre_attributions[current_person.name][(date, period)] = post_type
            
            # Mettre à jour pre_attributions dans le widget parent
            self.pre_attribution_widget.pre_attributions = pre_attributions
            
            # Ajouter l'action à l'historique
            details = f"{current_person.name} - {post_type} - {date.strftime('%d/%m/%Y')} - Période {period}"
            self.pre_attribution_widget.history_widget.add_action("Attribution", details)
            
            # Mettre à jour l'affichage
            self.update_display(current_person)
            self.pre_attribution_widget.post_list.update_for_period(date, period, current_person)

    # Méthode à modifier dans PreAttributionTable
    def delete_attribution(self, date, period, person):
        """Supprime une attribution existante"""
        # Utiliser _get_pre_attributions pour récupérer et modifier de manière sécurisée
        pre_attributions = self._get_pre_attributions()
        
        if person.name in pre_attributions:
            attributions = pre_attributions[person.name]
            if (date, period) in attributions:
                # Récupérer le type de poste avant de le supprimer
                post_type = attributions[(date, period)]
                
                del attributions[(date, period)]
                if not attributions:
                    del pre_attributions[person.name]
                
                # Mettre à jour pre_attributions dans le widget parent
                self.pre_attribution_widget.pre_attributions = pre_attributions
                
                # Ajouter l'action à l'historique
                details = f"{person.name} - {post_type} - {date.strftime('%d/%m/%Y')} - Période {period}"
                self.pre_attribution_widget.history_widget.add_action("Suppression", details)
                
                # Mettre à jour l'affichage
                self.update_display(person)
                self.pre_attribution_widget.post_list.update_for_period(date, period, person)
    def update_dates(self, start_date, end_date):
        """Met à jour les dates et rafraîchit l'affichage"""
        # Sauvegarder le nombre de lignes actuel pour détecter si une nouvelle ligne a été ajoutée
        old_row_count = self.rowCount()
        
        # Mettre à jour les dates et le tableau
        self.setup_planning_dates(start_date, end_date)
        self.populate_days()
        
        # Vérifier si une nouvelle ligne a été ajoutée et l'enlever si nécessaire
        if self.rowCount() > old_row_count + 1:  # +1 car on s'attend à ce que setup_planning_dates ajoute une ligne
            self.removeRow(1)  # Supprimer la ligne en trop (la deuxième ligne, car la première est l'en-tête des mois)
        
        # Mettre à jour l'affichage pour la personne actuelle
        current_person = self.pre_attribution_widget.get_current_person()
        if current_person:
            self.update_display(current_person)

    def get_date_from_cell(self, row, col):
        """Retourne la date correspondant à une cellule"""
        try:
            # Ajuster la ligne pour tenir compte de l'en-tête des mois
            # La première ligne (row=0) est l'en-tête des mois, donc les jours commencent à row=1
            if row == 0:  # Si on clique sur l'en-tête des mois, retourner None
                return None
                
            day = row  # row 1 correspond au jour 1, row 2 au jour 2, etc.
            
            # Calculer le mois en fonction de la colonne
            # Chaque mois a 4 colonnes: J, M, AM, S
            # La colonne 0 est la colonne des jours du mois
            if col == 0:  # Colonne des jours du mois
                # Utiliser le mois de la date de début
                month = self.start_date.month
                year = self.start_date.year
            else:
                # Calculer l'index du mois (0, 1, 2, ...)
                month_idx = (col - 1) // 4
                
                # Calculer le mois et l'année
                total_months = self.start_date.month + month_idx - 1
                year = self.start_date.year + total_months // 12
                month = total_months % 12 + 1
            
            return date(year, month, day)
        except ValueError:
            return None

    def update_display(self, person):
        """Met à jour l'affichage pour la personne sélectionnée"""
        # Réinitialiser l'affichage en repeuplant les jours
        self.populate_days()
        
        if not person:
            return
            
        # Affichage des desiderata en premier pour qu'ils soient toujours visibles
        for desiderata in person.desiderata:
            current_date = desiderata.start_date
            while current_date <= desiderata.end_date:
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
                
                # Utiliser la méthode update_cell de PlanningTableComponent
                self.update_cell(current_date, desiderata.period, "", color)
                
                current_date += timedelta(days=1)

        # Affichage des pré-attributions par dessus les desiderata
        # Utiliser la méthode sécurisée pour récupérer les pré-attributions
        attributions = self._get_pre_attributions().get(person.name, {})
        for (date_val, period), post in attributions.items():
            # Utiliser la méthode update_cell de PlanningTableComponent
            available_color = color_system.get_color('available') or QColor('#D1E6D6')
            self.update_cell(
                date_val, 
                period, 
                post, 
                available_color, 
                color_system.get_color('text', 'primary') or QColor('#2D3748')
            )


class AttributionHistoryWidget(QTableWidget):
    """Widget pour afficher l'historique des attributions"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pre_attribution_widget = parent
        
        # Charger les pré-attributions et l'historique
        result = self.pre_attribution_widget.main_window.data_persistence.load_pre_attributions(load_history=True)
        if isinstance(result, tuple):
            pre_attributions, self.history = result
        else:
            pre_attributions = result
            self.history = []
        
        # S'assurer que history est une liste et non None
        self.history = self.history or []
        
        # Convertir les pré-attributions existantes en entrées d'historique si elles n'y sont pas déjà
        self._sync_pre_attributions_to_history(pre_attributions)
        
        self.init_ui()
        
        # Afficher l'historique complet au démarrage
        self.refresh_display()

    def init_ui(self):
        """Initialise l'interface de l'historique"""
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Date", "Garde", "Médecin"])
        
        # Enable sorting
        self.setSortingEnabled(True)
        
        # Configure header and general properties
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionsClickable(True)
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
            QHeaderView::section {
                background-color: """ + color_system.colors['container']['background'].name() + """;
                padding: 5px;
                border: none;
                border-bottom: 1px solid """ + color_system.colors['container']['border'].name() + """;
            }
            QHeaderView::section:hover {
                background-color: """ + color_system.colors['table']['selected'].name() + """;
            }
        """)

    def add_action(self, action_type, details):
        """Ajoute une action à l'historique
        
        Args:
            action_type (str): Type d'action ('Attribution' ou 'Suppression')
            details (str): Détails de l'action au format "nom_medecin - type_garde - date - période"
        """
        # Parser les détails
        parts = details.split(" - ")
        if len(parts) >= 4:
            doctor_name = parts[0]
            guard_type = parts[1]
            date_str = parts[2]
            
            if action_type == "Suppression":
                # Trouver et supprimer l'entrée correspondante dans l'historique
                for i, (_, _, hist_details) in enumerate(self.history):
                    hist_parts = hist_details.split(" - ")
                    if (len(hist_parts) >= 4 and
                        hist_parts[0] == doctor_name and
                        hist_parts[1] == guard_type and
                        hist_parts[2] == date_str):
                        del self.history[i]
                        break
            else:
                # Ajouter la nouvelle attribution à l'historique
                timestamp = datetime.now()
                self.history.append((timestamp, action_type, details))
            
            # Mettre à jour l'affichage
            self.refresh_display()
            
            # Sauvegarder l'historique
            self.pre_attribution_widget.main_window.data_persistence.save_pre_attributions(
                self.pre_attribution_widget.pre_attributions,
                self.history
            )
            
    
    def _sync_pre_attributions_to_history(self, pre_attributions):
        """Synchronise les pré-attributions avec l'historique"""
        from datetime import datetime
        
        # Créer un ensemble des attributions déjà dans l'historique
        existing_entries = set()
        for entry in self.history:
            if isinstance(entry, tuple) and len(entry) >= 3:
                _, _, details = entry
                existing_entries.add(details)
        
        # Ajouter les pré-attributions qui ne sont pas dans l'historique
        for person_name, attributions in pre_attributions.items():
            for (date_obj, period), post_type in attributions.items():
                details = f"{person_name} - {post_type} - {date_obj.strftime('%d/%m/%Y')} - Période {period}"
                
                if details not in existing_entries:
                    # Ajouter à l'historique avec la date actuelle comme timestamp
                    self.history.append((datetime.now(), "Attribution", details))
                    existing_entries.add(details)

    def refresh_display(self):
        """Rafraîchit l'affichage de l'historique"""
        try:
            # Désactiver temporairement le tri
            self.setSortingEnabled(False)
            
            # Effacer le tableau
            self.setRowCount(0)
            
            # Trier l'historique par date (plus récent en premier)
            sorted_history = sorted(
                self.history,
                key=lambda x: x[0] if hasattr(x[0], 'timestamp') else datetime.now().timestamp(),
                reverse=True
            )
            
            # Remplir avec les données actuelles
            for entry in sorted_history:
                if isinstance(entry, tuple) and len(entry) >= 3:
                    timestamp, action_type, details = entry
                    
                    # Vérifier que details est bien formaté
                    parts = details.split(" - ")
                    if len(parts) >= 3:  # Au moins médecin, garde et date
                        doctor_name = parts[0]
                        guard_type = parts[1]
                        date_str = parts[2]
                        
                        row = self.rowCount()
                        self.insertRow(row)
                        
                        # Date avec tri personnalisé
                        date_item = QTableWidgetItem(date_str)
                        if hasattr(timestamp, 'timestamp'):
                            date_item.setData(Qt.ItemDataRole.UserRole, timestamp.timestamp())
                        
                        self.setItem(row, 0, date_item)
                        
                        # Type de garde
                        guard_item = QTableWidgetItem(guard_type)
                        color = color_system.colors.get('available')
                        if isinstance(color, QColor):
                            guard_item.setBackground(QBrush(color))
                        else:
                            guard_item.setBackground(QBrush(QColor('#D1E6D6')))
                        self.setItem(row, 1, guard_item)
                        
                        # Nom du médecin
                        doctor_item = QTableWidgetItem(doctor_name)
                        self.setItem(row, 2, doctor_item)
            
            # Réactiver le tri
            self.setSortingEnabled(True)
            self.resizeColumnsToContents()
            
        except Exception as e:
            print(f"Erreur lors du rafraîchissement de l'affichage: {e}")
    
    def load_history(self):
        """Charge l'historique depuis la persistance des données"""
        try:
            # Charger à la fois les pré-attributions et l'historique
            result = self.pre_attribution_widget.main_window.data_persistence.load_pre_attributions(load_history=True)
            if isinstance(result, tuple):
                pre_attributions, self.history = result
            else:
                pre_attributions = result
                self.history = []
            
            # S'assurer que history est une liste et non None
            self.history = self.history or []
            
            # Synchroniser avec les pré-attributions existantes
            self._sync_pre_attributions_to_history(pre_attributions)
            
            # Rafraîchir l'affichage
            self.refresh_display()
            return True
        except Exception as e:
            print(f"Erreur lors du chargement de l'historique: {e}")
            return False

    def clear_history(self):
        """Efface l'historique"""
        self.history.clear()
        self.setRowCount(0)
        # Sauvegarder l'historique vide
        self.pre_attribution_widget.main_window.data_persistence.save_pre_attributions(
            self.pre_attribution_widget.pre_attributions,
            self.history
        )
