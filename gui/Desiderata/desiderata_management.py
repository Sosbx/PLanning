# © 2024 HILAL Arkane. Tous droits réservés.
# gui/desiderata_management.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QGridLayout, QAbstractScrollArea,
                             QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QLabel, QDateEdit, QMessageBox,
                             QSplitter, QHeaderView,QDialog,QFileDialog)
from PyQt6.QtCore import Qt, QDate, QEvent, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from core.Constantes.models import Desiderata, Doctor, CAT
from datetime import date, timedelta
from workalendar.europe import France
from PyQt6.QtWidgets import QFileDialog
from datetime import datetime
import csv
import os
import logging
from gui.components.planning_table_component import PlanningTableComponent
import codecs
from gui.styles import color_system, ACTION_BUTTON_STYLE, ADD_BUTTON_STYLE, EDIT_DELETE_BUTTON_STYLE, GLOBAL_STYLE, DESIDERATA_TABLE_STYLE, PlatformHelper


logger = logging.getLogger(__name__)

class DesiderataCalendarWidget(PlanningTableComponent):
    """
    Widget de calendrier pour la gestion des desiderata, héritant du composant
    PlanningTableComponent pour une cohérence visuelle avec le reste de l'application.
    """
    def __init__(self, start_date, end_date):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.cal = France()
        self.selections = {}
        self.is_selecting = False
        self.current_selection_priority = None
        self.is_deselecting = False  # Mode pour la désélection
        self.init_desiderata_ui()
        
    def init_desiderata_ui(self):
        """Initialise l'interface utilisateur spécifique aux desiderata"""
        # Configurer les en-têtes et propriétés de base du tableau
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        
        # Configurer les dimensions et styles
        self.setStyleSheet(DESIDERATA_TABLE_STYLE)
        
        # Préparer le tableau et configurer les dates
        self.setup_planning_dates(self.start_date, self.end_date)
        
        # Initialiser les couleurs du calendrier pour les desiderata
        self.desiderata_colors = {
            'base': {
                'normal': color_system.colors['weekday'],
                'weekend': color_system.colors['weekend']
            },
            'primary': {
                'normal': color_system.colors['desiderata']['primary']['normal'],
                'weekend': color_system.colors['desiderata']['primary']['weekend']
            },
            'secondary': {
                'normal': color_system.colors['desiderata']['secondary']['normal'],
                'weekend': color_system.colors['desiderata']['secondary']['weekend']
            }
        }
        self.set_colors(self.desiderata_colors)
        
        # Remplir le calendrier avec les jours
        self.populate_days()
        
        # Connecter les événements
        self.cellPressed.connect(self.on_cell_pressed)
        self.cellEntered.connect(self.on_cell_entered)
        self.setMouseTracking(True)
        self.viewport().installEventFilter(self)
        
    def update_dates(self, start_date, end_date):
        """Met à jour les dates du calendrier et préserve les sélections"""
        self.store_selections()  # Stocker les sélections avant de mettre à jour
        self.start_date = start_date
        self.end_date = end_date
        
        # Sauvegarder le nombre de lignes actuel pour détecter si une nouvelle ligne a été ajoutée
        old_row_count = self.rowCount()
        
        # Mettre à jour les dates et le tableau
        self.setup_planning_dates(start_date, end_date)
        self.populate_days()
        
        # Vérifier si une nouvelle ligne a été ajoutée et l'enlever si nécessaire
        if self.rowCount() > old_row_count + 1:  # +1 car on s'attend à ce que setup_planning_dates ajoute une ligne
            self.removeRow(1)  # Supprimer la ligne en trop (la deuxième ligne, car la première est l'en-tête des mois)
            
        self.restore_selections()
        
    def store_selections(self):
        """Stocke les sélections actuelles avant une mise à jour"""
        self.selections.clear()
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if not item:
                    continue
                    
                data = item.data(Qt.ItemDataRole.UserRole)
                if not data or not isinstance(data, dict):
                    continue
                    
                date_val = data.get("date")
                period = data.get("period")
                if not date_val or not period or period < 1 or period > 3:
                    continue
                    
                priority = self.get_cell_priority(item)
                if priority:  # Si la cellule a une priorité (primary ou secondary)
                    self.selections[(date_val, period)] = priority
        
    def restore_selections(self):
        """Restaure les sélections après une mise à jour du calendrier"""
        for (date_val, period), priority in self.selections.items():
            if self.start_date <= date_val <= self.end_date and 1 <= period <= 3:
                self.update_cell(
                    date_val, 
                    period, 
                    "", 
                    self.desiderata_colors[priority]['weekend' if self._is_special_day(date_val) else 'normal']
                )
                
    def _is_special_day(self, day_date):
        """Vérifie si le jour est un week-end, un jour férié ou un pont"""
        return (day_date.weekday() >= 5 or 
                self.cal.is_holiday(day_date) or 
                self.is_bridge_day(day_date))
        
    def get_cell_priority(self, item):
        """Détermine la priorité d'une cellule selon sa couleur"""
        if not item:
            return None
            
        background = item.background().color()
        
        # Comparer avec les couleurs définies
        for priority in ['primary', 'secondary']:
            for context in ['normal', 'weekend']:
                if background == self.desiderata_colors[priority][context]:
                    return priority
        return None
        
    def toggle_cell(self, item, force_select=False, priority="primary"):
        """
        Bascule l'état d'une cellule avec la couleur appropriée selon la priorité
        
        Args:
            item: L'élément de cellule à modifier
            force_select: Force la sélection indépendamment de l'état actuel
            priority: La priorité ('primary' ou 'secondary')
        """
        if not item:
            return
            
        # Récupérer les informations de la cellule
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
            
        date_val = data.get("date")
        period = data.get("period")
        if not date_val or not period or period < 1 or period > 3:
            return
            
        is_special_day = self._is_special_day(date_val)
        current_priority = self.get_cell_priority(item)
        
        # Déterminer la nouvelle couleur
        if force_select:
            # Forcer la sélection (utilisé lors du chargement des desiderata)
            new_color = self.desiderata_colors[priority]['weekend' if is_special_day else 'normal']
        elif self.is_selecting:
            if self.is_deselecting:
                # Mode désélection : retourner à la couleur de base
                new_color = self.desiderata_colors['base']['weekend' if is_special_day else 'normal']
            else:
                # Mode sélection : appliquer la nouvelle couleur
                new_color = self.desiderata_colors[priority]['weekend' if is_special_day else 'normal']
        else:
            # Clic simple : inverser l'état
            if current_priority == priority:
                # Retourner à la couleur de base
                new_color = self.desiderata_colors['base']['weekend' if is_special_day else 'normal']
            else:
                # Appliquer la nouvelle couleur
                new_color = self.desiderata_colors[priority]['weekend' if is_special_day else 'normal']
        
        # Mettre à jour la cellule
        PlatformHelper.apply_background_color(item, new_color)
        
    def mousePressEvent(self, event):
        """Gestion des clics de souris pour les deux types de desiderata"""
        item = self.itemAt(event.pos())
        if not item:
            super().mousePressEvent(event)
            return

        # Vérifier si c'est une cellule de période
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            super().mousePressEvent(event)
            return
            
        period = data.get("period")
        if not period or period < 1 or period > 3:
            super().mousePressEvent(event)
            return

        self.is_selecting = True
        self.current_selection_priority = None
        
        # Détermine la priorité selon le bouton de souris
        if event.button() == Qt.MouseButton.LeftButton:
            self.current_selection_priority = "primary"
        elif event.button() == Qt.MouseButton.RightButton:
            self.current_selection_priority = "secondary"
            event.accept()
        else:
            super().mousePressEvent(event)
            return

        # Vérifie si on doit passer en mode désélection
        current_priority = self.get_cell_priority(item)
        self.is_deselecting = (current_priority == self.current_selection_priority)

        # Appliquer la sélection
        self.toggle_cell(item, priority=self.current_selection_priority)
        
    def mouseMoveEvent(self, event):
        """Gestion du glissement avec maintien du mode (sélection ou désélection)"""
        if not self.is_selecting:
            super().mouseMoveEvent(event)
            return

        item = self.itemAt(event.pos())
        if not item:
            return
            
        # Vérifier si c'est une cellule de période
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
            
        period = data.get("period")
        if not period or period < 1 or period > 3:
            return
            
        self.toggle_cell(item, priority=self.current_selection_priority)
        
    def mouseReleaseEvent(self, event):
        """Réinitialisation des états de sélection"""
        self.is_selecting = False
        self.current_selection_priority = None
        self.is_deselecting = False
        super().mouseReleaseEvent(event)
        
    def get_selected_desiderata(self):
        """Retourne les desiderata sélectionnés avec leur priorité"""
        desiderata = []
        
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if not item:
                    continue
                    
                priority = self.get_cell_priority(item)
                if not priority:
                    continue
                    
                data = item.data(Qt.ItemDataRole.UserRole)
                if not data or not isinstance(data, dict):
                    continue
                    
                date_val = data.get("date")
                period = data.get("period")
                if date_val and period and 1 <= period <= 3:
                    desiderata.append((date_val, period, priority))
                    
        return desiderata
        
    def set_desiderata(self, desiderata):
        """Configure les desiderata avec rétrocompatibilité pour l'ancien format"""
        # Réinitialiser le tableau
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if not item:
                    continue
                    
                data = item.data(Qt.ItemDataRole.UserRole)
                if not data or not isinstance(data, dict):
                    continue
                    
                date_val = data.get("date")
                period = data.get("period")
                
                if date_val and period and 1 <= period <= 3:
                    is_special_day = self._is_special_day(date_val)
                    base_color = self.desiderata_colors['base']['weekend' if is_special_day else 'normal']
                    PlatformHelper.apply_background_color(item, base_color)
        
        # Appliquer les desiderata
        for d in desiderata:
            # Vérification du type de l'objet Desiderata
            if isinstance(d, Desiderata):
                date_val = d.start_date
                period = d.period
                priority = getattr(d, 'priority', 'primary')
            elif isinstance(d, tuple):
                if len(d) == 2:  # Ancien format
                    date_val, period = d
                    priority = 'primary'
                elif len(d) == 3:  # Nouveau format
                    date_val, period, priority = d
                else:
                    continue
            else:
                continue

            if self.start_date <= date_val <= self.end_date and 1 <= period <= 3:
                # Appliquer directement la couleur à la cellule appropriée
                is_special_day = self._is_special_day(date_val)
                color = self.desiderata_colors[priority]['weekend' if is_special_day else 'normal']
                self.update_cell(date_val, period, "", color)
        
    def on_cell_pressed(self, row, col):
        """Gestion du clic sur une cellule"""
        item = self.item(row, col)
        if not item:
            return
            
        # Vérifier si c'est une cellule de période
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
            
        period = data.get("period")
        if not period or period < 1 or period > 3:
            return
            
        self.is_selecting = True
        current_priority = self.get_cell_priority(item)
        self.is_deselecting = (current_priority == "primary")  # Par défaut, desélection pour le clic gauche
        self.toggle_cell(item)
        
    def on_cell_entered(self, row, col):
        """Gestion du survol de cellule lorsque le bouton est maintenu"""
        if not self.is_selecting:
            return
            
        item = self.item(row, col)
        if not item:
            return
            
        # Vérifier si c'est une cellule de période
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
            
        period = data.get("period")
        if not period or period < 1 or period > 3:
            return
            
        self.toggle_cell(item, priority=self.current_selection_priority)
        
    def eventFilter(self, obj, event):
        """Filtre d'événements pour gérer le relâchement du bouton de souris"""
        if obj == self.viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            self.is_selecting = False
            self.current_selection_priority = None
            self.is_deselecting = False
        return super().eventFilter(obj, event)
        
    def clear_all_selections(self):
        """Réinitialise toutes les cellules à leur couleur de base"""
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if not item:
                    continue
                    
                data = item.data(Qt.ItemDataRole.UserRole)
                if not data or not isinstance(data, dict):
                    continue
                    
                date_val = data.get("date")
                
                if date_val:
                    is_special_day = self._is_special_day(date_val)
                    base_color = self.desiderata_colors['base']['weekend' if is_special_day else 'normal']
                    PlatformHelper.apply_background_color(item, base_color)

    def is_bridge_day(self, date):
        """Détermine si un jour est un pont"""
        # 1) Lundi avant un mardi férié
        if date.weekday() == 0 and self.cal.is_holiday(date + timedelta(days=1)):
            return True
        
        # 2) Vendredi et samedi après un jeudi férié
        if date.weekday() in [4, 5] and self.cal.is_holiday(date - timedelta(days=1 if date.weekday() == 4 else 2)):
            return True
        
        # 3) Samedi après un vendredi férié
        if date.weekday() == 5 and self.cal.is_holiday(date - timedelta(days=1)):
            return True
        
        # 4) Jour de semaine entre deux jours fériés
        if 0 <= date.weekday() <= 4:  # Jours de semaine (lundi à vendredi)
            if (self.cal.is_holiday(date - timedelta(days=1)) and 
                self.cal.is_holiday(date + timedelta(days=1))):
                return True
        
        return False

 

    
