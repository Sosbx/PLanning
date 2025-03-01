# © 2024 HILAL Arkane. Tous droits réservés.
# # core/Constantes/models.py
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import List, Dict, Optional, TYPE_CHECKING, Union
import logging
import datetime
from workalendar.europe import France
from core.Constantes.day_type import DayType

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .models import TimeSlot

ALL_POST_TYPES = [
    "ML","MC", "MM", "CM", "HM", "RM", "SM", "CA", "HA", "RA", "SA", "CS", "HS", "RS", "SS","AL", "AC",
    "NC", "NA", "NM", "NL", "CT"
]
WEEKEND_COMBINATIONS = [
    "MLCA", "MLHA", "MLSA", "MLRA", "MCCA", "MCHA", "MCRA", "MCSA", "MLAC"
    "CMCA", "MMCA", "CACS", "HMHA", "HAHS", "SMSA", "SASS", "RMRA", "RARS",
    "CMAC", "MMAC", "CMAL", "MMAL", "HMAL", "HMAC", "RMAL", "RMAC", "SMAL", "SMAC", 
    "MCAL", "CMRS", "CMSS", "CMHS",
    "MLCS", "MLRS", "MLSS", "MLHS", "MMCS",
    "MCCS", "MCRS", "MCSS", 'MCHS'
]

WEEKDAY_COMBINATIONS = [
    "MLCA", "MLHA", "MLSA", "MLRA", "MCCA", "MCHA", "MCRA", "MCSA", "MLAC"
    "CMCA", "MMCA", "CACS", "HMHA", "HAHS", "SMSA", "SASS", "RMRA", "RARS",
    "CMAC", "MMAC", "CMAL", "MMAL", "HMAL", "HMAC", "RMAL", "RMAC", "SMAL", "SMAC", 
    "MCAL", "CMRS", "CMSS", "CMHS", "CMNC", "SMCS", "SMHS",
    "MLCS", "MLRS", "MLSS", "MLHS", "MMCS",
    "MCCS", "MCRS", "MCSS", 'MCHS'
]

WEEKDAY_PRIORITY_GROUPS = {
    'high_priority': [
        "MCCA",  "MLCA",  
        "MMCA", "CMCA", "CACS", "HMHA", "HAHS", "RMRA", "RARS", "SMSA", "SASS"
    ],
    'medium_priority': [
        "MCRA", "MCSA", "MLAC","MCHA",
        "CMAC", "MMAC", "CMAL", "MMAL", "HMAL", "HMAC", 
        "RMAL", "RMAC", "SMAL", "SMAC", "MCAL", "CMCS",
        "CMHS", "CMNC", "MLCS", "MLRS", "MLSS", "MLHS", "MMCS","MLSA", "MLRA","MLHA"
    ],
    'low_priority': [
        "CMRS", "CMSS", "SMCS", "SMHS", "SMRS",
        "MCCS", "MCRS", "MCSS", "MCHS",
    ]
}

# Facteurs de priorité pour le calcul du score
PRIORITY_WEIGHTS = {
    'high_priority': 1.7,    # Bonus de 50% pour haute priorité
    'medium_priority': 1.0,  # Score normal pour priorité moyenne
    'low_priority': 0.4      # Pénalité de 30% pour basse priorité
}

ALL_COMBINATIONS = WEEKEND_COMBINATIONS + [combo for combo in WEEKDAY_COMBINATIONS if combo not in WEEKEND_COMBINATIONS]

@dataclass
class TimeSlot:
    start_time: datetime
    end_time: datetime
    site: str
    slot_type: str
    abbreviation: str
    assignee: str = None
    is_pre_attributed: bool = False  # Nouveau champ avec valeur par défaut False
    
class DesiderataPeriod(Enum):
    MORNING = 1
    AFTERNOON = 2
    NIGHT = 3



