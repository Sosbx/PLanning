# © 2024 HILAL Arkane. Tous droits réservés.
# gui/planning_comparison_view.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QHeaderView, QMessageBox,
                             QTableWidget, QTableWidgetItem, QDialog, QLabel, QScrollArea, QTextEdit, QGridLayout)

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont, QTextCharFormat
from datetime import date, timedelta, datetime, time
from core.utils import get_post_period
from core.Constantes.models import TimeSlot, Doctor, CAT
from dateutil.relativedelta import relativedelta
from core.Constantes.constraints import PlanningConstraints
from gui.Echanges.post_filter_component import PostFilterComponent
from gui.components.planning_table_component import PlanningTableComponent
from workalendar.europe import France

from ..styles import color_system, StyleConstants

# Get colors from color system
WEEKEND_COLOR = color_system.get_color('weekend')
WEEKDAY_COLOR = color_system.get_color('weekday')
WEEKDAY_TEXT_COLOR = color_system.get_color('text', 'primary')
AVAILABLE_COLOR = color_system.get_color('available')
DESIDERATA_COLOR = color_system.get_color('desiderata', 'secondary', 'normal')
WEEKEND_DESIDERATA_COLOR = color_system.get_color('desiderata', 'secondary', 'weekend')

class PlanningComparisonView(QWidget):
    def __init__(self, planning, doctors, cats, main_window):
        super().__init__()
        self.planning = planning
        self.main_window = main_window
        self.doctors = sorted(doctors, key=lambda d: d.name)
        self.cats = sorted(cats, key=lambda c: c.name)
        self.exchange_history = []
        self.post_balance = {}
        
        # Cache pour les objets fréquemment utilisés
        self._constraints = PlanningConstraints()
        self._calendar = France()
        
        # Mapping des périodes vers les abréviations de postes (cache)
        self._period_to_post = {
            1: ["ML", "MC", "MM", "CM", "HM", "SM", "RM"],  # Matin
            2: ["CA", "HA", "SA", "RA", "AL", "AC", "CT"],  # Après-midi
            3: ["CS", "HS", "SS", "RS", "NA", "NM", "NC"]   # Soir
        }
        
        # Initialisation des groupes de postes pour le bilan
        self.post_groups = {
            "Matin": ["ML", "MC", "MM", "CM", "HM", "SM", "RM"],
            "Après-midi": ["CA", "HA", "SA", "RA", "AL", "AC", "CT"],
            "Soir": ["CS", "HS", "SS", "RS", "NA", "NM", "NC"]
        }
         # Ajouter les caches pour les horaires comme dans DoctorPlanningView
        self._start_times = {
            1: (8, 0),   # Matin: 8h
            2: (14, 0),  # Après-midi: 14h
            3: (20, 0)   # Soir: 20h
        }
        self._end_times = {
            1: (13, 0),  # Matin: 13h
            2: (18, 0),  # Après-midi: 18h
            3: (23, 0)   # Soir: 23h
        }
        self.init_ui()

    def init_ui(self):
        # Layout principal avec marges et espacement standardisés
        layout = QVBoxLayout(self)  # Changé en QVBoxLayout pour un meilleur contrôle vertical
        layout.setContentsMargins(
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md']
        )
        layout.setSpacing(StyleConstants.SPACING['md'])

        # Style global du widget - Utilisation directe du système de couleurs
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color_system.get_hex_color('container', 'background')};
                font-family: {StyleConstants.FONT['family']['primary']};
                font-size: {StyleConstants.FONT['size']['md']};
                color: {color_system.get_hex_color('text', 'primary')};
            }}
            QComboBox {{
                background-color: {color_system.get_hex_color('container', 'background')};
                border: 1px solid {color_system.get_hex_color('container', 'border')};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                min-width: 200px;
            }}
            QComboBox:hover {{
                border-color: {color_system.get_hex_color('primary')};
            }}
        """)

        # Zone des sélecteurs compactée
        selectors_layout = QHBoxLayout()
        selectors_layout.setSpacing(StyleConstants.SPACING['md'])

        # Création des sélecteurs avec hauteur réduite
        self.selector1 = QComboBox()
        self.selector2 = QComboBox()
        
        # Style des sélecteurs - Utilisation du système de couleurs
        selector_style = f"""
            QComboBox {{
                background-color: {color_system.get_hex_color('container', 'background')};
                border: 1px solid {color_system.get_hex_color('container', 'border')};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                min-width: 200px;
                min-height: {StyleConstants.SPACING['lg']}px;
                max-height: {StyleConstants.SPACING['xl']}px;
            }}
            QComboBox:hover {{
                border-color: {color_system.get_hex_color('primary')};
            }}
        """
        self.selector1.setStyleSheet(selector_style)
        self.selector2.setStyleSheet(selector_style)
        
        selectors_layout.addWidget(self.selector1)
        selectors_layout.addWidget(self.selector2)
        layout.addLayout(selectors_layout)

        # Ajout des composants de filtre
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(StyleConstants.SPACING['sm'])
        
        # Filtres pour le planning de gauche
        self.filter1 = PostFilterComponent(self)
        self.filter1.filter_changed.connect(lambda filters: self.apply_filters(self.table1, filters))
        
        # Filtres pour le planning de droite
        self.filter2 = PostFilterComponent(self)
        self.filter2.filter_changed.connect(lambda filters: self.apply_filters(self.table2, filters))
        
        filter_layout.addWidget(self.filter1)
        filter_layout.addWidget(self.filter2)
        layout.addLayout(filter_layout)

        # Zone des tableaux
        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(StyleConstants.SPACING['md'])

        # Création des zones de défilement
        scroll_area1 = QScrollArea()
        scroll_area2 = QScrollArea()
        scroll_area1.setWidgetResizable(True)
        scroll_area2.setWidgetResizable(True)

        # Création et configuration des tableaux
        self.table1 = PlanningTableComponent(self)
        self.table2 = PlanningTableComponent(self)
        
        # Configuration des couleurs pour les deux tables - Utilisation du système de couleurs
        colors = {
            "primary": {
                "weekend": color_system.get_rgba_color('danger', alpha=150),   # Rouge vif pour weekend
                "normal": color_system.get_rgba_color('danger', alpha=100)     # Rouge clair pour jour normal
            },
            "secondary": {
                "weekend": color_system.get_rgba_color('info', alpha=150),     # Bleu vif pour weekend
                "normal": color_system.get_rgba_color('info', alpha=100)       # Bleu clair pour jour normal
            },
            "base": {
                "weekend": color_system.get_color('weekend'),
                "normal": color_system.get_color('weekday')
            }
        }

        # Appliquer directement ces couleurs
        self.table1.set_colors(colors)
        self.table2.set_colors(colors)
        
        # Configuration des dimensions adaptatives
        for table in [self.table1, self.table2]:
            table.set_min_row_height(18)
            table.set_max_row_height(25)
            table.set_min_column_widths(
                day_width=25,
                weekday_width=30,
                period_width=35
            )
            table.set_max_column_widths(
                day_width=35,
                weekday_width=40,
                period_width=70
            )
            
            # Configuration des polices
            table.set_font_settings(
                base_size=12,
                header_size=14,
                weekday_size=10
            )
            
        # Connecter les signaux
        self.table1.cell_clicked.connect(self.update_selected_cell)
        self.table1.cell_double_clicked.connect(self.on_cell_double_clicked)
        self.table2.cell_clicked.connect(self.update_selected_cell)
        self.table2.cell_double_clicked.connect(self.on_cell_double_clicked)
        
        scroll_area1.setWidget(self.table1)
        scroll_area2.setWidget(self.table2)

        tables_layout.addWidget(scroll_area1)
        tables_layout.addWidget(scroll_area2)
        layout.addLayout(tables_layout, 1)

        # Section du bas
        self.bottom_section = ComparisonBottomSection(self)
        layout.addWidget(self.bottom_section)

        # Initialisation des attributs de suivi
        self.selected_date = None
        self.selected_period = None
        
        # Initialisation des attributs de filtrage
        self.active_filters1 = self.filter1.get_active_filters()  # Tous les posts par défaut
        self.active_filters2 = self.filter2.get_active_filters()  # Tous les posts par défaut

        # Connexion des signaux
        self.selector1.currentIndexChanged.connect(self.on_selector_changed)
        self.selector2.currentIndexChanged.connect(self.on_selector_changed)

        # Mise à jour initiale des sélecteurs
        self.update_selectors()

        # Synchronisation des barres de défilement
        self.synchronize_scrollbars()

    def synchronize_scrollbars(self):
        """
        Synchronise les barres de défilement des deux tables pour un défilement simultané.
        Adapté pour fonctionner avec PlanningTableComponent.
        """
        # Synchronisation du défilement vertical
        self.table1.verticalScrollBar().valueChanged.connect(self.sync_scroll_vertical_table2)
        self.table2.verticalScrollBar().valueChanged.connect(self.sync_scroll_vertical_table1)

        # Synchronisation du défilement horizontal
        self.table1.horizontalScrollBar().valueChanged.connect(self.sync_scroll_horizontal_table2)
        self.table2.horizontalScrollBar().valueChanged.connect(self.sync_scroll_horizontal_table1)

        self.is_syncing_vertical = False
        self.is_syncing_horizontal = False

    def sync_scroll_vertical_table2(self, value):
        if not self.is_syncing_vertical:
            self.is_syncing_vertical = True
            self.table2.verticalScrollBar().setValue(value)
            self.is_syncing_vertical = False

    def sync_scroll_vertical_table1(self, value):
        if not self.is_syncing_vertical:
            self.is_syncing_vertical = True
            self.table1.verticalScrollBar().setValue(value)
            self.is_syncing_vertical = False

    def sync_scroll_horizontal_table2(self, value):
        if not self.is_syncing_horizontal:
            self.is_syncing_horizontal = True
            self.table2.horizontalScrollBar().setValue(value)
            self.is_syncing_horizontal = False

    def sync_scroll_horizontal_table1(self, value):
        if not self.is_syncing_horizontal:
            self.is_syncing_horizontal = True
            self.table1.horizontalScrollBar().setValue(value)
            self.is_syncing_horizontal = False
    
    def apply_filters(self, table, filters):
        """Applique les filtres de postes à la table spécifiée."""
        # Mise à jour des filtres actifs
        if table == self.table1:
            self.active_filters1 = filters
            self.populate_table(self.table1, self.selector1.currentText(), filters)
        else:
            self.active_filters2 = filters
            self.populate_table(self.table2, self.selector2.currentText(), filters)

    def get_doctor_parts(self, doctor_name):
        """
        Méthode pour récupérer dynamiquement le nombre de parts d'un médecin.
        Doit être adaptée en fonction de l'endroit où cette information est stockée.
        """
        doctor = next((d for d in self.doctors if d.name == doctor_name), None)
        if doctor:
            # Vérifier si le médecin a un attribut ou une méthode pour obtenir le nombre de parts
            return getattr(doctor, 'half_parts', 1)  # Utilise 'half_parts' ou une valeur par défaut de 1
        return None

    def update_selectors(self, preserve_selection=False, allow_new_selection=False):
        current1 = self.selector1.currentText() if preserve_selection else None
        current2 = self.selector2.currentText() if preserve_selection else None

        self.selector1.blockSignals(True)
        self.selector2.blockSignals(True)

        self.selector1.clear()
        self.selector2.clear()

        options = ["Non attribué"] + [d.name for d in self.doctors] + [c.name for c in self.cats]
        self.selector1.addItems(options)
        self.selector2.addItems(options)

        if preserve_selection:
            self.selector1.setCurrentText(current1)
            self.selector2.setCurrentText(current2)

        self.selector1.blockSignals(False)
        self.selector2.blockSignals(False)

        if allow_new_selection:
            # Reconnectez les signaux pour permettre de nouvelles sélections
            self.selector1.currentIndexChanged.connect(self.on_selector_changed)
            self.selector2.currentIndexChanged.connect(self.on_selector_changed)
                
        # Colorer les CAT
        for i in range(self.selector1.count()):
            if i > len(self.doctors):
                self.selector1.setItemData(i, QColor(Qt.GlobalColor.blue), Qt.ItemDataRole.ForegroundRole)
                self.selector2.setItemData(i, QColor(Qt.GlobalColor.blue), Qt.ItemDataRole.ForegroundRole)

        # Conserver le focus sur le sélecteur pour parcourir avec les flèches
        self.selector1.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.selector2.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def on_selector_changed(self):
        """Gère le changement de sélection dans les listes déroulantes"""
        sender = self.sender()
        if sender == self.selector1:
            self.current_selection1 = sender.currentText()
            self.populate_table(self.table1, self.current_selection1, self.active_filters1)
        elif sender == self.selector2:
            self.current_selection2 = sender.currentText()
            self.populate_table(self.table2, self.current_selection2, self.active_filters2)

    def update_comparison(self, preserve_selection=False):
        """Met à jour les deux tableaux de comparaison"""
        if preserve_selection and hasattr(self, 'current_selection1') and hasattr(self, 'current_selection2'):
            selected1 = self.current_selection1
            selected2 = self.current_selection2
        else:
            selected1 = self.selector1.currentText()
            selected2 = self.selector2.currentText()
        
        # Appeler la méthode de la classe pour peupler les tableaux
        self.populate_table(self.table1, selected1, self.active_filters1)
        self.populate_table(self.table2, selected2, self.active_filters2)
        
        if preserve_selection:
            self.selector1.setCurrentText(selected1)
            self.selector2.setCurrentText(selected2)

    def reset_selectors(self):
        self.selector1.setCurrentIndex(0)
        self.selector2.setCurrentIndex(0)
        self.update_comparison()

    def save_current_selections(self):
        self.current_selection1 = self.selector1.currentText()
        self.current_selection2 = self.selector2.currentText()

    def on_assignment_changed(self, old_assignee, new_assignee, post_type):
        """
        Gère la mise à jour après un changement d'assignation.
        """
        self.save_current_selections()
        
        # Récupérer le médecin actuellement sélectionné dans la vue de planning par médecin
        current_doctor_selected = self.main_window.doctor_planning_view.selector.currentText()
        
        # Mettre à jour les tables principales
        self.main_window.planning_tab.update_table()
        self.main_window.update_stats_view()
        
        # Mettre à jour la vue de planning par médecin
        self.main_window.doctor_planning_view.update_view(self.planning, self.doctors, self.cats)
        
        # Si le médecin concerné par le changement est actuellement affiché dans la vue de planning par médecin,
        # forcer une mise à jour complète de son affichage
        if current_doctor_selected == old_assignee or current_doctor_selected == new_assignee:
            # Forcer la mise à jour de la table pour le médecin actuellement sélectionné
            self.main_window.doctor_planning_view.update_table()
        
        # Mettre à jour les sélecteurs en permettant de nouvelles sélections
        self.update_selectors(preserve_selection=True, allow_new_selection=True)
        
        # Mettre à jour les tables
        self.populate_table(self.table1, self.current_selection1, self.active_filters1)
        self.populate_table(self.table2, self.current_selection2, self.active_filters2)
        
        # Ajouter à l'historique des échanges
        self.add_exchange_to_history(old_assignee, new_assignee, post_type)
        
        # Mettre à jour le bilan des postes
        self.update_post_balance(old_assignee, new_assignee, post_type)
        
        # Forcer la mise à jour de l'affichage dans la section du bas
        self.bottom_section.update_content(self.bottom_section.left_selector, 
                                         self.bottom_section.left_content)
        self.bottom_section.update_content(self.bottom_section.right_selector, 
                                         self.bottom_section.right_content)

    def add_exchange_to_history(self, old_assignee, new_assignee, post_type):
        """
        Ajoute un échange à l'historique et met à jour l'affichage si nécessaire.
        """
        exchange = f"{old_assignee} donne {post_type} à {new_assignee}"
        self.exchange_history.append(exchange)
        
        # Mettre à jour l'affichage si la vue d'historique est active
        if (self.bottom_section.left_selector.currentText() == "Historique des échanges"):
            self.bottom_section.show_exchange_history(self.bottom_section.left_content)
        if (self.bottom_section.right_selector.currentText() == "Historique des échanges"):
            self.bottom_section.show_exchange_history(self.bottom_section.right_content)

    def update_post_balance(self, old_assignee, new_assignee, post_type):
        """
        Met à jour le bilan des postes et rafraîchit l'affichage si nécessaire.
        """
        if old_assignee not in self.post_balance:
            self.post_balance[old_assignee] = {"posts": {}, "groups": {}}
        if new_assignee not in self.post_balance:
            self.post_balance[new_assignee] = {"posts": {}, "groups": {}}

        # Mise à jour des postes individuels
        self.post_balance[old_assignee]["posts"][post_type] = (
            self.post_balance[old_assignee]["posts"].get(post_type, 0) - 1
        )
        self.post_balance[new_assignee]["posts"][post_type] = (
            self.post_balance[new_assignee]["posts"].get(post_type, 0) + 1
        )

        # Mise à jour des groupes de postes
        for group, posts in self.post_groups.items():
            if post_type in posts:
                self.post_balance[old_assignee]["groups"][group] = (
                    self.post_balance[old_assignee]["groups"].get(group, 0) - 1
                )
                self.post_balance[new_assignee]["groups"][group] = (
                    self.post_balance[new_assignee]["groups"].get(group, 0) + 1
                )

        # Mettre à jour l'affichage si la vue de bilan est active
        if (self.bottom_section.left_selector.currentText() == "Bilan des postes"):
            self.bottom_section.show_post_balance(self.bottom_section.left_content)
        if (self.bottom_section.right_selector.currentText() == "Bilan des postes"):
            self.bottom_section.show_post_balance(self.bottom_section.right_content)
                
    def reset_view(self):
        # Reset data structures
        self.exchange_history = []
        self.post_balance = {}
        
        # Reset tables
        self.table1.clear()
        self.table2.clear()
        self.table1.setRowCount(0)
        self.table1.setColumnCount(0)
        self.table2.setRowCount(0)
        self.table2.setColumnCount(0)
        
        # Reset selectors
        self.selector1.setCurrentIndex(0)
        self.selector2.setCurrentIndex(0)
        
        # Reset filters
        self.filter1.toggle_all_filters(True)
        self.filter2.toggle_all_filters(True)
        
        # Reset bottom section text widgets
        self.bottom_section.left_content.clear()
        self.bottom_section.right_content.clear()
        
        # Reset bottom section selectors
        self.bottom_section.left_selector.setCurrentIndex(0)
        self.bottom_section.right_selector.setCurrentIndex(0)
        
    def _get_available_doctors(self, date, period):
        """
        Détermine les médecins disponibles pour une date et une période données.
        Suit la même logique que DoctorPlanningView.
        
        Args:
            date (date): Date à vérifier
            period (int): Période (1: Matin, 2: Après-midi, 3: Soir, None: Jour entier)
        
        Returns:
            set: Ensemble des noms des médecins disponibles
        """
        available_personnel = set()
        if not self.planning:
            return available_personnel

        # Récupérer le jour du planning
        day_planning = next((day for day in self.planning.days if day.date == date), None)
        if not day_planning:
            return available_personnel

        # Déterminer les périodes à vérifier
        periods_to_check = [1, 2, 3] if period is None else [period]

        # Déterminer le type de jour
        if self._calendar.is_holiday(date) or date.weekday() == 6:
            day_type = "sunday_holiday"
        elif date.weekday() == 5:
            day_type = "saturday"
        else:
            day_type = "weekday"

        # Pour chaque personne (médecin ou CAT)
        for person in self.doctors + self.cats:
            # Pour chaque période à vérifier
            for check_period in periods_to_check:
                # Vérifier si la personne a déjà un poste dans cette période
                has_slot_in_period = False
                for slot in day_planning.slots:
                    if (slot.assignee == person.name and
                        get_post_period(slot) == check_period - 1):
                        has_slot_in_period = True
                        break
                
                if has_slot_in_period:
                    if period is not None:  # Si on vérifie une période spécifique
                        continue  # Passer à la personne suivante
                    else:
                        break  # Pour la vue jour complet, passer à la personne suivante

                # Récupérer les types de postes possibles pour cette période
                possible_posts = self._period_to_post[check_period]
                
                # Pour chaque type de poste possible dans cette période
                for post_type in possible_posts:
                    can_take_post = True

                    # Pour les CAT, vérifier si le type de poste est autorisé
                    if isinstance(person, CAT):
                        if hasattr(self.planning, 'pre_analysis_results') and self.planning.pre_analysis_results:
                            daily_config = self.planning.pre_analysis_results.get('daily_config')
                            if daily_config:
                                cat_config = None
                                if day_type == "weekday":
                                    cat_config = daily_config.cat_weekday
                                elif day_type == "saturday":
                                    cat_config = daily_config.cat_saturday
                                else:  # sunday_holiday
                                    cat_config = daily_config.cat_sunday_holiday
                                
                                if not cat_config or post_type not in cat_config or cat_config[post_type].total == 0:
                                    can_take_post = False

                    if not can_take_post:
                        continue

                    # Créer un slot test pour ce type de poste
                    try:
                        # Gérer spécifiquement les horaires pour CT
                        if post_type == "CT":
                            start_time = time(10, 0)  # 10h00
                            end_time = time(15, 59)   # 15h59
                        else:
                            start_time = time(self._start_times[check_period][0], 
                                            self._start_times[check_period][1])
                            end_time = time(self._end_times[check_period][0], 
                                        self._end_times[check_period][1])

                        start_datetime = datetime.combine(date, start_time)
                        end_datetime = datetime.combine(date, end_time)
                        
                        # Si le end_time est avant le start_time (cas des postes qui finissent le lendemain)
                        if end_time < start_time:
                            end_datetime = datetime.combine(date + timedelta(days=1), end_time)
                        
                        test_slot = TimeSlot(
                            start_time=start_datetime,
                            end_time=end_datetime,
                            site="Test",
                            slot_type="Test",
                            abbreviation=post_type
                        )
                        
                        # Vérifier si la personne peut prendre ce poste selon les contraintes
                        if self._constraints.can_assign_to_assignee(person, date, test_slot, self.planning):
                            available_personnel.add(person.name)
                            break  # Si disponible pour un poste, passer à la période suivante
                            
                    except Exception as e:
                        continue

        return available_personnel

    def _get_secondary_desiderata_doctors(self, date, period):
        """
        Détermine les médecins ayant des désiderata secondaires pour une date et période données.
        
        Args:
            date (date): Date à vérifier
            period (int): Période (1: Matin, 2: Après-midi, 3: Soir, None: Jour entier)
        
        Returns:
            set: Ensemble des noms des médecins avec désiderata secondaires
        """
        secondary_personnel = set()
        if not self.planning:
            return secondary_personnel

        periods_to_check = [1, 2, 3] if period is None else [period]
        
        for person in self.doctors + self.cats:
            for check_period in periods_to_check:
                has_secondary = any(
                    desiderata.start_date <= date <= desiderata.end_date and
                    desiderata.period == check_period and
                    getattr(desiderata, 'priority', 'primary') == 'secondary'
                    for desiderata in person.desiderata
                )
                
                if has_secondary:
                    secondary_personnel.add(person.name)
                    break

        return secondary_personnel

    def _get_assigned_doctors(self, date):
        """
        Récupère les médecins assignés à des postes pour une date donnée.
        
        Args:
            date (date): Date à vérifier
        
        Returns:
            dict: Dictionnaire {nom_medecin: [postes_assignés]}
        """
        assigned_doctors = {}
        if not self.planning:
            return assigned_doctors

        # Récupérer le jour du planning
        day_planning = next((day for day in self.planning.days if day.date == date), None)
        if not day_planning:
            return assigned_doctors

        # Regrouper les postes par médecin
        for slot in day_planning.slots:
            if slot.assignee:
                if slot.assignee not in assigned_doctors:
                    assigned_doctors[slot.assignee] = []
                assigned_doctors[slot.assignee].append(slot.abbreviation)

        return assigned_doctors

    def update_selected_cell(self, date_val, period):
        """
        Met à jour la cellule sélectionnée et rafraîchit les informations associées.
        Maintenant compatible avec PlanningTableComponent qui envoie directement date et période.
        """
        # Mettre à jour la date et la période sélectionnées
        self.selected_date = date_val
        self.selected_period = period
        
        # Rafraîchir les sections du bas
        if self.selected_date:
            self.bottom_section.selected_date = self.selected_date
            self.bottom_section.selected_period = self.selected_period
            self.bottom_section.update_all_views()
    
    def get_post_period(self, post):
        """Détermine la période d'un type de poste"""
        if post in ["ML", "MC", "MM", "CM", "HM", "SM", "RM"]:
            return 1  # Matin
        elif post in ["CA", "HA", "SA", "RA", "AL", "AC", "CT"]:
            return 2  # Après-midi
        else:
            return 3  # Soir

    def has_desiderata(self, person, date, period, priority=None):
        """
        Vérifie si une personne a un desiderata pour une date et période spécifiques.
        
        Args:
            person: Médecin ou CAT à vérifier
            date: Date à vérifier
            period: Période à vérifier (1: Matin, 2: Après-midi, 3: Soir)
            priority: Priorité à vérifier ('primary', 'secondary', ou None pour les deux)
            
        Returns:
            bool: True si la personne a un desiderata correspondant, False sinon
        """
        if not person or not hasattr(person, 'desiderata'):
            return False
        
        for desiderata in person.desiderata:
            if (desiderata.start_date <= date <= desiderata.end_date and 
                desiderata.period == period):
                # Si une priorité spécifique est demandée, vérifier
                if priority is not None:
                    if getattr(desiderata, 'priority', 'primary') == priority:
                        return True
                else:
                    # Sinon, tout desiderata correspond
                    return True
        
        return False

    def prepare_cell_parameters(self, current_date, period, filtered_posts, selected_name, table):
        """
        Prépare tous les paramètres nécessaires pour update_cell
        
        Args:
            current_date: Date de la cellule
            period: Période (1=Matin, 2=Après-midi, 3=Soir)
            filtered_posts: Liste des postes filtrés pour cette cellule
            selected_name: Nom du médecin/CAT sélectionné
            table: Table concernée
            
        Returns:
            dict: Paramètres à utiliser pour update_cell
        """
        # Trouver le jour dans le planning
        day_planning = next((day for day in self.planning.days if day.date == current_date), None)
        
        # Valeurs par défaut
        params = {
            'display_text': "",
            'background_color': None,
            'foreground_color': None,
            'font': None,
            'tooltip': None,
            'custom_data': {
                'slots': filtered_posts,
                'date': current_date,
                'period': period
            }
        }
        
        if not day_planning:
            return params
        
        is_weekend_or_holiday = day_planning.is_weekend or day_planning.is_holiday_or_bridge
        
        # Texte à afficher
        text = ", ".join(slot.abbreviation for slot in filtered_posts)
        
        # Optimiser le texte si nécessaire
        if len(text) > 15:
            params['display_text'] = text[:15] + "..."
            params['tooltip'] = text
        else:
            params['display_text'] = text
        
        # Couleur de base
        base_color_key = "weekend" if is_weekend_or_holiday else "normal"
        params['background_color'] = table.current_colors["base"][base_color_key]
        
        # IMPORTANT: Vérification des desiderata même s'il n'y a pas de posts assignés
        # Ne pas utiliser "Non attribué" pour les désidératas
        if selected_name != "Non attribué":
            selected_person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
            
            if selected_person and hasattr(selected_person, 'desiderata'):
                has_primary_desiderata = False
                has_secondary_desiderata = False
                
                for desiderata in selected_person.desiderata:
                    # Vérifier si le désidérata correspond à la date et à la période
                    if (desiderata.start_date <= current_date <= desiderata.end_date and 
                        desiderata.period == period):
                        # Déterminer la priorité (primary par défaut)
                        priority = getattr(desiderata, 'priority', 'primary')
                        
                        # Mettre à jour les flags
                        if priority == 'primary':
                            has_primary_desiderata = True
                        else:
                            has_secondary_desiderata = True
                        
                        # Appliquer la couleur correspondante
                        color_key = "weekend" if is_weekend_or_holiday else "normal"
                        if priority in table.current_colors and color_key in table.current_colors[priority]:
                            params['background_color'] = table.current_colors[priority][color_key]
                        break  # Arrêter après avoir trouvé le premier désidérata correspondant
                
                # Stocker les informations sur les désidératas dans les données personnalisées
                params['custom_data']['has_primary_desiderata'] = has_primary_desiderata
                params['custom_data']['has_secondary_desiderata'] = has_secondary_desiderata
        
        # Vérifier les post-attributions
        has_post_attribution = False
        for slot in filtered_posts:
            if hasattr(slot, 'is_post_attribution') and slot.is_post_attribution:
                has_post_attribution = True
                break
        
        # Appliquer le style pour les post-attributions
        if has_post_attribution and hasattr(self.main_window, 'post_attribution_handler'):
            params['foreground_color'] = self.main_window.post_attribution_handler.get_post_color()
            params['font'] = self.main_window.post_attribution_handler.get_post_font()
        
        return params

   
    def populate_table(self, table, selected_name, active_filters=None):
        """
        Remplit le tableau avec les données du planning.
        Version corrigée basée sur doctor_planning_view qui fonctionne.
        """
        if not self.planning or not self.planning.days:
            return

        # Si aucun filtre n'est spécifié, utiliser tous les types de postes
        if active_filters is None:
            active_filters = [
                "ML", "MC", "MM", "CM", "HM", "RM", "SM", 
                "CA", "HA", "RA", "SA", "AL", "AC", "CT",
                "CS", "HS", "RS", "SS", "NC", "NA", "NM", "NL"
            ]
        
        # Configurer les dates du planning
        start_date = self.planning.start_date
        end_date = self.planning.end_date
        table.setup_planning_dates(start_date, end_date)
        
        # Remplir les jours de base
        table.populate_days()
        
        # Récupérer la personne sélectionnée pour les desiderata
        selected_person = None
        if selected_name != "Non attribué":
            selected_person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
        
        # Parcourir chaque jour du planning
        for day_planning in self.planning.days:
            current_date = day_planning.date
            is_weekend_or_holiday = day_planning.is_weekend or day_planning.is_holiday_or_bridge
            
            # Récupération et tri des slots par période pour la personne sélectionnée
            slots_by_period = [[] for _ in range(3)]  # 3 périodes : matin, après-midi, soir
            
            # Filtrer les slots selon la personne sélectionnée et les filtres actifs
            if selected_name == "Non attribué":
                filtered_slots = [
                    slot for slot in day_planning.slots 
                    if slot.assignee is None and slot.abbreviation in active_filters
                ]
            else:
                filtered_slots = [
                    slot for slot in day_planning.slots 
                    if slot.assignee == selected_name and slot.abbreviation in active_filters
                ]
            
            # Trier les slots par période
            for slot in filtered_slots:
                period_index = self.get_post_period(slot.abbreviation) - 1  # -1 car l'index commence à 0
                if 0 <= period_index < 3:  # Vérifier que l'index est valide (0-2)
                    slots_by_period[period_index].append(slot)
            
            # Mise à jour des cellules pour chaque période
            for i in range(3):
                period = i + 1
                post_list = slots_by_period[i]
                
                # Texte de la cellule
                text = ", ".join(slot.abbreviation for slot in post_list)
                
                # Optimiser le texte si nécessaire
                display_text, tooltip = table.optimize_cell_text(text)
                
                # Déterminer la couleur de fond en fonction des desiderata
                background_color = table.current_colors["base"]["weekend" if is_weekend_or_holiday else "normal"]
                
                # IMPORTANT: Cette partie est critique pour les désidératas
                if selected_person:
                    for desiderata in selected_person.desiderata:
                        if (desiderata.start_date <= current_date <= desiderata.end_date and 
                            desiderata.period == period):
                            priority = getattr(desiderata, 'priority', 'primary')
                            background_color = table.current_colors[priority]["weekend" if is_weekend_or_holiday else "normal"]
                            break  # S'arrêter au premier désidérata trouvé
                
                # Vérifier si c'est une post-attribution
                foreground_color = None
                font = None
                has_post_attribution = any(
                    hasattr(slot, 'is_post_attribution') and slot.is_post_attribution 
                    for slot in post_list
                )
                
                # Appliquer le style pour les post-attributions
                if has_post_attribution and hasattr(self.main_window, 'post_attribution_handler'):
                    foreground_color = self.main_window.post_attribution_handler.get_post_color()
                    font = self.main_window.post_attribution_handler.get_post_font()
                
                # Mettre à jour la cellule
                table.update_cell(
                    current_date, period, display_text,
                    background_color=background_color,
                    foreground_color=foreground_color,
                    font=font,
                    tooltip=tooltip,
                    custom_data={"slots": post_list}  # Stocker les slots pour usage ultérieur
                )
    def on_cell_double_clicked(self, date_val, period):
        """
        Gère le double-clic sur une cellule pour ouvrir le dialogue d'échange.
        Version adaptée pour PlanningTableComponent.
        
        Args:
            date_val: Date correspondant à la cellule
            period: Période (1=matin, 2=après-midi, 3=soir, None=jour)
        """
        if not date_val or not period or period not in [1, 2, 3]:
            return
        
        # Déterminer quelle table a été double-cliquée
        sender = self.sender()
        if not isinstance(sender, PlanningTableComponent):
            return
        
        # Déterminer l'assigné actuel et comparé
        if sender == self.table1:
            current_assignee = self.selector1.currentText()
            compared_assignee = self.selector2.currentText()
        else:
            current_assignee = self.selector2.currentText()
            compared_assignee = self.selector1.currentText()
        
        # Vérifier si un échange est possible
        if current_assignee == compared_assignee:
            QMessageBox.warning(self, "Échange impossible", "Impossible d'échanger avec le même assigné.")
            return
        
        # Obtenir le jour et les slots
        day = next((d for d in self.planning.days if d.date == date_val), None)
        if not day:
            return
        
        # Filtrer les slots par période et assigné
        if current_assignee == "Non attribué":
            available_slots = [
                slot for slot in day.slots 
                if slot.assignee is None and self.get_post_period(slot.abbreviation) == period
            ]
        else:
            available_slots = [
                slot for slot in day.slots 
                if slot.assignee == current_assignee and self.get_post_period(slot.abbreviation) == period
            ]
        
        # Obtenir les abréviations de postes disponibles
        available_posts = [slot.abbreviation for slot in available_slots]
        
        if not available_posts:
            QMessageBox.warning(self, "Échange impossible", "Aucun poste disponible pour l'échange.")
            return
        
        # Créer et afficher le dialogue d'échange
        period_names = ["Matin", "Après-midi", "Soir"]
        period_name = period_names[period - 1]
        
        dialog = PostAssignmentDialog(day, current_assignee, self.doctors, self.cats, compared_assignee, available_posts, period_name)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_assignee = dialog.get_selected_assignee()
            selected_post = dialog.get_selected_post()
            
            # Mettre à jour l'assignation
            for slot in day.slots:
                if (slot.abbreviation == selected_post and 
                    ((current_assignee == "Non attribué" and slot.assignee is None) or 
                     (current_assignee != "Non attribué" and slot.assignee == current_assignee))):
                    slot.assignee = None if new_assignee == "Non attribué" else new_assignee
                    
                    # Notification du changement
                    self.on_assignment_changed(current_assignee, new_assignee, selected_post)
                    break

            
