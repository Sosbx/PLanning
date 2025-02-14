# © 2024 HILAL Arkane. Tous droits réservés.
# core/constantes/QuotaTracking.py

from typing import Dict, List, Optional, Union, Tuple
from datetime import date, time
from collections import defaultdict
from core.Constantes.data_persistence import DataPersistence
import logging
from .models import Doctor, CAT, Planning, TimeSlot
from .day_type import DayType
from workalendar.europe import France

logger = logging.getLogger(__name__)

class QuotaCounter:
    """Composant pour le suivi des compteurs de quotas par personne."""
    def __init__(self, person_name: str):
        self.person_name = person_name
        self.posts = defaultdict(int)      # Compteurs par type de poste
        self.groups = defaultdict(int)     # Compteurs par groupe
        self.combinations = defaultdict(int)  # Compteurs par combinaison

    def increment_post(self, post_type: str):
        """Incrémente le compteur d'un type de poste."""
        self.posts[post_type] += 1
        
    def increment_group(self, group: str):
        """Incrémente le compteur d'un groupe."""
        if group:
            self.groups[group] += 1
            
    def increment_combination(self, combo: str):
        """Incrémente le compteur d'une combinaison."""
        self.combinations[combo] += 1

    def get_post_count(self, post_type: str) -> int:
        """Retourne le nombre d'utilisations d'un type de poste."""
        return self.posts.get(post_type, 0)
        
    def get_group_count(self, group: str) -> int:
        """Retourne le nombre d'utilisations d'un groupe."""
        return self.groups.get(group, 0)
        
    def get_combination_count(self, combo: str) -> int:
        """Retourne le nombre d'utilisations d'une combinaison."""
        return self.combinations.get(combo, 0)

