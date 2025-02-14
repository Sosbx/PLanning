# core/Analyzer/availability_matrix.py

from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional, Union
from core.Constantes.models import Doctor, CAT, Planning, TimeSlot, DayPlanning
from workalendar.europe import France
import logging

logger = logging.getLogger(__name__)

class AvailabilityMatrix:
    def __init__(self, start_date: date = None, end_date: date = None, doctors: List[Doctor] = None, cats: List[CAT] = None):
        self.start_date = start_date
        self.end_date = end_date
        self.doctors = doctors or []
        self.cats = cats or []
        self.cal = France()
        self.availability_matrix = {}
        self.critical_periods = []
        self._initialize_matrix()  # Renommé de init_matrix à _initialize_matrix
        
    def _initialize_matrix(self):  # Correction du nom de la méthode
        """Initialise la matrice de disponibilité"""
        self.availability_matrix = {
            person.name: {} for person in self.doctors + self.cats
        }
        
        if not (self.start_date and self.end_date):
            return

        # Initialiser la matrice avec les dates
        for person_name in self.availability_matrix:
            current_date = self.start_date
            while current_date <= self.end_date:
                self.availability_matrix[person_name][current_date] = {
                    1: True,  # Matin
                    2: True,  # Après-midi
                    3: True   # Soir/Nuit
                }
                current_date += timedelta(days=1)

        self._apply_desiderata()
        self._identify_critical_periods()

    def _apply_desiderata(self):
        """Applique les desiderata à la matrice"""
        if not (self.start_date and self.end_date):
            return
            
        for person in self.doctors + self.cats:
            for des in person.desiderata:
                current_date = max(des.start_date, self.start_date)
                end_date = min(des.end_date, self.end_date)
                while current_date <= end_date:
                    if current_date in self.availability_matrix[person.name]:
                        self.availability_matrix[person.name][current_date][des.period] = False
                    current_date += timedelta(days=1)

    def _identify_critical_periods(self):
        """Identifie les périodes critiques (≥35% d'indisponibilité)"""
        import random  # Ajouter en haut du fichier si pas déjà présent
        
        self.critical_periods = []
        
        if not (self.start_date and self.end_date):
            return

        current_date = self.start_date
        while current_date <= self.end_date:
            for period in [1, 2, 3]:  # Matin, Après-midi, Soir
                # Calculer le nombre de personnes disponibles
                available_count = sum(
                    1 for person in self.availability_matrix 
                    if current_date in self.availability_matrix[person] and 
                    self.availability_matrix[person][current_date][period]
                )
                
                total_personnel = len(self.doctors) + len(self.cats)
                if total_personnel == 0:
                    continue
                    
                # Calculer le pourcentage d'indisponibilité
                unavailability_percentage = ((total_personnel - available_count) / total_personnel) * 100
                
                # Ajouter si indisponibilité ≥ 35%
                if unavailability_percentage >= 35:
                    self.critical_periods.append((
                        current_date,
                        period,
                        unavailability_percentage,
                        available_count
                    ))
                    
            current_date += timedelta(days=1)

        # Trier d'abord par pourcentage d'indisponibilité (du plus critique au moins critique)
        self.critical_periods.sort(key=lambda x: (-x[2], x[3]))  # -x[2] pour ordre décroissant
        
        # Regrouper les périodes similaires (marge de 5%)
        if self.critical_periods:
            groups = []
            current_group = [self.critical_periods[0]]
            
            for i in range(1, len(self.critical_periods)):
                current = self.critical_periods[i]
                previous = current_group[0]
                
                if abs(current[2] - previous[2]) <= 5:  # Marge de 5%
                    current_group.append(current)
                else:
                    if len(current_group) > 1:
                        random.shuffle(current_group)
                    groups.extend(current_group)
                    current_group = [current]
            
            # Ne pas oublier le dernier groupe
            if len(current_group) > 1:
                random.shuffle(current_group)
            groups.extend(current_group)
            
            self.critical_periods = groups

        logger.debug(f"Périodes critiques identifiées : {len(self.critical_periods)}")
        for date, period, unavail_pct, available in self.critical_periods:
            period_name = {1: "Matin", 2: "Après-midi", 3: "Soir"}[period]
          

    def update_matrix(self, start_date: date, end_date: date):
        """Met à jour la matrice avec de nouvelles dates"""
        self.start_date = start_date
        self.end_date = end_date
        self._initialize_matrix()  # Utilisation du nouveau nom

    def get_period_availability(self, person: str, date: date, period: Union[int, str]) -> bool:
        """Vérifie la disponibilité d'une personne pour une période"""
        if isinstance(period, str):
            period = self.get_period_from_text(period)
        return (self.availability_matrix.get(person, {})
                .get(date, {})
                .get(period, False))

    def get_period_from_text(self, period_text: str) -> int:
        """Convertit une période textuelle en numéro"""
        period_mapping = {
            "morning": 1,
            "afternoon": 2,
            "evening": 3,
            "M": 1,
            "AM": 2,
            "S": 3,
        }
        return period_mapping.get(period_text, 1)

    def get_available_personnel(self, date: date, period: Union[int, str]) -> List[str]:
        """Retourne la liste du personnel disponible pour une période"""
        if isinstance(period, str):
            period = self.get_period_from_text(period)
        return [
            person for person in self.availability_matrix 
            if date in self.availability_matrix[person] and 
            self.availability_matrix[person][date][period]
        ]

    def update_availability(self, person: str, date: date, period: int, available: bool):
        """Met à jour la disponibilité"""
        try:
            if (person in self.availability_matrix and 
                date in self.availability_matrix[person]):
                self.availability_matrix[person][date][period] = available
                self._identify_critical_periods()  # Mettre à jour les périodes critiques
        except Exception as e:
            logger.error(f"Erreur mise à jour disponibilité pour {person} le {date}: {e}")
        
    def get_period_from_slot(self, slot: TimeSlot) -> int:
        """Détermine la période d'un slot"""
        start_hour = slot.start_time.hour
        if 7 <= start_hour < 13:
            return 1  # Matin
        elif 13 <= start_hour < 18:
            return 2  # Après-midi
        else:
            return 3  # Soir/Nuit

    def get_available_personnel(self, date: date, period: Union[int, str]) -> List[str]:
        """Retourne la liste du personnel disponible pour une période"""
        if isinstance(period, str):
            period = self.get_period_from_text(period)
        return [
            person for person in self.availability_matrix 
            if self.availability_matrix[person][date][period]
        ]


    def _update_critical_periods(self, date: date, period: int):
        """Met à jour les périodes critiques après une modification"""
        # Recalculer la disponibilité pour cette période
        available_count = sum(
            1 for person in self.availability_matrix 
            if self.availability_matrix[person][date][period]
        )
        
        # Mettre à jour la liste des périodes critiques
        self.critical_periods = [
            (d, p, c) for d, p, c in self.critical_periods 
            if d != date or p != period
        ]
        
        total_personnel = len(self.doctors) + len(self.cats)
        if available_count < total_personnel * 0.5:
            self.critical_periods.append((date, period, available_count))
            self.critical_periods.sort(key=lambda x: x[2])


   
    