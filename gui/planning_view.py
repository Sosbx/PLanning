# © 2024 HILAL Arkane. Tous droits réservés.
# gui/planning_view.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QLabel,
                             QTableWidget, QTableWidgetItem, QDateEdit, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush, QFont
from core.Generator.Weekend.planning_generator import PlanningGenerator
from core.Constantes.models import ALL_POST_TYPES, WEEKDAY_COMBINATIONS, WEEKEND_COMBINATIONS
from datetime import date, timedelta
from PyQt6.QtCore import pyqtSignal
from .pre_attribution_view import PreAttributionWidget



# Import pour la détection du système d'exploitation
import sys

# Définition des couleurs adaptées selon le système d'exploitation
if sys.platform == 'win32':
    # Couleurs optimisées pour Windows - plus contrastées et avec alpha channel
    WEEKEND_COLOR = QColor(200, 200, 200, 255)  # Gris plus foncé pour meilleur contraste
    WEEKDAY_COLOR = QColor(255, 255, 255, 255)  # Blanc pur
    DESIDERATA_COLOR = QColor(255, 180, 180, 255)  # Rouge plus foncé pour meilleure visibilité
    WEEKEND_DESIDERATA_COLOR = QColor(255, 130, 130, 255)  # Rouge encore plus foncé pour weekends
    WEEKDAY_TEXT_COLOR = QColor(60, 60, 60, 255)  # Gris très foncé pour meilleure lisibilité
else:
    # Couleurs originales pour macOS avec alpha channel ajouté
    WEEKEND_COLOR = QColor(220, 220, 220, 255)  # Gris clair pour les weekends et jours fériés
    WEEKDAY_COLOR = QColor(255, 255, 255, 255)  # Blanc pour les jours de semaine
    DESIDERATA_COLOR = QColor(255, 200, 200, 255)  # Rouge clair pour les desideratas
    WEEKEND_DESIDERATA_COLOR = QColor(255, 150, 150, 255)  # Rouge plus foncé pour les desideratas de weekend
    WEEKDAY_TEXT_COLOR = QColor(100, 100, 100, 255)  # Gris foncé pour le texte des jours de la semaine

class PlanningGenerationThread(QThread):
    """Thread dédié à la génération du planning avec gestion des étapes et des erreurs."""
    progress_update = pyqtSignal(str, int)  # Message, pourcentage
    planning_generated = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, planning_generator, start_date, end_date, doctors, cats, 
                post_configuration, generate_weekdays=False, existing_planning=None):
        super().__init__()
        self.planning_generator = planning_generator
        self.start_date = start_date
        self.end_date = end_date
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.generate_weekdays = generate_weekdays
        self.existing_planning = existing_planning
        self._is_cancelled = False

    def run(self):
        try:
            # Phase 1: Génération des weekends
            if not self.generate_weekdays:
                self.progress_update.emit("Génération des weekends...", 20)
                self.planning = self.planning_generator.generate_planning(
                    self.start_date, self.end_date
                )
                if not self.planning:
                    self.error_occurred.emit("Échec de la génération des weekends")
                    return
                    
                # Important: Ne pas générer la semaine ici
                if not self._is_cancelled:
                    self.planning_generated.emit(self.planning)
                    self.progress_update.emit("Génération des weekends terminée", 100)
                    
            # Phase 2: Génération de la semaine (uniquement si demandé)
            elif self.existing_planning and self.generate_weekdays:
                self.progress_update.emit("Génération du planning semaine...", 20)
                planning = self.planning_generator.generate_weekday_planning(self.existing_planning)
                if not planning:
                    self.error_occurred.emit("Échec de la génération du planning semaine")
                    return

                if not self._is_cancelled:
                    planning.weekend_validated = True  # Conserver l'état de validation
                    self.planning_generated.emit(planning)
                    self.progress_update.emit("Génération terminée", 100)

        except Exception as e:
            self.error_occurred.emit(f"Erreur lors de la génération: {str(e)}")

    def cancel(self):
        """Annule la génération en cours."""
        self._is_cancelled = True


