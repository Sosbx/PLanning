# © 2024 HILAL Arkane. Tous droits réservés.
# gui/planning_comparison_view.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QHeaderView, QMessageBox,
                             QTableWidget, QTableWidgetItem, QDialog, QLabel, QScrollArea, QTextEdit)

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QBrush, QFont, QTextCharFormat
from datetime import date, timedelta, datetime, time
from core.utils import get_post_period
from core.Constantes.models import TimeSlot, Doctor, CAT
from dateutil.relativedelta import relativedelta
from core.Constantes.constraints import PlanningConstraints
from workalendar.europe import France



from .styles import color_system, StyleConstants

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

        # Style global du widget
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color_system.colors['container']['background'].name()};
                font-family: {StyleConstants.FONT['family']['primary']};
                font-size: {StyleConstants.FONT['size']['md']};
                color: {color_system.colors['text']['primary'].name()};
            }}
            QComboBox {{
                background-color: {color_system.colors['container']['background'].name()};
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                min-width: 200px;
            }}
            QComboBox:hover {{
                border-color: {color_system.colors['primary'].name()};
            }}
        """)

        # Zone des sélecteurs
        selectors_layout = QHBoxLayout()
        selectors_layout.setSpacing(StyleConstants.SPACING['md'])

        # Création des sélecteurs
        self.selector1 = QComboBox()
        self.selector2 = QComboBox()
        
        # Style des sélecteurs
        selector_style = f"""
            QComboBox {{
                background-color: {color_system.colors['container']['background'].name()};
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                padding: {StyleConstants.SPACING['xs']}px;
                min-width: 200px;
                min-height: {StyleConstants.SPACING['xl']}px;
            }}
            QComboBox:hover {{
                border-color: {color_system.colors['primary'].name()};
            }}
        """
        self.selector1.setStyleSheet(selector_style)
        self.selector2.setStyleSheet(selector_style)
        
        selectors_layout.addWidget(self.selector1)
        selectors_layout.addWidget(self.selector2)
        layout.addLayout(selectors_layout)

        # Zone des tableaux
        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(StyleConstants.SPACING['md'])

        # Création des zones de défilement
        scroll_area1 = QScrollArea()
        scroll_area2 = QScrollArea()
        scroll_area1.setWidgetResizable(True)
        scroll_area2.setWidgetResizable(True)

        # Création et configuration des tableaux
        self.table1 = FullPlanningTable(self)
        self.table2 = FullPlanningTable(self)
        
        scroll_area1.setWidget(self.table1)
        scroll_area2.setWidget(self.table2)

        tables_layout.addWidget(scroll_area1)
        tables_layout.addWidget(scroll_area2)
        layout.addLayout(tables_layout, 1)  # Le 1 donne plus d'importance à la zone des tableaux

        # Section du bas
        self.bottom_section = ComparisonBottomSection(self)
        layout.addWidget(self.bottom_section)

        # Initialisation des attributs de suivi
        self.selected_date = None
        self.selected_period = None

        # Connexion des signaux
        self.selector1.currentIndexChanged.connect(self.on_selector_changed)
        self.selector2.currentIndexChanged.connect(self.on_selector_changed)

        # Mise à jour initiale des sélecteurs
        self.update_selectors()

        # Synchronisation des barres de défilement
        self.synchronize_scrollbars()


    def update_table_style(self, table):
        """Applique un style cohérent à une table."""
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setMinimumHeight(StyleConstants.SPACING['xl'])
        
        # Style des en-têtes
        header_font = QFont(StyleConstants.FONT['family']['primary'])
        header_font.setPointSize(int(StyleConstants.FONT['size']['md'].replace('px', '')))
        header_font.setWeight(StyleConstants.FONT['weight']['medium'])
        table.horizontalHeader().setFont(header_font)
        
        # Hauteur des lignes
        table.verticalHeader().setDefaultSectionSize(StyleConstants.SPACING['xl'])
        
        # Ajustement des colonnes
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)

    def synchronize_scrollbars(self):
        """
        Synchronise les barres de défilement des deux tables pour un défilement horizontal et vertical simultané.
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
        sender = self.sender()
        if sender == self.selector1:
            self.current_selection1 = sender.currentText()
            self.table1.populate_table(self.current_selection1)
        elif sender == self.selector2:
            self.current_selection2 = sender.currentText()
            self.table2.populate_table(self.current_selection2)

    def update_comparison(self, preserve_selection=False):
        if preserve_selection and hasattr(self, 'current_selection1') and hasattr(self, 'current_selection2'):
            selected1 = self.current_selection1
            selected2 = self.current_selection2
        else:
            selected1 = self.selector1.currentText()
            selected2 = self.selector2.currentText()
        
        self.table1.populate_table(selected1)
        self.table2.populate_table(selected2)
        
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
        self.main_window.planning_tab.update_table()
        self.main_window.update_stats_view()
        self.main_window.doctor_planning_view.update_view(self.planning, self.doctors, self.cats)
        
        # Mettre à jour les sélecteurs en permettant de nouvelles sélections
        self.update_selectors(preserve_selection=True, allow_new_selection=True)
        
        # Mettre à jour les tables
        self.table1.populate_table(self.current_selection1)
        self.table2.populate_table(self.current_selection2)
        
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
        
    

    def update_exchange_history(self, old_assignee, new_assignee, post_type):
        exchange = f"{old_assignee} donne {post_type} à {new_assignee}"
        self.exchange_history.append(exchange)

        cursor = self.exchange_history_widget.textCursor()
        format = QTextCharFormat()
        format.setForeground(QBrush(QColor(0, 0, 0)))  # Noir pour tous les échanges
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(exchange + "\n", format)

       
 

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
        
        # Reset bottom section text widgets
        self.bottom_section.left_content.clear()
        self.bottom_section.right_content.clear()
        
        # Reset bottom section selectors
        self.bottom_section.left_selector.setCurrentIndex(0)
        self.bottom_section.right_selector.setCurrentIndex(0)
        
    def _get_available_doctors(self, date, period):
        """
        Détermine les médecins disponibles pour une date et une période données.
        
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

        # Déterminer le type de jour
        from core.Constantes.day_type import DayType
        day_type = DayType.get_day_type(date, self._calendar)

        # Déterminer les périodes à vérifier
        periods_to_check = [1, 2, 3] if period is None else [period]

        # Pour chaque personne (médecin ou CAT)
        for person in self.doctors + self.cats:
            can_take_any_post = False
            
            # Pour chaque période à vérifier
            for check_period in periods_to_check:
                # Vérifier si la personne a déjà un poste dans cette période
                has_slot_in_period = any(
                    slot.assignee == person.name and get_post_period(slot) == check_period - 1
                    for slot in day_planning.slots
                )
                
                if has_slot_in_period:
                    continue

                # Vérifier les desiderata primaires
                has_primary_desiderata = any(
                    desiderata.start_date <= date <= desiderata.end_date and
                    desiderata.period == check_period and
                    getattr(desiderata, 'priority', 'primary') == 'primary'
                    for desiderata in person.desiderata
                )
                
                if has_primary_desiderata:
                    continue

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
                            can_take_any_post = True
                            break
                    except Exception as e:
                        continue

                if can_take_any_post:
                    break


            if can_take_any_post:
                # Vérifier si la personne a des desiderata secondaires pour cette période
                has_secondary_desiderata = False
                for check_period in periods_to_check:
                    if any(
                        desiderata.start_date <= date <= desiderata.end_date and
                        desiderata.period == check_period and
                        getattr(desiderata, 'priority', 'primary') == 'secondary'
                        for desiderata in person.desiderata
                    ):
                        has_secondary_desiderata = True
                        break
                
                # N'ajouter que si la personne n'a pas de desiderata secondaires
                if not has_secondary_desiderata:
                    available_personnel.add(person.name)

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

    def _get_slot_period(self, slot):
        """
        Détermine la période d'un slot.
        
        Args:
            slot: Le slot à vérifier
        
        Returns:
            int: 1 pour matin, 2 pour après-midi, 3 pour soir
        """
        start_hour = slot.start_time.hour
        
        if slot.abbreviation == "CT":
            # Pour CT, calculer la période dominante
            total_hours = (slot.end_time.hour - start_hour + 24) % 24
            morning_hours = sum(1 for h in range(start_hour, start_hour + total_hours) if 7 <= h % 24 < 13)
            afternoon_hours = sum(1 for h in range(start_hour, start_hour + total_hours) if 13 <= h % 24 < 18)
            
            if morning_hours > afternoon_hours:
                return 1
            else:
                return 2
        
        if 7 <= start_hour < 13:
            return 1  # Matin
        elif 13 <= start_hour < 18:
            return 2  # Après-midi
        else:
            return 3  # Soir

    def update_selected_cell(self, row, col):
        """
        Met à jour la cellule sélectionnée et rafraîchit les informations associées.
        
        Args:
            row (int): Index de la ligne
            col (int): Index de la colonne
        """
        # Mettre à jour la date et la période sélectionnées
        self.selected_date = self._get_date_from_row_col(row, col)
        self.selected_period = self._get_period_from_column(col)
        
        # Rafraîchir les sections du bas
        self.bottom_section.update_content(
            self.bottom_section.left_selector, 
            self.bottom_section.left_content
        )
        self.bottom_section.update_content(
            self.bottom_section.right_selector, 
            self.bottom_section.right_content
        )
class ComparisonBottomSection(QWidget):
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

        self.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #c0d0e0;
                border-radius: 4px;
                padding: 6px;
                color: #2d3748;
            }
            QComboBox:hover {
                border-color: #2c5282;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #c0d0e0;
                border-radius: 4px;
                padding: 6px;
                color: #2d3748;
            }
            QTextEdit:focus {
                border-color: #2c5282;
            }
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
        content = ""
        for exchange in self.parent.exchange_history:
            content += f"{exchange}\n"
        widget.setText(content)

    def show_post_balance(self, widget):
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
        """Affiche les médecins disponibles."""
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


class FullPlanningTable(QTableWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.colors = {
            "primary": {
                "weekend": color_system.get_color('desiderata', 'primary', 'weekend'),
                "normal": color_system.get_color('desiderata', 'primary', 'normal')
            },
            "secondary": {
                "weekend": color_system.get_color('desiderata', 'secondary', 'weekend'),
                "normal": color_system.get_color('desiderata', 'secondary', 'normal')
            },
            "base": {
                "weekend": color_system.get_color('weekend'),
                "normal": color_system.get_color('weekday')
            }
        }
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        
        self.itemClicked.connect(self.on_item_clicked)
        self.cellDoubleClicked.connect(self.on_item_double_clicked)

    def get_cell_color(self, date, is_weekend, person, slot):
        """Détermine la couleur de la cellule en fonction des desiderata"""
        if not person:
            return self.colors["base"]["weekend" if is_weekend else "normal"]

        for desiderata in person.desiderata:
            if (desiderata.start_date <= date <= desiderata.end_date and
                desiderata.overlaps_with_slot(slot)):
                priority = getattr(desiderata, 'priority', 'primary')
                return self.colors[priority]["weekend" if is_weekend else "normal"]

        return self.colors["base"]["weekend" if is_weekend else "normal"]


   
    def populate_table(self, selected):
        """Remplit le tableau avec les données du planning"""
        if not self.parent.planning or not self.parent.planning.days:
            return

        self.clear()

        start_date = self.parent.planning.start_date
        end_date = self.parent.planning.end_date
        
        # Calcul du nombre de mois
        total_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1

        # Configuration du tableau
        self.setRowCount(31)
        self.setColumnCount(total_months * 4 + 1)

        # En-têtes avec police en gras
        headers = ["Jour"]
        current_date = start_date.replace(day=1)
        for _ in range(total_months):
            month_name = current_date.strftime("%b")
            headers.extend([f"{month_name}\nJ", f"{month_name}\nM", f"{month_name}\nAM", f"{month_name}\nS"])
            current_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        
        # Appliquer le style aux en-têtes
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(10)
        
        for col, text in enumerate(headers):
            header_item = QTableWidgetItem(text)
            header_item.setFont(header_font)
            header_item.setForeground(QBrush(QColor(40, 40, 40)))
            self.setHorizontalHeaderItem(col, header_item)

        # Définition des couleurs par défaut
        default_colors = {
            "primary": {
                "weekend": QColor(255, 150, 150),     # Rouge plus foncé pour weekend
                "normal": QColor(255, 200, 200)       # Rouge clair pour jours normaux
            },
            "secondary": {
                "weekend": QColor(150, 200, 255),     # Bleu plus foncé pour weekend
                "normal": QColor(180, 220, 255)       # Bleu clair pour jours normaux
            },
            "base": {
                "weekend": QColor(220, 220, 220),     # Gris pour weekend
                "normal": QColor(255, 255, 255)       # Blanc pour jours normaux
            }
        }

        # Remplissage des données
        current_date = start_date
        while current_date <= end_date:
            day_row = current_date.day - 1
            month_col = (current_date.year - start_date.year) * 12 + current_date.month - start_date.month
            col_offset = month_col * 4 + 1

            # Police en gras pour toutes les cellules
            bold_font = QFont()
            bold_font.setBold(True)
            bold_font.setPointSize(10)
            
            # Configuration du jour et du jour de la semaine
            day_item = QTableWidgetItem(str(current_date.day))
            day_item.setFont(bold_font)
            day_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            day_item.setForeground(QBrush(QColor(40, 40, 40)))
            self.setItem(day_row, 0, day_item)
            
            weekday_item = QTableWidgetItem(self.get_weekday_abbr(current_date.weekday()))
            weekday_item.setFont(bold_font)
            weekday_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            weekday_item.setForeground(QBrush(QColor(40, 40, 40)))
            self.setItem(day_row, col_offset, weekday_item)

            # Traitement du planning du jour
            day_planning = next((day for day in self.parent.planning.days if day.date == current_date), None)
            if day_planning:
                is_weekend_or_holiday = day_planning.is_weekend or day_planning.is_holiday_or_bridge

                # Récupération des posts
                posts = [slot for slot in day_planning.slots if (selected == "Non attribué" and slot.assignee is None) or slot.assignee == selected]
                
                # Tri par période
                morning_posts = [p for p in posts if get_post_period(p) == 0]
                afternoon_posts = [p for p in posts if get_post_period(p) == 1]
                evening_posts = [p for p in posts if get_post_period(p) == 2]

                # Création des cellules pour chaque période
                for i, post_list in enumerate([morning_posts, afternoon_posts, evening_posts]):
                    posts_text = ", ".join([p.abbreviation for p in post_list])
                    if selected == "Non attribué":
                        unassigned_posts = [slot.abbreviation for slot in day_planning.slots 
                                        if slot.assignee is None and self.get_post_period(slot.abbreviation) == i]
                        posts_text = ", ".join(unassigned_posts)
                    
                    item = QTableWidgetItem(posts_text)
                    item.setFont(bold_font)
                    item.setData(Qt.ItemDataRole.UserRole, day_planning)
                    item.setForeground(QBrush(QColor(40, 40, 40)))
                    
                    # Couleur de base
                    base_color = default_colors["base"]["weekend" if is_weekend_or_holiday else "normal"]
                    item.setBackground(QBrush(base_color))
                    
                    # Vérification des desiderata
                    selected_person = next((p for p in self.parent.doctors + self.parent.cats if p.name == selected), None)
                    if selected_person:
                        for desiderata in selected_person.desiderata:
                            if desiderata.start_date <= current_date <= desiderata.end_date:
                                if desiderata.period == i + 1:
                                    priority = getattr(desiderata, 'priority', 'primary')
                                    color = default_colors[priority]["weekend" if is_weekend_or_holiday else "normal"]
                                    item.setBackground(QBrush(color))
                    
                    self.setItem(day_row, col_offset + i + 1, item)

            current_date += timedelta(days=1)

        # Ajustement de la taille des cellules
        for row in range(self.rowCount()):
            self.setRowHeight(row, 20)

        for col in range(self.columnCount()):
            if col == 0:
                self.setColumnWidth(col, 30)
            elif (col - 1) % 4 == 0:
                self.setColumnWidth(col, 30)
            else:
                self.setColumnWidth(col, 40)

        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                
    def toggle_cell(self, item):
        current_color = item.background().color()
        is_weekend_or_holiday = current_color == WEEKEND_COLOR
        
        if current_color == WEEKEND_COLOR:
            new_color = WEEKEND_DESIDERATA_COLOR
        elif current_color == WEEKEND_DESIDERATA_COLOR:
            new_color = WEEKEND_COLOR
        elif current_color == WEEKDAY_COLOR:
            new_color = DESIDERATA_COLOR
        else:
            new_color = WEEKDAY_COLOR
        
        item.setBackground(QBrush(new_color))

    def get_weekday_abbr(self, weekday):
        return ["L", "M", "M", "J", "V", "S", "D"][weekday]


    def get_post_period(self, post):
        if post in ["ML","MC","MM", "CM", "HM", "SM", "RM"]:
            return 0  # Matin
        elif post in ["CA", "HA", "SA", "RA", "AL", "AC"]:
            return 1  # Après-midi
        else:
            return 2  # Soir


    def on_item_clicked(self, item):
        """Gère le clic sur une cellule de la table."""
        if not item or item.column() <= 0:
            return

        row = item.row()
        column = item.column()

        # Mettre à jour la cellule sélectionnée dans l'autre table
        if self == self.parent.table1:
            other_table = self.parent.table2
        else:
            other_table = self.parent.table1
        
        other_table.setCurrentCell(row, column)

        # Mettre à jour les informations de la cellule sélectionnée
        selected_date = self.get_date_from_cell(row, column)
        selected_period = self.get_period_from_column(column)
        
        # Mettre à jour les attributs du parent
        self.parent.selected_date = selected_date
        self.parent.selected_period = selected_period
        
        # Mettre à jour les sections du bas
        if selected_date:
            self.parent.bottom_section.selected_date = selected_date
            self.parent.bottom_section.selected_period = selected_period
            self.parent.bottom_section.update_all_views()
    
    def get_date_from_cell(self, row, column):
        """Obtient la date correspondant à une cellule."""
        try:
            if column <= 0:
                return None
                
            # Le numéro du jour est dans la première colonne
            day = int(self.item(row, 0).text())
            
            # Calculer le mois et l'année
            month_col = (column - 1) // 4
            current_date = self.parent.planning.start_date
            month_date = current_date.replace(day=1) + relativedelta(months=month_col)
            
            # Créer la date complète
            try:
                return month_date.replace(day=day)
            except ValueError:  # Pour gérer les fins de mois
                return None
                
        except (ValueError, AttributeError, TypeError):
            return None

    def get_period_from_column(self, column):
        """Obtient la période correspondant à une colonne."""
        if column <= 0:
            return None
            
        column_in_group = (column - 1) % 4
        
        # 0 -> J (jour complet)
        # 1 -> M (matin)
        # 2 -> AM (après-midi)
        # 3 -> S (soir)
        if column_in_group == 0:
            return None
        else:
            return column_in_group

    def on_item_double_clicked(self, row, column):
        if column > 1 and (column - 1) % 4 != 0:
            item = self.item(row, column)
            if item and item.data(Qt.ItemDataRole.UserRole):
                day = item.data(Qt.ItemDataRole.UserRole)
                
                if self == self.parent.table1:
                    current_assignee = self.parent.selector1.currentText()
                    compared_assignee = self.parent.selector2.currentText()
                else:
                    current_assignee = self.parent.selector2.currentText()
                    compared_assignee = self.parent.selector1.currentText()

                # Vérifier si un échange est possible
                if current_assignee == compared_assignee:
                    QMessageBox.warning(self, "Échange impossible", "Impossible d'échanger avec le même assigné.")
                    return

                period = ((column - 1) % 4) - 1
                period_names = ["Matin", "Après-midi", "Soir"]
                period_name = period_names[period]

                if current_assignee == "Non attribué":
                    available_posts = [slot.abbreviation for slot in day.slots 
                                    if slot.assignee is None and self.get_post_period(slot.abbreviation) == period]
                else:
                    available_posts = [slot.abbreviation for slot in day.slots 
                                    if slot.assignee == current_assignee and self.get_post_period(slot.abbreviation) == period]

                if not available_posts:
                    QMessageBox.warning(self, "Échange impossible", "Aucun poste disponible pour l'échange.")
                    return

                dialog = PostAssignmentDialog(day, current_assignee, self.parent.doctors, self.parent.cats, compared_assignee, available_posts, period_name)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    new_assignee = dialog.get_selected_assignee()
                    selected_post = dialog.get_selected_post()
                    self.update_assignment(day, current_assignee, new_assignee, selected_post)

    def update_assignment(self, day, current_assignee, new_assignee, selected_post):
        """
        Met à jour l'assignation d'un seul poste, même s'il y en a plusieurs du même type.
        
        Args:
            day: Jour concerné
            current_assignee: Assigné actuel
            new_assignee: Nouvel assigné
            selected_post: Type de poste à échanger
        """
        if current_assignee == new_assignee:
            return  # Pas de changement nécessaire

        # Trouver le premier slot correspondant
        target_slot = None
        for slot in day.slots:
            if slot.abbreviation == selected_post:
                if (current_assignee == "Non attribué" and slot.assignee is None) or \
                (current_assignee != "Non attribué" and slot.assignee == current_assignee):
                    target_slot = slot
                    break  # On s'arrête au premier slot trouvé
        
        # Si un slot a été trouvé, le modifier
        if target_slot:
            target_slot.assignee = None if new_assignee == "Non attribué" else new_assignee
            self.parent.on_assignment_changed(current_assignee, new_assignee, selected_post)

    def get_selected_slot(self):
        return self.slot_list.currentData()

class PostAssignmentDialog(QDialog):
    def __init__(self, day, current_assignee, doctors, cats, compared_assignee, available_posts, period_name):
        super().__init__()
        self.day = day
        self.current_assignee = current_assignee
        self.doctors = doctors
        self.cats = cats
        self.compared_assignee = compared_assignee
        self.available_posts = available_posts
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QLabel {
                color: #2d3748;
                font-size: 10pt;
            }
            QComboBox {
                background-color: white;
                border: 1px solid #c0d0e0;
                border-radius: 4px;
                padding: 6px;
                min-width: 200px;
                color: #2d3748;
            }
            QComboBox:hover {
                border-color: #2c5282;
            }
            QPushButton {
                background-color: #2c5282;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #1a365d;
            }
        """)

        # Affichage du nom de l'assigné par défaut (comparé)
        layout.addWidget(QLabel(f"Nouvel assigné pour le {self.day.date}:"))
        
        # Sélecteur pour l'assigné (docteurs et CAT)
        self.assignee_selector = QComboBox()
        options = ["Non attribué"] + [d.name for d in self.doctors] + [c.name for c in self.cats]
        options = [option for option in options if option != self.current_assignee]  # Exclure l'assigné actuel
        self.assignee_selector.addItems(options)
        
        # Définir l'assigné par défaut comme celui comparé, sauf s'il est identique à l'actuel
        if self.compared_assignee != self.current_assignee:
            self.assignee_selector.setCurrentText(self.compared_assignee)

        # Sélecteur pour les postes disponibles (seulement les postes présents dans la case)
        layout.addWidget(QLabel("Choisir les postes à échanger :"))
        self.post_selector = QComboBox()
        self.post_selector.addItems(self.available_posts)
        layout.addWidget(self.post_selector)

        # Boutons d'action
        buttons = QHBoxLayout()
        save_button = QPushButton("Enregistrer")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Annuler")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        
        
        layout.addWidget(self.assignee_selector)

    def get_selected_assignee(self):
        return self.assignee_selector.currentText()

    def get_selected_post(self):
        return self.post_selector.currentText()
