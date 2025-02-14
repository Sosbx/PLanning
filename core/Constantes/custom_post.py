# core/Constantes/custom Custom_Post.py


from dataclasses import dataclass, field
from datetime import time
from typing import List, Set, Dict, Optional
from PyQt6.QtGui import QColor

@dataclass
class CustomPost:
    name: str
    start_time: time
    end_time: time
    day_types: Set[str]  # "weekday", "saturday", "sunday_holiday"
    assignment_type: str  # "doctors", "cats", "both"
    possible_combinations: Dict[str, str]  # {post_code: resulting_combination}
    statistic_group: Optional[str]
    preserve_in_planning: bool = field(default=False)  # Si True, le poste sera préservé même avec valeur 0
    force_zero_count: bool = field(default=False)  # Si True, le poste est toujours considéré comme ayant un quota de 0
    color: QColor = field(default_factory=lambda: QColor("#E6F3FF"))

    def __post_init__(self):
        self.validate()
        
        # Si force_zero_count est True, preserve_in_planning doit être True
        if self.force_zero_count:
            self.preserve_in_planning = True

    def validate(self):
        """Validation des données du poste personnalisé"""
        if not 2 <= len(self.name) <= 4:
            raise ValueError("Le nom du poste doit contenir entre 2 et 4 caractères")
        
        if not self.name.replace("_", "").isalnum():
            raise ValueError("Le nom ne peut contenir que des lettres, des chiffres et des underscores")
        
        if not self.day_types:
            raise ValueError("Au moins un type de jour doit être sélectionné")
        
        if self.start_time >= self.end_time:
            raise ValueError("L'heure de début doit être antérieure à l'heure de fin")

    def should_include_in_planning(self, quota: int = 0) -> bool:
        """
        Détermine si le poste doit être inclus dans le planning
        
        Args:
            quota: Quota configuré pour ce poste
            
        Returns:
            bool: True si le poste doit être inclus
        """
        if self.force_zero_count:
            return True
        if self.preserve_in_planning:
            return True
        return quota > 0

    def get_effective_quota(self, configured_quota: int) -> int:
        """
        Détermine le quota effectif à utiliser pour ce poste
        
        Args:
            configured_quota: Quota configuré dans la configuration des postes
            
        Returns:
            int: Quota effectif à utiliser
        """
        if self.force_zero_count:
            return 0
        return configured_quota

    def overlaps_with(self, other_post) -> bool:
        """Vérifie si les horaires se chevauchent avec un autre poste"""
        return not (self.end_time < other_post.start_time or 
                   self.start_time > other_post.end_time)

    def can_combine_with(self, other_post) -> bool:
        """Vérifie si le poste peut être combiné avec un autre poste"""
        if isinstance(other_post, str):
            # Si c'est un poste standard, vérifier dans la configuration standard
            # Vous devrez implémenter cette logique selon vos besoins
            return True
        else:
            # Vérifie que les horaires ne se chevauchent pas
            return not (self.start_time < other_post.end_time and
                    self.end_time > other_post.start_time)

    def to_dict(self) -> dict:
        """Convertit le poste en dictionnaire pour la sauvegarde"""
        return {
            'name': self.name,
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
            'day_types': list(self.day_types),
            'assignment_type': self.assignment_type,
            'possible_combinations': self.possible_combinations,
            'statistic_group': self.statistic_group,
            'preserve_in_planning': self.preserve_in_planning,
            'force_zero_count': self.force_zero_count,
            'color': self.color.name()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CustomPost':
        """Crée un poste à partir d'un dictionnaire"""
        return cls(
            name=data['name'],
            start_time=time.fromisoformat(data['start_time']),
            end_time=time.fromisoformat(data['end_time']),
            day_types=set(data['day_types']),
            assignment_type=data['assignment_type'],
            possible_combinations=data['possible_combinations'],
            statistic_group=data['statistic_group'],
            preserve_in_planning=data.get('preserve_in_planning', False),
            force_zero_count=data.get('force_zero_count', False),
            color=QColor(data['color'])
        )