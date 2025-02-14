#core/Constantes//day_type.py

from datetime import date
from workalendar.europe import France
from typing import List
import logging

logger = logging.getLogger(__name__)

class DayType:
   
    @staticmethod
    def get_day_type(date: date, cal: France) -> str:
        """
        Détermine le type de jour de manière cohérente.
        Ordre de priorité : pont > férié > dimanche > samedi > semaine
        """
        # D'abord vérifier si c'est un jour de pont
        if DayType.is_bridge_day(date, cal):
            logger.debug(f"{date} est un jour de pont")
            return "sunday_holiday"  # Les ponts sont traités comme des fériés
            
        # Ensuite vérifier si c'est un férié
        if cal.is_holiday(date):
            logger.debug(f"{date} est un jour férié")
            return "sunday_holiday"
            
        # Puis vérifier dimanche et samedi
        if date.weekday() == 6:  # Dimanche
            return "sunday_holiday"
        elif date.weekday() == 5:  # Samedi
            return "saturday"
        else:
            return "weekday"

    @staticmethod
    def is_bridge_day(day: date, cal: France) -> bool:
        """Détermine si une date est un jour de pont"""
        from datetime import timedelta
        
        # 1) Lundi avant un mardi férié
        if day.weekday() == 0 and cal.is_holiday(day + timedelta(days=1)):
            return True
        
        # 2) Vendredi et samedi après un jeudi férié
        if day.weekday() in [4, 5] and cal.is_holiday(day - timedelta(days=1 if day.weekday() == 4 else 2)):
            return True
        
        # 3) Samedi après un vendredi férié
        if day.weekday() == 5 and cal.is_holiday(day - timedelta(days=1)):
            return True
        
        # 4) Jour de semaine entre deux jours fériés
        if 0 <= day.weekday() <= 4:
            if (cal.is_holiday(day - timedelta(days=1)) and 
                cal.is_holiday(day + timedelta(days=1))):
                return True
        
        return False