class Desiderata:
    def __init__(self, start_date, end_date, type: str, period: int, priority: str = "primary"):
        self.start_date = self._ensure_date(start_date)
        self.end_date = self._ensure_date(end_date)
        self.type = type
        self.period = period
        self.priority = priority  # "primary" ou "secondary"


    @staticmethod
    def _ensure_date(date_input):
        if isinstance(date_input, datetime.date):
            return date_input
        elif isinstance(date_input, str):
            try:
                return datetime.date.fromisoformat(date_input)
            except ValueError:
                try:
                    return datetime.datetime.strptime(date_input, "%Y-%m-%d").date()
                except ValueError:
                    return datetime.date.today()
        return datetime.date.today()

    def __repr__(self):
        return f"Desiderata(start_date={self.start_date}, end_date={self.end_date}, type='{self.type}', period={self.period})"

    def overlaps_with_slot(self, slot: 'TimeSlot') -> bool:
        """
        Vérifie si un desiderata chevauche un slot, avec simplification pour CT
        """
        if self.start_date <= slot.start_time.date() <= self.end_date:
            # Si c'est un poste CT, toujours le considérer comme après-midi (période 2)
            if slot.abbreviation == "CT":
                return self.period == 2
            
            # Sinon, utiliser la méthode normale
            slot_period = self.get_slot_period(slot)
            return self.period == slot_period
        return False

    @staticmethod
    def get_slot_period(slot: 'TimeSlot') -> int:
        """
        Détermine la période d'un slot (1: matin, 2: après-midi, 3: soir/nuit)
        Simplifie le traitement de CT en l'attribuant toujours à l'après-midi
        """
        # Si c'est un poste CT, toujours le considérer comme après-midi
        if slot.abbreviation == "CT":
            return 2  # Toujours considéré comme période après-midi
        
        # Pour les autres postes, vérifier l'heure de début
        start_time = slot.start_time
        if hasattr(start_time, 'hour'):  # Vérification plus sûre
            start_hour = start_time.hour
        else:
            # Gérer le cas où start_time n'est pas un objet time/datetime
            # Si c'est une chaîne ou un autre format, essayer de l'interpréter
            # Pour cet exemple, on suppose que ce cas ne devrait pas se produire
            logger.warning(f"Type inattendu pour start_time: {type(start_time)}")
            return 2  # Valeur par défaut pour éviter les erreurs
        
        # Définition des périodes
        if 7 <= start_hour < 13:
            return 1  # Matin
        elif 13 <= start_hour < 18:
            return 2  # Après-midi
        else:
            return 3  # Soir/nuit
        