class ComparisonBottomSection(QWidget):
    """
    Section du bas de PlanningComparisonView qui affiche des informations supplémentaires
    comme l'historique des échanges, le bilan des postes, les médecins disponibles, etc.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.selected_date = None
        self.selected_period = None
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {color_system.colors['container']['background'].name()};
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                color: {color_system.colors['text']['primary'].name()};
            }}
            QComboBox:hover {{
                border-color: {color_system.colors['primary'].name()};
            }}
            QTextEdit {{
                background-color: {color_system.colors['container']['background'].name()};
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                color: {color_system.colors['text']['primary'].name()};
            }}
            QTextEdit:focus {{
                border-color: {color_system.colors['primary'].name()};
            }}
        """)

        # Section gauche
        left_section = QVBoxLayout()
        left_section.setSpacing(2)
        
        self.left_selector = QComboBox()
        self.left_selector.addItems([
            "Historique des échanges",
            "Bilan des postes",
            "Médecins disponibles",
            "Médecins en désiderata secondaires",
            "Médecins en poste"
        ])
        left_section.addWidget(self.left_selector)
        
        self.left_content = QTextEdit()
        self.left_content.setMinimumHeight(100)
        self.left_content.setMaximumHeight(150)
        self.left_content.setReadOnly(True)
        left_section.addWidget(self.left_content)
        
        layout.addLayout(left_section)

        # Section droite
        right_section = QVBoxLayout()
        right_section.setSpacing(2)
        
        self.right_selector = QComboBox()
        self.right_selector.addItems([
            "Bilan des postes",
            "Historique des échanges",
            "Médecins disponibles",
            "Médecins en désiderata secondaires",
            "Médecins en poste"
        ])
        right_section.addWidget(self.right_selector)
        
        self.right_content = QTextEdit()
        self.right_content.setMinimumHeight(100)
        self.right_content.setMaximumHeight(150)
        self.right_content.setReadOnly(True)
        right_section.addWidget(self.right_content)
        
        layout.addLayout(right_section)

        # Connecter les sélecteurs aux méthodes de mise à jour
        self.left_selector.currentIndexChanged.connect(
            lambda: self.update_content(self.left_selector, self.left_content))
        self.right_selector.currentIndexChanged.connect(
            lambda: self.update_content(self.right_selector, self.right_content))

    def show_exchange_history(self, widget):
        """Affiche l'historique des échanges dans le widget spécifié."""
        content = ""
        for exchange in self.parent.exchange_history:
            content += f"{exchange}\n"
        widget.setText(content)

    def show_post_balance(self, widget):
        """Affiche le bilan des postes dans le widget spécifié."""
        content = ""
        for assignee, balance in self.parent.post_balance.items():
            non_zero_posts = {post: count for post, count in balance["posts"].items() 
                            if count != 0}
            non_zero_groups = {group: count for group, count in balance["groups"].items() 
                             if count != 0}
            
            if non_zero_posts or non_zero_groups:
                post_text = ", ".join([f"{count:+d}{post}" 
                                     for post, count in non_zero_posts.items()])
                group_text = ", ".join([f"{count:+d}{group}" 
                                      for group, count in non_zero_groups.items()])
                
                content += f"{assignee}:\n"
                content += f"  Postes: {post_text}\n"
                content += f"  Groupes: {group_text}\n\n"
        widget.setText(content)

    def update_all_views(self):
        """Met à jour toutes les vues avec les nouvelles informations."""
        if not self.selected_date:
            return
            
        self.update_content(self.left_selector, self.left_content)
        self.update_content(self.right_selector, self.right_content)

    def show_available_doctors(self, widget):
        """Affiche les médecins disponibles pour la date et période sélectionnée."""
        if not self.selected_date:
            widget.setText("Sélectionnez une cellule pour voir les médecins disponibles")
            return

        doctors = self.parent._get_available_doctors(
            self.selected_date,
            self.selected_period
        )
        
        content = "Médecins disponibles:\n\n"
        for doctor_name in sorted(doctors):
            # Ajouter un marqueur pour les CAT
            is_cat = any(cat.name == doctor_name for cat in self.parent.cats)
            prefix = "CAT: " if is_cat else "- "
            content += f"{prefix}{doctor_name}\n"
            
        widget.setText(content)

    def show_secondary_desiderata(self, widget):
        """Affiche les médecins avec desiderata secondaires."""
        if not self.selected_date:
            widget.setText("Sélectionnez une cellule pour voir les médecins avec desiderata secondaires")
            return

        doctors = self.parent._get_secondary_desiderata_doctors(
            self.selected_date,
            self.selected_period
        )
        content = "Médecins avec désiderata secondaires:\n\n"
        for doctor_name in sorted(doctors):
            # Ajouter un marqueur pour les CAT
            is_cat = any(cat.name == doctor_name for cat in self.parent.cats)
            prefix = "CAT: " if is_cat else "- "
            content += f"{prefix}{doctor_name}\n"
        widget.setText(content)

    def show_assigned_doctors(self, widget):
        """Affiche les médecins en poste."""
        if not self.selected_date:
            widget.setText("Sélectionnez une cellule pour voir les médecins en poste")
            return

        doctors = self.parent._get_assigned_doctors(self.selected_date)
        content = "Médecins en poste:\n\n"
        for doctor_name, posts in sorted(doctors.items()):
            # Ajouter un marqueur pour les CAT
            is_cat = any(cat.name == doctor_name for cat in self.parent.cats)
            prefix = "* " if is_cat else "- "
            content += f"{prefix}{doctor_name}: {', '.join(posts)}\n"
        widget.setText(content)

    def update_content(self, selector, content_widget):
        """Met à jour le contenu en fonction de la sélection."""
        view_type = selector.currentText()
        
        if view_type == "Historique des échanges":
            self.show_exchange_history(content_widget)
        elif view_type == "Bilan des postes":
            self.show_post_balance(content_widget)
        elif view_type == "Médecins disponibles":
            self.show_available_doctors(content_widget)
        elif view_type == "Médecins en désiderata secondaires":
            self.show_secondary_desiderata(content_widget)
        elif view_type == "Médecins en poste":
            self.show_assigned_doctors(content_widget)


