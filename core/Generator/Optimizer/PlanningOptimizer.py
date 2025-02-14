# © 2024 HILAL Arkane. Tous droits réservés.
from typing import List, Dict, Set, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import date
import logging
from datetime import date, datetime, time, timedelta
from copy import deepcopy
import random
from collections import defaultdict
from core.Constantes.models import (
    Doctor, CAT, Planning, DayPlanning, TimeSlot, PostManager, PostConfig,SpecificPostConfig,
    ALL_POST_TYPES, WEEKDAY_COMBINATIONS, WEEKEND_COMBINATIONS
)
from core.Constantes.constraints import PlanningConstraints
from core.Constantes.data_persistence import DataPersistence
from core.Constantes.custom_post import CustomPost
from workalendar.europe import France
logger = logging.getLogger(__name__)

@dataclass
class ExchangeProposal:
    """Représente une proposition d'échange entre médecins"""
    doctors: List[str]  # Liste des médecins impliqués
    exchanges: List[Tuple[str, date, str, str]]  # [(post_type, date, from_doctor, to_doctor),...]
    group: str  # Groupe concerné par l'échange

class PlanningOptimizer:
    def __init__(self, planning: Planning, doctors: List[Doctor], 
                intervals: Dict, doctor_states: Dict):
        self.planning = planning
        self.doctors = {d.name: d for d in doctors}
        self.cats = {d.name: d for d in planning.cats}  # Ajout des CATs
        self.intervals = intervals
        # Assurer que doctor_states a la bonne structure
        self.doctor_states = {}
        for doctor_name, state in doctor_states.items():
            self.doctor_states[doctor_name] = {
                'post_counts': state.get('post_counts', {}),
                'group_counts': state.get('group_counts', {}),
                'total_combinations': 0
            }
        
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
        
        # Limites d'itération par niveau
        self.iteration_limits = {
            2: 100,  # 2 médecins
            3: 75,   # 3 médecins
            4: 50,   # 4 médecins
            5: 25    # 5+ médecins
        }
        
        # Cache des médecins par nombre de desiderata
        self.doctors_by_desiderata = self._sort_doctors_by_desiderata()
        
        # Initialisation du calendrier et des contraintes
        self.cal = France()
        self.constraints = PlanningConstraints()

    def optimize(self) -> bool:
        """
        Lance le processus complet d'optimisation.
        Returns:
            bool: True si des améliorations ont été apportées
        """
        try:
            logger.info("\nDÉBUT DE L'OPTIMISATION PAR ÉCHANGES")
            logger.info("=" * 60)
            
            initial_unassigned = self._count_unassigned_posts()
            improved = False
            
            # Phase 1: Échanges simples (2 médecins)
            logger.info("\nPHASE 1: ÉCHANGES ENTRE 2 MÉDECINS")
            if self._optimize_with_n_doctors(2):
                improved = True
                
            # Si encore des postes non attribués, continuer avec plus de médecins
            current_unassigned = self._count_unassigned_posts()
            if current_unassigned > 0:
                for n in range(3, len(self.doctors) + 1):
                    logger.info(f"\nPHASE {n-1}: ÉCHANGES ENTRE {n} MÉDECINS")
                    if self._optimize_with_n_doctors(n):
                        improved = True
                    
                    # Vérifier si tous les postes sont attribués
                    if self._count_unassigned_posts() == 0:
                        break
            
            final_unassigned = self._count_unassigned_posts()
            logger.info("\nRÉSULTAT DE L'OPTIMISATION")
            logger.info(f"Postes non attribués: {initial_unassigned} -> {final_unassigned}")
            
            return improved
            
        except Exception as e:
            logger.error(f"Erreur dans le processus d'optimisation: {e}")
            return False

    def _optimize_with_n_doctors(self, n: int) -> bool:
        """
        Optimise les échanges entre n médecins avec logs détaillés.
        """
        iteration_limit = self.iteration_limits.get(n, 25)
        iterations = 0
        improved = False
        
        logger.info(f"\nDébut optimisation avec {n} médecins")
        logger.info(f"Limite d'itérations: {iteration_limit}")
        
        # Liste des postes non attribués au début
        initial_unassigned = self._get_unassigned_details()
        logger.info("\nPostes non attribués initiaux:")
        for date_str, posts in initial_unassigned.items():
            logger.info(f"{date_str}: {', '.join(posts)}")
        
        while iterations < iteration_limit:
            logger.info(f"\nItération {iterations + 1}/{iteration_limit}")
            
            # 1. Sélection du groupe
            group = self._select_group_with_unassigned()
            if not group:
                logger.info("Aucun groupe avec postes non attribués trouvé")
                break
            logger.info(f"Groupe sélectionné: {group}")
            
            # 2. Recherche des candidats
            candidates = self._find_group_candidates(group, n)
            if len(candidates) < n:
                logger.info(f"Pas assez de candidats ({len(candidates)}/{n})")
                break
            logger.info(f"Candidats trouvés: {candidates}")
            
            # 3. Sélection des médecins
            selected_doctors = self._select_doctors_for_exchange(candidates, n)
            if not selected_doctors:
                logger.info("Pas de médecins sélectionnés")
                continue
            logger.info(f"Médecins sélectionnés: {selected_doctors}")
            
            # 4. Génération des échanges
            exchanges = self._generate_possible_exchanges(selected_doctors, group)
            if not exchanges:
                logger.info("Aucun échange possible trouvé")
                continue
            logger.info(f"Échanges générés: {len(exchanges)} échanges")
            
            # 5. Création de la proposition
            proposal = ExchangeProposal(
                doctors=selected_doctors,
                exchanges=exchanges,
                group=group
            )
            
            # 6. Évaluation et application
            if self._evaluate_exchange_proposal(proposal):
                if self._apply_exchange(proposal):
                    improved = True
                    logger.info("Échange appliqué avec succès")
                    
                    # Vérifier l'impact
                    current_unassigned = self._get_unassigned_details()
                    logger.info("\nNouvel état des postes non attribués:")
                    for date_str, posts in current_unassigned.items():
                        logger.info(f"{date_str}: {', '.join(posts)}")
                else:
                    logger.info("Échec de l'application de l'échange")
            else:
                logger.info("Proposition non retenue après évaluation")
            
            iterations += 1
            
        if improved:
            logger.info("\nOptimisation réussie - Améliorations apportées")
        else:
            logger.info("\nAucune amélioration trouvée")
        
        return improved

    def _generate_exchange_proposal(self, n: int) -> Optional[ExchangeProposal]:
        """
        Génère une proposition d'échange entre n médecins.
        
        Args:
            n: Nombre de médecins à impliquer
            
        Returns:
            ExchangeProposal ou None si pas de proposition possible
        """
        try:
            # 1. Sélectionner un groupe où il y a des postes non attribués
            group = self._select_group_with_unassigned()
            if not group:
                return None
                
            # 2. Trouver les médecins candidats pour ce groupe
            candidates = self._find_group_candidates(group, n)
            if len(candidates) < n:
                return None
                
            # 3. Sélectionner n médecins
            selected_doctors = self._select_doctors_for_exchange(candidates, n)
            if not selected_doctors:
                return None
                
            # 4. Générer les échanges possibles
            exchanges = self._generate_possible_exchanges(selected_doctors, group)
            if not exchanges:
                return None
                
            return ExchangeProposal(
                doctors=selected_doctors,
                exchanges=exchanges,
                group=group
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de proposition: {e}")
            return None

    def _get_unassigned_details(self) -> Dict[str, List[str]]:
        """
        Retourne les détails des postes non attribués par date.
        
        Returns:
            Dict[str, List[str]]: {date_str: [post_types]}
        """
        unassigned = defaultdict(list)
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
            
            date_str = day.date.strftime('%Y-%m-%d')
            for slot in day.slots:
                if not slot.assignee:
                    unassigned[date_str].append(slot.abbreviation)
        
        return dict(unassigned)

    def _evaluate_exchange_proposal(self, proposal: ExchangeProposal) -> bool:
        """
        Évalue si une proposition d'échange améliore le planning.
        Version améliorée avec plus de flexibilité.
        """
        try:
            # Sauvegarder l'état actuel
            current_state = self._save_current_state()
            
            # Appliquer l'échange temporairement
            if not self._apply_exchange(proposal, temporary=True):
                return False
            
            # Calculer les scores avant/après
            before_score = self._calculate_state_score(current_state)
            after_score = self._calculate_current_score()
            
            # Restaurer l'état initial
            self._restore_state(current_state)
            
            # Accepter si amélioration ou égalité avec plus de postes attribués
            if after_score > before_score:
                logger.info(f"Amélioration du score: {before_score} -> {after_score}")
                return True
            elif after_score == before_score:
                # En cas d'égalité, accepter si ça aide les médecins prioritaires
                if self._check_priority_doctors_improvement(proposal):
                    logger.info("Score égal mais amélioration pour médecins prioritaires")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation: {e}")
            return False

    def _apply_exchange(self, proposal: ExchangeProposal, temporary: bool = False) -> bool:
        """
        Applique un échange proposé.
        
        Args:
            proposal: Proposition à appliquer
            temporary: Si True, l'échange est temporaire pour évaluation
            
        Returns:
            bool: True si l'échange a été appliqué avec succès
        """
        try:
            # Vérifier une dernière fois les contraintes
            for exchange in proposal.exchanges:
                post_type, date, from_doctor, to_doctor = exchange
                
                # Vérifier les contraintes pour le nouveau médecin
                day = self.planning.get_day(date)
                if not day:
                    return False
                    
                slot = next((s for s in day.slots 
                        if s.abbreviation == post_type and s.assignee == from_doctor), None)
                if not slot:
                    return False
                    
                # Récupérer le médecin ou le CAT
                if to_doctor in self.doctors:
                    assignee = self.doctors[to_doctor]
                elif to_doctor in self.cats:
                    assignee = self.cats[to_doctor]
                else:
                    return False
                    
                if not self._check_constraints(assignee, date, slot):
                    return False
            
            # Appliquer les échanges
            for exchange in proposal.exchanges:
                post_type, date, from_doctor, to_doctor = exchange
                day = self.planning.get_day(date)
                
                for slot in day.slots:
                    if slot.abbreviation == post_type and slot.assignee == from_doctor:
                        slot.assignee = to_doctor
                        break
            
            # Mettre à jour les états si l'échange n'est pas temporaire
            if not temporary:
                self._update_doctor_states(proposal)
                
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'application de l'échange: {e}")
            return False

    def _sort_doctors_by_desiderata(self) -> List[Tuple[str, int]]:
        """
        Trie les médecins par nombre croissant de desiderata.
        
        Returns:
            List[Tuple[str, int]]: Liste des (nom_médecin, nb_desiderata)
        """
        return sorted(
            [(d.name, len(d.desiderata)) for d in self.doctors.values()],
            key=lambda x: x[1]
        )

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

    def _select_group_with_unassigned(self) -> Optional[str]:
        """
        Sélectionne un groupe avec des postes non attribués ou mal attribués.
        Amélioration : considère aussi les groupes où des échanges pourraient améliorer la situation
        """
        group_scores = defaultdict(float)
        
        # 1. Analyser les postes non attribués
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                group = self._get_post_group(slot.abbreviation, day.date)
                if not group:
                    continue
                    
                # Score pour les postes non attribués
                if not slot.assignee:
                    group_scores[group] += 2.0
                else:
                    # Score pour les violations de desiderata secondaires
                    assignee = self.doctors.get(slot.assignee)
                    if assignee:
                        for desiderata in assignee.desiderata:
                            if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                                desiderata.start_date <= day.date <= desiderata.end_date and
                                desiderata.overlaps_with_slot(slot)):
                                group_scores[group] += 0.5
        
        # 2. Analyser les déséquilibres de groupe
        for doctor_name, state in self.doctor_states.items():
            if doctor_name not in self.doctors:
                continue
                
            intervals = self.intervals.get(doctor_name, {}).get('weekend_groups', {})
            for group, count in state['group_counts'].items():
                if group in intervals:
                    min_val = intervals[group].get('min', 0)
                    max_val = intervals[group].get('max', float('inf'))
                    
                    # Score pour les écarts aux intervalles
                    if count < min_val:
                        group_scores[group] += 1.0
                    elif count > max_val:
                        group_scores[group] += 1.0
        
        if not group_scores:
            return None
            
        # Sélection pondérée par les scores
        groups = list(group_scores.items())
        total_score = sum(score for _, score in groups)
        if total_score == 0:
            return None
            
        rand = random.uniform(0, total_score)
        current = 0
        for group, score in groups:
            current += score
            if current >= rand:
                return group
                
        return groups[-1][0]

    def _find_group_candidates(self, group: str, n: int) -> List[str]:
        """
        Trouve les candidats pour un échange dans un groupe.
        Amélioration : considère plus de critères pour la sélection
        """
        candidates = set()
        
        # 1. Médecins ayant des postes dans ce groupe
        current_assignees = set()
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                if (slot.assignee and 
                    self._get_post_group(slot.abbreviation, day.date) == group):
                    current_assignees.add(slot.assignee)
                    candidates.add(slot.assignee)
        
        # 2. Médecins avec desiderata secondaires affectant ce groupe
        for doctor in self.doctors.values():
            if len(candidates) >= n * 3:  # Plus de candidats pour plus de possibilités
                break
                
            if doctor.name not in candidates:
                has_relevant_desiderata = False
                for desiderata in doctor.desiderata:
                    if getattr(desiderata, 'priority', 'primary') == "secondary":
                        has_relevant_desiderata = True
                        break
                        
                if has_relevant_desiderata:
                    candidates.add(doctor.name)
        
        # 3. Médecins sous leur minimum ou au-dessus de leur maximum
        for doctor_name, state in self.doctor_states.items():
            if doctor_name not in self.doctors or len(candidates) >= n * 3:
                continue
                
            intervals = self.intervals.get(doctor_name, {}).get('weekend_groups', {}).get(group, {})
            current = state['group_counts'].get(group, 0)
            
            if (current < intervals.get('min', 0) or 
                current > intervals.get('max', float('inf'))):
                candidates.add(doctor_name)
        
        # 4. Ajouter d'autres médecins disponibles si nécessaire
        if len(candidates) < n * 2:
            for doctor in self.doctors.values():
                if len(candidates) >= n * 2:
                    break
                if doctor.name not in candidates:
                    candidates.add(doctor.name)
        
        return list(candidates)


    def _select_doctors_for_exchange(self, candidates: List[str], n: int) -> List[str]:
        """
        Sélectionne n médecins parmi les candidats en favorisant ceux avec moins de desiderata.
        
        Args:
            candidates: Liste des médecins candidats
            n: Nombre de médecins à sélectionner
            
        Returns:
            List[str]: Médecins sélectionnés
        """
        if len(candidates) < n:
            return []
            
        # Trier les candidats par nombre de desiderata
        sorted_candidates = []
        for candidate in candidates:
            if candidate in self.doctors:
                sorted_candidates.append((candidate, len(self.doctors[candidate].desiderata)))
            else:
                # Si c'est un CAT, on considère qu'il n'a pas de desiderata
                sorted_candidates.append((candidate, 0))
        
        # Trier par nombre de desiderata
        sorted_candidates.sort(key=lambda x: x[1])
        sorted_candidates = [x[0] for x in sorted_candidates]
        
        # Sélectionner n médecins en favorisant ceux avec moins de desiderata
        # mais en gardant une part d'aléatoire
        selected = []
        remaining = sorted_candidates.copy()
        
        while len(selected) < n and remaining:
            # 70% de chance de prendre le médecin avec le moins de desiderata
            if random.random() < 0.7 and remaining:
                selected.append(remaining.pop(0))
            # 30% de chance de prendre un médecin au hasard
            elif remaining:
                idx = random.randint(0, len(remaining) - 1)
                selected.append(remaining.pop(idx))
        
        return selected if len(selected) == n else []

    def _save_current_state(self) -> Dict:
        """
        Sauvegarde l'état actuel du planning pour comparaison.
        
        Returns:
            Dict: État sauvegardé
        """
        return {
            'unassigned': self._count_unassigned_posts(),
            'secondary_violations': self._count_secondary_desiderata_violations(),
            'doctor_states': deepcopy(self.doctor_states)
        }
    
    def _calculate_state_score(self, state: Dict) -> float:
        """
        Calcule un score pour un état donné.
        """
        score = 0.0
        
        # Pénalité forte pour les postes non attribués
        score -= state['unassigned'] * 100
        
        # Pénalité pour les violations de desiderata secondaires
        score -= state['secondary_violations'] * 10
        
        # Bonus pour les médecins prioritaires respectés
        priority_doctors = [d for d, _ in self.doctors_by_desiderata[:3]]
        for doctor_name in priority_doctors:
            if doctor_name in state['doctor_states']:
                doctor_state = state['doctor_states'][doctor_name]
                # Vérifie si les intervalles sont respectés
                for group, count in doctor_state['group_counts'].items():
                    intervals = self.intervals.get(doctor_name, {}).get('weekend_groups', {}).get(group, {})
                    if intervals:
                        min_val = intervals.get('min', 0)
                        max_val = intervals.get('max', float('inf'))
                        if min_val <= count <= max_val:
                            score += 5
        
        return score

    def _calculate_current_score(self) -> float:
        """
        Calcule le score de l'état actuel.
        """
        return self._calculate_state_score({
            'unassigned': self._count_unassigned_posts(),
            'secondary_violations': self._count_secondary_desiderata_violations(),
            'doctor_states': self.doctor_states
        })
    def _restore_state(self, state: Dict) -> None:
        """
        Restaure un état sauvegardé.
        
        Args:
            state: État à restaurer
        """
        self.doctor_states.clear()
        self.doctor_states.update(deepcopy(state['doctor_states']))

    def _check_constraints(self, assignee: Union[Doctor, CAT], date: date, slot: TimeSlot) -> bool:
        """
        Vérifie toutes les contraintes pour un médecin/CAT et un slot.
        
        Args:
            assignee: Médecin ou CAT à vérifier
            date: Date du slot
            slot: Slot à vérifier
            
        Returns:
            bool: True si toutes les contraintes sont respectées
        """
        try:
            # Si c'est un CAT, on ne vérifie que le chevauchement horaire
            if isinstance(assignee, CAT):
                return self.constraints.check_time_overlap(assignee, date, slot, self.planning)
            
            # Pour un médecin, on vérifie toutes les contraintes
            return all([
                self.constraints.check_nl_constraint(assignee, date, slot, self.planning),
                self.constraints.check_nm_constraint(assignee, date, slot, self.planning),
                self.constraints.check_nm_na_constraint(assignee, date, slot, self.planning),
                self.constraints.check_time_overlap(assignee, date, slot, self.planning),
                self.constraints.check_max_posts_per_day(assignee, date, slot, self.planning),
                self.constraints.check_morning_after_night_shifts(assignee, date, slot, self.planning),
                self.constraints.check_consecutive_night_shifts(assignee, date, slot, self.planning),
                self.constraints.check_consecutive_working_days(assignee, date, slot, self.planning)
            ])
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des contraintes: {e}")
            return False

    def _generate_possible_exchanges(self, selected_doctors: List[str], group: str) -> List[Tuple[str, date, str, str]]:
        """
        Génère les échanges possibles entre médecins.
        Amélioration : maximise les chances de trouver des échanges valides
        """
        try:
            # 1. Collecter les postes échangeables par médecin
            doctor_posts = defaultdict(list)
            violation_scores = defaultdict(float)  # Score de violation par poste
            
            for day in self.planning.days:
                if not (day.is_weekend or day.is_holiday_or_bridge):
                    continue
                    
                for slot in day.slots:
                    if not slot.assignee or slot.assignee not in selected_doctors:
                        continue
                        
                    slot_group = self._get_post_group(slot.abbreviation, day.date)
                    if slot_group != group:
                        continue
                    
                    post_key = (slot.abbreviation, day.date)
                    doctor_posts[slot.assignee].append(post_key)
                    
                    # Calculer un score de violation pour ce poste
                    if slot.assignee in self.doctors:
                        doctor = self.doctors[slot.assignee]
                        for desiderata in doctor.desiderata:
                            if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                                desiderata.start_date <= day.date <= desiderata.end_date and
                                desiderata.overlaps_with_slot(slot)):
                                violation_scores[post_key] += 1
            
            # 2. Générer et évaluer les échanges possibles
            best_exchange = None
            best_score = float('-inf')
            attempts = 0
            max_attempts = 50  # Nombre raisonnable de tentatives
            
            while attempts < max_attempts:
                current_exchange = []
                exchange_score = 0
                posts_taken = defaultdict(list)
                
                # Prioriser les médecins avec plus de violations
                doctors_order = list(selected_doctors)
                random.shuffle(doctors_order)
                doctors_order.sort(
                    key=lambda d: sum(violation_scores[p] for p in doctor_posts[d]),
                    reverse=True
                )
                
                # Tenter de construire un échange complet
                for from_doctor in doctors_order:
                    if not doctor_posts[from_doctor]:
                        continue
                        
                    # Sélectionner préférentiellement des postes avec violations
                    available_posts = doctor_posts[from_doctor].copy()
                    available_posts.sort(key=lambda p: violation_scores[p], reverse=True)
                    
                    for post_info in available_posts:
                        post_type, date = post_info
                        
                        # Choisir un receveur valide
                        potential_receivers = [
                            d for d in selected_doctors
                            if d != from_doctor and len(posts_taken[d]) < len(doctor_posts[d])
                        ]
                        
                        if not potential_receivers:
                            continue
                            
                        # Prioriser les receveurs qui amélioreraient la situation
                        random.shuffle(potential_receivers)
                        for to_doctor in potential_receivers:
                            if self._check_exchange_feasibility(post_type, date, from_doctor, to_doctor):
                                current_exchange.append((post_type, date, from_doctor, to_doctor))
                                posts_taken[to_doctor].append(post_info)
                                exchange_score += violation_scores[post_info]
                                break
                
                # Vérifier si l'échange est valide et meilleur que le précédent
                if self._is_exchange_balanced(current_exchange, selected_doctors):
                    if exchange_score > best_score:
                        best_exchange = current_exchange
                        best_score = exchange_score
                
                attempts += 1
            
            return best_exchange if best_exchange else []
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération des échanges: {e}")
            return []

    def _check_exchange_feasibility(self, post_type: str, date: date, 
                                  from_doctor: str, to_doctor: str) -> bool:
        """
        Vérifie si un échange spécifique est faisable.
        
        Args:
            post_type: Type de poste
            date: Date du poste
            from_doctor: Médecin donnant le poste
            to_doctor: Médecin recevant le poste
            
        Returns:
            bool: True si l'échange est faisable
        """
        try:
            # Récupérer le médecin ou le CAT
            if to_doctor in self.doctors:
                assignee = self.doctors[to_doctor]
            elif to_doctor in self.cats:
                assignee = self.cats[to_doctor]
            else:
                return False
            day = self.planning.get_day(date)
            if not day:
                return False
                
            slot = next((s for s in day.slots 
                      if s.abbreviation == post_type and s.assignee == from_doctor), None)
            if not slot:
                return False
                
            # Vérifier les contraintes
            return self._check_constraints(assignee, date, slot)
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de faisabilité: {e}")
            return False

    def _is_exchange_balanced(self, exchange: List[Tuple[str, date, str, str]], 
                            doctors: List[str]) -> bool:
        """
        Vérifie si un échange est équilibré (chaque médecin donne/reçoit le même nombre de postes).
        
        Args:
            exchange: Liste des échanges
            doctors: Liste des médecins impliqués
            
        Returns:
            bool: True si l'échange est équilibré
        """
        if not exchange:
            return False
            
        given = defaultdict(int)
        received = defaultdict(int)
        
        for _, _, from_doc, to_doc in exchange:
            given[from_doc] += 1
            received[to_doc] += 1
        
        # Vérifier que chaque médecin donne et reçoit le même nombre de postes
        target = len(exchange) // len(doctors)
        for doctor in doctors:
            if given[doctor] != target or received[doctor] != target:
                return False
                
        return True

    def _count_unassigned_posts(self) -> int:
        """
        Compte le nombre de postes non attribués.
        
        Returns:
            int: Nombre de postes non attribués
        """
        count = 0
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
            count += sum(1 for slot in day.slots if not slot.assignee)
        return count

    def _count_secondary_desiderata_violations(self) -> int:
        """
        Compte le nombre de violations des desiderata secondaires.
        
        Returns:
            int: Nombre de violations
        """
        violations = 0
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                if not slot.assignee:
                    continue
                    
                # Ne compter les violations que pour les médecins, pas pour les CATs
                if slot.assignee in self.doctors:
                    doctor = self.doctors[slot.assignee]
                    for desiderata in doctor.desiderata:
                        if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                            desiderata.start_date <= day.date <= desiderata.end_date and
                            desiderata.overlaps_with_slot(slot)):
                            violations += 1
                        
        return violations

    def _check_group_intervals(self, proposal: ExchangeProposal) -> bool:
        """
        Vérifie si une proposition respecte les intervalles de groupe.
        
        Args:
            proposal: Proposition à vérifier
            
        Returns:
            bool: True si les intervalles sont respectés
        """
        for doctor_name in proposal.doctors:
            # Récupérer le médecin ou le CAT
            if doctor_name in self.doctors:
                assignee = self.doctors[doctor_name]
            elif doctor_name in self.cats:
                assignee = self.cats[doctor_name]
            else:
                return False
            group = proposal.group
            
            # Vérifier les intervalles du groupe
            intervals = self.intervals.get(doctor_name, {})
            group_intervals = intervals.get('weekend_groups', {}).get(group, {})
            current = self.doctor_states[doctor_name]['group_counts'].get(group, 0)
            
            if not (group_intervals.get('min', 0) <= current <= group_intervals.get('max', float('inf'))):
                return False
                
        return True

    def _check_priority_doctors_improvement(self, proposal: ExchangeProposal) -> bool:
        """
        Vérifie si la proposition améliore la situation des médecins prioritaires.
        
        Args:
            proposal: Proposition à vérifier
            
        Returns:
            bool: True si la situation est améliorée
        """
        # Les médecins sont déjà triés par nombre de desiderata
        priority_doctors = [d for d, _ in self.doctors_by_desiderata[:3]]
        
        improved = False
        for doctor_name in proposal.doctors:
            if doctor_name in priority_doctors:
                # Vérifier si le médecin prioritaire reçoit moins de violations
                doctor = self.doctors[doctor_name]
                violations_before = self._count_doctor_violations(doctor)
                violations_after = self._count_doctor_violations_after_exchange(doctor, proposal)
                
                if violations_after < violations_before:
                    improved = True
                elif violations_after > violations_before:
                    return False
                    
        return improved

    def _count_doctor_violations(self, doctor: Doctor) -> int:
        """
        Compte les violations de desiderata secondaires pour un médecin.
        
        Args:
            doctor: Médecin à vérifier
            
        Returns:
            int: Nombre de violations
        """
        violations = 0
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                if slot.assignee != doctor.name:
                    continue
                    
                for desiderata in doctor.desiderata:
                    if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                        desiderata.start_date <= day.date <= desiderata.end_date and
                        desiderata.overlaps_with_slot(slot)):
                        violations += 1
                        
        return violations

    def _count_doctor_violations_after_exchange(self, doctor: Doctor, 
                                              proposal: ExchangeProposal) -> int:
        """
        Simule les violations après un échange proposé.
        
        Args:
            doctor: Médecin à vérifier
            proposal: Proposition d'échange
            
        Returns:
            int: Nombre de violations simulées
        """
        violations = 0
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                continue
                
            for slot in day.slots:
                # Simuler l'échange
                assignee = slot.assignee
                for exchange in proposal.exchanges:
                    post_type, date, from_doc, to_doc = exchange
                    if (date == day.date and slot.abbreviation == post_type and
                        assignee == from_doc):
                        assignee = to_doc
                        break
                
                if assignee != doctor.name:
                    continue
                    
                for desiderata in doctor.desiderata:
                    if (getattr(desiderata, 'priority', 'primary') == "secondary" and
                        desiderata.start_date <= day.date <= desiderata.end_date and
                        desiderata.overlaps_with_slot(slot)):
                        violations += 1
                        
        return violations

    def _update_doctor_states(self, proposal: ExchangeProposal) -> None:
        """
        Met à jour les états des médecins après un échange.
        
        Args:
            proposal: Proposition appliquée
        """
        for exchange in proposal.exchanges:
            post_type, date, from_doctor, to_doctor = exchange
            
            # Déterminer le type de jour
            day_type = ("saturday" if date.weekday() == 5 and 
                       not self.is_bridge_day(date) else "sunday_holiday")
            
            # Mettre à jour les compteurs
            self.doctor_states[from_doctor]['post_counts'][day_type][post_type] -= 1
            self.doctor_states[to_doctor]['post_counts'][day_type][post_type] += 1
            
            # Mettre à jour les compteurs de groupe
            group = proposal.group
            self.doctor_states[from_doctor]['group_counts'][group] -= 1
            self.doctor_states[to_doctor]['group_counts'][group] += 1