@dataclass
class Doctor:
    name: str
    half_parts: int
    desiderata: List[Desiderata] = field(default_factory=list)
    
    
    # Gardes de nuit pour le weekend
    weekend_night_shifts: Dict[str, int] = field(default_factory=lambda: {'NLv': 0, 'NLs': 0, 'NLd': 0, 'total': 0})
    min_nlw: int = 0
    max_nlw: int = 0
    nam_shifts: Dict[str, int] = field(default_factory=lambda: {'NMs': 0, 'NMd': 0, 'NAs': 0, 'NAd': 0, 'total': 0})

    # Pour NLw
    nl_subtypes_counts: Dict[str, int] = field(default_factory=lambda: {
        'NLv': 0,  # Vendredi
        'NLs': 0,  # Samedi
        'NLd': 0   # Dimanche/Férié
    })
    
    # Pour NAMw
    nam_subtypes_counts: Dict[str, int] = field(default_factory=lambda: {
        'NA': 0,  # Nuit courte
        'NM': 0   # Nuit moyenne
    })
    
    # Gardes de nuit pour la semaine
    weekday_night_shifts: Dict[str, int] = field(default_factory=lambda: {'NL': 0, 'total': 0})
    min_nlw_weekday: int = 0
    max_nlw_weekday: int = 0
    
    # Gardes NM pour le weekend
    nam_shifts: Dict[str, int] = field(default_factory=lambda: {'NMs': 0, 'NMd': 0, 'NAs': 0, 'NAd': 0, 'total': 0})
    min_nam: int = 0
    max_nam: int = 0
    
    # Combinaisons pour le weekend
    combo_counts: Dict[str, int] = field(default_factory=lambda: {combo: 0 for combo in WEEKEND_COMBINATIONS})
    min_combo_counts: Dict[str, int] = field(default_factory=lambda: {combo: 0 for combo in WEEKEND_COMBINATIONS})
    max_combo_counts: Dict[str, int] = field(default_factory=lambda: {combo: float('inf') for combo in WEEKEND_COMBINATIONS})
    # Ajout de l'attribut manquant pour les combinaisons weekend
    weekend_combo_counts: Dict[str, int] = field(
        default_factory=lambda: {combo: 0 for combo in WEEKEND_COMBINATIONS}
    )
    # Combinaisons pour la semaine
    weekday_combo_counts: Dict[str, int] = field(default_factory=lambda: {combo: 0 for combo in WEEKDAY_COMBINATIONS})
    min_weekday_combos: Dict[str, int] = field(default_factory=dict)
    max_weekday_combos: Dict[str, int] = field(default_factory=dict)
    
    # Groupes pour le weekend
    group_counts: Dict[str, Union[int, Dict[str, int]]] = field(default_factory=lambda: {
        "CsSD": {"CS": 0, "HS": 0, "RS": 0, "SS": 0, "total": 0},
        "VmS": 0, "VmD": 0, "VaSD": 0, "CmS": 0, "CmD": 0, "CaSD": 0, "NAMw": 0, "NLw": 0
    })
    
    # Groupes pour la semaine
    weekday_group_counts: Dict[str, int] = field(default_factory=lambda: {
    group: 0 for group in ["XmM", "XM", "XA", "XS", "NM", "NC", "ML"]  # Vérifions ici
    })
    
    # Nouveaux attributs pour les postes de semaine
    weekday_post_counts: Dict[str, int] = field(default_factory=lambda: {post_type: 0 for post_type in ALL_POST_TYPES})
    min_weekday_posts: Dict[str, int] = field(default_factory=lambda: {post_type: 0 for post_type in ALL_POST_TYPES})
    max_weekday_posts: Dict[str, int] = field(default_factory=lambda: {post_type: float('inf') for post_type in ALL_POST_TYPES})
    
    cs_count: int = 0
    post_type_counts: Dict[str, int] = field(default_factory=dict)
    min_combos: Dict[str, int] = field(default_factory=dict)
    max_combos: Dict[str, int] = field(default_factory=dict)
    min_weekday_combos: Dict[str, int] = field(default_factory=dict)
    max_weekday_combos: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Initialisation post-création"""
        # S'assurer que toutes les combinaisons possibles sont initialisées
        for combo in WEEKEND_COMBINATIONS:
            if combo not in self.combo_counts:
                self.combo_counts[combo] = 0
            if combo not in self.min_combo_counts:
                self.min_combo_counts[combo] = 0
            if combo not in self.max_combo_counts:
                self.max_combo_counts[combo] = float('inf')
        
        for combo in WEEKDAY_COMBINATIONS:
            if combo not in self.weekday_combo_counts:
                self.weekday_combo_counts[combo] = 0
            if combo not in self.min_weekday_combos:
                self.min_weekday_combos[combo] = 0
            if combo not in self.max_weekday_combos:
                self.max_weekday_combos[combo] = float('inf')
            
    def can_work_shift(self, date: date, shift: 'TimeSlot') -> bool:
        if shift.abbreviation == "CT":
            for desiderata in self.desiderata:
                if desiderata.start_date <= date <= desiderata.end_date:
                    if desiderata.period in [1, 2]:  # Matin ou après-midi
                        return False
            return True
        else:
            for desiderata in self.desiderata:
                if desiderata.start_date <= date <= desiderata.end_date:
                    if desiderata.overlaps_with_slot(shift):
                        return False
            return True

    def update_shift_count(self, shift_type: str, is_weekend: bool):
        if is_weekend:
            if shift_type.startswith('NL'):
                self.weekend_night_shifts[shift_type] += 1
                self.weekend_night_shifts['total'] += 1
            elif shift_type.startswith('NM'):
                self.nm_shifts[shift_type] += 1
                self.nm_shifts['total'] += 1
        else:
            if shift_type == 'NL':
                self.weekday_night_shifts['NL'] += 1
                self.weekday_night_shifts['total'] += 1
            elif shift_type == 'NM':
                self.weekday_nm_shifts['NM'] += 1
                self.weekday_nm_shifts['total'] += 1

        self.post_type_counts[shift_type] = self.post_type_counts.get(shift_type, 0) + 1

    def update_combo_count(self, combo: str, is_weekend: bool):
        if is_weekend:
            self.combo_counts[combo] = self.combo_counts.get(combo, 0) + 1
        else:
            self.weekday_combo_counts[combo] = self.weekday_combo_counts.get(combo, 0) + 1

    def update_group_count(self, group: str, is_weekend: bool):
        if is_weekend:
            self.group_counts[group] = self.group_counts.get(group, 0) + 1
        else:
            self.weekday_group_counts[group] = self.weekday_group_counts.get(group, 0) + 1
    
@dataclass
class CAT:
    def __init__(self, name, desiderata=None):
        self.name = name
        self.posts = {}
        self.weekday_posts = {}  # Ajoutez cette ligne
        self.desiderata = desiderata if desiderata is not None else []

class SlotType(Enum):
    CONSULTATION = "Consultation"
    VISITE = "Visite"

class Site(Enum):
    CENON = "Cenon"
    BEYCHAC_ET_CAILLAU = "Beychac et Caillau"
    ST_ANDRE_DE_CUBZAC = "St André de Cubzac"
    CREON = "Créon"
    VISITES = "Visites"


@dataclass
class DayPlanning:
    date: date
    slots: List[TimeSlot] = field(default_factory=list)
    is_weekend: bool = False
    is_holiday_or_bridge: bool = False
    planning: Optional['Planning'] = None  # Ajout de la référence au planning parent



@dataclass
class Planning:
    def __init__(self, start_date: date, end_date: date, filename: str = None):
        self.start_date = start_date
        self.end_date = end_date
        self.days: List[DayPlanning] = []
        self.pre_analysis_results = None
        self.cats: List[CAT] = []  # Liste des CATs
        self.filename = filename  # Nom du fichier source
        self.weekend_validated = False  # Flag pour suivre la validation des weekends
        
        # Nouveaux attributs pour les phases de génération
        self.nl_distributed = False  # Flag pour suivre la distribution des NL
        self.nl_validated = False  # Flag pour suivre la validation des NL
        self.nam_distributed = False  # Flag pour suivre la distribution des NA/NM
        self.nam_validated = False  # Flag pour suivre la validation des NA/NM
        self.combinations_distributed = False  # Flag pour suivre la distribution des combinaisons

    def set_pre_analysis_results(self, results):
        self.pre_analysis_results = results

    def set_pre_analysis_results(self, results):
        self.pre_analysis_results = results

    def get_day(self, date: date) -> Optional[DayPlanning]:
        return next((day for day in self.days if day.date == date), None)
    

@dataclass
class CATPostConfiguration:
    weekday: Dict[str, int] = field(default_factory=dict)
    saturday: Dict[str, int] = field(default_factory=dict)
    sunday_holiday: Dict[str, int] = field(default_factory=dict)

@dataclass
class PostConfig:
    total: int = 0

@dataclass
class SpecificPostConfig:
    start_date: date
    end_date: date
    apply_to: str
    post_counts: Dict[str, int]

    # Mapping des types de jours
    DAY_TYPE_MAPPING = {
        "weekday": "Semaine",
        "Semaine": "Semaine",
        "saturday": "Samedi",
        "Samedi": "Samedi",
        "sunday_holiday": "Dimanche/Férié",
        "Dimanche/Férié": "Dimanche/Férié"
    }

    def __post_init__(self):
        """Validation et normalisation après l'initialisation"""
        # Normaliser le type de jour
        normalized_type = self.DAY_TYPE_MAPPING.get(self.apply_to)
        if normalized_type is None:
            raise ValueError(f"Type de jour invalide : {self.apply_to}")
        self.apply_to = normalized_type

        # Vérifier les dates
        if self.start_date.year < 2024:
            if 1900 <= self.start_date.year < 2000:
                self.start_date = self.start_date.replace(year=self.start_date.year + 100)

        if self.end_date.year < 2024:
            if 1900 <= self.end_date.year < 2000:
                self.end_date = self.end_date.replace(year=self.end_date.year + 100)

        # Si les dates sont inversées, les échanger
        if self.end_date < self.start_date:
            self.start_date, self.end_date = self.end_date, self.start_date
            logger.warning(f"Dates inversées automatiquement corrigées pour la période {self.start_date} - {self.end_date}")

    def to_dict(self):
        """Convertit l'objet en dictionnaire"""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'apply_to': self.apply_to,
            'post_counts': self.post_counts
        }
    
    
    @classmethod
    def normalize_day_type(cls, day_type: str) -> str:
        """Normalise le type de jour"""
        normalized = cls.DAY_TYPE_MAPPING.get(day_type)
        if normalized is None:
            raise ValueError(f"Type de jour invalide : {day_type}")
        return normalized

   

    @classmethod
    def from_dict(cls, data):
        """Crée une instance à partir d'un dictionnaire"""
        return cls(
            start_date=datetime.date.fromisoformat(data['start_date']),
            end_date=datetime.date.fromisoformat(data['end_date']),
            apply_to=data['apply_to'],
            post_counts=data['post_counts']
        )

