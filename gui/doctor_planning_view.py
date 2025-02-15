# © 2024 HILAL Arkane. Tous droits réservés.
# .gui/doctor_planning_view
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QScrollArea, 
                             QLabel, QScrollArea, QSplitter, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QTimer,QSize
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from datetime import date, timedelta, datetime, time
from typing import Union, Optional, Dict, List, Tuple
from collections import defaultdict
from core.utils import get_post_period

from core.Constantes.models import Doctor, CAT, TimeSlot

import logging
from dateutil.relativedelta import relativedelta#+
logger = logging.getLogger(__name__)

from .styles import color_system

# Utilisation du système de couleurs centralisé
WEEKEND_COLOR = color_system.colors["weekend"]
WEEKDAY_COLOR = color_system.colors["weekday"]
DESIDERATA_COLOR = color_system.colors["desiderata"]["primary"]["normal"]
WEEKEND_DESIDERATA_COLOR = color_system.colors["desiderata"]["primary"]["weekend"]
WEEKDAY_TEXT_COLOR = color_system.colors["text"]
AVAILABLE_COLOR = color_system.colors["available"]
SECONDARY_DESIDERATA_COLOR = color_system.colors["desiderata"]["secondary"]["normal"]


class CollapsibleWidget(QWidget):
    """Widget rétractable avec bouton de contrôle."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.stored_width = 300  # Largeur par défaut

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # En-tête avec titre et bouton
        header = QFrame()
        header.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(5, 5, 5, 5)

        self.title_label = QLabel(title)
        self.toggle_button = QPushButton("◀")  # Utiliser des caractères Unicode pour les flèches
        self.toggle_button.setFixedWidth(20)
        self.toggle_button.clicked.connect(self.toggle_collapsed)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.toggle_button)

        layout.addWidget(header)

        # Conteneur pour le contenu
        self.content = QFrame()
        self.content_layout = QVBoxLayout(self.content)
        layout.addWidget(self.content)

    def toggle_collapsed(self):
        """Bascule entre l'état rétracté et déployé."""
        self.is_collapsed = not self.is_collapsed
        
        if self.is_collapsed:
            self.stored_width = self.width()
            self.toggle_button.setText("▶")
            self.setMaximumWidth(30)
            self.content.hide()
        else:
            self.toggle_button.setText("◀")
            self.setMaximumWidth(16777215)  # Maximum Qt width
            self.setMinimumWidth(200)
            self.content.show()
            self.resize(self.stored_width, self.height())

    def add_widget(self, widget):
        """Ajoute un widget au contenu."""
        self.content_layout.addWidget(widget)

