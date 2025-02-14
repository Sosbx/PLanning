# © 2024 HILAL Arkane. Tous droits réservés.
# # core/Constantes/Constaints.py
from datetime import datetime, timedelta, date,time
from typing import Union, Tuple
from core.Constantes.models import Doctor, CAT, TimeSlot, DayPlanning, Planning
import logging

logger = logging.getLogger(__name__)

class PlanningConstraints:
    def __init__(self):
        # Liste des postes de matin à protéger
        self.morning_posts = ['ML', 'MC', 'MM', 'CM', 'HM', 'SM', 'RM']
        # Liste des postes tardifs
        self.late_posts = ['SS', 'RS', 'HS', 'NC', 'NM', 'NL', 'NA']

    def can_assign_to_assignee(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, 
                             planning: Planning, respect_secondary: bool = True) -> bool:
        """
        Vérifie si une assignation est possible en respectant toutes les contraintes.
        """
        return all([
            self.check_nl_constraint(assignee, date, slot, planning),
            self.check_nm_constraint(assignee, date, slot, planning),
            self.check_nm_na_constraint(assignee, date, slot, planning),
            self.check_time_overlap(assignee, date, slot, planning),
            self.check_max_posts_per_day(assignee, date, slot, planning),
            self.check_desiderata_constraint(assignee, date, slot, planning, respect_secondary),
            self.check_morning_after_night_shifts(assignee, date, slot, planning),  # Nouvelle contrainte unifiée
            self.check_consecutive_night_shifts(assignee, date, slot, planning),
            self.check_consecutive_working_days(assignee, date, slot, planning)
        ])

    def check_morning_after_night_shifts(self, assignee: Union[Doctor, CAT], date: date, 
                                       slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie les contraintes entre postes de nuit et postes du matin.
        Règles :
        1. Pas de poste du matin après un NM ou autre poste tardif
        2. Pas de NM ou poste tardif si poste du matin le lendemain
        """
        yesterday = planning.get_day(date - timedelta(days=1))
        tomorrow = planning.get_day(date + timedelta(days=1))

        # CAS 1: On veut attribuer un poste du matin
        if slot.abbreviation in self.morning_posts:
            if yesterday:
                # Vérifier si la personne avait un poste tardif la veille
                for prev_slot in yesterday.slots:
                    if prev_slot.assignee == assignee.name:
                        if (prev_slot.abbreviation in self.late_posts or 
                            prev_slot.end_time.hour >= 23):
                            return False

        # CAS 2: On veut attribuer un poste tardif
        elif slot.abbreviation in self.late_posts:
            if tomorrow:
                # Vérifier si la personne a un poste du matin le lendemain
                for next_slot in tomorrow.slots:
                    if (next_slot.assignee == assignee.name and 
                        next_slot.abbreviation in self.morning_posts):
                        return False

        return True


    def check_nl_constraint(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie les contraintes pour les NL:
        - Aucun poste le même jour si c'est un NL
        - Pas de NL la veille
        - Pas de poste le lendemain si c'est un NL

        Args:
            assignee: Le médecin ou CAT à vérifier
            date: Date du slot
            slot: Slot à vérifier
            planning: Planning en cours

        Returns:
            bool: True si l'attribution est possible, False sinon
        """
        today = planning.get_day(date)
        yesterday = planning.get_day(date - timedelta(days=1))
        tomorrow = planning.get_day(date + timedelta(days=1))

        # Si on veut attribuer un NL
        if slot.abbreviation == "NL":
            # Vérifier qu'il n'y a aucun autre poste ce jour-là
            if today:
                if any(s.assignee == assignee.name for s in today.slots):
                    return False
            # Vérifier qu'il n'y a pas de poste le lendemain
            if tomorrow:
                if any(s.assignee == assignee.name for s in tomorrow.slots):
                    return False
        
        # Dans tous les cas, vérifier qu'il n'y a pas de NL la veille
        if yesterday:
            if any(s.assignee == assignee.name and s.abbreviation == "NL" for s in yesterday.slots):
                return False
                
        # Dans tous les cas, vérifier qu'il n'y a pas déjà un NL ce jour-là
        if today:
            if any(s.assignee == assignee.name and s.abbreviation == "NL" for s in today.slots):
                return False

        return True
    
    def check_nm_constraint(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        today = planning.get_day(date)
        tomorrow = planning.get_day(date + timedelta(days=1))
        
        if today:
            for other_slot in today.slots:
                if other_slot.assignee == assignee.name:
                    if (slot.abbreviation == 'NM' or other_slot.abbreviation == 'NM') and \
                    (slot.start_time < other_slot.end_time and slot.end_time > other_slot.start_time):
                        return False
        
        if tomorrow and slot.abbreviation == 'NM':
            for other_slot in tomorrow.slots:
                if other_slot.assignee == assignee.name:
                    if slot.end_time > other_slot.start_time:
                        return False
        
        return True
    
    def check_nm_na_constraint(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        day = planning.get_day(date)
        if day:
            # Si le nouveau poste est NM, vérifier qu'aucun autre poste n'est assigné ce jour-là
            if slot.abbreviation == 'NM':
                return not any(s.assignee == assignee.name for s in day.slots)
            
            # Si un NM est déjà assigné ce jour-là, aucun autre poste ne peut être ajouté
            if any(s.abbreviation == 'NM' and s.assignee == assignee.name for s in day.slots):
                return False
        
        return True

  
    
    def check_consecutive_night_shifts(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie si l'attribution d'un poste de soir ou de nuit respecte la limite de 4 jours consécutifs.
        
        Args:
            assignee: Le médecin ou CAT à qui on veut attribuer le poste
            date: La date du poste
            slot: Le poste à attribuer
            planning: Le planning en cours
            
        Returns:
            bool: True si l'attribution est possible, False sinon
        """
        # Liste des postes considérés comme soir ou nuit
        evening_night_posts = ['CS', 'HS', 'RS', 'SS', 'NC', 'NM', 'NL', 'NA']
        
        # Vérifier si le poste actuel est un poste de soir ou nuit
        if slot.abbreviation in evening_night_posts:
            count = 0
            # Vérifier les 4 jours précédents
            for i in range(1, 5):
                prev_day = planning.get_day(date - timedelta(days=i))
                if prev_day:
                    # Vérifier si le médecin avait un poste de soir/nuit
                    has_evening_night = any(
                        s.assignee == assignee.name and s.abbreviation in evening_night_posts 
                        for s in prev_day.slots
                    )
                    if has_evening_night:
                        count += 1
                    else:
                        break  # On s'arrête dès qu'on trouve un jour sans poste soir/nuit
                        
            # Si on a déjà 4 jours consécutifs, on refuse le nouveau poste
            return count < 4
            
        return True  # On autorise si ce n'est pas un poste de soir/nuit

    def check_consecutive_working_days(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        count = 0
        for i in range(6):  # Vérifier les 6 jours précédents
            prev_day = planning.get_day(date - timedelta(days=i))
            if prev_day:
                if any(s.assignee == assignee.name for s in prev_day.slots):
                    count += 1
                else:
                    break
        return count < 6

    def check_time_overlap(self, assignee: Union[Doctor, CAT], current_date: date, 
                            slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie qu'il n'y a pas de chevauchement horaire avec d'autres slots.
        
        Args:
            assignee: Le médecin ou CAT à vérifier
            current_date: La date du slot
            slot: Le slot à vérifier
            planning: Le planning en cours
            
        Returns:
            bool: True si pas de chevauchement, False sinon
        """
        try:
            day = planning.get_day(current_date)
            if not day:
                return True

            def ensure_time(t: Union[time, datetime]) -> time:
                """S'assure que l'objet est un time."""
                if isinstance(t, datetime):
                    return t.time()
                return t

            def to_datetime_range(target_date: date, check_slot: TimeSlot) -> Tuple[datetime, datetime]:
                """Convertit un slot en plage datetime en gérant les cas spéciaux."""
                if check_slot.abbreviation == "CT":
                    # CT a des horaires fixes
                    start_time = time(10, 0)
                    end_time = time(15, 59)
                else:
                    # Convertir en time si nécessaire
                    start_time = ensure_time(check_slot.start_time)
                    end_time = ensure_time(check_slot.end_time)

                # Création des datetime
                start = datetime.combine(target_date, start_time)
                if end_time < start_time:  # Passage minuit
                    end = datetime.combine(target_date + timedelta(days=1), end_time)
                else:
                    end = datetime.combine(target_date, end_time)
                    
                return start, end

            try:
                # Convertir le nouveau slot
                slot_start, slot_end = to_datetime_range(current_date, slot)

                # Vérifier les chevauchements avec les slots existants
                for existing_slot in day.slots:
                    if existing_slot.assignee == assignee.name:
                        try:
                            existing_start, existing_end = to_datetime_range(current_date, existing_slot)
                            
                            # Vérification du chevauchement
                            if (slot_start < existing_end and slot_end > existing_start):
                                logger.debug(f"Chevauchement détecté pour {assignee.name} le {current_date}:")
                                logger.debug(f"  Slot existant: {existing_slot.abbreviation} "
                                        f"({existing_start.strftime('%H:%M')}-"
                                        f"{existing_end.strftime('%H:%M')})")
                                logger.debug(f"  Nouveau slot: {slot.abbreviation} "
                                        f"({slot_start.strftime('%H:%M')}-"
                                        f"{slot_end.strftime('%H:%M')})")
                                return False
                        except Exception as slot_error:
                            logger.error(f"Erreur avec le slot existant: {slot_error}")
                            return False

                return True

            except Exception as conversion_error:
                logger.error(f"Erreur lors de la conversion des temps: {conversion_error}")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la vérification du chevauchement: {e}")
            return False  # Par sécurité

    def check_max_posts_per_day(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        day = planning.get_day(date)
        if day:
            assigned_posts = sum(1 for s in day.slots if s.assignee == assignee.name)
            # On vérifie si le nombre de postes déjà assignés plus le nouveau poste dépasse 2
            return assigned_posts + 1 <= 2
        return True

    def check_desiderata_constraint(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, 
                                    planning: Planning, respect_secondary: bool = True) -> bool:
        """
        Vérifie les contraintes de desiderata.
        Args:
            assignee: Médecin ou CAT à vérifier
            date: Date du slot
            slot: Slot à vérifier
            planning: Planning en cours
            respect_secondary: Si False, ignore les desideratas secondaires
        Returns:
            bool: True si l'attribution est possible
        """
        # Vérification des desideratas primaires (toujours stricts)
        for desiderata in assignee.desiderata:
            if not hasattr(desiderata, 'priority'):  # Rétrocompatibilité
                priority = "primary"
            else:
                priority = desiderata.priority

            if priority == "primary":
                if (desiderata.start_date <= date <= desiderata.end_date and 
                    desiderata.overlaps_with_slot(slot)):
                    return False

        # Si respect_secondary est False, on ignore les desideratas secondaires
        if not respect_secondary:
            return True

        # Vérification des desideratas secondaires
        for desiderata in assignee.desiderata:
            if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                desiderata.start_date <= date <= desiderata.end_date and 
                desiderata.overlaps_with_slot(slot)):
                return False

        return True
    
   