class DesiderataManagementWidget(QWidget):
    """
    Widget de gestion des desiderata utilisant la nouvelle implémentation 
    basée sur PlanningTableComponent
    """
    desiderata_updated = pyqtSignal()  # Signal pour les mises à jour de desiderata
    
    def __init__(self, doctors, cats, planning_start_date, planning_end_date, main_window):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.planning_start_date = planning_start_date
        self.planning_end_date = planning_end_date
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def detect_file_encoding(self, file_path):
        """
        Détecte l'encodage d'un fichier CSV.
        
        Args:
            file_path (str): Chemin du fichier à analyser
            
        Returns:
            str: Encodage détecté ('utf-8-sig' ou 'utf-8')
        """
        try:
            with open(file_path, 'rb') as f:
                raw = f.read(4)
                if raw.startswith(b'\xef\xbb\xbf'):
                    self.logger.debug("Encodage détecté: UTF-8 avec BOM")
                    return 'utf-8-sig'
                elif raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                    self.logger.debug("Encodage détecté: UTF-16")
                    return 'utf-16'
                else:
                    try:
                        raw.decode('utf-8')
                        self.logger.debug("Encodage détecté: UTF-8 sans BOM")
                        return 'utf-8'
                    except UnicodeDecodeError:
                        self.logger.warning("Encodage non détecté, utilisation UTF-8 par défaut")
                        return 'utf-8'
        except Exception as e:
            self.logger.error(f"Erreur lors de la détection de l'encodage: {str(e)}")
            return 'utf-8'

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # Modifier les champs de date pour utiliser un calendrier
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.start_date.setDate(QDate(self.planning_start_date))
        self.end_date.setDate(QDate(self.planning_end_date))

        self.apply_dates_button = QPushButton("Appliquer les dates")
        self.apply_dates_button.clicked.connect(self.apply_dates)
        self.apply_dates_button.setStyleSheet(ACTION_BUTTON_STYLE)

        date_layout.addWidget(QLabel("Date de début:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("Date de fin:"))
        date_layout.addWidget(self.end_date)
        date_layout.addWidget(self.apply_dates_button)

        self.layout.addLayout(date_layout)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.person_selector = QComboBox()
        self.update_person_selector()
        self.person_selector.currentIndexChanged.connect(self.update_calendar)
        self.person_selector.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.person_selector.installEventFilter(self)
        left_layout.addWidget(self.person_selector)

        # Utiliser le nouveau calendrier basé sur PlanningTableComponent
        self.calendar_widget = DesiderataCalendarWidget(self.planning_start_date, self.planning_end_date)
        self.calendar_widget.setMinimumSize(800, 600)
        left_layout.addWidget(self.calendar_widget)

        # Création du layout des boutons
        button_layout = QHBoxLayout()
        
        # Bouton de sauvegarde
        save_button = QPushButton("Enregistrer les desiderata")
        save_button.clicked.connect(self.save_desiderata)
        save_button.setStyleSheet(ADD_BUTTON_STYLE)
        button_layout.addWidget(save_button)

        # Bouton de réinitialisation
        reset_button = QPushButton("Réinitialiser les desiderata")
        reset_button.clicked.connect(self.reset_desiderata)
        reset_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        button_layout.addWidget(reset_button)

        # Bouton de réinitialisation globale
        reset_all_button = QPushButton("Réinitialiser tous les desiderata")
        reset_all_button.clicked.connect(self.reset_all_desiderata)
        reset_all_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        button_layout.addWidget(reset_all_button)

        # Ajout du bouton d'import CSV
        import_button = QPushButton("Importer depuis CSV")
        import_button.clicked.connect(self.import_multiple_desiderata)
        import_button.setStyleSheet(ACTION_BUTTON_STYLE)
        button_layout.addWidget(import_button)

        left_layout.addLayout(button_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.stats_label = QLabel("Statistiques d'indisponibilité:")
        right_layout.addWidget(self.stats_label)
        
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(4)
        self.stats_table.setHorizontalHeaderLabels([
            "Médecin/CAT",
            "% Total",
            "% Primaire",
            "% Secondaire"
        ])
        right_layout.addWidget(self.stats_table)
        
        # Ajouter le bouton des périodes critiques
        self.show_critical_periods_button = QPushButton("Afficher les périodes critiques")
        self.show_critical_periods_button.clicked.connect(self.show_critical_periods)
        self.show_critical_periods_button.setStyleSheet(ACTION_BUTTON_STYLE)
        right_layout.addWidget(self.show_critical_periods_button)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([int(self.width() * 0.7), int(self.width() * 0.3)])

        self.layout.addWidget(splitter)

        self.update_stats()
        self.update_calendar()
        
    def apply_dates(self):
        new_start_date = self.start_date.date().toPyDate()
        new_end_date = self.end_date.date().toPyDate()
        
        if new_start_date > new_end_date:
            QMessageBox.warning(self, "Erreur", "La date de début doit être antérieure à la date de fin.")
            return

        self.planning_start_date = new_start_date
        self.planning_end_date = new_end_date
        
        self.calendar_widget.update_dates(new_start_date, new_end_date)
        
        # Mettre à jour les dates dans le planning principal
        self.main_window.planning_tab.start_date.setDate(QDate(new_start_date))
        self.main_window.planning_tab.end_date.setDate(QDate(new_end_date))
        
        self.update_stats()
        self.update_calendar()
        
        QMessageBox.information(self, "Succès", "Les dates ont été appliquées avec succès.")

    def sync_dates_from_planning(self, start_date, end_date):
        self.start_date.setDate(QDate(start_date))
        self.end_date.setDate(QDate(end_date))
        self.planning_start_date = start_date
        self.planning_end_date = end_date
        self.calendar_widget.update_dates(start_date, end_date)
        self.update_stats()
        self.update_calendar()

    # Méthode pour afficher la fenêtre des périodes critiques
    def show_critical_periods(self):
        self.critical_periods_window = CriticalPeriodsWindow(
            self.doctors,
            self.cats,
            self.planning_start_date,
            self.planning_end_date,
            self
        )
        self.critical_periods_window.show()
            
    def update_person_selector(self):
        self.person_selector.clear()
        sorted_doctors = sorted(self.doctors, key=lambda x: x.name.lower())
        sorted_cats = sorted(self.cats, key=lambda x: x.name.lower())
        
        for doctor in sorted_doctors:
            self.person_selector.addItem(doctor.name)
        
        if sorted_cats:
            self.person_selector.insertSeparator(len(sorted_doctors))
        
        for cat in sorted_cats:
            self.person_selector.addItem(cat.name)
            
    def update_calendar(self):
        """Met à jour le calendrier avec les desiderata de la personne sélectionnée"""
        selected_name = self.person_selector.currentText()
        person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
        if person:
            # Convertir les desiderata en tuples avec priorité
            desiderata_tuples = [
                (d.start_date, d.period, getattr(d, 'priority', 'primary'))
                for d in person.desiderata
            ]
            self.calendar_widget.set_desiderata(desiderata_tuples)
        else:
            self.calendar_widget.clear_all_selections()
    
    def eventFilter(self, obj, event):
        if obj == self.person_selector and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                index = self.person_selector.currentIndex()
                if index > 0:
                    self.person_selector.setCurrentIndex(index - 1)
                return True
            elif key == Qt.Key.Key_Down:
                index = self.person_selector.currentIndex()
                if index < self.person_selector.count() - 1:
                    self.person_selector.setCurrentIndex(index + 1)
                return True
        return super().eventFilter(obj, event)

    def save_desiderata(self):
        """Sauvegarde les desiderata avec leur priorité"""
        selected_name = self.person_selector.currentText()
        person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
        if person:
            new_desiderata = self.calendar_widget.get_selected_desiderata()
            person.desiderata = [
                Desiderata(date, date, "Indisponibilité", period, priority) 
                for date, period, priority in new_desiderata
            ]
            self.logger.info(f"Sauvegarde desiderata pour {person.name}")
            for d in person.desiderata:
                self.logger.debug(f"  - Date: {d.start_date}, Période: {d.period}, Priorité: {d.priority}")
            
            self.update_stats()
            self.main_window.save_data()
            self.desiderata_updated.emit()  # Emit signal after successful save
            QMessageBox.information(self, "Succès", f"Les desiderata de {person.name} ont été enregistrés avec succès.")
            
    def reset_desiderata(self):
        selected_name = self.person_selector.currentText()
        person = next((p for p in self.doctors + self.cats if p.name == selected_name), None)
        if person:
            confirm = QMessageBox.question(self, "Confirmation", 
                                           f"Êtes-vous sûr de vouloir réinitialiser les desiderata de {person.name} ?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                person.desiderata = []
                self.calendar_widget.clear_all_selections()
                self.update_stats()
                QMessageBox.information(self, "Succès", f"Les desiderata de {person.name} ont été réinitialisés.")

    def reset_all_desiderata(self):
        confirm = QMessageBox.question(self, "Confirmation", 
                                       "Êtes-vous sûr de vouloir réinitialiser tous les desiderata pour tous les médecins et CAT ?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            for person in self.doctors + self.cats:
                person.desiderata = []
            self.calendar_widget.clear_all_selections()
            self.update_stats()
            self.update_calendar()
            QMessageBox.information(self, "Succès", "Tous les desiderata ont été réinitialisés.")
    
    def update_stats(self):
        """
        Met à jour les statistiques d'indisponibilité pour chaque personne.
        Gère les cas où il n'y a pas de période ou de planning disponible.
        """
        self.stats_table.setRowCount(0)
        
        try:
            # Vérifier que les dates sont valides
            if not (self.planning_start_date and self.planning_end_date):
                logger.warning("Dates de planning non définies")
                return
                
            total_days = max(1, (self.planning_end_date - self.planning_start_date).days + 1)
            stats = []

            # Parcourir chaque personne (médecins et CAT)
            for person in self.doctors + self.cats:
                # Initialiser les compteurs pour chaque type de desiderata
                primary_periods = 0
                secondary_periods = 0
                
                # Compter les périodes d'indisponibilité par type
                for des in person.desiderata:
                    if des.type == "Indisponibilité":
                        # Compter uniquement les jours dans la période du planning
                        start = max(des.start_date, self.planning_start_date)
                        end = min(des.end_date, self.planning_end_date)
                        if start <= end:  # Vérifier que la période est valide
                            if getattr(des, 'priority', 'primary') == 'primary':
                                primary_periods += 1
                            else:
                                secondary_periods += 1

                # Calculer le nombre total de périodes possibles (3 périodes par jour)
                total_periods = max(1, total_days * 3)
                
                # Calculer les pourcentages
                primary_percentage = (primary_periods / total_periods) * 100
                secondary_percentage = (secondary_periods / total_periods) * 100
                total_percentage = ((primary_periods + secondary_periods) / total_periods) * 100
                
                # Initialiser le pourcentage de postes non attribués
                unassigned_percentage = 0
                
                # Vérifier si le planning est disponible
                planning = None
                if (hasattr(self.main_window, 'planning_tab') and 
                    hasattr(self.main_window.planning_tab, 'planning_generator')):
                    planning = getattr(self.main_window.planning_tab.planning_generator, 'planning', None)

                if planning is not None:
                    # Calculer le pourcentage de postes non attribués
                    unassigned_shifts = self.main_window.planning_tab.planning_generator.analyze_unassigned_shifts(planning)
                    target_distribution = getattr(
                        self.main_window.planning_tab.planning_generator,
                        'target_distribution',
                        {}
                    )

                    if person.name in target_distribution:
                        expected_shifts = sum(
                            target_distribution[person.name][day_type][post_type] 
                            for day_type in target_distribution[person.name] 
                            for post_type in target_distribution[person.name][day_type]
                        )
                        if expected_shifts > 0:
                            unassigned_total = sum(unassigned_shifts.get(person.name, {}).values())
                            unassigned_percentage = (unassigned_total / expected_shifts) * 100

                # Ajouter les statistiques à la liste
                stats.append((person.name, total_percentage, primary_percentage, secondary_percentage, unassigned_percentage))

            # Trier par pourcentage total d'indisponibilité décroissant
            stats.sort(key=lambda x: x[1], reverse=True)

            # Remplir le tableau des statistiques
            for row, (name, total_pct, primary_pct, secondary_pct, unassigned_pct) in enumerate(stats):
                self.stats_table.insertRow(row)
                
                # Ajouter le nom avec style selon le type de personne
                name_item = QTableWidgetItem(name)
                if any(cat.name == name for cat in self.cats):
                    PlatformHelper.apply_background_color(name_item, QColor(200, 255, 200))  # Vert clair pour les CAT
                elif any(doc.name == name and doc.half_parts == 1 for doc in self.doctors):
                    PlatformHelper.apply_background_color(name_item, QColor(255, 255, 200))  # Jaune clair pour les mi-temps
                self.stats_table.setItem(row, 0, name_item)
                
                # Ajouter le pourcentage total avec fond rouge
                total_item = QTableWidgetItem(f"{total_pct:.2f}%")
                PlatformHelper.apply_background_color(total_item, QColor(255, 200, 200))  # Fond rouge clair
                self.stats_table.setItem(row, 1, total_item)
                
                # Ajouter le pourcentage primaire en rouge sur fond blanc
                primary_item = QTableWidgetItem(f"{primary_pct:.2f}%")
                PlatformHelper.apply_foreground_color(primary_item, QColor(255, 0, 0))  # Texte rouge
                self.stats_table.setItem(row, 2, primary_item)
                
                # Ajouter le pourcentage secondaire en bleu sur fond blanc
                secondary_item = QTableWidgetItem(f"{secondary_pct:.2f}%")
                PlatformHelper.apply_foreground_color(secondary_item, QColor(0, 0, 255))  # Texte bleu
                self.stats_table.setItem(row, 3, secondary_item)

            # Mettre à jour les en-têtes et ajuster les colonnes
            self.stats_table.setHorizontalHeaderLabels([
                "Nom", "% Total", "% Primaire", "% Secondaire"
            ])
            self.stats_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des statistiques: {str(e)}", exc_info=True)
            # Afficher un message d'erreur à l'utilisateur
            QMessageBox.warning(
                self,
                "Erreur de mise à jour",
                "Une erreur est survenue lors de la mise à jour des statistiques."
            )
    
    def import_multiple_desiderata(self):
        """
        Gère l'import de plusieurs fichiers CSV de desiderata simultanément.
        """
        try:
            # Ouvrir le dialogue de sélection multiple de fichiers
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Sélectionner les fichiers CSV des desiderata",
                "",
                "Fichiers CSV (*.csv)"
            )
            
            if not file_paths:
                return
                
            # Variables pour le suivi global
            global_stats = {
                'files_processed': 0,
                'files_with_errors': 0,
                'total_rows': 0,
                'successful_imports': 0,
                'people_updated': set()
            }
            
            # Dictionnaire pour stocker tous les desiderata temporaires
            all_temp_desiderata = {}
            all_errors = {}

            # Traiter chaque fichier
            for file_path in file_paths:
                try:
                    self.logger.info(f"Traitement du fichier: {file_path}")
                    
                    # Détecter l'encodage et le séparateur
                    encoding = self.detect_file_encoding(file_path)
                    with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                        sample = f.read(1024)
                        try:
                            dialect = csv.Sniffer().sniff(sample)
                            separator = dialect.delimiter
                        except csv.Error:
                            separator = ';' if ';' in sample else ','
                    
                    # Lecture du fichier
                    file_errors = []
                    temp_desiderata = {}
                    row_count = 0
                    
                    with open(file_path, 'r', encoding=encoding) as csvfile:
                        reader = csv.DictReader(csvfile, delimiter=separator)
                        
                        # Vérifier les colonnes
                        headers = {h.lower().strip() for h in reader.fieldnames} if reader.fieldnames else set()
                        required_columns = {'nom', 'date', 'periode', 'priorite'}
                        
                        if not required_columns.issubset(headers):
                            missing = required_columns - headers
                            raise ValueError(f"Colonnes manquantes: {', '.join(missing)}")
                        
                        # Traiter les lignes
                        for row in reader:
                            row_count += 1
                            try:
                                # Nettoyer les données
                                cleaned_row = {k.lower().strip(): v.strip() for k, v in row.items()}
                                
                                # Validation du nom
                                name = cleaned_row['nom']
                                person = next(
                                    (p for p in self.doctors + self.cats if p.name == name),
                                    None
                                )
                                if not person:
                                    file_errors.append(f"Ligne {row_count}: Personne non trouvée: {name}")
                                    continue
                                
                                # Validation et conversion des données
                                try:
                                    date_val = datetime.strptime(cleaned_row['date'], '%Y-%m-%d').date()
                                    period = int(cleaned_row['periode'])
                                    priority = cleaned_row['priorite'].lower()
                                    
                                    # Validations
                                    if period not in {1, 2, 3}:
                                        raise ValueError("Période invalide")
                                    if priority not in {'primary', 'secondary'}:
                                        raise ValueError("Priorité invalide")
                                    if not (self.planning_start_date <= date_val <= self.planning_end_date):
                                        raise ValueError("Date hors période")
                                        
                                    # Ajouter le desiderata
                                    if name not in temp_desiderata:
                                        temp_desiderata[name] = []
                                    temp_desiderata[name].append((date_val, period, priority))
                                    
                                except ValueError as ve:
                                    file_errors.append(f"Ligne {row_count}: {str(ve)}")
                                    continue
                                    
                            except Exception as e:
                                file_errors.append(f"Ligne {row_count}: Erreur - {str(e)}")
                    
                    # Mettre à jour les statistiques
                    global_stats['files_processed'] += 1
                    global_stats['total_rows'] += row_count
                    
                    if file_errors:
                        global_stats['files_with_errors'] += 1
                        all_errors[file_path] = file_errors
                    
                    # Fusionner les desiderata temporaires
                    for name, desiderata_list in temp_desiderata.items():
                        if name not in all_temp_desiderata:
                            all_temp_desiderata[name] = []
                        all_temp_desiderata[name].extend(desiderata_list)
                        global_stats['people_updated'].add(name)
                    
                except Exception as e:
                    all_errors[file_path] = [f"Erreur de traitement du fichier: {str(e)}"]
                    global_stats['files_with_errors'] += 1

            # Afficher le résumé des erreurs s'il y en a
            if all_errors:
                error_message = "Erreurs détectées:\n\n"
                for file_path, errors in all_errors.items():
                    error_message += f"\nFichier: {os.path.basename(file_path)}\n"
                    error_message += "\n".join(errors) + "\n"
                    
                reply = QMessageBox.warning(
                    self,
                    "Avertissement",
                    f"{error_message}\n\nVoulez-vous continuer avec les données valides?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            # Appliquer les desiderata valides
            for name, desiderata_list in all_temp_desiderata.items():
                person = next(p for p in self.doctors + self.cats if p.name == name)
                person.desiderata = [
                    Desiderata(date, date, "Indisponibilité", period, priority)
                    for date, period, priority in desiderata_list
                ]
                global_stats['successful_imports'] += 1

            # Mise à jour de l'interface
            self.update_calendar()
            self.update_stats()
            self.main_window.save_data()

            # Afficher le résumé
            summary = (
                f"Import terminé :\n\n"
                f"Fichiers traités : {global_stats['files_processed']}\n"
                f"Fichiers avec erreurs : {global_stats['files_with_errors']}\n"
                f"Lignes traitées : {global_stats['total_rows']}\n"
                f"Personnes mises à jour : {len(global_stats['people_updated'])}\n"
                f"Imports réussis : {global_stats['successful_imports']}"
            )

            QMessageBox.information(self, "Import terminé", summary)

        except Exception as e:
            self.logger.error(f"Erreur d'importation multiple : {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'importation :\n{str(e)}"
            )


class CriticalPeriodsWindow(QDialog):
    """
    Fenêtre pour visualiser les périodes critiques d'indisponibilité
    """
    def __init__(self, doctors, cats, start_date, end_date, parent=None):
        super().__init__(parent)
        self.doctors = doctors
        self.cats = cats
        self.start_date = start_date
        self.end_date = end_date
        self.cal = France()
        self.setStyleSheet(GLOBAL_STYLE)  # Appliquer le style global à la fenêtre
        self.init_ui()
        self.update_critical_periods()

    def init_ui(self):
        self.setWindowTitle("Périodes critiques")
        self.setMinimumSize(1200, 600)
        main_layout = QVBoxLayout(self)

        # Layout horizontal pour le calendrier et la liste
        content_layout = QHBoxLayout()
        
        # Création du calendrier des périodes critiques avec la nouvelle implémentation
        self.calendar = CriticalPeriodsCalendar(self.start_date, self.end_date)
        self.calendar.cellClicked.connect(self.update_availability_list)
        content_layout.addWidget(self.calendar, stretch=2)

        # Création de la liste des disponibilités
        self.availability_list = QTableWidget()
        self.availability_list.setColumnCount(2)
        self.availability_list.setHorizontalHeaderLabels(["Médecin", "Statut"])
        self.availability_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.availability_list, stretch=1)

        main_layout.addLayout(content_layout)

        # Ajouter la légende
        legend_widget = self.calendar.add_legend(main_layout)
        main_layout.addWidget(legend_widget)

        # Ajuster les proportions
        self.calendar.setMinimumWidth(800)
        self.availability_list.setMinimumWidth(300)

        # Empêcher le redimensionnement des lignes
        self.availability_list.verticalHeader().setDefaultSectionSize(25)

    def update_critical_periods(self):
        # Calculer le nombre total de personnel (médecins + CAT)
        total_personnel = len(self.doctors) + len(self.cats)
        
        # Calculer le nombre de personnes indisponibles pour chaque période
        unavailability_map = {}
        for current_date in (self.start_date + timedelta(n) for n in range((self.end_date - self.start_date).days + 1)):
            for period in range(1, 4):  # 1: Matin, 2: Après-midi, 3: Soir
                unavailable_count = sum(
                    1 for person in (self.doctors + self.cats)
                    if any(
                        des.start_date <= current_date <= des.end_date and des.period == period
                        for des in person.desiderata
                    )
                )
                unavailability_map[(current_date, period)] = unavailable_count

        # Mettre à jour le calendrier avec les couleurs appropriées
        self.calendar.update_colors(unavailability_map, total_personnel)

    def update_availability_list(self, row, col):
        self.availability_list.setRowCount(0)
        
        # Récupérer la date et la période depuis la cellule cliquée
        item = self.calendar.item(row, col)
        if not item:
            return
            
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return
            
        date = data.get("date")
        period = data.get("period")
        
        if not date or not period or period < 1 or period > 3:
            return
            
        # Déterminer le nom de la période
        period_names = {1: "Matin", 2: "Après-midi", 3: "Soir"}
        period_name = period_names.get(period, "")

        # Ajouter une ligne d'en-tête avec la date et la période
        self.availability_list.insertRow(0)
        
        # Calculer le pourcentage d'indisponibilité
        total_personnel = len(self.doctors) + len(self.cats)
        unavailable_count = sum(
            1 for person in (self.doctors + self.cats)
            if any(des.start_date <= date <= des.end_date and des.period == period for des in person.desiderata)
        )
        percentage = (unavailable_count / total_personnel) * 100 if total_personnel > 0 else 0
        
        header_item = QTableWidgetItem(
            f"{date.strftime('%d/%m/%Y')} - {period_name}\n"
            f"{unavailable_count}/{total_personnel} ({percentage:.0f}% indisponibles)"
        )
        PlatformHelper.apply_background_color(header_item, QColor(240, 240, 240))
        header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.availability_list.setSpan(0, 0, 1, 2)
        self.availability_list.setItem(0, 0, header_item)

        # Trier et afficher tout le personnel (médecins et CAT)
        all_personnel = self.doctors + self.cats
        sorted_personnel = sorted(all_personnel, key=lambda p: (
            not any(des.start_date <= date <= des.end_date and des.period == period for des in p.desiderata),
            isinstance(p, CAT),  # Trier les CAT après les médecins
            p.name
        ))

        for person in sorted_personnel:
            row = self.availability_list.rowCount()
            self.availability_list.insertRow(row)
            
            # Nom avec indication du type et des demi-parts pour les médecins
            name_text = person.name
            if isinstance(person, Doctor):
                if person.half_parts == 1:
                    name_text += " (½)"
            else:
                name_text += " (CAT)"
            name_item = QTableWidgetItem(name_text)
            self.availability_list.setItem(row, 0, name_item)
            
            # Statut de disponibilité
            is_available = not any(
                des.start_date <= date <= des.end_date and des.period == period
                for des in person.desiderata
            )
            status_item = QTableWidgetItem("Disponible" if is_available else "Indisponible")
            color = QColor(150, 255, 150) if is_available else QColor(255, 150, 150)
            PlatformHelper.apply_background_color(status_item, color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.availability_list.setItem(row, 1, status_item)

        self.availability_list.resizeColumnsToContents()
            
class CriticalPeriodsCalendar(PlanningTableComponent):
    """
    Calendrier des périodes critiques utilisant le composant PlanningTableComponent
    pour la cohérence visuelle.
    """
    def __init__(self, start_date, end_date):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.cal = France()
        self.init_critical_periods_ui()
        
        # Définition des paliers et leurs couleurs
        self.color_ranges = {
            (0, 0): (QColor(255, 255, 255), "0% - Aucune indisponibilité"),
            (1, 25): (QColor(200, 255, 200), "1-25% - Indisponibilité faible"),
            (26, 50): (QColor(255, 255, 150), "26-50% - Indisponibilité modérée"),
            (51, 75): (QColor(255, 200, 150), "51-75% - Indisponibilité élevée"),
            (75, 99): (QColor(255, 0, 0), "76-99% - Indisponibilité critique"),
            (100, 100): (QColor(0, 0, 0), "100% - Indisponibilité totale")
        }

    def init_critical_periods_ui(self):
        """Initialise l'interface utilisateur spécifique aux périodes critiques"""
        # Configuration pour le mode sélection unique
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        
        # Nettoyer le tableau avant de configurer les dates
        self.setRowCount(0)
        self.setColumnCount(0)
        
        # Configurer les dates et créer le tableau
        self.setup_planning_dates(self.start_date, self.end_date)
        self.populate_days()
        
    def get_color_for_count(self, percentage):
        """
        Détermine la couleur en fonction du pourcentage d'indisponibilité
        """
        # Arrondir le pourcentage pour la comparaison
        percentage = round(percentage)
        
        for (min_val, max_val), (base_color, _) in self.color_ranges.items():
            if min_val <= percentage <= max_val:
                # Créer un dégradé subtil dans le palier
                if min_val != max_val:
                    ratio = (percentage - min_val) / (max_val - min_val)
                    base_h, base_s, base_v, _ = base_color.getHsvF()
                    # Ajuster légèrement la saturation pour le dégradé
                    new_s = min(1.0, base_s + (ratio * 0.2))
                    return QColor.fromHsvF(base_h, new_s, base_v)
                return base_color
                
        return self.color_ranges[(100, 100)][0]  # Noir pour 100%

    def update_colors(self, unavailability_map, total_personnel):
        """
        Met à jour les couleurs des cellules en fonction des taux d'indisponibilité
        
        Args:
            unavailability_map: Dictionnaire {(date, période): nombre_indisponibles}
            total_personnel: Nombre total de personnel
        """
        # Parcourir toutes les cellules du tableau
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if not item:
                    continue
                    
                data = item.data(Qt.ItemDataRole.UserRole)
                if not data or not isinstance(data, dict):
                    continue
                    
                date_val = data.get("date")
                period = data.get("period")
                
                if not date_val or not period or period < 1 or period > 3:
                    continue
                    
                # Calculer le pourcentage d'indisponibilité
                unavailable_count = unavailability_map.get((date_val, period), 0)
                percentage = (unavailable_count / total_personnel) * 100 if total_personnel > 0 else 0
                
                # Appliquer la couleur et le texte
                color = self.get_color_for_count(percentage)
                self.update_cell(
                    date_val, 
                    period, 
                    f"{percentage:.0f}%", 
                    color
                )

    def add_legend(self, parent_layout):
        """
        Crée et retourne un widget de légende pour le code couleur
        
        Args:
            parent_layout: Layout parent
            
        Returns:
            QWidget: Widget contenant la légende
        """
        legend_widget = QWidget()
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setSpacing(10)
        legend_layout.setContentsMargins(10, 5, 10, 5)

        for (min_val, max_val), (color, description) in self.color_ranges.items():
            # Créer un carré de couleur
            color_label = QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")
            
            # Texte de description
            text_label = QLabel(description)
            text_label.setMinimumWidth(150)  # Assurer une largeur minimale pour la lisibilité
            
            # Conteneur pour chaque paire couleur-texte
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setSpacing(5)
            container_layout.addWidget(color_label)
            container_layout.addWidget(text_label)
            
            legend_layout.addWidget(container)

        return legend_widget