class PostAssignmentDialog(QDialog):
    """
    Dialogue d'échange de poste qui permet de choisir un nouvel assigné
    et un poste à échanger.
    """
    def __init__(self, day, current_assignee, doctors, cats, compared_assignee, available_posts, period_name):
        super().__init__()
        self.day = day
        self.current_assignee = current_assignee
        self.doctors = doctors
        self.cats = cats
        self.compared_assignee = compared_assignee
        self.available_posts = available_posts
        self.period_name = period_name
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Utilisez les couleurs du système pour une meilleure cohérence
        bg_color = color_system.colors['container']['background'].name()
        border_color = color_system.colors['container']['border'].name()
        text_color = color_system.colors['text']['primary'].name()
        primary_color = color_system.colors['primary'].name()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
                font-size: {StyleConstants.FONT['size']['md']};
            }}
            QComboBox {{
                background-color: white;
                border: 1px solid {border_color};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                min-width: 200px;
                color: {text_color};
            }}
            QComboBox:hover {{
                border-color: {primary_color};
            }}
            QPushButton {{
                background-color: {primary_color};
                color: white;
                border: none;
                padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                font-weight: bold;
                min-width: 100px;
                font-size: {StyleConstants.FONT['size']['md']};
            }}
            QPushButton:hover {{
                background-color: {color_system.colors['primary'].darker(125).name()};
            }}
        """)
        
        # Affichage du titre avec informations sur l'échange
        title_label = QLabel(f"Échange de poste - {self.day.date.strftime('%d/%m/%Y')} - {self.period_name}")
        title_font = QFont(StyleConstants.FONT['family']['primary'])
        title_font.setPointSize(int(StyleConstants.FONT['size']['lg'].replace('px', '')))
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Informations sur l'assigné actuel
        current_info = f"Assigné actuel: {self.current_assignee if self.current_assignee != 'Non attribué' else 'Non attribué'}"
        layout.addWidget(QLabel(current_info))
        
        # Sélecteur pour le nouvel assigné
        layout.addWidget(QLabel(f"Nouvel assigné:"))
        self.assignee_selector = QComboBox()
        options = ["Non attribué"] + [d.name for d in self.doctors] + [c.name for c in self.cats]
        options = [option for option in options if option != self.current_assignee]  # Exclure l'assigné actuel
        self.assignee_selector.addItems(options)
        
        # Définir l'assigné par défaut comme celui comparé, sauf s'il est identique à l'actuel
        if self.compared_assignee != self.current_assignee and self.compared_assignee in options:
            self.assignee_selector.setCurrentText(self.compared_assignee)
        layout.addWidget(self.assignee_selector)

        # Sélecteur pour les postes disponibles (seulement les postes présents dans la case)
        layout.addWidget(QLabel("Poste à échanger:"))
        self.post_selector = QComboBox()
        self.post_selector.addItems(self.available_posts)
        layout.addWidget(self.post_selector)

        # Boutons d'action
        buttons = QHBoxLayout()
        save_button = QPushButton("Enregistrer")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Annuler")
        cancel_button.clicked.connect(self.reject)
        
        # Ajouter de l'espace pour que les boutons ne soient pas collés
        buttons.addStretch()
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        buttons.addStretch()
        
        layout.addSpacing(10)  # Espace avant les boutons
        layout.addLayout(buttons)
        
    def get_selected_assignee(self):
        """Retourne le nouvel assigné sélectionné."""
        return self.assignee_selector.currentText()

    def get_selected_post(self):
        """Retourne le poste sélectionné pour l'échange."""
        return self.post_selector.currentText()
