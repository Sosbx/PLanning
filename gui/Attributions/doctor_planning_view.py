# © 2024 HILAL Arkane. Tous droits réservés.
# .gui/doctor_planning_view
# © 2024 HILAL Arkane. Tous droits réservés.
# .gui/doctor_planning_view
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QScrollArea, 
                             QLabel, QScrollArea, QSplitter, QPushButton, QFrame,QMenu, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from datetime import date, timedelta, datetime, time
from typing import Union, Optional, Dict, List, Tuple
from collections import defaultdict
from core.utils import get_post_period
from core.Constantes.models import Doctor, CAT, TimeSlot
import logging
from dateutil.relativedelta import relativedelta
from gui.components.planning_table_component import PlanningTableComponent
from ..styles import color_system, StyleConstants


logger = logging.getLogger(__name__)

# Get colors from color system
WEEKEND_COLOR = color_system.get_color('weekend')
WEEKDAY_COLOR = color_system.get_color('weekday')
WEEKDAY_TEXT_COLOR = color_system.get_color('text', 'primary')
AVAILABLE_COLOR = color_system.get_color('available')
SECONDARY_DESIDERATA_COLOR = color_system.get_color('desiderata', 'normal', 'secondary')



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
        
        # Initialiser l'interface utilisateur (appel obligatoire avant d'utiliser table)
        self.init_ui()
        
        # Configurer uniquement le clic droit (supprimer le double-clic)
        self.set_context_menu_policy()

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

        # Utiliser le nouveau composant PlanningTableComponent
        self.table = PlanningTableComponent()

        # Configurer les dimensions adaptatives
        self.table.min_row_height = 20  # Augmenté pour accommoder des polices plus grandes
        self.table.max_row_height = 28  # Augmenté pour accommoder des polices plus grandes
        self.table.set_min_column_widths(
            day_width=28,      # Augmenté pour accommoder des polices plus grandes
            weekday_width=35,  # Augmenté pour accommoder des polices plus grandes
            period_width=40    # Augmenté pour accommoder des polices plus grandes
        )
        self.table.set_max_column_widths(
            day_width=40,
            weekday_width=45,
            period_width=80
        )

        # Configurer les paramètres de police - Tailles augmentées
        from PyQt6.QtGui import QFontDatabase
        available_fonts = QFontDatabase.families()
        preferred_fonts = ["Segoe UI", "Arial", "Helvetica", "San Francisco", "Roboto", "-apple-system"]
        selected_font = next((f for f in preferred_fonts if f in available_fonts), None)

        self.table.set_font_settings(
            font_family=selected_font,
            base_size=12,       # Taille augmentée
            header_size=14,     # Taille augmentée
            weekday_size=10      # Taille augmentée
        )

        # Activer la mise en gras des postes
        self.table.set_bold_posts(True)

        # Configurer les couleurs du tableau en utilisant les couleurs standard
        self.table.set_colors(PlanningTableComponent.get_standard_colors())
        

        # Connecter le signal de clic à notre méthode
        self.table.cell_clicked.connect(self._on_cell_clicked_date_period)

        scroll_area.setWidget(self.table)
        left_layout.addWidget(scroll_area)
        
        # Widget droit (détails) avec sections
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Section des postes attribués
        self.assigned_section = CollapsibleWidget("Détails des postes")
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(2)
        self.detail_table.setHorizontalHeaderLabels(["Poste", "Médecin"])
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.assigned_section.add_widget(self.detail_table)
        right_layout.addWidget(self.assigned_section)

        # Section des médecins disponibles
        self.available_section = CollapsibleWidget("Médecins disponibles")
        self.available_table = QTableWidget()
        self.available_table.setColumnCount(1)
        self.available_table.setHorizontalHeaderLabels(["Médecin"])
        self.available_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.available_section.add_widget(self.available_table)
        right_layout.addWidget(self.available_section)

        # Section des médecins avec desiderata secondaire
        self.secondary_section = CollapsibleWidget("Médecins avec desiderata secondaire")
        self.secondary_table = QTableWidget()
        self.secondary_table.setColumnCount(1)
        self.secondary_table.setHorizontalHeaderLabels(["Médecin"])
        self.secondary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.secondary_section.add_widget(self.secondary_table)
        right_layout.addWidget(self.secondary_section)

        # Ajouter les widgets au splitter
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        
        # Définir les tailles initiales (85% - 15%)
        self.splitter.setSizes([850, 150])
        
        # Style personnalisé pour le splitter
        custom_splitter_style = """
            QSplitter::handle {
                background-color: #CBD5E1;
            }
            
            QSplitter::handle:horizontal {
                width: 4px;
                margin: 4px 0px;
                border-radius: 2px;
                background-color: #CBD5E1;
            }
            
            QSplitter::handle:hover {
                background-color: #1A5A96;
            }
        """
        self.splitter.setStyleSheet(custom_splitter_style)
        
        # Connecter le signal splitterMoved pour sauvegarder l'état
        self.splitter.splitterMoved.connect(self.saveState)
        
        # Restaurer l'état précédent si disponible
        self.restoreState()
        
        layout.addWidget(self.splitter)
    
    def resizeEvent(self, event):
        """Réajuste les dimensions du tableau lors du redimensionnement de la fenêtre"""
        super().resizeEvent(event)
        if hasattr(self, 'table') and isinstance(self.table, PlanningTableComponent):
            # Réoptimiser les dimensions après le redimensionnement
            QTimer.singleShot(50, self.table.optimize_dimensions)

    def configure_font_size(self, size_adjustment=0):
        """
        Ajuste la taille de police du tableau
        
        Args:
            size_adjustment: Ajustement relatif de la taille (+1 pour augmenter, -1 pour diminuer)
        """
        if not hasattr(self, 'table') or not isinstance(self.table, PlanningTableComponent):
            return
        
        # Récupérer les paramètres actuels
        current_settings = self.table._font_settings
        
        # Appliquer l'ajustement
        self.table.set_font_settings(
            base_size=max(7, current_settings['base_size'] + size_adjustment),
            header_size=max(8, current_settings['header_size'] + size_adjustment),
            weekday_size=max(6, current_settings['weekday_size'] + size_adjustment)
        )
        
        # Réoptimiser les dimensions
        self.table.optimize_dimensions()
        
    def _on_cell_clicked_date_period(self, current_date, period):
        """
        Gère le clic sur une cellule du planning avec la nouvelle interface
        
        Args:
            current_date: Date correspondante
            period: Période (1=Matin, 2=Après-midi, 3=Soir, -1=Jour)
        """
        if not current_date:
            return
            
        # Convertir -1 en None pour la compatibilité avec le reste du code
        if period == -1:
            period = None
            
        # Stocker la date et la période sélectionnées pour pouvoir les réutiliser lors des mises à jour
        self.selected_date = current_date
        self.selected_period = period
            
        # Le reste du code est similaire à _on_cell_clicked mais utilise directement
        # current_date et period plutôt que de les calculer à partir de row et col
        
        # Déterminer le type de jour
        day_type = self._get_day_type(current_date)

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
                    if slot_period == period:  # Les périodes sont maintenant alignées
                        slots_by_type[slot.abbreviation].append(slot)

        # Préparer la liste d'affichage
        display_posts = []
        for post_type, slots in slots_by_type.items():
            for slot in sorted(slots, key=lambda x: x.abbreviation):
                display_posts.append((
                    slot.abbreviation,
                    slot.assignee if slot.assignee else "Non assigné"
                ))

        # Mettre à jour les titres des sections de manière plus compacte
        period_names = {1: "M", 2: "AM", 3: "S"}  # Abréviations: Matin, Après-Midi, Soir
        day_type_names = {
            "weekday": "Sem",
            "saturday": "Sam",
            "sunday_holiday": "Dim/Fér"
        }
        day_type_name = day_type_names.get(day_type, '')
        date_str = current_date.strftime('%d/%m')

        if period is None:
            title = f"{date_str} ({day_type_name})"
        else:
            period_name = period_names.get(period, '')
            title = f"{date_str} {period_name} ({day_type_name})"

        self.assigned_section.title_label.setText(f"Postes - {title}")
        self.available_section.title_label.setText(f"Disponibles - {title}")
        self.secondary_section.title_label.setText(f"Desiderata sec. - {title}")

        # Mettre à jour les tables
        self._update_assigned_section(display_posts)
        self._update_available_doctors(current_date, period, day_type)
        self._update_secondary_desiderata(current_date, period, day_type)

    # Les méthodes _toggle_panel_size et toggle_compact_mode ont été supprimées car elles ne sont plus nécessaires
    
    def saveState(self):
        """Sauvegarde l'état du splitter"""
        if hasattr(self, 'splitter') and self.splitter:
            sizes = self.splitter.sizes()
            # Sauvegarder les tailles dans les paramètres de l'application
            if hasattr(self.planning, 'main_window') and self.planning.main_window:
                self.planning.main_window.settings.setValue("doctor_planning_view/splitter_sizes", sizes)
    
    def restoreState(self):
        """Restaure l'état du splitter"""
        if hasattr(self, 'splitter') and self.splitter and hasattr(self.planning, 'main_window') and self.planning.main_window:
            # Restaurer la taille du splitter
            sizes = self.planning.main_window.settings.value("doctor_planning_view/splitter_sizes")
            if sizes:
                self.splitter.setSizes(sizes)
    
    def _update_assigned_section(self, display_posts):
        """Met à jour la section des postes attribués avec des indicateurs visuels"""
        self.detail_table.setRowCount(len(display_posts))
        for i, (post_type, assignee) in enumerate(display_posts):
            # Poste
            post_item = QTableWidgetItem(post_type)
            post_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_table.setItem(i, 0, post_item)
            
            # Médecin assigné
            doctor_item = QTableWidgetItem(assignee)
            doctor_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Style pour les postes non assignés
            if assignee == "Non assigné":
                from gui.styles import PlatformHelper
                PlatformHelper.apply_foreground_color(doctor_item, QColor(150, 150, 150))
                PlatformHelper.apply_background_color(doctor_item, QColor(255, 240, 240))  # Fond légèrement rouge
                doctor_item.setToolTip("Ce poste n'est pas encore assigné")
            else:
                from gui.styles import PlatformHelper
                PlatformHelper.apply_background_color(doctor_item, QColor(240, 255, 240))  # Fond légèrement vert
                
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
                        get_post_period(slot) == check_period):  # Les périodes sont maintenant alignées
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
                from gui.styles import PlatformHelper
                PlatformHelper.apply_background_color(item, AVAILABLE_COLOR)
                
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
                from gui.styles import PlatformHelper
                PlatformHelper.apply_background_color(item, SECONDARY_DESIDERATA_COLOR)
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
        
        # S'assurer que main_window est toujours défini (ajoutez cette ligne)
        if hasattr(self, 'main_window') and not self.main_window and hasattr(planning, 'main_window'):
            self.main_window = planning.main_window
        
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
        """Mise à jour de la table avec le nouveau composant"""
        if self._destroyed or not hasattr(self, 'table') or not self.table:
            return
            
        # Vérifications initiales
        if not self.planning or not self.planning.days:
            self.clear_table()
            return

        # Configuration des couleurs (déjà fait dans init_ui)
        selected_name = self.selector.currentText()
        start_date = self.planning.start_date
        end_date = self.planning.end_date
        
        # Désactiver les mises à jour de l'interface pendant les modifications
        self.table.setUpdatesEnabled(False)
        
        try:
            # Configurer les dates du planning
            self.table.setup_planning_dates(start_date, end_date)
            
            # Remplir les jours de base
            self.table.populate_days()
            
            # Mettre à jour les cellules pour le médecin/CAT sélectionné
            self._update_cells_for_selected(selected_name)
            
            # Mettre à jour les sections d'information si une cellule est sélectionnée
            if hasattr(self, 'selected_date') and self.selected_date:
                # Simuler un clic sur la cellule actuellement sélectionnée pour rafraîchir les informations
                self._on_cell_clicked_date_period(self.selected_date, self.selected_period)
        finally:
            # Réactiver les mises à jour de l'interface
            self.table.setUpdatesEnabled(True)
            
            # Forcer un rafraîchissement visuel
            self.table.viewport().update()
    
    def _update_cells_for_selected(self, selected_name):
        """
        Met à jour les cellules pour un médecin/CAT sélectionné
        
        Args:
            selected_name: Nom du médecin/CAT sélectionné
        """
        if not self.planning or not self.planning.days:
            return
            
        # Récupérer la personne sélectionnée pour les desiderata
        selected_person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
        
        # Parcourir tous les jours du planning
        for day_planning in self.planning.days:
            current_date = day_planning.date
            is_weekend_or_holiday = day_planning.is_weekend or day_planning.is_holiday_or_bridge
            
            # Récupération et tri des slots par période pour la personne sélectionnée
            slots = [slot for slot in day_planning.slots if slot.assignee == selected_name]
            periods = [[] for _ in range(3)]  # 3 périodes : matin, après-midi, soir
            
            for slot in slots:
                period_index = get_post_period(slot)  # Utilise la fonction existante
                if 0 <= period_index <= 3:  # Vérifie que l'index est valide (1-3)
                    periods[period_index - 1].append(slot)  # -1 car periods est indexé de 0 à 2
                    
            # Mise à jour des cellules pour chaque période
            for i in range(3):
                period = i + 1
                post_list = periods[i]
                
                # Texte de la cellule
                text = ", ".join(slot.abbreviation for slot in post_list)
                
                # Déterminer la couleur de fond en fonction des desiderata
                background_color = self.table.current_colors["base"]["weekend" if is_weekend_or_holiday else "normal"]
                
                if selected_person:
                    for desiderata in selected_person.desiderata:
                        if (desiderata.start_date <= current_date <= desiderata.end_date and 
                            desiderata.period == period):
                            priority = getattr(desiderata, 'priority', 'primary')
                            background_color = self.table.current_colors[priority]["weekend" if is_weekend_or_holiday else "normal"]
                            break
                
                # Vérifier si c'est une post-attribution
                has_post_attribution = False
                foreground_color = None
                font = None
                
                for slot in post_list:
                    if hasattr(slot, 'is_post_attribution') and slot.is_post_attribution:
                        has_post_attribution = True
                        break
                
                # Appliquer le style pour les post-attributions
                if has_post_attribution and hasattr(self, 'main_window') and hasattr(self.main_window, 'post_attribution_handler'):
                    foreground_color = self.main_window.post_attribution_handler.get_post_color()
                    font = self.main_window.post_attribution_handler.get_post_font()
                
                # Optimiser le texte si nécessaire
                display_text, tooltip = self.table.optimize_cell_text(text)
                
                # Mettre à jour la cellule
                self.table.update_cell(
                    current_date, period, display_text,
                    background_color=background_color,
                    foreground_color=foreground_color,
                    font=font,
                    tooltip=tooltip,
                    custom_data={"slots": post_list}  # Stocker les slots pour usage ultérieur
                )
                
            
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
                
   
    def set_context_menu_policy(self):
        """Définit la politique de menu contextuel pour la table."""
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
    def show_context_menu(self, position):
        """Affiche le menu contextuel pour gérer les post-attributions."""
        if not hasattr(self, 'main_window') or not self.main_window:
            print("Erreur: main_window n'est pas défini dans DoctorPlanningView")
            return
                
        if not hasattr(self.main_window, 'post_attribution_handler'):
            print("Erreur: post_attribution_handler n'est pas disponible dans main_window")
            return
        
        # Vérifier que le planning existe
        if not self.planning:
            print("Aucun planning disponible")
            return
        
        # Récupérer la cellule cliquée
        item = self.table.itemAt(position)
        if not item:
            return
        
        # Récupérer les données de la cellule
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
        
        date = data.get("date")
        period = data.get("period")
        
        if not date or not period or period not in [1, 2, 3]:
            return
        
        # Vérifier si le planning a été généré pour cette date
        is_date_generated = self._is_date_generated(date)
        
        # Créer le menu contextuel
        menu = QMenu(self)
        
        # Si la date n'est pas générée, afficher une option désactivée
        if not is_date_generated:
            no_planning_action = menu.addAction("Planning non généré pour post-attribution")
            no_planning_action.setEnabled(False)
            menu.exec(self.table.viewport().mapToGlobal(position))
            return
        
        # Obtenir le jour du planning
        day_planning = next((day for day in self.planning.days if day.date == date), None)
        if not day_planning:
            no_day_action = menu.addAction("Jour non disponible")
            no_day_action.setEnabled(False)
            menu.exec(self.table.viewport().mapToGlobal(position))
            return
        
        current_person = self.get_current_person()
        if not current_person:
            return
        
        # Vérifier dans post_attributions directement s'il y a une post-attribution
        # pour cette personne, date et période
        has_post_attr = False
        post_type = None
        
        handler = self.main_window.post_attribution_handler
        if hasattr(handler, 'post_attributions'):
            if date in handler.post_attributions:
                if current_person.name in handler.post_attributions[date]:
                    if period in handler.post_attributions[date][current_person.name]:
                        has_post_attr = True
                        post_type = handler.post_attributions[date][current_person.name][period]
        
        # Si une post-attribution existe, ajouter UNIQUEMENT l'option de suppression
        if has_post_attr and post_type:
            action = menu.addAction(f"Supprimer post-attribution: {post_type}")
            action.triggered.connect(
                lambda checked=False: handler.remove_post_attribution(
                    date, period, current_person.name, self.table
                )
            )
        else:
            # UNIQUEMENT si aucune post-attribution n'existe déjà, proposer l'ajout
            day_type = self._get_day_type(date)
            available_posts = handler._get_available_posts(
                date, period-1, day_type, current_person.name
            )
            
            if available_posts:
                add_menu = menu.addMenu("Ajouter un poste post-attribué")
                for post_type in available_posts:
                    action = add_menu.addAction(post_type)
                    action.triggered.connect(
                        lambda checked=False, pt=post_type: handler.add_post_attribution(
                            date, period, current_person.name, pt, self.table
                        )
                    )
            else:
                no_posts_action = menu.addAction("Aucun poste disponible à ajouter")
                no_posts_action.setEnabled(False)
        
        # Afficher le menu
        if menu.actions():
            menu.exec(self.table.viewport().mapToGlobal(position))

    def _is_date_generated(self, date):
        """
        Vérifie si le planning a été généré pour une date donnée.
        
        Args:
            date: Date à vérifier
            
        Returns:
            bool: True si le planning a été généré pour cette date, False sinon
        """
        # Vérifier si le planning existe
        if not self.planning or not hasattr(self.planning, 'weekend_validated'):
            return False
        
        # Déterminer si c'est un weekend ou jour férié
        is_weekend = date.weekday() >= 5  # 5=Samedi, 6=Dimanche
        from workalendar.europe import France
        calendar = France()
        is_holiday = calendar.is_holiday(date)
        
        # Règles:
        # - Pour les weekends et jours fériés: autorisé après génération des weekends
        # - Pour les jours de semaine: autorisé seulement si les weekends sont validés
        if is_weekend or is_holiday:
            return True  # Les weekends sont toujours générés en premier
        else:
            return self.planning.weekend_validated  # Jours de semaine uniquement si validés

    # 4. Ajouter la méthode get_current_person
    def get_current_person(self):
        """Retourne la personne actuellement sélectionnée."""
        name = self.selector.currentText()
        return next((p for p in self.doctors + self.cats if p.name == name), None)
    
    def _optimize_cell_display(self, item, text, max_length=15):
        """
        Optimise l'affichage des cellules avec beaucoup de contenu
        
        Args:
            item: QTableWidgetItem à configurer
            text: Texte à afficher
            max_length: Longueur maximale avant troncature
        """
        if len(text) > max_length:
            # Si le texte est trop long, le tronquer et ajouter une ellipse
            shortened_text = text[:max_length] + "..."
            item.setText(shortened_text)
            
            # Ajouter un tooltip avec le texte complet
            item.setToolTip(text)
        else:
            item.setText(text)
        
        # Ajuster le style pour rendre plus lisible
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # On pourrait aussi ajuster la taille de police pour les textes longs
        if len(text) > 10:
            font = item.font()
            font.setPointSize(7)  # Police plus petite pour les textes longs
            item.setFont(font)

    
    def clear_table(self):
        """Nettoie la table"""
        if hasattr(self, 'table') and self.table:
            self.table.clear()
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