@dataclass
class DailyPostConfiguration:
    weekday: Dict[str, PostConfig] = field(default_factory=dict)
    saturday: Dict[str, PostConfig] = field(default_factory=dict)
    sunday_holiday: Dict[str, PostConfig] = field(default_factory=dict)
    cat_weekday: Dict[str, PostConfig] = field(default_factory=dict)
    cat_saturday: Dict[str, PostConfig] = field(default_factory=dict)
    cat_sunday_holiday: Dict[str, PostConfig] = field(default_factory=dict)
    specific_configs: List[SpecificPostConfig] = field(default_factory=list)

    def get_config_for_day_type(self, day_type: str) -> Dict[str, PostConfig]:
        if day_type == "weekday":
            return self.weekday
        elif day_type == "saturday":
            return self.saturday
        elif day_type == "sunday_holiday":
            return self.sunday_holiday
        else:
            raise ValueError(f"Invalid day type: {day_type}")

    def add_specific_config(self, specific_config: SpecificPostConfig):
        """
        Ajoute une nouvelle configuration spécifique en gérant les 
        chevauchements et la priorité.
        """
        # Vérifier les chevauchements
        overlapping_configs = []
        for existing_config in self.specific_configs:
            if (specific_config.start_date <= existing_config.end_date and 
                specific_config.end_date >= existing_config.start_date):
                overlapping_configs.append(existing_config)
        
        # Supprimer les configurations qui se chevauchent
        for config in overlapping_configs:
            self.specific_configs.remove(config)
            logger.debug(f"Configuration supprimée car chevauchement: "
                        f"{config.start_date} - {config.end_date}")
        
        # Ajouter la nouvelle configuration
        self.specific_configs.append(specific_config)
        logger.debug(f"Nouvelle configuration ajoutée: "
                    f"{specific_config.start_date} - {specific_config.end_date}")

    def remove_specific_config(self, specific_config: SpecificPostConfig):
        self.specific_configs.remove(specific_config)

    def get_post_count(self, date: date, day_type: str, post_type: str) -> int:
        """
        Récupère le nombre de postes pour une configuration donnée.
        Priorise les configurations spécifiques et gère correctement les jours de pont.
        
        Args:
            date: Date pour laquelle récupérer la configuration
            day_type: Type de jour initial
            post_type: Type de poste à récupérer
            
        Returns:
            int: Nombre de postes configurés
        """
        # Vérifier d'abord les configurations spécifiques
        for config in sorted(self.specific_configs, 
                           key=lambda x: (x.start_date, x.end_date), reverse=True):
            if config.start_date <= date <= config.end_date:
                # Si le poste est configuré spécifiquement, retourner sa valeur
                if post_type in config.post_counts:
                    logger.debug(f"Configuration spécifique trouvée pour {date}: "
                               f"{post_type}={config.post_counts[post_type]}")
                    return config.post_counts[post_type]

        # Si aucune configuration spécifique n'est trouvée, 
        # vérifier si c'est un jour de pont
        cal = France()
        if DayType.is_bridge_day(date, cal) or cal.is_holiday(date):
            logger.debug(f"{date} est un jour férié/pont, utilisation de la "
                        "configuration sunday_holiday")
            return self.sunday_holiday.get(post_type, PostConfig()).total
        
        # Sinon utiliser la configuration standard selon le type de jour
        if day_type == "weekday":
            return self.weekday.get(post_type, PostConfig()).total
        elif day_type == "saturday":
            return self.saturday.get(post_type, PostConfig()).total
        elif day_type == "sunday_holiday":
            return self.sunday_holiday.get(post_type, PostConfig()).total
        else:
            raise ValueError(f"Type de jour invalide: {day_type}")


        
    def get_cat_post_count(self, date: date, day_type: str, post_type: str) -> int:
        # Chercher d'abord une configuration spécifique
        for config in self.specific_configs:
            if (config.start_date <= date <= config.end_date and
                config.day_type == day_type and
                config.post_type == post_type):
                return config.count

        # Si aucune configuration spécifique n'est trouvée, utiliser la configuration standard pour les CAT
        if day_type == "weekday":
            return self.cat_weekday.get(post_type, PostConfig()).total
        elif day_type == "saturday":
            return self.cat_saturday.get(post_type, PostConfig()).total
        elif day_type == "sunday_holiday":
            return self.cat_sunday_holiday.get(post_type, PostConfig()).total
        else:
            raise ValueError(f"Invalid day type: {day_type}")
        
