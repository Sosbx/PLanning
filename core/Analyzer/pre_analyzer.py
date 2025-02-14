# core/Analyzer/pre_analyzer.py

# © 2024 HILAL Arkane. Tous droits réservés.
# # core/pre_analyzer.py

from datetime import date, timedelta, time
from typing import List, Dict, Tuple
from core.Constantes.models import Doctor, CAT, DailyPostConfiguration, Desiderata, PostManager, WEEKEND_COMBINATIONS, WEEKDAY_COMBINATIONS, ALL_COMBINATIONS, ALL_POST_TYPES, PostConfig
from workalendar.europe import France
from core.Constantes.custom_post import CustomPost
from core.Constantes.day_type import DayType
from core.Analyzer.combinations_analyzer import CombinationsAnalyzer
from core.Analyzer.availability_matrix import AvailabilityMatrix


import logging
import math
from core.Constantes.data_persistence import DataPersistence
logger = logging.getLogger(__name__)

class PlanningPreAnalyzer:
    def __init__(self, doctors: List[Doctor], cats: List[CAT], post_configuration: DailyPostConfiguration):
        self.doctors = doctors
        self.cats = cats
        self.post_configuration = post_configuration
        self.start_date = None
        self.end_date = None 
        self.total_days = 0
        self.cal = France()
        self.logger = logging.getLogger(__name__)
        self.post_manager = PostManager()
        self.custom_posts = self.load_custom_posts()
        self.clean_invalid_custom_posts()
        self.combinations_cache = {"weekday": {}, "weekend": {}}
        # Nouveau : calculer le total des demi-parts
        self.total_half_parts = sum(doctor.half_parts for doctor in self.doctors)
        self.full_time_doctors = len([d for d in self.doctors if d.half_parts == 2])
        self.half_time_doctors = len([d for d in self.doctors if d.half_parts == 1])
        self.availability_matrix = None  # Ajout de l'attribut

    
    def clean_invalid_custom_posts(self):
        """Nettoie les postes personnalisés invalides"""
        if not self.custom_posts:
            return

        self.logger.info("Nettoyage des postes personnalisés")
        invalid_posts = []
        valid_config = set()

        # Collecter tous les postes valides depuis la configuration
        for config in [
            self.post_configuration.weekday,
            self.post_configuration.saturday,
            self.post_configuration.sunday_holiday,
            self.post_configuration.cat_weekday,
            self.post_configuration.cat_saturday,
            self.post_configuration.cat_sunday_holiday
        ]:
            valid_config.update(config.keys())

        # Ajouter les postes standard
        valid_config.update(ALL_POST_TYPES)

        # Identifier les postes invalides
        for name in self.custom_posts.keys():
            if name not in valid_config:
                invalid_posts.append(name)
                self.logger.debug(f"Poste personnalisé invalide trouvé: {name}")

        # Supprimer les postes invalides
        for name in invalid_posts:
            del self.custom_posts[name]
            self.logger.info(f"Suppression du poste personnalisé invalide: {name}")

        # Sauvegarder les modifications
        data_persistence = DataPersistence()
        custom_posts_data = {
            name: post.to_dict() 
            for name, post in self.custom_posts.items()
        }
        data_persistence.save_custom_posts(custom_posts_data)
        self.logger.info(f"Postes personnalisés nettoyés. {len(invalid_posts)} postes supprimés")

    def load_custom_posts(self):
        """Charge la configuration des postes personnalisés"""
        data_persistence = DataPersistence()
        custom_posts_data = data_persistence.load_custom_posts()
        
        # Convertir les données en objets CustomPost si ce n'est pas déjà fait
        if custom_posts_data and isinstance(next(iter(custom_posts_data.values())), dict):
            from core.Constantes.custom_post import CustomPost
            return {
                name: CustomPost.from_dict(data) 
                for name, data in custom_posts_data.items()
            }
        return custom_posts_data
    
    def calculate_total_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    def set_date_range(self, start_date: date, end_date: date):
        self.start_date = start_date
        self.end_date = end_date
        self.total_days = self.calculate_total_days()
        # Initialiser la matrice de disponibilités
        self.availability_matrix = AvailabilityMatrix(
            start_date=self.start_date,
            end_date=self.end_date,
            doctors=self.doctors,
            cats=self.cats
        )

    def analyze(self) -> Dict:
        if not self.start_date or not self.end_date or self.start_date > self.end_date:
            raise ValueError("Invalid date range. Please set valid start and end dates.")

        self.logger.info("=" * 100)
        self.logger.info(f"ANALYSE DU PLANNING: {self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')}")
        self.logger.info("=" * 100)

        # 1. Distribution des jours
        self._log_days_distribution()
        
        # 2. Vérification des configurations spécifiques
        config_errors = self.validate_specific_configs()
        if config_errors:
            self.logger.warning("\nAttention : Des configurations spécifiques se chevauchent !")
            for error in config_errors:
                self.logger.warning(error)

        # 3. Calcul du total des postes
        self.logger.info("\nÉTAPE 1: Calcul du nombre total de postes")
        total_posts = self.analyze_posts()
        self._log_total_posts_distribution(total_posts)

        # 4. Analyse des postes CAT
        self.logger.info("\nÉTAPE 2: Analyse des postes réservés aux CAT")
        cat_posts = self.analyze_cat_posts()
        self._log_cat_posts_distribution(cat_posts)

        # 5. Ajustement des postes après soustraction CAT
        self.logger.info("\nÉTAPE 3: Ajustement des postes pour les médecins")
        adjusted_posts = self.adjust_posts_for_cats(total_posts, cat_posts)
        self._log_adjusted_posts_distribution(adjusted_posts)

        # 6. Analyse du personnel et calcul de la distribution idéale
        personnel_analysis = self.analyze_personnel()
        ideal_distribution = self.analyze_ideal_distribution(adjusted_posts)
        self._log_ideal_distribution(adjusted_posts)

        # 7. Analyse des indisponibilités
        unavailability = self.analyze_unavailability()

        # 8. Distribution des jours
        days_distribution = self._collect_days_distribution()
        
        self._log_analysis_summary(total_posts, cat_posts, adjusted_posts)


        # 9. Analyse des combinaisons - après avoir calculé ideal_distribution
        self.logger.info("\nÉTAPE 4: ANALYSE DES COMBINAISONS")
        combinations_analyzer = CombinationsAnalyzer(
            self.doctors,
            self.cats,
            self.availability_matrix,
            {
                "ideal_distribution": ideal_distribution,
                "weekend_posts": adjusted_posts["saturday"],
                "weekday_posts": adjusted_posts["weekday"],
                "weekend_groups": adjusted_posts["weekend_groups"],
                "weekday_groups": adjusted_posts["weekday_groups"]
            }
        )
        combinations_analysis = combinations_analyzer.analyze()

        return {
            "personnel": personnel_analysis,
            "total_posts": total_posts,
            "cat_posts": cat_posts,
            "adjusted_posts": adjusted_posts,
            "ideal_distribution": ideal_distribution,
            "unavailability": unavailability,
            "days_distribution": days_distribution,
            "combinations_analysis": combinations_analysis
        }

    def _collect_days_distribution(self) -> Dict:
        """Collecte les informations sur la distribution des jours."""
        distribution = {
            'weekdays': [],
            'saturdays': [],
            'sundays': [],
            'holidays': [],
            'bridges': [],
            'specific_dates': {}
        }

        current_date = self.start_date
        while current_date <= self.end_date:
            day_type = DayType.get_day_type(current_date, self.cal)
            
            if day_type == "sunday_holiday":
                if current_date.weekday() == 6:
                    distribution['sundays'].append(current_date)
                elif self.cal.is_holiday(current_date):
                    distribution['holidays'].append(current_date)
                else:  # C'est un pont
                    distribution['bridges'].append(current_date)
            elif day_type == "saturday":
                distribution['saturdays'].append(current_date)
            else:
                distribution['weekdays'].append(current_date)

            # Ajouter les configurations spécifiques
            if hasattr(self.post_configuration, 'specific_configs'):
                for config in self.post_configuration.specific_configs:
                    if config.start_date <= current_date <= config.end_date:
                        if current_date not in distribution['specific_dates']:
                            distribution['specific_dates'][current_date] = []
                        distribution['specific_dates'][current_date].append({
                            'apply_to': config.apply_to,
                            'post_counts': config.post_counts
                        })

            current_date += timedelta(days=1)

        return distribution
    
    def validate_specific_configs(self) -> List[str]:
        """Vérifie la cohérence des configurations spécifiques"""
        errors = []
        
        # Définir le mapping de normalisation des types de jours
        day_type_mapping = {
            "weekday": "Semaine",
            "Semaine": "Semaine",
            "saturday": "Samedi",
            "Samedi": "Samedi",
            "sunday_holiday": "Dimanche/Férié",
            "Dimanche/Férié": "Dimanche/Férié"
        }
        
        grouped_configs = {
            "Semaine": [],
            "Samedi": [],
            "Dimanche/Férié": []
        }

        # Grouper les configurations par type de jour avec normalisation
        for config in self.post_configuration.specific_configs:
            normalized_type = day_type_mapping.get(config.apply_to)
            if normalized_type is None:
                errors.append(f"Type de jour invalide détecté : {config.apply_to}")
                continue
            grouped_configs[normalized_type].append(config)

        # Vérifier les chevauchements dans chaque groupe
        for day_type, configs in grouped_configs.items():
            sorted_configs = sorted(configs, key=lambda x: x.start_date)
            for i in range(len(sorted_configs) - 1):
                current = sorted_configs[i]
                next_config = sorted_configs[i + 1]
                if current.end_date >= next_config.start_date:
                    errors.append(
                        f"Chevauchement détecté pour {day_type} entre : \n"
                        f"  - {current.start_date.strftime('%d/%m/%Y')} → {current.end_date.strftime('%d/%m/%Y')}\n"
                        f"  - {next_config.start_date.strftime('%d/%m/%Y')} → {next_config.end_date.strftime('%d/%m/%Y')}"
                    )

        # Log des erreurs si présentes
        if errors:
            self.logger.error("\nERREURS DE CONFIGURATION SPÉCIFIQUE:")
            for error in errors:
                self.logger.error(error)

        return errors
    def calculate_total_posts(self) -> Dict:
        """Calculate the total number of posts for the entire period based on the configuration."""
        self.logger.info("Calculating total posts to distribute.")
        total_posts = {"weekday": {}, "saturday": {}, "sunday_holiday": {}}
        current_date = self.start_date

        while current_date <= self.end_date:
            day_type = DayType.get_day_type(current_date)
            config = self.post_configuration.get_config_for_day_type(day_type)

            for post_type, post_config in config.items():
                if post_type not in total_posts[day_type]:
                    total_posts[day_type][post_type] = 0
                total_posts[day_type][post_type] += post_config.total

            current_date += timedelta(days=1)

        self.logger.info(f"Total posts calculated: {total_posts}")
        return total_posts
    
    def analyze_cat_posts(self) -> Dict:
        """Calculate the total number of posts reserved for CATs."""
        self.logger.info("Analyzing CAT posts.")
        cat_posts = {"weekday": {}, "saturday": {}, "sunday_holiday": {}}

        for day_type in ["weekday", "saturday", "sunday_holiday"]:
            config = getattr(self.post_configuration, f"cat_{day_type}")
            for post_type, post_config in config.items():
                if post_type not in cat_posts[day_type]:
                    cat_posts[day_type][post_type] = 0
                cat_posts[day_type][post_type] += post_config.total

        self.logger.info(f"CAT posts calculated: {cat_posts}")
        return cat_posts

    

    def analyze_reserved_posts_distribution(self, cat_posts: Dict) -> Dict:
        """Analyse la distribution optimale des postes réservés"""
        total_days = (self.end_date - self.start_date).days + 1
        
        # Calculer le nombre total de postes réservés
        total_reserved = sum(sum(posts.values()) for posts in cat_posts.values())
        
        # Calculer l'espacement optimal
        optimal_spacing = max(1, total_days // total_reserved) if total_reserved > 0 else 1
        
        
        
        return {
            "total_reserved": total_reserved,
            "optimal_spacing": optimal_spacing,
           
        }

    



    def analyze_personnel(self) -> Dict:
        total_doctors = len(self.doctors)
        doctors_one_half_part = sum(1 for doctor in self.doctors if doctor.half_parts == 1)
        doctors_two_half_parts = sum(1 for doctor in self.doctors if doctor.half_parts == 2)
        total_half_parts = sum(doctor.half_parts for doctor in self.doctors)
        total_cats = len(self.cats)

        self.logger.info("EFFECTIFS:")
        self.logger.info(f"Médecins plein temps: {doctors_two_half_parts:2d}")
        self.logger.info(f"Médecins mi-temps  : {doctors_one_half_part:2d}")
        self.logger.info(f"Total parts        : {total_half_parts:2d}")
        self.logger.info("=" * 100)

        return {
            "total_doctors": total_doctors,
            "doctors_one_half_part": doctors_one_half_part,
            "doctors_two_half_parts": doctors_two_half_parts,
            "total_half_parts": total_half_parts,
            "total_cats": total_cats
        }
 
    def analyze_posts(self) -> Dict:
        """Analyse complète des postes sur la période donnée"""
        self.logger.info("\n" + "="*100)
        self.logger.info(f"ANALYSE DES POSTES: {self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')}")
        self.logger.info("="*100)

        # Initialisation des compteurs
        all_possible_posts = set(ALL_POST_TYPES)
        if hasattr(self, 'custom_posts'):
            all_possible_posts.update(self.custom_posts.keys())
            self.logger.debug(f"Postes personnalisés ajoutés à l'analyse: {[p for p in self.custom_posts.keys()]}")
        
        posts_analysis = {
            "weekday": {post_type: 0 for post_type in all_possible_posts},
            "saturday": {post_type: 0 for post_type in all_possible_posts},
            "sunday_holiday": {post_type: 0 for post_type in all_possible_posts},
            "weekend_groups": {
                "CmS": 0, "CmD": 0, "CaSD": 0, "CsSD": 0,
                "VmS": 0, "VmD": 0, "VaSD": 0, "NAMw": 0, "NLw": 0
            },
            "weekday_groups": {
                "XmM": 0, "XM": 0, "XA": 0, "XS": 0,
                "NMC": 0, "Vm": 0, "NL": 0, "NLv": 0
            }
        }

        current_date = self.start_date
        while current_date <= self.end_date:
            day_type = DayType.get_day_type(current_date, self.cal)
            
            normalized_day_type = {
                "weekday": "Semaine",
                "saturday": "Samedi",
                "sunday_holiday": "Dimanche/Férié"
            }.get(day_type)
            
            # Recherche de configuration spécifique
            specific_config = next(
                (sc for sc in self.post_configuration.specific_configs 
                if sc.start_date <= current_date <= sc.end_date 
                and sc.apply_to == normalized_day_type),
                None
            )

            for post_type in all_possible_posts:
                # Déterminer le nombre de postes
                if specific_config and post_type in specific_config.post_counts:
                    post_count = specific_config.post_counts[post_type]
                else:
                    config = getattr(self.post_configuration, day_type)
                    post_count = config.get(post_type, PostConfig()).total

                # Traitement spécial des NL
                if post_type == "NL" and day_type == "weekday":
                    if current_date.weekday() == 4:  # Vendredi
                        posts_analysis["weekday_groups"]["NLv"] += post_count
                        posts_analysis["weekend_groups"]["NLw"] += post_count
                    else:
                        posts_analysis["weekday_groups"]["NL"] += post_count
                    posts_analysis["weekday"][post_type] += post_count
                    
                else:
                    posts_analysis[day_type][post_type] += post_count
                    
                    # Mise à jour des groupes selon le type de poste
                    if post_type in self.custom_posts:
                        custom_post = self.custom_posts[post_type]
                        if custom_post.statistic_group:
                            group = custom_post.statistic_group.strip()
                            if day_type == "weekday" and group in posts_analysis["weekday_groups"]:
                                posts_analysis["weekday_groups"][group] += post_count
                            elif day_type in ["saturday", "sunday_holiday"] and group in posts_analysis["weekend_groups"]:
                                posts_analysis["weekend_groups"][group] += post_count
                                self.logger.debug(f"Groupe {group} mis à jour pour {post_type}: +{post_count}")
                    else:
                        # Postes standards
                        if day_type == "weekday":
                            self._update_weekday_group_counts(posts_analysis["weekday_groups"], post_type, post_count)
                        else:
                            self._update_weekend_group_counts(posts_analysis["weekend_groups"], post_type, post_count, day_type, current_date)

            current_date += timedelta(days=1)

        # Log des résultats
        self.logger.info("\nTOTAL DES POSTES PAR TYPE:")
        self.logger.info("\nWEEKDAY:")
        nl_count = posts_analysis["weekday_groups"]["NL"]
        nlv_count = posts_analysis["weekday_groups"]["NLv"]
        self.logger.info(f"NL (lundi-jeudi) : {nl_count:3d}")
        self.logger.info(f"NLv (vendredi)   : {nlv_count:3d}")
        self.logger.info(f"Total NL semaine : {nl_count + nlv_count:3d}")

        # Log des postes de semaine
        for post_type, count in sorted(posts_analysis["weekday"].items()):
            if count > 0 and post_type != "NL":
                if post_type in self.custom_posts:
                    self.logger.info(f"{post_type:4}: {count:3d} (Personnalisé)")
                else:
                    self.logger.info(f"{post_type:4}: {count:3d}")

        # Log des postes de weekend
        if any(posts_analysis["saturday"].values()) or any(posts_analysis["sunday_holiday"].values()):
            self.logger.info("\nPOSTES WEEKEND:")
            for post_type in all_possible_posts:
                total = posts_analysis["saturday"].get(post_type, 0) + posts_analysis["sunday_holiday"].get(post_type, 0)
                if total > 0:
                    if post_type in self.custom_posts:
                        self.logger.info(f"{post_type:4}: {total:3d} (Personnalisé)")
                    else:
                        self.logger.info(f"{post_type:4}: {total:3d}")

        self.logger.info("\nGROUPES WEEKEND:")
        for group, count in posts_analysis["weekend_groups"].items():
            if count > 0:
                self.logger.info(f"{group:6}: {count:3d}")

        self.logger.info("\nGROUPES SEMAINE:")
        for group, count in posts_analysis["weekday_groups"].items():
            if count > 0:
                self.logger.info(f"{group:6}: {count:3d}")

        return posts_analysis
    def calculate_cat_group_count(self, group: str, cat_posts: Dict) -> int:
        """Calcule le nombre de postes CAT pour un groupe donné"""
        total = 0
        
        # Définition des mappings de postes pour chaque groupe
        group_mappings = {
            # Groupes Weekend (uniquement samedi et dimanche/férié)
            "CmS": ["CM", "HM","SM", "RM", "MM"],  # Uniquement samedi
            "CmD": ["CM", "HM", "SM", "RM"],  # Uniquement dimanche
            "CaSD": ["CA", "HA", "SA", "RA"],  # Samedi + Dimanche
            "CsSD": ["CS", "HS", "SS", "RS"],  # Samedi + Dimanche
            "VmS": ["ML","MC"],  # Uniquement samedi
            "VmD": ["ML", "MC"],  # Uniquement dimanche
            "VaSD": ["AL", "AC"],  # Samedi + Dimanche
            "NAMw": ["NM", "NA", "NC"],  # Samedi + Dimanche
            "NLw": ["NL"],  # NLw = NLs + NLd + NLv
            
            # Groupes Semaine (uniquement weekday)
            "XmM": ["MM", "SM", "RM"],
            "XM": ["CM", "HM"],
            "XA": ["CA", "HA", "SA","RA","CT"],
            "XS": ["CS", "HS", "SS", "RS"],
            "NMC": ["NM", "NC","NA"],
            "Vm": ["ML", "MC"],
            "NL": ["NL"],
            "NLv": ["NL"]
        }
        
        if group in group_mappings:
            if group == "NLw":
                # NLs + NLd + NLv
                total = (
                    cat_posts["saturday"].get("NL", 0) +          # NLs
                    cat_posts["sunday_holiday"].get("NL", 0) +    # NLd
                    cat_posts["weekday"].get("NLv", 0)           # NLv
                )
            elif group in ["CmS", "VmS"]:
                # Groupes uniquement samedi
                for post_type in group_mappings[group]:
                    total += cat_posts["saturday"].get(post_type, 0)
            elif group in ["CmD", "VmD"]:
                # Groupes uniquement dimanche
                for post_type in group_mappings[group]:
                    total += cat_posts["sunday_holiday"].get(post_type, 0)
            elif group in ["CaSD", "CsSD", "VaSD", "NAMw"]:
                # Groupes samedi + dimanche
                for post_type in group_mappings[group]:
                    total += (cat_posts["saturday"].get(post_type, 0) +
                            cat_posts["sunday_holiday"].get(post_type, 0))
            else:
                # Groupes semaine (uniquement weekday)
                for post_type in group_mappings[group]:
                    total += cat_posts["weekday"].get(post_type, 0)
        
        return total
    def _update_weekend_group_counts(self, groups: Dict, post_type: str, count: int, day_type: str, current_date: date):
        """
        Met à jour les compteurs de groupes pour le weekend.
        Les jours de pont sont traités comme des fériés, même les samedis.
        """
        is_bridge = self.is_bridge_day(current_date)
        is_holiday = self.cal.is_holiday(current_date)
        is_sunday = current_date.weekday() == 6
        
        # Un samedi qui est un jour de pont est traité comme un férié
        is_saturday = day_type == "saturday" and not (is_bridge or is_holiday)
        is_sunday_or_holiday = (day_type == "sunday_holiday" or is_bridge or is_holiday or is_sunday)

        # Gestion des postes personnalisés
        if post_type in self.custom_posts:
            custom_post = self.custom_posts[post_type]
            if custom_post.statistic_group:
                if custom_post.statistic_group in ["CmS", "VmS"] and is_saturday:
                    groups[custom_post.statistic_group] += count
                elif custom_post.statistic_group in ["CmD", "VmD"] and is_sunday_or_holiday:
                    groups[custom_post.statistic_group] += count
                elif custom_post.statistic_group in ["CaSD", "CsSD", "VaSD", "NAMw", "NLw"]:
                    groups[custom_post.statistic_group] += count
            return

        # Gestion des postes standards
        if post_type in ["MM", "CM", "HM", "SM", "RM"]:
            if is_saturday:
                groups["CmS"] += count
            elif is_sunday_or_holiday:
                groups["CmD"] += count
        elif post_type in ["CA", "HA", "SA", "RA"]:
            groups["CaSD"] += count
        elif post_type in ["CS", "HS", "SS", "RS"]:
            groups["CsSD"] += count
        elif post_type == "ML":
            if is_saturday:
                groups["VmS"] += count
            elif is_sunday_or_holiday:
                groups["VmD"] += count
        elif post_type == "MC":
            if is_sunday_or_holiday:
                groups["VmD"] += count
        elif post_type in ["AL", "AC"]:
            groups["VaSD"] += count
        elif post_type in ["NM", "NA"]:
            groups["NAMw"] += count
        elif post_type == "NL":  # NLw inclut maintenant NLv + NLs + NLd
            groups["NLw"] += count

    def _update_weekday_group_counts(self, groups: Dict, post_type: str, count: int):
        """Met à jour les compteurs de groupes pour la semaine"""
        if post_type in self.custom_posts:
            custom_post = self.custom_posts[post_type]
            period = self.get_post_period(custom_post.start_time, custom_post.end_time)
            
            statistic_group = custom_post.statistic_group
            
            if statistic_group:
                if period == 0:  # Matin
                    if statistic_group == "XmM":
                        groups["XmM"] += count
                    elif statistic_group == "XM":
                        groups["XM"] += count
                    elif statistic_group == "Vm":
                        groups["Vm"] += count
                elif period == 1:  # Après-midi
                    if statistic_group == "XA":
                        groups["XA"] += count
                elif period == 2:  # Soir
                    if statistic_group == "XS":
                        groups["XS"] += count
                    elif statistic_group == "NMC":
                        groups["NMC"] += count
            return

        # Gestion des postes standards
        else:
            period = self.get_post_period_static(post_type)
        if post_type in ["MM", "SM", "RM"]:
            groups["XmM"] += count
        elif post_type in ["CM", "HM"]:
            groups["XM"] += count
        elif post_type in ["CA", "HA", "SA", "RA","CT"]:
            groups["XA"] += count
        elif post_type in ["CS", "HS", "SS", "RS"]:
            groups["XS"] += count
        elif post_type in ["ML", "MC"]:
            groups["Vm"] += count
        elif post_type in ["NM", "NC", "NA"]:
            groups["NMC"] += count

    def _update_cat_groups(self, cat_posts: Dict):
        """Met à jour les groupes pour les postes CAT"""
        # Groupes de semaine
        cat_posts["weekday_groups"]["XmM"] = cat_posts["weekday"]["MM"] + cat_posts["weekday"]["SM"]
        cat_posts["weekday_groups"]["XM"] = cat_posts["weekday"]["CM"] + cat_posts["weekday"]["HM"]
        cat_posts["weekday_groups"]["XA"] = cat_posts["weekday"]["CA"] + cat_posts["weekday"]["HA"]
        cat_posts["weekday_groups"]["XS"] = cat_posts["weekday"]["CS"] + cat_posts["weekday"]["HS"]
        cat_posts["weekday_groups"]["NMC"] = cat_posts["weekday"]["NM"] + cat_posts["weekday"]["NC"]
        cat_posts["weekday_groups"]["Vm"] = cat_posts["weekday"]["ML"] + cat_posts["weekday"]["MC"]

        # Groupes de weekend
        weekend_nl = cat_posts["saturday"]["NL"] + cat_posts["sunday_holiday"]["NL"]
        cat_posts["weekend_groups"]["NLw"] = weekend_nl

        cat_posts["weekend_groups"]["CmS"] = cat_posts["saturday"]["CM"] + cat_posts["saturday"]["HM"] + cat_posts["saturday"]["MM"]
        cat_posts["weekend_groups"]["CmD"] = (cat_posts["sunday_holiday"]["CM"] + 
                                            cat_posts["sunday_holiday"]["HM"] + 
                                            cat_posts["sunday_holiday"]["SM"] + 
                                            cat_posts["sunday_holiday"]["RM"])

        weekend_ca = (cat_posts["saturday"]["CA"] + cat_posts["saturday"]["HA"] +
                    cat_posts["sunday_holiday"]["CA"] + cat_posts["sunday_holiday"]["HA"])
        cat_posts["weekend_groups"]["CaSD"] = weekend_ca

        weekend_cs = (cat_posts["saturday"]["CS"] + cat_posts["saturday"]["HS"] +
                    cat_posts["sunday_holiday"]["CS"] + cat_posts["sunday_holiday"]["HS"])
        cat_posts["weekend_groups"]["CsSD"] = weekend_cs

        cat_posts["weekend_groups"]["VmS"] = cat_posts["saturday"]["ML"]
        cat_posts["weekend_groups"]["VmD"] = cat_posts["sunday_holiday"]["ML"] + cat_posts["sunday_holiday"]["MC"]
        
        weekend_va = (cat_posts["saturday"]["AL"] + cat_posts["saturday"]["AC"] +
                    cat_posts["sunday_holiday"]["AL"] + cat_posts["sunday_holiday"]["AC"])
        cat_posts["weekend_groups"]["VaSD"] = weekend_va

        weekend_nam = (cat_posts["saturday"]["NA"] + cat_posts["saturday"]["NM"] +
                    cat_posts["sunday_holiday"]["NA"] + cat_posts["sunday_holiday"]["NM"])
        cat_posts["weekend_groups"]["NAMw"] = weekend_nam

    
    
    
    def _log_days_distribution(self):
        """Log la répartition des jours sur la période"""
        details = {
            'weekdays': [],
            'saturdays': [],
            'sundays': [],
            'holidays': [],
            'bridges': [],
            'sunday_holiday_total': [],  # Pour compter tous les jours traités comme dimanche/férié
            'saturday_bridges': [],  # Samedis de pont spécifiquement
            'specific_configs': []
        }

        # Analyser d'abord les configurations spécifiques
        if hasattr(self.post_configuration, 'specific_configs'):
            for config in self.post_configuration.specific_configs:
                start = max(config.start_date, self.start_date)
                end = min(config.end_date, self.end_date)
                
                # Compter les jours spécifiques
                matching_days = 0
                current_date = start
                while current_date <= end:
                    counts_as_match = False
                    
                    if config.apply_to == "Semaine":
                        if current_date.weekday() < 5 and not self.cal.is_holiday(current_date) and not self.is_bridge_day(current_date):
                            counts_as_match = True
                    elif config.apply_to == "Samedi":
                        if current_date.weekday() == 5 and not self.cal.is_holiday(current_date) and not self.is_bridge_day(current_date):
                            counts_as_match = True
                    elif config.apply_to == "Dimanche/Férié":
                        if current_date.weekday() == 6 or self.cal.is_holiday(current_date) or self.is_bridge_day(current_date):
                            counts_as_match = True
                    
                    if counts_as_match:
                        matching_days += 1
                    current_date += timedelta(days=1)

                details['specific_configs'].append({
                    'start_date': config.start_date,
                    'end_date': config.end_date,
                    'apply_to': config.apply_to,
                    'posts': config.post_counts,
                    'matching_days': matching_days
                })

        # Collecte des jours normaux
        current_date = self.start_date
        while current_date <= self.end_date:
            if DayType.is_bridge_day(current_date, self.cal):
                details['bridges'].append(current_date)
                details['sunday_holiday_total'].append(current_date)
                if current_date.weekday() == 5:
                    details['saturday_bridges'].append(current_date)
            elif self.cal.is_holiday(current_date):
                details['holidays'].append(current_date)
                details['sunday_holiday_total'].append(current_date)
            elif current_date.weekday() == 6:  # Dimanche
                details['sundays'].append(current_date)
                details['sunday_holiday_total'].append(current_date)
            elif current_date.weekday() == 5 and not self.is_bridge_day(current_date):  # Samedi normal
                details['saturdays'].append(current_date)
            else:
                details['weekdays'].append(current_date)

            current_date += timedelta(days=1)

        # Affichage standard
        self.logger.info("\nDÉTAIL DES JOURS")
        self.logger.info("="*80)
        self.logger.info(f"Jours de semaine      : {len(details['weekdays']):3d}")
        self.logger.info(f"Samedis normaux       : {len(details['saturdays']):3d}")
        self.logger.info("\nJOURS TRAITÉS COMME DIMANCHE/FÉRIÉ:")
        self.logger.info(f"Dimanches             : {len(details['sundays']):3d}")
        self.logger.info(f"Jours fériés          : {len(details['holidays']):3d}")
        self.logger.info(f"Jours de pont         : {len(details['bridges']):3d}")
        self.logger.info(f"   dont samedis       : {len(details['saturday_bridges']):3d}")
        self.logger.info(f"TOTAL Dim/Férié/Pont  : {len(details['sunday_holiday_total']):3d}")

        # Affichage des configurations spécifiques
        if details['specific_configs']:
            self.logger.info("\nCONFIGURATIONS SPÉCIFIQUES:")
            self.logger.info("-"*80)
            for config in details['specific_configs']:
                # Formatage des postes prévus
                posts_detail = ", ".join([f"{count}{post}" for post, count in config['posts'].items()])
                
                self.logger.info(
                    f"* du {config['start_date'].strftime('%d/%m/%Y')} "
                    f"au {config['end_date'].strftime('%d/%m/%Y')} "
                    f"- {config['apply_to']} : {len(config['posts'])} postes "
                    f"({posts_detail})"
                )
                self.logger.info(f"  → {config['matching_days']} jours concernés")

        self.logger.info("-"*80)
        self.logger.info(f"Total jours période   : {self.total_days:3d}")

        self.logger.info("="*80)
        
    def _log_total_posts_distribution(self, total_posts: Dict):
        self.logger.info("\nDISTRIBUTION TOTALE DES POSTES")
        self.logger.info("=" * 80)
        # Affichage détaillé des postes par type de jour
    
    def _log_cat_posts_distribution(self, cat_posts: Dict):
        self.logger.info("\nDISTRIBUTION DES POSTES CAT")
        self.logger.info("=" * 80)
        # Affichage des postes réservés aux CAT

    def _log_adjusted_posts_distribution(self, adjusted_posts: Dict):
        """Affiche les détails de la distribution ajustée pour les médecins"""
        self.logger.info("\nDISTRIBUTION AJUSTÉE POUR LES MÉDECINS")
        self.logger.info("=" * 80)
        total_half_parts = sum(doctor.half_parts for doctor in self.doctors)

        # Postes de semaine
        self.logger.info("\nWEEKDAY:")
        self.logger.info("-" * 60)
        header = f"{'Type':<6} {'Total':<8} {'Plein temps (min-max)':<25} {'Mi-temps (min-max)':<25}"
        self.logger.info(header)
        
        for post_type, count in sorted(adjusted_posts["weekday"].items()):
            if count > 0:
                full_time_range = self.round_ideal(count, 2)
                half_time_range = self.round_ideal(count, 1)
                self.logger.info(
                    f"{post_type:<6} {count:>8} "
                    f"[{full_time_range['min']:>2}-{full_time_range['max']:<2}]"
                    f"{' '*15}"
                    f"[{half_time_range['min']:>2}-{half_time_range['max']:<2}]"
                )

        # Postes de samedi et dimanche séparément
        for day_type in ["saturday", "sunday_holiday"]:
            day_name = "SATURDAY:" if day_type == "saturday" else "SUNDAY/HOLIDAY:"
            self.logger.info(f"\n{day_name}")
            self.logger.info("-" * 60)
            self.logger.info(header)
            
            for post_type, count in sorted(adjusted_posts[day_type].items()):
                if count > 0:
                    full_time_range = self.round_ideal(count, 2)
                    half_time_range = self.round_ideal(count, 1)
                    self.logger.info(
                        f"{post_type:<6} {count:>8} "
                        f"[{full_time_range['min']:>2}-{full_time_range['max']:<2}]"
                        f"{' '*15}"
                        f"[{half_time_range['min']:>2}-{half_time_range['max']:<2}]"
                    )

        # Groupes de semaine
        self.logger.info("\nGROUPES SEMAINE:")
        self.logger.info("-" * 60)
        self.logger.info(header)
        
        for group, count in adjusted_posts["weekday_groups"].items():
            if count > 0:
                full_time_range = self.round_ideal(count, 2)
                half_time_range = self.round_ideal(count, 1)
                self.logger.info(
                    f"{group:<6} {count:>8} "
                    f"[{full_time_range['min']:>2}-{full_time_range['max']:<2}]"
                    f"{' '*15}"
                    f"[{half_time_range['min']:>2}-{half_time_range['max']:<2}]"
                )

        # Groupes weekend (fusion des groupes samedi et dimanche)
        self.logger.info("\nGROUPES WEEKEND:")
        self.logger.info("-" * 60)
        self.logger.info(header)
        
        weekend_groups = adjusted_posts["weekend_groups"]
        # Correction du calcul de NLw
        weekend_groups["NLw"] = (
            adjusted_posts["saturday"].get("NL", 0) +  # NLs
            adjusted_posts["sunday_holiday"].get("NL", 0) +  # NLd
            adjusted_posts["weekday_groups"].get("NLv", 0)  # NLv
        )
        
        for group, count in weekend_groups.items():
            if count > 0:
                full_time_range = self.round_ideal(count, 2)
                half_time_range = self.round_ideal(count, 1)
                self.logger.info(
                    f"{group:<6} {count:>8} "
                    f"[{full_time_range['min']:>2}-{full_time_range['max']:<2}]"
                    f"{' '*15}"
                    f"[{half_time_range['min']:>2}-{half_time_range['max']:<2}]"
                )

    def _log_ideal_distribution(self, adjusted_posts: Dict):
        """Affiche la distribution idéale des postes par type de médecin"""
        total_half_parts = sum(doctor.half_parts for doctor in self.doctors)
        full_time_count = sum(1 for d in self.doctors if d.half_parts == 2)
        half_time_count = sum(1 for d in self.doctors if d.half_parts == 1)

        self.logger.info("\nDISTRIBUTION IDÉALE PAR MÉDECIN TYPE")
        self.logger.info("=" * 100)

        # En-tête avec le nombre de médecins
        self.logger.info(f"Nombre de médecins plein temps: {full_time_count}")
        self.logger.info(f"Nombre de médecins mi-temps: {half_time_count}")
        self.logger.info(f"Total demi-parts: {total_half_parts}")
        self.logger.info("")

        header = "{:<8} {:<10} {:<25} {:<25}".format(
            "Type", "Total", "Plein temps", "Mi-temps"
        )

        def log_section(title: str, items: Dict[str, int]):
            """Affiche une section des résultats"""
            self.logger.info(f"\n{title}")
            self.logger.info("-" * 100)
            self.logger.info(header)
            self.logger.info("-" * 100)

            for post_type, total in sorted(items.items()):
                if total > 0:
                    # Utiliser round_ideal pour les deux calculs
                    full_time_range = self.round_ideal(total, 2)
                    half_time_range = self.round_ideal(total, 1)

                    self.logger.info("{:<8} {:<10.1f} [{:>2d}-{:<2d}] ({:.1f})           [{:>2d}-{:<2d}] ({:.1f})".format(
                        post_type,
                        total,
                        full_time_range['min'], full_time_range['max'], full_time_range['target'],
                        half_time_range['min'], half_time_range['max'], half_time_range['target']
                    ))

        # Gardes de nuit semaine
        night_posts = {
            "NL": adjusted_posts["weekday"]["NL"],
            "NLv": adjusted_posts["weekday_groups"]["NLv"]
        }
        log_section("GARDES DE NUIT SEMAINE", night_posts)

        # Autres postes semaine
        weekday_posts = {
            k: v for k, v in adjusted_posts["weekday"].items() 
            if k not in ["NL", "NLv"]
        }
        log_section("AUTRES POSTES SEMAINE", weekday_posts)

        # Groupes semaine
        weekday_groups = {
            k: v for k, v in adjusted_posts["weekday_groups"].items() 
            if k not in ["NL", "NLv"]
        }
        log_section("GROUPES SEMAINE", weekday_groups)

        # Postes weekend
        weekend_posts = {}
        for post_type in set(list(adjusted_posts["saturday"].keys()) + 
                            list(adjusted_posts["sunday_holiday"].keys())):
            total = (adjusted_posts["saturday"].get(post_type, 0) + 
                    adjusted_posts["sunday_holiday"].get(post_type, 0))
            if total > 0:
                weekend_posts[post_type] = total
        log_section("POSTES WEEKEND", weekend_posts)

        # Groupes weekend
        log_section("GROUPES WEEKEND", adjusted_posts["weekend_groups"])
    
        
    def _log_weekend_posts(self, total_posts: Dict, total_parts: int):
        """Affiche les statistiques des postes du weekend"""
        self.logger.info("\nPOSTES WEEKEND")
        self.logger.info("="*80)
        header = f"{'Type':<6} {'Total':<8} {'Plein temps (min-max)':<20} {'Mi-temps (min-max)':<20}"
        self.logger.info(header)
        
        for day_type in ["saturday", "sunday_holiday"]:
            self.logger.info(f"\n{day_type.upper()}:")
            self.logger.info("-"*80)
            
            for post_type, count in sorted(total_posts[day_type].items()):
                if count > 0:
                    full_time, half_time = self._calculate_ranges(count, total_parts)
                    self.logger.info(
                        f"{post_type:<6} {count:<8} "
                        f"[{full_time['min']}-{full_time['max']}]"
                        f"{' '*8}"
                        f"[{half_time['min']}-{half_time['max']}]"
                    )

    def _log_weekend_groups(self, groups: Dict, total_parts: int):
        """Affiche les statistiques des groupes du weekend"""
        self.logger.info("\nGROUPES WEEKEND")
        self.logger.info("="*80)
        header = f"{'Groupe':<6} {'Total':<8} {'Plein temps (min-max)':<20} {'Mi-temps (min-max)':<20}"
        self.logger.info(header)
        self.logger.info("-"*80)
        
        for group, count in sorted(groups.items()):
            if count > 0:
                full_time, half_time = self._calculate_ranges(count, total_parts)
                self.logger.info(
                    f"{group:<6} {count:<8} "
                    f"[{full_time['min']}-{full_time['max']}]"
                    f"{' '*8}"
                    f"[{half_time['min']}-{half_time['max']}]"
                )

    def _log_weekday_distribution(self, weekday_posts: Dict, weekday_groups: Dict, total_parts: int):
        """Affiche les statistiques des postes et groupes de semaine"""
        self.logger.info("\nDISTRIBUTION SEMAINE")
        self.logger.info("="*80)
        header = f"{'Type':<6} {'Total':<8} {'Plein temps (min-max)':<20} {'Mi-temps (min-max)':<20}"
        self.logger.info(header)
        
        self.logger.info("\nPOSTES:")
        self.logger.info("-"*80)
        for post_type, count in sorted(weekday_posts.items()):
            if count > 0:
                full_time, half_time = self._calculate_ranges(count, total_parts)
                self.logger.info(
                    f"{post_type:<6} {count:<8} "
                    f"[{full_time['min']}-{full_time['max']}]"
                    f"{' '*8}"
                    f"[{half_time['min']}-{half_time['max']}]"
                )
        
        self.logger.info("\nGROUPES:")
        self.logger.info("-"*80)
        for group, count in sorted(weekday_groups.items()):
            if count > 0:
                full_time, half_time = self._calculate_ranges(count, total_parts)
                self.logger.info(
                    f"{group:<6} {count:<8} "
                    f"[{full_time['min']}-{full_time['max']}]"
                    f"{' '*8}"
                    f"[{half_time['min']}-{half_time['max']}]"
                )




    def is_bridge_day(self, day: date) -> bool:
        return DayType.is_bridge_day(day, self.cal)

    def get_post_period(self, start_time: time, end_time: time) -> int:
        """
        Détermine la période d'un poste basé sur ses horaires.
        Retourne:
            0: Matin (7h-13h)
            1: Après-midi (13h-18h)
            2: Soir (18h-7h)
        """
        # Si le poste traverse minuit
        if end_time < start_time:
            hours_range = list(range(start_time.hour, 24)) + list(range(0, end_time.hour + 1))
        else:
            hours_range = list(range(start_time.hour, end_time.hour + 1))
        
        # Compte les heures dans chaque période
        morning_hours = sum(1 for h in hours_range if 7 <= (h % 24) < 13)
        afternoon_hours = sum(1 for h in hours_range if 13 <= (h % 24) < 18)
        evening_hours = sum(1 for h in hours_range if (h % 24) >= 18 or (h % 24) < 7)
        
        # Retourne la période avec le plus d'heures
        max_hours = max(morning_hours, afternoon_hours, evening_hours)
        if max_hours == morning_hours:
            return 0
        elif max_hours == afternoon_hours:
            return 1
        else:
            return 2

    def get_post_period_static(self, post_type: str) -> int:
        """
        Détermine la période d'un poste standard basé sur son type.
        Retourne:
            0: Matin (ML, MC, MM, CM, HM, SM, RM)
            1: Après-midi (CA, HA, SA, RA, AL, AC)
            2: Soir (autres)
        """
        if post_type in ["ML", "MC", "MM", "CM", "HM", "SM", "RM"]:
            return 0
        elif post_type in ["CA", "HA", "SA", "RA", "AL", "AC"]:
            return 1
        else:
            return 2
        
    def overlaps(self, desiderata: Desiderata, start: date, end: date) -> bool:
        """Vérifie si une période de desiderata chevauche une période donnée"""
        return max(desiderata.start_date, start) <= min(desiderata.end_date, end)

    def analyze_unavailability(self) -> Dict:
        """
        Analyse les indisponibilités des médecins sur la période.
        Distingue les desiderata primaires (stricts) et secondaires (souples).
        """
        unavailability = {}
        daily_availability = {
            (self.start_date + timedelta(days=i)): {
                "primary": 0,
                "secondary": 0,
                "total": 0
            } for i in range((self.end_date - self.start_date).days + 1)
        }
        
        total_days = (self.end_date - self.start_date).days + 1
        total_periods = total_days * 3  # 3 périodes par jour

        self.logger.info(f"Analyzing unavailability for {len(self.doctors)} doctors over {total_days} days ({total_periods} total periods)")

        for doctor in self.doctors:
            # Initialisation des compteurs par type
            primary_periods = 0
            secondary_periods = 0
            
            for desiderata in doctor.desiderata:
                if self.overlaps(desiderata, self.start_date, self.end_date):
                    start = max(desiderata.start_date, self.start_date)
                    end = min(desiderata.end_date, self.end_date)
                    days = (end - start).days + 1
                    
                    # Détermination du type de desiderata (rétrocompatibilité)
                    priority = getattr(desiderata, 'priority', 'primary')
                    
                    # Mise à jour des compteurs selon le type
                    if priority == "primary":
                        primary_periods += days
                    else:  # secondary
                        secondary_periods += days
                    
                    # Mise à jour du compteur quotidien
                    for day in (start + timedelta(n) for n in range(days)):
                        daily_availability[day][priority] += 1
                        daily_availability[day]["total"] += 1

            # Calcul des pourcentages pour chaque type
            total_periods_unavailable = primary_periods + secondary_periods
            raw_primary = round((primary_periods / total_periods) * 100, 2)
            raw_secondary = round((secondary_periods / total_periods) * 100, 2)
            raw_total = round((total_periods_unavailable / total_periods) * 100, 2)
            
            # Ajustement pour les mi-temps
            if doctor.half_parts == 1:
                adjusted_primary = round(raw_primary / 2, 2)
                adjusted_secondary = round(raw_secondary / 2, 2)
                adjusted_total = round(raw_total / 2, 2)
                
                unavailability[doctor.name] = {
                    "primary": {
                        "raw": raw_primary,
                        "adjusted": adjusted_primary,
                        "periods": primary_periods
                    },
                    "secondary": {
                        "raw": raw_secondary,
                        "adjusted": adjusted_secondary,
                        "periods": secondary_periods
                    },
                    "total": {
                        "raw": raw_total,
                        "adjusted": adjusted_total,
                        "periods": total_periods_unavailable
                    },
                    "is_half_time": True
                }
                
                self.logger.debug(
                    f"Doctor {doctor.name} (mi-temps):\n"
                    f"  Primary: {primary_periods} périodes ({raw_primary}% brut, {adjusted_primary}% ajusté)\n"
                    f"  Secondary: {secondary_periods} périodes ({raw_secondary}% brut, {adjusted_secondary}% ajusté)\n"
                    f"  Total: {total_periods_unavailable} périodes ({raw_total}% brut, {adjusted_total}% ajusté)")
            else:
                unavailability[doctor.name] = {
                    "primary": {
                        "raw": raw_primary,
                        "adjusted": raw_primary,
                        "periods": primary_periods
                    },
                    "secondary": {
                        "raw": raw_secondary,
                        "adjusted": raw_secondary,
                        "periods": secondary_periods
                    },
                    "total": {
                        "raw": raw_total,
                        "adjusted": raw_total,
                        "periods": total_periods_unavailable
                    },
                    "is_half_time": False
                }
                
                self.logger.debug(
                    f"Doctor {doctor.name}:\n"
                    f"  Primary: {primary_periods} périodes ({raw_primary}%)\n"
                    f"  Secondary: {secondary_periods} périodes ({raw_secondary}%)\n"
                    f"  Total: {total_periods_unavailable} périodes ({raw_total}%)")

        # Tri des médecins par pourcentage total d'indisponibilité
        sorted_unavailability = sorted(
            unavailability.items(),
            key=lambda x: x[1]["total"]["raw"],
            reverse=True
        )

        # Log détaillé des résultats
        self.logger.info("\nINDISPONIBILITÉS DES MÉDECINS:")
        self.logger.info("-" * 80)
        for doctor_name, data in sorted_unavailability:
            if data["is_half_time"]:
                self.logger.info(
                    f"{doctor_name:<15}: "
                    f"Primaire: {data['primary']['raw']:>5.2f}% ({data['primary']['adjusted']:>5.2f}% ajusté), "
                    f"Secondaire: {data['secondary']['raw']:>5.2f}% ({data['secondary']['adjusted']:>5.2f}% ajusté), "
                    f"Total: {data['total']['raw']:>5.2f}% ({data['total']['adjusted']:>5.2f}% ajusté)"
                )
            else:
                self.logger.info(
                    f"{doctor_name:<15}: "
                    f"Primaire: {data['primary']['raw']:>5.2f}%, "
                    f"Secondaire: {data['secondary']['raw']:>5.2f}%, "
                    f"Total: {data['total']['raw']:>5.2f}%"
                )

        # Identification des jours critiques
        least_available_days = sorted(
            [(day, counts) for day, counts in daily_availability.items()],
            key=lambda x: x[1]["total"],
            reverse=True
        )[:5]

        self.logger.info("\nJOURS LES PLUS CRITIQUES:")
        self.logger.info("-" * 80)
        for day, counts in least_available_days:
            self.logger.info(
                f"{day.strftime('%d/%m/%Y')} : "
                f"{counts['total']} médecins indisponibles "
                f"(Primaire: {counts['primary']}, Secondaire: {counts['secondary']})"
            )

        return {
            "doctor_unavailability": unavailability,
            "least_available_days": least_available_days
        }

    def analyze_ideal_distribution(self, adjusted_posts: Dict) -> Dict:
        """Calcule la distribution idéale des postes et groupes pour chaque médecin"""
        ideal_distribution = {}
        total_half_parts = sum(doctor.half_parts for doctor in self.doctors)

        for doctor in self.doctors:
            ideal_distribution[doctor.name] = {
                "weekday_posts": {},
                "weekend_posts": {},
                "weekday_groups": {},
                "weekend_groups": {}
            }

            # Traitement des postes de semaine
            for post_type, total in adjusted_posts["weekday"].items():
                if total > 0:
                    # Calcul du nombre idéal pour ce médecin
                    posts_per_half_part = total / total_half_parts
                    target_value = posts_per_half_part * doctor.half_parts

                    # Utiliser la logique de 0.3 pour les mi-temps uniquement
                    if doctor.half_parts == 1:
                        decimal_part = target_value - math.floor(target_value)
                        if decimal_part < 0.3:
                            min_val = max_val = math.floor(target_value)
                        else:
                            min_val = math.floor(target_value)
                            max_val = math.ceil(target_value)
                    else:
                        # Pour les temps pleins, garder la logique standard
                        min_val = math.floor(target_value)
                        max_val = math.ceil(target_value)

                    ideal_distribution[doctor.name]["weekday_posts"][post_type] = {
                        "min": min_val,
                        "max": max_val,
                        "target": target_value
                    }

            # Traitement des postes de weekend
            for post_type, total in adjusted_posts.get("saturday", {}).items():
                weekend_total = (total + adjusted_posts["sunday_holiday"].get(post_type, 0))
                if weekend_total > 0:
                    posts_per_half_part = weekend_total / total_half_parts
                    target_value = posts_per_half_part * doctor.half_parts

                    # Utiliser la logique de 0.3 pour les mi-temps uniquement
                    if doctor.half_parts == 1:
                        decimal_part = target_value - math.floor(target_value)
                        if decimal_part < 0.3:
                            min_val = max_val = math.floor(target_value)
                        else:
                            min_val = math.floor(target_value)
                            max_val = math.ceil(target_value)
                    else:
                        # Pour les temps pleins, garder la logique standard
                        min_val = math.floor(target_value)
                        max_val = math.ceil(target_value)

                    ideal_distribution[doctor.name]["weekend_posts"][post_type] = {
                        "min": min_val,
                        "max": max_val,
                        "target": target_value
                    }

            # Traitement des groupes
            for group_type, groups in [
                ("weekend_groups", ["CmS", "CmD", "CaSD", "CsSD", "VmS", "VmD", "VaSD", "NAMw", "NLw"]),
                ("weekday_groups", ["XmM", "XM", "XA", "XS", "NMC", "Vm", "NL", "NLv"])
            ]:
                for group in groups:
                    total = adjusted_posts.get(group_type.split('_')[0] + "_groups", {}).get(group, 0)
                    if total > 0:
                        posts_per_half_part = total / total_half_parts
                        target_value = posts_per_half_part * doctor.half_parts

                        # Utiliser la logique de 0.3 pour les mi-temps uniquement
                        if doctor.half_parts == 1:
                            decimal_part = target_value - math.floor(target_value)
                            if decimal_part < 0.3:
                                min_val = max_val = math.floor(target_value)
                            else:
                                min_val = math.floor(target_value)
                                max_val = math.ceil(target_value)
                        else:
                            # Pour les temps pleins, garder la logique standard
                            min_val = math.floor(target_value)
                            max_val = math.ceil(target_value)

                        ideal_distribution[doctor.name][group_type][group] = {
                            "min": min_val,
                            "max": max_val,
                            "target": target_value
                        }

        return ideal_distribution

    def _get_combo_groups(self, combo: str) -> List[str]:
        """Retourne les groupes impliqués dans une combinaison"""
        group_mapping = {
            # Premier poste
            "ML": ["VmS", "VmD"],
            "MC": ["VmD"],
            "CM": ["CmS"],
            "HM": ["CmS"],
            "SM": ["CmD"],
            "RM": ["CmD"],
            # Second poste
            "CA": ["CaSD"],
            "HA": ["CaSD"],
            "SA": ["CaSD"],
            "RA": ["CaSD"],
            "CS": ["CsSD"],
            "HS": ["CsSD"],
            "SS": ["CsSD"],
            "RS": ["CsSD"],
            "AL": ["VaSD"],
            "AC": ["VaSD"],
            "NA": ["NAMw"]
        }
        
        first_post = combo[:2]
        second_post = combo[2:]
        
        groups = set()
        if first_post in group_mapping:
            groups.update(group_mapping[first_post])
        if second_post in group_mapping:
            groups.update(group_mapping[second_post])
            
        return list(groups)

    def _calculate_combo_total(self, combo: str, adjusted_posts: Dict) -> int:
        """Calcule le total possible pour une combinaison"""
        first_post = combo[:2]
        second_post = combo[2:]
        
        first_total = (
            adjusted_posts["saturday"].get(first_post, 0) +
            adjusted_posts["sunday_holiday"].get(first_post, 0)
        )
        second_total = (
            adjusted_posts["saturday"].get(second_post, 0) +
            adjusted_posts["sunday_holiday"].get(second_post, 0)
        )
        
        return min(first_total, second_total)
    def _calculate_combo_base_value(self, combo: str, adjusted_posts: Dict, half_parts: int) -> float:
        """Calcule la valeur de base pour une combinaison"""
        # Trouver les postes constituant la combinaison
        first_post, second_post = combo[:2], combo[2:]
        
        # Calculer le total disponible
        total_first = (
            adjusted_posts["saturday"].get(first_post, 0) +
            adjusted_posts["sunday_holiday"].get(first_post, 0)
        )
        total_second = (
            adjusted_posts["saturday"].get(second_post, 0) +
            adjusted_posts["sunday_holiday"].get(second_post, 0)
        )
        
        total_combo = min(total_first, total_second)
        total_half_parts = sum(doctor.half_parts for doctor in self.doctors)
        
        # Retourne la valeur proportionnelle aux demi-parts
        return total_combo * (half_parts / total_half_parts)
    
    def adjust_posts_for_cats(self, total_posts_analysis: Dict, cat_posts: Dict) -> Dict:
        """Ajuste les totaux de postes en soustrayant les postes CAT, avec chaque CAT recevant son quota complet"""
        self.logger.info("\nAjustement des postes pour les médecins")
        
        # Nombre de CAT
        num_cats = len(self.cats)
        
        # Initialisation des dictionnaires de résultats
        adjusted_posts = {
            "weekday": {},
            "saturday": {},
            "sunday_holiday": {},
            "weekend_groups": {},
            "weekday_groups": {}
        }
        
        # 1. Ajustement des postes de semaine
        self.logger.info("\nAJUSTEMENT POSTES SEMAINE:")
        for post_type in total_posts_analysis["weekday"]:
            if post_type not in ["NL", "NLv"]:  # Traitement spécial pour NL/NLv
                total_count = total_posts_analysis["weekday"].get(post_type, 0)
                cat_count = cat_posts["weekday"].get(post_type, 0)
                cat_total = cat_count * num_cats  # Multiplier par le nombre de CAT
                adjusted_count = max(0, total_count - cat_total)
                adjusted_posts["weekday"][post_type] = adjusted_count
                if total_count > 0 or cat_count > 0:
                    self.logger.info(f"{post_type:4}: Total={total_count:3d}, CAT={cat_count:2d} x {num_cats} = {cat_total:2d}, Ajusté={adjusted_count:3d}")

        # 2. Ajustement spécial pour NL et NLv de semaine
        total_nl = total_posts_analysis["weekday_groups"]["NL"]
        total_nlv = total_posts_analysis["weekday_groups"]["NLv"]
        cat_nl = cat_posts["weekday"].get("NL", 0) * num_cats
        cat_nlv = cat_posts["weekday"].get("NLv", 0) * num_cats

        adjusted_nl = max(0, total_nl - cat_nl)
        adjusted_nlv = max(0, total_nlv - cat_nlv)

        adjusted_posts["weekday"]["NL"] = adjusted_nl
        adjusted_posts["weekday_groups"]["NL"] = adjusted_nl
        adjusted_posts["weekday_groups"]["NLv"] = adjusted_nlv

        self.logger.info(f"NL  : Total={total_nl:3d}, CAT={cat_nl//num_cats:2d} x {num_cats} = {cat_nl:2d}, Ajusté={adjusted_nl:3d}")
        self.logger.info(f"NLv : Total={total_nlv:3d}, CAT={cat_nlv//num_cats:2d} x {num_cats} = {cat_nlv:2d}, Ajusté={adjusted_nlv:3d}")

        # 3. Ajustement des postes de weekend (samedi et dimanche séparément)
        for day_type in ["saturday", "sunday_holiday"]:
            self.logger.info(f"\nAJUSTEMENT POSTES {day_type.upper()}:")
            for post_type in total_posts_analysis[day_type]:
                total_count = total_posts_analysis[day_type].get(post_type, 0)
                cat_count = cat_posts[day_type].get(post_type, 0)
                cat_total = cat_count * num_cats
                adjusted_count = max(0, total_count - cat_total)
                adjusted_posts[day_type][post_type] = adjusted_count
                if total_count > 0 or cat_count > 0:
                    self.logger.info(f"{post_type:4}: Total={total_count:3d}, CAT={cat_count:2d} x {num_cats} = {cat_total:2d}, Ajusté={adjusted_count:3d}")

        # 4. Ajustement des groupes de semaine
        self.logger.info("\nAJUSTEMENT GROUPES SEMAINE:")
        for group in total_posts_analysis["weekday_groups"]:
            if group not in ["NL", "NLv"]:  # Déjà traités
                cat_group_count = self.calculate_cat_group_count(group, cat_posts) * num_cats
                total_group_count = total_posts_analysis["weekday_groups"][group]
                adjusted_count = max(0, total_group_count - cat_group_count)
                adjusted_posts["weekday_groups"][group] = adjusted_count
                if total_group_count > 0 or cat_group_count > 0:
                    self.logger.info(f"{group:6}: Total={total_group_count:3d}, CAT={cat_group_count//num_cats:2d} x {num_cats} = {cat_group_count:2d}, Ajusté={adjusted_count:3d}")

        # 5. Ajustement des groupes de weekend
        self.logger.info("\nAJUSTEMENT GROUPES WEEKEND:")
        for group in total_posts_analysis["weekend_groups"]:
            if group != "NLw":  # Traitement spécial pour NLw
                cat_group_count = self.calculate_cat_group_count(group, cat_posts) * num_cats
                total_group_count = total_posts_analysis["weekend_groups"][group]
                adjusted_count = max(0, total_group_count - cat_group_count)
                adjusted_posts["weekend_groups"][group] = adjusted_count
                if total_group_count > 0 or cat_group_count > 0:
                    self.logger.info(f"{group:6}: Total={total_group_count:3d}, CAT={cat_group_count//num_cats:2d} x {num_cats} = {cat_group_count:2d}, Ajusté={adjusted_count:3d}")

        # 6. Calcul spécial pour NLw
        total_nls = total_posts_analysis["saturday"].get("NL", 0)
        total_nld = total_posts_analysis["sunday_holiday"].get("NL", 0)
        total_nlv = total_posts_analysis["weekday_groups"].get("NLv", 0)
        total_nlw = total_nls + total_nld + total_nlv

        cat_nls = cat_posts["saturday"].get("NL", 0) * num_cats
        cat_nld = cat_posts["sunday_holiday"].get("NL", 0) * num_cats
        cat_nlv = cat_posts["weekday"].get("NLv", 0) * num_cats
        cat_total = cat_nls + cat_nld + cat_nlv

        adjusted_nls = max(0, total_nls - cat_nls)
        adjusted_nld = max(0, total_nld - cat_nld)
        adjusted_nlv = max(0, total_nlv - cat_nlv)
        adjusted_total = adjusted_nls + adjusted_nld + adjusted_nlv

        adjusted_posts["weekend_groups"]["NLw"] = adjusted_total

        self.logger.info(
            f"NLw    : Total={total_nlw:3d} (NLs {total_nls} + NLd {total_nld} + NLv {total_nlv})  "
            f"CAT={cat_total//num_cats:2d} (NLs {cat_nls//num_cats} + NLd {cat_nld//num_cats} + NLv {cat_nlv//num_cats}) x {num_cats} = {cat_total:2d}  "
            f"Ajusté={adjusted_total:3d}"
        )

        return adjusted_posts
    

    def round_ideal(self, total_posts: float, half_parts: int) -> Dict[str, float]:
        """
        Calcule la répartition idéale des postes basée sur le nombre de demi-parts
        avec un intervalle ajusté selon les critères suivants:
        - Pour les temps pleins (half_parts=2): intervalle de ±1 autour de la moyenne arrondie
        - Pour les mi-temps (half_parts=1): 
        * Si partie décimale < 0.3: intervalle [floor, floor]
        * Si partie décimale >= 0.3: intervalle [floor, ceil]
        
        Args:
            total_posts: Nombre total de postes à répartir
            half_parts: Nombre de demi-parts du médecin (1 ou 2)
                
        Returns:
            Dict avec min, max et target (moyenne exacte)
        """
        # Calcul de la moyenne exacte
        base_value = total_posts * (half_parts / self.total_half_parts)
        
        if half_parts == 2:  # Pour les temps pleins, garder la logique existante
            rounded = round(base_value)
            if base_value < rounded:
                return {
                    "min": max(0, rounded - 1),
                    "max": rounded,
                    "target": base_value
                }
            else:
                return {
                    "min": rounded,
                    "max": rounded + 1,
                    "target": base_value
                }
        else:  # Pour les mi-temps, nouvelle logique
            floor_value = math.floor(base_value)
            decimal_part = base_value - floor_value
            
            if decimal_part < 0.3:
                return {
                    "min": floor_value,
                    "max": floor_value,
                    "target": base_value
                }
            else:
                return {
                    "min": floor_value,
                    "max": math.ceil(base_value),
                    "target": base_value
                }
    

    
    
    
    
    def _log_analysis_summary(self, total_posts: Dict, cat_posts: Dict, adjusted_posts: Dict):
        """Affiche un tableau récapitulatif de l'analyse complète"""
        
        def print_header():
            headers = [
                "Type", "Total", "CAT", "Médecins", 
                "Temps Plein [min-max]", "Mi-temps [min-max]"
            ]
            header = "{:<20} {:>8} {:>8} {:>10} {:>20} {:>20}".format(*headers)
            self.logger.info("\n" + "=" * 90)
            self.logger.info(header)
            self.logger.info("-" * 90)

        def print_section(title):
            self.logger.info("\n" + title)
            self.logger.info("-" * 90)
            print_header()

        def format_line(post_type, total, cat, med, full_range, half_range):
            return "{:<20} {:>8d} {:>8d} {:>10d} {:>20} {:>20}".format(
                post_type, total, cat, med,
                f"[{full_range['min']}-{full_range['max']}]",
                f"[{half_range['min']}-{half_range['max']}]"
            )

        self.logger.info("\nTABLEAU RÉCAPITULATIF DE L'ANALYSE")
        self.logger.info("=" * 90)

        # SEMAINE
        print_section("POSTES SEMAINE")
        for post in sorted(total_posts["weekday"]):
            if total_posts["weekday"][post] > 0:
                total = total_posts["weekday"][post]
                cat = cat_posts["weekday"].get(post, 0) * len(self.cats)
                med = adjusted_posts["weekday"][post]
                full_range = self.round_ideal(med, 2)
                half_range = self.round_ideal(med, 1)
                self.logger.info(format_line(post, total, cat, med, full_range, half_range))

        # GROUPES SEMAINE
        print_section("GROUPES SEMAINE")
        for group in sorted(total_posts["weekday_groups"]):
            total = total_posts["weekday_groups"][group]
            cat = self.calculate_cat_group_count(group, cat_posts) * len(self.cats)
            med = adjusted_posts["weekday_groups"][group]
            full_range = self.round_ideal(med, 2)
            half_range = self.round_ideal(med, 1)
            self.logger.info(format_line(group, total, cat, med, full_range, half_range))

        # WEEKEND (SAMEDI)
        print_section("POSTES SAMEDI")
        for post in sorted(total_posts["saturday"]):
            if total_posts["saturday"][post] > 0:
                total = total_posts["saturday"][post]
                cat = cat_posts["saturday"].get(post, 0) * len(self.cats)
                med = adjusted_posts["saturday"][post]
                full_range = self.round_ideal(med, 2)
                half_range = self.round_ideal(med, 1)
                self.logger.info(format_line(post, total, cat, med, full_range, half_range))

        # WEEKEND (DIMANCHE)
        print_section("POSTES DIMANCHE/FÉRIÉS")
        for post in sorted(total_posts["sunday_holiday"]):
            if total_posts["sunday_holiday"][post] > 0:
                total = total_posts["sunday_holiday"][post]
                cat = cat_posts["sunday_holiday"].get(post, 0) * len(self.cats)
                med = adjusted_posts["sunday_holiday"][post]
                full_range = self.round_ideal(med, 2)
                half_range = self.round_ideal(med, 1)
                self.logger.info(format_line(post, total, cat, med, full_range, half_range))

        # GROUPES WEEKEND
        print_section("GROUPES WEEKEND")
        for group in sorted(total_posts["weekend_groups"]):
            total = total_posts["weekend_groups"][group]
            cat = self.calculate_cat_group_count(group, cat_posts) * len(self.cats)
            med = adjusted_posts["weekend_groups"][group]
            full_range = self.round_ideal(med, 2)
            half_range = self.round_ideal(med, 1)
            self.logger.info(format_line(group, total, cat, med, full_range, half_range))
            
            
            
            
    def get_all_post_types(self, day_type: str) -> List[str]:
        """Retourne tous les types de postes pour un type de jour donné"""
        all_posts = set(ALL_POST_TYPES)  # Utiliser un set pour éviter les doublons
        
        # Ajouter les postes personnalisés
        if hasattr(self, 'custom_posts'):
            custom_posts = [
                post_name
                for post_name, post in self.custom_posts.items()
                if hasattr(post, 'day_types') and day_type in post.day_types
            ]
            all_posts.update(custom_posts)
            
        return list(all_posts)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    def analyze_weekend_combinations_distribution(self, adjusted_posts: Dict) -> Dict:
        """
        Analyse avancée de la distribution des combinaisons pour le weekend avec la nouvelle 
        logique d'intervalles.
        
        Args:
            adjusted_posts: Dict contenant les postes ajustés après distribution CAT
            
        Returns:
            Dict contenant l'analyse détaillée des combinaisons
        """
        self.logger.info("\nANALYSE DES COMBINAISONS WEEKEND")
        self.logger.info("=" * 100)

        # Structure pour les postes disponibles
        available_posts = {
            "saturday": adjusted_posts["saturday"].copy(),
            "sunday_holiday": adjusted_posts["sunday_holiday"].copy()
        }
        
        # Calcul des postes CAT
        cat_posts = self._calculate_cat_weekend_posts()
        
        # Structure pour l'analyse
        combinations_analysis = {}
        priority_combinations = self._get_post_combinations()

        # En-tête détaillé
        header = "{:<10} {:<8} {:<20} {:<20} {:<30} {:<15}".format(
            "Combo", "Total", "Plein temps", "Mi-temps", "CAT (S/D/Total)", "Faisabilité"
        )
        self.logger.info("\n" + header)
        self.logger.info("-" * 100)

        for priority, combinations in priority_combinations.items():
            if not combinations:
                continue
                
            self.logger.info(f"\nPriorité {priority[-1]}:")
            priority_results = {}

            for combo in combinations:
                first_post, second_post = combo[:2], combo[2:]
                
                # Calcul des combinaisons possibles pour médecins
                med_combinations = self._calculate_possible_combinations(
                    first_post, second_post, available_posts
                )
                
                # Calcul détaillé pour les CAT
                cat_detail = self._calculate_cat_combinations(
                    first_post, second_post, cat_posts
                )
                
                # Analyse de la distribution possible
                distribution = self.analyze_combination_distribution(med_combinations)
                intervals = self._calculate_combination_intervals(med_combinations, cat_detail['total'])
                
                # Stockage des résultats
                result = {
                    "total": med_combinations,
                    "cat_detail": cat_detail,
                    "intervals": intervals,
                    "distribution": distribution
                }
                priority_results[combo] = result

                # Affichage détaillé
                cat_display = (f"{cat_detail['saturday']}/{cat_detail['sunday_holiday']}/"
                            f"{cat_detail['total']}" if self.cats else "N/A")
                
                feasibility = "✓" if distribution["possible"] else "✗"
                
                self.logger.info(
                    "{:<10} {:<8d} {:<20} {:<20} {:<30} {:<15}".format(
                        combo,
                        med_combinations,
                        f"[{intervals['full_time']['min']}-{intervals['full_time']['max']}]",
                        f"[{intervals['half_time']['min']}-{intervals['half_time']['max']}]",
                        cat_display,
                        feasibility
                    )
                )

                # Log détaillé pour le débogage
                if not distribution["possible"]:
                    self.logger.debug(f"""
                    Détails distribution {combo}:
                    Min requis: {distribution['analysis']['min_required']}
                    Max possible: {distribution['analysis']['max_possible']}
                    Disponible: {distribution['analysis']['total_available']}
                    """)

            if priority_results:
                combinations_analysis[priority] = priority_results

        return combinations_analysis

    def _calculate_possible_combinations(self, first_post: str, second_post: str, 
                                    posts: Dict[str, Dict[str, int]]) -> int:
        """
        Calcule le nombre de combinaisons possibles entre deux postes
        """
        # Log des postes disponibles
        self.logger.debug(f"\nAnalyse combinaison {first_post}+{second_post}:")
        for day_type in ["saturday", "sunday_holiday"]:
            self.logger.debug(f"{day_type} - {first_post}: {posts[day_type].get(first_post, 0)}, "
                            f"{second_post}: {posts[day_type].get(second_post, 0)}")

        # Somme des postes disponibles sur samedi et dimanche
        first_count = sum(posts[day].get(first_post, 0) for day in ["saturday", "sunday_holiday"])
        second_count = sum(posts[day].get(second_post, 0) for day in ["saturday", "sunday_holiday"])

        self.logger.debug(f"Totaux: {first_post}={first_count}, {second_post}={second_count}")

        # Vérifier la compatibilité temporelle
        compatible = any(self._are_posts_compatible(first_post, second_post, day_type) 
                        for day_type in ["saturday", "sunday_holiday"])
        self.logger.debug(f"Compatible: {compatible}")

        if not compatible:
            return 0

        # Pour les combinaisons avec visites
        if any(p.startswith(('ML', 'MC', 'AL', 'AC')) for p in (first_post, second_post)):
            result = min(first_count, second_count, 
                        math.floor(min(first_count, second_count) * 0.8))
            self.logger.debug(f"Combinaison avec visite: {result}")
            return result
        
        result = min(first_count, second_count)
        self.logger.debug(f"Combinaison standard: {result}")
        return result

    def _calculate_combination_intervals(self, total_combinations: int, cat_combinations: int) -> Dict:
        """
        Calcule les intervalles pour les combinaisons de postes en utilisant la même logique
        que round_ideal, notamment pour le traitement spécial des mi-temps.
        
        Args:
            total_combinations: Nombre total de combinaisons possibles
            cat_combinations: Nombre de combinaisons réservées aux CAT
            
        Returns:
            Dict contenant les intervalles pour temps plein, mi-temps et CAT
        """
        # Calcul séparé pour temps plein et mi-temps
        full_time_value = total_combinations * (2 / self.total_half_parts)
        half_time_value = total_combinations * (1 / self.total_half_parts)
        
        # Utiliser round_ideal directement pour la cohérence
        full_time_interval = self.round_ideal(total_combinations, 2)
        half_time_interval = self.round_ideal(total_combinations, 1)
        
        # Pour les CAT, si présents
        cat_interval = {"min": 0, "max": 0, "total": 0}
        if self.cats:
            cat_per_cat = cat_combinations / len(self.cats)
            cat_interval = {
                "min": math.floor(cat_per_cat),
                "max": math.ceil(cat_per_cat),
                "total": cat_combinations
            }
        
        # Log pour le débogage
        self.logger.debug(f"""
        Calcul des intervalles pour {total_combinations} combinaisons:
        Temps plein: valeur={full_time_value:.2f}, intervalle={full_time_interval}
        Mi-temps: valeur={half_time_value:.2f}, intervalle={half_time_interval}
        CAT: {cat_interval}
        """)
        
        return {
            "full_time": full_time_interval,
            "half_time": half_time_interval,
            "cat": cat_interval
        }
    
    def analyze_combination_distribution(self, total_combinations: int) -> Dict:
        """
        Analyse la distribution des combinaisons entre les différents types de médecins.
        
        Args:
            total_combinations: Nombre total de combinaisons à distribuer
            
        Returns:
            Dict contenant les détails de la distribution
        """
        # Vérifier si la distribution est possible
        if total_combinations <= 0:
            return {
                "possible": False,
                "full_time": {"min": 0, "max": 0, "target": 0},
                "half_time": {"min": 0, "max": 0, "target": 0}
            }
        
        # Utiliser round_ideal pour calculer les intervalles
        full_time = self.round_ideal(total_combinations, 2)
        half_time = self.round_ideal(total_combinations, 1)
        
        # Vérifier si la distribution est réalisable
        full_time_docs = len([d for d in self.doctors if d.half_parts == 2])
        half_time_docs = len([d for d in self.doctors if d.half_parts == 1])
        
        min_required = (full_time["min"] * full_time_docs + 
                    half_time["min"] * half_time_docs)
        max_possible = (full_time["max"] * full_time_docs + 
                    half_time["max"] * half_time_docs)
        
        return {
            "possible": min_required <= total_combinations <= max_possible,
            "full_time": full_time,
            "half_time": half_time,
            "analysis": {
                "min_required": min_required,
                "max_possible": max_possible,
                "total_available": total_combinations
            }
        }
    def _calculate_cat_combinations(self, first_post: str, second_post: str, cat_posts: Dict) -> Dict:
        """
        Calcule et détaille les combinaisons possibles pour les CAT par jour.
        """
        self.logger.debug(f"\nCalcul combinaisons CAT pour {first_post}+{second_post}:")
        
        cat_detail = {
            "saturday": 0,
            "sunday_holiday": 0,
            "total": 0
        }
        
        num_cats = len(self.cats)
        if num_cats == 0:
            return cat_detail
            
        for day_type in ["saturday", "sunday_holiday"]:
            # Log des postes disponibles pour CAT
            first_count = cat_posts[day_type].get(first_post, 0) // num_cats
            second_count = cat_posts[day_type].get(second_post, 0) // num_cats
            
            self.logger.debug(f"{day_type} - Postes disponibles:")
            self.logger.debug(f"{first_post}: {first_count} par CAT ({cat_posts[day_type].get(first_post, 0)} total)")
            self.logger.debug(f"{second_post}: {second_count} par CAT ({cat_posts[day_type].get(second_post, 0)} total)")
                
            # Vérifier la compatibilité temporelle
            if self._are_posts_compatible(first_post, second_post, day_type):
                # Calculer les combinaisons possibles
                day_combinations = min(first_count, second_count)
                
                # Pour les visites, réduire de 20%
                if any(p.startswith(('ML', 'MC', 'AL', 'AC')) for p in (first_post, second_post)):
                    day_combinations = math.floor(day_combinations * 0.8)
                    
                cat_detail[day_type] = day_combinations * num_cats
                cat_detail["total"] += cat_detail[day_type]
                
                self.logger.debug(f"Combinaisons pour {day_type}: {day_combinations} par CAT ({cat_detail[day_type]} total)")

        self.logger.debug(f"Total combinaisons CAT: {cat_detail['total']}")
        return cat_detail
    
    def _format_interval(self, interval: Dict) -> str:
        """Formate un intervalle pour l'affichage"""
        return f"[{interval['min']:2d}-{interval['max']:2d}]"

    def _get_post_combinations(self) -> Dict[str, List[str]]:
        """
        Retourne les combinaisons de postes organisées par priorité.
        Les combinaisons sont ordonnées selon leur importance stratégique dans le planning.
        """
        return {
            # Priorité 1: Combinaisons stratégiques principales
            "priority1": [
                # Combinaisons St André et Créon soir
                "SASS", "RARS",  # Combinaisons après-midi/soir pour les sites distants
                "SMSA", "RMRA",  # Combinaisons après-midi/soir pour les sites distants
                "MLCA","MMAC"         # Visite longue avec consultation Cenon
                "CMAL","MMAL"         # Consultation Cenon avec visite après-midi
                "HMAL",         # Consultation Beychac avec visite après-midi
                "HAHS",         # Beychac après-midi/soir
                "HMAC",         # Beychac matin avec visite
                "SMAC",         # St André matin avec visite
                "CMAC"          # Cenon matin avec visite
            ],
            
            # Priorité 2: Combinaisons visites-consultations
            "priority2": [
                "MLHA",  # Visite longue avec Beychac après-midi
                "MLSA",  # Visite longue avec St André après-midi
                "MLRA",  # Visite longue avec Créon après-midi
                "MCCA",  # Visite courte avec Cenon après-midi
                "MCHA",  # Visite courte avec Beychac après-midi
                "MCRA",  # Visite courte avec Créon après-midi
                "MCSA"   # Visite courte avec St André après-midi
            ],
            
            # Priorité 3: Combinaisons matin-après-midi visites
            "priority3": [
                "MCAL",  # Visite courte matin avec visite après-midi
                "CMAL",  # Cenon matin avec visite après-midi
                "CACS",  # Cenon matin avec visite après-midi
                "HMAL",  # Beychac matin avec visite après-midi
                "HMAC",  # Beychac matin avec visite courte
                "RMAL",  # Créon matin avec visite après-midi
                "RMAC",  # Créon matin avec visite courte
                "SMAL",  # St André matin avec visite après-midi
                "SMAC"   # St André matin avec visite courte
            ],
            
            # Priorité 5: Combinaisons avec nuit courte (NA)
            "priority5": [
                "SANA",  # St André après-midi + nuit courte
                "RANA",  # Créon après-midi + nuit courte
                "CANA",  # Cenon après-midi + nuit courte
                "HANA"   # Beychac après-midi + nuit courte
            ]
        }
    def _are_posts_compatible(self, post1: str, post2: str, day_type: str) -> bool:
        """Vérifie si deux postes sont compatibles dans le même jour"""
        # Récupérer les détails des postes depuis le PostManager
        post1_details = self.post_manager.get_post_details(post1, day_type)
        post2_details = self.post_manager.get_post_details(post2, day_type)
        
        self.logger.debug(f"\nVérification compatibilité {post1}-{post2} ({day_type}):")
        self.logger.debug(f"Post1 {post1}: {post1_details}")
        self.logger.debug(f"Post2 {post2}: {post2_details}")
        
        if not (post1_details and post2_details):
            self.logger.debug("Un des postes n'a pas de détails")
            return False
            
        # Vérifier le chevauchement des horaires
        compatible = (post1_details["end_time"] <= post2_details["start_time"] or
                    post2_details["end_time"] <= post1_details["start_time"])
        self.logger.debug(f"Compatibilité: {compatible}")
        return compatible
    
    
    def _check_combination_compatibility(self, first_post: str, second_post: str, 
                                    day_type: str, remaining_posts: Dict) -> int:
        """
        Vérifie la compatibilité d'une combinaison de postes et retourne le nombre possible.
        
        Args:
            first_post: Premier poste de la combinaison
            second_post: Second poste de la combinaison
            day_type: Type de jour (saturday/sunday_holiday)
            remaining_posts: Dictionnaire des postes restants disponibles
        
        Returns:
            Nombre de combinaisons possibles
        """
        # Vérifier si les postes existent et sont disponibles
        if first_post not in remaining_posts[day_type] or second_post not in remaining_posts[day_type]:
            return 0
            
        first_count = remaining_posts[day_type][first_post]
        second_count = remaining_posts[day_type][second_post]
        
        # Vérifier la compatibilité temporelle des postes
        if not self._are_posts_compatible(first_post, second_post, day_type):
            return 0
            
        # Pour les combinaisons avec visites (ML, MC, AL, AC)
        if any(p.startswith(('ML', 'MC', 'AL', 'AC')) for p in (first_post, second_post)):
            # Réduire le nombre possible pour tenir compte des temps de déplacement
            return min(first_count, second_count, math.floor(min(first_count, second_count) * 0.8))
        
        return min(first_count, second_count)

    def _log_combinations_analysis(self, analysis: Dict):
        """Affiche les résultats de l'analyse des combinaisons"""
        headers = ["Combinaison", "Total", "Plein temps", "Mi-temps", "CAT"]
        format_str = "{:<12} {:<8} {:<15} {:<15} {:<15}"
        
        self.logger.info(format_str.format(*headers))
        self.logger.info("-" * 70)
        
        for priority in ["priority1", "priority2", "priority3", "priority4", "priority5"]:
            if analysis[priority]:
                self.logger.info(f"\nPriorité {priority[-1]}:")
                for combo, data in analysis[priority].items():
                    intervals = data["intervals"]
                    self.logger.info(format_str.format(
                        combo,
                        data["total"],
                        f"[{intervals['full_time']['min']}-{intervals['full_time']['max']}]",
                        f"[{intervals['half_time']['min']}-{intervals['half_time']['max']}]",
                        f"[{intervals['cat']['min']}-{intervals['cat']['max']}]"
                    ))
                    
    
    def analyze_weekday_combinations_distribution(self, adjusted_posts: Dict) -> Dict:
        """
        Analyse avancée de la distribution des combinaisons pour les jours de semaine
        avec la nouvelle logique d'intervalles.
        
        Args:
            adjusted_posts: Dict contenant les postes ajustés après distribution CAT
            
        Returns:
            Dict contenant l'analyse détaillée des combinaisons
        """
        self.logger.info("\nANALYSE DES COMBINAISONS SEMAINE")
        self.logger.info("=" * 100)

        # Structure pour les postes disponibles
        available_posts = {"weekday": adjusted_posts["weekday"].copy()}
        
        # Calcul des postes CAT pour la semaine
        cat_posts = self._calculate_cat_weekday_posts()
        
        combinations_analysis = {}
        priority_combinations = self._get_weekday_post_combinations()

        # En-tête détaillé
        header = "{:<10} {:<8} {:<20} {:<20} {:<15} {:<15}".format(
            "Combo", "Total", "Plein temps", "Mi-temps", "CAT", "Faisabilité"
        )
        self.logger.info("\n" + header)
        self.logger.info("-" * 90)

        for priority, combinations in priority_combinations.items():
            if not combinations:
                continue
                
            self.logger.info(f"\nPriorité {priority[-1]}:")
            priority_results = {}

            for combo in combinations:
                first_post, second_post = combo[:2], combo[2:]
                
                # Calcul des combinaisons possibles
                med_combinations = self._calculate_weekday_possible_combinations(
                    first_post, second_post, available_posts
                )
                
                # Calcul pour les CAT
                cat_combinations = self._calculate_weekday_possible_combinations(
                    first_post, second_post, {"weekday": cat_posts}
                )
                
                # Analyse de la distribution
                distribution = self.analyze_combination_distribution(med_combinations)
                intervals = self._calculate_combination_intervals(med_combinations, cat_combinations)
                
                # Stockage des résultats
                result = {
                    "total": med_combinations,
                    "cat_total": cat_combinations,
                    "intervals": intervals,
                    "distribution": distribution
                }
                priority_results[combo] = result

                # Affichage détaillé
                feasibility = "✓" if distribution["possible"] else "✗"
                
                self.logger.info(
                    "{:<10} {:<8d} {:<20} {:<20} {:<15} {:<15}".format(
                        combo,
                        med_combinations,
                        f"[{intervals['full_time']['min']}-{intervals['full_time']['max']}]",
                        f"[{intervals['half_time']['min']}-{intervals['half_time']['max']}]",
                        str(cat_combinations),
                        feasibility
                    )
                )

                # Log des problèmes de distribution
                if not distribution["possible"]:
                    self.logger.debug(f"""
                    Détails distribution {combo}:
                    Min requis: {distribution['analysis']['min_required']}
                    Max possible: {distribution['analysis']['max_possible']}
                    Disponible: {distribution['analysis']['total_available']}
                    """)

            if priority_results:
                combinations_analysis[priority] = priority_results

        return combinations_analysis
    
    def _calculate_cat_weekend_posts(self) -> Dict:
        """
        Calcule les postes disponibles pour les CAT pendant le weekend.
        """
        cat_posts = {
            "saturday": {},
            "sunday_holiday": {}
        }
        
        for day_type in ["saturday", "sunday_holiday"]:
            config = getattr(self.post_configuration, f"cat_{day_type}")
            for post_type in ALL_POST_TYPES:
                if hasattr(config, post_type):
                    cat_posts[day_type][post_type] = config[post_type].total * len(self.cats)
                    
        return cat_posts

    def _calculate_cat_weekday_posts(self) -> Dict:
        """
        Calcule les postes disponibles pour les CAT pendant la semaine.
        """
        cat_posts = {}
        config = self.post_configuration.cat_weekday
        
        for post_type in ALL_POST_TYPES:
            if hasattr(config, post_type):
                cat_posts[post_type] = config[post_type].total * len(self.cats)
                
        return cat_posts

    def _get_weekday_post_combinations(self) -> Dict[str, List[str]]:
        """
        Retourne les combinaisons de postes pour les jours de semaine.
        Les combinaisons sont organisées par priorité.
        """
        return {
            "priority1": [
                "MLCA", "MLHA",  # Visite longue avec consultations après-midi
                "MLSA", "MLRA", 
                "MCCA", "MCHA",  # Visite courte avec consultations après-midi
                "MCRA", "MCSA"
            
            ],
            "priority2": [
                "CMCA", "CACS","MMCA",  # Cenon matin-après-midi et après-midi-soir
                "HMHA", "HAHS",  # Beychac matin-après-midi et après-midi-soir
                "SMSA", "SASS",  # St André matin-après-midi et après-midi-soir
                "RMRA", "RARS"   # Créon matin-après-midi et après-midi-soir
            ],
            "priority3": [
                "MCAL", "CMAL", "MMAC", # Combinaisons avec visites après-midi
                "HMAL", "HMAC", "MMAL", 
                "RMAL", "RMAC",
                "SMAL", "SMAC"
            ],
            "priority5": [
                "SANA", "RANA",  # Combinaisons avec nuit courte
                "CANA", "HANA"
            ]
        }

    def _calculate_weekday_possible_combinations(self, first_post: str, second_post: str, 
                                            posts: Dict[str, Dict[str, int]]) -> int:
        """
        Calcule le nombre de combinaisons possibles entre deux postes pour les jours de semaine
        """
        # Obtenir le nombre de postes disponibles
        first_count = posts["weekday"].get(first_post, 0)
        second_count = posts["weekday"].get(second_post, 0)

        # Vérifier la compatibilité temporelle
        if not self._are_posts_compatible(first_post, second_post, "weekday"):
            return 0

        # Ajustement pour les visites
        if any(p.startswith(('ML', 'MC', 'AL', 'AC')) for p in (first_post, second_post)):
            return min(first_count, second_count, 
                    math.floor(min(first_count, second_count) * 0.8))
        
        return min(first_count, second_count)
