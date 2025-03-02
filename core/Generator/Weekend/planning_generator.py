# core/Generator/Weekend/planning_generator.py

"""
planning_generator.py
Module de génération du planning basé sur les résultats de la pré-analyse
"""

import logging
import random
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple, Union
import math
from core.Constantes.models import (
    Doctor, CAT, Planning, DayPlanning, TimeSlot, PostManager, PostConfig,SpecificPostConfig,
    ALL_POST_TYPES, WEEKDAY_COMBINATIONS, WEEKEND_COMBINATIONS
)
from core.Constantes.constraints import PlanningConstraints
from core.Analyzer.pre_analyzer import PlanningPreAnalyzer
from core.Constantes.data_persistence import DataPersistence
from core.Constantes.day_type import DayType
from core.Constantes.custom_post import CustomPost
from collections import defaultdict
from core.Generator.Weekday.weekday_gen import WeekdayGenerator
from copy import deepcopy
from workalendar.europe import France


logger = logging.getLogger(__name__)

class PlanningGenerator:
    def __init__(self, doctors: List[Doctor], cats: List[CAT], post_configuration, pre_attributions=None):
        """
        Initialise le générateur de planning.
        
        Args:
            doctors: Liste des médecins
            cats: Liste des CAT
            post_configuration: Configuration des postes
            pre_attributions: Dictionnaire des pré-attributions {person_name: {(date, period): post_type}}
        """
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        
        # Normalisation des pré-attributions (gérer le cas où c'est un tuple)
        if pre_attributions is not None:
            if isinstance(pre_attributions, tuple):
                pre_attributions, _ = pre_attributions
        self.pre_attributions = pre_attributions if pre_attributions is not None else {}
        
        self.constraints = PlanningConstraints()
        self.cal = France()
        self.post_manager = PostManager()
        
        # Chargement des postes personnalisés
        data_persistence = DataPersistence()
        self.custom_posts = data_persistence.load_custom_posts()
        
        # Vérification que tous les postes sont bien des objets CustomPost
        invalid_posts = []
        for name, post in list(self.custom_posts.items()):
            if not isinstance(post, CustomPost):
                try:
                    self.custom_posts[name] = CustomPost.from_dict(post if isinstance(post, dict) else post.__dict__)
                except Exception as e:
                    logger.error(f"Impossible de convertir le poste {name}: {e}")
                    invalid_posts.append(name)
        
        # Supprimer les postes invalides
        for name in invalid_posts:
            del self.custom_posts[name]
        
        logger.info(f"Postes personnalisés chargés: {list(self.custom_posts.keys())}")
        
        # Initialisation du suivi de distribution 
        self.current_distribution = {
            "weekend": {
                person.name: {
                    "NLv": 0, "NLs": 0, "NLd": 0,  # NL weekend
                    "NAs": 0, "NAd": 0,  # NA weekend
                    "NMs": 0, "NMd": 0,  # NM weekend
                    "weekend_groups": {}  # Groupes weekend
                } for person in doctors + cats  # Ajouter aussi les CAT
            },
            "weekday": {
                person.name: {
                    "NL": 0,      # NL semaine
                    "weekday_groups": {}  # Groupes semaine
                } for person in doctors + cats  # Ajouter aussi les CAT
            }
        }
    def _initialize_planning_days(self, planning: Planning) -> None:
        """
        Initialise les jours du planning en gérant correctement les postes à quota zéro.
        """
        logger.info("\nINITIALISATION DU PLANNING")
        logger.info("=" * 80)

        planning.days = []
        current_date = planning.start_date

        while current_date <= planning.end_date:
            # Déterminer le type de jour et le statut de pont
            day_type = DayType.get_day_type(current_date, self.cal)
            is_bridge = DayType.is_bridge_day(current_date, self.cal)
            is_bridge_saturday = (current_date.weekday() == 5 and is_bridge)
            
            # Déterminer le type de jour effectif
            effective_day_type = day_type
            if is_bridge or is_bridge_saturday:
                effective_day_type = "sunday_holiday"
                
            # Vérifier configuration spécifique
            specific_config = self._get_specific_config(current_date, effective_day_type)
            if specific_config:
                config_to_use = specific_config
            else:
                if effective_day_type == "sunday_holiday":
                    config_to_use = self.post_configuration.sunday_holiday
                elif day_type == "saturday" and not is_bridge_saturday:
                    config_to_use = self.post_configuration.saturday
                else:
                    config_to_use = self.post_configuration.weekday

            # Créer l'instance du jour
            day = DayPlanning(
                date=current_date,
                slots=[],
                is_weekend=(day_type in ["saturday", "sunday_holiday"]),
                is_holiday_or_bridge=(day_type == "sunday_holiday" or is_bridge_saturday)
            )

            # Créer les slots standard et personnalisés
            self._create_standard_slots(day, config_to_use, day_type)
            self._create_custom_slots(day, config_to_use, day_type)

            planning.days.append(day)
            current_date += timedelta(days=1)

        # Vérifier les attributions des postes à quota zéro
        if not self._verify_zero_quota_assignments(planning):
            logger.warning("Certaines pré-attributions de postes à quota zéro n'ont pas été correctement appliquées")

        self._log_slots_summary(planning)
    def _get_specific_config(self, current_date: date, day_type: str) -> Optional[Dict]:
        """
        Vérifie s'il existe une configuration spécifique pour cette date.
        Prend en compte le type réel du jour (pont = Dimanche/Férié).
        
        Args:
            current_date: Date à vérifier
            day_type: Type de jour initial
            
        Returns:
            Optional[Dict]: Configuration spécifique ou None
        """
        if not hasattr(self.post_configuration, 'specific_configs'):
            return None

        # 1. Déterminer le type de jour effectif
        is_bridge = DayType.is_bridge_day(current_date, self.cal)
        is_bridge_saturday = (current_date.weekday() == 5 and is_bridge)
        
        # 2. Déterminer le type normalisé pour la recherche de configuration
        if is_bridge or is_bridge_saturday:
            normalized_type = "Dimanche/Férié"
            logger.debug(f"{current_date} est un jour de pont - recherche config Dimanche/Férié")
        else:
            normalized_type = {
                "weekday": "Semaine",
                "saturday": "Samedi",
                "sunday_holiday": "Dimanche/Férié"
            }[day_type]
            logger.debug(f"{current_date} est un jour normal - recherche config {normalized_type}")
        
        # 3. Rechercher une configuration spécifique
        for config in self.post_configuration.specific_configs:
            if (config.start_date <= current_date <= config.end_date and
                config.apply_to == normalized_type):
                logger.debug(f"Configuration spécifique trouvée pour {current_date}")

                # Convertir les valeurs de la configuration en objets PostConfig
                converted_config = {}
                for post_type, count in config.post_counts.items():
                    try:
                        if isinstance(count, PostConfig):
                            converted_config[post_type] = count
                        elif isinstance(count, dict):
                            if 'total' in count:
                                converted_config[post_type] = PostConfig(total=int(count['total']))
                            else:
                                converted_config[post_type] = PostConfig(total=0)
                        elif isinstance(count, (int, float)):
                            converted_config[post_type] = PostConfig(total=int(count))
                        else:
                            logger.warning(f"Type de count non géré pour {post_type}: {type(count)}")
                            converted_config[post_type] = PostConfig(total=0)
                            
                        logger.debug(f"Conversion réussie pour {post_type}: {converted_config[post_type].total}")
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Erreur lors de la conversion pour {post_type}: {e}")
                        converted_config[post_type] = PostConfig(total=0)
                
                return converted_config

        # 4. Si pas de configuration spécifique pour un pont, vérifier config Dimanche/Férié
        if (is_bridge or is_bridge_saturday) and normalized_type == "Dimanche/Férié":
            for config in self.post_configuration.specific_configs:
                if (config.start_date <= current_date <= config.end_date and
                    config.apply_to == "Dimanche/Férié"):
                    logger.debug(f"Configuration Dimanche/Férié trouvée pour le pont du {current_date}")
                    converted_config = {}
                    for post_type, count in config.post_counts.items():
                        try:
                            if isinstance(count, PostConfig):
                                converted_config[post_type] = count
                            elif isinstance(count, dict):
                                converted_config[post_type] = PostConfig(total=int(count.get('total', 0)))
                            elif isinstance(count, (int, float)):
                                converted_config[post_type] = PostConfig(total=int(count))
                            else:
                                converted_config[post_type] = PostConfig(total=0)
                        except (ValueError, TypeError) as e:
                            logger.error(f"Erreur lors de la conversion pour {post_type}: {e}")
                            converted_config[post_type] = PostConfig(total=0)
                    return converted_config
        
        logger.debug(f"Aucune configuration spécifique trouvée pour {current_date}")
        return None


    def _get_config_from_analysis(self, current_date: date, day_type: str) -> Dict:
        """
        Récupère la configuration à utiliser pour un jour donné.
        Prend en compte les configurations spécifiques et les jours de pont.
        """
        # 1. Déterminer le type effectif du jour
        is_bridge = DayType.is_bridge_day(current_date, self.cal)
        is_bridge_saturday = (current_date.weekday() == 5 and is_bridge)
        effective_day_type = "sunday_holiday" if (is_bridge or is_bridge_saturday) else day_type
        
        # 2. Vérifier les configurations spécifiques d'abord
        if hasattr(self.post_configuration, 'specific_configs'):
            # Normaliser le type de jour
            normalized_type = {
                "weekday": "Semaine",
                "saturday": "Samedi",
                "sunday_holiday": "Dimanche/Férié"
            }[effective_day_type]
            
            # Chercher une configuration spécifique
            for config in self.post_configuration.specific_configs:
                if (config.start_date <= current_date <= config.end_date and
                    config.apply_to == normalized_type):
                    logger.debug(f"{current_date} : configuration spécifique trouvée pour {normalized_type}")
                    return config.post_counts
            
            # Pour les ponts, chercher aussi une config Dimanche/Férié
            if is_bridge or is_bridge_saturday:
                for config in self.post_configuration.specific_configs:
                    if (config.start_date <= current_date <= config.end_date and
                        config.apply_to == "Dimanche/Férié"):
                        logger.debug(f"{current_date} : configuration Dimanche/Férié trouvée pour le pont")
                        return config.post_counts
        
        # 3. Utiliser la configuration standard appropriée
        if is_bridge or is_bridge_saturday:
            logger.debug(f"{current_date} : jour de pont - utilisation config sunday_holiday")
            return self.post_configuration.sunday_holiday
        elif day_type == "sunday_holiday":
            logger.debug(f"{current_date} : dimanche/férié standard")
            return self.post_configuration.sunday_holiday
        elif day_type == "saturday" and not is_bridge_saturday:
            logger.debug(f"{current_date} : samedi standard")
            return self.post_configuration.saturday
        else:
            logger.debug(f"{current_date} : jour de semaine standard")
            return self.post_configuration.weekday
        
    def _normalize_day_type(self, day_type: str) -> str:
        """
        Normalise le type de jour pour la comparaison avec les configurations spécifiques.
        """
        mapping = {
            "weekday": "Semaine",
            "saturday": "Samedi",
            "sunday_holiday": "Dimanche/Férié"
        }
        return mapping.get(day_type, day_type)

    def _get_config_value(self, config_item) -> int:
        """
        Extrait la valeur numérique d'une configuration, qu'elle soit PostConfig ou autre.
        
        Args:
            config_item: Item de configuration (PostConfig, dict, int, etc.)
            
        Returns:
            int: Valeur numérique de la configuration
        """
        try:
            if isinstance(config_item, PostConfig):
                return config_item.total
            elif isinstance(config_item, dict):
                return int(config_item.get('total', 0))
            elif isinstance(config_item, (int, float)):
                return int(config_item)
            else:
                logger.warning(f"Type de configuration non géré: {type(config_item)}")
                return 0
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Erreur lors de l'extraction de la valeur: {e}")
            return 0

    def _create_standard_slots(self, day: DayPlanning, config: Dict, day_type: str):
        """
        Version mise à jour qui intègre la gestion des postes à quota zéro
        """
        try:
            # 1. Déterminer le type effectif du jour
            is_bridge = DayType.is_bridge_day(day.date, self.cal)
            is_bridge_saturday = (day.date.weekday() == 5 and is_bridge)
            effective_day_type = "sunday_holiday" if (is_bridge or is_bridge_saturday) else day_type

            # 2. Vérifier s'il existe une configuration spécifique
            specific_config = self._get_specific_config(day.date, effective_day_type)
            config_to_use = specific_config if specific_config else (
                self.post_configuration.sunday_holiday if (is_bridge or is_bridge_saturday)
                else config
            )

            # 3. Créer les slots standards
            for post_type, config_value in config_to_use.items():
                # Ignorer les postes personnalisés
                if post_type in self.custom_posts:
                    continue

                # Extraire le nombre total de slots à créer
                total = self._get_config_value(config_value)
                
                # Si quota zéro, utiliser le gestionnaire spécial
                if total == 0:
                    self._handle_zero_quota_posts(config_to_use, day, day_type)
                    continue

                # Récupérer les détails du poste
                post_details = self.post_manager.get_post_details(post_type, day_type)
                if not post_details:
                    logger.warning(f"Pas de détails trouvés pour le poste {post_type}")
                    continue

                # Créer les slots requis
                for _ in range(total):
                    slot = TimeSlot(
                        start_time=datetime.combine(day.date, post_details['start_time']),
                        end_time=datetime.combine(
                            day.date + timedelta(days=1 if post_details['end_time'] < post_details['start_time'] else 0),
                            post_details['end_time']
                        ),
                        site=post_details['site'],
                        slot_type="Consultation" if "Visite" not in post_details['site'] else "Visite",
                        abbreviation=post_type,
                        assignee=None
                    )
                    day.slots.append(slot)

        except Exception as e:
            logger.error(f"Erreur lors de la création des slots standards: {e}", exc_info=True)
            raise

    def _create_custom_slots(self, day: DayPlanning, config: Dict, day_type: str):
        """
        Version mise à jour qui intègre la gestion des postes personnalisés.
        Ne crée pas de slots pour les postes à quota zéro, qui seront traités par _handle_zero_quota_posts.
        """
        if not self.custom_posts:
            return

        # 1. Déterminer le type effectif du jour et la configuration
        is_bridge = DayType.is_bridge_day(day.date, self.cal)
        is_bridge_saturday = (day.date.weekday() == 5 and is_bridge)
        effective_day_type = "sunday_holiday" if (is_bridge or is_bridge_saturday) else day_type

        # 2. Obtenir la configuration appropriée
        specific_config = self._get_specific_config(day.date, effective_day_type)
        if specific_config:
            config = specific_config
        elif is_bridge or is_bridge_saturday:
            config = self.post_configuration.sunday_holiday

        # 3. Traiter chaque poste personnalisé
        for post_name, custom_post in self.custom_posts.items():
            if effective_day_type not in custom_post.day_types:
                continue

            # Extraire la valeur configurée
            configured_count = self._get_config_value(config.get(post_name, PostConfig(total=0)))
            
            # Si quota zéro ou force_zero_count, ne pas créer de slots ici
            if configured_count == 0 or custom_post.force_zero_count:
                continue
                
            effective_count = custom_post.get_effective_quota(configured_count)
            
            # Créer les slots nécessaires
            for _ in range(effective_count):
                slot = TimeSlot(
                    start_time=datetime.combine(day.date, custom_post.start_time),
                    end_time=datetime.combine(
                        day.date + timedelta(days=1 if custom_post.end_time < custom_post.start_time else 0),
                        custom_post.end_time
                    ),
                    site="Personnalisé",
                    slot_type=custom_post.statistic_group.strip() if custom_post.statistic_group else "Personnalisé",
                    abbreviation=post_name,
                    assignee=None
                )
                day.slots.append(slot)
                
            
    def _handle_zero_quota_posts(self, config: Dict, day: DayPlanning, day_type: str) -> None:
        """
        Gère la création et l'attribution des slots pour les postes ayant un quota de 0.
        Optimisé pour éviter toute redondance et garantir l'unicité des slots.
        """
        # Identifier les postes à quota zéro
        zero_quota_posts = {
            post_type: config_value for post_type, config_value in config.items()
            if self._get_config_value(config_value) == 0
        }
        
        if not zero_quota_posts: 
            return

        # Récupérer les pré-attributions de manière sécurisée
        pre_attributions = self._get_pre_attributions()
        
        # Regrouper les pré-attributions par poste et par personne pour éviter les doublons
        attributions_by_post_person = {}
        
        for person_name, attributions in pre_attributions.items():
            for (attr_date, period), post_type in attributions.items():
                # Ne traiter que les pré-attributions pour cette date et pour les postes à quota zéro
                if attr_date != day.date or post_type not in zero_quota_posts:
                    continue
                    
                # Utiliser une clé unique (poste, personne) pour éviter les doublons
                key = (post_type, person_name)
                if key not in attributions_by_post_person:
                    attributions_by_post_person[key] = (post_type, person_name)
        
        # Créer un seul slot par combinaison unique (poste, personne)
        for post_type, person_name in attributions_by_post_person.values():
            logger.info(f"Traitement pré-attribution quota zéro: {person_name} - {post_type} le {day.date}")
            
            # Vérifier si un slot identique existe déjà
            has_identical_slot = False
            for slot in day.slots:
                if (slot.abbreviation == post_type and slot.assignee == person_name):
                    has_identical_slot = True
                    logger.info(f"Slot identique déjà existant pour {post_type} le {day.date} - Assigné à {person_name}")
                    break
                    
            # Créer un nouveau slot uniquement si nécessaire
            if not has_identical_slot:
                # Création du slot selon le type de poste
                if post_type in self.custom_posts:
                    custom_post = self.custom_posts[post_type]
                    new_slot = TimeSlot(
                        start_time=datetime.combine(day.date, custom_post.start_time),
                        end_time=datetime.combine(
                            day.date + timedelta(days=1 if custom_post.end_time < custom_post.start_time else 0),
                            custom_post.end_time
                        ),
                        site="Personnalisé",
                        slot_type=custom_post.statistic_group.strip() if custom_post.statistic_group else "Personnalisé",
                        abbreviation=post_type,
                        assignee=person_name,
                        is_pre_attributed=True
                    )
                    day.slots.append(new_slot)
                    logger.info(f"Nouveau slot créé pour {post_type} le {day.date} - Assigné à {person_name}")
                else:
                    # Pour les postes standards sans détails, créer un slot avec horaires par défaut
                    post_details = self.post_manager.get_post_details(post_type, day_type)
                    if post_details:
                        new_slot = TimeSlot(
                            start_time=datetime.combine(day.date, post_details['start_time']),
                            end_time=datetime.combine(
                                day.date + timedelta(days=1 if post_details['end_time'] < post_details['start_time'] else 0),
                                post_details['end_time']
                            ),
                            site=post_details['site'],
                            slot_type="Consultation" if "Visite" not in post_details['site'] else "Visite",
                            abbreviation=post_type,
                            assignee=person_name,
                            is_pre_attributed=True
                        )
                        day.slots.append(new_slot)
                        logger.info(f"Nouveau slot créé pour {post_type} le {day.date} - Assigné à {person_name}")
                    else:
                        # Créer un slot avec des horaires par défaut pour les postes sans détails
                        default_start = time(12, 0)  # Midi par défaut
                        default_end = time(17, 0)    # 17h par défaut
                        
                        # Utiliser des horaires spécifiques selon la première lettre du poste
                        if post_type.startswith('N'):  # Postes de nuit
                            default_start = time(20, 0)
                            default_end = time(8, 0)
                        elif post_type.startswith('C'):  # Postes de consultation
                            default_start = time(9, 0)
                            default_end = time(13, 0)
                        
                        new_slot = TimeSlot(
                            start_time=datetime.combine(day.date, default_start),
                            end_time=datetime.combine(
                                day.date + timedelta(days=1 if default_end < default_start else 0),
                                default_end
                            ),
                            site="Personnalisé (auto)",
                            slot_type="Personnalisé",
                            abbreviation=post_type,
                            assignee=person_name,
                            is_pre_attributed=True
                        )
                        day.slots.append(new_slot)
                        logger.info(f"Nouveau slot créé avec horaires par défaut pour {post_type} le {day.date} - Assigné à {person_name}")

    def _get_pre_attributions(self):
        """
        Récupère les pré-attributions de manière sécurisée.
        Gère les cas où pre_attributions est un tuple ou None.
        
        Returns:
            Dict: Dictionnaire des pré-attributions
        """
        if not hasattr(self, 'pre_attributions'):
            return {}
            
        pre_attributions = self.pre_attributions
        
        # Si pre_attributions est un tuple, extraire le dictionnaire
        if isinstance(pre_attributions, tuple):
            pre_attributions, _ = pre_attributions
        
        # S'assurer que pre_attributions est un dictionnaire
        if pre_attributions is None:
            pre_attributions = {}
                
        return pre_attributions


    def _verify_zero_quota_assignments(self, planning: Planning) -> bool:
        """
        Vérifie que toutes les pré-attributions de postes à quota zéro ont été correctement appliquées.
        
        Returns:
            bool: True si toutes les pré-attributions sont correctes
        """
        all_correct = True
        
        # Créer un index détaillé de tous les slots existants dans le planning
        # Format: {(date, abbreviation, assignee): [slot1, slot2, ...]}
        slots_index = {}
        for day in planning.days:
            for slot in day.slots:
                if slot.assignee:
                    key = (day.date, slot.abbreviation, slot.assignee)
                    if key not in slots_index:
                        slots_index[key] = []
                    slots_index[key].append(slot)
        
        # Vérifier chaque pré-attribution
        for person_name, attributions in self.pre_attributions.items():
            for (attr_date, period), post_type in attributions.items():
                key = (attr_date, post_type, person_name)
                
                # Vérifier si le slot existe pour cette combinaison (date, type, personne)
                if key not in slots_index or not slots_index[key]:
                    logger.error(f"Slot manquant pour {post_type} le {attr_date} (assigné à {person_name})")
                    all_correct = False
                    continue
                
                # Pour les postes standards (non personnalisés et non à quota zéro), vérifier aussi la période
                day_type = "weekday"
                if attr_date.weekday() == 5 and not DayType.is_bridge_day(attr_date, self.cal):
                    day_type = "saturday"
                elif attr_date.weekday() == 6 or self.cal.is_holiday(attr_date) or DayType.is_bridge_day(attr_date, self.cal):
                    day_type = "sunday_holiday"
                    
                is_zero_quota = self._is_zero_quota_post(post_type, attr_date, day_type)
                if not is_zero_quota and post_type not in self.custom_posts:
                    slot = slots_index[key][0]
                    slot_period = self._get_slot_period(slot)
                    
                    if slot_period != period:
                        logger.error(f"Période incorrecte pour {post_type} le {attr_date} "
                                    f"(assigné à {person_name}, attendu: période {period}, actuel: période {slot_period})")
                        all_correct = False
                        
        return all_correct


    def _log_custom_slots_creation(self, day: DayPlanning, post_name: str,
                                effective_count: int, configured_count: int) -> None:
        """
        Log les détails de la création des slots personnalisés.
        
        Args:
            day: Le jour concerné
            post_name: Nom du poste
            effective_count: Nombre de slots effectivement créés
            configured_count: Nombre de slots configurés
        """
        logger.info(f"Slots créés pour {post_name} le {day.date}:")
        logger.info(f"  - Configurés: {configured_count}")
        logger.info(f"  - Effectifs: {effective_count}")
        
        if effective_count != configured_count:
            logger.info("  - Différence due à:")
            if self.custom_posts[post_name].force_zero_count:
                logger.info("    * force_zero_count actif")
            if self.custom_posts[post_name].preserve_in_planning:
                logger.info("    * preserve_in_planning actif")

    def _log_slots_summary(self, planning: Planning):
        """
        Affiche un résumé détaillé des slots qui ont été créés.
        """
        logger.info("\nRÉSUMÉ DES SLOTS INITIALISÉS")
        logger.info("=" * 80)

        # Structure pour compter les slots par type de jour
        counts = {
            "weekday": defaultdict(int),    # Jours de semaine
            "saturday": defaultdict(int),    # Samedis normaux
            "sunday_holiday": defaultdict(int)  # Dimanches/Fériés/Ponts
        }

        # Les NL nécessitent un traitement spécial
        nl_slots = {
            "weekday": 0,   # Lundi-Jeudi
            "nlv": 0,       # Vendredi
            "nls": 0,       # Samedi normal
            "nld": 0        # Dimanche/Férié/Pont
        }

        # Compter les slots existants
        for day in planning.days:
            for slot in day.slots:
                if slot.abbreviation == "NL":
                    if day.is_holiday_or_bridge:
                        nl_slots["nld"] += 1
                    elif day.is_weekend and not day.is_holiday_or_bridge:
                        nl_slots["nls"] += 1
                    elif day.date.weekday() == 4:  # Vendredi
                        nl_slots["nlv"] += 1
                    else:
                        nl_slots["weekday"] += 1
                else:
                    if day.is_holiday_or_bridge:
                        counts["sunday_holiday"][slot.abbreviation] += 1
                    elif day.is_weekend and not day.is_holiday_or_bridge:
                        counts["saturday"][slot.abbreviation] += 1
                    else:
                        counts["weekday"][slot.abbreviation] += 1

        # Affichage des résultats
        for day_type, label in [
            ("weekday", "SEMAINE"),
            ("saturday", "SAMEDI"),
            ("sunday_holiday", "DIMANCHE/FÉRIÉ")
        ]:
            logger.info(f"\n{label}")
            logger.info("-" * 40)

            # Afficher d'abord les NL
            if day_type == "weekday":
                logger.info(f"NL (lundi-jeudi)   : {nl_slots['weekday']:3d} slots")
                logger.info(f"NL (vendredi)      : {nl_slots['nlv']:3d} slots")
            elif day_type == "saturday":
                logger.info(f"NL  : {nl_slots['nls']:3d} slots")
            else:
                logger.info(f"NL  : {nl_slots['nld']:3d} slots")

            # Afficher les autres postes triés
            if counts[day_type]:
                logger.info("\nAutres postes:")
                for post_type, count in sorted(counts[day_type].items()):
                    logger.info(f"{post_type:4}: {count:3d} slots")

        # Afficher les totaux NL
        logger.info("\nTOTAUX NL PAR CATÉGORIE:")
        logger.info("-" * 40)
        logger.info(f"NLv (Vendredi)        : {nl_slots['nlv']:3d} slots")
        logger.info(f"NLs (Samedi)          : {nl_slots['nls']:3d} slots")
        logger.info(f"NLd (Dimanche/Férié)  : {nl_slots['nld']:3d} slots")
        total_nl = sum(nl_slots.values())
        logger.info(f"Total NL              : {total_nl:3d} slots")

        # Statistiques NLd
        logger.info("\nSTATISTIQUES FINALES")
        logger.info("-" * 40)
        nld_days = nl_slots["nld"] // 2  # Car 2 slots par jour
        logger.info(f"Nombre total de jours NLd   : {nld_days}")
        logger.info(f"Nombre total de slots NLd   : {nl_slots['nld']}")

        # Vérification avec la pré-analyse
        if hasattr(planning, 'pre_analysis_results') and planning.pre_analysis_results is not None:
            target_nlw = planning.pre_analysis_results.get('adjusted_posts', {}).get('weekend_groups', {}).get('NLw', 0)
            if target_nlw:
                weekend_nl = nl_slots['nls'] + nl_slots['nld'] + nl_slots['nlv']
                logger.info(f"Requis selon pré-analyse    : {target_nlw}")
                if weekend_nl != target_nlw:
                    logger.warning(f"ATTENTION: Différence entre slots créés ({weekend_nl}) et requis ({target_nlw})")    
    def is_bridge_day(self, day: date) -> bool:
        """Détermine si une date est un jour de pont"""
        # 1) Lundi avant un mardi férié
        if day.weekday() == 0 and self.cal.is_holiday(day + timedelta(days=1)):
            return True
        
        # 2) Vendredi et samedi après un jeudi férié
        if day.weekday() in [4, 5] and self.cal.is_holiday(day - timedelta(days=1 if day.weekday() == 4 else 2)):
            return True
        
        # 3) Samedi après un vendredi férié
        if day.weekday() == 5 and self.cal.is_holiday(day - timedelta(days=1)):
            return True
        
        # 4) Jour de semaine entre deux jours fériés
        if 0 <= day.weekday() <= 4:
            if (self.cal.is_holiday(day - timedelta(days=1)) and 
                self.cal.is_holiday(day + timedelta(days=1))):
                return True
        
        return False

    def _apply_pre_attributions(self, pre_attributions: Dict, planning: Planning) -> bool:
        """
        Applique les pré-attributions sans vérification de contraintes.
        Les pré-attributions sont appliquées telles quelles, servant ensuite de base fixe
        pour la génération du reste du planning.
        """
        try:
            logger.info("\nAPPLICATION DES PRÉ-ATTRIBUTIONS")
            logger.info("=" * 80)
            
            # Récupérer les pré-attributions de manière sécurisée
            pre_attributions = self._get_pre_attributions()
            self.pre_attributions = pre_attributions  # Mettre à jour l'attribut avec la version sécurisée
            
            success = True
            
            # Obtenir la liste de tous les jours pour indexation rapide
            days_by_date = {day.date: day for day in planning.days}
            
            # Construire un index des slots existants pour une recherche rapide
            # Format: {(date, post_type, assignee): [slot1, slot2, ...]}
            existing_slots = {}
            for day in planning.days:
                for slot in day.slots:
                    if slot.assignee:
                        key = (day.date, slot.abbreviation, slot.assignee)
                        if key not in existing_slots:
                            existing_slots[key] = []
                        existing_slots[key].append(slot)
            
            # Trier les pré-attributions par date
            all_attributions = []
            for person_name, attributions in pre_attributions.items():
                person = next((p for p in self.doctors + self.cats if p.name == person_name), None)
                if not person:
                    logger.warning(f"Personne non trouvée pour les pré-attributions : {person_name}")
                    continue
                    
                for (date, period), post_type in attributions.items():
                    all_attributions.append((date, period, post_type, person))
            
            # Trier par date
            all_attributions.sort(key=lambda x: x[0])
            
            # Traiter chaque pré-attribution
            for date, period, post_type, person in all_attributions:
                # Récupérer le jour
                day = days_by_date.get(date)
                if not day:
                    logger.error(f"Jour non trouvé : {date}")
                    success = False
                    continue
                
                # Déterminer le type de jour pour les logs
                day_type = "weekday"
                if date.weekday() == 5 and not DayType.is_bridge_day(date, self.cal):
                    day_type = "saturday"
                elif date.weekday() == 6 or self.cal.is_holiday(date) or DayType.is_bridge_day(date, self.cal):
                    day_type = "sunday_holiday"
                    
                # Log du type de jour
                logger.debug(f"{date} : {day_type}")
                
                # Vérifier si le slot existe déjà (créé lors de l'initialisation)
                key = (date, post_type, person.name)
                slot_already_exists = key in existing_slots and existing_slots[key]
                
                if slot_already_exists:
                    # Le slot existe déjà, vérifier s'il a la bonne période
                    existing_slot = existing_slots[key][0]
                    existing_period = self._get_slot_period(existing_slot)
                    
                    # Pour les postes personnalisés à quota zéro, la période n'est pas vérifiée
                    is_custom_zero_quota = (post_type in self.custom_posts and 
                                        self._is_zero_quota_post(post_type, date, day_type))
                                        
                    if is_custom_zero_quota or existing_period == period:
                        logger.info(f"Pré-attribution déjà appliquée: {person.name} - {post_type} - {date}")
                    else:
                        logger.warning(f"Pré-attribution existante avec mauvaise période: {person.name} - {post_type} - {date}")
                        if not is_custom_zero_quota:
                            # Pour les postes normaux, on peut réattribuer avec la bonne période
                            existing_slot.assignee = None  # Libérer le slot existant
                            
                            # Chercher un slot avec la bonne période
                            matching_slots = [
                                slot for slot in day.slots
                                if slot.abbreviation == post_type and not slot.assignee
                                and self._get_slot_period(slot) == period
                            ]
                            
                            if matching_slots:
                                matching_slots[0].assignee = person.name
                                matching_slots[0].is_pre_attributed = True
                                logger.info(f"Pré-attribution corrigée: {person.name} - {post_type} - {date}")
                            else:
                                logger.error(f"Pas de slot disponible pour {post_type} le {date} avec période {period}")
                                success = False
                else:
                    # Vérifier si c'est un poste à quota zéro
                    is_zero_quota = self._is_zero_quota_post(post_type, date, day_type)
                    
                    # Création d'un nouveau slot si nécessaire
                    if is_zero_quota or post_type in self.custom_posts:
                        # Pour les postes personnalisés ou à quota zéro
                        if post_type in self.custom_posts:
                            # Utiliser les horaires du poste personnalisé
                            custom_post = self.custom_posts[post_type]
                            new_slot = TimeSlot(
                                start_time=datetime.combine(date, custom_post.start_time),
                                end_time=datetime.combine(
                                    date + timedelta(days=1 if custom_post.end_time < custom_post.start_time else 0),
                                    custom_post.end_time
                                ),
                                site="Personnalisé",
                                slot_type=custom_post.statistic_group.strip() if custom_post.statistic_group else "Personnalisé",
                                abbreviation=post_type,
                                assignee=person.name,
                                is_pre_attributed=True
                            )
                        else:
                            # Pour les postes standards à quota zéro, chercher les détails ou créer avec des horaires par défaut
                            post_details = self.post_manager.get_post_details(post_type, day_type)
                            if post_details:
                                new_slot = TimeSlot(
                                    start_time=datetime.combine(date, post_details['start_time']),
                                    end_time=datetime.combine(
                                        date + timedelta(days=1 if post_details['end_time'] < post_details['start_time'] else 0),
                                        post_details['end_time']
                                    ),
                                    site=post_details['site'],
                                    slot_type="Consultation" if "Visite" not in post_details['site'] else "Visite",
                                    abbreviation=post_type,
                                    assignee=person.name,
                                    is_pre_attributed=True
                                )
                            else:
                                # Créer un slot avec des horaires par défaut pour les postes sans détails
                                default_start = time(12, 0)  # Midi par défaut
                                default_end = time(17, 0)    # 17h par défaut
                                
                                # Utiliser des horaires spécifiques selon la première lettre du poste
                                if post_type.startswith('N'):  # Postes de nuit
                                    default_start = time(20, 0)
                                    default_end = time(8, 0)
                                elif post_type.startswith('C'):  # Postes de consultation
                                    default_start = time(9, 0)
                                    default_end = time(13, 0)
                                
                                new_slot = TimeSlot(
                                    start_time=datetime.combine(date, default_start),
                                    end_time=datetime.combine(
                                        date + timedelta(days=1 if default_end < default_start else 0),
                                        default_end
                                    ),
                                    site="Personnalisé (auto)",
                                    slot_type="Personnalisé",
                                    abbreviation=post_type,
                                    assignee=person.name,
                                    is_pre_attributed=True
                                )
                        
                        # Ajouter le slot au planning
                        day.slots.append(new_slot)
                        
                        # Mettre à jour l'index des slots existants
                        key = (date, post_type, person.name)
                        if key not in existing_slots:
                            existing_slots[key] = []
                        existing_slots[key].append(new_slot)
                        
                        logger.info(f"Pré-attribution appliquée (quota zéro): {person.name} - {post_type} - {date}")
                    else:
                        # Pour les postes standards ou non à quota zéro, chercher un slot disponible
                        matching_slots = [
                            slot for slot in day.slots
                            if slot.abbreviation == post_type and not slot.assignee
                            and self._get_slot_period(slot) == period
                        ]
                        
                        if not matching_slots:
                            logger.error(f"Pas de slot disponible pour {post_type} le {date}")
                            success = False
                            continue
                        
                        slot = matching_slots[0]
                        
                        # Appliquer la pré-attribution
                        slot.assignee = person.name
                        slot.is_pre_attributed = True
                        
                        # Mettre à jour l'index des slots existants
                        key = (date, post_type, person.name)
                        if key not in existing_slots:
                            existing_slots[key] = []
                        existing_slots[key].append(slot)
                        
                        logger.info(f"Pré-attribution appliquée : {person.name} - {post_type} - {date}")
                
                # Mettre à jour les compteurs de distribution
                self._update_distribution_counters(person, date, post_type)

            # Log du résultat final
            if success:
                self._log_pre_attribution_results()
            else:
                logger.warning("Certaines pré-attributions n'ont pas pu être appliquées")

            return success
                
        except Exception as e:
            logger.error(f"Erreur dans l'application des pré-attributions: {e}")
            return False


    def _is_zero_quota_post(self, post_type: str, date: date, day_type: str) -> bool:
        """
        Vérifie si un poste a un quota de zéro pour une date et un type de jour donnés.
        Gère également les postes personnalisés qui ont force_zero_count=True.
        
        Args:
            post_type: Type de poste
            date: Date à vérifier
            day_type: Type de jour (weekday, saturday, sunday_holiday)
            
        Returns:
            bool: True si le poste a un quota de zéro
        """
        # Vérifier d'abord si c'est un poste personnalisé avec force_zero_count
        if post_type in self.custom_posts and getattr(self.custom_posts[post_type], 'force_zero_count', False):
            return True
        
        # Obtenir la configuration pour ce jour
        config = self._get_config_from_analysis(date, day_type)
        
        # Vérifier si le poste est dans la configuration et a un quota de zéro
        if post_type in config:
            quota = self._get_config_value(config[post_type])
            return quota == 0
        
        # Pour les postes qui ne sont pas dans la configuration, on suppose qu'ils ont un quota de zéro
        return True


    def _log_pre_attribution_results(self):
        """Log détaillé des résultats des pré-attributions."""
        logger.info("\nRÉSULTAT DES PRÉ-ATTRIBUTIONS")
        logger.info("=" * 60)

        for person_name, counts in self.current_distribution['weekend'].items():
            if any(v > 0 for v in counts.values() if isinstance(v, (int, float))):
                logger.info(f"\n{person_name}:")
                
                # Log des NL
                if counts['NLv'] > 0:
                    logger.info(f"NLv: {counts['NLv']}")
                if counts['NLs'] > 0:
                    logger.info(f"NLs: {counts['NLs']}")
                if counts['NLd'] > 0:
                    logger.info(f"NLd: {counts['NLd']}")
                
                # Log des NA/NM
                for post_type in ['NA', 'NM']:
                    for suffix in ['s', 'd']:
                        key = f"{post_type}{suffix}"
                        if counts.get(key, 0) > 0:
                            logger.info(f"{key}: {counts[key]}")
                
                # Log des groupes
                for group, count in counts.get('weekend_groups', {}).items():
                    if count > 0:
                        logger.info(f"Groupe {group}: {count}")

    def _get_slot_period(self, slot) -> int:
        """
        Détermine la période d'un slot (1: matin, 2: après-midi, 3: soir)
        Prend en compte les spécificités de chaque type de poste.
        """
        # 1. Cas spéciaux
        if slot.abbreviation == "CT":
            return 2  # CT est toujours en après-midi
            
        # 2. Récupérer les détails du poste
        day_type = "sunday_holiday" if self.cal.is_holiday(slot.start_time.date()) else (
            "saturday" if slot.start_time.date().weekday() == 5 else "weekday"
        )
        post_details = self.post_manager.get_post_details(slot.abbreviation, day_type)
        
        if not post_details:
            logger.warning(f"Pas de détails trouvés pour le poste {slot.abbreviation}")
            return 0

        # 3. Déterminer la période en fonction de l'heure de début
        start_hour = post_details['start_time'].hour
        
        # Postes du matin (7h-13h)
        if any(slot.abbreviation.startswith(prefix) for prefix in ["ML", "MC", "MM", "CM", "HM", "SM", "RM"]):
            return 1
            
        # Postes de l'après-midi (13h-18h)
        elif any(slot.abbreviation.startswith(prefix) for prefix in ["AL", "AC", "CA", "HA", "SA", "RA"]):
            return 2
            
        # Postes du soir (après 18h)
        elif any(slot.abbreviation.startswith(prefix) for prefix in ["CS", "HS", "SS", "RS", "NA", "NM", "NL"]):
            return 3
            
        # Pour les autres postes, utiliser l'heure de début
        elif 7 <= start_hour < 13:
            return 1  # Matin
        elif 13 <= start_hour < 18:
            return 2  # Après-midi
        else:
            return 3  # Soir

    def _update_distribution_counters(self, person, date, post_type):
        """Met à jour les compteurs de distribution après une pré-attribution"""
        # Déterminer si weekend/semaine
        is_weekend = date.weekday() >= 5 or self.cal.is_holiday(date)
        
        if is_weekend:
            # Mise à jour des compteurs weekend
            counter = self.current_distribution["weekend"][person.name]
            group = self._get_post_group(post_type, date)
            if group:
                counter["weekend_groups"][group] = counter["weekend_groups"].get(group, 0) + 1
        else:
            # Mise à jour des compteurs semaine
            counter = self.current_distribution["weekday"][person.name]
            group = self._get_post_group(post_type, date)
            if group:
                counter["weekday_groups"][group] = counter["weekday_groups"].get(group, 0) + 1
    
  

    def reset_distribution_slots(self, planning, slot_types=None):
        """
        Réinitialise les slots de types spécifiques dans le planning pour permettre une redistribution.
        
        Args:
            planning: Le planning à mettre à jour
            slot_types: Liste des types de slots à réinitialiser ou None pour tous les types
        """
        if not planning or not hasattr(planning, 'days'):
            return False
        
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                # Ne pas réinitialiser les slots pré-attribués
                if getattr(slot, 'is_pre_attributed', False):
                    continue
                    
                # Réinitialiser les slots des types spécifiés
                if slot_types is None or slot.abbreviation in slot_types:
                    slot.assignee = None
                    
        return True

    def generate_planning(self, start_date: date, end_date: date) -> Optional[Planning]:
        """
        Génération initiale du planning weekend sans distribution automatique.
        Initialise le planning et applique les pré-attributions uniquement.
        """
        try:
            logger.info("=" * 80)
            logger.info(f"INITIALISATION DU PLANNING: {start_date} - {end_date}")
            logger.info("=" * 80)
            
            # Import ici pour éviter les imports circulaires si nécessaire
            from core.Constantes.models import Planning

            # Créer le planning
            planning = Planning(start_date, end_date)
            
            # 1. Initialiser les jours du planning
            self._initialize_planning_days(planning)
            
            # 2. Pré-analyse initiale pour obtenir les quotas et limites
            pre_analyzer = PlanningPreAnalyzer(self.doctors, self.cats, self.post_configuration)
            pre_analyzer.set_date_range(start_date, end_date)
            pre_analysis_results = pre_analyzer.analyze()
            planning.set_pre_analysis_results(pre_analysis_results)
            
            # 3. Récupérer les pré-attributions de manière sécurisée
            pre_attributions = self._get_pre_attributions()
            
            # 4. Appliquer les pré-attributions
            pre_attributions_success = self._apply_pre_attributions(pre_attributions, planning)
            if not pre_attributions_success:
                logger.warning("Certaines pré-attributions n'ont pas pu être appliquées")
            
            # 5. Mettre à jour la pré-analyse en tenant compte des pré-attributions
            pre_analysis_results = pre_analyzer.analyze()
            planning.set_pre_analysis_results(pre_analysis_results)
            
            return planning
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du planning: {e}")
            return None


    def generate_weekday_planning(self, planning: Planning) -> Optional[Planning]:
        """Génération du planning de semaine après validation des weekends."""
        try:
            if not planning:
                logger.error("Planning non initialisé")
                return None
                
            logger.info("\nGÉNÉRATION DU PLANNING DE SEMAINE")
            logger.info("=" * 80)

            # Sauvegarder les pré-attributions existantes par assignation directe 
            existing_pre_attributions = {}
            for day in planning.days:
                if day.is_weekend or day.is_holiday_or_bridge:
                    continue
                for slot in day.slots:
                    if slot.assignee:
                        period = self._get_slot_period(slot)
                        if (day.date, period) not in existing_pre_attributions:
                            existing_pre_attributions[(day.date, period)] = {}
                        existing_pre_attributions[(day.date, period)][slot.assignee] = slot.abbreviation

            # Log de vérification des pré-attributions existantes
            logger.info("\nPré-attributions extraites du planning:")
            for (date, period), assignments in existing_pre_attributions.items():
                for person_name, post_type in assignments.items():
                    logger.info(f"  - {person_name}: {post_type} le {date} (période {period})")

            # Créer le générateur de semaine avec les deux sources de pré-attributions
            final_pre_attributions = {}
            
            # 1. Ajouter les pré-attributions stockées
            if self.pre_attributions:
                for person_name, attributions in self.pre_attributions.items():
                    if person_name not in final_pre_attributions:
                        final_pre_attributions[person_name] = {}
                    final_pre_attributions[person_name].update(attributions)
            
            # 2. Ajouter les pré-attributions existantes dans le planning
            for (date, period), assignments in existing_pre_attributions.items():
                for person_name, post_type in assignments.items():
                    if person_name not in final_pre_attributions:
                        final_pre_attributions[person_name] = {}
                    final_pre_attributions[person_name][(date, period)] = post_type

            # Log des pré-attributions finales
            logger.info("\nPré-attributions totales transmises au générateur semaine:")
            if not final_pre_attributions:
                logger.warning("Aucune pré-attribution à transmettre")
            else:
                for person_name, attributions in final_pre_attributions.items():
                    logger.info(f"\n{person_name}:")
                    for (date, period), post_type in attributions.items():
                        logger.info(f"  - {post_type} le {date} (période {period})")

            # Créer le générateur avec les pré-attributions complètes
            weekday_generator = WeekdayGenerator(
                self.doctors,
                self.cats,
                planning,
                self.post_configuration,
                pre_attributions=final_pre_attributions
            )

            # Vérifier la réception des pré-attributions par le générateur
            if not weekday_generator.pre_attributions:
                logger.warning("Pré-attributions non reçues par le générateur semaine")
            else:
                logger.info("\nPré-attributions reçues par le générateur:")
                for person_name, attributions in weekday_generator.pre_attributions.items():
                    logger.info(f"\n{person_name}:")
                    for (date, period), post_type in attributions.items():
                        logger.info(f"  - {post_type} le {date} (période {period})")

            # Suite du processus
            weekday_generator.full_weekday_reset()
            
            if not weekday_generator.distribute_weekday_nl():
                logger.error("Échec distribution NL semaine")
                return planning
                
            if not weekday_generator.distribute_weekday_nanm():
                logger.error("Échec distribution NA/NM/NC semaine")
                return planning
                
            if not weekday_generator.distribute_weekday_combinations():
                logger.error("Échec distribution combinaisons semaine")
                return planning
                
            if not weekday_generator.distribute_remaining_weekday_posts():
                logger.error("Échec distribution postes restants semaine")
                return planning
                
            return planning
            
        except Exception as e:
            logger.error(f"Erreur dans la génération du planning de semaine: {e}")
            return planning

            
    def distribute_weekend(self, planning: Planning) -> bool:
        """
        Méthode conservée pour la compatibilité mais ne sera plus utilisée pour la distribution
        automatique complète. Utiliser plutôt les méthodes spécifiques à chaque phase.
        """
        # Si on utilise cette méthode, on vérifie si les validations ont déjà été effectuées
        if hasattr(planning, 'weekend_validated') and planning.weekend_validated:
            logger.info("Les weekends sont déjà validés")
            return True
        
        # Pour la compatibilité avec l'ancien code, on pourrait distribuer tout si nécessaire
        # Mais il est préférable d'utiliser les méthodes spécifiques à chaque phase
        logger.warning("Cette méthode est dépréciée. Utilisez plutôt les méthodes de distribution par phase.")
        return True

    def distribute_nlw_phase(self, planning: Planning) -> bool:
        """
        Distribution spécifique des NL weekend.
        Cette méthode peut être appelée directement depuis le thread PlanningPhaseGenerationThread.
        
        Args:
            planning: Le planning à mettre à jour
            
        Returns:
            bool: True si la distribution est réussie
        """
        try:
            logger.info("\nDISTRIBUTION DES NL WEEKEND - PHASE 1")
            logger.info("=" * 80)
            
            # Vérifier si la distribution a déjà été effectuée
            if hasattr(planning, 'nl_distributed') and planning.nl_distributed:
                logger.info("Les NL ont déjà été distribuées")
                return True
                
            # Exécuter la distribution des NL
            if self.distribute_nlw(planning, planning.pre_analysis_results):
                # Marquer la phase comme distribuée
                planning.nl_distributed = True
                return True
            else:
                logger.error("Échec de la distribution des NL weekend")
                return False
        
        except Exception as e:
            logger.error(f"Erreur dans la phase de distribution NL: {e}")
            return False

    def distribute_namw_phase(self, planning: Planning) -> bool:
        """
        Distribution spécifique des NA/NM weekend.
        Cette méthode peut être appelée directement depuis le thread PlanningPhaseGenerationThread.
        
        Args:
            planning: Le planning à mettre à jour
            
        Returns:
            bool: True si la distribution est réussie
        """
        try:
            logger.info("\nDISTRIBUTION DES NA/NM WEEKEND - PHASE 2")
            logger.info("=" * 80)
            
            # Vérifier si la phase précédente a été validée
            if not hasattr(planning, 'nl_validated') or not planning.nl_validated:
                logger.error("Les NL doivent être validés avant de distribuer les NA/NM")
                return False
                
            # Vérifier si la distribution a déjà été effectuée
            if hasattr(planning, 'nam_distributed') and planning.nam_distributed:
                logger.info("Les NA/NM ont déjà été distribuées")
                return True
                
            # Exécuter la distribution des NA/NM
            if self.distribute_namw(planning, planning.pre_analysis_results):
                # Marquer la phase comme distribuée
                planning.nam_distributed = True
                return True
            else:
                logger.error("Échec de la distribution des NA/NM weekend")
                return False
        
        except Exception as e:
            logger.error(f"Erreur dans la phase de distribution NA/NM: {e}")
            return False

    def distribute_combinations_phase(self, planning: Planning) -> bool:
        """
        Distribution spécifique des combinaisons et postes restants weekend.
        Cette méthode peut être appelée directement depuis le thread PlanningPhaseGenerationThread.
        
        Args:
            planning: Le planning à mettre à jour
            
        Returns:
            bool: True si la distribution est réussie
        """
        try:
            logger.info("\nDISTRIBUTION DES COMBINAISONS ET POSTES RESTANTS - PHASE 3")
            logger.info("=" * 80)
            
            # Vérifier si la phase précédente a été validée
            if not hasattr(planning, 'nam_validated') or not planning.nam_validated:
                logger.error("Les NA/NM doivent être validés avant de distribuer les combinaisons")
                return False
                
            # Vérifier si la distribution a déjà été effectuée
            if hasattr(planning, 'combinations_distributed') and planning.combinations_distributed:
                logger.info("Les combinaisons ont déjà été distribuées")
                return True
                
            # 1. Distribuer les combinaisons aux CAT
            logger.info("\nDISTRIBUTION DES COMBINAISONS AUX CAT")
            cat_success = self._distribute_cat_weekend_combinations(planning)
            if not cat_success:
                logger.warning("Distribution des combinaisons CAT incomplète")
                
            # 2. Distribuer les combinaisons aux médecins
            logger.info("\nDISTRIBUTION DES COMBINAISONS AUX MÉDECINS")
            med_success = self._distribute_doctor_weekend_combinations(planning)
            if not med_success:
                logger.warning("Distribution des combinaisons médecins incomplète")
                
            # 3. Distribuer les postes restants
            logger.info("\nDISTRIBUTION DES POSTES RESTANTS")
            remaining_success = self.distribute_remaining_weekend_posts(planning)
            if not remaining_success:
                logger.warning("Distribution des postes restants incomplète")
                
            # Même en cas de distribution partielle, on marque comme distribuée
            planning.combinations_distributed = True
            
            # Si toutes les distributions ont réussi
            return cat_success and med_success and remaining_success
        
        except Exception as e:
            logger.error(f"Erreur dans la phase de distribution des combinaisons: {e}")
            return False
   
    

    
    def distribute_nlw(self, planning: Planning, pre_analysis) -> bool:
        """Distribution des NL weekend en tenant compte des pré-attributions"""
        try:
            logger.info("\nDISTRIBUTION DES NL WEEKEND")
            logger.info("=" * 80)
            
            # 1. Calcul des quotas ajustés en tenant compte des pré-attributions
            cat_count = len(self.cats)
            
            # Quotas bruts pour les CAT depuis pre_analysis
            cat_nlv = pre_analysis["cat_posts"]["weekday"].get("NLv", 0) 
            cat_nls = pre_analysis["cat_posts"]["saturday"].get("NL", 0)
            cat_nld = pre_analysis["cat_posts"]["sunday_holiday"].get("NL", 0)
            
            cat_totals = {
                "NLv": cat_nlv * cat_count,
                "NLs": cat_nls * cat_count,
                "NLd": cat_nld * cat_count
            }
            
            # Quotas bruts pour les médecins
            med_nlv = pre_analysis["adjusted_posts"]["weekday_groups"]["NLv"]
            med_nlw = pre_analysis["adjusted_posts"]["weekend_groups"]["NLw"]
            med_nls = pre_analysis["adjusted_posts"]["saturday"]["NL"]
            med_nld = pre_analysis["adjusted_posts"]["sunday_holiday"]["NL"]
            
            # Soustraire les pré-attributions des quotas
            pre_attributions_count = {
                "NLv": 0, "NLs": 0, "NLd": 0,
                "cat_NLv": 0, "cat_NLs": 0, "cat_NLd": 0
            }
            
            # Compter les pré-attributions existantes
            for day in planning.days:
                for slot in day.slots:
                    if slot.abbreviation == "NL" and slot.assignee:
                        is_cat = any(cat.name == slot.assignee for cat in self.cats)
                        
                        if day.date.weekday() == 4:  # Vendredi
                            key = "cat_NLv" if is_cat else "NLv"
                        elif day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal):
                            key = "cat_NLs" if is_cat else "NLs"
                        else:  # Dimanche/Férié
                            key = "cat_NLd" if is_cat else "NLd"
                        
                        pre_attributions_count[key] += 1
            
            # Ajuster les quotas en soustrayant les pré-attributions
            med_totals = {
                "NLv": med_nlv - pre_attributions_count["NLv"],
                "NLs": med_nls - pre_attributions_count["NLs"],
                "NLd": med_nld - pre_attributions_count["NLd"]
            }
            
            cat_totals = {
                "NLv": cat_totals["NLv"] - pre_attributions_count["cat_NLv"],
                "NLs": cat_totals["NLs"] - pre_attributions_count["cat_NLs"],
                "NLd": cat_totals["NLd"] - pre_attributions_count["cat_NLd"]
            }
            
            # Log des quotas ajustés
            logger.info("\nQUOTAS AJUSTÉS APRÈS PRÉ-ATTRIBUTIONS:")
            logger.info("CAT:")
            for nl_type, count in cat_totals.items():
                logger.info(f"{nl_type}: {count} (pré-attribués: {pre_attributions_count['cat_' + nl_type]})")
            logger.info("\nMÉDECINS:")
            for nl_type, count in med_totals.items():
                logger.info(f"{nl_type}: {count} (pré-attribués: {pre_attributions_count[nl_type]})")
            
            # Création des slots une seule fois
            nl_slots = self._create_nl_distribution_map(planning)
            
            # Vérification de disponibilité
            for nl_type in ["NLv", "NLs", "NLd"]:
                total_needed = cat_totals[nl_type] + med_totals[nl_type]
                available = len(nl_slots[nl_type])
                
                logger.info(f"\nVérification {nl_type}:")
                logger.info(f"Requis : {total_needed} slots")
                logger.info(f"Disponible : {available} slots")
                
                if available < total_needed:
                    logger.error(f"Pas assez de slots {nl_type} disponibles.")
                    return False
            
            # Distribution aux CAT des slots restants
            if not self._distribute_nl_to_cats(planning, 
                                            cat_totals["NLv"],
                                            cat_totals["NLs"], 
                                            cat_totals["NLd"],
                                            nl_slots):
                return False
            
            # Distribution aux médecins des slots restants
            if not self._distribute_nl_to_doctors(planning,
                                                med_totals["NLv"],
                                                med_totals["NLs"],
                                                med_totals["NLd"],
                                                pre_analysis):
                logger.error("Échec de la distribution des NL aux médecins")
                return False
            
            # Vérification finale
            verification_data = {
                'cats': {
                    'total': sum(cat_totals.values()),
                    'NLv': cat_totals["NLv"],
                    'NLs': cat_totals["NLs"],
                    'NLd': cat_totals["NLd"]
                },
                'doctors': {
                    'total': med_nlw,
                    'NLv': med_totals["NLv"],
                    'NLs': med_totals["NLs"],
                    'NLd': med_totals["NLd"]
                }
            }
            
            self._verify_nl_distribution(planning, verification_data)
            return True
            
        except Exception as e:
            logger.error(f"Erreur dans la distribution NLw: {e}", exc_info=True)
            return False

    def _create_nl_distribution_map(self, planning):
        """
        Crée un dictionnaire organisé des slots NL déjà créés
        Assure que seuls les Vendredis, Samedis, et Dimanches/Fériés/Ponts soient inclus
        """
        nl_slots = {
            "NLv": [],  # UNIQUEMENT les vendredis non fériés/pont
            "NLs": [],  # UNIQUEMENT les samedis non fériés/pont
            "NLd": []   # Dimanches + tous les jours fériés/pont
        }

        for day in planning.days:
            # Ne traiter que les slots NL non assignés
            nl_slots_day = [slot for slot in day.slots if slot.abbreviation == "NL" and not slot.assignee]
            
            # Déterminer le type de jour précisément
            day_type = DayType.get_day_type(day.date, self.cal)
            is_bridge = DayType.is_bridge_day(day.date, self.cal)
            weekday = day.date.weekday()

            # Distribution stricte selon le type de jour
            if weekday == 4 and not (day_type == "sunday_holiday" or is_bridge):
                # Uniquement les vendredis normaux
                nl_slots["NLv"].extend((day, slot) for slot in nl_slots_day)
            
            elif weekday == 5 and not (day_type == "sunday_holiday" or is_bridge):
                # Uniquement les samedis normaux
                nl_slots["NLs"].extend((day, slot) for slot in nl_slots_day)
            
            elif weekday == 6 or day_type == "sunday_holiday" or is_bridge:
                # Dimanches + tous les jours fériés/pont
                nl_slots["NLd"].extend((day, slot) for slot in nl_slots_day)


        # Log de vérification
        logger.debug("\nVérification des slots NL collectés:")
        for nl_type, slots in nl_slots.items():
            logger.debug(f"{nl_type}: {len(slots)} slots")

        return nl_slots
    
    

    def _distribute_nl_to_cats(self, planning: Planning, nlv_total: int, nls_total: int, nld_total: int, nl_slots: Dict) -> bool:
        try:
            logger.info("Distribution NL aux CAT")
            cat_counts = {
                cat.name: {
                    "NLv": 0, "NLs": 0, "NLd": 0, "total": 0
                } for cat in self.cats
            }

            # Calculer les quotas par CAT
            cat_count = len(self.cats)
            quotas = {
                "NLv": nlv_total // cat_count,
                "NLs": nls_total // cat_count,
                "NLd": nld_total // cat_count
            }

            # Priorité à la distribution équitable
            for nl_type in ["NLv", "NLs", "NLd"]:
                quota = quotas[nl_type]
                available_slots = nl_slots[nl_type].copy()
                random.shuffle(available_slots)

                # Première passe : distribution égale garantie
                for cat in self.cats:
                    slots_needed = quota
                    slots_assigned = 0
                    
                    while slots_assigned < slots_needed and available_slots:
                        day, slot = available_slots[0]
                        if self.constraints.can_assign_to_assignee(cat, day.date, slot, planning):
                            slot.assignee = cat.name
                            cat_counts[cat.name][nl_type] += 1
                            cat_counts[cat.name]["total"] += 1
                            available_slots.pop(0)
                            slots_assigned += 1
                        else:
                            available_slots.pop(0)
                            continue

                    if slots_assigned < slots_needed:
                        logger.warning(f"Impossible d'atteindre le quota {nl_type} pour {cat.name} "
                                    f"({slots_assigned}/{slots_needed})")

            # Vérification des totaux
            total_assigned = sum(counts["total"] for counts in cat_counts.values())
            total_expected = sum(quotas.values()) * cat_count

            if total_assigned != total_expected:
                logger.warning(f"Distribution inégale des NL pour les CAT: "
                            f"Attendu {total_expected}, Obtenu {total_assigned}")

            return True

        except Exception as e:
            logger.error(f"Erreur distribution CAT: {e}", exc_info=True)
            return False

    def _distribute_nl_to_doctors(self, planning: Planning, nlv_total: int, nls_total: int, nld_total: int, pre_analysis: dict) -> bool:
        """
        Distribution optimisée des NL aux médecins avec priorité aux NLv.
        Assure que tous les médecins atteignent leur minimum de NLv en premier.
        
        Args:
            planning: Le planning en cours de génération
            nlv_total: Total des NLv à distribuer
            nls_total: Total des NLs à distribuer
            nld_total: Total des NLd à distribuer
            pre_analysis: Résultats de la pré-analyse
            
        Returns:
            bool: True si la distribution est réussie
        """
        try:
            logger.info("\nDISTRIBUTION DES NL AUX MÉDECINS")
            logger.info("=" * 60)

            # Récupérer les intervalles depuis la pré-analyse
            nlw_distribution = pre_analysis["ideal_distribution"]
            
            logger.info("\nINTERVALLES PAR MÉDECIN:")

            # Initialisation des compteurs EN INCLUANT les pré-attributions existantes
            doctor_nl_counts = {}
            for doctor in self.doctors:
                # Compter les NL déjà attribuées
                pre_attributed = {
                    "NLv": 0, "NLs": 0, "NLd": 0, "total": 0
                }
                
                for day in planning.days:
                    for slot in day.slots:
                        if slot.abbreviation == "NL" and slot.assignee == doctor.name:
                            if day.date.weekday() == 4:  # Vendredi
                                pre_attributed["NLv"] += 1
                            elif day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal):
                                pre_attributed["NLs"] += 1
                            else:  # Dimanche/Férié
                                pre_attributed["NLd"] += 1
                            pre_attributed["total"] += 1

                # Calculer les minimums spécifiques pour chaque type de NL
                nlw_min = nlw_distribution[doctor.name]["weekend_groups"]["NLw"]["min"]
                nlw_max = nlw_distribution[doctor.name]["weekend_groups"]["NLw"]["max"]
                
                # Déterminer les minimums par type
                # Le minimum de NLv est calculé en fonction du total NLw et des proportions NLv/NLs/NLd
                total_nl_slots = nlv_total + nls_total + nld_total
                if total_nl_slots > 0:
                    nlv_ratio = nlv_total / total_nl_slots
                    nlv_min = max(1, round(nlw_min * nlv_ratio))  # Au moins 1 NLv si le minimum total > 0
                else:
                    nlv_min = 0
                
                doctor_nl_counts[doctor.name] = {
                    "NLv": pre_attributed["NLv"],
                    "NLs": pre_attributed["NLs"], 
                    "NLd": pre_attributed["NLd"],
                    "total": pre_attributed["total"],
                    "max": nlw_max,
                    "min": nlw_min,
                    "nlv_min": nlv_min
                }

                logger.info(f"\nCompteurs initiaux pour {doctor.name}:")
                logger.info(f"NL pré-attribuées: {pre_attributed['total']} "
                        f"(NLv:{pre_attributed['NLv']}, "
                        f"NLs:{pre_attributed['NLs']}, "
                        f"NLd:{pre_attributed['NLd']})")
                logger.info(f"Minimum NLv requis: {nlv_min}")

            # Distribution des NL restantes
            available_slots = self._create_nl_distribution_map(planning)
            all_doctors = self.doctors.copy()

            # Phase 1: Priorité à la distribution du minimum de NLv pour tous les médecins
            logger.info("\nPHASE 1: Distribution du minimum de NLv")
            logger.info("=" * 50)

            # Trier les médecins par priorité: d'abord les pleins temps, puis aléatoirement
            sorted_doctors = sorted(all_doctors, key=lambda d: (-d.half_parts, random.random()))

            for doctor in sorted_doctors:
                min_nlv = doctor_nl_counts[doctor.name]["nlv_min"]
                current_nlv = doctor_nl_counts[doctor.name]["NLv"]
                
                if current_nlv >= min_nlv:
                    logger.info(f"{doctor.name}: Minimum NLv déjà atteint avec les pré-attributions "
                            f"({current_nlv}/{min_nlv})")
                    continue

                logger.info(f"\nDistribution NLv pour {doctor.name} "
                        f"(minimum NLv: {min_nlv}, actuel: {current_nlv})")

                # Distribution des NLv manquantes
                while (doctor_nl_counts[doctor.name]["NLv"] < min_nlv and 
                    doctor_nl_counts[doctor.name]["total"] < doctor_nl_counts[doctor.name]["max"]):
                    if not available_slots["NLv"]:
                        logger.warning(f"Plus de slots NLv disponibles pour {doctor.name}")
                        break

                    success = self._try_assign_nl_slot(
                        doctor,
                        available_slots["NLv"],
                        planning,
                        doctor_nl_counts[doctor.name],
                        "NLv"
                    )

                    if success:
                        logger.info(f"{doctor.name}: NLv attribué "
                                f"({doctor_nl_counts[doctor.name]['NLv']}/{min_nlv})")
                    else:
                        logger.warning(f"Impossible d'attribuer NLv à {doctor.name}")
                        break

            # Phase 2: Distribution du minimum global NLw restant
            logger.info("\nPHASE 2: Distribution du minimum global NLw restant")
            logger.info("=" * 50)

            for doctor in sorted_doctors:
                min_nlw = doctor_nl_counts[doctor.name]["min"]
                current_total = doctor_nl_counts[doctor.name]["total"]
                
                if current_total >= min_nlw:
                    logger.info(f"{doctor.name}: Minimum global déjà atteint "
                            f"({current_total}/{min_nlw})")
                    continue

                logger.info(f"\nDistribution pour {doctor.name} "
                        f"(minimum global: {min_nlw}, actuel: {current_total})")

                # Distribution du reste du minimum nécessaire avec priorité NLd puis NLs
                for nl_type in ["NLd", "NLs"]:
                    while (doctor_nl_counts[doctor.name]["total"] < min_nlw and 
                        doctor_nl_counts[doctor.name]["total"] < doctor_nl_counts[doctor.name]["max"]):
                        if not available_slots[nl_type]:
                            break

                        success = self._try_assign_nl_slot(
                            doctor,
                            available_slots[nl_type],
                            planning,
                            doctor_nl_counts[doctor.name],
                            nl_type
                        )

                        if success:
                            logger.info(f"{doctor.name}: {nl_type} attribué "
                                    f"({doctor_nl_counts[doctor.name]['total']}/{min_nlw})")
                        else:
                            break

                    if doctor_nl_counts[doctor.name]["total"] >= min_nlw:
                        break

                # Si toujours pas suffisant, essayer encore avec les NLv si disponibles
                if (doctor_nl_counts[doctor.name]["total"] < min_nlw and available_slots["NLv"]):
                    while (doctor_nl_counts[doctor.name]["total"] < min_nlw and 
                        doctor_nl_counts[doctor.name]["total"] < doctor_nl_counts[doctor.name]["max"]):
                        if not available_slots["NLv"]:
                            break

                        success = self._try_assign_nl_slot(
                            doctor,
                            available_slots["NLv"],
                            planning,
                            doctor_nl_counts[doctor.name],
                            "NLv"
                        )

                        if success:
                            logger.info(f"{doctor.name}: NLv supplémentaire attribué "
                                    f"({doctor_nl_counts[doctor.name]['total']}/{min_nlw})")
                        else:
                            break

            # Phase 3: Distribution du reste dans la limite des maximums
            logger.info("\nPHASE 3: Distribution complémentaire")
            while any(len(slots) > 0 for slots in available_slots.values()):
                random.shuffle(all_doctors)
                assigned = False

                for doctor in all_doctors:
                    current_count = doctor_nl_counts[doctor.name]["total"]
                    max_allowed = doctor_nl_counts[doctor.name]["max"]
                    
                    if current_count >= max_allowed:
                        continue

                    # Choisir le type de NL à distribuer en fonction de l'équilibre actuel
                    nl_type = self._distribute_nl_type_balanced(
                        doctor, 
                        available_slots,
                        doctor_nl_counts[doctor.name]
                    )
                    
                    if not nl_type:
                        continue

                    if current_count + 1 > max_allowed:
                        continue

                    success = self._try_assign_nl_slot(
                        doctor,
                        available_slots[nl_type],
                        planning,
                        doctor_nl_counts[doctor.name],
                        nl_type
                    )
                    
                    if success:
                        assigned = True
                        logger.info(f"{doctor.name}: {nl_type} attribué "
                                f"(total: {doctor_nl_counts[doctor.name]['total']}/{max_allowed})")
                        break

                if not assigned:
                    logger.info("Aucune attribution possible, fin de la distribution")
                    break

            # Log des résultats finaux
            logger.info("\nRÉSULTAT FINAL DE LA DISTRIBUTION")
            logger.info("=" * 40)
            for doctor in sorted(all_doctors, key=lambda x: x.name):
                counts = doctor_nl_counts[doctor.name]
                logger.info(f"\n{doctor.name} ({doctor.half_parts} demi-parts):")
                logger.info(f"NLv: {counts['NLv']} (minimum requis: {counts['nlv_min']})")
                logger.info(f"NLs: {counts['NLs']}")
                logger.info(f"NLd: {counts['NLd']}")
                logger.info(f"Total: {counts['total']} (min: {counts['min']}, max: {counts['max']})")

            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution NL: {e}", exc_info=True)
            return False

    def _try_assign_nl_slot(self, person, available_slots, planning, person_counts, nl_type, max_attempts=3):
        """Essaie d'assigner un slot NL avec un nombre limité de tentatives"""
        if not available_slots:
            return False

        slots_to_try = available_slots.copy()
        random.shuffle(slots_to_try)
        
        attempts = 0
        while slots_to_try and attempts < max_attempts:
            day, slot = slots_to_try.pop(0)  # Prendre et retirer le premier slot
            
            if self.constraints.can_assign_to_assignee(person, day.date, slot, planning):
                slot.assignee = person.name
                person_counts[nl_type] += 1
                person_counts["total"] += 1
                available_slots.remove((day, slot))
                logger.debug(f"Slot {nl_type} assigné à {person.name} le {day.date}")
                return True
                
            attempts += 1
        
        if attempts >= max_attempts:
            logger.debug(f"Limite de tentatives atteinte pour {person.name} sur {nl_type}")
        elif not slots_to_try:
            logger.debug(f"Plus de slots disponibles pour {person.name} sur {nl_type}")
        
        return False

    def _assign_nl_slots_to_person(self, person, quota, available_slots, planning, counts, nl_type):
        """Méthode commune pour assigner des slots à un médecin ou CAT"""
        remaining = quota
        assigned = 0
        
        while remaining > 0 and available_slots:
            success = self._try_assign_nl_slot(
                person,
                available_slots,
                planning,
                counts,
                nl_type
            )
            
            if success:
                assigned += 1
                remaining -= 1
            else:
                break
                
        if remaining > 0:
            logger.warning(f"  {person.name}: {assigned}/{quota} {nl_type} assignés")
        else:
            logger.info(f"  {person.name}: {assigned}/{quota} {nl_type} assignés")

        return assigned

    def _verify_nl_distribution(self, planning: Planning, expected_counts: Dict) -> bool:
        """
        Vérifie la distribution des NL et compare avec les totaux attendus
        """
        logger.info("\nVÉRIFICATION DE LA DISTRIBUTION NL")
        logger.info("=" * 80)
        
        actual_counts = {
            'cats': {'NLv': 0, 'NLs': 0, 'NLd': 0, 'total': 0},
            'doctors': {'NLv': 0, 'NLs': 0, 'NLd': 0, 'total': 0}
        }
        
        # Compter les NL distribués
        for day in planning.days:
            nl_slots = [slot for slot in day.slots if slot.abbreviation == "NL" and slot.assignee]
            
            # Ignorer les slots vides
            if not nl_slots:
                continue
                
            for slot in nl_slots:
                is_cat = any(cat.name == slot.assignee for cat in self.cats)
                person_type = 'cats' if is_cat else 'doctors'
                
                # Nouveau : Détection correcte du type de NL
                if day.date.weekday() == 4 and not day.is_holiday_or_bridge:  
                    # Vendredi normal
                    actual_counts[person_type]['NLv'] += 1
                elif day.date.weekday() == 5 and not day.is_holiday_or_bridge:  
                    # Samedi normal
                    actual_counts[person_type]['NLs'] += 1
                elif (day.date.weekday() == 6 or  # Dimanche
                    day.is_holiday_or_bridge or  # Jour férié ou pont
                    (day.date.weekday() == 5 and DayType.is_bridge_day(day.date, self.cal))):  # Samedi pont
                    actual_counts[person_type]['NLd'] += 1
                
                actual_counts[person_type]['total'] += 1

        
        # Comparer avec les totaux attendus
        all_match = True
        for person_type in ['cats', 'doctors']:
            logger.info(f"\n{person_type.upper()}:")
            for nl_type in ['NLv', 'NLs', 'NLd']:
                actual = actual_counts[person_type][nl_type]
                expected = expected_counts[person_type][nl_type]
                matches = actual == expected
                all_match &= matches
                
                logger.info(f"{nl_type}: {actual:3d} / {expected:3d} "
                        f"({'OK' if matches else 'ÉCART'})")
                
                # Log détaillé en cas d'écart
                if not matches:
                    logger.warning(f"Écart détecté pour {person_type} {nl_type}: "
                                f"Attendu {expected}, Obtenu {actual}")
            
            actual_total = actual_counts[person_type]['total']
            expected_total = expected_counts[person_type]['total']
            total_matches = actual_total == expected_total
            all_match &= total_matches
            
            logger.info(f"Total: {actual_total:3d} / {expected_total:3d} "
                    f"({'OK' if total_matches else 'ÉCART'})")
            
            if not total_matches:
                logger.warning(f"Écart total détecté pour {person_type}: "
                            f"Attendu {expected_total}, Obtenu {actual_total}")

        return all_match
    
    def _log_distribution_results(self, counts, quotas, person_type: str):
        """Log les résultats de distribution des NL"""
        logger.info(f"\nRÉSULTATS DISTRIBUTION {person_type}:")
        logger.info("=" * 40)
        
        for name, person_counts in sorted(counts.items()):
            logger.info(f"\n{name}:")
            total_assigned = 0
            total_quota = 0
            
            for nl_type in ["NLv", "NLs", "NLd"]:
                assigned = person_counts[nl_type]
                quota = quotas[nl_type]
                total_assigned += assigned
                total_quota += quota
                
                status = "OK" if assigned >= quota else f"MANQUE {quota - assigned}"
                logger.info(f"{nl_type}: {assigned}/{quota} ({status})")
            
            completion_rate = (total_assigned / total_quota * 100) if total_quota > 0 else 0
            logger.info(f"Total: {total_assigned}/{total_quota} ({completion_rate:.1f}%)")

    
    def _distribute_nl_type_balanced(self, doctor, available_slots, nl_counts):
        """
        Choisit le type de NL à distribuer pour assurer un équilibre.
        Intègre une priorité pour NLv si le médecin en a moins que sa cible idéale.
        
        Returns:
            str or None: Le type de NL à distribuer ou None si aucun n'est disponible
        """
        # Filtrer les types de NL disponibles
        available_types = [nl_type for nl_type, slots in available_slots.items() if slots]
        if not available_types:
            return None
            
        # Vérifier s'il y a encore des NLv à distribuer et si le médecin est sous sa cible
        if "NLv" in available_types and nl_counts.get("NLv", 0) < nl_counts.get("nlv_min", 0):
            return "NLv"
        
        # Calculer les ratios actuels pour les différents types
        total_nl = nl_counts.get("total", 0)
        if total_nl == 0:
            # Premier NL: priorité à NLv si disponible, sinon aléatoire
            return "NLv" if "NLv" in available_types else random.choice(available_types)
        
        # Calculer les proportions actuelles
        proportions = {
            nl_type: nl_counts.get(nl_type, 0) / total_nl
            for nl_type in ["NLv", "NLs", "NLd"]
        }
        
        # Calculer les proportions idéales
        ideal_proportions = {
            "NLv": 0.34,  # Légèrement augmenté pour favoriser NLv
            "NLs": 0.33,
            "NLd": 0.33
        }
        
        # Calculer les écarts et ajouter un facteur aléatoire
        random_factor = 0.2
        weighted_deviations = {
            nl_type: (ideal_proportions[nl_type] - proportions.get(nl_type, 0)) + (random.random() * random_factor)
            for nl_type in available_types
        }
        
        # Retourner le type avec la plus grande déviation positive + facteur aléatoire
        return max(available_types, key=lambda x: weighted_deviations[x])
    
    def _log_doctor_nl_distribution(self, doctor_name: str, counts: Dict):
        """Affiche la distribution actuelle des NL pour un médecin"""
        logger.info(f"\nDistribution pour {doctor_name}:")
        logger.info(f"NLv: {counts['NLv']}")
        logger.info(f"NLs: {counts['NLs']}")
        logger.info(f"NLd: {counts['NLd']}")
        logger.info(f"Total: {counts['total']}")
    
    
    
    
    
    def distribute_namw(self, planning: Planning, pre_analysis) -> bool:
        """Distribution des NA et NM du weekend suivant le même modèle que NLw"""
        try:
            logger.info("\nDISTRIBUTION NAM WEEKEND")
            logger.info("=" * 80)
            
            # 1. Récupération des totaux CAT avec le même format que NLw
            cat_count = len(self.cats)
            cat_nam = {
                "NAs": pre_analysis["cat_posts"]["saturday"].get("NA", 0),
                "NAd": pre_analysis["cat_posts"]["sunday_holiday"].get("NA", 0),
                "NMs": pre_analysis["cat_posts"]["saturday"].get("NM", 0),
                "NMd": pre_analysis["cat_posts"]["sunday_holiday"].get("NM", 0)
            }
            
            cat_totals = {k: v * cat_count for k, v in cat_nam.items()}
            cat_total = sum(cat_totals.values())
            
            # 2. Récupération des totaux médecins
            med_nam = {
                "NAs": pre_analysis["adjusted_posts"]["saturday"]["NA"],
                "NAd": pre_analysis["adjusted_posts"]["sunday_holiday"]["NA"],
                "NMs": pre_analysis["adjusted_posts"]["saturday"]["NM"],
                "NMd": pre_analysis["adjusted_posts"]["sunday_holiday"]["NM"]
            }
            med_total = sum(med_nam.values())
            med_namw = pre_analysis["adjusted_posts"]["weekend_groups"]["NAMw"]
            
            # Log des quotas comme pour NLw
            logger.info("\nTOTAUX CAT À DISTRIBUER:")
            for slot_type, count in cat_totals.items():
                logger.info(f"{slot_type}: {count} ({cat_nam[slot_type]}/CAT)")
            logger.info(f"Total: {cat_total}")
            
            logger.info("\nTOTAUX MÉDECINS À DISTRIBUER:")
            for slot_type, count in med_nam.items():
                logger.info(f"{slot_type}: {count}")
            logger.info(f"Total NAMw: {med_namw}")
            
            # 3. Vérification de cohérence comme pour NLw
            if med_namw != sum(med_nam.values()):
                logger.error("Incohérence dans les totaux médecins: "
                            f"NAMw ({med_namw}) ≠ Total NA+NM ({sum(med_nam.values())})")
                return False
            
            # Collecter les slots une seule fois
            nam_slots = self._collect_nam_slots(planning)

            # 5. Distribution aux CAT
            if not self._distribute_nam_to_cats(planning, cat_totals):  # Enlever nam_slots ici
                logger.error("Échec de la distribution des NAM aux CAT")
                return False
                
            # 7. Distribution médecins (3 phases)
            if not self._distribute_nam_to_doctors(planning, med_nam, pre_analysis):
                return False
                
           # Vérification finale
            verification_data = {
                'cats': cat_totals,
                'doctors': med_nam
            }
            
            completed = self._verify_nam_distribution(planning, verification_data)
            
            if not completed:
                logger.info("Des postes NAM restent non attribués - "
                        "ils seront traités dans la distribution finale")
                
            # Toujours retourner True pour continuer le processus
            return True
            
        except Exception as e:
            logger.error(f"Erreur dans la distribution NAMw: {e}", exc_info=True)
            return False

        
    
    def _distribute_nam_to_cats(self, planning: Planning, cat_totals: Dict) -> bool:
        try:
            logger.info("\nDISTRIBUTION DES NAM AUX CAT")
            logger.info("=" * 60)

            cat_counts = {
                cat.name: {
                    "NAs": 0, "NAd": 0, "NMs": 0, "NMd": 0
                } for cat in self.cats
            }

            # Récupérer les slots par type
            nam_slots = self._collect_nam_slots(planning)  # Déplacer la collecte ici

            # Pour chaque type de garde, respecter exactement les quotas
            for slot_type in ["NAs", "NAd", "NMs", "NMd"]:
                quota_per_cat = cat_totals[slot_type] // len(self.cats)
                available_slots = nam_slots[slot_type].copy()
                random.shuffle(available_slots)

                # Distribution stricte par CAT
                for cat in self.cats:
                    slots_assigned = 0
                    while slots_assigned < quota_per_cat and available_slots:
                        assigned = False
                        for slot_index in range(len(available_slots)):
                            day, slot = available_slots[slot_index]
                            if self.constraints.can_assign_to_assignee(cat, day.date, slot, planning):
                                slot.assignee = cat.name
                                cat_counts[cat.name][slot_type] += 1
                                available_slots.pop(slot_index)
                                slots_assigned += 1
                                assigned = True
                                break
                        if not assigned:
                            break
                    
                    if slots_assigned < quota_per_cat:
                        logger.warning(f"CAT {cat.name}: impossible d'atteindre le quota {slot_type} "
                                    f"({slots_assigned}/{quota_per_cat})")

            # Log des résultats
            self._log_nam_distribution_results(cat_counts, cat_totals, "CAT")
            return True

        except Exception as e:
            logger.error(f"Erreur distribution NAM CAT: {e}", exc_info=True)
            return False

    def _distribute_nam_to_doctors(self, planning: Planning, med_nam: Dict, pre_analysis: dict) -> bool:
        try:
            logger.info("\nDISTRIBUTION DES NAM AUX MÉDECINS")
            logger.info("=" * 60)

            # Récupération des intervalles depuis la pré-analyse
            doctor_intervals = {}
            for doctor in self.doctors:
                # Récupérer les intervalles personnalisés de chaque médecin
                doctor_distribution = pre_analysis["ideal_distribution"].get(doctor.name, {})
                weekend_groups = doctor_distribution.get("weekend_groups", {})
                
                # L'intervalle NAMw est dans les groupes weekend
                nam_interval = weekend_groups.get("NAMw", {"min": 0, "max": 0})
                
                doctor_intervals[doctor.name] = {
                    "min": nam_interval.get("min", 0),
                    "max": nam_interval.get("max", float('inf'))
                }
                
                logger.info(f"Intervalles pour {doctor.name}: "
                        f"[{doctor_intervals[doctor.name]['min']}-"
                        f"{doctor_intervals[doctor.name]['max']}]")

            # Initialisation des compteurs en incluant les pré-attributions
            doctor_counts = {}
            for doctor in self.doctors:
                # Compter les NAM déjà attribués
                pre_attributed = {
                    "NAs": 0, "NAd": 0, "NMs": 0, "NMd": 0, "NAMw": 0
                }
                
                for day in planning.days:
                    if not (day.is_weekend or day.is_holiday_or_bridge):
                        continue
                        
                    for slot in day.slots:
                        if slot.assignee == doctor.name and slot.abbreviation in ["NA", "NM"]:
                            is_saturday = day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal)
                            if slot.abbreviation == "NA":
                                if is_saturday:
                                    pre_attributed["NAs"] += 1
                                else:  # Dimanche/Férié
                                    pre_attributed["NAd"] += 1
                            else:  # NM
                                if is_saturday:
                                    pre_attributed["NMs"] += 1
                                else:  # Dimanche/Férié
                                    pre_attributed["NMd"] += 1
                            pre_attributed["NAMw"] += 1

                doctor_counts[doctor.name] = {
                    "NAs": pre_attributed["NAs"],
                    "NAd": pre_attributed["NAd"],
                    "NMs": pre_attributed["NMs"],
                    "NMd": pre_attributed["NMd"],
                    "NAMw": pre_attributed["NAMw"],
                    "min": doctor_intervals[doctor.name]["min"],
                    "max": doctor_intervals[doctor.name]["max"]
                }

                logger.info(f"\nCompteurs initiaux pour {doctor.name}:")
                logger.info(f"NAM pré-attribués: {pre_attributed['NAMw']} "
                        f"(NAs:{pre_attributed['NAs']}, NAd:{pre_attributed['NAd']}, "
                        f"NMs:{pre_attributed['NMs']}, NMd:{pre_attributed['NMd']})")

            # Récupération et mélange des slots disponibles
            all_slots = []
            nam_slots = self._collect_nam_slots(planning)
            for slot_type, slots in nam_slots.items():
                for slot_info in slots:
                    all_slots.append((slot_info[0], slot_info[1], slot_type))
            
            random.shuffle(all_slots)

            # Phase 1: Distribution du minimum en tenant compte des pré-attributions
            logger.info("\nPHASE 1: Distribution du minimum à tous les médecins")
            logger.info("=" * 50)

            for doctor in self.doctors:
                min_target = doctor_counts[doctor.name]["min"]
                current_total = doctor_counts[doctor.name]["NAMw"]
                
                if current_total >= min_target:
                    logger.info(f"{doctor.name}: Minimum déjà atteint avec les pré-attributions "
                            f"({current_total}/{min_target})")
                    continue

                logger.info(f"\nDistribution pour {doctor.name} "
                        f"(minimum: {min_target}, actuel: {current_total}, "
                        f"maximum: {doctor_counts[doctor.name]['max']})")

                while doctor_counts[doctor.name]["NAMw"] < min_target and all_slots:
                    assigned = False
                    for slot_index in range(len(all_slots)):
                        day, slot, slot_type = all_slots[slot_index]
                        if self.constraints.can_assign_to_assignee(doctor, day.date, slot, planning):
                            slot.assignee = doctor.name
                            doctor_counts[doctor.name][slot_type] += 1
                            doctor_counts[doctor.name]["NAMw"] += 1
                            all_slots.pop(slot_index)
                            assigned = True
                            logger.info(f"{doctor.name}: {slot_type} attribué (total: {doctor_counts[doctor.name]['NAMw']}/{min_target})")
                            break
                    if not assigned:
                        logger.warning(f"Impossible d'atteindre le minimum pour {doctor.name}")
                        break

            # Phase 2: Distribution du reste dans la limite des maximums
            logger.info("\nPHASE 2: Distribution du reste aux médecins")
            logger.info("=" * 50)

            while all_slots:
                random.shuffle(self.doctors)
                assigned = False

                for doctor in self.doctors:
                    current_count = doctor_counts[doctor.name]["NAMw"]
                    max_allowed = doctor_counts[doctor.name]["max"]

                    # Vérification stricte du maximum
                    if current_count >= max_allowed:
                        continue

                    # Tenter l'assignation
                    for slot_index in range(len(all_slots)):
                        day, slot, slot_type = all_slots[slot_index]
                        if self.constraints.can_assign_to_assignee(doctor, day.date, slot, planning):
                            slot.assignee = doctor.name
                            doctor_counts[doctor.name][slot_type] += 1
                            doctor_counts[doctor.name]["NAMw"] += 1
                            all_slots.pop(slot_index)
                            assigned = True
                            logger.info(f"{doctor.name}: {slot_type} attribué (total: {doctor_counts[doctor.name]['NAMw']}/{max_allowed})")
                            break

                    if assigned:
                        break

                if not assigned:
                    logger.info("Aucune assignation possible, fin de la distribution")
                    break

            # Log des résultats finaux
            logger.info("\nRÉSULTAT FINAL DE LA DISTRIBUTION")
            logger.info("=" * 40)
            for doctor in sorted(self.doctors, key=lambda x: x.name):
                counts = doctor_counts[doctor.name]
                logger.info(f"\n{doctor.name} ({doctor.half_parts} demi-parts):")
                logger.info(f"NAs: {counts['NAs']}")
                logger.info(f"NAd: {counts['NAd']}")
                logger.info(f"NMs: {counts['NMs']}")
                logger.info(f"NMd: {counts['NMd']}")
                logger.info(f"Total NAMw: {counts['NAMw']} [{counts['min']}-{counts['max']}]")

            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution NAM: {e}", exc_info=True)
            return False
        
    def _collect_nam_slots(self, planning: Planning) -> Dict:
        """Collecte tous les slots NA et NM disponibles"""
        nam_slots = {
            "NAs": [],  # NA samedi
            "NAd": [],  # NA dimanche/férié/pont
            "NMs": [],  # NM samedi
            "NMd": []   # NM dimanche/férié/pont
        }

        for day in planning.days:
            slots_available = [slot for slot in day.slots 
                            if slot.abbreviation in ["NA", "NM"] and not slot.assignee]
            
            day_type = DayType.get_day_type(day.date, self.cal)
            is_bridge = DayType.is_bridge_day(day.date, self.cal)

            for slot in slots_available:
                if day_type == "sunday_holiday" or is_bridge:
                    suffix = "d"  # dimanche/férié/pont
                elif day.date.weekday() == 5 and not is_bridge:
                    suffix = "s"  # samedi normal
                else:
                    continue  # Ignorer les autres jours

                slot_type = f"{slot.abbreviation}{suffix}"
                nam_slots[slot_type].append((day, slot))

        return nam_slots

    def _try_assign_nam_slot(self, person, available_slots, planning, person_counts, nam_type, max_attempts=3):
        """Version NAM de _try_assign_nl_slot"""
        if not available_slots:
            return False

        slots_to_try = available_slots.copy()
        random.shuffle(slots_to_try)
        
        attempts = 0
        while slots_to_try and attempts < max_attempts:
            day, slot = slots_to_try.pop(0)
            
            if self.constraints.can_assign_to_assignee(person, day.date, slot, planning):
                slot.assignee = person.name
                person_counts[nam_type] += 1
                person_counts["total" if "total" in person_counts else "NAMw"] += 1
                available_slots.remove((day, slot))
                logger.debug(f"Slot {nam_type} assigné à {person.name} le {day.date}")
                return True
                
            attempts += 1
        
        return False
    
    def _assign_nam_slots_to_person(self, person, quota, available_slots, planning, counts, slot_type):
        """Méthode commune pour assigner des slots NAM à un médecin ou CAT"""
        remaining = quota
        assigned = 0
        
        while remaining > 0 and available_slots:
            success = self._try_assign_nam_slot(
                person,
                available_slots,
                planning,
                counts,
                slot_type
            )
            
            if success:
                assigned += 1
                remaining -= 1
            else:
                break
                
            # Log des résultats
            if remaining > 0:
                logger.warning(f"  {person.name}: {assigned}/{quota} {slot_type} assignés")
            else:
                logger.info(f"  {person.name}: {assigned}/{quota} {slot_type} assignés")

        return assigned

    def _distribute_nam_type_randomly(self, doctor, available_slots, nam_counts):
        """Version NAM de _distribute_nl_type_randomly"""
        # Calcul des ratios pour NA et NM séparément
        total_na = nam_counts.get("NAs", 0) + nam_counts.get("NAd", 0)
        total_nm = nam_counts.get("NMs", 0) + nam_counts.get("NMd", 0)
        total = total_na + total_nm
        
        if total == 0:
            # Premier choix : complètement aléatoire
            available_types = [t for t, slots in available_slots.items() if slots]
            return random.choice(available_types) if available_types else None
        
        # Calculer les ratios idéaux (équilibre entre NA et NM)
        ideal_ratio = 0.5
        
        # Calculer les déviations actuelles
        na_ratio = total_na / total if total > 0 else 0
        nm_ratio = total_nm / total if total > 0 else 0
        
        # Ajouter un facteur aléatoire
        random_factor = 0.2
        weighted_deviations = {
            "NA": (ideal_ratio - na_ratio) + (random.random() * random_factor),
            "NM": (ideal_ratio - nm_ratio) + (random.random() * random_factor)
        }
        
        # Choisir entre NA et NM
        prefer_na = weighted_deviations["NA"] > weighted_deviations["NM"]
        
        # Filtrer les types disponibles
        available_types = []
        for t, slots in available_slots.items():
            if not slots:
                continue
            if prefer_na and t.startswith("NA"):
                available_types.append(t)
            elif not prefer_na and t.startswith("NM"):
                available_types.append(t)
        
        return random.choice(available_types) if available_types else None

    def _log_nam_distribution_results(self, counts, quotas, person_type: str, ranges: Dict = None):
        """Log unifié et concis des résultats de distribution NAM"""
        logger.info(f"\nRÉSULTATS DISTRIBUTION {person_type} NAM WEEKEND")
        logger.info("=" * 80)

        # En-têtes adaptés selon le type de personne (CAT ou Médecin)
        if person_type == "CAT":
            headers = ["Nom", "NA(s/d)", "NM(s/d)", "Total", "Quota", "Statut"]
        else:
            headers = ["Médecin", "NA(s/d)", "NM(s/d)", "Total", "Cible", "Statut"]

        # Affichage des en-têtes
        logger.info(f"{headers[0]:<15} {headers[1]:<12} {headers[2]:<12} {headers[3]:<8} {headers[4]:<10} {headers[5]}")
        logger.info("-" * 80)

        for name, person_counts in sorted(counts.items()):
            # Calcul des totaux NA et NM
            na_total = person_counts.get("NAs", 0) + person_counts.get("NAd", 0)
            nm_total = person_counts.get("NMs", 0) + person_counts.get("NMd", 0)
            total = na_total + nm_total

            # Format compact pour NA et NM
            na_str = f"{na_total}({person_counts.get('NAs',0)}/{person_counts.get('NAd',0)})"
            nm_str = f"{nm_total}({person_counts.get('NMs',0)}/{person_counts.get('NMd',0)})"

            # Détermination du statut selon le type
            if person_type == "CAT":
                quota_total = sum(quotas.values())
                status = "OK" if total >= quota_total else f"MANQUE {quota_total - total}"
                target = f"{quota_total}"
            else:
                range_info = ranges.get(name, {"min": 0, "max": 0})
                target = f"[{range_info['min']}-{range_info['max']}]"
                if total < range_info["min"]:
                    status = "SOUS MIN"
                elif total > range_info["max"]:
                    status = "SUR MAX"
                else:
                    status = "OK"

            # Affichage de la ligne
            logger.info(f"{name:<15} {na_str:<12} {nm_str:<12} {total:<8} {target:<10} {status}")

        # Affichage du résumé uniquement en cas d'écarts
        ecarts = sum(1 for _, counts in counts.items() if "MANQUE" in counts or "SOUS" in counts or "SUR" in counts)
        if ecarts > 0:
            logger.info("\nRésumé des écarts :")
            for name, person_counts in counts.items():
                if "MANQUE" in person_counts or "SOUS" in person_counts or "SUR" in person_counts:
                    logger.warning(f"{name}: {person_counts['status']}")

    def _verify_nam_distribution(self, planning: Planning, expected_counts: Dict) -> bool:
        """Vérification concise de la distribution NAM"""
        logger.info("\nVÉRIFICATION DISTRIBUTION NAM")
        logger.info("=" * 60)

        actual_counts = {
            'cats': {'NAs': 0, 'NAd': 0, 'NMs': 0, 'NMd': 0},
            'doctors': {'NAs': 0, 'NAd': 0, 'NMs': 0, 'NMd': 0}
        }

        # Compter les NAM distribués
        for day in planning.days:
            day_type = DayType.get_day_type(day.date, self.cal)
            is_bridge = DayType.is_bridge_day(day.date, self.cal)
            
            for slot in day.slots:
                if slot.abbreviation not in ["NA", "NM"] or not slot.assignee:
                    continue
                    
                is_cat = any(cat.name == slot.assignee for cat in self.cats)
                person_type = 'cats' if is_cat else 'doctors'
                
                if day_type == "sunday_holiday" or is_bridge:
                    suffix = "d"
                elif day.date.weekday() == 5 and not is_bridge:
                    suffix = "s"
                else:
                    continue
                    
                slot_type = f"{slot.abbreviation}{suffix}"
                actual_counts[person_type][slot_type] += 1

        # Affichage en format tableau
        headers = ["Type", "NAs", "NAd", "NMs", "NMd", "Total", "Attendu", "Statut"]
        logger.info(f"{headers[0]:<10} {headers[1]:>5} {headers[2]:>5} {headers[3]:>5} {headers[4]:>5} {headers[5]:>7} {headers[6]:>8} {headers[7]}")
        logger.info("-" * 65)

        all_match = True
        for person_type in ['cats', 'doctors']:
            actual = actual_counts[person_type]
            expected = expected_counts[person_type]
            
            actual_total = sum(actual.values())
            expected_total = sum(expected.values())
            
            status = "OK" if actual_total == expected_total else "ÉCART"
            all_match &= actual_total == expected_total
            
            logger.info(f"{person_type:<10} {actual['NAs']:>5} {actual['NAd']:>5} {actual['NMs']:>5} {actual['NMd']:>5} "
                    f"{actual_total:>7} {expected_total:>8} {status}")

            # Log des écarts si présents
            if actual_total != expected_total:
                for slot_type in ['NAs', 'NAd', 'NMs', 'NMd']:
                    if actual[slot_type] != expected[slot_type]:
                        logger.warning(f"  {slot_type}: Attendu={expected[slot_type]}, Obtenu={actual[slot_type]}")

        return all_match
    
    
 



    def _get_critical_weekend_periods(self, planning: Planning) -> List[date]:
        """Identifie les périodes critiques du weekend basées sur les disponibilités des médecins"""
        critical_dates = []
        weekend_dates = self._get_weekend_dates(planning)
        
        for current_date in weekend_dates:
            # Compter les médecins disponibles pour cette date
            available_doctors = 0
            for doctor in self.doctors:
                if not any(
                    desiderata.start_date <= current_date <= desiderata.end_date 
                    for desiderata in doctor.desiderata
                ):
                    available_doctors += 1
            
            # Calculer le pourcentage de médecins disponibles
            availability_percentage = (available_doctors / len(self.doctors)) * 100
            
            # Si moins de 50% des médecins sont disponibles, c'est une période critique
            if availability_percentage < 65:
                critical_dates.append({
                    'date': current_date,
                    'availability': availability_percentage
                })
        
        # Trier les dates par ordre croissant de disponibilité
        critical_dates.sort(key=lambda x: x['availability'])
        
        logger.info("\nPÉRIODES CRITIQUES IDENTIFIÉES:")
        for period in critical_dates:
            logger.info(f"Date: {period['date'].strftime('%Y-%m-%d')} - "
                    f"Disponibilité: {period['availability']:.1f}%")
        
        return critical_dates

    def _distribute_cat_weekend_combinations(self, planning: Planning) -> bool:
        """Distribution des combinaisons weekend pour les CAT en incluant les postes personnalisés"""
        try:
            logger.info("\nDISTRIBUTION DES COMBINAISONS WEEKEND AUX CAT")
            logger.info("=" * 60)

            # Identifier les périodes critiques
            critical_periods = self._get_critical_weekend_periods(planning)
            critical_dates = [period['date'] for period in critical_periods]

            # Organiser les dates
            weekend_dates = {
                "saturday": [],
                "sunday": []
            }
            
            # Séparer les dates normales des dates critiques
            normal_dates = []
            for date in self._get_weekend_dates(planning):
                if date not in critical_dates:
                    if date.weekday() == 5 and not DayType.is_bridge_day(date, self.cal):
                        weekend_dates["saturday"].append(date)
                    else:
                        weekend_dates["sunday"].append(date)
                else:
                    normal_dates.append(date)

            day_type_mapping = {
                "saturday": "saturday",
                "sunday": "sunday_holiday"
            }

            for cat in self.cats:
                logger.info(f"\nAnalyse des combinaisons pour {cat.name}:")
                
                # Récupérer toutes les combinaisons possibles (standards + personnalisées)
                combinations = self._get_cat_possible_combinations(cat, planning)
                logger.debug(f"Combinaisons disponibles pour {cat.name}: {combinations}")
                
                used_posts = {
                    "saturday": defaultdict(int),
                    "sunday": defaultdict(int)
                }
                assignments = {
                    "saturday": defaultdict(int),
                    "sunday": defaultdict(int)
                }

                # 1. Traiter d'abord les périodes critiques
                for critical_date in critical_dates:
                    day_type = "saturday" if critical_date.weekday() == 5 and not DayType.is_bridge_day(critical_date, self.cal) else "sunday"
                    
                    if not self._is_cat_available_for_date(cat, critical_date, planning):
                        continue

                    self._try_assign_cat_combination(
                        cat, critical_date, day_type, combinations,
                        used_posts, assignments, planning,
                        is_critical=True
                    )

                # 2. Traiter ensuite les autres dates
                for day_type, dates in weekend_dates.items():
                    dates_to_process = dates.copy()
                    random.shuffle(dates_to_process)

                    for date in dates_to_process:
                        if not self._is_cat_available_for_date(cat, date, planning):
                            continue

                        self._try_assign_cat_combination(
                            cat, date, day_type, combinations,
                            used_posts, assignments, planning,
                            is_critical=False
                        )

                # Log des résultats
                self._log_cat_weekend_distribution(cat, used_posts, assignments, combinations, planning)

            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution CAT weekend: {e}", exc_info=True)
            return False

    def _try_assign_cat_combination(self, cat: CAT, date: date, day_type: str,
                            combinations: Dict, used_posts: Dict, assignments: Dict,
                            planning: Planning, is_critical: bool) -> bool:
        """Tente d'attribuer une combinaison pour une date donnée"""
        pre_analysis_day_type = "saturday" if day_type == "saturday" else "sunday_holiday"
        quotas = planning.pre_analysis_results["cat_posts"][pre_analysis_day_type]

        available_combinations = []
        for combo, max_count in combinations[day_type]:
            # Vérifier si c'est une combinaison de poste personnalisé
            is_custom = combo in sum([list(p.possible_combinations.values()) 
                                    for p in self.custom_posts.values()], [])
            
            if is_custom:
                # Récupérer les postes de la combinaison à partir du nom du combo
                for custom_post in self.custom_posts.values():
                    if combo in custom_post.possible_combinations.values():
                        for post, combo_name in custom_post.possible_combinations.items():
                            if combo_name == combo:
                                first_post = custom_post.name
                                second_post = post
                                break
            else:
                first_post, second_post = combo[:2], combo[2:]

            if (used_posts[day_type][first_post] < quotas.get(first_post, 0) and
                used_posts[day_type][second_post] < quotas.get(second_post, 0) and
                assignments[day_type][combo] < max_count and
                self._can_assign_cat_combination(cat, combo, date, planning)):
                available_combinations.append(combo)

        if available_combinations:
            weighted_combinations = []
            for combo in available_combinations:
                weight = (max_count + 1 - assignments[day_type][combo])
                if is_critical:
                    weight *= 2
                weighted_combinations.extend([combo] * weight)

            if weighted_combinations:
                combo = random.choice(weighted_combinations)
                if self._assign_combination_to_cat(cat, combo, date, planning):
                    if combo in sum([list(p.possible_combinations.values()) 
                                for p in self.custom_posts.values()], []):
                        # Trouver les postes pour la combinaison personnalisée
                        for custom_post in self.custom_posts.values():
                            if combo in custom_post.possible_combinations.values():
                                for post, combo_name in custom_post.possible_combinations.items():
                                    if combo_name == combo:
                                        first_post = custom_post.name
                                        second_post = post
                                        break
                    else:
                        first_post, second_post = combo[:2], combo[2:]

                    used_posts[day_type][first_post] += 1
                    used_posts[day_type][second_post] += 1
                    assignments[day_type][combo] += 1
                    logger.info(f"{cat.name}: {combo} attribué pour {date} "
                            f"({day_type}) {'[CRITIQUE]' if is_critical else ''}")
                    return True

        return False

    def _get_weekend_dates(self, planning: Planning) -> List[date]:
        weekend_dates = []
        current_date = planning.start_date
        
        while current_date <= planning.end_date:
            if (current_date.weekday() >= 5 or
                self.cal.is_holiday(current_date) or
                DayType.is_bridge_day(current_date, self.cal)):
                weekend_dates.append(current_date)
            current_date += timedelta(days=1)
        
        return weekend_dates

    def _can_assign_cat_combination(self, cat: CAT, combo: str, date: date, planning: Planning) -> bool:
        """Vérifie si une combinaison peut être attribuée à un CAT pour une date donnée"""
        # Récupérer les slots pour la date
        day = planning.get_day(date)
        if not day:
            return False

        # Vérifier si c'est une combinaison de poste personnalisé
        is_custom_combo = any(combo in post.possible_combinations.values() 
                            for post in self.custom_posts.values())

        if is_custom_combo:
            # Trouver les postes impliqués dans la combinaison personnalisée
            first_post = None
            second_post = None
            for custom_post in self.custom_posts.values():
                for post, combo_name in custom_post.possible_combinations.items():
                    if combo_name == combo:
                        first_post = custom_post.name
                        second_post = post
                        break
                if first_post:
                    break
        else:
            # Combinaison standard
            first_post, second_post = combo[:2], combo[2:]

        if not (first_post and second_post):
            logger.error(f"Impossible de déterminer les postes pour la combinaison {combo}")
            return False

        # Vérifier la disponibilité des slots
        first_slot = next((s for s in day.slots if s.abbreviation == first_post and not s.assignee), None)
        second_slot = next((s for s in day.slots if s.abbreviation == second_post and not s.assignee), None)

        if not (first_slot and second_slot):
            logger.debug(f"Slots non disponibles pour {combo} le {date}")
            return False

        # Vérifier les contraintes pour chaque slot
        can_assign = (self.constraints.can_assign_to_assignee(cat, date, first_slot, planning) and
                    self.constraints.can_assign_to_assignee(cat, date, second_slot, planning))
        
        if can_assign:
            logger.debug(f"Combinaison {combo} possible pour {cat.name} le {date}")
        
        return can_assign

    def _assign_combination_to_cat(self, cat: CAT, combo: str, date: date, planning: Planning) -> bool:
        """Attribution d'une combinaison à un CAT"""
        try:
            day = planning.get_day(date)
            if not day:
                return False

            # Vérifier si c'est une combinaison personnalisée
            is_custom_combo = any(combo in post.possible_combinations.values() 
                                for post in self.custom_posts.values())

            if is_custom_combo:
                # Trouver les postes impliqués
                first_post = None
                second_post = None
                for custom_post in self.custom_posts.values():
                    for post, combo_name in custom_post.possible_combinations.items():
                        if combo_name == combo:
                            first_post = custom_post.name
                            second_post = post
                            break
                    if first_post:
                        break
            else:
                first_post, second_post = combo[:2], combo[2:]

            if not (first_post and second_post):
                logger.error(f"Impossible de déterminer les postes pour la combinaison {combo}")
                return False

            # Trouver les slots non assignés
            first_slot = next((s for s in day.slots if s.abbreviation == first_post and not s.assignee), None)
            second_slot = next((s for s in day.slots if s.abbreviation == second_post and not s.assignee), None)

            if not (first_slot and second_slot):
                logger.debug(f"Slots non disponibles pour {combo} le {date}")
                return False

            # Vérifier les contraintes
            if not (self.constraints.can_assign_to_assignee(cat, date, first_slot, planning) and
                    self.constraints.can_assign_to_assignee(cat, date, second_slot, planning)):
                return False

            # Assigner les slots
            first_slot.assignee = cat.name
            second_slot.assignee = cat.name

            logger.info(f"Attribution réussie: {combo} ({first_post}+{second_post}) à {cat.name} pour {date}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution de {combo} à {cat.name}: {e}")
            return False

    def _get_cat_possible_combinations(self, cat: CAT, planning: Planning) -> Dict[str, List[Tuple[str, int]]]:
        """Détermine les combinaisons possibles pour un CAT"""
        combinations = {"saturday": [], "sunday": []}
        
        # Récupérer les quotas pour chaque type de jour
        for day_type, pre_analysis_key in [("saturday", "saturday"), ("sunday", "sunday_holiday")]:
            quotas = planning.pre_analysis_results["cat_posts"][pre_analysis_key]
            
            # Debug des quotas disponibles
            logger.debug(f"Quotas {day_type} pour {cat.name}: {quotas}")

            # Ajouter les combinaisons standards
            for combo in WEEKEND_COMBINATIONS:
                first_post, second_post = combo[:2], combo[2:]
                if quotas.get(first_post, 0) > 0 and quotas.get(second_post, 0) > 0:
                    max_count = min(quotas[first_post], quotas[second_post])
                    if max_count > 0:
                        combinations[day_type].append((combo, max_count))

            # Ajouter les combinaisons des postes personnalisés
            for post_name, custom_post in self.custom_posts.items():
                if custom_post.assignment_type in ['cats', 'both']:
                    if day_type.replace('sunday', 'sunday_holiday') in custom_post.day_types:
                        quota_custom = quotas.get(post_name, 0)
                        if quota_custom > 0:
                            for other_post, combo_name in custom_post.possible_combinations.items():
                                quota_other = quotas.get(other_post, 0)
                                if quota_other > 0:
                                    max_count = min(quota_custom, quota_other)
                                    combinations[day_type].append((combo_name, max_count))
                                    logger.debug(f"Ajout combinaison {combo_name} pour {cat.name} "
                                            f"({post_name}+{other_post}) avec max={max_count}")

        # Log des combinaisons disponibles
        logger.debug(f"Combinaisons disponibles pour {cat.name}: {combinations}")
        
        return combinations

    def _is_cat_available_for_date(self, cat: CAT, date: date, planning: Planning) -> bool:
        """Vérifie si un CAT est disponible pour une date donnée"""
        # Vérifier les desiderata
        for desiderata in cat.desiderata:
            if desiderata.start_date <= date <= desiderata.end_date:
                return False
                
        # Vérifier si le CAT a déjà des postes ce jour
        day = planning.get_day(date)
        if day:
            return not any(slot.assignee == cat.name for slot in day.slots)
        
        return True

    def _verify_cat_combinations(self, cat_combinations: Dict):
        """Vérifie et log la distribution finale des combinaisons aux CAT"""
        logger.info("\nVÉRIFICATION FINALE DES COMBINAISONS CAT")
        logger.info("=" * 60)
        
        for cat_name, counts in cat_combinations.items():
            logger.info(f"\n{cat_name}:")
            for combo, count in counts.items():
                if combo != "total" and count > 0:
                    logger.info(f"{combo}: {count}")
            logger.info(f"Total combinaisons: {counts['total']}")
            
    def _log_cat_weekend_distribution(self, cat: CAT, used_posts: Dict, 
                                    assignments: Dict, combinations: Dict, planning: Planning):
        """Log détaillé de la distribution pour un CAT"""
        logger.info(f"\nRésultats de distribution pour {cat.name}:")
        
        for day_type in ["saturday", "sunday"]:
            logger.info(f"\n{day_type.upper()}:")
            logger.info("-" * 40)
            
            # Log des combinaisons utilisées
            logger.info("Combinaisons utilisées:")
            for combo, count in assignments[day_type].items():
                if count > 0:
                    max_count = next(m for c, m in combinations[day_type] if c == combo)
                    logger.info(f"{combo}: {count}/{max_count}")
            
            # Log des postes utilisés
            logger.info("\nPostes utilisés:")
            pre_analysis_day_type = "saturday" if day_type == "saturday" else "sunday_holiday"
            quotas = planning.pre_analysis_results["cat_posts"][pre_analysis_day_type]
            
            for post_type, used in used_posts[day_type].items():
                if used > 0:
                    is_custom = post_type in self.custom_posts
                    quota = quotas.get(post_type, 0)
                    logger.info(f"{post_type}: {used}/{quota}" + 
                            " (Personnalisé)" if is_custom else "")
    
    
    
    
    def _distribute_doctor_weekend_combinations(self, planning: Planning) -> bool:
        """
        Distribue les combinaisons de postes weekend aux médecins.
        Prend en compte les périodes critiques, les indisponibilités et les contraintes.
        """
        try:
            logger.info("\nDISTRIBUTION DES COMBINAISONS WEEKEND AUX MÉDECINS")
            logger.info("=" * 80)

            # Initialisation des structures de données
            doctor_counts = self._initialize_doctor_counts(planning)  # Modification ici
            critical_periods = self._get_critical_weekend_periods(planning)

            # Récupération et organisation des combinaisons disponibles
            available_combinations = self._get_available_doctor_combinations(planning)
            if not available_combinations:
                logger.error("Aucune combinaison disponible pour la distribution")
                return False

            # 1. Distribution pour les périodes critiques
            if critical_periods:
                logger.info("\nPHASE 1: DISTRIBUTION PÉRIODES CRITIQUES")
                logger.info("-" * 60)
                sorted_doctors = self._sort_doctors_by_unavailability(planning)
                
                for period in critical_periods:
                    date = period['date']
                    logger.info(f"\nTraitement période critique: {date} "
                            f"(disponibilité: {period['availability']:.1f}%)")
                    
                    if not self._distribute_critical_period(
                        date, sorted_doctors, doctor_counts,
                        available_combinations, planning
                    ):
                        logger.warning(f"Distribution incomplète pour {date}")

            # 2. Distribution générale équilibrée
            logger.info("\nPHASE 2: DISTRIBUTION GÉNÉRALE")
            logger.info("-" * 60)

            if not self._distribute_remaining_combinations(
                doctor_counts, available_combinations, planning
            ):
                logger.warning("Distribution générale incomplète")

            # Vérification et log des résultats
            self._verify_doctor_distribution(doctor_counts, planning)
            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution des combinaisons médecins: {e}", 
                        exc_info=True)
            return False

    def _initialize_doctor_counts(self, planning: Planning) -> Dict:
        """Initialise les compteurs pour chaque médecin."""
        doctor_counts = {}
        
        for doctor in self.doctors:
            doctor_counts[doctor.name] = {
                "posts": {post_type: 0 for post_type in ALL_POST_TYPES},
                "combinations": {combo: 0 for combo in WEEKEND_COMBINATIONS},
                "total_combinations": 0,
                "custom_posts": {name: 0 for name in self.custom_posts.keys()},
                "intervals": self._get_doctor_intervals(doctor, planning)
            }
            
        return doctor_counts

    def _get_doctor_intervals(self, doctor: Doctor, planning: Planning) -> Dict:
        """
        Récupère les intervalles min-max pour un médecin depuis la pré-analyse.
        """
        intervals = {}
        pre_analysis = planning.pre_analysis_results
        if not pre_analysis or 'ideal_distribution' not in pre_analysis:
            return intervals

        doctor_distribution = pre_analysis['ideal_distribution'].get(doctor.name, {})
        
        # Intervalles pour les postes standards
        for post_type in ALL_POST_TYPES:
            if post_type in doctor_distribution.get('weekend_posts', {}):
                intervals[post_type] = {
                    'min': doctor_distribution['weekend_posts'][post_type]['min'],
                    'max': doctor_distribution['weekend_posts'][post_type]['max']
                }
                
        # Intervalles pour les postes personnalisés
        for post_name in self.custom_posts.keys():
            if post_name in doctor_distribution.get('weekend_posts', {}):
                intervals[post_name] = {
                    'min': doctor_distribution['weekend_posts'][post_name]['min'],
                    'max': doctor_distribution['weekend_posts'][post_name]['max']
                }
                
        return intervals

    def _sort_doctors_by_unavailability(self, planning: Planning) -> List[Doctor]:
        """
        Trie les médecins par ordre décroissant d'indisponibilités weekend.
        Ajoute un facteur aléatoire pour éviter la monotonie.
        """
        doctor_unavailability = {}
        
        for doctor in self.doctors:
            weekend_unavailable = 0
            for desiderata in doctor.desiderata:
                # Compte les weekends dans la période de desiderata
                current_date = max(desiderata.start_date, planning.start_date)
                end_date = min(desiderata.end_date, planning.end_date)
                
                while current_date <= end_date:
                    if (current_date.weekday() >= 5 or 
                        self.cal.is_holiday(current_date) or
                        DayType.is_bridge_day(current_date, self.cal)):
                        weekend_unavailable += 1
                    current_date += timedelta(days=1)
                    
            # Ajout d'un facteur aléatoire (±10%)
            random_factor = 1 + (random.random() * 0.2 - 0.1)
            doctor_unavailability[doctor.name] = weekend_unavailable * random_factor

        # Tri par indisponibilité décroissante en utilisant le nom comme clé
        return sorted(self.doctors, 
                    key=lambda d: doctor_unavailability[d.name], 
                    reverse=True)

    def _distribute_critical_period(self, date: date, sorted_doctors: List[Doctor],
                                doctor_counts: Dict, available_combinations: Dict,
                                planning: Planning) -> bool:
        """
        Distribution prioritaire pour une période critique.
        """
        try:
            # Identifier le type de jour
            is_saturday = date.weekday() == 5 and not self.is_bridge_day(date)
            day_type = "saturday" if is_saturday else "sunday_holiday"
            
            # Filtrer les médecins disponibles pour cette date
            available_doctors = [
                doctor for doctor in sorted_doctors
                if self._is_doctor_available_for_date(doctor, date, planning)
            ]
            
            if not available_doctors:
                logger.warning(f"Aucun médecin disponible pour {date}")
                return False
                
            combinations_assigned = 0
            max_combinations = len(available_combinations[day_type])
            
            # Attribution des combinaisons
            for doctor in available_doctors:
                if combinations_assigned >= max_combinations:
                    break
                    
                # Tenter d'attribuer une combinaison appropriée
                combo = self._get_best_combination_for_doctor(
                    doctor, date, available_combinations[day_type],
                    doctor_counts[doctor.name], planning
                )
                
                if combo and self._try_assign_combination(
                    doctor, combo, date, doctor_counts[doctor.name], planning
                ):
                    combinations_assigned += 1
                    logger.info(f"{doctor.name}: {combo} attribué pour {date}")
                    
            return combinations_assigned > 0
            
        except Exception as e:
            logger.error(f"Erreur distribution période critique {date}: {e}")
            return False

    def _is_doctor_available_for_date(self, doctor: Doctor, date: date, 
                                planning: Planning) -> bool:
        """
        Vérifie la disponibilité d'un médecin pour une date donnée.
        """
        # Vérifier les desiderata
        for desiderata in doctor.desiderata:
            if desiderata.start_date <= date <= desiderata.end_date:
                return False
                
        # Vérifier les postes déjà attribués ce jour
        day = planning.get_day(date)
        if day:
            return not any(slot.assignee == doctor.name for slot in day.slots)
            
        return True

    def _get_best_combination_for_doctor(self, doctor: Doctor, date: date,
                                    available_combinations: List[str],
                                    doctor_state: Dict,
                                    planning: Planning) -> Optional[str]:
        """
        Sélectionne la meilleure combinaison pour un médecin.
        Prend en compte les limites max et l'équilibre des postes.
        """
        suitable_combinations = []
        
        for combo in available_combinations:
            # Vérifier si la combinaison est possible
            if self._can_assign_combination(doctor, combo, date, 
                                        doctor_state, planning):
                # Calcul du score de pertinence
                score = self._calculate_combination_score(
                    combo, doctor_state, doctor.half_parts
                )
                suitable_combinations.append((combo, score))
                
        if not suitable_combinations:
            return None
                
        # Sélection pondérée par le score
        total_score = sum(score for _, score in suitable_combinations)
        if total_score == 0:
            return None
                
        random_value = random.uniform(0, total_score)
        current_sum = 0
        
        for combo, score in suitable_combinations:
            current_sum += score
            if current_sum >= random_value:
                return combo
                    
        return suitable_combinations[-1][0] if suitable_combinations else None

    def _calculate_combination_score(self, combo: str, doctor_state: Dict,
                                half_parts: int) -> float:
        """
        Calcule un score de pertinence pour une combinaison.
        Prend en compte:
        - L'écart aux intervalles idéaux
        - Le nombre de demi-parts du médecin
        - L'historique des attributions
        """
        score = 10.0  # Score de base
        
        # Pénaliser si proche des maximums
        for post in self._get_posts_from_combo(combo):
            if post in doctor_state['intervals']:
                current = doctor_state['posts'].get(post, 0)
                max_val = doctor_state['intervals'][post]['max']
                if max_val > 0:
                    ratio = current / max_val
                    score *= (1 - ratio)  # Réduction progressive du score
        
        # Bonus pour les combinaisons moins utilisées
        combo_count = doctor_state['combinations'].get(combo, 0)
        score *= (1 + (3 - combo_count) * 0.2)  # +20% par combo manquant
        
        # Ajustement selon les demi-parts
        score *= 1.2 if half_parts == 2 else 0.8
        
        # Facteur aléatoire (±10%)
        score *= 1 + (random.random() * 0.2 - 0.1)
        
        return max(0.1, score)  # Score minimum pour garder une chance

    def _distribute_remaining_combinations(self, doctor_counts: Dict,
                                    available_combinations: Dict,
                                    planning: Planning) -> bool:
        """
        Distribution des combinaisons restantes de manière équilibrée.
        """
        try:
            remaining_dates = self._get_remaining_weekend_dates(planning)
            if not remaining_dates:
                return True
                
            # Organisation par type de jour
            dates_by_type = {
                "saturday": [],
                "sunday_holiday": []
            }
            
            for date in remaining_dates:
                if date.weekday() == 5 and not DayType.is_bridge_day(date, self.cal):
                    dates_by_type["saturday"].append(date)
                else:
                    dates_by_type["sunday_holiday"].append(date)
                    
            # Distribution pour chaque type de jour
            for day_type, dates in dates_by_type.items():
                if not dates:
                    continue
                    
                logger.info(f"\nDistribution {day_type}:")
                random.shuffle(dates)  # Ordre aléatoire
                
                for date in dates:
                    available_doctors = self._get_available_doctors_weighted(
                        date, doctor_counts, planning
                    )
                    
                    if not available_doctors:
                        logger.warning(f"Aucun médecin disponible pour {date}")
                        continue
                        
                    # Distribution pondérée
                    assignments_made = self._distribute_day_combinations(
                        date, available_doctors, doctor_counts,
                        available_combinations[day_type], planning
                    )
                    
                    if not assignments_made:
                        logger.warning(f"Impossible de distribuer pour {date}")
                        
            return True
            
        except Exception as e:
            logger.error(f"Erreur distribution générale: {e}")
            return False
        
    def _get_available_doctors_weighted(self, date: date, doctor_counts: Dict,
                                    planning: Planning) -> List[Tuple[Doctor, float]]:
        """
        Retourne les médecins disponibles avec leur pondération.
        """
        weighted_doctors = []
        
        for doctor in self.doctors:
            if not self._is_doctor_available_for_date(doctor, date, planning):
                continue
                
            # Calcul du poids basé sur plusieurs facteurs
            weight = self._calculate_doctor_weight(
                doctor, doctor_counts[doctor.name], date, planning
            )
            
            if weight > 0:
                weighted_doctors.append((doctor, weight))
                
        return sorted(weighted_doctors, key=lambda x: x[1], reverse=True)

    def _calculate_doctor_weight(self, doctor: Doctor, doctor_state: Dict, 
                            date: date, planning: Planning) -> float:
        """
        Calcule le poids d'un médecin pour la distribution.
        Prend en compte:
        - Le nombre de combinaisons reçues
        - Les demi-parts du médecin 
        - Le temps depuis la dernière attribution
        - L'atteinte des intervalles cibles
        """
        # 1. Calcul du poids basé sur les combinaisons reçues
        total_combos = doctor_state.get('total_combinations', 0)
        max_combos = max((state.get('total_combinations', 0) 
                for state in self._get_all_doctor_states(planning)), default=1)
        combo_weight = 1 - (total_combos / max_combos) if max_combos > 0 else 1.0

        # 2. Poids basé sur les demi-parts
        half_parts_weight = 1.2 if doctor.half_parts == 2 else 0.8

        # 3. Poids basé sur le temps depuis la dernière attribution
        last_weekend = self._get_last_weekend_date(doctor, planning)
        if last_weekend:
            days_since = (date - last_weekend).days
            time_weight = min(1.5, days_since / 14)  # Bonus max après 2 semaines
        else:
            time_weight = 1.5  # Bonus pour première attribution

        # 4. Poids basé sur les intervalles
        interval_weights = []
        for post_type, interval in doctor_state['intervals'].items():
            current = doctor_state['posts'].get(post_type, 0)
            if interval['max'] > 0:
                ratio = current / interval['max']
                interval_weights.append(1 - ratio)
        
        interval_weight = (sum(interval_weights) / len(interval_weights)) if interval_weights else 1.0
        
        # Combinaison des facteurs avec pondération
        base_weight = (combo_weight * 0.4 + 
                    half_parts_weight * 0.2 + 
                    time_weight * 0.2 + 
                    interval_weight * 0.2)
        
        random_factor = 1 + (random.random() * 0.2 - 0.1)  # ±10%
        return max(0.1, base_weight * random_factor)


    def _get_last_weekend_date(self, doctor: Doctor, planning: Planning) -> Optional[date]:
        """
        Trouve la date du dernier weekend où le médecin a été assigné.
        """
        last_date = None
        for day in reversed(planning.days):
            if not (day.date.weekday() >= 5 or 
                    self.cal.is_holiday(day.date) or
                    DayType.is_bridge_day(day.date, self.cal)):
                continue
                
            if any(slot.assignee == doctor.name for slot in day.slots):
                last_date = day.date
                break
                
        return last_date

    def _distribute_day_combinations(self, date: date, 
                                weighted_doctors: List[Tuple[Doctor, float]],
                                doctor_counts: Dict, 
                                available_combinations: List[str],
                                planning: Planning) -> bool:
        """
        Distribue les combinaisons pour un jour donné aux médecins en quatre passes :
        1. Première passe : priorité aux médecins sans combinaison
        2. Deuxième passe : compléter pour les médecins sous la moyenne
        3. Troisième passe : optimiser pour les médecins disponibles sous-utilisés
        4. Quatrième passe : maximiser l'utilisation de toutes les combinaisons restantes
        """
        try:
            assignments_made = False
            remaining_combinations = available_combinations.copy()
            if not remaining_combinations:
                return False

            # Calculer la moyenne actuelle des combinaisons
            total_combinations = sum(state['total_combinations'] 
                                for state in doctor_counts.values())
            nb_doctors = len(self.doctors)
            average_combinations = total_combinations / nb_doctors if nb_doctors > 0 else 0
            
            logger.debug(f"Moyenne actuelle: {average_combinations:.2f} combinaisons par médecin")

            # Première passe : médecins sans combinaison
            doctors_no_combo = sorted(
                [d for d, w in weighted_doctors if doctor_counts[d.name]['total_combinations'] == 0],
                key=lambda d: doctor_counts[d.name]['total_combinations']
            )
            
            if doctors_no_combo:
                logger.debug(f"Passe 1: {len(doctors_no_combo)} médecins sans combinaison")
                for doctor in doctors_no_combo:
                    if not remaining_combinations:
                        break
                        
                    combo = self._get_best_combination_for_doctor(
                        doctor, date, remaining_combinations,
                        doctor_counts[doctor.name], planning
                    )
                    
                    if combo and self._try_assign_combination(
                        doctor, combo, date, doctor_counts[doctor.name], planning
                    ):
                        remaining_combinations.remove(combo)
                        assignments_made = True
                        logger.info(f"Passe 1: {doctor.name}: {combo} attribué")

            # Deuxième passe : médecins sous la moyenne
            if remaining_combinations:
                doctors_under_avg = sorted(
                    [d for d, w in weighted_doctors 
                    if doctor_counts[d.name]['total_combinations'] < average_combinations],
                    key=lambda d: doctor_counts[d.name]['total_combinations']
                )
                
                if doctors_under_avg:
                    logger.debug(f"Passe 2: {len(doctors_under_avg)} médecins sous la moyenne")
                    for doctor in doctors_under_avg:
                        if not remaining_combinations:
                            break
                            
                        combo = self._get_best_combination_for_doctor(
                            doctor, date, remaining_combinations,
                            doctor_counts[doctor.name], planning
                        )
                        
                        if combo and self._try_assign_combination(
                            doctor, combo, date, doctor_counts[doctor.name], planning
                        ):
                            remaining_combinations.remove(combo)
                            assignments_made = True
                            logger.info(f"Passe 2: {doctor.name}: {combo} attribué")

            # Troisième passe : médecins disponibles sous-utilisés
            if remaining_combinations:
                available_doctors = [
                    d for d, w in weighted_doctors
                    if self._can_receive_more_combinations(d, doctor_counts[d.name])
                ]
                
                if available_doctors:
                    logger.debug(f"Passe 3: {len(available_doctors)} médecins disponibles")
                    available_doctors.sort(
                        key=lambda d: doctor_counts[d.name]['total_combinations']
                    )
                    
                    for doctor in available_doctors:
                        if not remaining_combinations:
                            break
                            
                        combo = self._get_best_combination_for_doctor(
                            doctor, date, remaining_combinations,
                            doctor_counts[doctor.name], planning
                        )
                        
                        if combo and self._try_assign_combination(
                            doctor, combo, date, doctor_counts[doctor.name], planning
                        ):
                            remaining_combinations.remove(combo)
                            assignments_made = True
                            logger.info(f"Passe 3: {doctor.name}: {combo} attribué")

            # Quatrième passe : maximiser l'utilisation des combinaisons restantes
            if remaining_combinations:
                # Récupérer tous les médecins qui peuvent recevoir des combinaisons
                all_available_doctors = [
                    doctor for doctor, _ in weighted_doctors
                    if self._is_doctor_available_for_date(doctor, date, planning) and
                    any(self._can_assign_combination(doctor, combo, date, 
                                                    doctor_counts[doctor.name], planning)
                        for combo in remaining_combinations)
                ]

                if all_available_doctors:
                    logger.debug(f"Passe 4: {len(all_available_doctors)} médecins disponibles "
                            f"pour {len(remaining_combinations)} combinaisons restantes")
                    
                    # Trier par nombre de combinaisons possibles
                    all_available_doctors.sort(
                        key=lambda d: sum(1 for combo in remaining_combinations 
                                        if self._can_assign_combination(
                                            d, combo, date, 
                                            doctor_counts[d.name], planning)
                                    ),
                        reverse=True
                    )

                    for doctor in all_available_doctors:
                        if not remaining_combinations:
                            break

                        # Essayer toutes les combinaisons possibles
                        possible_combinations = [
                            combo for combo in remaining_combinations
                            if self._can_assign_combination(
                                doctor, combo, date, 
                                doctor_counts[doctor.name], planning)
                        ]

                        if possible_combinations:
                            combo = self._get_best_combination_for_doctor(
                                doctor, date, possible_combinations,
                                doctor_counts[doctor.name], planning
                            )
                            if combo and self._try_assign_combination(
                                doctor, combo, date, doctor_counts[doctor.name], planning
                            ):
                                remaining_combinations.remove(combo)
                                assignments_made = True
                                logger.info(f"Passe 4: {doctor.name}: {combo} attribué")

            # Log du résultat final
            combinations_used = len(available_combinations) - len(remaining_combinations)
            if assignments_made:
                distribution_rate = (combinations_used / len(available_combinations)) * 100
                logger.info(f"Distribution finale pour {date}: "
                        f"{combinations_used}/{len(available_combinations)} "
                        f"combinaisons attribuées ({distribution_rate:.1f}%)")
                if remaining_combinations:
                    logger.info(f"Combinaisons non attribuées: {', '.join(remaining_combinations)}")
            else:
                logger.warning(f"Aucune attribution pour {date}")

            return assignments_made

        except Exception as e:
            logger.error(f"Erreur dans la distribution des combinaisons du jour {date}: {e}")
            return False

    def _can_receive_more_combinations(self, doctor: Doctor, doctor_state: Dict) -> bool:
        """
        Vérifie si un médecin peut encore recevoir des combinaisons
        en fonction de ses limites pour chaque type de poste.
        """
        for post_type, interval in doctor_state['intervals'].items():
            current = doctor_state['posts'].get(post_type, 0)
            if current < interval['max']:
                return True
        return False
    def _can_assign_combination(self, doctor: Doctor, combo: str, date: date,
                                doctor_state: Dict, planning: Planning) -> bool:
        """
        Version corrigée de la vérification des limites de groupe pour les combinaisons.
        Vérifie l'impact combiné des deux postes sur les limites de groupe.
        """
        # 1. Extraire les deux postes de la combinaison
        first_post, second_post = self._get_posts_from_combo(combo)
        
        # 2. Identifier les groupes impactés
        first_group = self._get_post_group(first_post, date)
        second_group = self._get_post_group(second_post, date)
        
        # 3. Vérifier les limites de groupe de manière combinée
        impacted_groups = {}
        
        if first_group:
            impacted_groups[first_group] = impacted_groups.get(first_group, 0) + 1
        if second_group:
            impacted_groups[second_group] = impacted_groups.get(second_group, 0) + 1
            
        # 4. Pour chaque groupe impacté, vérifier si l'ajout violerait la limite
        for group, impact in impacted_groups.items():
            current_count = self._count_group_posts(doctor, group, planning)
            group_max = (planning.pre_analysis_results.get('ideal_distribution', {})
                        .get(doctor.name, {})
                        .get('weekend_groups', {})
                        .get(group, {})
                        .get('max', float('inf')))
                        
            if current_count + impact > group_max:
                logger.debug(f"Attribution impossible: {doctor.name} - {combo} "
                            f"dépasserait la limite du groupe {group} "
                            f"({current_count + impact} > {group_max})")
                return False
        # 1. Vérification de base des desiderata
        if not self._is_doctor_available_for_date(doctor, date, planning):
            return False
            
        # 2. Détermination du type de jour
        is_saturday = date.weekday() == 5 and not self.is_bridge_day(date)
        day_type = "saturday" if is_saturday else "sunday_holiday"
        
        # 3. Extraction des postes de la combinaison
        first_post, second_post = self._get_posts_from_combo(combo)
        day = planning.get_day(date)
        if not day:
            return False

        # 4. Vérification des slots disponibles
        first_slot = next((s for s in day.slots if s.abbreviation == first_post and not s.assignee), None)
        second_slot = next((s for s in day.slots if s.abbreviation == second_post and not s.assignee), None)
        if not (first_slot and second_slot):
            return False

        # 5. Vérification des contraintes globales
        if not (self.constraints.can_assign_to_assignee(doctor, date, first_slot, planning) and
                self.constraints.can_assign_to_assignee(doctor, date, second_slot, planning)):
            return False

        # 6. Vérification des limites pour chaque poste
        for post in [first_post, second_post]:
            # 6.1 Vérification du groupe
            group = self._get_post_group(post, date)
            if group:
                current_group = self._count_group_posts(doctor, group, planning)
                group_max = (planning.pre_analysis_results.get('ideal_distribution', {})
                            .get(doctor.name, {})
                            .get('weekend_groups', {})
                            .get(group, {})
                            .get('max', float('inf')))
                
                # Vérification par type de jour pour le groupe
                group_this_type = sum(
                    1 for d in planning.days
                    if ((d.date.weekday() == 5 and not DayType.is_bridge_day(d.date, self.cal)) == is_saturday)
                    for s in d.slots
                    if s.assignee == doctor.name and self._get_post_group(s.abbreviation, d.date) == group
                )
                
                group_max_per_type = (group_max + 1) // 2  # Arrondissement supérieur
                if group_this_type >= group_max_per_type:
                    logger.debug(f"{doctor.name}: Limite de groupe {group} atteinte pour {day_type}")
                    return False

            # 6.2 Vérification du type de poste
            if post in doctor_state['intervals']:
                post_max = doctor_state['intervals'][post]['max']
                current_type = sum(
                    1 for d in planning.days
                    if ((d.date.weekday() == 5 and not DayType.is_bridge_day(d.date, self.cal)) == is_saturday)
                    for s in d.slots
                    if s.assignee == doctor.name and s.abbreviation == post
                )
                
                post_max_per_type = (post_max + 1) // 2  # Arrondissement supérieur
                if current_type >= post_max_per_type:
                    logger.debug(f"{doctor.name}: Limite de poste {post} atteinte pour {day_type}")
                    return False
                    
        return True

    

    def _try_assign_combination(self, doctor: Doctor, combo: str, date: date,
                                    doctor_state: Dict, planning: Planning) -> bool:
        """
        Version corrigée de l'attribution des combinaisons avec double vérification
        des limites de groupe avant l'attribution.
        """
        try:
            # 1. Vérifier une dernière fois les limites de groupe avant l'attribution
            if not self._can_assign_combination(doctor, combo, date, 
                                                    doctor_state, planning):
                return False
                
            # 2. Procéder à l'attribution comme avant
            day = planning.get_day(date)
            if not day:
                return False
                
            first_post, second_post = self._get_posts_from_combo(combo)
            
            # 3. Rechercher les slots et attribuer
            first_slot = next((s for s in day.slots 
                            if s.abbreviation == first_post and not s.assignee), None)
            second_slot = next((s for s in day.slots 
                            if s.abbreviation == second_post and not s.assignee), None)
                            
            if not (first_slot and second_slot):
                return False
                
            # 4. Double vérification finale des contraintes
            if not (self.constraints.can_assign_to_assignee(doctor, date, first_slot, planning) and
                    self.constraints.can_assign_to_assignee(doctor, date, second_slot, planning)):
                return False
                
            # 5. Attribution et mise à jour des compteurs
            first_slot.assignee = doctor.name
            second_slot.assignee = doctor.name
            
            doctor_state['posts'][first_post] = doctor_state['posts'].get(first_post, 0) + 1
            doctor_state['posts'][second_post] = doctor_state['posts'].get(second_post, 0) + 1
            doctor_state['combinations'][combo] = doctor_state['combinations'].get(combo, 0) + 1
            doctor_state['total_combinations'] += 1
            
            return True
                
        except Exception as e:
            logger.error(f"Erreur attribution {combo} à {doctor.name}: {e}")
            return False

    def _get_available_doctor_combinations(self, planning: Planning) -> Dict[str, List[str]]:
        """
        Récupère les combinaisons disponibles pour les médecins sur le weekend.
        Retourne un dictionnaire séparé pour samedi et dimanche/férié.
        """
        combinations = {
            "saturday": [],
            "sunday_holiday": []
        }
        
        pre_analysis = planning.pre_analysis_results
        if not pre_analysis or 'adjusted_posts' not in pre_analysis:
            return combinations
        
        # Récupération des quotas ajustés pour les médecins
        for day_type in ["saturday", "sunday_holiday"]:
            quotas = pre_analysis['adjusted_posts'][day_type]
            
            # Ajout des combinaisons standards
            for combo in WEEKEND_COMBINATIONS:
                first_post, second_post = combo[:2], combo[2:]
                if quotas.get(first_post, 0) > 0 and quotas.get(second_post, 0) > 0:
                    combinations[day_type].append(combo)
                    
            # Ajout des combinaisons personnalisées
            for post_name, custom_post in self.custom_posts.items():
                if custom_post.assignment_type in ['doctors', 'both']:
                    if day_type in custom_post.day_types:
                        quota_custom = quotas.get(post_name, 0)
                        if quota_custom > 0:
                            for other_post, combo_name in custom_post.possible_combinations.items():
                                if quotas.get(other_post, 0) > 0:
                                    combinations[day_type].append(combo_name)
        
        return combinations

    def _get_remaining_weekend_dates(self, planning: Planning) -> List[date]:
        """
        Récupère les dates weekend restantes où il y a encore des slots non assignés.
        """
        remaining_dates = []
        
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            # Vérifier s'il reste des slots non assignés
            unassigned_slots = [slot for slot in day.slots if not slot.assignee]
            if unassigned_slots:
                remaining_dates.append(day.date)
        
        return remaining_dates

    def _get_posts_from_combo(self, combo: str) -> Tuple[str, str]:
        """
        Extrait les deux postes d'une combinaison, en gérant les cas personnalisés.
        Retourne un tuple (premier_poste, second_poste).
        """
        # Vérifier si c'est une combinaison personnalisée
        for custom_post in self.custom_posts.values():
            if combo in custom_post.possible_combinations.values():
                for post, combo_name in custom_post.possible_combinations.items():
                    if combo_name == combo:
                        return custom_post.name, post
        
        # Combinaison standard
        return combo[:2], combo[2:]
    def _get_all_doctor_states(self, planning: Planning) -> List[Dict]:
        """
        Récupère l'état de distribution pour tous les médecins.
        Utilisé pour calculer les maximums globaux.
        """
        states = []
        for day in planning.days:
            for slot in day.slots:
                if slot.assignee:
                    doctor_state = next(
                        (state for state in states 
                        if state.get('doctor_name') == slot.assignee),
                        None
                    )
                    if not doctor_state:
                        doctor_state = {
                            'doctor_name': slot.assignee,
                            'total_combinations': 0
                        }
                        states.append(doctor_state)
                    # Compte uniquement les combinaisons weekend
                    if day.is_weekend or day.is_holiday_or_bridge:
                        doctor_state['total_combinations'] += 1
        return states


    def _verify_doctor_distribution(self, doctor_counts: Dict, planning: Planning) -> bool:
        """
        Vérifie et log la distribution finale des combinaisons aux médecins.
        """
        logger.info("\nVÉRIFICATION FINALE DE LA DISTRIBUTION")
        logger.info("=" * 60)
        
        all_ok = True
        for doctor in self.doctors:
            logger.info(f"\n{doctor.name} ({doctor.half_parts} demi-parts):")
            state = doctor_counts[doctor.name]
            
            # Vérification des postes
            logger.info("Postes attribués:")
            for post_type, count in sorted(state['posts'].items()):
                if count > 0:
                    if post_type in state['intervals']:
                        min_val = state['intervals'][post_type]['min']
                        max_val = state['intervals'][post_type]['max']
                        status = "OK"
                        if count < min_val:
                            status = "SOUS MIN"
                            all_ok = False
                        elif count > max_val:
                            status = "SUR MAX"
                            all_ok = False
                        logger.info(f"{post_type:4}: {count:2d} [{min_val}-{max_val}] {status}")
                    else:
                        logger.info(f"{post_type:4}: {count:2d}")
            
            # Vérification des combinaisons
            logger.info("\nCombinaisons utilisées:")
            for combo, count in sorted(state['combinations'].items()):
                if count > 0:
                    logger.info(f"{combo}: {count}")
            logger.info(f"Total combinaisons: {state['total_combinations']}")
            
        return all_ok
    
    
    
    
    
    
    def distribute_remaining_weekend_posts(self, planning: Planning) -> bool:
        """
        Distribution des postes restants du weekend après NL, NAM et combinaisons.
        Processus en 3 phases : analyse, CAT, médecins.
        """
        try:
            logger.info("\nDISTRIBUTION DES POSTES RESTANTS WEEKEND")
            logger.info("=" * 80)

            # 1. Collecte et analyse des postes restants
            posts_to_distribute = self._collect_remaining_weekend_posts(planning)
            if not posts_to_distribute["saturday"] and not posts_to_distribute["sunday_holiday"]:
                logger.info("Aucun poste restant à distribuer")
                return True

            # 2. Distribution aux CAT
            cat_quotas = self._calculate_cat_remaining_quotas(planning)
            if not self._distribute_remaining_to_cats(planning, posts_to_distribute, cat_quotas):
                logger.warning("Distribution incomplète aux CAT")
                return False

            # 3. Distribution aux médecins
            return self._distribute_remaining_to_doctors(planning, posts_to_distribute)
        
        

        except Exception as e:
            logger.error(f"Erreur distribution postes restants weekend: {e}", exc_info=True)
            return False

    def _collect_remaining_weekend_posts(self, planning: Planning) -> Dict:
        """Collecte tous les postes non attribués du weekend."""
        posts = {
            "saturday": defaultdict(list),
            "sunday_holiday": defaultdict(list)
        }

        for day in planning.days:
            if not day.is_weekend and not day.is_holiday_or_bridge:
                continue

            day_type = "saturday" if day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal) else "sunday_holiday"
            
            for slot in day.slots:
                if not slot.assignee and slot.abbreviation not in ["NL", "NM", "NA"]:
                    # Ajouter à la liste avec la date
                    posts[day_type][slot.abbreviation].append((day.date, slot))

        # Log des postes collectés
        for day_type, type_posts in posts.items():
            logger.info(f"\nPostes restants {day_type}:")
            for post_type, slots in type_posts.items():
                if slots:
                    logger.info(f"{post_type}: {len(slots)} slots")

        return posts

    def _calculate_cat_remaining_quotas(self, planning: Planning) -> Dict:
        """Calcule les quotas restants pour les CAT."""
        pre_analysis = planning.pre_analysis_results
        cat_quotas = {cat.name: {
            "saturday": defaultdict(int),
            "sunday_holiday": defaultdict(int)
        } for cat in self.cats}

        # Pour chaque CAT, calculer les quotas par type de jour
        for cat in self.cats:
            for day_type in ["saturday", "sunday_holiday"]:
                # Quotas attendus depuis la pré-analyse
                expected = pre_analysis["cat_posts"][day_type]
                
                # Compter les postes déjà attribués
                assigned = defaultdict(int)
                for day in planning.days:
                    if ((day_type == "saturday" and day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal)) or
                        (day_type == "sunday_holiday" and (day.date.weekday() == 6 or day.is_holiday_or_bridge))):
                        for slot in day.slots:
                            if slot.assignee == cat.name:
                                assigned[slot.abbreviation] += 1

                # Calculer les quotas restants
                for post_type, quota in expected.items():
                    remaining = quota - assigned[post_type]
                    if remaining > 0:
                        cat_quotas[cat.name][day_type][post_type] = remaining

        return cat_quotas

    def _distribute_remaining_to_cats(self, planning: Planning, 
                                    available_posts: Dict,
                                    cat_quotas: Dict) -> bool:
        """
        Distribution des postes restants aux CAT selon leurs quotas.
        Fait deux passes et continue même si certains quotas ne sont pas atteints.
        """
        try:
            logger.info("\nDISTRIBUTION CAT DES POSTES RESTANTS")
            logger.info("-" * 60)
            
            # Phase 1 : Distribution sur les périodes critiques
            logger.info("\nPHASE 1: Distribution sur périodes critiques")
            critical_periods = self._get_critical_weekend_periods(planning)
            for period in critical_periods:
                date = period['date']
                day_type = "saturday" if date.weekday() == 5 and not DayType.is_bridge_day(date, self.cal) else "sunday_holiday"
                
                # Distribution prioritaire aux CAT disponibles
                for cat in self.cats:
                    if not self._is_cat_available_for_date(cat, date, planning):
                        continue
                        
                    quota = cat_quotas[cat.name][day_type]
                    for post_type, count in quota.items():
                        available = [slot for d, slot in available_posts[day_type][post_type] if d == date]
                        for slot in available:
                            if count > 0 and self.constraints.can_assign_to_assignee(cat, date, slot, planning):
                                slot.assignee = cat.name
                                cat_quotas[cat.name][day_type][post_type] -= 1
                                count -= 1
                                logger.info(f"CAT {cat.name}: {post_type} attribué le {date} (période critique)")

            # Phase 2 : Distribution normale
            logger.info("\nPHASE 2: Distribution normale")
            for day_type in ["saturday", "sunday_holiday"]:
                for post_type in ALL_POST_TYPES:
                    if post_type not in available_posts[day_type]:
                        continue

                    # Pour chaque date disponible
                    available_slots = available_posts[day_type][post_type].copy()
                    random.shuffle(available_slots)  # Mélanger pour plus d'équité
                    
                    for date, slot in available_slots:
                        if slot.assignee:  # Déjà attribué
                            continue

                        # Trouver un CAT qui a encore besoin de ce type de poste
                        available_cats = [
                            cat for cat in self.cats
                            if (cat_quotas[cat.name][day_type][post_type] > 0 and
                                self._is_cat_available_for_date(cat, date, planning))
                        ]

                        if available_cats:
                            cat = random.choice(available_cats)  # Choix aléatoire
                            if self.constraints.can_assign_to_assignee(cat, date, slot, planning):
                                slot.assignee = cat.name
                                cat_quotas[cat.name][day_type][post_type] -= 1
                                logger.info(f"CAT {cat.name}: {post_type} attribué le {date}")

            # Phase 3 : Deuxième passe pour tenter de compléter les quotas
            logger.info("\nPHASE 3: Distribution complémentaire")
            random.shuffle(self.cats)  # Ordre aléatoire pour l'équité
            for cat in self.cats:
                for day_type in ["saturday", "sunday_holiday"]:
                    quotas_restants = cat_quotas[cat.name][day_type]
                    for post_type, quota in quotas_restants.items():
                        if quota <= 0:
                            continue

                        available = []
                        for date, slot in available_posts[day_type].get(post_type, []):
                            if not slot.assignee and self._is_cat_available_for_date(cat, date, planning):
                                available.append((date, slot))

                        random.shuffle(available)  # Mélanger les slots disponibles
                        for date, slot in available:
                            if self.constraints.can_assign_to_assignee(cat, date, slot, planning):
                                slot.assignee = cat.name
                                cat_quotas[cat.name][day_type][post_type] -= 1
                                logger.info(f"CAT {cat.name}: {post_type} attribué le {date} (phase complémentaire)")
                                if cat_quotas[cat.name][day_type][post_type] <= 0:
                                    break
            # Phase 4 : Distribution avec assouplissement des desideratas secondaires
            logger.info("\nPHASE 4: Distribution avec assouplissement des desideratas secondaires")
            
            # Récupérer les périodes critiques non couvertes
            critical_periods = self._get_critical_weekend_periods(planning)
            critical_periods.sort(key=lambda x: x['availability'])  # Trier par criticité croissante
            
            # Pour chaque CAT ayant encore des quotas non remplis
            for cat_name, quotas in cat_quotas.items():
                cat = next(c for c in self.cats if c.name == cat_name)
                
                # Parcourir d'abord les périodes critiques
                for period in critical_periods:
                    date = period['date']
                    day_type = "saturday" if date.weekday() == 5 and not DayType.is_bridge_day(date, self.cal) else "sunday_holiday"
                    
                    # Pour chaque type de poste avec quota non atteint
                    for post_type, remaining in quotas[day_type].items():
                        if remaining <= 0:
                            continue
                            
                        # Chercher un slot disponible pour ce post_type à cette date
                        available = [slot for d, slot in available_posts[day_type].get(post_type, []) 
                                   if d == date and not slot.assignee]
                        
                        for slot in available:
                            # Vérifier les contraintes en ignorant les desideratas secondaires
                            if self.constraints.can_assign_to_assignee(
                                cat, date, slot, planning, respect_secondary=False
                            ):
                                slot.assignee = cat.name
                                quotas[day_type][post_type] -= 1
                                logger.info(f"CAT {cat.name}: {post_type} attribué le {date} "
                                          f"(assouplissement, criticité: {period['availability']:.1f}%)")
                                break
                
                # Puis traiter les dates restantes
                for day_type in ["saturday", "sunday_holiday"]:
                    for post_type, remaining in quotas[day_type].items():
                        if remaining <= 0:
                            continue
                            
                        # Chercher parmi tous les slots disponibles restants
                        available = [(d, s) for d, s in available_posts[day_type].get(post_type, [])
                                   if not s.assignee]
                        random.shuffle(available)  # Mélanger pour l'équité
                        
                        for date, slot in available:
                            if self.constraints.can_assign_to_assignee(
                                cat, date, slot, planning, respect_secondary=False
                            ):
                                slot.assignee = cat.name
                                quotas[day_type][post_type] -= 1
                                logger.info(f"CAT {cat.name}: {post_type} attribué le {date} "
                                          f"(assouplissement)")
                                if quotas[day_type][post_type] <= 0:
                                    break
            # Log final des quotas non atteints
            incomplete = False
            for cat_name, quotas in cat_quotas.items():
                for day_type, type_quotas in quotas.items():
                    for post_type, remaining in type_quotas.items():
                        if remaining > 0:
                            logger.warning(f"CAT {cat_name}: {remaining} {post_type} non attribués ({day_type})")
                            incomplete = True

            if incomplete:
                logger.warning("Distribution incomplète aux CAT - Poursuite avec les médecins")
                
            # Toujours retourner True pour continuer avec les médecins
            return True

        except Exception as e:
            logger.error(f"Erreur distribution CAT: {e}", exc_info=True)
            # Continuer malgré l'erreur pour passer aux médecins
            return True

    def _distribute_remaining_to_doctors(self, planning: Planning, available_posts: Dict) -> bool:
        """
        Distribution optimisée des postes restants aux médecins avec respect strict des limites de groupe.
        """
        try:
            logger.info("\nDISTRIBUTION MÉDECINS DES POSTES RESTANTS")
            logger.info("=" * 60)

            # Récupération des intervalles et initialisation des compteurs
            intervals = planning.pre_analysis_results.get('ideal_distribution', {})
            doctor_states = self._initialize_doctor_states(planning)

            # PHASE 1: Distribution minimale obligatoire
            logger.info("\nPHASE 1: Distribution minimale obligatoire")
            self._distribute_minimum_requirements(planning, available_posts, intervals, doctor_states)

            # PHASE 2: Distribution équilibrée
            logger.info("\nPHASE 2: Distribution équilibrée")
            self._distribute_balanced_posts(planning, available_posts, intervals, doctor_states)

            # PHASE 3: Distribution finale
            remaining = self._count_unassigned_slots(planning)
            if remaining > 0:
                logger.info(f"\nPHASE 3: Distribution finale ({remaining} slots)")
                self._distribute_final_posts(planning, available_posts, intervals, doctor_states)

            # Vérification finale des limites de groupe
            status = self._verify_group_limits(planning, intervals)
            if not status:
                logger.error("Des dépassements de limites de groupe ont été détectés")
            return status

        except Exception as e:
            logger.error(f"Erreur distribution médecins: {e}", exc_info=True)
            return False

    def _initialize_doctor_states(self, planning: Planning) -> Dict:
        """Initialise l'état de distribution pour chaque médecin."""
        states = {}
        for doctor in self.doctors:
            states[doctor.name] = {
                'post_counts': self._get_doctor_weekend_counts(doctor, planning),
                'group_counts': {
                    group: self._count_group_posts(doctor, group, planning)
                    for group in ["CmS", "CmD", "CaSD", "CsSD", "VmS", "VmD", "VaSD", "NAMw", "NLw"]
                }
            }
        return states

    def _can_assign_post(self, doctor: Doctor, post_type: str, date: date, 
                        slot: TimeSlot, planning: Planning, intervals: Dict, 
                        doctor_state: Dict) -> bool:
        """
        Vérifie si un poste peut être attribué en respectant toutes les contraintes.
        Ajoute une double vérification pour les chevauchements.
        """
        # 1. Vérification explicite des postes déjà attribués ce jour
        day = planning.get_day(date)
        if day:
            day_posts = [s for s in day.slots if s.assignee == doctor.name]
            for existing_slot in day_posts:
                # Vérifier si même type de poste
                if existing_slot.abbreviation == post_type:
                    return False
                # Vérifier le chevauchement horaire
                if (slot.start_time < existing_slot.end_time and 
                    slot.end_time > existing_slot.start_time):
                    return False

        # 2. Vérifier la limite du groupe
        group = self._get_post_group(post_type, date)
        if group:
            group_max = intervals.get(doctor.name, {}).get('weekend_groups', {}).get(group, {}).get('max', float('inf'))
            current_group = doctor_state['group_counts'].get(group, 0)
            if current_group >= group_max:
                return False

        # 3. Vérifier la limite du type de poste
        post_max = intervals.get(doctor.name, {}).get('weekend_posts', {}).get(post_type, {}).get('max', float('inf'))
        current_post = sum(
            counts.get(post_type, 0)
            for counts in doctor_state['post_counts'].values()
        )
        if current_post >= post_max:
            return False

        # 4. Vérifier toutes les autres contraintes via le système de contraintes
        return self.constraints.can_assign_to_assignee(doctor, date, slot, planning)

    def _distribute_minimum_requirements(self, planning: Planning, available_posts: Dict,
                                    intervals: Dict, doctor_states: Dict) -> None:
        """
        Distribution des minimums requis en priorisant l'atteinte des minimums pour tous les médecins.
        Procède groupe par groupe jusqu'à ce que tous les médecins atteignent leur minimum
        ou que la progression ne soit plus possible.
        """
        logger.info("\nDISTRIBUTION DES MINIMUMS REQUIS")
        logger.info("=" * 60)

        # Récupérer tous les groupes à traiter
        all_groups = ["CmS", "CmD", "CaSD", "CsSD", "VmS", "VmD", "VaSD", "NAMw", "NLw"]
        
        # Phase 1: Distribution stricte des minimums par groupe
        progress_made = True
        while progress_made:
            progress_made = False
            
            # Pour chaque groupe
            for group in all_groups:
                logger.info(f"\nTraitement du groupe {group}")
                
                # Identifier les médecins sous le minimum pour ce groupe
                doctors_under_min = []
                for doctor in self.doctors:
                    doctor_state = doctor_states[doctor.name]
                    group_intervals = intervals.get(doctor.name, {}).get('weekend_groups', {}).get(group, {})
                    min_required = group_intervals.get('min', 0)
                    current = doctor_state.get('group_counts', {}).get(group, 0)
                    
                    if current < min_required:
                        gap = min_required - current
                        priority_score = (
                            gap * 10 +  # Priorité basée sur l'écart au minimum
                            doctor.half_parts * 5 +  # Bonus pour les pleins temps
                            (1 / (current + 1))  # Priorité aux plus bas
                        )
                        doctors_under_min.append((doctor, gap, priority_score))
                
                if not doctors_under_min:
                    continue
                    
                # Trier par priorité
                doctors_under_min.sort(key=lambda x: x[2], reverse=True)
                
                # Traiter d'abord les périodes critiques
                critical_periods = self._get_critical_weekend_periods(planning)
                critical_dates = {p['date']: p['availability'] for p in critical_periods}
                
                for doctor, needed, _ in doctors_under_min:
                    doctor_state = doctor_states[doctor.name]
                    logger.info(f"\n{doctor.name}: {needed} postes manquants pour {group}")
                    
                    # 1. Essayer d'abord les périodes critiques
                    for period in critical_periods:
                        date = period['date']
                        day_type = ("saturday" if date.weekday() == 5 and 
                                not DayType.is_bridge_day(date, self.cal) 
                                else "sunday_holiday")
                                
                        # Chercher les postes disponibles pour ce groupe à cette date
                        for post_type in self._get_group_members(group):
                            if post_type not in available_posts[day_type]:
                                continue
                                
                            slots = [(d, s) for d, s in available_posts[day_type][post_type]
                                    if d == date and not s.assignee]
                                    
                            for date, slot in slots:
                                if self._can_assign_post(doctor, post_type, date, slot,
                                                    planning, intervals, doctor_state):
                                    self._assign_post_and_update_state(
                                        doctor, post_type, date, slot, planning, doctor_state
                                    )
                                    available_posts[day_type][post_type].remove((date, slot))
                                    needed -= 1
                                    progress_made = True
                                    logger.info(f"Attribution critique: {post_type} le {date}")
                                    break
                                    
                            if needed <= 0:
                                break
                        if needed <= 0:
                            break
                    
                    # 2. Puis les autres dates si encore nécessaire
                    if needed > 0:
                        for day_type in ["saturday", "sunday_holiday"]:
                            if needed <= 0:
                                break
                                
                            for post_type in self._get_group_members(group):
                                if post_type not in available_posts[day_type]:
                                    continue
                                    
                                slots = [(d, s) for d, s in available_posts[day_type][post_type]
                                        if not s.assignee and d not in critical_dates]
                                        
                                for date, slot in slots:
                                    if self._can_assign_post(doctor, post_type, date, slot,
                                                        planning, intervals, doctor_state):
                                        self._assign_post_and_update_state(
                                            doctor, post_type, date, slot, planning, doctor_state
                                        )
                                        available_posts[day_type][post_type].remove((date, slot))
                                        needed -= 1
                                        progress_made = True
                                        logger.info(f"Attribution normale: {post_type} le {date}")
                                        break
                                        
                                if needed <= 0:
                                    break
        
        # Vérification finale et log des résultats
        logger.info("\nRÉSULTATS DE LA DISTRIBUTION MINIMALE")
        logger.info("=" * 60)
        
        all_minimums_met = True
        for doctor in sorted(self.doctors, key=lambda x: x.name):
            group_tracking = self._track_group_minimums(doctor, planning, intervals)
            logger.info(f"\n{doctor.name}:")
            
            for group, data in group_tracking.items():
                if data['needed'] > 0:
                    all_minimums_met = False
                    logger.warning(f"  {group}: {data['needed']} postes manquants "
                            f"(actuel: {data['current']}/{data['min']})")
                else:
                    logger.info(f"  {group}: OK ({data['current']}/{data['min']})")
                    
        if not all_minimums_met:
            logger.warning("\nCertains minimums n'ont pas été atteints - "
                        "La distribution continue avec les postes restants")

    def _track_group_minimums(self, doctor: Doctor, planning: Planning, intervals: Dict) -> Dict[str, Dict]:
        """
        Suit les minimums requis pour chaque groupe de postes pour un médecin.
        
        Args:
            doctor: Le médecin concerné
            planning: Le planning en cours
            intervals: Les intervalles de la pré-analyse
            
        Returns:
            Dict contenant pour chaque groupe:
                - current: nombre actuel de postes
                - min: minimum requis
                - needed: nombre encore nécessaire
        """
        # Groupes à suivre
        weekend_groups = ["CmS", "CmD", "CaSD", "CsSD", "VmS", "VmD", "VaSD", "NAMw", "NLw"]
        
        # Initialisation du suivi
        group_tracking = {}
        doctor_intervals = intervals.get(doctor.name, {}).get('weekend_groups', {})
        
        for group in weekend_groups:
            current_count = self._count_group_posts(doctor, group, planning)
            min_required = doctor_intervals.get(group, {}).get('min', 0)
            
            group_tracking[group] = {
                'current': current_count,
                'min': min_required,
                'needed': max(0, min_required - current_count)
            }
        
        return group_tracking

    def _update_distribution_priorities(self, doctor_states: Dict[str, Dict], 
                                    planning: Planning, intervals: Dict) -> Dict[str, List[str]]:
        """
        Détermine l'ordre de priorité des groupes pour la distribution en fonction des minimums manquants.
        
        Args:
            doctor_states: État actuel de la distribution par médecin
            planning: Le planning en cours
            intervals: Les intervalles de la pré-analyse
            
        Returns:
            Dict[str, List[str]]: Liste des groupes prioritaires par médecin
        """
        priorities = {}
        
        for doctor in self.doctors:
            # Suivre les minimums pour ce médecin
            group_tracking = self._track_group_minimums(doctor, planning, intervals)
            
            # Trier les groupes par nombre de postes manquants
            groups_needed = [(group, data['needed']) 
                            for group, data in group_tracking.items() 
                            if data['needed'] > 0]
                            
            # Trier par nombre de postes manquants décroissant
            sorted_groups = [group for group, needed in 
                            sorted(groups_needed, key=lambda x: x[1], reverse=True)]
                            
            priorities[doctor.name] = sorted_groups
            
            # Log des priorités
            if sorted_groups:
                logger.info(f"\nPriorités pour {doctor.name}:")
                for group in sorted_groups:
                    needed = group_tracking[group]['needed']
                    logger.info(f"  {group}: {needed} postes manquants")
                    
        return priorities

    def _prioritize_group_distribution(self, doctor: Doctor, 
                                    available_slots: Dict,
                                    doctor_state: Dict,
                                    planning: Planning,
                                    intervals: Dict) -> Optional[Tuple[str, date, TimeSlot]]:
        """
        Trouve le meilleur slot à attribuer en fonction des minimums de groupe.
        
        Returns:
            Tuple[str, date, TimeSlot] ou None: Le meilleur post à attribuer
        """
        # Obtenir les priorités actuelles
        group_tracking = self._track_group_minimums(doctor, planning, intervals)
        
        # Filtrer les groupes qui ont encore besoin de postes
        needed_groups = {group: data for group, data in group_tracking.items() 
                        if data['needed'] > 0}
        
        if not needed_groups:
            return None
            
        # Pour chaque groupe prioritaire
        for group, data in sorted(needed_groups.items(), 
                                key=lambda x: x[1]['needed'], 
                                reverse=True):
            # Récupérer les membres du groupe
            group_members = self._get_group_members(group)
            
            # Pour chaque type de jour
            for day_type in ["saturday", "sunday_holiday"]:
                for post_type in group_members:
                    if post_type not in available_slots[day_type]:
                        continue
                        
                    # Chercher un slot disponible pour ce post
                    for date, slot in available_slots[day_type][post_type]:
                        if (not slot.assignee and 
                            self._can_assign_post(doctor, post_type, date, slot, 
                                            planning, intervals, doctor_state)):
                            return post_type, date, slot
                            
        return None

    def _distribute_balanced_posts(self, planning: Planning, available_posts: Dict,
                                intervals: Dict, doctor_states: Dict) -> None:
        """
        Distribution équilibrée des postes restants après la phase minimale.
        Se concentre uniquement sur le respect des intervalles min/max avec une gestion
        améliorée des slots disponibles.
        """
        # Créer une copie de travail des posts disponibles pour éviter les problèmes de référence
        available_slots = {
            day_type: {
                post_type: [(date, slot) for date, slot in slots if not slot.assignee]
                for post_type, slots in day_posts.items()
            }
            for day_type, day_posts in available_posts.items()
        }

        # Pour chaque type de jour
        for day_type in ["saturday", "sunday_holiday"]:
            while any(slots for slots in available_slots[day_type].values()):
                doctors_copy = self.doctors.copy()
                random.shuffle(doctors_copy)
                assignment_made = False

                for doctor in doctors_copy:
                    doctor_state = doctor_states[doctor.name]

                    # Parcourir tous les types de postes disponibles
                    for post_type, slots in list(available_slots[day_type].items()):
                        if not slots:  # Ignorer les types de poste sans slots disponibles
                            continue

                        # Vérifier les limites du type de poste
                        post_max = intervals.get(doctor.name, {}).get('weekend_posts', {}).get(post_type, {}).get('max', float('inf'))
                        current_posts = sum(
                            counts.get(post_type, 0)
                            for counts in doctor_state['post_counts'].values()
                        )

                        if current_posts >= post_max:
                            continue

                        # Essayer chaque slot disponible
                        for idx, (date, slot) in enumerate(slots):
                            if self._can_assign_post(doctor, post_type, date, slot, planning, 
                                                intervals, doctor_state):
                                
                                # Vérification supplémentaire des postes du même jour
                                day = planning.get_day(date)
                                has_same_post_today = any(
                                    s.assignee == doctor.name and s.abbreviation == post_type
                                    for s in day.slots
                                )
                                if has_same_post_today:
                                    continue

                                # Attribution du slot
                                self._assign_post_and_update_state(doctor, post_type, date, slot, 
                                                                planning, doctor_state)
                                
                                # Retirer le slot des disponibles
                                slots.pop(idx)
                                
                                # Retirer aussi de available_posts pour cohérence
                                original_slots = available_posts[day_type][post_type]
                                if (date, slot) in original_slots:
                                    original_slots.remove((date, slot))
                                    
                                assignment_made = True
                                logger.debug(f"Attribution à {doctor.name}: {post_type} le {date}")
                                break

                        if assignment_made:
                            break

                # Si aucune attribution n'a été possible sur cette itération
                if not assignment_made:
                    # Compter et logger les slots non attribués
                    remaining = sum(len(slots) for slots in available_slots[day_type].values())
                    if remaining > 0:
                        logger.warning(f"{remaining} slots ({day_type}) n'ont pas pu être attribués")
                    break
    def _assign_post_and_update_state(self, doctor: Doctor, post_type: str,
                                    date: date, slot: TimeSlot, planning: Planning,
                                    doctor_state: Dict) -> None:
        """
        Attribue un poste et met à jour tous les compteurs d'état.
        """
        slot.assignee = doctor.name
        
        # Mettre à jour les compteurs de type de poste
        day_type = "saturday" if date.weekday() == 5 and not DayType.is_bridge_day(date, self.cal) else "sunday_holiday"
        doctor_state['post_counts'][day_type][post_type] = doctor_state['post_counts'][day_type].get(post_type, 0) + 1
        
        # Mettre à jour les compteurs de groupe
        group = self._get_post_group(post_type, date)
        if group:
            doctor_state['group_counts'][group] = doctor_state['group_counts'].get(group, 0) + 1
            
        logger.info(f"{doctor.name}: {post_type} attribué le {date} "
                    f"(groupe {group if group else 'N/A'})")

    def _verify_group_limits(self, planning: Planning, intervals: Dict) -> bool:
        """
        Vérifie que toutes les limites de groupe sont respectées.
        """
        all_ok = True
        for doctor in self.doctors:
            doctor_intervals = intervals.get(doctor.name, {}).get('weekend_groups', {})
            
            for group, max_allowed in doctor_intervals.items():
                current = self._count_group_posts(doctor, group, planning)
                if current > max_allowed.get('max', float('inf')):
                    logger.error(f"Dépassement pour {doctor.name}: "
                            f"groupe {group} = {current}/{max_allowed.get('max')}")
                    all_ok = False
                    
        return all_ok
    

    def _assign_needed_posts(self, doctor: Doctor, post_type: str, needed: int,
                            day_type: str, available_slots: List[Tuple[date, TimeSlot]],
                            planning: Planning) -> int:
        """
        Assigne un nombre déterminé de postes à un médecin en respectant toutes 
        les contraintes.

        Args:
            doctor (Doctor): Médecin à qui attribuer les postes
            post_type (str): Type de poste à attribuer (ex: ML, CM, etc.)
            needed (int): Nombre de postes à attribuer
            day_type (str): Type de jour (saturday/sunday_holiday)
            available_slots (List[Tuple[date, TimeSlot]]): Slots disponibles
            planning (Planning): Planning en cours

        Returns:
            int: Nombre de postes effectivement attribués
        """
        # Validations initiales
        if not doctor or not available_slots or needed <= 0:
            return 0

        # Initialisation
        assigned_count = 0
        doctor_intervals = planning.pre_analysis_results.get('ideal_distribution', {}).get(doctor.name, {})
        
        try:
            # Récupérer les compteurs actuels du médecin
            current_counts = self._get_doctor_weekend_counts(doctor, planning)
            
            # Pour chaque slot disponible
            for date, slot in available_slots:
                # Si on a atteint le nombre nécessaire
                if assigned_count >= needed:
                    break

                if slot.assignee:  # Déjà attribué
                    continue

                # Vérifications principales
                if not self._is_doctor_available_for_date(doctor, date, planning):
                    continue

                # Vérifier le maximum pour ce type de poste
                doctor_max = (doctor_intervals.get('weekend_posts', {})
                            .get(post_type, {})
                            .get('max', float('inf')))
                current_count = (current_counts.get(day_type, {})
                            .get(post_type, 0))
                if current_count >= doctor_max:
                    continue

                # Vérifier les limites de groupe
                group = self._get_post_group(post_type, date)
                if group:
                    group_intervals = doctor_intervals.get('weekend_groups', {}).get(group, {})
                    group_max = group_intervals.get('max', float('inf'))
                    group_count = self._count_group_posts(doctor, group, planning)
                    if group_count >= group_max:
                        continue

                # Vérifier les contraintes globales du planning
                if not self.constraints.can_assign_to_assignee(doctor, date, slot, planning):
                    continue

                # Attribution du slot
                slot.assignee = doctor.name
                assigned_count += 1

                # Log de l'attribution
                logger.info(f"{doctor.name} ({doctor.half_parts} demi-parts): "
                        f"{post_type} attribué le {date.strftime('%d/%m/%Y')} "
                        f"({assigned_count}/{needed})")

                # Mise à jour des compteurs
                current_counts[day_type][post_type] = current_count + 1

            # Log du résultat final
            if assigned_count < needed:
                logger.warning(
                    f"{doctor.name}: {assigned_count}/{needed} {post_type} attribués "
                    f"pour {day_type}")
            else:
                logger.info(
                    f"{doctor.name}: Attribution complète - {assigned_count} {post_type} "
                    f"pour {day_type}")

            return assigned_count

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution des postes pour {doctor.name}: {e}")
            return assigned_count  # Retourner le nombre attribué avant l'erreur

    def _check_group_limit(self, doctor: Doctor, post_type: str, date: date,
                        planning: Planning) -> bool:
        """Vérifie si l'attribution respecte les limites de groupe."""
        # Identifier le groupe du poste
        group = self._get_post_group(post_type, date)
        if not group:
            return True  # Pas de groupe = pas de limite
            
        # Récupérer l'intervalle du groupe
        intervals = planning.pre_analysis_results.get('ideal_distribution', {})
        group_intervals = intervals.get(doctor.name, {}).get('weekend_groups', {})
        if group not in group_intervals:
            return True
            
        # Compter les postes actuels du groupe
        current_count = self._count_group_posts(doctor, group, planning)
        max_count = group_intervals[group].get('max', float('inf'))
        
        return current_count < max_count

    def _get_doctor_weekend_counts(self, doctor: Doctor, planning: Planning) -> Dict:
        """Compte les postes weekend déjà attribués à un médecin."""
        counts = {
            "saturday": defaultdict(int),
            "sunday_holiday": defaultdict(int)
        }
        
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            day_type = "saturday" if day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal) else "sunday_holiday"
            
            for slot in day.slots:
                if slot.assignee == doctor.name:
                    counts[day_type][slot.abbreviation] += 1
                    
        return counts

    def _count_unassigned_slots(self, planning: Planning) -> int:
        """Compte les slots weekend non attribués."""
        count = 0
        for day in planning.days:
            if day.is_weekend or day.is_holiday_or_bridge:
                count += sum(1 for slot in day.slots if not slot.assignee)
        return count
    
    
    
    def _get_post_group(self, post_type: str, date: date) -> Optional[str]:
        """
        Détermine le groupe weekend du poste.
        
        Args:
            post_type: Type de poste (ML, CM, etc.)
            date: Date du poste
            
        Returns:
            str: Nom du groupe ou None si le poste n'appartient à aucun groupe
        """
        # Vérifier si c'est un poste personnalisé
        if post_type in self.custom_posts:
            return self.custom_posts[post_type].statistic_group

        # Déterminer le type de jour
        is_saturday = date.weekday() == 5 and not self.is_bridge_day(date)

        # Groupes de consultation matin
        if post_type in ["MM", "CM", "HM", "SM", "RM"]:
            return "CmS" if is_saturday else "CmD"

        # Groupes de consultation après-midi
        elif post_type in ["CA", "HA", "SA", "RA"]:
            return "CaSD"  # Même groupe pour samedi et dimanche

        # Groupes de consultation soir
        elif post_type in ["CS", "HS", "SS", "RS"]:
            return "CsSD"  # Même groupe pour samedi et dimanche

        # Groupes de visites matin
        elif post_type in ["ML", "MC"]:
            return "VmS" if is_saturday else "VmD"

        # Groupes de visites après-midi
        elif post_type in ["AL", "AC"]:
            return "VaSD"  # Même groupe pour samedi et dimanche

        # Groupes de nuit
        elif post_type in ["NM", "NA"]:
            return "NAMw"  # Groupe commun weekend

        # NL week-end
        elif post_type == "NL":
            if date.weekday() == 4:  # Vendredi
                return "NLw"  # NLv compte dans le groupe NLw
            elif is_saturday:
                return "NLw"  # NLs compte dans le groupe NLw
            else:
                return "NLw"  # NLd compte dans le groupe NLw

        return None

    def _count_group_posts(self, doctor: Doctor, group: str, planning: Planning) -> int:
        """
        Compte précisément le nombre de postes d'un groupe déjà attribués à un médecin.
        """
        count = 0
        
        # Mappings des postes par groupe
        group_mappings = {
            "CmS": ["MM", "CM", "HM", "SM", "RM"],  # Consultation matin samedi
            "CmD": ["MM", "CM", "HM", "SM", "RM"],  # Consultation matin dimanche
            "CaSD": ["CA", "HA", "SA", "RA"],  # Consultation après-midi samedi/dimanche
            "CsSD": ["CS", "HS", "SS", "RS"],  # Consultation soir samedi/dimanche
            "VmS": ["ML", "MC"],  # Visites matin samedi
            "VmD": ["ML", "MC"],  # Visites matin dimanche
            "VaSD": ["AL", "AC"],  # Visites après-midi samedi/dimanche
        }
        
        posts_to_count = group_mappings.get(group, [])
        
        # Ajouter les postes personnalisés du même groupe
        for post_name, custom_post in self.custom_posts.items():
            if custom_post.statistic_group == group:
                posts_to_count.append(post_name)
                
        # Comptage précis par type de jour
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue

            # Pour les groupes spécifiques au samedi
            is_saturday = day.date.weekday() == 5 and not DayType.is_bridge_day(day.date, self.cal)
            if group in ["CmS", "VmS"] and not is_saturday:
                continue

            # Pour les groupes spécifiques au dimanche
            if group in ["CmD", "VmD"] and is_saturday:
                continue

            count += sum(1 for slot in day.slots
                        if slot.assignee == doctor.name
                        and slot.abbreviation in posts_to_count)
                        
        return count

    def _get_group_members(self, group: str) -> List[str]:
        """
        Retourne la liste des types de poste appartenant à un groupe.
        
        Args:
            group: Nom du groupe
            
        Returns:
            List[str]: Liste des types de poste du groupe
        """
        # Définition des groupes standard
        standard_groups = {
            "CmS": ["MM", "CM", "HM", "SM", "RM"],  # Consultation matin samedi
            "CmD": ["MM", "CM", "HM", "SM", "RM"],  # Consultation matin dimanche
            "CaSD": ["CA", "HA", "SA", "RA"],  # Consultation après-midi samedi/dimanche
            "CsSD": ["CS", "HS", "SS", "RS"],  # Consultation soir samedi/dimanche
            "VmS": ["ML", "MC"],  # Visites matin samedi
            "VmD": ["ML", "MC"],  # Visites matin dimanche
            "VaSD": ["AL", "AC"],  # Visites après-midi samedi/dimanche
            "NAMw": ["NM", "NA"],  # Nuits courtes/moyennes weekend
            "NLw": ["NL"]  # Nuits longues weekend
        }
        
        members = standard_groups.get(group, []).copy()
        
        # Ajouter les postes personnalisés du groupe
        for post_name, custom_post in self.custom_posts.items():
            if custom_post.statistic_group == group:
                members.append(post_name)
                
        return members

    def _get_group_stats(self, group: str, planning: Planning) -> Dict:
        """
        Calcule les statistiques d'utilisation d'un groupe.
        
        Args:
            group: Nom du groupe
            planning: Le planning en cours
            
        Returns:
            Dict: Statistiques du groupe (total, par médecin, etc.)
        """
        stats = {
            "total": 0,
            "by_doctor": defaultdict(int),
            "by_type": defaultdict(int)
        }
        
        members = self._get_group_members(group)
        
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                if not (group == "NLw" and day.date.weekday() == 4):  # NLv compte pour NLw
                    continue

            for slot in day.slots:
                if slot.abbreviation in members and slot.assignee:
                    stats["total"] += 1
                    stats["by_doctor"][slot.assignee] += 1
                    stats["by_type"][slot.abbreviation] += 1
                    
        return stats
    
    def _get_remaining_slots(self, available_posts: Dict) -> Dict:
        """
        Récupère les slots encore disponibles, filtrés et organisés.
        
        Args:
            available_posts: Structure de données contenant tous les posts disponibles
                Format: {
                    "saturday": {post_type: [(date, slot), ...], ...},
                    "sunday_holiday": {post_type: [(date, slot), ...], ...}
                }
        
        Returns:
            Dict: Slots restants filtrés et organisés
                Format similaire à available_posts mais uniquement avec les slots non assignés
        """
        remaining = {
            "saturday": defaultdict(list),
            "sunday_holiday": defaultdict(list)
        }
        
        # Pour chaque type de jour
        for day_type, day_posts in available_posts.items():
            # Pour chaque type de poste
            for post_type, slots in day_posts.items():
                # Ne garder que les slots non assignés
                remaining_slots = [(date, slot) for date, slot in slots if not slot.assignee]
                if remaining_slots:
                    remaining[day_type][post_type] = remaining_slots
                    count = len(remaining_slots)
                    logger.debug(f"Slots restants {day_type} {post_type}: {count}")

        return remaining

    def _get_remaining_slots_for_group(self, group: str, available_posts: Dict) -> List[Tuple[date, TimeSlot]]:
        """
        Récupère tous les slots disponibles pour un groupe donné.
        
        Args:
            group: Nom du groupe (CmS, CmD, etc.)
            available_posts: Structure des posts disponibles
            
        Returns:
            List[Tuple[date, TimeSlot]]: Liste des slots disponibles pour ce groupe
        """
        remaining_slots = []
        group_members = self._get_group_members(group)
        
        for day_type, day_posts in available_posts.items():
            for post_type, slots in day_posts.items():
                if post_type in group_members:
                    # Filtrer selon le type de jour si nécessaire
                    for date, slot in slots:
                        slot_group = self._get_post_group(post_type, date)
                        if slot_group == group and not slot.assignee:
                            remaining_slots.append((date, slot))
        
        return remaining_slots

    def _get_slots_by_criticality(self, available_posts: Dict, planning: Planning = None) -> Dict[str, List[Tuple[date, TimeSlot]]]:
        """
        Organise les slots disponibles par niveau de criticité.
        
        Args:
            available_posts: Structure des posts disponibles
            
        Returns:
            Dict: Slots organisés par niveau de criticité
                Keys: "critical", "high", "normal"
        """
        slots_by_criticality = {
            "critical": [],  # < 40% disponibilité
            "high": [],     # 40-60% disponibilité
            "normal": []    # > 60% disponibilité
        }
        
        # Récupérer les périodes critiques
        critical_periods = self._get_critical_weekend_periods(planning)
        critical_dates = {period['date']: period['availability'] for period in critical_periods}
        
        # Pour chaque type de jour
        for day_type, day_posts in available_posts.items():
            for post_type, slots in day_posts.items():
                for date, slot in slots:
                    if not slot.assignee:
                        availability = critical_dates.get(date, 100)  # 100% par défaut
                        if availability < 40:
                            slots_by_criticality["critical"].append((date, slot))
                        elif availability < 60:
                            slots_by_criticality["high"].append((date, slot))
                        else:
                            slots_by_criticality["normal"].append((date, slot))
        
        # Log du résultat
        for criticality, slots in slots_by_criticality.items():
            logger.debug(f"Slots {criticality}: {len(slots)}")
        
        return slots_by_criticality

    
    
    def _distribute_final_posts(self, planning: Planning, available_posts: Dict,
                                intervals: Dict, doctor_states: Dict) -> bool:
        """
        Distribution finale des postes restants selon un processus en 4 phases.
        
        Args:
            planning: Planning en cours
            available_posts: Dictionnaire des postes disponibles
            intervals: Intervalles min/max pour chaque médecin
            doctor_states: État courant des attributions
            
        Returns:
            bool: True si tous les postes ont été attribués ou si impossible d'aller plus loin
        """
        try:
            # Collecter les slots restants
            remaining_slots = self._get_remaining_slots(available_posts)
            if not any(slots for day_slots in remaining_slots.values() 
                    for slots in day_slots.values()):
                return True

            initial_remaining = self._count_total_remaining(remaining_slots)
            logger.info(f"\nDISTRIBUTION FINALE: {initial_remaining} postes à attribuer")
            
            # Phase 1: Distribution aux CAT sous quotas
            self._final_distribute_to_cats(planning, remaining_slots)
            remaining_after_cats = self._count_total_remaining(remaining_slots)
            logger.info(f"Postes restants après CAT: {remaining_after_cats}")
            
            if remaining_after_cats > 0:
                # Phase 2: Distribution aux médecins sous minimum
                self._final_distribute_to_doctors_under_min(
                    planning, remaining_slots, intervals, doctor_states
                )
                remaining_after_min = self._count_total_remaining(remaining_slots)
                logger.info(f"Postes restants après distribution minimum: {remaining_after_min}")
                
                if remaining_after_min > 0:
                    # Phase 3: Distribution avec assouplissement
                    remaining = self._final_distribute_with_relaxed_constraints(
                        planning, remaining_slots, intervals, doctor_states
                    )
                    logger.info(f"Postes restants après assouplissement: {remaining}")
                    
                    # Phase 4: Rééquilibrage si nécessaire
                    if remaining > 0:
                        remaining = self._final_rebalance_distribution(
                            planning, remaining_slots, intervals, doctor_states
                        )
            
            # Vérification finale
            final_remaining = self._count_total_remaining(remaining_slots)
            if final_remaining == 0:
                logger.info("Distribution finale réussie - tous les postes attribués")
                return True
            else:
                logger.warning(f"Distribution incomplète: {final_remaining} postes non attribués")
                self._log_unassigned_posts(remaining_slots)
                return False
                
        except Exception as e:
            logger.error(f"Erreur dans la distribution finale: {e}")
            return False

    def _final_distribute_to_cats(self, planning: Planning, remaining_slots: Dict) -> None:
        """
        Phase 1: Distribution aux CAT n'ayant pas atteint leurs quotas.
        """
        logger.info("\nPHASE 1: DISTRIBUTION AUX CAT")
        logger.info("=" * 60)
        
        # Calcul des quotas restants
        cat_quotas = self._calculate_cat_remaining_quotas(planning)
        
        # Pour chaque type de jour
        for day_type in ["saturday", "sunday_holiday"]:
            for post_type, slots in list(remaining_slots[day_type].items()):
                if not slots:
                    continue
                    
                # Pour chaque CAT n'ayant pas atteint son quota
                for cat in self.cats:
                    quota = cat_quotas[cat.name][day_type].get(post_type, 0)
                    if quota <= 0:
                        continue
                        
                    # 1. Essai avec tous les desideratas
                    for idx, (date, slot) in enumerate(slots[:]):
                        if slot.assignee:
                            continue
                            
                        assigned = self._try_assign_to_cat(
                            cat, date, slot, planning, respect_secondary=True
                        )
                        
                        if assigned:
                            slots.pop(idx)
                            quota -= 1
                            if quota <= 0:
                                break
                                
                    # 2. Si quota non atteint, essai sans desideratas secondaires
                    if quota > 0:
                        for idx, (date, slot) in enumerate(slots[:]):
                            if slot.assignee:
                                continue
                                
                            assigned = self._try_assign_to_cat(
                                cat, date, slot, planning, respect_secondary=False
                            )
                            
                            if assigned:
                                slots.pop(idx)
                                quota -= 1
                                if quota <= 0:
                                    break

    def _final_distribute_to_doctors_under_min(self, planning: Planning,
                                            remaining_slots: Dict,
                                            intervals: Dict,
                                            doctor_states: Dict) -> None:
        """
        Phase 2: Distribution aux médecins sous le minimum de groupe.
        """
        logger.info("\nPHASE 2: DISTRIBUTION AUX MÉDECINS SOUS MINIMUM")
        logger.info("=" * 60)
        
        # Traiter d'abord les périodes critiques
        critical_periods = self._get_critical_weekend_periods(planning)
        critical_periods.sort(key=lambda x: x['availability'])
        
        # Traiter les périodes critiques
        for period in critical_periods:
            current_date = period['date']
            day_type = ("saturday" if current_date.weekday() == 5 and 
                        not DayType.is_bridge_day(current_date, self.cal) 
                        else "sunday_holiday")
            self._process_date_for_minimum(current_date, day_type, True, 
                                        planning, remaining_slots, intervals, 
                                        doctor_states)
        
        # Traiter les autres dates
        dates_processed = set()  # Utiliser un ensemble de dates
        for day_type in ["saturday", "sunday_holiday"]:
            for post_type, slots in remaining_slots[day_type].items():
                for date, _ in slots:
                    if date not in dates_processed and not any(p['date'] == date for p in critical_periods):
                        dates_processed.add(date)
                        self._process_date_for_minimum(date, day_type, False,
                                                planning, remaining_slots, intervals,
                                                doctor_states)

    def _process_date_for_minimum(self, current_date: date, day_type: str, 
                                is_critical: bool, planning: Planning,
                                remaining_slots: Dict, intervals: Dict,
                                doctor_states: Dict) -> None:
        """
        Traite une date donnée pour la distribution aux médecins sous minimum.
        """
        # Récupérer tous les slots pour cette date
        date_slots = []
        for post_type, slots in list(remaining_slots[day_type].items()):
            # Filtrer les slots pour la date courante
            slots_for_date = [(d, s, post_type) for d, s in slots 
                            if d == current_date and not s.assignee]
            date_slots.extend(slots_for_date)
        
        # Traiter les slots par groupe
        for date, slot, post_type in date_slots:
            group = self._get_post_group(post_type, date)
            if not group:
                continue
                
            # Trouver les médecins sous minimum pour ce groupe
            doctors_under_min = []
            for doctor in self.doctors:
                doctor_state = doctor_states.get(doctor.name, {})
                group_intervals = doctor_state.get('intervals', {}).get(group, {})
                group_min = group_intervals.get('min', 0)
                current = doctor_state.get('group_counts', {}).get(group, 0)
                
                if current < group_min:
                    score = (
                        group_min - current,  # Écart au minimum
                        self._calculate_unavailability_score(doctor, planning),  # Score d'indisponibilité
                        doctor.half_parts  # Priorité aux pleins temps
                    )
                    doctors_under_min.append((doctor, score))
            
            # Trier les médecins selon leurs scores
            doctors_under_min.sort(key=lambda x: x[1], reverse=True)
            
            # Tenter l'attribution
            success = False
            for doctor, _ in doctors_under_min:
                if self._try_assign_post(
                    doctor, date, slot, post_type,
                    planning, intervals, doctor_states
                ):
                    # Retirer le slot des remaining_slots
                    slots_list = remaining_slots[day_type][post_type]
                    slots_list.remove((date, slot))
                    if not slots_list:  # Si la liste est vide
                        del remaining_slots[day_type][post_type]
                    success = True
                    break
            
            if not success and is_critical:
                logger.warning(f"Impossible d'attribuer {post_type} le {date} "
                            f"(période critique)")

    def _find_matching_slots(self, current_date: date, day_type: str,
                        remaining_slots: Dict) -> List[Tuple[date, TimeSlot, str]]:
        """
        Trouve tous les slots correspondant à une date donnée.
        """
        matching_slots = []
        for post_type, slots in remaining_slots[day_type].items():
            for d, slot in slots:
                if d == current_date and not slot.assignee:
                    matching_slots.append((d, slot, post_type))
        return matching_slots

    def _final_distribute_with_relaxed_constraints(self, planning: Planning,
                                            remaining_slots: Dict,
                                            intervals: Dict,
                                            doctor_states: Dict) -> int:
        """
        Phase 3: Distribution avec assouplissement des desideratas secondaires.
        Returns:
            int: Nombre de postes restants
        """
        logger.info("\nPHASE 3: DISTRIBUTION AVEC ASSOUPLISSEMENT")
        logger.info("=" * 60)
        
        # Trier les périodes critiques
        critical_periods = self._get_critical_weekend_periods(planning)
        critical_periods.sort(key=lambda x: x['availability'])
        
        def calculate_doctor_score(doctor: Doctor) -> float:
            """Calcule le score d'un médecin pour l'attribution."""
            # Score basé sur le taux d'indisponibilité
            unavailability_score = self._calculate_unavailability_score(doctor, planning)
            
            # Score basé sur la charge de travail
            total_posts = sum(
                sum(counts.values())
                for counts in doctor_states[doctor.name]['post_counts'].values()
            )
            workload_score = 1 / (total_posts + 1)  # Éviter division par zéro
            
            # Combinaison des scores avec facteur aléatoire
            score = (unavailability_score * 0.6 + workload_score * 0.4) 
            score *= 1 + (random.random() * 0.2 - 0.1)  # ±10% aléatoire
            
            return score
        
        # Traiter d'abord les périodes critiques
        for period in critical_periods:
            date = period['date']
            day_type = ("saturday" if date.weekday() == 5 and 
                        not DayType.is_bridge_day(date, self.cal) 
                        else "sunday_holiday")
                        
            for post_type, slots in list(remaining_slots[day_type].items()):
                slots_for_date = [(d, s) for d, s in slots 
                                if d == date and not s.assignee]
                
                for date, slot in slots_for_date:
                    # 1. Essai avec toutes les contraintes
                    available_doctors = self._get_available_doctors_for_slot(
                        date, slot, post_type, planning, intervals, False
                    )
                    
                    if available_doctors:
                        best_doctor = max(
                            available_doctors,
                            key=calculate_doctor_score
                        )
                        
                        if self._try_assign_post(
                            best_doctor, date, slot, post_type,
                            planning, intervals, doctor_states
                        ):
                            slots.remove((date, slot))
                            continue
                    
                    # 2. Essai sans desideratas secondaires
                    available_doctors = self._get_available_doctors_for_slot(
                        date, slot, post_type, planning, intervals, True
                    )
                    
                    if available_doctors:
                        best_doctor = max(
                            available_doctors,
                            key=calculate_doctor_score
                        )
                        
                        if self._try_assign_post(
                            best_doctor, date, slot, post_type,
                            planning, intervals, doctor_states,
                            ignore_secondary=True
                        ):
                            slots.remove((date, slot))
        
        # Traiter les autres dates
        previous_remaining = float('inf')
        while True:
            current_remaining = self._count_total_remaining(remaining_slots)
            if current_remaining >= previous_remaining:
                break
            previous_remaining = current_remaining
            
            for day_type in ["saturday", "sunday_holiday"]:
                for post_type, slots in list(remaining_slots[day_type].items()):
                    for date, slot in slots[:]:
                        if slot.assignee:
                            continue
                            
                        # Même processus que pour les périodes critiques
                        available_doctors = self._get_available_doctors_for_slot(
                            date, slot, post_type, planning, intervals, True
                        )
                        
                        if available_doctors:
                            best_doctor = max(
                                available_doctors,
                                key=calculate_doctor_score
                            )
                            
                            if self._try_assign_post(
                                best_doctor, date, slot, post_type,
                                planning, intervals, doctor_states,
                                ignore_secondary=True
                            ):
                                slots.remove((date, slot))
        
        return self._count_total_remaining(remaining_slots)
    
    
    

    def _final_rebalance_distribution(self, planning: Planning,
                                    remaining_slots: Dict,
                                    intervals: Dict,
                                    doctor_states: Dict) -> int:
        """
        Phase 4: Tentative de rééquilibrage des postes restants.
        Essaie de réaffecter les postes en déplaçant des attributions existantes.
        
        Args:
            planning: Planning en cours
            remaining_slots: Slots restants à attribuer
            intervals: Intervalles min/max
            doctor_states: États des médecins
            
        Returns:
            int: Nombre de postes restants après rééquilibrage
        """
        try:
            logger.info("\nPHASE 4: RÉÉQUILIBRAGE")
            logger.info("=" * 60)
            
            # Sauvegarder l'état initial complet avec doctor_states
            initial_state = self._save_planning_state(planning, doctor_states)
            best_state = None
            min_unassigned = float('inf')
            
            # Pour chaque slot non attribué
            for day_type in ["saturday", "sunday_holiday"]:
                for post_type, slots in list(remaining_slots[day_type].items()):
                    for date, slot in slots[:]:
                        if slot.assignee:
                            continue
                            
                        logger.info(f"\nTentative de rééquilibrage pour {post_type} le {date}")
                        
                        # Pour chaque médecin disponible
                        available_doctors = self._get_available_doctors_for_forced(
                            planning, date, slot
                        )
                        
                        for doctor in available_doctors:
                            # Sauvegarder l'état actuel avant la tentative
                            current_state = self._save_planning_state(planning, doctor_states)
                            
                            # Tenter l'attribution forcée
                            if self._force_assign_post(doctor, date, slot, post_type,
                                            planning, doctor_states):
                                logger.info(f"Attribution forcée à {doctor.name}")
                                
                                # Tenter le rééquilibrage du groupe affecté
                                group = self._get_post_group(post_type, date)
                                if group:
                                    success = self._rebalance_group_assignments(
                                        doctor, group, planning, intervals,
                                        doctor_states
                                    )
                                    
                                    if success:
                                        # Vérifier si c'est la meilleure solution
                                        unassigned = self._count_total_remaining(remaining_slots)
                                        if unassigned < min_unassigned:
                                            min_unassigned = unassigned
                                            best_state = self._save_planning_state(planning, doctor_states)
                                            logger.info("Nouvelle meilleure solution trouvée")
                                    
                            # Restaurer l'état avant tentative
                            self._restore_planning_state(planning, current_state, doctor_states)
            
            # Appliquer la meilleure solution si trouvée
            if best_state is not None:
                logger.info("\nApplication de la meilleure solution trouvée")
                self._restore_planning_state(planning, best_state, doctor_states)
                return min_unassigned
            else:
                # Restaurer l'état initial si aucune amélioration
                logger.warning("\nAucune solution de rééquilibrage trouvée")
                self._restore_planning_state(planning, initial_state, doctor_states)
                return self._count_total_remaining(remaining_slots)
                
        except Exception as e:
            logger.error(f"Erreur dans le rééquilibrage: {e}")
            # En cas d'erreur, restaurer l'état initial
            if initial_state:
                self._restore_planning_state(planning, initial_state, doctor_states)
            return self._count_total_remaining(remaining_slots)

    

    def _rebalance_group_assignments(self, doctor: Doctor, group: str,
                                    planning: Planning, intervals: Dict,
                                    doctor_states: Dict) -> bool:
        """
        Tente de rééquilibrer les attributions d'un groupe après une attribution forcée.
        
        Args:
            doctor: Médecin concerné
            group: Groupe à rééquilibrer
            planning: Planning en cours
            intervals: Intervalles min/max
            doctor_states: État des attributions
            
        Returns:
            bool: True si le rééquilibrage est réussi
        """
        try:
            # 1. Trouver tous les postes du groupe attribués au médecin
            group_posts = self._find_group_posts(doctor, group, planning)
            if not group_posts:
                return False
                
            # 2. Trier les postes par facilité de réattribution
            sorted_posts = self._sort_posts_by_reattribution_ease(
                group_posts, planning, intervals
            )
            
            # 3. Pour chaque poste, tenter un échange
            for date, slot in sorted_posts:
                # Sauvegarder l'assignation actuelle
                original_assignee = slot.assignee
                slot.assignee = None
                
                # Chercher un médecin pour la réattribution
                available_doctors = [
                    d for d in self.doctors
                    if d.name != doctor.name and 
                    self._can_potentially_take_post(d, date, slot, planning, intervals)
                ]
                
                # Trier par charge de travail et demi-parts
                available_doctors.sort(
                    key=lambda d: (
                        -d.half_parts,  # Priorité aux pleins temps
                        sum(sum(counts.values()) 
                            for counts in doctor_states[d.name]['post_counts'].values())
                    )
                )
                
                # Tenter la réattribution
                assigned = False
                for new_doctor in available_doctors:
                    if self._try_assign_post(
                        new_doctor, date, slot, slot.abbreviation,
                        planning, intervals, doctor_states,
                        ignore_secondary=True
                    ):
                        assigned = True
                        logger.info(f"Poste réattribué de {doctor.name} à {new_doctor.name}")
                        break
                        
                if not assigned:
                    # Restaurer l'attribution originale si échec
                    slot.assignee = original_assignee
                    continue
                
                # Vérifier si le rééquilibrage est satisfaisant
                if self._check_group_balance(doctor, group, planning, intervals):
                    return True
                    
                # Sinon, annuler cette réattribution
                slot.assignee = original_assignee
                
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors du rééquilibrage du groupe: {e}")
            return False

    def _check_group_balance(self, doctor: Doctor, group: str,
                            planning: Planning, intervals: Dict) -> bool:
        """
        Vérifie si les attributions d'un groupe sont équilibrées pour un médecin.
        
        Args:
            doctor: Médecin à vérifier
            group: Groupe à vérifier
            planning: Planning en cours
            intervals: Intervalles min/max
            
        Returns:
            bool: True si le groupe est équilibré
        """
        try:
            # Récupérer les limites du groupe
            group_intervals = intervals.get(doctor.name, {}).get('weekend_groups', {}).get(group, {})
            if not group_intervals:
                return True
                
            min_required = group_intervals.get('min', 0)
            max_allowed = group_intervals.get('max', float('inf'))
            
            # Compter les postes actuels
            current_count = self._count_group_posts(doctor, group, planning)
            
            # Vérifier l'équilibre
            return min_required <= current_count <= max_allowed
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'équilibre: {e}")
            return False

    def _calculate_unavailability_score(self, doctor: Doctor, planning: Planning) -> float:
        """
        Calcule un score basé sur le taux d'indisponibilité du médecin.
        Plus le médecin a demandé d'indisponibilités, plus son score est élevé.
        
        Args:
            doctor: Médecin à évaluer
            planning: Planning en cours
            
        Returns:
            float: Score entre 0 et 1
        """
        # Compter les jours d'indisponibilité weekend
        unavailable_days = set()
        
        for desiderata in doctor.desiderata:
            current_date = max(desiderata.start_date, planning.start_date)
            end_date = min(desiderata.end_date, planning.end_date)
            
            while current_date <= end_date:
                if (current_date.weekday() >= 5 or 
                    self.cal.is_holiday(current_date) or
                    DayType.is_bridge_day(current_date, self.cal)):
                    unavailable_days.add(current_date)
                current_date += timedelta(days=1)
        
        # Calculer le total des jours weekend
        total_weekend_days = len([
            d for d in planning.days
            if d.is_weekend or d.is_holiday_or_bridge
        ])
        
        if total_weekend_days == 0:
            return 0.0
            
        # Calculer le score
        return len(unavailable_days) / total_weekend_days
    
    
    
    def _get_remaining_slots(self, available_posts: Dict) -> Dict:
        """
        Organise les slots non attribués par type de jour et type de poste.
        
        Args:
            available_posts: Dict des postes disponibles
            
        Returns:
            Dict: Structure organisée des slots restants
        """
        remaining = {
            "saturday": defaultdict(list),
            "sunday_holiday": defaultdict(list)
        }
        
        # Pour chaque type de jour
        for day_type, day_posts in available_posts.items():
            # Pour chaque type de poste
            for post_type, slots in day_posts.items():
                # Ne garder que les slots non assignés
                remaining_slots = [(date, slot) for date, slot in slots 
                                if not slot.assignee]
                if remaining_slots:
                    remaining[day_type][post_type] = remaining_slots
                    logger.debug(f"Slots restants {day_type} {post_type}: {len(remaining_slots)}")
        
        return remaining

    def _calculate_cat_remaining_quotas(self, planning: Planning) -> Dict:
        """
        Calcule les quotas restants pour les CAT.
        
        Args:
            planning: Planning en cours
            
        Returns:
            Dict: Structure {cat_name: {day_type: {post_type: quota}}}
        """
        quotas = {}
        pre_analysis = planning.pre_analysis_results
        
        # Pour chaque CAT
        for cat in self.cats:
            quotas[cat.name] = {
                "saturday": defaultdict(int),
                "sunday_holiday": defaultdict(int)
            }
            
            # Pour chaque type de jour
            for day_type in ["saturday", "sunday_holiday"]:
                # Récupérer les quotas attendus
                expected = pre_analysis["cat_posts"][day_type]
                
                # Compter les postes déjà attribués
                assigned = defaultdict(int)
                for day in planning.days:
                    if ((day_type == "saturday" and day.date.weekday() == 5 and 
                        not DayType.is_bridge_day(day.date, self.cal)) or
                        (day_type == "sunday_holiday" and 
                        (day.date.weekday() == 6 or day.is_holiday_or_bridge))):
                        for slot in day.slots:
                            if slot.assignee == cat.name:
                                assigned[slot.abbreviation] += 1
                
                # Calculer les quotas restants
                for post_type, expected_count in expected.items():
                    remaining = expected_count - assigned[post_type]
                    if remaining > 0:
                        quotas[cat.name][day_type][post_type] = remaining
        
        return quotas

    def _save_planning_state(self, planning: Planning, doctor_states: Dict) -> Dict:
        """
        Sauvegarde l'état complet du planning et des états des médecins.
        
        Args:
            planning: Planning à sauvegarder
            doctor_states: États des médecins à sauvegarder
            
        Returns:
            Dict: État sauvegardé complet
        """
        state = {
            'assignments': [],
            'doctor_states': deepcopy(doctor_states)
        }
        
        # Sauvegarder toutes les assignations
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                if slot.assignee:
                    state['assignments'].append({
                        'date': day.date,
                        'post_type': slot.abbreviation,
                        'assignee': slot.assignee,
                        'slot_id': id(slot)
                    })
        
        return state

    def _restore_planning_state(self, planning: Planning, state: Dict, doctor_states: Dict) -> None:
        """
        Restaure un état complet du planning.
        
        Args:
            planning: Planning à restaurer
            state: État sauvegardé à restaurer
        """
        try:
            # 1. Réinitialiser toutes les assignations
            for day in planning.days:
                if not (day.is_weekend or day.is_holiday_or_bridge):
                    continue
                for slot in day.slots:
                    slot.assignee = None
            
            # 2. Restaurer les assignations
            for assignment in state['assignments']:
                date = assignment['date']
                post_type = assignment['post_type']
                assignee = assignment['assignee']
                
                day = planning.get_day(date)
                if day:
                    for slot in day.slots:
                        if (slot.abbreviation == post_type and 
                            id(slot) == assignment['slot_id']):
                            slot.assignee = assignee
                            break
            
            # 3. Restaurer les états des médecins
            if 'doctor_states' in state:
                doctor_states.clear()
                doctor_states.update(deepcopy(state['doctor_states']))
                
        except Exception as e:
            logger.error(f"Erreur lors de la restauration de l'état: {e}")
            
    def _find_group_posts(self, doctor: Doctor, group: str, 
                        planning: Planning) -> List[Tuple[date, TimeSlot]]:
        """
        Trouve tous les postes d'un groupe attribués à un médecin.
        
        Args:
            doctor: Médecin concerné
            group: Groupe à chercher
            planning: Planning en cours
            
        Returns:
            List[Tuple[date, TimeSlot]]: Liste des postes triés par date
        """
        group_posts = []
        
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                if (slot.assignee == doctor.name and 
                    self._get_post_group(slot.abbreviation, day.date) == group):
                    group_posts.append((day.date, slot))
        
        return sorted(group_posts, key=lambda x: x[0])

    def _sort_posts_by_reattribution_ease(self, 
                                        posts: List[Tuple[date, TimeSlot]],
                                        planning: Planning,
                                        intervals: Dict) -> List[Tuple[date, TimeSlot]]:
        """
        Trie les postes par facilité estimée de réattribution.
        
        Args:
            posts: Liste des postes à trier
            planning: Planning en cours
            intervals: Intervalles min/max
            
        Returns:
            List[Tuple[date, TimeSlot]]: Postes triés
        """
        def get_reattribution_score(date_slot: Tuple[date, TimeSlot]) -> float:
            date, slot = date_slot
            score = 0.0
            
            # 1. Score basé sur les médecins disponibles
            available_count = sum(
                1 for doctor in self.doctors
                if self._can_potentially_take_post(doctor, date, slot,
                                            planning, intervals)
            )
            score = available_count / len(self.doctors)
            
            # 2. Bonus pour les dates plus éloignées
            days_ahead = (date - planning.start_date).days
            score += min(days_ahead * 0.01, 0.5)  # Max 50% de bonus
            
            # 3. Malus pour les périodes critiques
            critical_periods = self._get_critical_weekend_periods(planning)
            if any(p['date'] == date for p in critical_periods):
                score *= 0.8  # 20% de malus
                
            return score

        return sorted(posts, key=get_reattribution_score, reverse=True)

    def _get_available_doctors_for_slot(self, date: date, slot: TimeSlot,
                                    post_type: str, planning: Planning,
                                    intervals: Dict, ignore_secondary: bool = False
                                    ) -> List[Doctor]:
        """
        Version optimisée de la récupération des médecins disponibles.
        
        Args:
            date: Date du slot
            slot: Slot à attribuer
            post_type: Type de poste
            planning: Planning en cours
            intervals: Intervalles min/max
            ignore_secondary: Si True, ignore les desideratas secondaires
            
        Returns:
            List[Doctor]: Liste des médecins disponibles
        """
        available_doctors = []
        
        for doctor in self.doctors:
            # Vérification rapide des contraintes critiques
            if not self._check_critical_constraints(doctor, date, slot, planning):
                continue
                
            # Vérification des desideratas selon le mode
            if not ignore_secondary:
                if not self.constraints.check_desiderata_constraint(
                    doctor, date, slot, planning
                ):
                    continue
            else:
                # Vérifier uniquement les desideratas primaires
                if not self._check_primary_desiderata_only(doctor, date, slot):
                    continue
                    
            # Vérification des limites de groupe
            group = self._get_post_group(post_type, date)
            if group:
                group_max = intervals.get(doctor.name, {}).get('weekend_groups', {})\
                                .get(group, {}).get('max', float('inf'))
                current = self._count_group_posts(doctor, group, planning)
                if current >= group_max:
                    continue
                    
            # Si toutes les vérifications passent
            available_doctors.append(doctor)
            
        return available_doctors

    def _check_critical_constraints(self, doctor: Doctor, date: date,
                                slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie les contraintes critiques pour un médecin.
        
        Args:
            doctor: Médecin à vérifier
            date: Date du slot
            slot: Slot à vérifier
            planning: Planning en cours
            
        Returns:
            bool: True si toutes les contraintes critiques sont respectées
        """
        try:
            # 1. Vérifier les chevauchements
            day = planning.get_day(date)
            if day:
                for existing_slot in day.slots:
                    if existing_slot.assignee == doctor.name:
                        if (slot.start_time < existing_slot.end_time and 
                            slot.end_time > existing_slot.start_time):
                            return False

            # 2. Vérifier les contraintes de planning.py
            return all([
                self.constraints.check_nl_constraint(doctor, date, slot, planning),
                self.constraints.check_nm_na_constraint(doctor, date, slot, planning),
                self.constraints.check_max_posts_per_day(doctor, date, slot, planning),
                self.constraints.check_morning_after_night_shifts(doctor, date, slot, planning),
                self.constraints.check_consecutive_night_shifts(doctor, date, slot, planning),
                self.constraints.check_consecutive_working_days(doctor, date, slot, planning)
            ])

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des contraintes pour {doctor.name}: {e}")
            return False
        
    def _count_total_remaining(self, remaining_slots: Dict) -> int:
        """
        Compte le nombre total de slots restants à attribuer.
        
        Args:
            remaining_slots: Structure des slots restants par type de jour et type de poste
            
        Returns:
            int: Nombre total de slots non attribués
        """
        return sum(
            len(slots) for day_slots in remaining_slots.values()
            for slots in day_slots.values()
        )

    def _try_assign_to_cat(self, cat: CAT, date: date, slot: TimeSlot,
                        planning: Planning, respect_secondary: bool = True) -> bool:
        """
        Tente d'attribuer un slot à un CAT en respectant les contraintes.
        
        Args:
            cat: CAT à qui attribuer le poste
            date: Date du slot
            slot: Slot à attribuer
            planning: Planning en cours
            respect_secondary: Si False, ignore les desideratas secondaires
            
        Returns:
            bool: True si l'attribution est réussie
        """
        try:
            # 1. Vérification des desideratas
            if respect_secondary:
                if not self.constraints.can_assign_to_assignee(cat, date, slot, planning):
                    return False
            else:
                # Vérification uniquement des desideratas primaires
                for desiderata in cat.desiderata:
                    if not hasattr(desiderata, 'priority') or desiderata.priority == "primary":
                        if (desiderata.start_date <= date <= desiderata.end_date and
                            desiderata.overlaps_with_slot(slot)):
                            return False

                # Vérifier les autres contraintes (repos, chevauchement)
                temp_desiderata = cat.desiderata
                cat.desiderata = [d for d in cat.desiderata
                            if not hasattr(d, 'priority') or d.priority == "primary"]
                can_assign = all([
                    self.constraints.check_nl_constraint(cat, date, slot, planning),
                    self.constraints.check_nm_na_constraint(cat, date, slot, planning),
                    self.constraints.check_time_overlap(cat, date, slot, planning),
                    self.constraints.check_max_posts_per_day(cat, date, slot, planning)
                ])
                cat.desiderata = temp_desiderata
                
                if not can_assign:
                    return False

            # 2. Attribution du poste
            slot.assignee = cat.name
            logger.info(f"CAT {cat.name}: {slot.abbreviation} attribué le {date} "
                    f"{'(sans desiderata secondaire)' if not respect_secondary else ''}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution au CAT {cat.name}: {e}")
            return False

    def _get_available_doctors_for_forced(self, planning: Planning, date: date,
                                    slot: TimeSlot) -> List[Doctor]:
        """
        Récupère les médecins disponibles pour une attribution forcée.
        Vérifie uniquement les contraintes critiques de base.
        
        Args:
            planning: Planning en cours
            date: Date du slot
            slot: Slot à attribuer
            
        Returns:
            List[Doctor]: Liste des médecins disponibles triée par priorité
        """
        available_doctors = []
        
        for doctor in self.doctors:
            # Vérifier uniquement les contraintes critiques de base
            if not self._check_critical_constraints_for_forced(doctor, date, slot, planning):
                continue
                
            available_doctors.append(doctor)
        
        # Trier par priorité
        return sorted(available_doctors, 
                    key=lambda d: (d.half_parts, 
                                -len(d.desiderata)), # Moins de desiderata = plus prioritaire
                    reverse=True)

    def _check_critical_constraints_for_forced(self, doctor: Doctor, date: date,
                                        slot: TimeSlot, planning: Planning) -> bool:
        """
        Vérifie uniquement les contraintes critiques de base pour une attribution forcée.
        
        Args:
            doctor: Médecin à vérifier
            date: Date du slot
            slot: Slot à attribuer
            planning: Planning en cours
            
        Returns:
            bool: True si les contraintes critiques sont respectées
        """
        # 1. Vérifier les desideratas primaires
        for desiderata in doctor.desiderata:
            if not hasattr(desiderata, 'priority') or desiderata.priority == "primary":
                if (desiderata.start_date <= date <= desiderata.end_date and
                    desiderata.overlaps_with_slot(slot)):
                    return False
        
        # 2. Vérifier les chevauchements
        day = planning.get_day(date)
        if day:
            for existing_slot in day.slots:
                if existing_slot.assignee == doctor.name:
                    if (slot.start_time < existing_slot.end_time and
                        slot.end_time > existing_slot.start_time):
                        return False
        
        # 3. Vérifier les contraintes de repos critiques
        return all([
            self.constraints.check_nl_constraint(doctor, date, slot, planning),
            self.constraints.check_morning_after_night_shifts(doctor, date, slot, planning),
            self.constraints.check_consecutive_night_shifts(doctor, date, slot, planning),
            self.constraints.check_consecutive_working_days(doctor, date, slot, planning)
        ])

    def _force_assign_post(self, doctor: Doctor, date: date, slot: TimeSlot,
                        post_type: str, planning: Planning, doctor_states: Dict) -> bool:
        """
        Force l'attribution d'un poste sans vérifier toutes les contraintes.
        
        Args:
            doctor: Médecin à qui attribuer le poste
            date: Date du slot
            slot: Slot à attribuer
            post_type: Type de poste
            planning: Planning en cours
            doctor_states: États des médecins
            
        Returns:
            bool: True si l'attribution est réussie
        """
        try:
            # Vérifier uniquement les contraintes critiques de base
            if not self._check_critical_constraints_for_forced(doctor, date, slot, planning):
                return False

            # Attribution forcée
            slot.assignee = doctor.name
            
            # Mise à jour des états
            day_type = ("saturday" if date.weekday() == 5 and
                    not DayType.is_bridge_day(date, self.cal)
                    else "sunday_holiday")
            
            if doctor.name not in doctor_states:
                doctor_states[doctor.name] = {
                    'post_counts': {day_type: {}},
                    'group_counts': {}
                }
            
            if day_type not in doctor_states[doctor.name]['post_counts']:
                doctor_states[doctor.name]['post_counts'][day_type] = {}
            
            # Mise à jour des compteurs
            doctor_states[doctor.name]['post_counts'][day_type][post_type] = \
                doctor_states[doctor.name]['post_counts'][day_type].get(post_type, 0) + 1
            
            # Mise à jour groupe si applicable
            group = self._get_post_group(post_type, date)
            if group:
                doctor_states[doctor.name]['group_counts'][group] = \
                    doctor_states[doctor.name]['group_counts'].get(group, 0) + 1
            
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution forcée à {doctor.name}: {e}")
            return False

    def _can_potentially_take_post(self, doctor: Doctor, date: date,
                                slot: TimeSlot, planning: Planning,
                                intervals: Dict) -> bool:
        """
        Vérifie si un médecin pourrait potentiellement prendre un poste.
        
        Args:
            doctor: Médecin à vérifier
            date: Date du slot
            slot: Slot à vérifier
            planning: Planning en cours
            intervals: Intervalles min/max
            
        Returns:
            bool: True si le médecin peut potentiellement prendre le poste
        """
        # 1. Vérification rapide des contraintes de base
        if not self._check_critical_constraints_for_forced(doctor, date, slot, planning):
            return False
        
        # 2. Vérification des limites de groupe
        group = self._get_post_group(slot.abbreviation, date)
        if group:
            current = self._count_group_posts(doctor, group, planning)
            max_allowed = intervals.get(doctor.name, {}).get('weekend_groups', {})\
                                .get(group, {}).get('max', float('inf'))
            if current >= max_allowed:
                return False
        
        return True

    def _check_primary_desiderata_only(self, doctor: Doctor, date: date,
                                    slot: TimeSlot) -> bool:
        """
        Vérifie uniquement les desideratas primaires d'un médecin.
        
        Args:
            doctor: Médecin à vérifier
            date: Date du slot
            slot: Slot à vérifier
            
        Returns:
            bool: True si aucun conflit avec les desideratas primaires
        """
        for desiderata in doctor.desiderata:
            if not hasattr(desiderata, 'priority') or desiderata.priority == "primary":
                if (desiderata.start_date <= date <= desiderata.end_date and
                    desiderata.overlaps_with_slot(slot)):
                    return False
        return True

    
    def _try_assign_post(self, doctor: Doctor, date: date, slot: TimeSlot,
                        post_type: str, planning: Planning,
                        intervals: Dict, doctor_states: Dict,
                        ignore_secondary: bool = False) -> bool:
        """
        Tente d'attribuer un poste à un médecin en respectant les contraintes.
        
        Args:
            doctor: Médecin à qui attribuer le poste
            date: Date du slot
            slot: Slot à attribuer
            post_type: Type de poste
            planning: Planning en cours
            intervals: Intervalles min/max
            doctor_states: États des médecins
            ignore_secondary: Si True, ignore les desideratas secondaires
            
        Returns:
            bool: True si l'attribution est réussie
        """
        try:
            # 1. Vérifications initiales des contraintes critiques
            if not self._check_critical_constraints(doctor, date, slot, planning):
                return False

            # 2. Vérification des desideratas
            if not ignore_secondary:
                if not self.constraints.check_desiderata_constraint(
                    doctor, date, slot, planning, respect_secondary=True
                ):
                    return False
            else:
                # Vérifier uniquement les desideratas primaires
                if not self._check_primary_desiderata_only(doctor, date, slot):
                    return False

            # 3. Vérification des limites de groupe
            group = self._get_post_group(post_type, date)
            if group:
                doc_intervals = intervals.get(doctor.name, {})
                group_max = (doc_intervals.get('weekend_groups', {})
                            .get(group, {})
                            .get('max', float('inf')))
                
                current = doctor_states.get(doctor.name, {}).get('group_counts', {}).get(group, 0)
                if current >= group_max:
                    return False

            # 4. Attribution du poste
            slot.assignee = doctor.name

            # 5. Mise à jour des états
            day_type = ("saturday" if date.weekday() == 5 and 
                    not DayType.is_bridge_day(date, self.cal) 
                    else "sunday_holiday")
            
            # Initialiser la structure des états si nécessaire
            if doctor.name not in doctor_states:
                doctor_states[doctor.name] = {
                    'post_counts': {day_type: {}},
                    'group_counts': {}
                }
            if day_type not in doctor_states[doctor.name]['post_counts']:
                doctor_states[doctor.name]['post_counts'][day_type] = {}

            # Mettre à jour les compteurs de poste
            doctor_states[doctor.name]['post_counts'][day_type][post_type] = \
                doctor_states[doctor.name]['post_counts'][day_type].get(post_type, 0) + 1

            # Mettre à jour les compteurs de groupe si nécessaire
            if group:
                doctor_states[doctor.name]['group_counts'][group] = \
                    doctor_states[doctor.name]['group_counts'].get(group, 0) + 1

            logger.info(f"Attribution réussie: {doctor.name} - {post_type} le {date}")
            if group:
                logger.debug(f"  Groupe {group}: {doctor_states[doctor.name]['group_counts'][group]}")
            
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution à {doctor.name}: {e}")
            # En cas d'erreur, annuler l'attribution
            if slot.assignee == doctor.name:
                slot.assignee = None
            return False

    
        
        
    def _log_unassigned_posts(self, remaining_slots: Dict) -> None:
        """
        Log détaillé des postes non attribués.
        
        Args:
            remaining_slots: Structure des slots restants
        """
        logger.warning("\nDétail des postes non attribués:")
        for day_type in ["saturday", "sunday_holiday"]:
            unassigned = {
                post_type: [(date.strftime("%Y-%m-%d"), slot.abbreviation)
                        for date, slot in slots]
                for post_type, slots in remaining_slots[day_type].items()
                if slots
            }
            if unassigned:
                logger.warning(f"\n{day_type.upper()}:")
                for post_type, dates_slots in unassigned.items():
                    for date, abbrev in dates_slots:
                        logger.warning(f"  - {abbrev} le {date}")