class DoctorPlanningView(QWidget):
    def __init__(self, planning, doctors, cats):
        super().__init__()
        self.planning = planning
        self.doctors = sorted(doctors, key=lambda d: d.name.lower()) if doctors else []
        self.cats = sorted(cats, key=lambda c: c.name.lower()) if cats else []
        
        self._destroyed = False
        self._is_updating = False
        self._update_pending = False
        
        # Cache pour les objets fréquemment utilisés
        from core.Constantes.constraints import PlanningConstraints
        self._constraints = PlanningConstraints()
        from workalendar.europe import France
        self._calendar = France()
        
        # Mapping des périodes vers les abréviations de postes (cache)
        self._period_to_post = {
            1: ["ML", "MC", "MM", "CM", "HM", "SM", "RM"],  # Matin
            2: ["CA", "HA", "SA", "RA", "AL", "AC", "CT"],  # Après-midi
            3: ["CS", "HS", "SS", "RS", "NA", "NM", "NC"]   # Soir
        }
        
        # Cache des horaires
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
        # Layout principal
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Créer un splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Widget gauche (planning)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Sélecteur de médecin/CAT
        selector_layout = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.addItems([doctor.name for doctor in self.doctors])
        self.selector.addItems([cat.name for cat in self.cats])
        
        if self.selector.count() == 0:
            self.selector.addItem("Aucun médecin/CAT")
        
        self.selector.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.selector.installEventFilter(self)
        self.selector.currentIndexChanged.connect(self._on_selection_changed)
        selector_layout.addWidget(self.selector)
        left_layout.addLayout(selector_layout)

        # Table du planning
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._on_cell_clicked)
        scroll_area.setWidget(self.table)
        left_layout.addWidget(scroll_area)

        # Widget droit (détails) avec sections
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Police en gras pour les en-têtes
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(10)

        # Section des postes attribués
        self.assigned_section = CollapsibleWidget("Détails des postes")
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(2)
        
        # En-têtes avec style pour detail_table
        for col, text in enumerate(["Poste", "Médecin"]):
            header_item = QTableWidgetItem(text)
            header_item.setFont(header_font)
            header_item.setForeground(QBrush(QColor(40, 40, 40)))
            self.detail_table.setHorizontalHeaderItem(col, header_item)
            
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.assigned_section.add_widget(self.detail_table)
        right_layout.addWidget(self.assigned_section)

        # Section des médecins disponibles
        self.available_section = CollapsibleWidget("Médecins disponibles")
        self.available_table = QTableWidget()
        self.available_table.setColumnCount(1)
        
        # En-tête avec style pour available_table
        header_item = QTableWidgetItem("Médecin")
        header_item.setFont(header_font)
        header_item.setForeground(QBrush(QColor(40, 40, 40)))
        self.available_table.setHorizontalHeaderItem(0, header_item)
        
        self.available_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.available_section.add_widget(self.available_table)
        right_layout.addWidget(self.available_section)

        # Section des médecins avec desiderata secondaire
        self.secondary_section = CollapsibleWidget("Médecins avec desiderata secondaire")
        self.secondary_table = QTableWidget()
        self.secondary_table.setColumnCount(1)
        
        # En-tête avec style pour secondary_table
        header_item = QTableWidgetItem("Médecin")
        header_item.setFont(header_font)
        header_item.setForeground(QBrush(QColor(40, 40, 40)))
        self.secondary_table.setHorizontalHeaderItem(0, header_item)
        
        self.secondary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.secondary_section.add_widget(self.secondary_table)
        right_layout.addWidget(self.secondary_section)

        # Ajouter les widgets au splitter
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        
        # Définir les tailles initiales (70% - 30%)
        self.splitter.setSizes([700, 300])
        
        layout.addWidget(self.splitter)

    def _on_cell_clicked(self, row: int, col: int):
        """
        Gère le clic sur une cellule du planning et affiche les postes.
        Si la colonne est 'J', affiche tous les postes du jour.
        Sinon, affiche les postes de la période correspondante.
        """
        try:
            # Récupérer la date correspondante
            current_date = self._get_date_from_row_col(row, col)
            if not current_date:
                return

            # Déterminer le type de jour
            day_type = self._get_day_type(current_date)
            period = self._get_period_from_column(col)

            # Récupérer le jour du planning
            day_planning = next((day for day in self.planning.days if day.date == current_date), None)
            
            # Récupérer la configuration des postes pour ce type de jour
            post_config = self._get_post_config_for_day(day_type)
            if not post_config:
                return

            # Obtenir les slots du jour actuel
            slots_by_type = defaultdict(list)
            if day_planning:
                for slot in day_planning.slots:
                    if period is None:  # Tous les postes du jour
                        slots_by_type[slot.abbreviation].append(slot)
                    else:
                        slot_period = get_post_period(slot)
                        if slot_period == period - 1:  # -1 car period commence à 1
                            slots_by_type[slot.abbreviation].append(slot)

            # Préparer la liste d'affichage
            display_posts = []
            for post_type, slots in slots_by_type.items():
                for slot in sorted(slots, key=lambda x: x.abbreviation):
                    display_posts.append((
                        slot.abbreviation,
                        slot.assignee if slot.assignee else "Non assigné"
                    ))

            # Mettre à jour les titres des sections
            period_names = {1: "Matin", 2: "Après-midi", 3: "Soir"}
            day_type_names = {
                "weekday": "Semaine",
                "saturday": "Samedi",
                "sunday_holiday": "Dimanche/Férié"
            }
            day_type_name = day_type_names.get(day_type, '')

            if period is None:
                title = f"Postes du {current_date.strftime('%d/%m/%Y')} ({day_type_name})"
            else:
                period_name = period_names.get(period, '')
                title = f"Postes du {current_date.strftime('%d/%m/%Y')} - {period_name} ({day_type_name})"

            self.assigned_section.title_label.setText(f"Détails des postes - {title}")
            self.available_section.title_label.setText(f"Médecins disponibles - {title}")
            self.secondary_section.title_label.setText(f"Médecins avec desiderata secondaire - {title}")

            # Mettre à jour les tables
            self._update_assigned_section(display_posts)
            self._update_available_doctors(current_date, period, day_type)
            self._update_secondary_desiderata(current_date, period, day_type)

        except Exception as e:
            logger.error(f"Erreur lors de l'affichage des détails: {e}")

    def _update_assigned_section(self, display_posts):
        """Met à jour la section des postes attribués"""
        self.detail_table.setRowCount(len(display_posts))
        for i, (post_type, assignee) in enumerate(display_posts):
            # Police en gras pour toutes les cellules
            bold_font = QFont()
            bold_font.setBold(True)
            
            # Poste
            post_item = QTableWidgetItem(post_type)
            post_item.setFont(bold_font)
            post_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            post_item.setForeground(QBrush(QColor(40, 40, 40)))
            self.detail_table.setItem(i, 0, post_item)
            
            # Médecin assigné
            doctor_item = QTableWidgetItem(assignee)
            doctor_item.setFont(bold_font)
            doctor_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Style pour les postes non assignés
            if assignee == "Non assigné":
                doctor_item.setForeground(QBrush(QColor(120, 120, 120)))
            else:
                doctor_item.setForeground(QBrush(QColor(40, 40, 40)))
                
            self.detail_table.setItem(i, 1, doctor_item)

    def _update_available_doctors(self, current_date: date, period: Optional[int], day_type: str):
        """
        Met à jour la section des médecins et CAT disponibles.
        
        Args:
            current_date: Date sélectionnée
            period: Période sélectionnée
                - None: colonne Jour (toutes périodes)
                - 1: Matin
                - 2: Après-midi
                - 3: Soir
            day_type: Type de jour (weekday, saturday, sunday_holiday)
        """
        logger.debug(f"Mise à jour des disponibilités pour {current_date}, période {period}, type {day_type}")
        
        self.available_table.clearContents()
        self.available_table.setRowCount(0)
        
        if not self.planning:
            return

        # Récupérer le jour du planning
        day_planning = next((day for day in self.planning.days if day.date == current_date), None)
        if not day_planning:
            return

        # Déterminer les périodes à vérifier
        periods_to_check = [1, 2, 3] if period is None else [period]
        available_personnel = set()

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
                    logger.debug(f"{person.name} a déjà un poste en période {check_period}")
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

                        start_datetime = datetime.combine(current_date, start_time)
                        end_datetime = datetime.combine(current_date, end_time)
                        
                        # Si le end_time est avant le start_time (cas des postes qui finissent le lendemain)
                        if end_time < start_time:
                            end_datetime = datetime.combine(current_date + timedelta(days=1), end_time)
                        
                        test_slot = TimeSlot(
                            start_time=start_datetime,
                            end_time=end_datetime,
                            site="Test",
                            slot_type="Test",
                            abbreviation=post_type
                        )
                        
                        # Vérifier si la personne peut prendre ce poste selon les contraintes
                        if self._constraints.can_assign_to_assignee(person, current_date, test_slot, self.planning):
                            logger.debug(f"{person.name} est disponible pour {post_type} en période {check_period}")
                            available_personnel.add(person.name)
                            break  # Si disponible pour un poste, passer à la période suivante
                            
                    except Exception as e:
                        logger.error(f"Erreur lors de la vérification de {person.name} pour {post_type}: {e}")
                        continue

        # Mise à jour de l'interface
        try:
            self.available_table.setRowCount(len(available_personnel))
            for i, name in enumerate(sorted(available_personnel)):
                item = QTableWidgetItem(name)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QBrush(AVAILABLE_COLOR))
                
                # Distinguer les CAT visuellement
                if any(cat.name == name for cat in self.cats):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    
                self.available_table.setItem(i, 0, item)
                
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'interface: {e}")
            
        logger.debug(f"Nombre de personnel disponible: {len(available_personnel)}")

    def _update_secondary_desiderata(self, current_date: date, period: Optional[int], day_type: str):
        """
        Met à jour en temps réel la section des médecins et CAT avec desiderata secondaire.
        """
        try:
            self.secondary_table.clearContents()
            self.secondary_table.setRowCount(0)
            
            if not self.planning:
                return

            secondary_personnel = set()
            all_personnel = self.doctors + self.cats
            
            for person in all_personnel:
                if not hasattr(person, 'desiderata'):
                    logger.debug(f"{person.name} n'a pas d'attribut desiderata")
                    continue
                    
                periods_to_check = [1, 2, 3] if period is None else [period]
                
                for check_period in periods_to_check:
                    for desiderata in person.desiderata:
                        if (desiderata.start_date <= current_date <= desiderata.end_date and 
                            desiderata.period == check_period and 
                            getattr(desiderata, 'priority', 'primary') == "secondary"):
                            secondary_personnel.add(person.name)
                            logger.debug(f"Personnel avec desiderata secondaire ajouté: {person.name}")
                            break

            # Mise à jour de l'interface
            self.secondary_table.setRowCount(len(secondary_personnel))
            for i, name in enumerate(sorted(secondary_personnel)):
                item = QTableWidgetItem(name)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QBrush(SECONDARY_DESIDERATA_COLOR))
                if any(cat.name == name for cat in self.cats):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.secondary_table.setItem(i, 0, item)
                
        except Exception as e:
            logger.error(f"Erreur dans _update_secondary_desiderata: {e}")

    def _get_day_type(self, date_to_check: date) -> str:
        """Détermine le type de jour (semaine, samedi, dimanche/férié)."""
        if self._calendar.is_holiday(date_to_check) or date_to_check.weekday() == 6:
            return "sunday_holiday"
        elif date_to_check.weekday() == 5:
            return "saturday"
        return "weekday"

    def _get_post_config_for_day(self, day_type: str) -> Dict:
        """Récupère la configuration des postes pour un type de jour."""
        if not self.planning or not hasattr(self.planning, 'pre_analysis_results'):
            return None
            
        return self.planning.pre_analysis_results.get('adjusted_posts', {}).get(day_type, {})

    def _get_posts_for_period(self, period: int, post_config: Dict) -> List[Tuple[str, int]]:
        """
        Retourne la liste des postes configurés avec leur nombre total requis.
        Returns:
            List[Tuple[str, int]]: Liste de tuples (type_poste, nombre_requis)
        """
        # Filtrer les postes configurés pour cette période
        period_posts = self._period_to_post[period]  # Get exact post types for this period
        configured_posts = []
        
        for post_type in period_posts:
            if post_type in post_config:
                config_value = post_config[post_type]
                # Gérer le cas où config_value est un objet PostConfig
                total = config_value.total if hasattr(config_value, 'total') else config_value
                if total > 0:
                    configured_posts.append((post_type, total))

        return sorted(configured_posts)
            
    def _get_date_from_row_col(self, row: int, col: int) -> Optional[date]:
        """Calcule la date correspondant à une cellule."""
        try:
            if not self.planning:
                return None
                
            # La première colonne est pour les jours
            if col < 1:
                return None
                
            # Le numéro du jour est dans la première colonne
            day = int(self.table.item(row, 0).text())
            
            # Calculer le mois à partir de la colonne
            month_col = (col - 1) // 4
            current_date = self.planning.start_date
            target_date = current_date.replace(day=1) + relativedelta(months=month_col)
            
            return target_date.replace(day=day)
            
        except Exception as e:
            logger.error(f"Erreur calcul date: {e}")
            return None

    def _get_period_from_column(self, col: int) -> Optional[int]:
        """
        Détermine la période à partir de la colonne.
        Returns:
            - None pour la colonne J (tous les postes)
            - 1 pour la colonne M (matin)
            - 2 pour la colonne AM (après-midi)
            - 3 pour la colonne S (soir)
        """
        if col < 1:
            return None
            
        # Calculer l'index dans le groupe de colonnes (J, M, AM, S)
        column_in_group = (col - 1) % 4
        
        # column_in_group peut être:
        # 0 -> J (jour)
        # 1 -> M (matin)
        # 2 -> AM (après-midi)
        # 3 -> S (soir)
        
        if column_in_group == 0:  # Colonne J
            return None
        else:
            return column_in_group  # Les autres colonnes correspondent directement aux périodes
    
    def update_selector(self):
        """Mise à jour sécurisée du sélecteur avec vérification de l'état"""
        if not hasattr(self, 'selector') or not self.selector:
            return
            
        current_text = self.selector.currentText()
        
        self.selector.blockSignals(True)
        try:
            self.selector.clear()
            
            # Ajout des médecins
            if self.doctors:
                for doctor in self.doctors:
                    self.selector.addItem(doctor.name)
                    
            # Ajout des CAT
            if self.cats:
                for cat in self.cats:
                    self.selector.addItem(cat.name)
            
            # S'assurer qu'il y a au moins un élément
            if self.selector.count() == 0:
                self.selector.addItem("Aucun médecin/CAT")
                return
                
            # Restaurer la sélection précédente si possible
            index = self.selector.findText(current_text)
            if index >= 0:
                self.selector.setCurrentIndex(index)
            else:
                self.selector.setCurrentIndex(0)  # Sélectionner le premier élément par défaut
                
        finally:
            self.selector.blockSignals(False)

    def _safe_process_update(self):
        """Traitement sécurisé des mises à jour"""
        try:
            if self._destroyed or not self.isVisible():
                return
                
            self._is_updating = True
            if hasattr(self, 'table') and self.table:
                self.table.setUpdatesEnabled(False)
            
            try:
                self.update_table()
            finally:
                if hasattr(self, 'table') and self.table:
                    self.table.setUpdatesEnabled(True)
                self._is_updating = False
                
                if self._update_pending:
                    self._update_pending = False
                    self._schedule_update()
                    
        except RuntimeError:
            # Ignorer les erreurs si le widget est détruit
            pass

    def _on_selection_changed(self, index):
        """Gestionnaire d'événements optimisé"""
        if self._destroyed:
            return
            
        if self._is_updating:
            self._update_pending = True
            return
            
        self._schedule_update()

    def update_view(self, planning, doctors, cats):
        """Mise à jour complète de la vue avec vérification des données"""
        if not planning or (not doctors and not cats):
            self.clear_view()
            return
            
        self.planning = planning
        self.doctors = sorted(doctors, key=lambda d: d.name.lower())
        self.cats = sorted(cats, key=lambda c: c.name.lower())
        
        # Mise à jour immédiate
        self._safe_process_update()

    def _schedule_update(self):
        """Mise à jour immédiate de l'interface"""
        if self._destroyed:
            return
            
        self._safe_process_update()

    def _process_delayed_update(self):
        """Traite la mise à jour différée avec protection"""
        if not self.isVisible():
            return
            
        self._is_updating = True
        try:
            self.blockSignals(True)
            self.update_table()
        except Exception as e:
            print(f"Erreur mise à jour différée: {e}")
        finally:
            self.blockSignals(False)
            self._is_updating = False
            
            if self._update_pending:
                self._update_pending = False
                self._schedule_update()
            
            
    def eventFilter(self, obj, event):
        if obj == self.selector and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up or key == Qt.Key.Key_Down:
                current_index = self.selector.currentIndex()
                if key == Qt.Key.Key_Up and current_index > 0:
                    self.selector.setCurrentIndex(current_index - 1)
                elif key == Qt.Key.Key_Down and current_index < self.selector.count() - 1:
                    self.selector.setCurrentIndex(current_index + 1)
                return True
        return super().eventFilter(obj, event)

    def update_table(self):
        """Mise à jour sécurisée de la table"""
        if self._destroyed or not hasattr(self, 'table') or not self.table:
            return
            
        # Vérifications initiales
        if not self.planning or not self.planning.days:
            self.clear_table()
            return

        # Configuration des couleurs
        colors = {
            "primary": {
                "weekend": QColor(255, 150, 150),
                "normal": QColor(255, 200, 200)
            },
            "secondary": {
                "weekend": QColor(150, 200, 255),
                "normal": QColor(180, 220, 255)
            },
            "base": {
                "weekend": WEEKEND_COLOR,
                "normal": WEEKDAY_COLOR
            }
        }

        # Désactiver les mises à jour pendant le traitement
        self.table.setUpdatesEnabled(False)
        try:
            if not self.planning or not self.planning.days:
                self.clear_table()
                return

            selected_name = self.selector.currentText()
            start_date = self.planning.start_date
            end_date = self.planning.end_date
            
            # Calcul des mois
            total_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1

            # Configuration initiale
            self.table.clear()
            self.table.setRowCount(31)
            self.table.setColumnCount(total_months * 4 + 1)

            # En-têtes avec police en gras
            headers = ["Jour"]
            current_date = date(start_date.year, start_date.month, 1)
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
                self.table.setHorizontalHeaderItem(col, header_item)

            # Remplissage des données
            current_date = start_date
            while current_date <= end_date:
                self._populate_day_row(current_date, selected_name, colors)
                current_date += timedelta(days=1)

            # Ajustement final
            self._adjust_table_dimensions()
            
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                # Recréer la table en cas d'erreur
                self.table = None
                QTimer.singleShot(100, self.init_ui)
                return
            raise
        finally:
            if hasattr(self, 'table') and self.table:
                self.table.setUpdatesEnabled(True)
                
    def closeEvent(self, event):
        """Nettoyage amélioré lors de la fermeture"""
        self._destroyed = True
        
        # Nettoyage explicite
        if hasattr(self, 'table'):
            self.table.clearContents()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
        
        super().closeEvent(event)
        
    def hideEvent(self, event):
        """Gestion des événements de masquage"""
        super().hideEvent(event)
        
    def showEvent(self, event):
        """Gestion des événements d'affichage"""
        if not self._destroyed and self._update_pending:
            self._schedule_update()
        super().showEvent(event)
                
    def _populate_day_row(self, current_date, selected_name, colors):
        """Remplit une ligne du tableau pour un jour donné"""
        day_row = current_date.day - 1
        month_col = (current_date.year - self.planning.start_date.year) * 12 + current_date.month - self.planning.start_date.month
        col_offset = month_col * 4 + 1

        # Configuration de base de la ligne
        self._set_basic_row_items(day_row, col_offset, current_date)

        # Traitement des postes
        day_planning = next((day for day in self.planning.days if day.date == current_date), None)
        if day_planning:
            is_weekend_or_holiday = day_planning.is_weekend or day_planning.is_holiday_or_bridge
            background_color = colors["base"]["weekend" if is_weekend_or_holiday else "normal"]
            
            # Récupération et tri des slots par période
            slots = [slot for slot in day_planning.slots if slot.assignee == selected_name]
            periods = [[] for _ in range(3)]  # 3 périodes : matin, après-midi, soir
            
            for slot in slots:
                period_index = get_post_period(slot)  # Utilise la fonction existante
                if 0 <= period_index < 3:  # Vérifie que l'index est valide
                    periods[period_index].append(slot)

            # Obtention de la personne sélectionnée
            selected_person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
            
            # Police en gras pour toutes les cellules
            bold_font = QFont()
            bold_font.setBold(True)
            bold_font.setPointSize(10)

            # Remplissage des cellules pour chaque période
            for i in range(3):
                item = QTableWidgetItem()
                post_list = periods[i]
                
                # Texte de la cellule
                text = ", ".join(slot.abbreviation for slot in post_list)
                item.setText(text)
                item.setFont(bold_font)
                item.setForeground(QBrush(QColor(40, 40, 40)))
                
                # Coloration selon desiderata
                current_color = background_color
                
                if selected_person:
                    for desiderata in selected_person.desiderata:
                        if (desiderata.start_date <= current_date <= desiderata.end_date and 
                            desiderata.period == i + 1):  # +1 car les périodes de desiderata commencent à 1
                            priority = getattr(desiderata, 'priority', 'primary')
                            current_color = colors[priority]["weekend" if is_weekend_or_holiday else "normal"]
                            break
                
                item.setBackground(QBrush(current_color))
                self.table.setItem(day_row, col_offset + i + 1, item)

    def _set_basic_row_items(self, day_row, col_offset, current_date):
        """Configure les cellules de base d'une ligne (jour et jour de la semaine)"""
        # Police en gras pour toutes les cellules
        bold_font = QFont()
        bold_font.setBold(True)
        bold_font.setPointSize(10)
        
        # Jour
        day_item = QTableWidgetItem(str(current_date.day))
        day_item.setFont(bold_font)
        day_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        day_item.setForeground(QBrush(QColor(40, 40, 40)))
        self.table.setItem(day_row, 0, day_item)
        
        # Jour de la semaine
        weekday_names = ["L", "M", "M", "J", "V", "S", "D"]
        weekday_item = QTableWidgetItem(weekday_names[current_date.weekday()])
        weekday_item.setFont(bold_font)
        weekday_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        weekday_item.setForeground(QBrush(QColor(40, 40, 40)))
        self.table.setItem(day_row, col_offset, weekday_item)

    def _adjust_table_dimensions(self):
        """Ajuste les dimensions finales du tableau"""
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 20)

        for col in range(self.table.columnCount()):
            if col == 0:
                self.table.setColumnWidth(col, 40)  # Colonne des jours
            elif (col - 1) % 4 == 0:
                self.table.setColumnWidth(col, 30)  # Colonnes J
            else:
                self.table.setColumnWidth(col, 50)  # Colonnes M, AM, S

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def clear_table(self):
        """Nettoie la table"""
        if hasattr(self, 'table') and self.table:
            self.table.clearContents()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)

    def clear_view(self):
        """Nettoie la vue complète"""
        self.clear_table()
        if hasattr(self, 'detail_table'):
            self.detail_table.clearContents()
            self.detail_table.setRowCount(0)
        if hasattr(self, 'available_table'):
            self.available_table.clearContents()
            self.available_table.setRowCount(0)
        if hasattr(self, 'secondary_table'):
            self.secondary_table.clearContents()
            self.secondary_table.setRowCount(0)
