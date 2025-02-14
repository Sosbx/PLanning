# core/Optimizer/distribution_optimizer.py

from typing import Dict, List, Tuple, Optional, Any
from datetime import date, datetime
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from core.Constantes.models import Doctor, Planning, TimeSlot
import random

logger = logging.getLogger(__name__)

@dataclass
class DistributionState:
    """État de base pour le suivi de distribution"""
    total_assigned: int = 0
    assignments: Dict[str, List[Tuple[date, str]]] = field(default_factory=dict)
    group_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    post_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)

@dataclass
class OptimizationContext:
    """Contexte pour l'optimisation de la distribution"""
    planning: Planning
    intervals: Dict
    available_slots: Dict
    constraints: Any
    start_date: date
    end_date: date
    doctors: List[Doctor]  # Ajout de la liste des médecins
    cats: List[Any]  # Ajout des CATs si nécessaire

class DistributionOptimizer(ABC):
    """Classe de base pour l'optimisation de distribution"""
    
    def __init__(self, context: OptimizationContext):
        self.context = context
        self.state = DistributionState()
        self.doctor_states: Dict[str, Dict] = {}
        self.initialize_states()

    def initialize_states(self):
        """Initialise les états pour tous les médecins"""
        for doctor in self.context.doctors:  # Utiliser les médecins du contexte
            doctor_intervals = self.context.intervals.get(doctor.name, {})
            
            self.doctor_states[doctor.name] = {
                'min_intervals': self._get_doctor_minimums(doctor, doctor_intervals),
                'max_intervals': self._get_doctor_maximums(doctor, doctor_intervals),
                'current_counts': {'groups': {}, 'posts': {}},
                'assignments': [],
                'half_parts': doctor.half_parts
            }

    def _get_doctor_minimums(self, doctor: Doctor, intervals: Dict) -> Dict[str, int]:
        """Récupère les minimums requis pour un médecin"""
        minimums = {}
        for category in ['weekend_groups', 'weekend_posts']:
            if category in intervals:
                for item, values in intervals[category].items():
                    if 'min' in values:
                        minimums[item] = values['min']
        return minimums

    def _get_doctor_maximums(self, doctor: Doctor, intervals: Dict) -> Dict[str, int]:
        """Récupère les maximums autorisés pour un médecin"""
        maximums = {}
        for category in ['weekend_groups', 'weekend_posts']:
            if category in intervals:
                for item, values in intervals[category].items():
                    if 'max' in values:
                        maximums[item] = values['max']
                    else:
                        maximums[item] = float('inf')
        return maximums

    def calculate_priority_score(self, doctor: Doctor, item_type: str, 
                               item: str, date: date = None) -> float:
        """
        Calcule un score de priorité pour une attribution.
        
        Args:
            doctor: Le médecin concerné
            item_type: Type d'item (post, group, combination)
            item: Identifiant de l'item
            date: Date optionnelle pour le contexte
            
        Returns:
            float: Score de priorité
        """
        state = self.doctor_states[doctor.name]
        score = 0.0

        # 1. Score basé sur l'écart aux minimums
        current = state['current_counts'].get(item_type, {}).get(item, 0)
        min_required = state['min_intervals'].get(item, 0)
        if current < min_required:
            score += (min_required - current) * 2.0

        # 2. Score basé sur les demi-parts
        score *= 1.2 if doctor.half_parts == 2 else 0.8

        # 3. Score basé sur le total des attributions
        total_min = sum(state['min_intervals'].values())
        if len(state['assignments']) < total_min:
            score *= 1.5

        # 4. Score basé sur la criticité de la date si fournie
        if date:
            date_score = self._calculate_date_score(date)
            score *= date_score

        # 5. Facteur aléatoire
        score *= (0.9 + random.random() * 0.2)

        return score

    def _calculate_date_score(self, target_date: date) -> float:
        """Calcule un score pour une date basé sur sa criticité"""
        score = 1.0
        
        # Vérifier si c'est une période critique
        critical_periods = self._get_critical_periods()
        for period in critical_periods:
            if period['date'] == target_date:
                # Plus la disponibilité est faible, plus le score est élevé
                score *= (100 / period['availability'])
                break

        return score

    def _get_critical_periods(self) -> List[Dict]:
        """Identifie les périodes critiques"""
        critical_periods = []
        for day in self.context.planning.days:
            if day.is_weekend or day.is_holiday_or_bridge:
                # Calculer la disponibilité des médecins
                available_doctors = sum(
                    1 for doctor in self.context.doctors  # Utiliser les médecins du contexte
                    if self._is_doctor_available(doctor, day.date)
                )
                availability = (available_doctors / len(self.context.doctors)) * 100
                
                if availability < 65:  # Seuil de criticité
                    critical_periods.append({
                        'date': day.date,
                        'availability': availability
                    })

        return sorted(critical_periods, key=lambda x: x['availability'])
    def _is_doctor_available(self, doctor: Doctor, date: date) -> bool:
        """Vérifie la disponibilité basique d'un médecin"""
        return not any(
            desiderata.start_date <= date <= desiderata.end_date
            for desiderata in doctor.desiderata
        )

    def optimize_distribution(self) -> Dict:
        """
        Point d'entrée principal pour l'optimisation.
        À surcharger dans les classes dérivées.
        """
        return self._optimize()

    @abstractmethod
    def _optimize(self) -> Dict:
        """Méthode principale d'optimisation à implémenter"""
        pass

    def _can_assign(self, doctor: Doctor, item_type: str, item: str, 
                   date: date = None, slot: TimeSlot = None) -> bool:
        """Vérifie si une attribution est possible"""
        state = self.doctor_states[doctor.name]

        # 1. Vérifier les maximums
        current = state['current_counts'].get(item_type, {}).get(item, 0)
        max_allowed = state['max_intervals'].get(item, float('inf'))
        if current >= max_allowed:
            return False

        # 2. Vérifier les contraintes spécifiques si slot fourni
        if slot and not self.context.constraints.can_assign_to_assignee(
            doctor, date, slot, self.context.planning
        ):
            return False

        return True

    def _update_state(self, doctor: Doctor, item_type: str, item: str, 
                     date: date, slot: TimeSlot = None):
        """Met à jour l'état après une attribution"""
        state = self.doctor_states[doctor.name]

        # Mettre à jour les compteurs
        if item_type not in state['current_counts']:
            state['current_counts'][item_type] = {}
        state['current_counts'][item_type][item] = state['current_counts'][item_type].get(item, 0) + 1

        # Enregistrer l'attribution
        state['assignments'].append((date, item))

        # Mise à jour des compteurs globaux
        self.state.total_assigned += 1
        if doctor.name not in self.state.assignments:
            self.state.assignments[doctor.name] = []
        self.state.assignments[doctor.name].append((date, item))

    def get_distribution_stats(self) -> Dict:
        """Retourne les statistiques de distribution"""
        stats = {
            'total_assigned': self.state.total_assigned,
            'by_doctor': {},
            'unmet_minimums': {},
            'over_maximums': {}
        }

        for doctor_name, state in self.doctor_states.items():
            stats['by_doctor'][doctor_name] = {
                'total': len(state['assignments']),
                'by_type': state['current_counts']
            }

            # Vérifier les minimums non atteints
            unmet = {}
            for item, min_val in state['min_intervals'].items():
                current = state['current_counts'].get('groups', {}).get(item, 0)
                if current < min_val:
                    unmet[item] = min_val - current
            if unmet:
                stats['unmet_minimums'][doctor_name] = unmet

            # Vérifier les dépassements de maximum
            over = {}
            for item, max_val in state['max_intervals'].items():
                current = state['current_counts'].get('groups', {}).get(item, 0)
                if current > max_val:
                    over[item] = current - max_val
            if over:
                stats['over_maximums'][doctor_name] = over

        return stats