# © 2024 HILAL Arkane. Tous droits réservés.
# core/GEnerator/Optimizer/backtracking.py

from typing import List, Dict, Tuple, Optional, Set
from datetime import date
import logging
from dataclasses import dataclass
from copy import deepcopy

from core.Constantes.models import Doctor, TimeSlot, Planning
from core.Constantes.constraints import PlanningConstraints

logger = logging.getLogger(__name__)

@dataclass
class AssignmentState:
    """État d'une attribution pour le backtracking"""
    doctor: Doctor
    date: date
    slot: TimeSlot
    score: float
    violated_secondary: Set[str] = None
    
    def __post_init__(self):
        if self.violated_secondary is None:
            self.violated_secondary = set()

class BacktrackingOptimizer:
    def __init__(self, planning: Planning, constraints: PlanningConstraints, doctors: List[Doctor]):
        self.planning = planning
        self.constraints = constraints
        self.doctors = doctors  # Stockage direct de la liste des médecins
        self.best_solution = None
        self.best_score = float('-inf')
        self.max_depth = 5
        
    def optimize_distribution(self, slots_to_assign: List[Tuple[date, TimeSlot]], 
                            available_doctors: List[Doctor],
                            current_assignments: Dict = None) -> Optional[Dict]:
        """
        Optimise la distribution des postes en utilisant le backtracking.
        
        Args:
            slots_to_assign: Liste des slots à attribuer
            available_doctors: Liste des médecins disponibles
            current_assignments: État actuel des attributions
            
        Returns:
            Dict: Meilleure solution trouvée ou None si pas de solution
        """
        self.best_solution = None
        self.best_score = float('-inf')
        
        # Initialiser l'état courant si non fourni
        if current_assignments is None:
            current_assignments = {}
            
        # Trier les slots par ordre de difficulté
        sorted_slots = self._sort_slots_by_difficulty(slots_to_assign)
        
        # Commencer le backtracking
        self._backtrack(sorted_slots, available_doctors, current_assignments, 0, set())
        
        return self.best_solution
        
    def _backtrack(self, slots: List[Tuple[date, TimeSlot]], 
                   doctors: List[Doctor],
                   current_assignments: Dict,
                   depth: int,
                   violated_desiderata: Set[str]) -> None:
        """
        Fonction récursive de backtracking.
        
        Args:
            slots: Slots restants à attribuer
            doctors: Médecins disponibles
            current_assignments: Attributions actuelles
            depth: Profondeur actuelle de récursion
            violated_desiderata: Ensemble des desiderata secondaires violés
        """
        # Vérifier si on a atteint une solution complète
        if not slots:
            score = self._evaluate_solution(current_assignments, violated_desiderata)
            if score > self.best_score:
                self.best_score = score
                self.best_solution = deepcopy(current_assignments)
            return
            
        # Vérifier la profondeur maximale
        if depth >= self.max_depth:
            return
            
        # Prendre le prochain slot à attribuer
        date, slot = slots[0]
        remaining_slots = slots[1:]
        
        # Pour chaque médecin disponible
        for doctor in doctors:
            # Vérifier si l'attribution est possible
            assignment_state = self._try_assignment(doctor, date, slot)
            if not assignment_state:
                continue
                
            # Sauvegarder l'état actuel
            old_assignee = slot.assignee
            old_violations = violated_desiderata.copy()
            
            # Effectuer l'attribution
            slot.assignee = doctor.name
            violated_desiderata.update(assignment_state.violated_secondary)
            
            # Mettre à jour les attributions courantes
            if date not in current_assignments:
                current_assignments[date] = {}
            current_assignments[date][slot.abbreviation] = doctor.name
            
            # Récursion
            self._backtrack(remaining_slots, doctors, current_assignments, 
                          depth + 1, violated_desiderata)
                          
            # Restaurer l'état
            slot.assignee = old_assignee
            violated_desiderata.clear()
            violated_desiderata.update(old_violations)
            
            if date in current_assignments:
                if slot.abbreviation in current_assignments[date]:
                    del current_assignments[date][slot.abbreviation]
                if not current_assignments[date]:
                    del current_assignments[date]
                    
    def _try_assignment(self, doctor: Doctor, date: date, 
                       slot: TimeSlot) -> Optional[AssignmentState]:
        """
        Teste si une attribution est possible et retourne son état.
        
        Args:
            doctor: Médecin à tester
            date: Date du slot
            slot: Slot à attribuer
            
        Returns:
            AssignmentState: État de l'attribution ou None si impossible
        """
        # Vérifier d'abord les contraintes primaires
        if not self._check_primary_constraints(doctor, date, slot):
            return None
            
        # Identifier les desiderata secondaires violés
        violated_secondary = set()
        for desiderata in doctor.desiderata:
            if (getattr(desiderata, 'priority', 'primary') == 'secondary' and
                desiderata.start_date <= date <= desiderata.end_date and
                desiderata.overlaps_with_slot(slot)):
                violated_secondary.add(f"{date}-{slot.abbreviation}")
                
        # Calculer le score de cette attribution
        score = self._calculate_assignment_score(doctor, date, slot, violated_secondary)
        
        return AssignmentState(doctor, date, slot, score, violated_secondary)
        
    def _check_primary_constraints(self, doctor: Doctor, date: date, 
                                 slot: TimeSlot) -> bool:
        """
        Vérifie les contraintes primaires pour une attribution.
        """
        # Vérifier les desiderata primaires
        for desiderata in doctor.desiderata:
            if not hasattr(desiderata, 'priority') or desiderata.priority == 'primary':
                if (desiderata.start_date <= date <= desiderata.end_date and
                    desiderata.overlaps_with_slot(slot)):
                    return False
                    
        # Vérifier les autres contraintes via le système de contraintes
        return self.constraints.can_assign_to_assignee(
            doctor, date, slot, self.planning, respect_secondary=False
        )
        
    def _calculate_assignment_score(self, doctor: Doctor, date: date,
                                  slot: TimeSlot, violated_secondary: Set[str]) -> float:
        """
        Calcule un score pour une attribution potentielle.
        """
        score = 100.0  # Score de base
        
        # Pénalité pour les desiderata secondaires violés
        score -= len(violated_secondary) * 10
        
        # Bonus pour les médecins pleins temps
        if doctor.half_parts == 2:
            score += 20
            
        # Pénalité basée sur le nombre de violations déjà accumulées
        previous_violations = sum(
            1 for day in self.planning.days
            for s in day.slots
            if s.assignee == doctor.name and 
            self._violates_secondary_desiderata(doctor, day.date, s)
        )
        score -= previous_violations * 5
        
        return score
        
    def _violates_secondary_desiderata(self, doctor: Doctor, date: date, 
                                     slot: TimeSlot) -> bool:
        """
        Vérifie si un slot viole des desiderata secondaires.
        """
        return any(
            desiderata.priority == 'secondary' and
            desiderata.start_date <= date <= desiderata.end_date and
            desiderata.overlaps_with_slot(slot)
            for desiderata in doctor.desiderata
            if hasattr(desiderata, 'priority')
        )
        
    def _sort_slots_by_difficulty(self, slots: List[Tuple[date, TimeSlot]]) -> List[Tuple[date, TimeSlot]]:
        """
        Trie les slots par ordre de difficulté d'attribution.
        Les slots les plus contraints sont traités en premier.
        """
        def calculate_difficulty(date_slot: Tuple[date, TimeSlot]) -> float:
            date, slot = date_slot
            difficulty = 0.0
            
            # Nombre de médecins disponibles pour ce slot
            available_count = sum(
                1 for doctor in self.doctors  # Utilisation de self.doctors au lieu de planning.doctors
                if self._check_primary_constraints(doctor, date, slot)
            )
            if available_count == 0:
                return float('inf')
                
            difficulty += 100 / available_count
            
            # Proximité avec d'autres slots déjà attribués
            day = self.planning.get_day(date)
            if day:
                assigned_count = sum(1 for s in day.slots if s.assignee)
                difficulty += assigned_count * 2
                
            return difficulty
            
        return sorted(slots, key=calculate_difficulty, reverse=True)
        
    def _evaluate_solution(self, assignments: Dict, 
                         violated_desiderata: Set[str]) -> float:
        """
        Évalue la qualité globale d'une solution.
        
        Args:
            assignments: Dictionnaire des attributions
            violated_desiderata: Ensemble des desiderata secondaires violés
            
        Returns:
            float: Score de la solution
        """
        score = 1000.0  # Score de base
        
        # Pénalité pour les desiderata secondaires violés
        score -= len(violated_desiderata) * 10
        
        # Vérifier l'équilibre entre les médecins
        doctor_counts = {}
        for date_assignments in assignments.values():
            for doctor_name in date_assignments.values():
                doctor_counts[doctor_name] = doctor_counts.get(doctor_name, 0) + 1
                
        if doctor_counts:
            # Pénaliser les écarts importants
            min_count = min(doctor_counts.values())
            max_count = max(doctor_counts.values())
            score -= (max_count - min_count) * 5
            
        return score

    def reset(self):
        """Réinitialise l'optimiseur pour une nouvelle utilisation."""
        self.best_solution = None
        self.best_score = float('-inf')