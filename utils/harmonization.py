# © 2024 HILAL Arkane. Tous droits réservés.
# utils/harmonization.py

import logging
from datetime import date, timedelta
from workalendar.europe import France
from core.Constantes.models import PostConfig, SpecificPostConfig
from core.Constantes.day_type import DayType

logger = logging.getLogger(__name__)

class ConfigHarmonizer:
    """
    Classe utilitaire pour harmoniser et vérifier la cohérence des configurations de postes.
    """
    
    def __init__(self, post_configuration):
        """
        Initialise l'harmoniseur avec une configuration de postes.
        
        Args:
            post_configuration: La configuration de postes à harmoniser
        """
        self.post_configuration = post_configuration
        self.cal_france = France()
        self.issues = []
    
    def check_all(self):
        """
        Vérifie l'ensemble des problèmes potentiels dans la configuration.
        
        Returns:
            list: Liste des problèmes identifiés
        """
        self.issues = []
        
        # Vérification des configurations spécifiques
        self.check_specific_configs()
        
        # Vérification des types de jour
        self.check_day_type_consistency()
        
        # Vérification des types de postes
        self.check_post_types()
        
        # Vérification des chevauchements
        self.check_overlapping_configs()
        
        return self.issues
    
    def fix_all(self):
        """
        Corrige automatiquement les problèmes identifiés.
        
        Returns:
            dict: Rapport des corrections effectuées
        """
        report = {
            'fixed_issues': 0,
            'remaining_issues': 0,
            'details': []
        }
        
        # Vérifier les problèmes
        self.check_all()
        total_issues = len(self.issues)
        
        # Corriger les chevauchements
        fixed = self.fix_overlapping_configs()
        if fixed > 0:
            report['details'].append(f"Corrigé {fixed} chevauchements de configuration")
        
        # Corriger les types de jour inappropriés
        fixed = self.fix_day_type_mismatches()
        if fixed > 0:
            report['details'].append(f"Corrigé {fixed} types de jour inappropriés")
        
        # Mettre à jour les compteurs
        self.check_all()  # Revérifier après les corrections
        report['fixed_issues'] = total_issues - len(self.issues)
        report['remaining_issues'] = len(self.issues)
        
        return report
    
    def check_specific_configs(self):
        """
        Vérifie les configurations spécifiques pour des problèmes potentiels.
        """
        if not hasattr(self.post_configuration, 'specific_configs'):
            return
        
        for config in self.post_configuration.specific_configs:
            # Vérifier les dates
            if config.start_date > config.end_date:
                self.issues.append({
                    'type': 'date_order',
                    'message': self.format_issue_message('date_order', 
                                                    start_date=config.start_date, 
                                                    end_date=config.end_date),
                    'config': config
                })
            
            # Vérifier le type de jour
            day_type = config.apply_to
            if day_type not in ["Semaine", "Samedi", "Dimanche/Férié"]:
                self.issues.append({
                    'type': 'invalid_day_type',
                    'message': self.format_issue_message('invalid_day_type', 
                                                    day_type=day_type),
                    'config': config
                })
            
            # Vérifier si le type de jour est approprié pour chaque jour de la période
            current_date = config.start_date
            while current_date <= config.end_date:
                appropriate_type = self.get_appropriate_day_type(current_date)
                if appropriate_type != day_type:
                    self.issues.append({
                        'type': 'day_type_mismatch',
                        'message': self.format_issue_message('day_type_mismatch',
                                                        date=current_date,
                                                        current_type=day_type,
                                                        appropriate_type=appropriate_type),
                        'config': config,
                        'date': current_date,
                        'appropriate_type': appropriate_type
                    })
                current_date += timedelta(days=1)
    
    def check_specific_configs(self):
        """
        Vérifie les configurations spécifiques pour des problèmes potentiels.
        """
        if not hasattr(self.post_configuration, 'specific_configs'):
            return
        
        for config in self.post_configuration.specific_configs:
            # Vérifier les dates
            if config.start_date > config.end_date:
                self.issues.append({
                    'type': 'date_order',
                    'message': f"Configuration avec dates inversées:\n"
                            f"Date de début ({config.start_date}) > Date de fin ({config.end_date})",
                    'config': config
                })
            
            # Vérifier le type de jour
            day_type = config.apply_to
            if day_type not in ["Semaine", "Samedi", "Dimanche/Férié"]:
                self.issues.append({
                    'type': 'invalid_day_type',
                    'message': f"Type de jour invalide: '{day_type}'\n"
                            f"Les types valides sont: Semaine, Samedi, Dimanche/Férié",
                    'config': config
                })
            
            # Vérifier si le type de jour est approprié pour chaque jour de la période
            current_date = config.start_date
            while current_date <= config.end_date:
                appropriate_type = self.get_appropriate_day_type(current_date)
                if appropriate_type != day_type:
                    self.issues.append({
                        'type': 'day_type_mismatch',
                        'message': f"Le {current_date.strftime('%d/%m/%Y')} est un {appropriate_type}\n"
                                f"mais est configuré comme {day_type}",
                        'config': config,
                        'date': current_date,
                        'appropriate_type': appropriate_type
                    })
                current_date += timedelta(days=1)



    def check_day_type_consistency(self):
        """
        Vérifie la cohérence des types de jour dans toutes les configurations.
        """
        # Vérifier que tous les jours fériés utilisent la configuration Dimanche/Férié
        year = date.today().year
        holidays = self.cal_france.holidays(year)
        
        for holiday_date, holiday_name in holidays:
            # Chercher si ce jour férié a une configuration spécifique
            configs = self.find_configs_for_date(holiday_date)
            for config in configs:
                if config.apply_to != "Dimanche/Férié":
                    self.issues.append({
                        'type': 'holiday_wrong_type',
                        'message': f"Le jour férié {holiday_date.strftime('%d/%m/%Y')} ({holiday_name})\n"
                                f"est configuré comme '{config.apply_to}' au lieu de 'Dimanche/Férié'",
                        'config': config,
                        'date': holiday_date,
                        'appropriate_type': "Dimanche/Férié"
                    })
        
        # Vérifier les jours de pont
        bridge_days = self.find_bridge_days(year)
        for bridge_date in bridge_days:
            configs = self.find_configs_for_date(bridge_date)
            for config in configs:
                if config.apply_to != "Dimanche/Férié":
                    self.issues.append({
                        'type': 'bridge_day_wrong_type',
                        'message': f"Le jour de pont {bridge_date.strftime('%d/%m/%Y')}\n"
                                f"est configuré comme '{config.apply_to}' au lieu de 'Dimanche/Férié'",
                        'config': config,
                        'date': bridge_date,
                        'appropriate_type': "Dimanche/Férié"
                    })
    
    def check_post_types(self):
        """
        Vérifie que tous les types de postes utilisés dans les configurations spécifiques existent
        dans les configurations standard correspondantes.
        """
        from core.Constantes.models import ALL_POST_TYPES
        
        if not hasattr(self.post_configuration, 'specific_configs'):
            return
        
        for config in self.post_configuration.specific_configs:
            day_type = config.apply_to
            
            # Déterminer la configuration standard correspondante
            if day_type == "Semaine":
                standard_config = self.post_configuration.weekday
            elif day_type == "Samedi":
                standard_config = self.post_configuration.saturday
            elif day_type == "Dimanche/Férié":
                standard_config = self.post_configuration.sunday_holiday
            else:
                continue  # Type de jour inconnu, déjà signalé par une autre vérification
            
            # Vérifier chaque type de poste
            for post_type in config.post_counts.keys():
                if post_type not in ALL_POST_TYPES and post_type not in standard_config:
                    self.issues.append({
                        'type': 'unknown_post_type',
                        'message': f"Type de poste inconnu: {post_type} dans configuration {config.start_date} - {config.end_date}",
                        'config': config,
                        'post_type': post_type
                    })
    
    def check_overlapping_configs(self):
        """
        Vérifie si des configurations spécifiques se chevauchent pour le même type de jour.
        """
        if not hasattr(self.post_configuration, 'specific_configs'):
            return
        
        # Trier les configurations par date de début
        sorted_configs = sorted(self.post_configuration.specific_configs, key=lambda x: x.start_date)
        
        # Regrouper par type de jour
        day_type_groups = {}
        for config in sorted_configs:
            day_type = config.apply_to
            if day_type not in day_type_groups:
                day_type_groups[day_type] = []
            day_type_groups[day_type].append(config)
        
        # Pour chaque type de jour, vérifier les chevauchements
        for day_type, configs in day_type_groups.items():
            for i in range(len(configs)):
                for j in range(i + 1, len(configs)):
                    config1 = configs[i]
                    config2 = configs[j]
                    
                    # Vérifier s'il y a chevauchement
                    if (config1.start_date <= config2.end_date and
                        config1.end_date >= config2.start_date):
                        self.issues.append({
                            'type': 'overlapping_configs',
                            'message': self.format_issue_message('overlapping_configs',
                                                                config1=config1,
                                                                config2=config2,
                                                                day_type=day_type),
                            'config1': config1,
                            'config2': config2
                        })
                        
    def fix_overlapping_configs(self):
        """
        Corrige les chevauchements de configuration en fusionnant ou en ajustant les dates.
        
        Returns:
            int: Nombre de problèmes corrigés
        """
        # Identifier tous les chevauchements
        overlaps = [issue for issue in self.issues if issue['type'] == 'overlapping_configs']
        if not overlaps:
            return 0
        
        # Configurations à supprimer et remplacer
        to_remove = set()
        to_add = []
        
        for overlap in overlaps:
            config1 = overlap['config1']
            config2 = overlap['config2']
            
            # Si les deux configurations ont exactement les mêmes valeurs, fusionner
            if config1.post_counts == config2.post_counts:
                # Créer une nouvelle configuration avec la période étendue
                new_start = min(config1.start_date, config2.start_date)
                new_end = max(config1.end_date, config2.end_date)
                
                new_config = SpecificPostConfig(
                    start_date=new_start,
                    end_date=new_end,
                    apply_to=config1.apply_to,
                    post_counts=config1.post_counts.copy()
                )
                
                to_remove.add(config1)
                to_remove.add(config2)
                to_add.append(new_config)
            else:
                # Cas plus complexe: ajuster les dates pour éviter le chevauchement
                # Pour simplifier, on donne la priorité à la configuration la plus récente
                if config1.start_date <= config2.start_date:
                    # config1 est plus ancienne, ajuster sa date de fin
                    new_end = config2.start_date - timedelta(days=1)
                    if new_end >= config1.start_date:  # Vérifier que la configuration reste valide
                        config1.end_date = new_end
                else:
                    # config2 est plus ancienne, ajuster sa date de fin
                    new_end = config1.start_date - timedelta(days=1)
                    if new_end >= config2.start_date:  # Vérifier que la configuration reste valide
                        config2.end_date = new_end
        
        # Effectuer les modifications
        for config in to_remove:
            if config in self.post_configuration.specific_configs:
                self.post_configuration.specific_configs.remove(config)
        
        for config in to_add:
            self.post_configuration.specific_configs.append(config)
        
        return len(overlaps)
    
        

    def fix_day_type_mismatches(self):
        """
        Corrige les types de jour inappropriés dans les configurations spécifiques.
        
        Returns:
            int: Nombre de problèmes corrigés
        """
        mismatches = [issue for issue in self.issues if issue['type'] in 
                    ['day_type_mismatch', 'holiday_wrong_type', 'bridge_day_wrong_type']]
        if not mismatches:
            return 0
        
        # Regrouper par configuration en utilisant un identifiant unique au lieu de l'objet lui-même
        config_issues = {}
        for issue in mismatches:
            config = issue['config']
            # Créer un identifiant unique basé sur les attributs de la configuration
            config_id = (id(config), config.start_date, config.end_date, config.apply_to)
            if config_id not in config_issues:
                config_issues[config_id] = {'config': config, 'issues': []}
            config_issues[config_id]['issues'].append(issue)
        
        fixed_count = 0
        
        for config_data in config_issues.values():
            config = config_data['config']
            issues = config_data['issues']
            
            # Si la configuration couvre une seule date et qu'elle est de type inapproprié,
            # simplement ajuster le type de jour
            if config.start_date == config.end_date:
                appropriate_type = self.get_appropriate_day_type(config.start_date)
                if config.apply_to != appropriate_type:
                    config.apply_to = appropriate_type
                    fixed_count += 1
            else:
                # Configuration multi-jours avec des types de jour inappropriés
                # Segmenter la configuration en fonction des types de jour
                segments = {}
                
                current_date = config.start_date
                while current_date <= config.end_date:
                    day_type = self.get_appropriate_day_type(current_date)
                    if day_type not in segments:
                        segments[day_type] = []
                    segments[day_type].append(current_date)
                    current_date += timedelta(days=1)
                
                # Si tous les jours ont le même type approprié et que ce n'est pas le type actuel,
                # simplement ajuster le type de jour
                if len(segments) == 1:
                    appropriate_type = list(segments.keys())[0]
                    if config.apply_to != appropriate_type:
                        config.apply_to = appropriate_type
                        fixed_count += 1
                else:
                    # Cas complexe: plusieurs types de jour appropriés
                    # Supprimer cette configuration et créer des segments distincts
                    if config in self.post_configuration.specific_configs:
                        self.post_configuration.specific_configs.remove(config)
                    
                    for day_type, dates in segments.items():
                        # Regrouper les dates consécutives
                        date_ranges = self._group_consecutive_dates(dates)
                        
                        for start_date, end_date in date_ranges:
                            new_config = SpecificPostConfig(
                                start_date=start_date,
                                end_date=end_date,
                                apply_to=day_type,
                                post_counts=config.post_counts.copy()
                            )
                            self.post_configuration.specific_configs.append(new_config)
                            fixed_count += 1
        
        return fixed_count
    
    def _group_consecutive_dates(self, dates):
        """
        Regroupe des dates consécutives en plages.
        
        Args:
            dates: Liste de dates à regrouper
            
        Returns:
            list: Liste de tuples (date_début, date_fin)
        """
        if not dates:
            return []
        
        # Trier les dates
        sorted_dates = sorted(dates)
        
        ranges = []
        range_start = sorted_dates[0]
        prev_date = sorted_dates[0]
        
        for current_date in sorted_dates[1:]:
            if (current_date - prev_date).days > 1:
                # Nouvelle plage
                ranges.append((range_start, prev_date))
                range_start = current_date
            prev_date = current_date
        
        # Ajouter la dernière plage
        ranges.append((range_start, prev_date))
        
        return ranges
    
    def find_configs_for_date(self, target_date):
        """
        Trouve toutes les configurations spécifiques qui couvrent une date donnée.
        
        Args:
            target_date: Date à rechercher
            
        Returns:
            list: Liste des configurations concernées
        """
        if not hasattr(self.post_configuration, 'specific_configs'):
            return []
        
        return [config for config in self.post_configuration.specific_configs 
                if config.start_date <= target_date <= config.end_date]
    
    def find_bridge_days(self, year):
        """
        Trouve tous les jours de pont pour une année donnée.
        
        Args:
            year: Année à analyser
            
        Returns:
            list: Liste des jours de pont
        """
        bridge_days = []
        
        # Parcourir chaque jour de l'année
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        current_date = start_date
        while current_date <= end_date:
            if DayType.is_bridge_day(current_date, self.cal_france):
                bridge_days.append(current_date)
            current_date += timedelta(days=1)
        
        return bridge_days
    
    def get_appropriate_day_type(self, target_date):
        """
        Détermine le type de jour approprié pour une date donnée.
        
        Args:
            target_date: Date à analyser
            
        Returns:
            str: Type de jour approprié ("Semaine", "Samedi", "Dimanche/Férié")
        """
        # Jour férié ou pont
        if self.cal_france.is_holiday(target_date) or DayType.is_bridge_day(target_date, self.cal_france):
            return "Dimanche/Férié"
        
        # Jour de la semaine
        weekday = target_date.weekday()
        if weekday == 5:  # Samedi
            return "Samedi"
        elif weekday == 6:  # Dimanche
            return "Dimanche/Férié"
        else:  # Lundi-Vendredi
            return "Semaine"
    
    
    def format_date_range(self, start_date, end_date):
        """
        Formate une plage de dates de manière lisible.
        
        Args:
            start_date: Date de début
            end_date: Date de fin
            
        Returns:
            str: Plage de dates formatée
        """
        start_fmt = start_date.strftime("%d/%m/%Y")
        
        if start_date == end_date:
            return start_fmt
        
        end_fmt = end_date.strftime("%d/%m/%Y")
        return f"{start_fmt} au {end_fmt}"

    def format_issue_message(self, issue_type, **kwargs):
        """
        Génère un message d'erreur formaté pour différents types de problèmes.
        
        Args:
            issue_type: Type de problème
            **kwargs: Arguments spécifiques au type de problème
            
        Returns:
            str: Message formaté
        """
        if issue_type == 'date_order':
            start_date = kwargs.get('start_date')
            end_date = kwargs.get('end_date')
            return (
                f"Dates inversées:\n"
                f"Date de début: {start_date.strftime('%d/%m/%Y')}\n"
                f"Date de fin: {end_date.strftime('%d/%m/%Y')}"
            )
        
        elif issue_type == 'invalid_day_type':
            day_type = kwargs.get('day_type')
            return (
                f"Type de jour invalide: '{day_type}'\n"
                f"Les types valides sont:\n"
                f"- Semaine\n"
                f"- Samedi\n"
                f"- Dimanche/Férié"
            )
        
        elif issue_type == 'day_type_mismatch':
            date_obj = kwargs.get('date')
            current_type = kwargs.get('current_type')
            appropriate_type = kwargs.get('appropriate_type')
            
            # Déterminer le jour de la semaine
            weekday_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            weekday = weekday_names[date_obj.weekday()]
            
            return (
                f"{weekday} {date_obj.strftime('%d/%m/%Y')}\n"
                f"Type actuel : {current_type}\n"
                f"Type correct : {appropriate_type}"
            )
        
        elif issue_type == 'holiday_wrong_type':
            date_obj = kwargs.get('date')
            holiday_name = kwargs.get('holiday_name', "")
            current_type = kwargs.get('current_type')
            
            message = f"Jour férié : {date_obj.strftime('%d/%m/%Y')}"
            if holiday_name:
                message += f" ({holiday_name})"
            
            return (
                f"{message}\n"
                f"Type actuel : {current_type}\n"
                f"Type correct : Dimanche/Férié"
            )
        
        elif issue_type == 'bridge_day_wrong_type':
            date_obj = kwargs.get('date')
            current_type = kwargs.get('current_type')
            
            return (
                f"Jour de pont : {date_obj.strftime('%d/%m/%Y')}\n"
                f"Type actuel : {current_type}\n"
                f"Type correct : Dimanche/Férié"
            )
        
        elif issue_type == 'unknown_post_type':
            post_type = kwargs.get('post_type')
            config = kwargs.get('config')
            
            return (
                f"Type de poste inconnu : '{post_type}'\n"
                f"Configuration : {self.format_date_range(config.start_date, config.end_date)}\n"
                f"Ce type de poste n'existe pas dans la configuration standard."
            )
        
        elif issue_type == 'overlapping_configs':
            config1 = kwargs.get('config1')
            config2 = kwargs.get('config2')
            day_type = kwargs.get('day_type')
            
            return (
                f"Chevauchement de configurations ({day_type}) :\n"
                f"1) {self.format_date_range(config1.start_date, config1.end_date)}\n"
                f"2) {self.format_date_range(config2.start_date, config2.end_date)}"
            )
        
        # Par défaut, retourner un message générique
        return "Problème détecté dans la configuration"