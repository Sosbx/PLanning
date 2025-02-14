# core/Optimizer/weekend_optimizer.py

from typing import Dict, List, Tuple, Optional
from datetime import date, datetime, time, timedelta
from core.Constantes.models import Doctor, TimeSlot, WEEKEND_COMBINATIONS
from core.Constantes.day_type import DayType
from .distribution_optimizer import DistributionOptimizer, OptimizationContext
from workalendar.europe import France
import random
import logging

logger = logging.getLogger(__name__)

class WeekendCombinationOptimizer(DistributionOptimizer):
    """Optimiseur spécialisé pour les combinaisons weekend"""
    
    def __init__(self, context: OptimizationContext):
        super().__init__(context)
        self.cal = France()
        self.available_combinations = self._initialize_available_combinations()
        
    def _initialize_available_combinations(self) -> Dict[date, List[str]]:
        """Initialise les combinaisons disponibles pour chaque date weekend"""
        available = {}
        
        current_date = self.context.start_date
        while current_date <= self.context.end_date:
            if current_date.weekday() >= 5 or self.cal.is_holiday(current_date):
                day = self.context.planning.get_day(current_date)
                if day:
                    combinations = []
                    for combo in WEEKEND_COMBINATIONS:
                        first_post, second_post = combo[:2], combo[2:]
                        if any(s.abbreviation == first_post for s in day.slots) and \
                           any(s.abbreviation == second_post for s in day.slots):
                            combinations.append(combo)
                    if combinations:
                        available[current_date] = combinations
            
            current_date += timedelta(days=1)
            
        return available

    def _optimize(self) -> Dict:
        """Implémentation spécifique pour les combinaisons weekend"""
        results = {}
        
        # 1. Distribution initiale pour les minimums critiques
        critical_assignments = self._distribute_critical_minimums()
        results.update(critical_assignments)

        # 2. Distribution générale équilibrée
        if self._has_unmet_minimums():
            balanced_assignments = self._distribute_balanced()
            results.update(balanced_assignments)

        # 3. Distribution finale avec contraintes assouplies si nécessaire
        if self._has_unmet_minimums():
            final_assignments = self._distribute_with_relaxed_constraints()
            results.update(final_assignments)

        return results

    def _distribute_critical_minimums(self) -> Dict:
        """Distribution prioritaire pour les périodes critiques"""
        assignments = {}
        critical_periods = self._get_critical_periods()

        for period in critical_periods:
            date = period['date']
            available_combinations = self._get_available_combinations_for_date(date)

            # Trier les médecins par priorité pour cette date
            scored_doctors = []
            for doctor in self.context.doctors:
                if self._is_doctor_available(doctor, date):
                    score = self.calculate_priority_score(doctor, 'groups', 'total', date)
                    scored_doctors.append((score, doctor))

            # Trier par score décroissant en utilisant uniquement le score (premier élément du tuple)
            scored_doctors.sort(key=lambda x: x[0], reverse=True)

            # Attribuer les combinaisons disponibles
            for score, doctor in scored_doctors:
                if not available_combinations:
                    break

                best_combo = self._find_best_combination(doctor, date, available_combinations)
                if best_combo:
                    if self._try_assign_combination(doctor, date, best_combo):
                        if date not in assignments:
                            assignments[date] = {}
                        assignments[date][best_combo] = doctor.name
                        available_combinations.remove(best_combo)
                        logger.debug(f"Attribution critique: {doctor.name} - {best_combo} le {date} (score: {score})")

        return assignments

    def _distribute_balanced(self) -> Dict:
        """Distribution équilibrée standard"""
        assignments = {}
        
        # Parcourir les dates non critiques
        for day in self.context.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            if day.date in [p['date'] for p in self._get_critical_periods()]:
                continue  # Déjà traité dans _distribute_critical_minimums

            available_combinations = self._get_available_combinations_for_date(day.date)
            if not available_combinations:
                continue

            # Distribution équilibrée pour cette date
            date_assignments = self._balanced_distribution_for_date(
                day.date, available_combinations
            )
            if date_assignments:
                assignments[day.date] = date_assignments

        return assignments

    def _distribute_with_relaxed_constraints(self) -> Dict:
        """Distribution finale avec contraintes assouplies"""
        assignments = {}
        
        # Ne traiter que les médecins n'ayant pas atteint leurs minimums
        doctors_needing_assignments = [
            doctor for doctor in self.context.doctors  # Ici : utiliser self.context.doctors
            if self._needs_more_assignments(doctor)
        ]

        if not doctors_needing_assignments:
            return assignments

        # Parcourir toutes les dates restantes
        for day in self.context.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue

            available_combinations = self._get_available_combinations_for_date(day.date)
            if not available_combinations:
                continue

            # Essayer d'attribuer avec contraintes assouplies
            for doctor in doctors_needing_assignments:
                if not self._is_doctor_available(doctor, day.date):
                    continue

                best_combo = self._find_best_combination(
                    doctor, day.date, available_combinations, 
                    ignore_secondary=True  # Ignorer les desideratas secondaires
                )
                
                if best_combo and self._try_assign_combination(
                    doctor, day.date, best_combo, ignore_secondary=True
                ):
                    if day.date not in assignments:
                        assignments[day.date] = {}
                    assignments[day.date][best_combo] = doctor.name
                    available_combinations.remove(best_combo)
                    logger.debug(f"Attribution assouplie: {doctor.name} - {best_combo} le {day.date}")

        return assignments
    
    def _balanced_distribution_for_date(self, date: date, 
                                      available_combinations: List[str]) -> Dict[str, str]:
        """Distribution équilibrée pour une date donnée"""
        assignments = {}
        
        # Calculer les scores pour tous les médecins disponibles
        scored_doctors = []
        for doctor in self.context.doctors:
            if not self._is_doctor_available(doctor, date):
                continue
            
            score = self.calculate_priority_score(doctor, 'groups', 'total', date)
            # Ajouter des bonus/malus basés sur l'historique
            score = self._adjust_score_based_on_history(doctor, date, score)
            scored_doctors.append((score, doctor))

        # Trier par score décroissant en utilisant le score
        scored_doctors.sort(key=lambda x: x[0], reverse=True)
        
        # Attribution des combinaisons
        for score, doctor in scored_doctors:
            if not available_combinations:
                break
                
            best_combo = self._find_best_combination(doctor, date, available_combinations)
            if best_combo and self._try_assign_combination(doctor, date, best_combo):
                assignments[best_combo] = doctor.name
                available_combinations.remove(best_combo)
                logger.debug(f"Attribution équilibrée: {doctor.name} - {best_combo} le {date} (score: {score})")

        return assignments

    def _adjust_score_based_on_history(self, doctor: Doctor, date: date, base_score: float) -> float:
        """Ajuste le score en fonction de l'historique des attributions"""
        state = self.doctor_states[doctor.name]
        
        # 1. Malus pour les attributions récentes
        recent_assignments = [
            d for d, _ in state['assignments']
            if (date - d).days <= 7  # Sur 7 jours glissants
        ]
        recency_penalty = len(recent_assignments) * 0.1  # -10% par attribution récente
        
        # 2. Bonus pour les longues périodes sans attribution
        if state['assignments']:
            last_assignment = max(d for d, _ in state['assignments'])
            days_since_last = (date - last_assignment).days
            if days_since_last > 14:  # Bonus après 2 semaines
                base_score *= 1.2
                
        # 3. Ajustement selon l'équilibre des groupes
        group_balance_score = self._calculate_group_balance_score(doctor)
        
        return base_score * (1 - recency_penalty) * group_balance_score

    def _calculate_group_balance_score(self, doctor: Doctor) -> float:
        """Calcule un score basé sur l'équilibre des groupes"""
        state = self.doctor_states[doctor.name]
        group_counts = state['current_counts'].get('groups', {})
        
        if not group_counts:
            return 1.0  # Score neutre si pas d'attributions
            
        # Calculer la variance des écarts aux minimums
        variances = []
        for group, min_val in state['min_intervals'].items():
            current = group_counts.get(group, 0)
            if min_val > 0:  # Ne considérer que les groupes avec minimum
                variance = (current / min_val) if current < min_val else 1.0
                variances.append(variance)
                
        if not variances:
            return 1.0
            
        # Plus la variance est faible, plus le score est élevé
        mean_variance = sum(variances) / len(variances)
        return 2 - mean_variance  # Score entre 1 et 2

    def _find_best_combination(self, doctor: Doctor, date: date, 
                             available_combinations: List[str],
                             ignore_secondary: bool = False) -> Optional[str]:
        """Trouve la meilleure combinaison disponible pour un médecin"""
        best_score = -1
        best_combo = None
        
        for combo in available_combinations:
            # Vérifier d'abord si la combinaison est possible
            if not self._can_assign_combination(doctor, date, combo, ignore_secondary):
                continue
                
            # Calculer le score pour cette combinaison
            score = self._calculate_combination_score(doctor, date, combo)
            
            if score > best_score:
                best_score = score
                best_combo = combo
                
        return best_combo

    def _calculate_combination_score(self, doctor: Doctor, date: date, combo: str) -> float:
        """Calcule un score pour une combinaison spécifique"""
        state = self.doctor_states[doctor.name]
        score = 0.0
        
        # 1. Score de base pour les groupes impactés
        groups = self._get_groups_for_combo(combo, date)
        for group in groups:
            current = state['current_counts'].get('groups', {}).get(group, 0)
            min_required = state['min_intervals'].get(group, 0)
            if current < min_required:
                score += 2.0  # Fort bonus pour atteindre les minimums
            max_allowed = state['max_intervals'].get(group, float('inf'))
            if current >= max_allowed - 1:  # Proche du maximum
                score *= 0.5  # Pénalité pour éviter de saturer
                
        # 2. Score pour les postes individuels
        first_post, second_post = combo[:2], combo[2:]
        for post in [first_post, second_post]:
            current = state['current_counts'].get('posts', {}).get(post, 0)
            min_required = state['min_intervals'].get(post, 0)
            if current < min_required:
                score += 1.0

        # 3. Bonus pour équilibrage
        balance_score = self._calculate_post_balance_score(doctor, combo)
        score *= balance_score

        return score

    def _calculate_post_balance_score(self, doctor: Doctor, combo: str) -> float:
        """Calcule un score d'équilibre pour les postes d'une combinaison"""
        state = self.doctor_states[doctor.name]
        posts = [combo[:2], combo[2:]]
        
        # Calculer le ratio moyen d'utilisation des postes
        ratios = []
        for post in posts:
            current = state['current_counts'].get('posts', {}).get(post, 0)
            min_val = state['min_intervals'].get(post, 0)
            if min_val > 0:
                ratio = current / min_val
                ratios.append(ratio)
                
        if not ratios:
            return 1.0
            
        # Score basé sur l'équilibre entre les ratios
        mean_ratio = sum(ratios) / len(ratios)
        return 1 / (1 + abs(mean_ratio - 1))  # Score proche de 1 si équilibré

    def _can_assign_combination(self, doctor: Doctor, date: date, combo: str,
                              ignore_secondary: bool = False) -> bool:
        """Vérifie si une combinaison peut être attribuée"""
        # 1. Vérifier les limites de groupe
        for group in self._get_groups_for_combo(combo, date):
            current = self.doctor_states[doctor.name]['current_counts'].get('groups', {}).get(group, 0)
            max_allowed = self.doctor_states[doctor.name]['max_intervals'].get(group, float('inf'))
            if current >= max_allowed:
                return False

        # 2. Récupérer les slots pour la combinaison
        first_post, second_post = combo[:2], combo[2:]
        first_slot = self._get_slot_for_post(date, first_post)
        second_slot = self._get_slot_for_post(date, second_post)
        
        if not (first_slot and second_slot):
            return False

        # 3. Vérifier les contraintes pour chaque slot
        for slot in [first_slot, second_slot]:
            if not self.context.constraints.can_assign_to_assignee(
                doctor, date, slot, self.context.planning, 
                respect_secondary=not ignore_secondary
            ):
                return False

        return True

    def _get_slot_for_post(self, date: date, post_type: str) -> Optional[TimeSlot]:
        """Récupère le slot disponible pour un type de poste à une date donnée"""
        day = self.context.planning.get_day(date)
        if not day:
            return None
            
        return next(
            (slot for slot in day.slots 
             if slot.abbreviation == post_type and not slot.assignee),
            None
        )
        
    def _get_groups_for_combo(self, combo: str, date: date = None) -> List[str]:
        """
        Détermine les groupes impactés par une combinaison.
        
        Args:
            combo: Combinaison de postes (ex: 'MLCA', 'HMHA', etc.)
            
        Returns:
            List[str]: Liste des groupes impactés
        """
        groups = []
        first_post, second_post = combo[:2], combo[2:]

        # Mapping des postes vers les groupes
        post_group_mapping = {
            # Groupes de consultation matin
            "MM": ["CmS", "CmD"],
            "CM": ["CmS", "CmD"],
            "HM": ["CmS", "CmD"],
            "SM": ["CmS", "CmD"],
            "RM": ["CmS", "CmD"],
            
            # Groupes de consultation après-midi
            "CA": ["CaSD"],
            "HA": ["CaSD"],
            "SA": ["CaSD"],
            "RA": ["CaSD"],
            
            # Groupes de consultation soir
            "CS": ["CsSD"],
            "HS": ["CsSD"],
            "SS": ["CsSD"],
            "RS": ["CsSD"],
            
            # Groupes de visites matin
            "ML": ["VmS", "VmD"],
            "MC": ["VmD"],
            
            # Groupes de visites après-midi
            "AL": ["VaSD"],
            "AC": ["VaSD"],
            
            # Groupes de nuit
            "NA": ["NAMw"],
            "NM": ["NAMw"],
            "NL": ["NLw"]
        }

        # Ajouter les groupes pour chaque poste
        for post in [first_post, second_post]:
            if post in post_group_mapping:
                groups.extend(post_group_mapping[post])
                
        # Gérer le cas spécial de NL pour NLw les vendredis
        if "NL" in [first_post, second_post]:
            day = self.context.planning.get_day(date)
            if day and day.date.weekday() == 4:  # Vendredi
                groups.append("NLw")

        # Filtrer les doublons et trier pour la cohérence
        return sorted(list(set(groups)))

    def _get_date_type(self, date: date) -> str:
        """
        Détermine le type de jour (saturday/sunday_holiday).
        Prend en compte les ponts.
        """
        if self.cal.is_holiday(date) or DayType.is_bridge_day(date, self.cal):
            return "sunday_holiday"
        if date.weekday() == 5:  # Samedi
            return "saturday"
        if date.weekday() == 6:  # Dimanche
            return "sunday_holiday"
        return None  # Pour les autres jours

    def _try_assign_combination(self, doctor: Doctor, date: date, combo: str,
                              ignore_secondary: bool = False) -> bool:
        """Tente d'attribuer une combinaison"""
        try:
            # 1. Vérification finale
            if not self._can_assign_combination(doctor, date, combo, ignore_secondary):
                return False

            # 2. Récupérer les slots
            first_post, second_post = combo[:2], combo[2:]
            first_slot = self._get_slot_for_post(date, first_post)
            second_slot = self._get_slot_for_post(date, second_post)

            # 3. Attribution
            first_slot.assignee = doctor.name
            second_slot.assignee = doctor.name

            # 4. Mise à jour des états
            state = self.doctor_states[doctor.name]
            
            # Mise à jour des groupes
            for group in self._get_groups_for_combo(combo, date):
                if 'groups' not in state['current_counts']:
                    state['current_counts']['groups'] = {}
                state['current_counts']['groups'][group] = \
                    state['current_counts']['groups'].get(group, 0) + 1

            # Mise à jour des postes
            if 'posts' not in state['current_counts']:
                state['current_counts']['posts'] = {}
            for post in [first_post, second_post]:
                state['current_counts']['posts'][post] = \
                    state['current_counts']['posts'].get(post, 0) + 1

            # Enregistrer l'attribution
            state['assignments'].append((date, combo))

            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution de {combo} à {doctor.name}: {e}")
            # Annuler les changements en cas d'erreur
            if first_slot and first_slot.assignee == doctor.name:
                first_slot.assignee = None
            if second_slot and second_slot.assignee == doctor.name:
                second_slot.assignee = None
            return False

    def _has_unmet_minimums(self) -> bool:
        """Vérifie s'il reste des minimums non atteints"""
        for doctor_name, state in self.doctor_states.items():
            for item, min_val in state['min_intervals'].items():
                current = state['current_counts'].get('groups', {}).get(item, 0)
                if current < min_val:
                    return True
        return False

    def _needs_more_assignments(self, doctor: Doctor) -> bool:
        """Vérifie si un médecin a besoin de plus d'attributions"""
        state = self.doctor_states[doctor.name]
        return any(
            state['current_counts'].get('groups', {}).get(group, 0) < min_val
            for group, min_val in state['min_intervals'].items()
        )

    def _get_available_combinations_for_date(self, date: date) -> List[str]:
        """Récupère les combinaisons disponibles pour une date"""
        day = self.context.planning.get_day(date)
        if not day:
            return []

        available = []
        for combo in self.context.available_slots:
            first_post, second_post = combo[:2], combo[2:]
            
            # Vérifier la disponibilité des deux slots
            first_available = any(
                s.abbreviation == first_post and not s.assignee 
                for s in day.slots
            )
            second_available = any(
                s.abbreviation == second_post and not s.assignee 
                for s in day.slots
            )
            
            if first_available and second_available:
                available.append(combo)

        return available