def create_default_post_configuration():
    weekday_config = {
        "NL": PostConfig(total=2),
        "NM": PostConfig(total=2),
        "NA": PostConfig(total=0),
        "NC": PostConfig(total=1),
        "AC": PostConfig(total=0),
        "AL": PostConfig(total=0),
        "ML": PostConfig(total=2),
        "MC": PostConfig(total=0),
        "MM": PostConfig(total=1),
        "CM": PostConfig(total=1),
        "CT": PostConfig(total=0),
        "CA": PostConfig(total=2),
        "CS": PostConfig(total=1),
        "HM": PostConfig(total=1),
        "HA": PostConfig(total=1),
        "HS": PostConfig(total=1),
        "SM": PostConfig(total=0),
        "SA": PostConfig(total=0),
        "SS": PostConfig(total=1),
        "RM": PostConfig(total=0),
        "RA": PostConfig(total=0),
        "RS": PostConfig(total=1)      
    }

    saturday_config = {
        "NL": PostConfig(total=2),
        "NM": PostConfig(total=2),
        "NA": PostConfig(total=1),
        "NC": PostConfig(total=0),
        "AC": PostConfig(total=1),
        "AL": PostConfig(total=2),
        "ML": PostConfig(total=2),
        "MC": PostConfig(total=0),
        "MM": PostConfig(total=1),
        "CM": PostConfig(total=1),
        "CA": PostConfig(total=2),
        "CS": PostConfig(total=1),
        "HM": PostConfig(total=1),
        "HA": PostConfig(total=1),
        "HS": PostConfig(total=1),
        "SM": PostConfig(total=0),
        "SA": PostConfig(total=1),
        "SS": PostConfig(total=1),
        "RM": PostConfig(total=0),
        "RA": PostConfig(total=1),
        "RS": PostConfig(total=1) 
    }

    sunday_holiday_config = {
        "NL": PostConfig(total=2),
        "NM": PostConfig(total=2),
        "NA": PostConfig(total=1),
        "NC": PostConfig(total=0),
        "AC": PostConfig(total=1),
        "AL": PostConfig(total=2),
        "ML": PostConfig(total=2),
        "MC": PostConfig(total=1),
        "MM": PostConfig(total=0),
        "CM": PostConfig(total=1),
        "CA": PostConfig(total=2),
        "CS": PostConfig(total=1),
        "HM": PostConfig(total=1),
        "HA": PostConfig(total=1),
        "HS": PostConfig(total=1),
        "SM": PostConfig(total=1),
        "SA": PostConfig(total=1),
        "SS": PostConfig(total=1),
        "RM": PostConfig(total=1),
        "RA": PostConfig(total=1),
        "RS": PostConfig(total=1) 
    }

    # Configuration par défaut pour les CAT
    cat_weekday_config = {
        "NL": PostConfig(total=1),
        "NLv": PostConfig(total=1),  # Ajout de la configuration NLv
        "NM": PostConfig(total=1),
        "ML": PostConfig(total=1),
        "CA": PostConfig(total=1),
        "CS": PostConfig(total=1),
        "NC": PostConfig(total=1)
    }

    cat_saturday_config = {
        "NL": PostConfig(total=1),
        "NM": PostConfig(total=1),
        "ML": PostConfig(total=1),
        "AL": PostConfig(total=1),
        "CA": PostConfig(total=1),
        "CS": PostConfig(total=1),
        "NA": PostConfig(total=1)
    }

    cat_sunday_holiday_config = {
        "NL": PostConfig(total=1),
        "NM": PostConfig(total=1),
        "ML": PostConfig(total=1),
        "AL": PostConfig(total=1),
        "CA": PostConfig(total=1),
        "CS": PostConfig(total=1),
        "NA": PostConfig(total=1)
    }

    return DailyPostConfiguration(
        weekday=weekday_config,
        saturday=saturday_config,
        sunday_holiday=sunday_holiday_config,
        cat_weekday=cat_weekday_config,
        cat_saturday=cat_saturday_config,
        cat_sunday_holiday=cat_sunday_holiday_config
    )