class PlanningViewWidget(QWidget):
    """Widget principal pour la vue et la génération du planning."""
    dates_changed = pyqtSignal(date, date)

    def __init__(self, doctors, cats, post_configuration, main_window):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.main_window = main_window
        self.planning_generator = PlanningGenerator(doctors, cats, post_configuration)
        self.planning = None
        self.weekend_validated = False
        self.generation_thread = None
        self.init_ui()


    def init_ui(self):
        layout = QVBoxLayout(self)

        # Contrôles de date et bouton de génération
        date_layout = QHBoxLayout()
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)

        # Définir les dates par défaut
        today = date.today()
        end_date = today + timedelta(days=4*30)  # Environ 4 mois plus tard
        self.start_date.setDate(QDate(today.year, today.month, today.day))
        self.end_date.setDate(QDate(end_date.year, end_date.month, end_date.day))

        date_layout.addWidget(QLabel("Du:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("Au:"))
        date_layout.addWidget(self.end_date)
        
        # Bouton de génération
        generate_button = QPushButton("Générer le planning")
        generate_button.clicked.connect(self.generate_planning)
        generate_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f8f8;
                color: #333;
                border: 1px solid #ddd;
                padding: 5px 10px;
                font-size: 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)
        self.generate_button = QPushButton("Générer le planning")
        self.generate_button.clicked.connect(self.generate_planning)
        date_layout.addWidget(self.generate_button)
        self.validate_weekends_button = QPushButton("Valider les weekends")
        self.validate_weekends_button.clicked.connect(self.validate_weekends)
        self.validate_weekends_button.setEnabled(False)  # Désactivé par défaut
        date_layout.addWidget(self.validate_weekends_button)

        date_layout.setStretchFactor(self.start_date, 2)
        date_layout.setStretchFactor(self.end_date, 2)
        date_layout.setStretchFactor(generate_button, 1)
        
        layout.addLayout(date_layout)

        # Ajout du nouveau bouton de réinitialisation
        self.reset_planning_button = QPushButton("Réinitialiser le planning")
        self.reset_planning_button.clicked.connect(self.reset_planning)
        self.reset_planning_button.setEnabled(True)  # Activez le bouton
        date_layout.addWidget(self.reset_planning_button)

        # Barre de progression
        self.progress_bar = QProgressBar(self)
        layout.addWidget(self.progress_bar)

        # Créer un widget avec des onglets
        tab_widget = QTabWidget()
        
        # Vue globale du planning
        self.global_view = QTableWidget(self)
        tab_widget.addTab(self.global_view, "Vue globale")
        layout.addWidget(tab_widget)
        
        self.start_date.dateChanged.connect(self.on_date_changed)
        self.end_date.dateChanged.connect(self.on_date_changed)
        
        # Create pre-attribution tab
        self.pre_attribution_tab = PreAttributionWidget(self.doctors, self.cats, 
            self.start_date.date().toPyDate(), 
            self.end_date.date().toPyDate(), 
            self.main_window)
        tab_widget.addTab(self.pre_attribution_tab, "Pré-attribution")
        
        # Connect dates_changed signal to pre_attribution_tab after creation
        self.dates_changed.connect(self.pre_attribution_tab.update_dates)

    def update_data(self, doctors, cats, post_configuration):
        # Stocker les données à mettre à jour et démarrer le timer
        self.pending_update = (doctors, cats, post_configuration)
        if not self.update_timer.isActive():
            self.update_timer.start(100)

    def _delayed_update(self):
        if self.pending_update:
            doctors, cats, post_configuration = self.pending_update
            self.doctors = doctors
            self.cats = cats
            self.post_configuration = post_configuration
            self.planning_generator = PlanningGenerator(doctors, cats, post_configuration)
            if self.planning:
                # Update UI based on validation state
                if self.weekend_validated:
                    self.generate_button.setText("Générer planning semaine")
                    self.validate_weekends_button.setEnabled(False)
                else:
                    self.generate_button.setText("Générer le planning")
                    self.validate_weekends_button.setEnabled(True)
                
                self.update_table()
            self.pending_update = None
            
    def update_dates(self, start_date, end_date):
        self.start_date.setDate(QDate(start_date))
        self.end_date.setDate(QDate(end_date))
        self.on_date_changed()  # Ceci émettra le signal dates_changed
        
    def on_date_changed(self):
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        self.dates_changed.emit(start_date, end_date)

    def generate_planning(self, existing_planning=None):
        """Lance la génération du planning avec gestion des états."""
        try:
            start_date = self.start_date.date().toPyDate()
            end_date = self.end_date.date().toPyDate()

            if start_date > end_date:
                QMessageBox.warning(self, "Erreur", 
                                "La date de début doit être antérieure à la date de fin.")
                return

            # Désactiver les contrôles pendant la génération
            self._set_controls_enabled(False)
            self.progress_bar.setValue(0)

            # Get pre-attributions from the pre-attribution tab
            pre_attributions = self.pre_attribution_tab.pre_attributions
            
            # Create a new generator with pre-attributions
            self.planning_generator = PlanningGenerator(
                self.doctors, 
                self.cats, 
                self.post_configuration,
                pre_attributions=pre_attributions
            )
            
            # Create and configure the thread based on validation state
            if self.weekend_validated:
                # Si les weekends sont validés, générer uniquement la semaine
                if not self.planning:
                    QMessageBox.warning(self, "Erreur", 
                                    "Aucun planning weekend validé trouvé.")
                    self._set_controls_enabled(True)
                    return
                    
                self.generation_thread = PlanningGenerationThread(
                    self.planning_generator, start_date, end_date,
                    self.doctors, self.cats, self.post_configuration,
                    generate_weekdays=True,
                    existing_planning=self.planning  # Use current validated planning
                )
                self.generate_button.setText("Génération planning semaine en cours...")
            else:
                # Sinon, générer uniquement les weekends
                self.generation_thread = PlanningGenerationThread(
                    self.planning_generator, start_date, end_date,
                    self.doctors, self.cats, self.post_configuration,
                    generate_weekdays=False,
                    existing_planning=None
                )
                self.generate_button.setText("Génération weekends en cours...")

            # Connecter les signaux
            self.generation_thread.progress_update.connect(self._update_progress)
            self.generation_thread.planning_generated.connect(self._planning_generated)
            self.generation_thread.error_occurred.connect(self._handle_generation_error)
            self.generation_thread.finished.connect(
                lambda: self._set_controls_enabled(True)
            )

            # Démarrer la génération
            self.generation_thread.start()

        except Exception as e:
            self._handle_generation_error(f"Erreur de démarrage: {str(e)}")
            self._set_controls_enabled(True)
            
    def _planning_generated(self, planning):
        """Gère la fin de la génération avec succès."""
        if planning:
            self.planning = planning
            # Conserver l'état de validation des weekends
            if hasattr(planning, 'weekend_validated'):
                self.weekend_validated = planning.weekend_validated
            else:
                self.weekend_validated = False
                
            self.update_table()
            
            # Mise à jour des boutons selon l'étape
            if self.weekend_validated:
                # Fin de la génération de la semaine
                self.validate_weekends_button.setEnabled(False)
                self.generate_button.setText("Générer le planning")
                QMessageBox.information(self, "Génération réussie", 
                    "Le planning de semaine a été généré avec succès.")
            else:
                # Fin de la génération des weekends uniquement
                self.validate_weekends_button.setEnabled(True)
                self.generate_button.setText("Générer planning semaine")
                QMessageBox.information(self, "Génération réussie", 
                    "Les weekends ont été générés. Vous devez maintenant les valider avant de générer le planning de semaine.")
            
            # Démarrer la sauvegarde automatique
            self.main_window.planning_management_tab.start_auto_save()
            self.main_window.update_data()
        else:
            self._handle_generation_error("La génération n'a pas produit de planning valide")


    def _handle_generation_error(self, error_message: str):
        """Gère les erreurs de génération."""
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, "Erreur", f"Erreur lors de la génération:\n{error_message}")
        self._set_controls_enabled(True)

    def _update_progress(self, message: str, value: int):
        """Met à jour la barre de progression."""
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{message} ({value}%)")

    def _set_controls_enabled(self, enabled: bool):
        """Active/désactive les contrôles pendant la génération."""
        self.generate_button.setEnabled(enabled)
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)
        self.reset_planning_button.setEnabled(enabled)
        if self.planning:
            self.validate_weekends_button.setEnabled(enabled and not self.weekend_validated)

    def cancel_generation(self):
        """Annule la génération en cours."""
        if self.generation_thread and self.generation_thread.isRunning():
            self.generation_thread.cancel()
            self.generation_thread.wait()
            self._set_controls_enabled(True)
            self.progress_bar.setValue(0)

            
    def validate_weekends(self):
        """Valide les weekends et prépare la génération de la semaine."""
        if self.planning:
            confirm = QMessageBox.question(
                self,
                "Confirmation",
                "Voulez-vous valider les weekends ? Cette action ne pourra pas être annulée.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if confirm == QMessageBox.StandardButton.Yes:
                # Set both the widget and planning model flags
                self.weekend_validated = True
                self.planning.weekend_validated = True
                
                # Update UI to reflect weekday generation mode
                self.generate_button.setText("Générer planning semaine")
                self.validate_weekends_button.setEnabled(False)
                
                # Ensure the planning generator is ready for weekday generation
                self.planning_generator = PlanningGenerator(
                    self.doctors, 
                    self.cats, 
                    self.post_configuration,
                    pre_attributions=self.pre_attribution_tab.pre_attributions
                )
                
                # Sauvegarder l'état
                self.main_window.planning_management_tab.save_planning()
                
                # Notify user
                QMessageBox.information(
                    self, 
                    "Validation", 
                    "Les weekends ont été validés. Vous pouvez maintenant générer le planning de la semaine."
                )
        else:
            QMessageBox.warning(
                self,
                "Erreur",
                "Aucun planning n'a été généré. Veuillez d'abord générer un planning.")

    def generate_weekday_planning(self):
        if self.weekend_validated:
            # Appeler la méthode pour générer le planning de la semaine
            new_planning = self.planning_generator.generate_weekday_planning(self.planning)
            if new_planning:
                # Ensure the new planning keeps the weekend validation state
                new_planning.weekend_validated = True
                self.planning = new_planning
                self.update_table()
                self.main_window.update_data()
                QMessageBox.information(self, "Génération terminée", "Le planning de la semaine a été généré avec succès.")
            else:
                QMessageBox.warning(self, "Erreur", "La génération du planning de la semaine a échoué.")
        else:
            QMessageBox.warning(self, "Erreur", "Veuillez d'abord valider les weekends avant de générer le planning de la semaine.")
            
    def display_constraint_analysis(self):
            if hasattr(self.planning_generator, 'pre_analyzer'):
                analysis = self.planning_generator.pre_analyzer.analyze()
                if analysis is not None and 'constraint_analysis' in analysis:
                    constraint_analysis = analysis['constraint_analysis']
                    
                    message = f"Analyse des contraintes :\n"
                    message += f"Conflits potentiels : {constraint_analysis.get('potential_conflicts', 'N/A')}\n"
                    # Ajoutez d'autres informations sur les contraintes ici
                    
                    QMessageBox.information(self, "Analyse des contraintes", message)
                else:
                    QMessageBox.warning(self, "Erreur", "L'analyse des contraintes n'est pas disponible.")
            else:
                QMessageBox.warning(self, "Erreur", "L'analyseur de pré-planning n'est pas disponible.")
                
 

    def update_table(self):
        if not self.planning:
            return

        self.global_view.clear()
        self.global_view.setRowCount(0)
        self.global_view.setColumnCount(5)
        self.global_view.setHorizontalHeaderLabels(["Date", "Créneau", "Type", "Site", "Assigné à"])

        # Définition des couleurs pour les desiderata
        colors = {
            "primary": {
                "weekend": QColor(255, 150, 150),     # Rouge plus foncé pour weekend
                "normal": QColor(255, 200, 200)       # Rouge clair pour jours normaux
            },
            "secondary": {
                "weekend": QColor(150, 200, 255),     # Bleu plus foncé pour weekend
                "normal": QColor(180, 220, 255)       # Bleu clair pour jours normaux
            }
        }

        for day_planning in self.planning.days:
            for slot in day_planning.slots:
                row = self.global_view.rowCount()
                self.global_view.insertRow(row)
                
                date_item = QTableWidgetItem(day_planning.date.strftime("%d-%m-%y"))
                self.global_view.setItem(row, 0, date_item)
                self.global_view.setItem(row, 1, QTableWidgetItem(f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}"))
                self.global_view.setItem(row, 2, QTableWidgetItem(slot.abbreviation))
                self.global_view.setItem(row, 3, QTableWidgetItem(slot.site))
                self.global_view.setItem(row, 4, QTableWidgetItem(slot.assignee or "Non attribué"))

                # Coloration selon le type de jour et les desiderata
                is_weekend = day_planning.is_weekend or day_planning.is_holiday_or_bridge
                base_color = WEEKEND_COLOR if is_weekend else WEEKDAY_COLOR

                # Vérifier les desiderata de l'assigné
                if slot.assignee:
                    assignee = next((d for d in self.doctors + self.cats if d.name == slot.assignee), None)
                    if assignee:
                        for desiderata in assignee.desiderata:
                            if (desiderata.start_date <= day_planning.date <= desiderata.end_date and
                                desiderata.overlaps_with_slot(slot)):
                                priority = getattr(desiderata, 'priority', 'primary')
                                color_key = "weekend" if is_weekend else "normal"
                                base_color = colors[priority][color_key]
                                break

                # Appliquer la couleur
                for col in range(self.global_view.columnCount()):
                    self.global_view.item(row, col).setBackground(QBrush(base_color))

        self.global_view.resizeColumnsToContents()
        
        # Fixer la hauteur des lignes
        for row in range(self.global_view.rowCount()):
            self.global_view.setRowHeight(row, 25)

        # Empêcher l'édition des cellules
        self.global_view.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
    def update_post_configuration(self, new_post_configuration):
        self.post_configuration = new_post_configuration
        self.planning_generator = PlanningGenerator(self.doctors, self.cats, self.post_configuration)
        if self.planning:
            self.generate_planning(self.planning)  # Passez le planning existant
        else:
            self.generate_planning()  # Créez un nouveau planning si aucun n'existe
            
    def refresh_custom_posts(self):
        """Refresh custom posts in pre-attribution tab"""
        if hasattr(self, 'pre_attribution_tab'):
            self.pre_attribution_tab.refresh_custom_posts()

    def update_data(self, doctors, cats, post_configuration):
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.planning_generator = PlanningGenerator(doctors, cats, post_configuration)
        if self.planning:
            # Update UI based on validation state
            if self.weekend_validated:
                self.generate_button.setText("Générer planning semaine")
                self.validate_weekends_button.setEnabled(False)
            else:
                self.generate_button.setText("Générer le planning")
                self.validate_weekends_button.setEnabled(True)
            
            self.update_table()

    def update_planning(self, updated_planning):
        self.planning = updated_planning
        # Sync weekend validation state
        self.weekend_validated = updated_planning.weekend_validated
        # Update UI based on validation state
        if self.weekend_validated:
            self.generate_button.setText("Générer planning semaine")
            self.validate_weekends_button.setEnabled(False)
        else:
            self.generate_button.setText("Générer le planning")
            self.validate_weekends_button.setEnabled(True)
        
            self.update_table()
            self.main_window.update_data()


    def reset_planning(self):
        confirm = QMessageBox.question(self, "Confirmation", 
                                    "Êtes-vous sûr de vouloir réinitialiser le planning ? Toutes les données de planning seront perdues.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                    QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            # Réinitialiser le planning et les flags de validation
            if self.planning:
                self.planning.weekend_validated = False
            self.planning = None
            self.weekend_validated = False

            # Réinitialiser l'état des boutons
            self.generate_button.setText("Générer le planning")
            self.generate_button.setEnabled(True)
            self.validate_weekends_button.setEnabled(False)

            # Déconnecter et reconnecter le signal pour s'assurer qu'il n'y a qu'une seule connexion
            self.generate_button.clicked.disconnect()
            self.generate_button.clicked.connect(self.generate_planning)

            # Réinitialiser les compteurs et attributs des médecins et CAT
            for doctor in self.doctors:
                doctor.night_shifts = {'NLv': 0, 'NLs': 0, 'NLd': 0, 'total': 0}
                doctor.nm_shifts = {'NMs': 0, 'NMd': 0, 'total': 0}
                doctor.combo_counts = {combo: 0 for combo in WEEKEND_COMBINATIONS}
                doctor.group_counts = {group: 0 for group in ["CmS", "CmD", "CaS", "CaD", "CsSD", "VmS", "VmD", "VaSD"]}
                doctor.weekday_night_shifts = {'NL': 0, 'total': 0}
                doctor.weekday_nm_shifts = {'NM': 0, 'total': 0}
                doctor.weekday_combo_counts = {combo: 0 for combo in WEEKDAY_COMBINATIONS}
                doctor.weekday_post_counts = {post_type: 0 for post_type in ALL_POST_TYPES}

            for cat in self.cats:
                cat.posts = {}
                cat.weekday_posts = {}

            # Effacer la vue
            self.global_view.setRowCount(0)
            self.global_view.setColumnCount(0)

            # Réinitialiser le générateur de planning
            self.planning_generator = PlanningGenerator(self.doctors, self.cats, self.post_configuration)

            # Réinitialiser la barre de progression
            self.progress_bar.setValue(0)

            # Mettre à jour les données dans la fenêtre principale
            self.main_window.reset_all_views()

            QMessageBox.information(self, "Réinitialisation", "Le planning a été réinitialisé avec succès. Vous pouvez maintenant générer un nouveau planning.")
