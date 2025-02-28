# © 2024 HILAL Arkane. Tous droits réservés.
# core/post_attribution_handler.py

from PyQt6.QtWidgets import QMenu, QMessageBox
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QBrush, QFont
from datetime import datetime, date, time, timedelta
from core.Constantes.models import TimeSlot, PostManager
from core.utils import get_post_period, PostPeriod
from workalendar.europe import France
import logging

logger = logging.getLogger(__name__)

class PostAttributionHandler:
    """
    Gestionnaire pour les post-attributions.
    Permet d'ajouter des postes après la génération du planning.
    """
    def __init__(self, main_window):
        self.main_window = main_window
        self.post_attributions = {}  # Format: {date: {assignee: {period: post_type}}}
        self.history = []  # Historique des actions [(timestamp, type, details)]
        self.calendar = France()
        self.post_manager = PostManager()
        self.constraints = main_window.planning_constraints if hasattr(main_window, 'planning_constraints') else None

    def get_post_color(self):
        """Retourne la couleur utilisée pour les postes post-attribués."""
        return QColor(255, 0, 0)  # Rouge

    def get_post_font(self):
        """Retourne la police utilisée pour les postes post-attribués."""
        font = QFont()
        font.setBold(True)
        return font

    def is_post_attributed(self, date, period, post_type, current_planning):
        """
        Vérifie si un poste est déjà attribué.
        
        Args:
            date: Date à vérifier
            period: Période (1: Matin, 2: Après-midi, 3: Soir)
            post_type: Type de poste à vérifier
            current_planning: Objet planning actuel
            
        Returns:
            bool: True si le poste est déjà attribué, False sinon
        """
        # Vérifier dans le planning existant
        day = current_planning.get_day(date)
        if day:
            for slot in day.slots:
                if (slot.abbreviation == post_type and 
                    get_post_period(slot) + 1 == period):  # +1 car get_post_period renvoie 0, 1, 2
                    return True
        
        # Vérifier dans les post-attributions
        if date in self.post_attributions:
            for assignee, periods in self.post_attributions[date].items():
                if period in periods and periods[period] == post_type:
                    return True
        
        return False

    def show_post_attribution_menu(self, event, table, row, col, date, period, assignee):
        """
        Affiche le menu contextuel pour les post-attributions.
        
        Args:
            event: Événement de clic droit (position globale)
            table: Table sur laquelle le clic a été effectué
            row, col: Position de la cellule cliquée
            date: Date correspondant à la cellule
            period: Période (1: Matin, 2: Après-midi, 3: Soir)
            assignee: Nom du médecin ou CAT concerné
        """
        # Vérification des paramètres
        if not date:
            logger.error("Date invalide pour le menu contextuel")
            return
        
        if not period or period < 1 or period > 3:
            logger.error(f"Période invalide: {period}")
            return
        
        if not assignee:
            logger.error("Aucun assigné spécifié")
            return
        
        menu = QMenu(table)
        
        # Debug info
        logger.debug(f"Création du menu pour {assignee} le {date} période {period}")
        
        # Vérifier si un poste est déjà post-attribué à cette personne pour cette période
        is_already_post_attributed = False
        existing_post_type = None
        if date in self.post_attributions and assignee in self.post_attributions[date]:
            if period in self.post_attributions[date][assignee]:
                is_already_post_attributed = True
                existing_post_type = self.post_attributions[date][assignee][period]
        
        if is_already_post_attributed:
            # Option pour supprimer la post-attribution
            delete_action = menu.addAction(f"Supprimer le poste post-attribué ({existing_post_type})")
            delete_action.triggered.connect(
                lambda: self.remove_post_attribution(date, period, assignee, table)
            )
        else:
            # Déterminer le type de jour
            day_type = self._get_day_type(date)
            
            # Obtenir les postes disponibles pour cette période et ce type de jour
            available_posts = self._get_available_posts(date, period, day_type, assignee)
            
            logger.debug(f"Postes disponibles: {available_posts}")
            
            if available_posts:
                add_post_menu = menu.addMenu("Ajouter un poste post-attribué")
                for post_type in available_posts:
                    action = add_post_menu.addAction(post_type)
                    # Utiliser une closure pour capturer la valeur actuelle de post_type
                    action.triggered.connect(
                        lambda checked=False, pt=post_type: self.add_post_attribution(date, period, assignee, pt, table)
                    )
            else:
                no_posts_action = menu.addAction("Aucun poste disponible")
                no_posts_action.setEnabled(False)
        
        # Assurez-vous que event est bien une QPoint
        if isinstance(event, QPoint):
            menu.exec(event)
        else:
            # Tenter de convertir en QPoint ou utiliser une position par défaut
            try:
                menu.exec(event)
            except:
                logger.error(f"Type d'événement invalide pour exec: {type(event)}")
                # Tenter d'utiliser une position centrée sur l'écran
                from PyQt6.QtWidgets import QApplication
                screen = QApplication.primaryScreen().geometry()
                menu.exec(QPoint(screen.width() // 2, screen.height() // 2))

    def add_post_attribution(self, date, period, assignee, post_type, table):
        """
        Ajoute une post-attribution.
        
        Args:
            date: Date du poste
            period: Période (1: Matin, 2: Après-midi, 3: Soir)
            assignee: Médecin ou CAT assigné
            post_type: Type de poste
            table: Table à mettre à jour
        """
        logger.info(f"Tentative d'ajout de post-attribution: {date}, période {period}, {assignee}, {post_type}")
        
        # Vérification DIRECTE dans la structure post_attributions
        if date in self.post_attributions:
            if assignee in self.post_attributions[date]:
                if period in self.post_attributions[date][assignee]:
                    existing_post = self.post_attributions[date][assignee][period]
                    QMessageBox.warning(
                        table,
                        "Poste déjà attribué",
                        f"Un poste ({existing_post}) est déjà post-attribué à cette période. Supprimez-le d'abord."
                    )
                    return
        
        # Vérification SUPPLÉMENTAIRE dans le planning actuel
        day = self.main_window.planning.get_day(date)
        if day:
            for slot in day.slots:
                if (slot.assignee == assignee and get_post_period(slot) + 1 == period):
                    if hasattr(slot, 'is_post_attribution') and slot.is_post_attribution:
                        QMessageBox.warning(
                            table,
                            "Poste déjà attribué",
                            f"Un poste ({slot.abbreviation}) est déjà post-attribué à cette période. Supprimez-le d'abord."
                        )
                        return
        
        # Créer un slot temporaire pour la vérification des contraintes
        test_slot = self._create_timeslot_for_post(post_type, date)
        if not test_slot:
            QMessageBox.warning(
                table,
                "Erreur",
                f"Configuration introuvable pour le poste {post_type}"
            )
            return
        
        # Vérifier les contraintes
        current_person = next(
            (p for p in self.main_window.doctors + self.main_window.cats if p.name == assignee),
            None
        )
        if not current_person:
            QMessageBox.warning(
                table,
                "Erreur",
                f"Médecin ou CAT introuvable: {assignee}"
            )
            return
        
        # Vérifier les contraintes avec le planning temporaire
        warnings = self._check_constraints(current_person, date, test_slot)
        
        # Si des violations sont détectées, demander confirmation
        if warnings:
            warning_text = "Cette post-attribution ne respecte pas les contraintes suivantes :\n\n"
            warning_text += "\n".join(warnings)
            warning_text += "\n\nVoulez-vous continuer quand même ?"
            
            reply = QMessageBox.question(
                table,
                "Confirmation d'entorse aux contraintes",
                warning_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Ajouter la post-attribution
        if date not in self.post_attributions:
            self.post_attributions[date] = {}
        if assignee not in self.post_attributions[date]:
            self.post_attributions[date][assignee] = {}
        self.post_attributions[date][assignee][period] = post_type
        
        # Ajouter à l'historique
        timestamp = datetime.now()
        details = f"{assignee} - {post_type} - {date.strftime('%d/%m/%Y')} - Période {period}"
        self.history.append((timestamp, "Ajout post-attribution", details))
        
        # Marquer explicitement le slot comme post-attribution
        test_slot.is_post_attribution = True
        test_slot.assignee = assignee
        
        # Mettre à jour l'affichage
        self._update_planning_slot(date, assignee, post_type, test_slot)
        self._save_post_attributions()
        
        # Si le planning est affiché, rafraîchir la vue
        if hasattr(self.main_window, 'doctor_planning_view') and self.main_window.doctor_planning_view:
            self.main_window.doctor_planning_view.update_view(
                self.main_window.planning,
                self.main_window.doctors,
                self.main_window.cats
            )
        if hasattr(self.main_window, 'comparison_view') and self.main_window.comparison_view:
            self.main_window.comparison_view.update_comparison(preserve_selection=True)
        
        # Mettre à jour les statistiques
        if hasattr(self.main_window, 'update_stats_view'):
            self.main_window.update_stats_view()
            
    def clean_and_restore_post_attributions(self):
        """
        Nettoie toutes les post-attributions existantes et les restaure proprement.
        À appeler aux moments clés: après validation des weekends, après génération des semaines.
        """
        if not self.main_window.planning:
            logger.warning("Pas de planning disponible, impossible de nettoyer/restaurer les post-attributions")
            return
        
        logger.info("Nettoyage et restauration des post-attributions...")
        
        # 1. Sauvegarde forcée des post-attributions (par précaution)
        self._save_post_attributions()
        
        # 2. Suppression de tous les slots post-attribués existants
        for day in self.main_window.planning.days:
            slots_to_keep = []
            for slot in day.slots:
                if not hasattr(slot, 'is_post_attribution') or not slot.is_post_attribution:
                    slots_to_keep.append(slot)
            
            # Compter combien de slots ont été supprimés
            removed = len(day.slots) - len(slots_to_keep)
            if removed > 0:
                logger.info(f"Supprimé {removed} slots post-attribués pour le {day.date}")
            
            day.slots = slots_to_keep
        
        # 3. Restauration propre des post-attributions
        self._restore_slots_in_planning()
        
        logger.info("Nettoyage et restauration des post-attributions terminés")
            
    def remove_post_attribution(self, date, period, assignee, table):
        """
        Supprime une post-attribution.
        
        Args:
            date: Date du poste
            period: Période (1: Matin, 2: Après-midi, 3: Soir)
            assignee: Médecin ou CAT assigné
            table: Table à mettre à jour
        """
        print(f"Tentative de suppression pour {assignee}, date={date}, période={period}")
        
        # Vérifier si la post-attribution existe
        has_post_attr = False
        post_type = None
        
        if date in self.post_attributions:
            if assignee in self.post_attributions[date]:
                if period in self.post_attributions[date][assignee]:
                    has_post_attr = True
                    post_type = self.post_attributions[date][assignee][period]
        
        print(f"Post-attribution trouvée: {has_post_attr}, type={post_type}")
        
        if not has_post_attr or not post_type:
            print("Aucune post-attribution trouvée à supprimer")
            return
        
        # Supprimer du planning
        day = self.main_window.planning.get_day(date)
        if day:
            slots_to_remove = []
            
            for slot in day.slots:
                # Recherche simple par assigné et type de poste
                if slot.assignee == assignee and slot.abbreviation == post_type:
                    print(f"Slot trouvé à supprimer: {slot.abbreviation}")
                    slots_to_remove.append(slot)
            
            print(f"Nombre de slots à supprimer: {len(slots_to_remove)}")
            
            for slot in slots_to_remove:
                day.slots.remove(slot)
        
        # Supprimer de la structure de données
        del self.post_attributions[date][assignee][period]
        if not self.post_attributions[date][assignee]:
            del self.post_attributions[date][assignee]
        if not self.post_attributions[date]:
            del self.post_attributions[date]
        
        # Ajouter à l'historique
        timestamp = datetime.now()
        details = f"{assignee} - {post_type} - {date.strftime('%d/%m/%Y')} - Période {period}"
        self.history.append((timestamp, "Suppression post-attribution", details))
        
        # Enregistrer les modifications
        self._save_post_attributions()
        
        # Mettre à jour les vues
        if hasattr(self.main_window, 'doctor_planning_view') and self.main_window.doctor_planning_view:
            self.main_window.doctor_planning_view.update_view(
                self.main_window.planning,
                self.main_window.doctors,
                self.main_window.cats
            )
        if hasattr(self.main_window, 'comparison_view') and self.main_window.comparison_view:
            self.main_window.comparison_view.update_comparison(preserve_selection=True)
        
        # Mettre à jour les statistiques
        if hasattr(self.main_window, 'update_stats_view'):
            self.main_window.update_stats_view()
    
    def _get_day_type(self, date_to_check):
        """Détermine le type de jour (semaine, samedi, dimanche/férié)."""
        if self.calendar.is_holiday(date_to_check) or date_to_check.weekday() == 6:
            return "sunday_holiday"
        elif date_to_check.weekday() == 5:
            return "saturday"
        return "weekday"
    
    def _get_available_posts(self, date, period_index, day_type, assignee):
        """
        Retourne les postes disponibles pour une période donnée.
        
        Args:
            date: Date à vérifier
            period_index: Index de période (0: Matin, 1: Après-midi, 2: Soir) - IMPORTANT: maintenant 0-based
            day_type: Type de jour ('weekday', 'saturday', 'sunday_holiday')
            assignee: Nom du médecin ou CAT
            
        Returns:
            list: Liste des types de postes disponibles
        """
        available_posts = []
        
        # Vérifier si l'assigné est un médecin ou un CAT
        is_cat = any(cat.name == assignee for cat in self.main_window.cats)
        
        # Logs pour déboguer
        logger.debug(f"Recherche de postes pour {assignee} le {date} (période index={period_index}, type {day_type})")
        logger.debug(f"Est un CAT: {is_cat}")
        
        # Définir les listes de postes par période et type de jour
        # Ces listes doivent contenir TOUS les types de postes possibles
        post_types_by_period = {
            # Jour de semaine (lundi au vendredi)
            "weekday": {
                0: ["MM", "CM", "HM", "SM", "RM", "ML", "MC"],  # Matin (index 0)
                1: ["CA", "HA", "SA", "RA", "CT", "AL", "AC"],  # Après-midi (index 1)
                2: ["CS", "HS", "SS", "RS", "NC", "NM", "NL", "NA"]  # Soir/Nuit (index 2)
            },
            # Samedi
            "saturday": {
                0: ["CM", "HM", "ML", "MC"],  # Matin (index 0)
                1: ["CA", "HA", "SA", "RA", "AL", "AC"],  # Après-midi (index 1)
                2: ["CS", "HS", "SS", "RS", "NA", "NM", "NL"]  # Soir/Nuit (index 2)
            },
            # Dimanche et jours fériés
            "sunday_holiday": {
                0: ["CM", "HM", "SM", "RM", "ML", "MC"],  # Matin (index 0)
                1: ["CA", "HA", "SA", "RA", "AL", "AC"],  # Après-midi (index 1)
                2: ["CS", "HS", "SS", "RS", "NA", "NM", "NL"]  # Soir/Nuit (index 2)
            }
        }
        
        # Obtenir la liste des postes pour la période et le type de jour demandés
        possible_posts = post_types_by_period.get(day_type, {}).get(period_index, [])
        
        logger.debug(f"Postes possibles pour période index {period_index}, jour {day_type}: {possible_posts}")
        
        # Pour chaque type de poste possible
        for post_type in possible_posts:
            # Vérifier si le poste est compatible avec l'assigné (médecin/CAT)
            if is_cat:
                # Si l'assigné est un CAT, vérifier si les CATs peuvent prendre ce poste
                post_details = self.post_manager.get_post_details(post_type, day_type)
                if not post_details:
                    logger.warning(f"Détails introuvables pour le poste {post_type}")
                    continue
                    
                # Pour simplifier, on ajoute tous les postes pour les CATs
                # La vérification des contraintes se fera ailleurs
                
            # Vérifier uniquement si le poste est déjà attribué
            # IMPORTANT: Convertir period_index en période 1-based pour is_post_attributed
            ui_period = period_index + 1
            if not self.is_post_attributed(date, ui_period, post_type, self.main_window.planning):
                # Récupérer les détails du poste pour vérifier sa validité
                post_details = self.post_manager.get_post_details(post_type, day_type)
                if post_details:
                    available_posts.append(post_type)
                    logger.debug(f"Ajout du poste {post_type} aux postes disponibles")
        
        # Ajouter les postes personnalisés
        if hasattr(self.main_window, 'data_persistence') and self.main_window.data_persistence:
            custom_posts = self.main_window.data_persistence.load_custom_posts() or {}
            
            for name, custom_post in custom_posts.items():
                # Vérifier si le poste est compatible avec le type de personne et le jour
                is_compatible = False
                if is_cat:
                    if custom_post.assignment_type in ['cats', 'both']:
                        is_compatible = True
                else:  # Médecin
                    if custom_post.assignment_type in ['doctors', 'both']:
                        is_compatible = True
                
                if is_compatible and day_type in custom_post.day_types:
                    post_start_hour = custom_post.start_time.hour
                    
                    # Vérifier si le poste correspond à la période demandée
                    is_matching = False
                    if period_index == 0 and 7 <= post_start_hour < 13:  # Matin (index 0)
                        is_matching = True
                    elif period_index == 1 and 13 <= post_start_hour < 18:  # Après-midi (index 1)
                        is_matching = True
                    elif period_index == 2 and (post_start_hour >= 18 or post_start_hour < 7):  # Soir/Nuit (index 2)
                        is_matching = True
                    
                    # IMPORTANT: Convertir period_index en période 1-based pour is_post_attributed
                    ui_period = period_index + 1
                    if is_matching and not self.is_post_attributed(date, ui_period, name, self.main_window.planning):
                        available_posts.append(name)
                        logger.debug(f"Ajout du poste personnalisé {name} aux postes disponibles")
        
        logger.debug(f"Postes disponibles finaux: {available_posts}")
        return sorted(available_posts)
    
    def _create_timeslot_for_post(self, post_type, date):
        """
        Crée un TimeSlot pour un type de poste donné.
        
        Args:
            post_type: Type de poste
            date: Date du poste
            
        Returns:
            TimeSlot: Objet TimeSlot créé, ou None si impossible
        """
        day_type = self._get_day_type(date)
        
        # Vérifier si c'est un poste personnalisé
        if hasattr(self.main_window, 'data_persistence') and self.main_window.data_persistence:
            custom_posts = self.main_window.data_persistence.load_custom_posts() or {}
            if post_type in custom_posts:
                custom_post = custom_posts[post_type]
                slot = TimeSlot(
                    start_time=datetime.combine(date, custom_post.start_time),
                    end_time=datetime.combine(date, custom_post.end_time),
                    site="Custom",
                    slot_type="Custom",
                    abbreviation=post_type
                )
                # S'assurer que l'attribut is_post_attribution est explicitement défini
                slot.is_post_attribution = True
                return slot
        
        # Poste standard
        post_details = self.post_manager.get_post_details(post_type, day_type)
        if post_details:
            slot = TimeSlot(
                start_time=datetime.combine(date, post_details['start_time']),
                end_time=datetime.combine(date, post_details['end_time']),
                site=post_details['site'],
                slot_type="Standard",
                abbreviation=post_type
            )
            # S'assurer que l'attribut is_post_attribution est explicitement défini
            slot.is_post_attribution = True
            return slot
        
        return None
    
    def _check_constraints(self, person, date, new_slot):
        """
        Vérifie toutes les contraintes et retourne la liste des violations.
        
        Args:
            person: Médecin ou CAT concerné
            date: Date du poste
            new_slot: Slot à vérifier
            
        Returns:
            list: Liste des violations de contraintes
        """
        warnings = []
        
        if not self.constraints or not self.main_window.planning:
            return warnings
        
        planning = self.main_window.planning
        
        # Vérifier les desiderata
        new_slot_period = self._get_period_from_slot(new_slot)
        for des in person.desiderata:
            if des.start_date <= date <= des.end_date and des.period == new_slot_period:
                priority = getattr(des, 'priority', 'primary')
                warnings.append(f"Non respect d'un desiderata {priority}")
        
        # Vérifier le nombre maximum de postes par jour
        if not self.constraints.check_max_posts_per_day(person, date, new_slot, planning):
            warnings.append("Dépasse le maximum de 2 postes par jour")
        
        # Autres contraintes
        if not self.constraints.check_nl_constraint(person, date, new_slot, planning):
            warnings.append("Entorse aux règles NL")
            
        if not self.constraints.check_nm_na_constraint(person, date, new_slot, planning):
            warnings.append("Entorse aux règles NM/NA")
            
        if not self.constraints.check_morning_after_night_shifts(person, date, new_slot, planning):
            warnings.append("Entorse aux règles de repos après poste de nuit")
            
        if not self.constraints.check_consecutive_night_shifts(person, date, new_slot, planning):
            warnings.append("Entorse aux règles de nuits consécutives")
            
        if not self.constraints.check_consecutive_working_days(person, date, new_slot, planning):
            warnings.append("Entorse aux règles de jours consécutifs")
        
        return warnings
    
    def _get_period_from_slot(self, slot):
        """
        Détermine la période (1, 2 ou 3) d'un TimeSlot en fonction de son heure de début.
        
        Args:
            slot: TimeSlot à vérifier
            
        Returns:
            int: 1 pour Matin, 2 pour Après-midi, 3 pour Soir/Nuit
        """
        start_hour = slot.start_time.hour
        
        if 7 <= start_hour < 13:
            return PostPeriod.MORNING  # 1: Matin
        elif 13 <= start_hour < 18:
            return PostPeriod.AFTERNOON  # 2: Après-midi
        else:
            return PostPeriod.EVENING  # 3: Soir/Nuit
    
    def _update_planning_slot(self, date, assignee, post_type, slot):
        """
        Ajoute ou met à jour un slot dans le planning.
        
        Args:
            date: Date du poste
            assignee: Médecin ou CAT assigné
            post_type: Type de poste
            slot: TimeSlot à ajouter
        """
        # Vérifier si le planning existe
        if not self.main_window.planning:
            logger.error("Impossible de mettre à jour le planning: planning non initialisé")
            return
        
        # Récupérer ou créer le jour dans le planning
        day = self.main_window.planning.get_day(date)
        if not day:
            logger.error(f"Jour introuvable dans le planning: {date}")
            return
        
        # Définir l'assigné du slot
        slot.assignee = assignee
        
        # S'assurer que l'attribut is_post_attribution est défini
        if not hasattr(slot, 'is_post_attribution'):
            slot.is_post_attribution = True
        else:
            # Vérifier que l'attribut est bien True
            slot.is_post_attribution = True
        
        # Log de débogage
        logger.debug(f"Ajout d'un slot post-attribué: {post_type} pour {assignee} le {date}")
        logger.debug(f"Attribut is_post_attribution: {getattr(slot, 'is_post_attribution', 'Non défini')}")
        
        # Ajouter le slot au jour
        day.slots.append(slot)
    
    def _save_post_attributions(self):
        """Sauvegarde les post-attributions dans un fichier."""
        if hasattr(self.main_window, 'data_persistence') and self.main_window.data_persistence:
            try:
                self.main_window.data_persistence.save_post_attributions(self.post_attributions)
                logger.info("Post-attributions sauvegardées avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde des post-attributions: {e}")
    
    def load_post_attributions(self):
        """Charge les post-attributions depuis un fichier sans les restaurer directement."""
        if hasattr(self.main_window, 'data_persistence') and self.main_window.data_persistence:
            try:
                loaded_data = self.main_window.data_persistence.load_post_attributions()
                if loaded_data:
                    self.post_attributions = loaded_data
                    logger.info("Post-attributions chargées avec succès")
                    
                    # Ne plus restaurer automatiquement les slots dans le planning ici
                    # La restauration sera faite explicitement aux moments appropriés
                    
                    return True
            except Exception as e:
                logger.error(f"Erreur lors du chargement des post-attributions: {e}")
                return False
        
        return False

    def _restore_slots_in_planning(self):
        """Restaure les slots de post-attribution dans le planning."""
        if not self.main_window.planning:
            logger.warning("Impossible de restaurer les slots: planning non initialisé")
            return
        
        logger.info("Restauration des slots de post-attribution...")
        slots_added = 0
        slots_skipped = 0
        
        # D'abord, nettoyage complet de tous les slots post-attribués existants
        for day in self.main_window.planning.days:
            slots_to_keep = []
            for slot in day.slots:
                if not hasattr(slot, 'is_post_attribution') or not slot.is_post_attribution:
                    slots_to_keep.append(slot)
                else:
                    logger.debug(f"Suppression d'un slot post-attribué existant: {slot.abbreviation} pour {slot.assignee} le {day.date}")
            
            # Compter combien de slots ont été supprimés
            removed = len(day.slots) - len(slots_to_keep)
            if removed > 0:
                logger.info(f"Supprimé {removed} slots post-attribués pour le {day.date}")
            
            day.slots = slots_to_keep
        
        # Ensuite, ajout des post-attributions
        for date, assignees in self.post_attributions.items():
            for assignee, periods in assignees.items():
                for period, post_type in periods.items():
                    # Récupérer le jour du planning
                    day = self.main_window.planning.get_day(date)
                    if not day:
                        logger.warning(f"Jour {date} non trouvé dans le planning, impossible de restaurer le poste")
                        continue
                    
                    # Créer un nouveau slot
                    slot = self._create_timeslot_for_post(post_type, date)
                    if slot:
                        slot.assignee = assignee
                        slot.is_post_attribution = True
                        day.slots.append(slot)
                        slots_added += 1
                        logger.info(f"Slot restauré: {post_type} pour {assignee} le {date}")
                    else:
                        logger.warning(f"Impossible de créer un slot pour {post_type} le {date}")
        
        logger.info(f"{slots_added} slots de post-attribution restaurés, {slots_skipped} slots existants ignorés")

    
    def get_history(self):
        """Retourne l'historique des post-attributions."""
        return self.history
    
    def clear_history(self):
        """Efface l'historique des post-attributions."""
        self.history = []
    
    def get_formatted_history(self):
        """Retourne l'historique formaté pour l'affichage."""
        formatted_history = []
        for timestamp, action_type, details in self.history:
            formatted_entry = f"{timestamp.strftime('%d/%m %H:%M')} - {action_type} - {details}"
            formatted_history.append(formatted_entry)
        return formatted_history
