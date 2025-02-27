# core/utils.py
from typing import Union
from datetime import datetime
import sys
import os

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    
    Args:
        relative_path (str): Relative path to the resource
        
    Returns:
        str: Absolute path to the resource
        
    Raises:
        FileNotFoundError: If the resource cannot be found
    """
    try:
        # Try to get the PyInstaller bundle path
        base_path = sys._MEIPASS
    except AttributeError:
        # Fallback to PLanning directory in development
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    full_path = os.path.normpath(os.path.join(base_path, relative_path))
    
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
        
    return full_path

from enum import IntEnum
from typing import Union

class PostPeriod(IntEnum):
    MORNING = 1
    AFTERNOON = 2
    EVENING = 3

STANDARD_POSTS = {
    PostPeriod.MORNING: {"ML", "MC", "MM", "CM", "HM", "SM", "RM"},
    PostPeriod.AFTERNOON: {"CA", "HA", "SA", "RA", "AL", "AC", "CT"},
    PostPeriod.EVENING: {"CS", "HS", "SS", "RS", "NC", "NM", "NL", "NA"}
}

def get_post_period(post_or_slot: Union[str, object]) -> PostPeriod:
    """
    Détermine la période d'un poste basé sur la plage horaire majoritaire.
    
    Args:
        post_or_slot: Soit un code de poste (str) soit un objet avec start_time et end_time
        
    Returns:
        PostPeriod: Enum représentant la période du poste
        
    Examples:
        >>> get_post_period("ML")  # Matin
        <PostPeriod.MORNING: 0>
        
        >>> get_post_period(slot_object)  # Après-midi
        <PostPeriod.AFTERNOON: 1>
    """
    # Pour les postes standards (strings)
    if isinstance(post_or_slot, str):
        for period, codes in STANDARD_POSTS.items():
            if post_or_slot in codes:
                return period
        return PostPeriod.EVENING
    
    # Pour les postes avec horaires
    start_hour = post_or_slot.start_time.hour
    end_hour = post_or_slot.end_time.hour
    
    # Si le poste traverse minuit
    if end_hour < start_hour:
        hours_range = list(range(start_hour, 24)) + list(range(0, end_hour + 1))
    else:
        hours_range = list(range(start_hour, end_hour + 1))
    
    # Compte des heures dans chaque période (ajusté pour les nouvelles valeurs)
    period_counts = {
        PostPeriod.MORNING: sum(1 for h in hours_range if 7 <= (h % 24) < 13),    # 1: Matin (7h-13h)
        PostPeriod.AFTERNOON: sum(1 for h in hours_range if 13 <= (h % 24) < 18),  # 2: Après-midi (13h-18h)
        PostPeriod.EVENING: sum(1 for h in hours_range if (h % 24) >= 18 or (h % 24) < 7)  # 3: Soir/Nuit (18h-7h)
    }
    
    # Retourne la période avec le plus d'heures
    return max(period_counts.items(), key=lambda x: x[1])[0]
