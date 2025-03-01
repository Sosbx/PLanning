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
from ..Attributions.pre_attribution_view import PreAttributionWidget
from ..styles import color_system, EDIT_DELETE_BUTTON_STYLE, ACTION_BUTTON_STYLE, ADD_BUTTON_STYLE, StyleConstants


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

class PlanningPhaseGenerationThread(QThread):
    """Thread dédié à la génération d'une phase spécifique du planning weekend."""
    progress_update = pyqtSignal(str, int)  # Message, pourcentage
    planning_generated = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, planning_generator, phase_type, planning):
        """
        Initialise le thread de génération par phase.
        
        Args:
            planning_generator: Générateur de planning
            phase_type: Type de phase à générer ("nl", "nam", "combinations")
            planning: Planning existant à mettre à jour
        """
        super().__init__()
        self.planning_generator = planning_generator
        self.phase_type = phase_type
        self.planning = planning
        self._is_cancelled = False

    def run(self):
        """Exécute la génération de la phase demandée avec possibilité de redistribution."""
        try:
            if self.phase_type == "nl":
                # Phase 1: Distribution des NL
                self.progress_update.emit("Distribution des gardes NL...", 20)
                
                # Réinitialiser les slots NL non attribués avant redistribution
                if hasattr(self.planning, 'days'):
                    for day in self.planning.days:
                        for slot in day.slots:
                            if slot.abbreviation == "NL" and not slot.is_pre_attributed:
                                slot.assignee = None
                
                # Utiliser la méthode dédiée pour la distribution des NL
                success = self.planning_generator.distribute_nlw(
                    self.planning, 
                    self.planning.pre_analysis_results
                )
                
                if not success:
                    self.error_occurred.emit("Échec de la distribution des gardes NL")
                    return
                    
                # Marquer la phase comme distribuée
                self.planning.nl_distributed = True
                
                if not self._is_cancelled:
                    self.progress_update.emit("Distribution des NL terminée", 100)
                    self.planning_generated.emit(self.planning)
                
            elif self.phase_type == "nam":
                # Phase 2: Distribution des NA/NM
                self.progress_update.emit("Distribution des gardes NA/NM...", 20)
                
                # Vérifier que la phase NL a été validée
                if not self.planning.nl_validated:
                    self.error_occurred.emit("Les gardes NL doivent être validées avant les NA/NM")
                    return
                
                # Réinitialiser les slots NA/NM non attribués avant redistribution
                if hasattr(self.planning, 'days'):
                    for day in self.planning.days:
                        for slot in day.slots:
                            if slot.abbreviation in ["NA", "NM"] and not getattr(slot, 'is_pre_attributed', False):
                                slot.assignee = None
                
                # Exécuter la distribution des NA/NM
                success = self.planning_generator.distribute_namw(
                    self.planning, 
                    self.planning.pre_analysis_results
                )
                
                if not success:
                    self.error_occurred.emit("Échec de la distribution des gardes NA/NM")
                    return
                
                # Marquer la phase comme distribuée
                self.planning.nam_distributed = True
                
                if not self._is_cancelled:
                    self.progress_update.emit("Distribution des NA/NM terminée", 100)
                    self.planning_generated.emit(self.planning)
                
            elif self.phase_type == "combinations":
                # Phase 3: Distribution des combinaisons et postes restants
                self.progress_update.emit("Distribution des combinaisons...", 20)
                
                # Vérifier que la phase précédente a été validée
                if not self.planning.nam_validated:
                    self.error_occurred.emit("Les gardes NA/NM doivent être validées avant les combinaisons")
                    return
                
                # Réinitialiser les slots restants (qui ne sont ni NL, ni NA, ni NM)
                if hasattr(self.planning, 'days'):
                    for day in self.planning.days:
                        if day.is_weekend or day.is_holiday_or_bridge:
                            for slot in day.slots:
                                if slot.abbreviation not in ["NL", "NA", "NM"] and not getattr(slot, 'is_pre_attributed', False):
                                    slot.assignee = None
                
                # Distribuer les combinaisons aux CAT
                success_cat = self.planning_generator._distribute_cat_weekend_combinations(self.planning)
                if not success_cat:
                    self.error_occurred.emit("Échec de la distribution des combinaisons aux CAT")
                    return
                
                self.progress_update.emit("Distribution des combinaisons aux médecins...", 40)
                
                # Distribuer les combinaisons aux médecins
                success_med = self.planning_generator._distribute_doctor_weekend_combinations(self.planning)
                if not success_med:
                    self.error_occurred.emit("Échec de la distribution des combinaisons aux médecins")
                    return
                
                self.progress_update.emit("Distribution des postes restants...", 70)
                
                # Distribuer les postes restants
                success_remaining = self.planning_generator.distribute_remaining_weekend_posts(self.planning)
                if not success_remaining:
                    self.error_occurred.emit("Échec de la distribution des postes restants")
                    return
                
                # Marquer la phase comme distribuée
                self.planning.combinations_distributed = True
                
                if not self._is_cancelled:
                    self.progress_update.emit("Distribution terminée", 100)
                    self.planning_generated.emit(self.planning)
                
            else:
                self.error_occurred.emit(f"Phase de génération inconnue: {self.phase_type}")
                
        except Exception as e:
            self.error_occurred.emit(f"Erreur lors de la génération de la phase {self.phase_type}: {str(e)}")
            import traceback
            traceback.print_exc()


