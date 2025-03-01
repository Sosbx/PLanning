# © 2024 HILAL Arkane. Tous droits réservés.
# utils/integration_tools.py

import logging
from datetime import date, timedelta
from PyQt6.QtWidgets import QMessageBox, QDialog
from PyQt6.QtCore import QDate
from gui.post_configuration import AddConfigDialog

logger = logging.getLogger(__name__)

def integrate_improvements(main_window):
    """
    Intègre toutes les améliorations au projet principal.
    
    Args:
        main_window: Fenêtre principale de l'application
    """
    try:
        # Attacher les nouvelles fonctionnalités
        attach_harmonization_tools(main_window)
        patch_post_configuration_widget(main_window)
        patch_calendar_view(main_window)
        
        logger.info("Intégration des améliorations effectuée avec succès")
        
        # Notification à l'utilisateur
        QMessageBox.information(
            main_window,
            "Améliorations intégrées",
            "Les nouvelles fonctionnalités d'harmonisation et d'édition améliorée "
            "ont été intégrées avec succès."
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'intégration des améliorations: {e}", exc_info=True)
        QMessageBox.warning(
            main_window,
            "Erreur d'intégration",
            f"Une erreur est survenue lors de l'intégration des améliorations:\n{str(e)}\n\n"
            "Certaines fonctionnalités peuvent ne pas être disponibles."
        )

def attach_harmonization_tools(main_window):
    """
    Attache les outils d'harmonisation à la fenêtre principale.
    
    Args:
        main_window: Fenêtre principale de l'application
    """
    from gui.harmonization_dialog import HarmonizationDialog
    
    # Ajouter une méthode pour ouvrir le dialogue d'harmonisation
    def show_harmonization_dialog():
        if hasattr(main_window, 'post_configuration'):
            dialog = HarmonizationDialog(main_window.post_configuration, main_window)
            dialog.exec()
        else:
            QMessageBox.warning(
                main_window,
                "Configuration manquante",
                "Aucune configuration de postes n'est actuellement chargée."
            )
    
    # Attacher la méthode à la fenêtre principale
    main_window.show_harmonization_dialog = show_harmonization_dialog
    
    # Ajouter une entrée au menu (si applicable)
    if hasattr(main_window, 'menuTools'):
        harmonize_action = main_window.menuTools.addAction("Harmoniser les configurations")
        harmonize_action.triggered.connect(show_harmonization_dialog)

def patch_post_configuration_widget(main_window):
    """
    Améliore le widget de configuration des postes.
    
    Args:
        main_window: Fenêtre principale de l'application
    """
    # Patch pour SpecificConfigWidget
    if hasattr(main_window, 'post_config_widget'):
        widget = main_window.post_config_widget
        
        # Sauvegarder la méthode d'édition originale
        original_edit_group = widget.specific_config_tab._edit_group
        
        # Remplacer par la version améliorée
        def enhanced_edit_group(row, group):
            # Créer une liste de toutes les dates du groupe
            all_dates = []
            for config in group:
                current_date = config.start_date
                while current_date <= config.end_date:
                    all_dates.append(current_date)
                    current_date += timedelta(days=1)

            # Trier les dates et prendre la première comme date d'édition
            if all_dates:
                all_dates.sort()
                edit_date = all_dates[0]
            else:
                edit_date = None

            # Créer le dialogue avec les dates et la configuration
            dialog = AddConfigDialog(
                widget.specific_config_tab,
                widget.specific_config_tab.post_configuration,
                existing_config=group[0],  # Configuration modèle
                existing_dates=all_dates,  # Toutes les dates du groupe
                edit_date=edit_date        # Date à éditer pour positionnement du calendrier
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Supprimer les anciennes configurations
                for config in group:
                    widget.specific_config_tab.post_configuration.remove_specific_config(config)
                
                # Ajouter les nouvelles
                for new_config in dialog.config_results:
                    widget.specific_config_tab.post_configuration.add_specific_config(new_config)
                    
                widget.specific_config_tab.update_table()
        
        # Appliquer le patch
        widget.specific_config_tab._edit_group = enhanced_edit_group
        
        # Ajouter la méthode d'harmonisation
        def show_harmonization_dialog():
            from gui.harmonization_dialog import HarmonizationDialog
            
            try:
                dialog = HarmonizationDialog(widget.specific_config_tab.post_configuration, widget.specific_config_tab)
                result = dialog.exec()
                
                if result == QDialog.DialogCode.Accepted:
                    widget.specific_config_tab.update_table()
                    
            except Exception as e:
                logger.error(f"Erreur lors de l'affichage du dialogue d'harmonisation: {e}", exc_info=True)
                QMessageBox.critical(
                    widget.specific_config_tab,
                    "Erreur",
                    f"Une erreur est survenue lors de l'affichage du dialogue d'harmonisation:\n{str(e)}"
                )
        
        widget.specific_config_tab.show_harmonization_dialog = show_harmonization_dialog
        
        logger.info("Widget de configuration des postes amélioré")

def patch_calendar_view(main_window):
    """
    Améliore la vue calendrier.
    
    Args:
        main_window: Fenêtre principale de l'application
    """
    from gui.calendar_view import CalendarView
    
    # Sauvegarder les méthodes originales
    original_show_date_configs = CalendarView.show_date_configs
    original_add_configuration = CalendarView.add_configuration
    
    # Remplacer par les versions améliorées
    def enhanced_show_date_configs(self, date_obj):
        """Affiche les configurations pour une date spécifique avec préréglage du type de jour."""
        from gui.post_configuration import SpecificConfigDialog
        
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
    
    def enhanced_add_configuration(self, date_obj=None):
        """Ajoute une nouvelle configuration pour une date avec présélection améliorée."""
        from gui.post_configuration import AddConfigDialog
        
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
    
    # Appliquer les patches
    CalendarView.show_date_configs = enhanced_show_date_configs
    CalendarView.add_configuration = enhanced_add_configuration
    
    logger.info("Vue calendrier améliorée")