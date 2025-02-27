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
        Vérifie si une assignation est possible en respectant les contraintes.
        Les pré-attributions sont considérées comme fixes et ne sont pas comptées
        dans les vérifications de contraintes.
        """
        # Ne pas vérifier les contraintes pour les slots déjà pré-attribués
        if hasattr(slot, 'is_pre_attributed') and slot.is_pre_attributed:
            return True
        
        # Pour les nouveaux slots, vérifier toutes les contraintes normales
        # en excluant les slots pré-attribués des vérifications
        return all([
            self.check_nl_constraint(assignee, date, slot, planning),
            self.check_nm_na_constraint(assignee, date, slot, planning),
            self.check_time_overlap(assignee, date, slot, planning),
            self.check_max_posts_per_day(assignee, date, slot, planning),
            self.check_desiderata_constraint(assignee, date, slot, planning, respect_secondary),
            self.check_morning_after_night_shifts(assignee, date, slot, planning),
            self.check_consecutive_night_shifts(assignee, date, slot, planning),
            self.check_consecutive_working_days(assignee, date, slot, planning)
        ])

    def _is_pre_attributed_slot(self, slot: TimeSlot) -> bool:
        """Vérifie si un slot est pré-attribué"""
        return hasattr(slot, 'is_pre_attributed') and slot.is_pre_attributed

    def can_pre_attribute(self, assignee: Union[Doctor, CAT], date: date, 
                         slot: TimeSlot, planning: Planning) -> bool:
        """
        Méthode spécifique pour vérifier si une pré-attribution est possible.
        Ne vérifie que le chevauchement horaire.
        
        Args:
            assignee: Le médecin ou CAT
            date: La date de la pré-attribution
            slot: Le poste à pré-attribuer
            planning: Le planning en cours
            
        Returns:
            bool: True si la pré-attribution est possible, False sinon
        """
        return self.check_time_overlap(assignee, date, slot, planning)

    def check_morning_after_night_shifts(self, assignee: Union[Doctor, CAT], date: date, 
                                    slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie les contraintes entre postes de nuit et postes du matin avec
        une exception pour les postes du matin commençant à 9h attribués via les
        combinaisons du générateur de planning.
        
        Règles :
        1. Pas de poste du matin après un poste tardif ou de nuit, SAUF
        si le poste du matin commence à 9h et fait partie d'une combinaison reconnue
        2. Pas de poste tardif si un poste du matin est prévu le lendemain
        
        Args:
            assignee: Le médecin ou CAT à vérifier
            date: Date du slot à attribuer
            slot: Slot à vérifier
            planning: Planning en cours
            
        Returns:
            bool: True si l'attribution est possible, False sinon
        """
        yesterday = planning.get_day(date - timedelta(days=1))
        tomorrow = planning.get_day(date + timedelta(days=1))
        
        # Liste des postes du matin commençant à 9h (peuvent être exceptionnellement attribués)
        nine_am_posts = ['CM', 'HM']  # Uniquement ces postes commencent à 9h
        
        # Liste des combinaisons reconnues par le générateur
        weekday_combinations = ['CMCA', 'HMHA', 'CMCS', 'HMHS']  # Uniquement les combinaisons avec postes à 9h
        weekend_combinations = ['CMCA', 'HMHA', 'CMCS', 'HMHS','SMSA','RMRA']  # Uniquement les combinaisons avec postes à 9h
        
        # CAS 1: On veut attribuer un poste du matin
        if slot.abbreviation in self.morning_posts:
            if yesterday:
                # Vérifier si la personne avait un poste tardif la veille
                had_late_post = False
                for prev_slot in yesterday.slots:
                    if prev_slot.assignee == assignee.name:
                        if (prev_slot.abbreviation in self.late_posts or 
                            prev_slot.end_time.hour >= 23):
                            had_late_post = True
                            break
                
                if had_late_post:
                    # Exception 1: Si c'est un poste commençant à 9h
                    if slot.abbreviation in nine_am_posts:
                        # Vérifier si le slot a un attribut indiquant qu'il fait partie d'une combinaison
                        if hasattr(slot, 'is_part_of_combination') and slot.is_part_of_combination:
                            return True
                        
                        # Ou vérifier si ce poste fait déjà partie d'une combinaison par déduction
                        day = planning.get_day(date)
                        if day:
                            # Pour chaque combinaison possible
                            all_combinations = weekday_combinations + weekend_combinations
                            for combo in all_combinations:
                                # Si le poste actuel est la première partie de la combinaison
                                if combo.startswith(slot.abbreviation):
                                    second_post = combo[2:4]  # Extraire le code du deuxième poste
                                    # Vérifier si le deuxième poste est déjà attribué ou va être attribué
                                    if any(s.abbreviation == second_post and s.assignee == assignee.name 
                                        for s in day.slots):
                                        return True
                                # Si le poste actuel est la deuxième partie de la combinaison
                                elif combo[2:4] == slot.abbreviation:
                                    first_post = combo[0:2]  # Extraire le code du premier poste
                                    # Vérifier si le premier poste est déjà attribué
                                    if any(s.abbreviation == first_post and s.assignee == assignee.name 
                                        for s in day.slots):
                                        return True
                    
                    # Si ce n'est pas un poste à 9h ou pas attribué en combinaison, refuser
                    return False

        # CAS 2: On veut attribuer un poste tardif
        elif slot.abbreviation in self.late_posts:
            if tomorrow:
                # Vérifier si la personne a un poste du matin le lendemain
                has_morning_post = False
                morning_post_abbr = None
                
                for next_slot in tomorrow.slots:
                    if (next_slot.assignee == assignee.name and 
                        next_slot.abbreviation in self.morning_posts):
                        has_morning_post = True
                        morning_post_abbr = next_slot.abbreviation
                        break
                
                if has_morning_post:
                    # Si le poste du matin commence à 9h et fait partie d'une combinaison,
                    # on peut autoriser le poste tardif la veille
                    if morning_post_abbr in nine_am_posts:
                        if hasattr(next_slot, 'is_part_of_combination') and next_slot.is_part_of_combination:
                            return True
                        
                        # Vérifier si ce poste fait partie d'une combinaison par déduction
                        tomorrow_day = planning.get_day(date + timedelta(days=1))
                        if tomorrow_day:
                            all_combinations = weekday_combinations + weekend_combinations
                            for combo in all_combinations:
                                if combo.startswith(morning_post_abbr) or combo[2:4] == morning_post_abbr:
                                    # Vérifier si l'autre partie de la combinaison est attribuée
                                    other_post = combo[2:4] if combo.startswith(morning_post_abbr) else combo[0:2]
                                    if any(s.abbreviation == other_post and s.assignee == assignee.name 
                                        for s in tomorrow_day.slots):
                                        return True
                    
                    # Sinon, on refuse le poste tardif
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
    
    def check_nm_na_constraint(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie les contraintes pour les NM et NA:
        - Exclusivité: un NM ou NA ne peut pas être attribué s'il y a déjà un autre poste le même jour
        - Inversement, aucun autre poste ne peut être attribué si un NM ou NA est déjà présent
        
        Note: La vérification de chevauchement temporel est déjà gérée par check_time_overlap
        
        Args:
            assignee: Le médecin ou CAT à vérifier
            date: Date du slot
            slot: Slot à vérifier
            planning: Planning en cours
            
        Returns:
            bool: True si l'attribution est possible, False sinon
        """
        day = planning.get_day(date)
        if day:
            # Si le nouveau poste est NM ou NA, vérifier qu'aucun autre poste n'est assigné ce jour-là
            if slot.abbreviation in ['NM', 'NA']:
                return not any(s.assignee == assignee.name for s in day.slots)
            
            # Si un NM ou NA est déjà assigné ce jour-là, aucun autre poste ne peut être ajouté
            if any(s.abbreviation in ['NM', 'NA'] and s.assignee == assignee.name for s in day.slots):
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

    def can_pre_attribute(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot, planning: Planning) -> bool:
        """Vérifie uniquement le chevauchement horaire pour les pré-attributions"""
        return self.check_time_overlap(assignee, date, slot, planning)

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
                                planning: Planning, respect_secondary: bool = True,
                                is_pre_attribution: bool = False) -> bool:
        """
        Vérifie les contraintes de desiderata en tenant compte uniquement de la période concernée.
        
        Args:
            assignee: Médecin ou CAT à vérifier
            date: Date du slot
            slot: Slot à vérifier
            planning: Planning en cours
            respect_secondary: Si False, ignore les desideratas secondaires
            is_pre_attribution: Si True, ignore toutes les contraintes de desiderata
            
        Returns:
            bool: True si l'attribution est possible
        """
        # Les pré-attributions ignorent les contraintes de desiderata
        if is_pre_attribution:
            return True
            
        # Déterminer la période du slot à attribuer (1: matin, 2: après-midi, 3: soir/nuit)
        slot_period = self._get_slot_period(slot)
        
        # Vérification des desideratas primaires (toujours stricts)
        for desiderata in assignee.desiderata:
            if not hasattr(desiderata, 'priority'):  # Rétrocompatibilité
                priority = "primary"
            else:
                priority = desiderata.priority

            # Vérifier si le desiderata s'applique à cette date et à cette période précise
            if (priority == "primary" and 
                desiderata.start_date <= date <= desiderata.end_date and 
                desiderata.period == slot_period):
                return False

        # Si respect_secondary est False, on ignore les desideratas secondaires
        if not respect_secondary:
            return True

        # Vérification des desideratas secondaires avec la même logique de période
        for desiderata in assignee.desiderata:
            if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                desiderata.start_date <= date <= desiderata.end_date and 
                desiderata.period == slot_period):
                return False

        return True
        
    def _get_slot_period(self, slot: TimeSlot) -> int:
        """
        Détermine la période d'un slot (1: matin, 2: après-midi, 3: soir/nuit)
        
        Args:
            slot: Le TimeSlot à analyser
            
        Returns:
            int: période (1, 2 ou 3)
        """
        # Convertir en time si nécessaire
        if isinstance(slot.start_time, datetime):
            start_hour = slot.start_time.hour
        else:
            start_hour = slot.start_time.hour
        
        # Définition des périodes
        if 7 <= start_hour < 13:
            return 1  # Matin
        elif 13 <= start_hour < 18:
            return 2  # Après-midi
        else:
            return 3  # Soir/nuit