class PlanningViewWidget(QWidget):
    """Widget principal pour la vue et la génération du planning."""
    dates_changed = pyqtSignal(date, date)

    def __init__(self, doctors, cats, post_configuration, main_window, pre_attributions=None):
        super().__init__()
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.main_window = main_window
        self.pre_attributions = pre_attributions or {}
        self.planning_generator = PlanningGenerator(doctors, cats, post_configuration)
        self.planning = None
        self.weekend_validated = False
        self.nl_validated = False
        self.nam_validated = False
        self.combinations_validated = False
        self.generation_thread = None
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._delayed_update)
        self.pending_update = None
        self.generation_phase = "init"  # ["init", "nl", "nam", "combinations", "weekday"]
        self.init_ui()


    # Modifiez la méthode init_ui dans PlanningViewWidget pour n'avoir que deux boutons évolutifs

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md']
        )
        layout.setSpacing(StyleConstants.SPACING['md'])

        # Contrôles de date et bouton de génération
        date_layout = QHBoxLayout()
        date_layout.setSpacing(StyleConstants.SPACING['sm'])
        
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
        
        # Modification des boutons de génération et de validation
        self.generate_button = QPushButton("Générer les gardes NL")
        self.generate_button.clicked.connect(self.generate_planning)
        self.generate_button.setStyleSheet(ACTION_BUTTON_STYLE)
        date_layout.addWidget(self.generate_button)

        # Bouton de validation
        self.validate_button = QPushButton("Valider les gardes NL")
        self.validate_button.clicked.connect(self.validate_current_phase)
        self.validate_button.setEnabled(False)  # Désactivé par défaut
        self.validate_button.setStyleSheet(ACTION_BUTTON_STYLE)
        date_layout.addWidget(self.validate_button)
        
        # Bouton de réinitialisation
        self.reset_planning_button = QPushButton("Réinitialiser le planning")
        self.reset_planning_button.clicked.connect(self.reset_planning)
        self.reset_planning_button.setEnabled(True)
        self.reset_planning_button.setStyleSheet(EDIT_DELETE_BUTTON_STYLE)
        date_layout.addWidget(self.reset_planning_button)
        
        layout.addLayout(date_layout)
        
        # Barre de progression avec style
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                background-color: {color_system.colors['container']['background'].name()};
                padding: {StyleConstants.SPACING['xxs']}px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color_system.colors['primary'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm'] - 1}px;
            }}
        """)
        self.progress_bar.setMinimumHeight(StyleConstants.SPACING['lg'])
        layout.addWidget(self.progress_bar)

        # Widget avec des onglets
        tab_widget = QTabWidget()
        
        tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {color_system.colors['container']['border'].name()};
                background-color: {color_system.colors['container']['background'].name()};
                border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
            }}
            QTabBar::tab {{
                background-color: {color_system.colors['table']['header'].name()};
                color: {color_system.colors['text']['primary'].name()};
                padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
                border: 1px solid {color_system.colors['container']['border'].name()};
                border-bottom: none;
                border-top-left-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                border-top-right-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
                min-width: 100px;
                font-family: {StyleConstants.FONT['family']['primary']};
                font-size: {StyleConstants.FONT['size']['md']};
            }}
            QTabBar::tab:selected {{
                background-color: {color_system.colors['primary'].name()};
                color: {color_system.colors['text']['light'].name()};
                font-weight: {StyleConstants.FONT['weight']['medium']};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {color_system.colors['table']['hover'].name()};
                transition: background-color {StyleConstants.ANIMATION['fast']}ms;
            }}
        """)
        
        # Vue globale du planning avec style
        self.global_view = QTableWidget(self)
        self.global_view.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {color_system.colors['table']['border'].name()};
                gridline-color: {color_system.colors['table']['border'].name()};
                font-family: {StyleConstants.FONT['family']['primary']};
                font-size: {StyleConstants.FONT['size']['md']};
            }}
            QHeaderView::section {{
                background-color: {color_system.colors['table']['header'].name()};
                color: {color_system.colors['text']['primary'].name()};
                padding: {StyleConstants.SPACING['xs']}px;
                border: none;
                border-bottom: 2px solid {color_system.colors['table']['border'].name()};
                font-weight: {StyleConstants.FONT['weight']['medium']};
            }}
            QTableWidget::item {{
                padding: {StyleConstants.SPACING['xs']}px;
            }}
            QTableWidget::item:selected {{
                background-color: {color_system.colors['table']['selected'].name()};
                color: {color_system.colors['text']['primary'].name()};
            }}
        """)
        tab_widget.addTab(self.global_view, "Vue globale")
        layout.addWidget(tab_widget)
        
        self.start_date.dateChanged.connect(self.on_date_changed)
        self.end_date.dateChanged.connect(self.on_date_changed)
        
        # Create pre-attribution tab with existing pre-attributions
        self.pre_attribution_tab = PreAttributionWidget(self.doctors, self.cats, 
            self.start_date.date().toPyDate(), 
            self.end_date.date().toPyDate(), 
            self.main_window)
        # Set pre-attributions after widget creation
        if self.pre_attributions:
            self.pre_attribution_tab.pre_attributions = self.pre_attributions
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
        """Lance la génération du planning selon la phase actuelle, avec possibilité de redistribution."""
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
            
            # Si on est en phase initiale ou sans planning, on initialise
            if self.generation_phase == "init" or not self.planning:
                # Créer un nouveau planning
                self.planning = self.planning_generator.generate_planning(start_date, end_date)
                if not self.planning:
                    self._handle_generation_error("Échec de l'initialisation du planning")
                    return
                    
                # Passer à la phase NL
                self.generation_phase = "nl"
            
            # Configure the thread based on current phase
            if hasattr(self.planning, 'weekend_validated') and self.planning.weekend_validated:
                # Si les weekends sont validés, générer uniquement la semaine
                # Utiliser la classe existante PlanningGenerationThread pour la génération de semaine
                self.generation_thread = PlanningGenerationThread(
                    self.planning_generator, start_date, end_date,
                    self.doctors, self.cats, self.post_configuration,
                    generate_weekdays=True,
                    existing_planning=self.planning
                )
                self.generate_button.setText("Génération planning semaine en cours...")
            else:
                # Sinon, générer selon la phase actuelle
                if self.generation_phase == "nl":
                    self.generate_button.setText("Distribution NL en cours...")
                    # Réinitialiser l'état de distribution pour permettre la redistribution
                    self.planning.nl_distributed = False
                    self.generation_thread = PlanningPhaseGenerationThread(
                        self.planning_generator, 
                        "nl", 
                        self.planning
                    )
                elif self.generation_phase == "nam":
                    self.generate_button.setText("Distribution NA/NM en cours...")
                    # Réinitialiser l'état de distribution pour permettre la redistribution
                    self.planning.nam_distributed = False
                    self.generation_thread = PlanningPhaseGenerationThread(
                        self.planning_generator, 
                        "nam", 
                        self.planning
                    )
                else:  # phase "combinations"
                    self.generate_button.setText("Distribution postes restants en cours...")
                    # Réinitialiser l'état de distribution pour permettre la redistribution
                    if hasattr(self.planning, 'combinations_distributed'):
                        self.planning.combinations_distributed = False
                    self.generation_thread = PlanningPhaseGenerationThread(
                        self.planning_generator, 
                        "combinations", 
                        self.planning
                    )

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
        """Gère la fin de la génération avec succès, adaptée pour les redistributions."""
        if planning:
            self.planning = planning
            self.update_table()
            
            # Mise à jour des boutons selon l'étape
            if hasattr(planning, 'weekend_validated') and planning.weekend_validated:
                # Fin de la génération de la semaine
                self.validate_button.setEnabled(False)
                self.generate_button.setText("Générer le planning")
                QMessageBox.information(self, "Génération réussie", 
                                    "Le planning de semaine a été généré avec succès.")
            else:
                # Phase weekend - mise à jour selon la phase actuelle
                if self.generation_phase == "nl":
                    self.validate_button.setText("Valider les gardes NL")
                    self.validate_button.setEnabled(True)  # Toujours activer après distribution
                    self.generate_button.setText("Générer les gardes NL")  # Permettre la redistribution
                    QMessageBox.information(self, "Distribution NL terminée", 
                                        "Les gardes NL ont été distribuées. Vous pouvez les valider ou redistribuer.")
                elif self.generation_phase == "nam":
                    self.validate_button.setText("Valider les gardes NA/NM")
                    self.validate_button.setEnabled(True)  # Toujours activer après distribution
                    self.generate_button.setText("Générer les gardes NA/NM")  # Permettre la redistribution
                    QMessageBox.information(self, "Distribution NA/NM terminée", 
                                        "Les gardes NA/NM ont été distribuées. Vous pouvez les valider ou redistribuer.")
                else:  # phase "combinations"
                    self.validate_button.setText("Valider les weekends")
                    self.validate_button.setEnabled(True)  # Toujours activer après distribution
                    self.generate_button.setText("Générer les postes restants")  # Permettre la redistribution
                    QMessageBox.information(self, "Distribution terminée", 
                                        "Les postes weekend restants ont été distribués. Vous pouvez les valider ou redistribuer.")
            
            # Démarrer la sauvegarde automatique
            try:
                if hasattr(self.main_window, 'planning_management_tab'):
                    self.main_window.planning_management_tab.start_auto_save()
            except Exception as e:
                print(f"Erreur lors du démarrage de la sauvegarde automatique: {str(e)}")
            
            # Charger les post-attributions après génération
            if hasattr(self.main_window, 'load_post_attributions'):
                self.main_window.load_post_attributions()
                
            self.main_window.update_data()
        else:
            self._handle_generation_error("La génération n'a pas produit de planning valide")


    def validate_current_phase(self):
        """Valide la phase actuelle et prépare la suivante."""
        if not self.planning:
            QMessageBox.warning(self, "Erreur", "Aucun planning n'a été généré.")
            return
        
        confirm_msg = ""
        
        if self.generation_phase == "nl":
            confirm_msg = "Voulez-vous valider les gardes NL ? Cette action ne pourra pas être annulée."
        elif self.generation_phase == "nam":
            confirm_msg = "Voulez-vous valider les gardes NA/NM ? Cette action ne pourra pas être annulée."
        else:  # phase "combinations"
            confirm_msg = "Voulez-vous valider les weekends ? Cette action ne pourra pas être annulée."
        
        confirm = QMessageBox.question(
            self,
            "Confirmation",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            if self.generation_phase == "nl":
                # Valider les NL
                self.planning.nl_validated = True
                self.generation_phase = "nam"
                self.generate_button.setText("Générer les gardes NA/NM")
                self.validate_button.setEnabled(False)
                QMessageBox.information(self, "Validation", "Les gardes NL ont été validées.")
            elif self.generation_phase == "nam":
                # Valider les NA/NM
                self.planning.nam_validated = True
                self.generation_phase = "combinations"
                self.generate_button.setText("Générer les postes restants")
                self.validate_button.setEnabled(False)
                QMessageBox.information(self, "Validation", "Les gardes NA/NM ont été validées.")
            else:  # phase "combinations"
                # Valider les weekends comme dans le code original
                self.planning.weekend_validated = True
                
                # Gestion des post-attributions
                if hasattr(self.main_window, 'post_attribution_handler'):
                    self.main_window.post_attribution_handler.clean_and_restore_post_attributions()
                    
                    # Suppression et recréation des slots pour éviter les duplications
                    if hasattr(self.planning, 'days'):
                        for day in self.planning.days:
                            slots_to_keep = []
                            for slot in day.slots:
                                if not hasattr(slot, 'is_post_attribution') or not slot.is_post_attribution:
                                    slots_to_keep.append(slot)
                            day.slots = slots_to_keep
                    
                    # Restauration contrôlée des post-attributions
                    self.main_window.post_attribution_handler._restore_slots_in_planning()
                
                # Update UI to reflect weekday generation mode
                self.generate_button.setText("Générer planning semaine")
                self.validate_button.setEnabled(False)
                
                # Sauvegarder l'état
                self.main_window.planning_management_tab.save_planning()
                
                # Notify user
                QMessageBox.information(
                    self, 
                    "Validation", 
                    "Les weekends ont été validés. Vous pouvez maintenant générer le planning de la semaine."
                )
                
            # Sauvegarder après chaque validation
            if hasattr(self.main_window, 'planning_management_tab'):
                self.main_window.planning_management_tab.save_planning()

    def _set_controls_enabled(self, enabled: bool):
        """Active/désactive les contrôles pendant la génération avec une logique améliorée pour les redistributions."""
        self.generate_button.setEnabled(enabled)
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)
        self.reset_planning_button.setEnabled(enabled)
        
        # Mise à jour du bouton de validation selon la phase
        if self.planning:
            if self.generation_phase == "nl":
                # Activer le bouton de validation seulement si la phase actuelle est distribuée
                self.validate_button.setEnabled(enabled and hasattr(self.planning, 'nl_distributed') and self.planning.nl_distributed)
                self.validate_button.setText("Valider les gardes NL")
            elif self.generation_phase == "nam":
                # Pour NAM, vérifier aussi que NL est validé
                if hasattr(self.planning, 'nl_validated') and self.planning.nl_validated:
                    self.validate_button.setEnabled(enabled and hasattr(self.planning, 'nam_distributed') and self.planning.nam_distributed)
                    self.validate_button.setText("Valider les gardes NA/NM")
                else:
                    self.validate_button.setEnabled(False)
            elif self.generation_phase == "combinations":
                # Pour les combinaisons, vérifier que NAM est validé
                if hasattr(self.planning, 'nam_validated') and self.planning.nam_validated:
                    self.validate_button.setEnabled(enabled and hasattr(self.planning, 'combinations_distributed') and self.planning.combinations_distributed)
                    self.validate_button.setText("Valider les weekends")
                else:
                    self.validate_button.setEnabled(False)
            elif hasattr(self.planning, 'weekend_validated') and self.planning.weekend_validated:
                # Si les weekends sont validés, le bouton de validation reste désactivé
                self.validate_button.setEnabled(False)
            else:
                self.validate_button.setEnabled(False)



    def _handle_generation_error(self, error_message: str):
        """Gère les erreurs de génération."""
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, "Erreur", f"Erreur lors de la génération:\n{error_message}")
        self._set_controls_enabled(True)

    def _update_progress(self, message: str, value: int):
        """Met à jour la barre de progression."""
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{message} ({value}%)")


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
                
                # AJOUT: S'assurer que les post-attributions sont correctement enregistrées
                if hasattr(self.main_window, 'post_attribution_handler'):
                    self.main_window.post_attribution_handler.clean_and_restore_post_attributions()
                    
                    # Suppression et recréation des slots pour éviter les duplications
                    if hasattr(self.planning, 'days'):
                        for day in self.planning.days:
                            slots_to_keep = []
                            for slot in day.slots:
                                if not hasattr(slot, 'is_post_attribution') or not slot.is_post_attribution:
                                    slots_to_keep.append(slot)
                            day.slots = slots_to_keep
                    
                    # Restauration contrôlée des post-attributions
                    self.main_window.post_attribution_handler._restore_slots_in_planning()
                
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
                
                # AJOUT: Nettoyer le planning des post-attributions pour éviter les duplications
                if hasattr(self.main_window, 'post_attribution_handler'):
                    self.main_window.post_attribution_handler.clean_and_restore_post_attributions()
                    
                    # Supprimer les slots post-attribués du nouveau planning
                    for day in new_planning.days:
                        slots_to_keep = []
                        for slot in day.slots:
                            if not hasattr(slot, 'is_post_attribution') or not slot.is_post_attribution:
                                slots_to_keep.append(slot)
                        day.slots = slots_to_keep
                
                # Mettre à jour le planning et l'interface
                self.planning = new_planning
                self.update_table()
                
                # AJOUT: Restaurer les post-attributions sans duplication
                if hasattr(self.main_window, 'post_attribution_handler'):
                    self.main_window.post_attribution_handler._restore_slots_in_planning()
                
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
                base_color = color_system.get_color('weekend' if is_weekend else 'weekday')

                # Vérifier les desiderata de l'assigné
                if slot.assignee:
                    assignee = next((d for d in self.doctors + self.cats if d.name == slot.assignee), None)
                    if assignee:
                        for desiderata in assignee.desiderata:
                            if (desiderata.start_date <= day_planning.date <= desiderata.end_date and
                                desiderata.overlaps_with_slot(slot)):
                                priority = getattr(desiderata, 'priority', 'primary')
                                context = 'weekend' if is_weekend else 'normal'
                                base_color = color_system.get_color('desiderata', context, priority)
                                break

                # Appliquer la couleur
                for col in range(self.global_view.columnCount()):
                    self.global_view.item(row, col).setBackground(QBrush(base_color))

        self.global_view.resizeColumnsToContents()
        
        # Fixer la hauteur des lignes
        for row in range(self.global_view.rowCount()):
            self.global_view.setRowHeight(row, StyleConstants.SPACING['xl'])

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
        """Met à jour les données du planning."""
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.planning_generator = PlanningGenerator(doctors, cats, post_configuration)
        
        if self.planning:
            # Mise à jour du bouton selon la phase
            if self.weekend_validated:
                self.generate_button.setText("Générer planning semaine")
                self.validate_button.setEnabled(False)
            else:
                if self.generation_phase == "nl":
                    self.generate_button.setText("Générer les gardes NL")
                    if not self.nl_validated:
                        self.validate_button.setText("Valider les gardes NL")
                        self.validate_button.setEnabled(True)
                elif self.generation_phase == "nam":
                    self.generate_button.setText("Générer les gardes NA/NM")
                    if not self.nam_validated:
                        self.validate_button.setText("Valider les gardes NA/NM")
                        self.validate_button.setEnabled(True)
                else:
                    self.generate_button.setText("Générer les postes restants")
                    self.validate_button.setText("Valider les weekends")
                    self.validate_button.setEnabled(True)
            
            self.update_table()
    
    def update_planning(self, updated_planning):
        """Met à jour le planning."""
        self.planning = updated_planning
        
        # Récupérer les états de validation du planning
        if hasattr(updated_planning, 'weekend_validated'):
            self.weekend_validated = updated_planning.weekend_validated
        if hasattr(updated_planning, 'nl_validated'):
            self.nl_validated = updated_planning.nl_validated
        if hasattr(updated_planning, 'nam_validated'):
            self.nam_validated = updated_planning.nam_validated
        
        # Déterminer la phase actuelle
        if self.weekend_validated:
            self.generation_phase = "weekday"
        elif self.nam_validated:
            self.generation_phase = "combinations"
        elif self.nl_validated:
            self.generation_phase = "nam"
        else:
            self.generation_phase = "nl"
        
        # Mise à jour de l'interface
        self.update_data(self.doctors, self.cats, self.post_configuration)


    def reset_planning(self):
        """Réinitialise le planning."""
        confirm = QMessageBox.question(self, "Confirmation", 
                                "Êtes-vous sûr de vouloir réinitialiser le planning ? Toutes les données de planning seront perdues.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            # Réinitialiser le planning
            self.planning = None
            self.generation_phase = "init"

            # Réinitialiser l'état des boutons
            self.generate_button.setText("Générer les gardes NL")
            self.generate_button.setEnabled(True)
            self.validate_button.setText("Valider les gardes NL")
            self.validate_button.setEnabled(False)

            # Réinitialiser les compteurs et attributs
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

            QMessageBox.information(self, "Réinitialisation", "Le planning a été réinitialisé avec succès.")