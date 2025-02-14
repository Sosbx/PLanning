# core/Analyzer/combinations_analyzer.py

from typing import Dict, List, Tuple, Optional
from datetime import date, timedelta
from core.Constantes.models import (Doctor, CAT, WEEKEND_COMBINATIONS, 
                        WEEKDAY_COMBINATIONS, ALL_POST_TYPES)
from core.Analyzer.availability_matrix import AvailabilityMatrix
import logging

class CombinationsAnalyzer:
    def __init__(self, doctors: List[Doctor], cats: List[CAT], 
                availability_matrix: AvailabilityMatrix, 
                pre_analysis_results: Dict):
        self.doctors = doctors
        self.cats = cats
        self.availability_matrix = availability_matrix
        self.pre_analysis_results = pre_analysis_results
        self.logger = logging.getLogger(__name__)
        
        # Vérification détaillée de la structure pre_analysis_results
        self.logger.info("\nVérification structure pre_analysis_results:")
        if "ideal_distribution" in pre_analysis_results:
            first_doctor = next(iter(pre_analysis_results["ideal_distribution"].values()))
            if "weekday_groups" in first_doctor:
                self.logger.info("Structure weekday_groups pour le premier médecin:")
                for group, value in first_doctor["weekday_groups"].items():
                    self.logger.info(f"- {group}: {value}")
            else:
                self.logger.error("weekday_groups non trouvé dans ideal_distribution")
        else:
            self.logger.error("ideal_distribution non trouvé dans pre_analysis_results")

    def analyze(self) -> Dict:
        """Point d'entrée principal de l'analyse des combinaisons."""
        self.logger.info("\nANALYSE GLOBALE DES COMBINAISONS")
        self.logger.info("=" * 100)

        # Ajout de la vérification des groupes disponibles
        if "ideal_distribution" in self.pre_analysis_results:
            first_doctor = next(iter(self.pre_analysis_results["ideal_distribution"].values()))
            self.logger.info("Groupes disponibles dans weekday_groups:")
            for group in first_doctor.get("weekday_groups", {}):
                self.logger.info(f"- {group}")

        analysis_results = {
            "weekend": self.analyze_weekend_combinations(),
            "weekday": self.analyze_weekday_combinations()
        }

        self._log_summary(analysis_results)
        return analysis_results

    def analyze_weekend_combinations(self) -> Dict:
        """Analyse toutes les combinaisons weekend."""
        self._log_analysis_header("weekend")
        results = {}
        
        for combo in WEEKEND_COMBINATIONS:
            results[combo] = self._analyze_combination(combo, "weekend")
            self._log_combination_analysis(combo, results[combo], "weekend")
        
        return results

    def analyze_weekday_combinations(self) -> Dict:
        """Analyse toutes les combinaisons semaine."""
        self._log_analysis_header("weekday")
        results = {}
        
        for combo in WEEKDAY_COMBINATIONS:
            results[combo] = self._analyze_combination(combo, "weekday")
            self._log_combination_analysis(combo, results[combo], "weekday")
        
        return results

    def _analyze_combination(self, combo: str, day_type: str) -> Dict:
        """Analyse détaillée d'une combinaison spécifique."""
        eligible_doctors = self._get_eligible_doctors(combo, day_type)
        groups = self._get_combo_groups(combo, day_type)  # Ajout du day_type ici
        posts = self._get_combo_posts(combo)
        requirements = self._get_posts_requirements(combo, day_type)
        
        ratio = self._calculate_combination_ratio(combo, len(eligible_doctors), day_type)
        status = self._determine_combination_status(ratio)
        
        return {
            "eligible_doctors": [doc.name for doc in eligible_doctors],
            "groups": groups,
            "posts": posts,
            "requirements": requirements,
            "ratio": ratio,
            "status": status
        }

    def _get_eligible_doctors(self, combo: str, day_type: str) -> List[Doctor]:
        """Retourne la liste des médecins pouvant prendre cette combinaison."""
        return [
            doctor for doctor in self.doctors
            if self._can_doctor_take_combo(doctor, combo, day_type)
        ]

    def _can_doctor_take_combo(self, doctor: Doctor, combo: str, day_type: str) -> bool:
        """Vérifie si un médecin peut prendre une combinaison."""
        groups = self._get_combo_groups(combo, day_type)  # Ajout day_type
        doctor_limits = self.pre_analysis_results["ideal_distribution"][doctor.name]

        for group in groups:
            if day_type == "weekend":
                max_allowed = doctor_limits["weekend_groups"][group]["max"]
                current = doctor.weekend_combo_counts.get(group, 0)
            else:
                max_allowed = doctor_limits["weekday_groups"][group]["max"]
                current = doctor.weekday_combo_counts.get(group, 0)
                
            if current >= max_allowed:
                return False
                
        return self._check_doctor_availability(doctor, combo, day_type)

    def _check_doctor_availability(self, doctor: Doctor, combo: str, day_type: str) -> bool:
        """Vérifie les disponibilités du médecin pour la combinaison."""
        post1, post2 = self._get_combo_posts(combo)
        doctor_limits = self.pre_analysis_results["ideal_distribution"][doctor.name]
        
        if day_type == "weekend":
            max_post1 = doctor_limits["weekend_posts"].get(post1, {}).get("max", 0)
            max_post2 = doctor_limits["weekend_posts"].get(post2, {}).get("max", 0)
        else:
            max_post1 = doctor_limits["weekday_posts"].get(post1, {}).get("max", 0)
            max_post2 = doctor_limits["weekday_posts"].get(post2, {}).get("max", 0)
            
        return max_post1 > 0 and max_post2 > 0

    def _check_group_limits(self, doctor: Doctor, combo: str, day_type: str) -> bool:
        """
        Vérifie les limites de groupes pour le médecin.
        """
        groups = self._get_combo_groups(combo, day_type)
        doctor_limits = self.pre_analysis_results["ideal_distribution"][doctor.name]
        
        for group in groups:
            try:
                if day_type == "weekend":
                    current = doctor.weekend_combo_counts.get(group, 0)
                    max_allowed = doctor_limits["weekend_groups"][group]["max"]
                else:
                    current = doctor.weekday_combo_counts.get(group, 0)
                    # Si le groupe n'existe pas ou a une limite de 0, 
                    # la combinaison n'est pas possible
                    if group not in doctor_limits["weekday_groups"]:
                        max_allowed = 0
                    else:
                        max_allowed = doctor_limits["weekday_groups"].get(group, {}).get("max", 0)

                # Si max_allowed est 0, cette combinaison n'est pas possible
                if max_allowed == 0:
                    return False
                    
                if current >= max_allowed:
                    return False
                    
            except KeyError:
                # Si une clé n'existe pas, c'est que le groupe n'est pas disponible
                self.logger.debug(f"Groupe {group} non disponible pour {doctor.name}")
                return False
                    
        return True

    def _get_combo_groups(self, combo: str, day_type: str) -> List[str]:
        """
        Identifie les groupes impactés par une combinaison selon le type de jour.
        """
        groups = set()
        first_post = combo[:2]
        second_post = combo[2:]
        
        if day_type == "weekend":
            # Mapping des postes vers les groupes weekend
            WEEKEND_MAPPING = {
                "ML": "VmS",
                "MC": "VmD",
                "CM": "CmS",
                "HM": "CmS",
                "SM": "CmD",
                "RM": "CmD",
                "CA": "CaSD",
                "HA": "CaSD",
                "SA": "CaSD",
                "RA": "CaSD",
                "CS": "CsSD",
                "HS": "CsSD",
                "SS": "CsSD",
                "RS": "CsSD",
                "AL": "VaSD",
                "AC": "VaSD"
            }
            
            if first_post in WEEKEND_MAPPING:
                groups.add(WEEKEND_MAPPING[first_post])
            if second_post in WEEKEND_MAPPING:
                groups.add(WEEKEND_MAPPING[second_post])
                
        else:
            # Mapping des postes vers les groupes semaine
            WEEKDAY_MAPPING = {
                "MM": "XmM",
                "SM": "XmM",
                "RM": "XmM",
                "CM": "XM",
                "HM": "XM",
                "CA": "XA",
                "HA": "XA",
                "SA": "XA",
                "RA": "XA",
                "CS": "XS",
                "HS": "XS",
                "SS": "XS",
                "RS": "XS",
                "ML": "Vm",
                "MC": "Vm",
            }
            
            if first_post in WEEKDAY_MAPPING:
                groups.add(WEEKDAY_MAPPING[first_post])
            if second_post in WEEKDAY_MAPPING:
                groups.add(WEEKDAY_MAPPING[second_post])

        if not groups:
            self.logger.warning(f"Aucun groupe identifié pour la combinaison {combo} ({day_type})")
        
        return list(groups)
    def _get_combo_posts(self, combo: str) -> Tuple[str, str]:
        """Sépare une combinaison en ses deux postes."""
        return combo[:2], combo[2:]

    def _get_posts_requirements(self, combo: str, day_type: str) -> Dict:
        """Récupère les besoins en postes pour cette combinaison."""
        post1, post2 = self._get_combo_posts(combo)
        if day_type == "weekend":
            return {
                post1: self.pre_analysis_results["weekend_posts"].get(post1, 0),
                post2: self.pre_analysis_results["weekend_posts"].get(post2, 0)
            }
        return {
            post1: self.pre_analysis_results["weekday_posts"].get(post1, 0),
            post2: self.pre_analysis_results["weekday_posts"].get(post2, 0)
        }

    def _calculate_combination_ratio(self, combo: str, eligible_count: int, day_type: str) -> float:
        """Calcule le ratio de disponibilité/besoin pour une combinaison."""
        requirements = self._get_posts_requirements(combo, day_type)
        groups = self._get_combo_groups(combo, day_type)  # Ajout day_type
        needed = max(requirements.values()) if requirements else 0
        return eligible_count / needed if needed > 0 else float('inf')

    def _determine_combination_status(self, ratio: float) -> str:
        """Détermine le statut d'une combinaison basé sur son ratio."""
        if ratio >= 1.2:
            return "OK"
        elif ratio >= 0.8:
            return "ATTENTION"
        return "CRITIQUE"

    def _log_analysis_header(self, day_type: str):
        """Affiche l'en-tête de l'analyse."""
        self.logger.info(f"\nANALYSE DES COMBINAISONS {day_type.upper()}")
        self.logger.info("=" * 100)
        self.logger.info("{:<8} {:<15} {:<25} {:<12} {:<10}".format(
            "COMBO", "ÉLIGIBLES", "GROUPES", "RATIO", "STATUT"
        ))
        self.logger.info("-" * 80)

    def _log_combination_analysis(self, combo: str, analysis: Dict, day_type: str):
        """Log les résultats d'analyse d'une combinaison."""
        self.logger.info("{:<8} {:<15} {:<25} {:<12.2f} {:<10}".format(
            combo,
            f"{len(analysis['eligible_doctors'])}/{len(self.doctors)}",
            "+".join(analysis['groups']),
            analysis['ratio'],
            analysis['status']
        ))


    def _log_summary(self, all_analysis: Dict):
        """Affiche un résumé de l'analyse complète."""
        self.logger.info("\nRÉSUMÉ DE L'ANALYSE DES COMBINAISONS")
        self.logger.info("=" * 100)
        
        for day_type, combinations in all_analysis.items():
            critical = sum(1 for c in combinations.values() if c['status'] == "CRITIQUE")
            attention = sum(1 for c in combinations.values() if c['status'] == "ATTENTION")
            ok = sum(1 for c in combinations.values() if c['status'] == "OK")
            
            self.logger.info(f"\n{day_type.upper()}:")
            self.logger.info(f"Critiques  : {critical}")
            self.logger.info(f"Attention  : {attention}")
            self.logger.info(f"OK        : {ok}")
            
            