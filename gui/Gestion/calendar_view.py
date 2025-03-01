# © 2024 HILAL Arkane. Tous droits réservés.
# gui/calendar_view.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                           QDialog, QComboBox, QGridLayout, QScrollArea, QSizePolicy, QFrame,
                           QMessageBox)
from PyQt6.QtCore import Qt, QDate, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QColor, QPalette, QBrush
from datetime import date, timedelta
import calendar
from core.Constantes.models import SpecificPostConfig
from core.Constantes.day_type import DayType
from workalendar.europe import France
from ..styles import color_system, ACTION_BUTTON_STYLE, StyleConstants
import logging

logger = logging.getLogger(__name__)

class CalendarCell(QWidget):
    """Cellule du calendrier représentant un jour"""
    
    clicked = pyqtSignal(date)
    
    def __init__(self, date_obj, configs=None, is_current_month=True, day_type=None, parent=None):
        super().__init__(parent)
        self.date_obj = date_obj
        self.configs = configs or []  # Liste des configurations pour ce jour
        self.is_current_month = is_current_month
        self.is_weekend = date_obj.weekday() >= 5  # 5=samedi, 6=dimanche
        self.is_sunday = date_obj.weekday() == 6  # 6=dimanche
        self.is_today = date_obj == date.today()
        self.day_type = day_type  # "normal", "holiday", "bridge_day"
        # Ne plus définir de taille fixe pour permettre l'adaptativité
        self.setMinimumSize(110, 100)  # Taille minimale seulement
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Politique de taille expansive
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Style de base pour la cellule avec bordure plus visible
        base_style = """
            QWidget {
                border-radius: 4px;
                border: 1px solid #D0D0D0;
            }
        """
        
        # Définir la couleur de fond en fonction des propriétés
        if not self.is_current_month:
            # Jour d'un autre mois
            self.setStyleSheet(base_style + """
                background-color: #F0F0F0;
                color: #A0A0A0;
            """)
        elif self.day_type == "holiday":
            # Jour férié
            self.setStyleSheet(base_style + """
                background-color: #FCE4EC;
            """)
        elif self.day_type == "bridge_day":
            # Jour de pont
            self.setStyleSheet(base_style + """
                background-color: #FFF3E0;
            """)
        elif self.is_sunday:
            # Dimanche
            self.setStyleSheet(base_style + """
                background-color: #F3E5F5;
            """)
        elif self.is_weekend:
            # Samedi
            self.setStyleSheet(base_style + """
                background-color: #E8EDF5;
            """)
        else:
            # Jour normal
            self.setStyleSheet(base_style + """
                background-color: #FFFFFF;
            """)
        
        # Mise en évidence pour aujourd'hui
        if self.is_today:
            self.setStyleSheet(self.styleSheet() + """
                border: 2px solid #3498db;
            """)
        
        # Entête avec le numéro du jour
        header_widget = QWidget()
        header_widget.setStyleSheet("border: none;")  # Pas de bordure pour le widget d'entête
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        
        # Numéro du jour avec indication du type de jour spécial
        day_number = QLabel(str(self.date_obj.day))
        day_number.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        if self.day_type == "holiday":
            day_number.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                padding: 2px;
                background-color: transparent;
                border: none;
                color: #C2185B;  /* Rouge plus foncé pour jour férié */
            """)
        elif self.day_type == "bridge_day":
            day_number.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                padding: 2px;
                background-color: transparent;
                border: none;
                color: #E65100;  /* Orange pour jour de pont */
            """)
        else:
            day_number.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                padding: 2px;
                background-color: transparent;
                border: none;
            """)
            
        # Ajouter une icône ou une indication pour le type de jour
        day_type_indicator = QLabel()
        if self.day_type == "holiday":
            day_type_indicator.setText("F")  # F pour Férié
            day_type_indicator.setStyleSheet("""
                font-size: 10px;
                font-weight: bold;
                color: #C2185B;
                background-color: transparent;
                border: none;
            """)
        elif self.day_type == "bridge_day":
            day_type_indicator.setText("P")  # P pour Pont
            day_type_indicator.setStyleSheet("""
                font-size: 10px;
                font-weight: bold;
                color: #E65100;
                background-color: transparent;
                border: none;
            """)
            
        header_layout.addWidget(day_type_indicator)
        header_layout.addStretch()
        header_layout.addWidget(day_number)
        
        layout.addWidget(header_widget)
        
        # Séparateur
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("border: none; background-color: #D0D0D0; max-height: 1px;")
        layout.addWidget(separator)
        
        # Zone de contenu pour les modifications
        if self.configs:
            config_area = QScrollArea()
            config_area.setWidgetResizable(True)
            config_area.setStyleSheet("""
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QScrollBar {
                    width: 5px;
                }
            """)
            
            config_container = QWidget()
            config_layout = QVBoxLayout(config_container)
            config_layout.setContentsMargins(0, 0, 0, 0)
            config_layout.setSpacing(1)
            
            # Afficher les différences pour chaque configuration
            for config in self.configs:
                # Calcul des différences avec la configuration de base
                differences = self._get_config_differences(config)
                
                if differences:
                    has_additions = any(diff['new'] - diff['base'] > 0 for diff in differences.values())
                    has_subtractions = any(diff['new'] - diff['base'] < 0 for diff in differences.values())
                    
                    for post_type, diff in differences.items():
                        # Créer un label pour chaque modification
                        value_change = diff['new'] - diff['base']
                        
                        # Choisir la couleur en fonction du changement
                        if value_change > 0:
                            # Bleu pour augmentation
                            bg_color = "#D4E6F1"  # Bleu clair
                            text_color = "#2874A6"  # Bleu plus foncé
                            text = f"{post_type}: +{value_change}"
                        elif value_change < 0:
                            # Rouge pour diminution
                            bg_color = "#F5B7B1"  # Rouge clair
                            text_color = "#A93226"  # Rouge plus foncé
                            text = f"{post_type}: {value_change}"
                        else:
                            continue  # Skip si pas de changement
                        
                        change_label = QLabel(text)
                        change_label.setStyleSheet(f"""
                            background-color: {bg_color};
                            color: {text_color};
                            border-radius: 2px;
                            padding: 2px 4px;
                            font-size: 10px;
                            font-weight: bold;
                            margin: 1px;
                        """)
                        config_layout.addWidget(change_label)
            
            config_layout.addStretch()
            config_area.setWidget(config_container)
            layout.addWidget(config_area)
        
        # Ajouter un espace extensible
        layout.addStretch()
        
    def _get_config_differences(self, config):
        """Récupère les différences pré-calculées pour une configuration"""
        if hasattr(config, 'differences'):
            return config.differences
        
        # Fallback au cas où les différences n'auraient pas été calculées
        result = {}
        for post_type, value in config.post_counts.items():
            result[post_type] = {
                'base': 0,  # Valeur par défaut
                'new': value
            }
        
        return result
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.date_obj)
        super().mousePressEvent(event)


class CalendarView(QDialog):
    """Visualisation du planning sous forme de calendrier"""
    
    def __init__(self, post_configuration, parent=None, start_date=None, end_date=None):
        super().__init__(parent)
        self.post_configuration = post_configuration
        self.start_date = start_date or date.today()
        self.end_date = end_date or (date.today() + timedelta(days=180))
        self.current_month = date.today().month
        self.current_year = date.today().year
        
        # Calendrier français pour les jours fériés
        self.cal_france = France()
        
        # Récupérer les configurations avec les dates
        self.config_dates = self.get_config_dates()
        
        self.setWindowTitle("Visualisation du Planning")
        self.setMinimumSize(900, 700)  # Taille augmentée pour mieux afficher le contenu
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Barre de navigation
        nav_layout = QHBoxLayout()
        
        prev_month_btn = QPushButton("< Mois précédent")
        prev_month_btn.setStyleSheet(ACTION_BUTTON_STYLE)
        prev_month_btn.clicked.connect(self.previous_month)
        
        next_month_btn = QPushButton("Mois suivant >")
        next_month_btn.setStyleSheet(ACTION_BUTTON_STYLE)
        next_month_btn.clicked.connect(self.next_month)
        
        self.month_year_label = QLabel()
        self.month_year_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
        """)
        
        # ComboBox pour le type de configuration avec légende de couleur
        self.config_type_combo = QComboBox()
        self.config_type_combo.setStyleSheet("""
            QComboBox {
                min-height: 30px;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
        """)
        self.config_type_combo.addItem("Tous les types", None)
        self.config_type_combo.addItem("Semaine", "Semaine")
        self.config_type_combo.addItem("Samedi", "Samedi")
        self.config_type_combo.addItem("Dimanche/Férié", "Dimanche/Férié")
        self.config_type_combo.currentIndexChanged.connect(self.update_calendar)
        
        # Légende pour les types de jours
        legend_layout = QHBoxLayout()
        
        # Jour normal
        normal_legend = QLabel("Jour normal")
        normal_indicator = QLabel()
        normal_indicator.setFixedSize(16, 16)
        normal_indicator.setStyleSheet("background-color: #FFFFFF; border: 1px solid #D0D0D0; border-radius: 4px;")
        
        # Samedi
        saturday_legend = QLabel("Samedi")
        saturday_indicator = QLabel()
        saturday_indicator.setFixedSize(16, 16)
        saturday_indicator.setStyleSheet("background-color: #E8EDF5; border: 1px solid #D0D0D0; border-radius: 4px;")
        
        # Dimanche
        sunday_legend = QLabel("Dimanche")
        sunday_indicator = QLabel()
        sunday_indicator.setFixedSize(16, 16)
        sunday_indicator.setStyleSheet("background-color: #F3E5F5; border: 1px solid #D0D0D0; border-radius: 4px;")
        
        # Jour férié
        holiday_legend = QLabel("Férié")
        holiday_indicator = QLabel()
        holiday_indicator.setFixedSize(16, 16)
        holiday_indicator.setStyleSheet("background-color: #FCE4EC; border: 1px solid #D0D0D0; border-radius: 4px;")
        
        # Jour de pont
        bridge_legend = QLabel("Pont")
        bridge_indicator = QLabel()
        bridge_indicator.setFixedSize(16, 16)
        bridge_indicator.setStyleSheet("background-color: #FFF3E0; border: 1px solid #D0D0D0; border-radius: 4px;")
        
        # Ajouter les éléments de légende
        legend_layout.addWidget(normal_indicator)
        legend_layout.addWidget(normal_legend)
        legend_layout.addSpacing(10)
        legend_layout.addWidget(saturday_indicator)
        legend_layout.addWidget(saturday_legend)
        legend_layout.addSpacing(10)
        legend_layout.addWidget(sunday_indicator)
        legend_layout.addWidget(sunday_legend)
        legend_layout.addSpacing(10)
        legend_layout.addWidget(holiday_indicator)
        legend_layout.addWidget(holiday_legend)
        legend_layout.addSpacing(10)
        legend_layout.addWidget(bridge_indicator)
        legend_layout.addWidget(bridge_legend)
        legend_layout.addStretch()
        
        nav_layout.addWidget(prev_month_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.month_year_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self.config_type_combo)
        nav_layout.addWidget(next_month_btn)
        
        main_layout.addLayout(nav_layout)
        
        # Ajouter la légende
        main_layout.addLayout(legend_layout)
        
        # Entêtes des jours de la semaine
        days_layout = QHBoxLayout()
        days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        
        for day in days:
            day_label = QLabel(day)
            day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            day_label.setStyleSheet("""
                font-weight: bold;
                background-color: #F8F9FA;
                padding: 8px;
                border-radius: 4px;
            """)
            days_layout.addWidget(day_label)
        
        main_layout.addLayout(days_layout)
        
        # Zone de défilement pour le calendrier avec adaptativité
        self.calendar_container = QWidget()
        self.calendar_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.calendar_layout = QVBoxLayout(self.calendar_container)
        self.calendar_layout.setSpacing(10)
        
        # Utiliser un scroll area pour permettre le défilement pour les grands mois
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        scroll_area.setWidget(self.calendar_container)
        
        # Ajouter le scroll area au layout principal avec policy d'expansion
        main_layout.addWidget(scroll_area, 1)  # Stretch factor 1 pour qu'il prenne tout l'espace disponible
        
        # Boutons d'action
        action_layout = QHBoxLayout()
        
        add_config_btn = QPushButton("Ajouter une configuration")
        add_config_btn.setStyleSheet(ACTION_BUTTON_STYLE)
        add_config_btn.clicked.connect(self.add_configuration)
        
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.close)
        
        action_layout.addWidget(add_config_btn)
        action_layout.addStretch()
        action_layout.addWidget(close_btn)
        
        main_layout.addLayout(action_layout)
        
        # Définir notre dialogue pour qu'il puisse être redimensionné
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        
        # Initialisation du calendrier
        self.update_calendar()
    
    def get_config_dates(self):
        """Récupère toutes les dates avec des configurations spécifiques"""
        config_dates = {}
        
        if hasattr(self.post_configuration, 'specific_configs'):
            for config in self.post_configuration.specific_configs:
                current_date = config.start_date
                while current_date <= config.end_date:
                    if current_date not in config_dates:
                        config_dates[current_date] = []
                    config_dates[current_date].append(config)
                    current_date += timedelta(days=1)
        
        return config_dates
    
    def update_calendar(self):
        """Met à jour l'affichage du calendrier"""
        # Effacer le calendrier actuel
        while self.calendar_layout.count():
            child = self.calendar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Mise à jour du label mois/année
        month_name = calendar.month_name[self.current_month]
        self.month_year_label.setText(f"{month_name} {self.current_year}")
        
        # Filtrer les configurations par type si nécessaire
        selected_type = self.config_type_combo.currentData()
        
        # Obtenir les configurations filtrées en prenant en compte les jours de pont
        if selected_type:
            filtered_configs = {}
            
            # Pour chaque date dans notre plage
            current_date = date(self.current_year, self.current_month, 1)
            for _ in range(31):  # Maximum 31 jours dans un mois
                if current_date.month != self.current_month:
                    break
                
                # Déterminer le type de jour applicable (en tenant compte des ponts)
                applicable_type = self.get_applicable_config(current_date)
                
                # Si le type sélectionné correspond au type applicable
                if selected_type == applicable_type:
                    # Chercher des configurations spécifiques pour cette date
                    if current_date in self.config_dates:
                        filtered_configs[current_date] = [config for config in self.config_dates[current_date]
                                                        if config.apply_to == selected_type]
                    
                    # Si on n'a pas trouvé de configurations spécifiques mais que c'est un jour de pont
                    # et qu'on a sélectionné "Dimanche/Férié", chercher aussi les configurations génériques
                    elif (self._get_day_type(current_date) == "bridge_day" and 
                        selected_type == "Dimanche/Férié"):
                        # Chercher des configurations génériques pour les jours fériés
                        generic_configs = []
                        for configs in self.config_dates.values():
                            for config in configs:
                                if (config.apply_to == "Dimanche/Férié" and 
                                    config.start_date <= current_date <= config.end_date and
                                    config not in generic_configs):
                                    generic_configs.append(config)
                        
                        if generic_configs:
                            filtered_configs[current_date] = generic_configs
                
                current_date += timedelta(days=1)
        else:
            # Si aucun type n'est sélectionné, montrer toutes les configurations
            filtered_configs = self.config_dates.copy()
        
        # Générer le calendrier
        cal = calendar.monthcalendar(self.current_year, self.current_month)
        
        # Calcul des dates du mois précédent pour compléter la première semaine
        first_day = date(self.current_year, self.current_month, 1)
        first_weekday = first_day.weekday()
        
        prev_month = self.current_month - 1
        prev_year = self.current_year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        
        prev_month_days = calendar.monthrange(prev_year, prev_month)[1]
        
        # Pour chaque mois à afficher (généralement 1, mais peut être étendu)
        for month_offset in range(1):
            target_year = self.current_year
            target_month = self.current_month + month_offset
            
            if target_month > 12:
                target_month -= 12
                target_year += 1
            
            # Créer une grille adaptative pour ce mois
            month_grid = QGridLayout()
            month_grid.setSpacing(8)  # Espacement entre les cellules
            
            # Important: définir les politiques de dimensionnement pour les colonnes et les lignes
            for col in range(7):  # 7 jours par semaine
                month_grid.setColumnStretch(col, 1)  # Chaque colonne a le même poids
            
            cal = calendar.monthcalendar(target_year, target_month)
            
            # Pour chaque semaine du mois
            for week_idx, week in enumerate(cal):
                month_grid.setRowStretch(week_idx, 1)  # Chaque ligne a le même poids
                
                for day_idx, day in enumerate(week):
                    if day == 0:
                        # Jour du mois précédent ou suivant
                        if week_idx == 0:
                            # Mois précédent
                            prev_day = prev_month_days - first_weekday + day_idx + 1
                            cell_date = date(prev_year, prev_month, prev_day)
                            cell_configs = filtered_configs.get(cell_date, [])
                            
                            # Déterminer le type de jour
                            day_type = self._get_day_type(cell_date)
                            
                            cell = CalendarCell(cell_date, 
                                             self._prepare_configs_for_cell(cell_configs), 
                                             False,
                                             day_type)
                        else:
                            # Mois suivant
                            next_month = target_month + 1
                            next_year = target_year
                            if next_month > 12:
                                next_month = 1
                                next_year += 1
                            
                            next_day = day_idx + 1
                            cell_date = date(next_year, next_month, next_day)
                            cell_configs = filtered_configs.get(cell_date, [])
                            
                            # Déterminer le type de jour
                            day_type = self._get_day_type(cell_date)
                            
                            cell = CalendarCell(cell_date, 
                                             self._prepare_configs_for_cell(cell_configs), 
                                             False,
                                             day_type)
                    else:
                        # Jour du mois courant
                        cell_date = date(target_year, target_month, day)
                        cell_configs = filtered_configs.get(cell_date, [])
                        
                        # Déterminer le type de jour
                        day_type = self._get_day_type(cell_date)
                        
                        cell = CalendarCell(cell_date, 
                                         self._prepare_configs_for_cell(cell_configs), 
                                         True,
                                         day_type)
                    
                    cell.clicked.connect(self.on_date_clicked)
                    month_grid.addWidget(cell, week_idx, day_idx)
            
            # Ajouter la grille dans un widget conteneur
            month_container = QWidget()
            month_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            month_container.setLayout(month_grid)
            self.calendar_layout.addWidget(month_container, 1)  # Stretch factor 1
        
        # Ajouter un stretch à la fin pour que le calendrier reste en haut si l'espace est grand
        self.calendar_layout.addStretch()
    
    def on_date_clicked(self, date_obj):
        """Gère le clic sur une date du calendrier avec identification améliorée du type de jour"""
        # Déterminer le type de jour applicable
        applicable_type = self.get_applicable_config(date_obj)
        
        # Si c'est un jour de pont et qu'il n'a pas déjà une configuration spécifique
        if self._get_day_type(date_obj) == "bridge_day" and date_obj not in self.config_dates:
            # Demander à l'utilisateur quelle action effectuer
            msgbox = QMessageBox(self)
            msgbox.setWindowTitle("Jour de pont")
            msgbox.setText(f"Le {date_obj.strftime('%d/%m/%Y')} est un jour de pont.")
            msgbox.setInformativeText("Ce jour utilise par défaut la configuration 'Dimanche/Férié'. Que souhaitez-vous faire ?")
            
            btn_specific = msgbox.addButton("Configurer spécifiquement", QMessageBox.ButtonRole.ActionRole)
            btn_cancel = msgbox.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
            
            msgbox.exec()
            
            if msgbox.clickedButton() == btn_specific:
                self.add_configuration(date_obj)
            return
        
        # Comportement normal pour les autres jours
        if date_obj in self.config_dates:
            self.show_date_configs(date_obj)
        else:
            self.add_configuration(date_obj)

    def show_date_configs(self, date_obj):
        """Affiche les configurations pour une date spécifique avec préréglage du type de jour"""
        from .post_configuration import SpecificConfigDialog
        
        configs = self.config_dates.get(date_obj, [])
        if configs:
            # Pour simplifier, on prend la première configuration
            # On pourrait améliorer pour montrer toutes les configurations
            config = configs[0]
            
            # Déterminer le type applicable pour cette date
            applicable_type = self.get_applicable_config(date_obj)
            
            # Si c'est un jour de pont sans configuration spécifique, créer une nouvelle configuration de type Dimanche/Férié
            if self._get_day_type(date_obj) == "bridge_day" and not config.post_counts:
                # Créer une configuration avec les valeurs par défaut de Dimanche/Férié
                if applicable_type == "Dimanche/Férié":
                    default_config = self.post_configuration.sunday_holiday
                else:
                    default_config = getattr(self.post_configuration, applicable_type.lower(), {})
                
                # Récupérer les configurations par défaut pour les différents types de jours
                dialog = SpecificConfigDialog(
                    self,
                    date_obj,
                    date_obj,  # Même date pour début et fin
                    self.post_configuration.weekday,
                    self.post_configuration.saturday,
                    self.post_configuration.sunday_holiday,
                    existing_config=None  # Pas de configuration existante
                )
                
                # Prérégler le type de jour à Dimanche/Férié
                dialog.day_type_group.button(3).setChecked(True)
                dialog.update_table()
                
            else:
                # Récupérer les configurations par défaut pour les différents types de jours
                dialog = SpecificConfigDialog(
                    self,
                    config.start_date,
                    config.end_date,
                    self.post_configuration.weekday,
                    self.post_configuration.saturday,
                    self.post_configuration.sunday_holiday,
                    existing_config=config
                )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Mettre à jour la configuration
                result = dialog.result
                if result:
                    # Supprimer l'ancienne configuration
                    for config in configs:
                        self.post_configuration.specific_configs.remove(config)
                    
                    # Ajouter la nouvelle configuration
                    self.post_configuration.specific_configs.append(result)
                    
                    # Mettre à jour les dates de configuration
                    self.config_dates = self.get_config_dates()
                    
                    # Mettre à jour le calendrier
                    self.update_calendar()

    def add_configuration(self, date_obj=None):
        """Ajoute une nouvelle configuration pour une date avec présélection améliorée"""
        from .post_configuration import AddConfigDialog
        
        # Si une date est fournie, déterminer son type
        selected_day_type = None
        if date_obj:
            selected_day_type = self.get_applicable_config(date_obj)
        
        dialog = AddConfigDialog(self, self.post_configuration, edit_date=date_obj)
        
        # Si une date est fournie, la présélectionner dans le calendrier
        if date_obj:
            dialog.calendar.selected_dates.add(date_obj)
            dialog.calendar.updateCells()
            dialog.update_selection_count()
            
            # Présélectionner le type de jour correct
            if selected_day_type:
                index = dialog.day_type_combo.findText(selected_day_type)
                if index >= 0:
                    dialog.day_type_combo.setCurrentIndex(index)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Ajouter les nouvelles configurations
            for new_config in dialog.config_results:
                self.post_configuration.add_specific_config(new_config)
            
            # Mettre à jour les dates de configuration
            self.config_dates = self.get_config_dates()
            
            # Mettre à jour le calendrier
            self.update_calendar()

    def _prepare_configs_for_cell(self, configs):
        """Prépare les configurations pour une cellule du calendrier"""
        if not configs:
            return []
            
        for config in configs:
            # Calculer les différences pour chaque configuration
            day_type = config.apply_to
            
            # Sélectionner la configuration de base appropriée
            if day_type == "Semaine":
                base_config = self.post_configuration.weekday
            elif day_type == "Samedi":
                base_config = self.post_configuration.saturday
            else:  # Dimanche/Férié
                base_config = self.post_configuration.sunday_holiday
                
            # Ajouter les différences à la configuration
            config.differences = {}
            
            # Parcourir tous les types de postes dans la configuration spécifique
            for post_type, value in config.post_counts.items():
                # Obtenir la valeur de base
                base_value = base_config.get(post_type, None)
                base_total = 0 if base_value is None else base_value.total
                
                # Calculer la différence
                diff = value - base_total
                
                # Si différence non nulle, l'ajouter
                if diff != 0:
                    config.differences[post_type] = {
                        'base': base_total,
                        'new': value,
                        'diff': diff
                    }
        
        return configs
        
    def _get_config_differences(self, config, date_obj=None):
        """Calcule les différences entre une configuration spécifique et la configuration de base"""
        differences = {}
        
        # Sélectionner la configuration de base appropriée
        if config.apply_to == "Semaine":
            base_config = self.post_configuration.weekday
        elif config.apply_to == "Samedi":
            base_config = self.post_configuration.saturday
        else:  # Dimanche/Férié
            base_config = self.post_configuration.sunday_holiday
        
        # Calculer les différences pour chaque type de poste
        for post_type, value in config.post_counts.items():
            base_value = base_config.get(post_type, None)
            base_total = 0 if base_value is None else base_value.total
            
            # Ajouter la différence si elle existe
            if value != base_total:
                differences[post_type] = {
                    'base': base_total,
                    'new': value
                }
        
        return differences
    
    def previous_month(self):
        """Passe au mois précédent"""
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.update_calendar()
    
    def _get_day_type(self, date_obj):
        """Détermine le type de jour (normal, férié, pont)"""
        # Vérifier si c'est un jour férié
        if self.cal_france.is_holiday(date_obj):
            return "holiday"
        
        # Vérifier si c'est un jour de pont
        if DayType.is_bridge_day(date_obj, self.cal_france):
            return "bridge_day"
        
        # Jour normal
        return "normal"
        
    def get_applicable_config(self, date_obj):
        """
        Détermine quelle configuration est applicable à une date donnée.
        Prend en compte les jours de pont qui doivent utiliser la configuration Dimanche/Férié.
        """
        day_type = self._get_day_type(date_obj)
        
        # Si c'est un jour férié ou un jour de pont, utiliser la configuration Dimanche/Férié
        if day_type in ["holiday", "bridge_day"]:
            return "Dimanche/Férié"
        # Si c'est un samedi
        elif date_obj.weekday() == 5:  # 5 = samedi
            return "Samedi"
        # Si c'est un dimanche
        elif date_obj.weekday() == 6:  # 6 = dimanche
            return "Dimanche/Férié"
        # Sinon c'est un jour de semaine normal
        else:
            return "Semaine"
            
    def next_month(self):
        """Passe au mois suivant"""
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.update_calendar()