class QuotaTracker:
    """
    Gestionnaire principal pour le suivi des quotas.
    Maintient l'état des compteurs et vérifie les limites pour tous les types de distribution.
    """
    def __init__(self, planning: Planning, persons: List[Union[Doctor, CAT]], day_type: str):
        """
        Initialise le gestionnaire de quotas.
        
        Args:
            planning: Planning en cours
            persons: Liste des médecins ou CAT
            day_type: Type de jour ('weekday', 'saturday', 'sunday_holiday')
        """
        self.planning = planning
        self.persons = persons
        self.day_type = day_type
        self.cal = France()
        
        # Détecter le type de personnes (CAT ou médecins)
        self.person_type = 'cats' if hasattr(persons[0], 'posts') else 'doctors'
        
        # Initialiser les quotas depuis la pré-analyse
        self.pre_analysis = planning.pre_analysis_results
        if self.person_type == 'cats':
            self.quotas = self.pre_analysis["cat_posts"][day_type]
        else:
            self.quotas = self.pre_analysis["adjusted_posts"][day_type]
            
        # Initialiser les compteurs pour chaque personne
        self.counters = {
            person.name: QuotaCounter(person.name)
            for person in persons
        }
        
        # Charger l'état actuel du planning
        self._load_current_state()
        
    def _load_current_state(self):
        """Charge l'état actuel des compteurs depuis le planning."""
        for day in self.planning.days:
            # Vérifier si le jour correspond au type demandé
            if not self._is_matching_day_type(day.date):
                continue
                
            # Parcourir les slots de la journée
            for slot in day.slots:
                if any(person.name == slot.assignee for person in self.persons):
                    counter = self.counters[slot.assignee]
                    
                    # Incrémenter les compteurs appropriés
                    counter.increment_post(slot.abbreviation)
                    
                    group = self._get_post_group(slot.abbreviation, day.date)
                    if group:
                        counter.increment_group(group)

    def _is_matching_day_type(self, check_date: date) -> bool:
        """Vérifie si une date correspond au type de jour géré."""
        day_type = DayType.get_day_type(check_date, self.cal)
        
        if self.day_type == 'weekday':
            return day_type == 'weekday'
        elif self.day_type == 'saturday':
            return day_type == 'saturday'
        else:  # sunday_holiday
            return day_type == 'sunday_holiday'

    def can_assign_post(self, person: Union[Doctor, CAT], post_type: str) -> bool:
        """Vérifie si un poste peut être attribué sans dépasser le quota."""
        counter = self.counters[person.name]
        current = counter.get_post_count(post_type)
        quota = self.quotas.get(post_type, 0)
        
        if current >= quota:
            logger.debug(f"{person.name}: Quota atteint pour {post_type} "
                      f"({current}/{quota})")
            return False
        return True

    def can_assign_combination(self, person: Union[Doctor, CAT], combo: str, date: date) -> bool:
        """
        Vérifie si une combinaison peut être attribuée en respectant tous les quotas.
        
        Args:
            person: Médecin ou CAT à vérifier
            combo: Code de la combinaison
            date: Date de l'attribution
            
        Returns:
            bool: True si l'attribution est possible, False sinon
        """
        try:
            # Extraire les postes de la combinaison
            first_post, second_post = self._get_posts_from_combo(combo)
            
            # Vérifier les quotas de poste
            if not (self.can_assign_post(person, first_post) and 
                   self.can_assign_post(person, second_post)):
                logger.debug(f"{person.name}: Quota dépassé pour {first_post} ou {second_post}")
                return False
            
            # Pour les médecins, vérifier aussi les groupes
            if self.person_type == 'doctors':
                first_group = self._get_post_group(first_post, date)
                second_group = self._get_post_group(second_post, date)
                
                if not (self._check_group_limit(person, first_group) and
                       self._check_group_limit(person, second_group)):
                    logger.debug(f"{person.name}: Limite de groupe atteinte")
                    return False
            
            return True
            
        except ValueError as e:
            # Combinaison invalide
            logger.warning(f"Combinaison invalide pour {person.name}: {e}")
            return False
        except Exception as e:
            # Autre erreur inattendue
            logger.error(f"Erreur vérification combinaison pour {person.name}: {e}")
            return False

    def update_assignment(self, person: Union[Doctor, CAT], post_type: str, 
                         date: date, combo: Optional[str] = None):
        """Met à jour les compteurs après une attribution."""
        counter = self.counters[person.name]
        
        # Incrémenter le compteur de poste
        counter.increment_post(post_type)
        
        # Incrémenter le compteur de groupe si applicable
        group = self._get_post_group(post_type, date)
        if group:
            counter.increment_group(group)
            
        # Incrémenter le compteur de combinaison si fournie
        if combo:
            counter.increment_combination(combo)

    def get_remaining_quotas(self, person: Union[Doctor, CAT]) -> Dict:
        """Retourne les quotas restants pour une personne."""
        result = {
            'posts': {},
            'groups': {},
            'combinations': {}
        }
        
        counter = self.counters[person.name]
        
        # Quotas de postes
        for post_type, quota in self.quotas.items():
            current = counter.get_post_count(post_type)
            result['posts'][post_type] = max(0, quota - current)
            
        # Pour les médecins, ajouter les groupes
        if self.person_type == 'doctors':
            group_limits = (self.pre_analysis.get('ideal_distribution', {})
                          .get(person.name, {})
                          .get('groups', {}))
            
            for group, limits in group_limits.items():
                current = counter.get_group_count(group)
                max_allowed = limits.get('max', float('inf'))
                if max_allowed < float('inf'):
                    result['groups'][group] = max(0, max_allowed - current)
        
        return result

    def _get_posts_from_combo(self, combo: str) -> Tuple[str, str]:
        """
        Extrait les deux postes d'une combinaison.
        Gère à la fois les combinaisons personnalisées et standards.
        
        Args:
            combo: Code de la combinaison à analyser
            
        Returns:
            Tuple[str, str]: Les deux codes de poste qui composent la combinaison
            
        Raises:
            ValueError: Si la combinaison n'est pas valide ou reconnue
        """
        # 1. Vérifier les combinaisons de postes personnalisés
        data_persistence = DataPersistence()
        custom_posts = data_persistence.load_custom_posts()
        
        for custom_post in custom_posts.values():
            if combo in custom_post.possible_combinations.values():
                for post, combo_name in custom_post.possible_combinations.items():
                    if combo_name == combo:
                        return custom_post.name, post

        # 2. Si ce n'est pas une combinaison personnalisée, extraire les postes standards
        if len(combo) >= 4:  # Une combinaison standard fait 4 caractères (ex: MLCA)
            return combo[:2], combo[2:]
            
        # 3. Si on arrive ici, la combinaison n'est pas valide
        raise ValueError(f"Combinaison invalide: {combo}")

    def _get_post_group(self, post_type: str, date: date) -> Optional[str]:
        """Détermine le groupe d'un poste selon le type de jour."""
        # Accès aux postes personnalisés via DataPersistence
        data_persistence = DataPersistence()
        custom_posts = data_persistence.load_custom_posts()
        
        if post_type in custom_posts:
            return custom_posts[post_type].statistic_group

    def _get_weekday_group(self, post_type: str) -> Optional[str]:
        """Retourne le groupe de semaine d'un poste."""
        weekday_groups = {
            "XM": ["CM", "HM", "SM", "RM"],
            "XmM": ["MM"],
            "XA": ["CA", "HA", "SA", "RA"],
            "XS": ["CS", "HS", "SS", "RS"],
            "Vm": ["ML"],
            "Va": ["AL", "AC"],
            "NMC": ["NM", "NC", "NA"]
        }
        
        for group, posts in weekday_groups.items():
            if post_type in posts:
                return group
        return None

    def _get_weekend_group(self, post_type: str, date: date) -> Optional[str]:
        """Retourne le groupe de weekend d'un poste."""
        is_saturday = self.day_type == 'saturday'
        
        weekend_groups = {
            "CmS" if is_saturday else "CmD": ["MM", "CM", "HM", "SM", "RM"],
            "CaSD": ["CA", "HA", "SA", "RA"],
            "CsSD": ["CS", "HS", "SS", "RS"],
            "VmS" if is_saturday else "VmD": ["ML", "MC"],
            "VaSD": ["AL", "AC"],
            "NAMw": ["NM", "NA"],
            "NLw": ["NL"]
        }
        
        for group, posts in weekend_groups.items():
            if post_type in posts:
                return group
        return None

    def _check_group_limit(self, person: Union[Doctor, CAT], group: str) -> bool:
        """Vérifie les limites de groupe pour les médecins."""
        if not group or self.person_type == 'cats':
            return True
            
        # Récupérer la limite depuis la distribution idéale
        group_limits = (self.pre_analysis.get('ideal_distribution', {})
                      .get(person.name, {})
                      .get('groups', {})
                      .get(group, {}))
                      
        max_allowed = group_limits.get('max', float('inf'))
        current = self.counters[person.name].get_group_count(group)
        
        return current < max_allowed

    def log_status(self):
        """Affiche l'état détaillé des quotas et compteurs."""
        logger.info(f"\nÉTAT DES QUOTAS ({self.person_type.upper()}):")
        
        for person in self.persons:
            logger.info(f"\n{person.name}:")
            counter = self.counters[person.name]
            
            # Postes
            logger.info("Postes:")
            for post_type, quota in self.quotas.items():
                current = counter.get_post_count(post_type)
                status = "OK" if current <= quota else "DÉPASSÉ"
                logger.info(f"  {post_type}: {current}/{quota} ({status})")
            
            # Groupes (médecins seulement)
            if self.person_type == 'doctors':
                group_limits = (self.pre_analysis.get('ideal_distribution', {})
                              .get(person.name, {})
                              .get('groups', {}))
                
                if group_limits:
                    logger.info("\nGroupes:")
                    for group, limits in group_limits.items():
                        current = counter.get_group_count(group)
                        max_allowed = limits.get('max', float('inf'))
                        if max_allowed < float('inf'):
                            status = "OK" if current <= max_allowed else "DÉPASSÉ"
                            logger.info(f"  {group}: {current}/{max_allowed} ({status})")