class PostManager:
    """Classe pour gérer les différents types de postes et leurs horaires en fonction du jour de la semaine."""
    
    def __init__(self):
        # Dictionnaire contenant les types de poste pour la semaine
        self.weekday_posts = {
            "ML": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "Visites"},
            "MM": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "Cenon"},
            "AL": {"start_time": time(13, 0), "end_time": time(19, 59), "site": "Visites"},
            "MC": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Visites"},
            "AC": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Visites"},
            "NA": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Visites"},
            "NC": {"start_time": time(20, 0), "end_time": time(23, 59), "site": "Visites"},
            "NM": {"start_time": time(20, 0), "end_time": time(1, 59), "site": "Visites"},
            "NL": {"start_time": time(20, 0), "end_time": time(6, 59), "site": "Visites"},
            "CM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Cenon"},
            "CT": {"start_time": time(11, 0), "end_time": time(15, 59), "site": "Cenon"},
            "CA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Cenon"},
            "CS": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Cenon"},
            "HM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Beychac et Caillau"},
            "HA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Beychac et Caillau"},
            "HS": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Beychac et Caillau"},
            "SM": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "St André de Cubzac"},
            "SA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "St André de Cubzac"},
            "SS": {"start_time": time(20, 0), "end_time": time(23, 59), "site": "St André de Cubzac"},
            "RM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Créon"},
            "RA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Créon"},
            "RS": {"start_time": time(20, 0), "end_time": time(23, 59), "site": "Créon"},
        }

        # Dictionnaire pour les postes du samedi
        self.saturday_posts = {
            "ML": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "Visites"},
            "MM": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "Cenon"},
            "AL": {"start_time": time(13, 0), "end_time": time(19, 59), "site": "Visites"},
            "MC": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Visites"},
            "AC": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Visites"},
            "NA": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Visites"},
            "NC": {"start_time": time(20, 0), "end_time": time(23, 59), "site": "Visites"},
            "NM": {"start_time": time(20, 0), "end_time": time(1, 59), "site": "Visites"},
            "NL": {"start_time": time(20, 0), "end_time": time(6, 59), "site": "Visites"},
            "CM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Cenon"},
            "CA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Cenon"},
            "CS": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Cenon"},
            "HM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Beychac et Caillau"},
            "HA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Beychac et Caillau"},
            "HS": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Beychac et Caillau"},
            "SM": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "St André de Cubzac"},
            "SA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "St André de Cubzac"},
            "SS": {"start_time": time(18, 0), "end_time": time(23, 59), "site": "St André de Cubzac"},
            "RM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Créon"},
            "RA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Créon"},
            "RS": {"start_time": time(18, 0), "end_time": time(23, 59), "site": "Créon"},
        }

        # Dictionnaire pour les postes du dimanche et jours fériés
        self.sunday_holiday_posts = {
            "ML": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "Visites"},
            "MM": {"start_time": time(7, 0), "end_time": time(12, 59), "site": "Cenon"},
            "AL": {"start_time": time(13, 0), "end_time": time(19, 59), "site": "Visites"},
            "MC": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Visites"},
            "AC": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Visites"},
            "NA": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Visites"},
            "NC": {"start_time": time(20, 0), "end_time": time(23, 59), "site": "Visites"},
            "NM": {"start_time": time(20, 0), "end_time": time(1, 59), "site": "Visites"},
            "NL": {"start_time": time(20, 0), "end_time": time(6, 59), "site": "Visites"},
            "CM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Cenon"},
            "CA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Cenon"},
            "CS": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Cenon"},
            "HM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Beychac et Caillau"},
            "HA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Beychac et Caillau"},
            "HS": {"start_time": time(18, 0), "end_time": time(22, 59), "site": "Beychac et Caillau"},
            "SM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "St André de Cubzac"},
            "SA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "St André de Cubzac"},
            "SS": {"start_time": time(18, 0), "end_time": time(23, 59), "site": "St André de Cubzac"},
            "RM": {"start_time": time(9, 0), "end_time": time(12, 59), "site": "Créon"},
            "RA": {"start_time": time(13, 0), "end_time": time(17, 59), "site": "Créon"},
            "RS": {"start_time": time(18, 0), "end_time": time(23, 59), "site": "Créon"},
        }

    def get_post_details(self, post_type, day_type):
        """Retourne les détails d'un poste spécifique en fonction du jour (weekday, samedi, dimanche)."""
        if day_type == "weekday":
            return self.weekday_posts.get(post_type, None)
        elif day_type == "saturday":
            return self.saturday_posts.get(post_type, None)
        elif day_type == "sunday_holiday":
            return self.sunday_holiday_posts.get(post_type, None)

    def get_posts_for_day(self, day_type):
        """Retourne tous les postes disponibles pour un jour donné (semaine, samedi, ou dimanche/jour férié)."""
        if day_type == "weekday":
            return self.weekday_posts
        elif day_type == "saturday":
            return self.saturday_posts
        elif day_type == "sunday_holiday":
            return self.sunday_holiday_posts
