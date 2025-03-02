from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple, Set
import random
import logging
from collections import defaultdict
from core.Constantes.models import Doctor, CAT, Planning, DayPlanning, TimeSlot, WEEKDAY_COMBINATIONS, ALL_POST_TYPES, WEEKDAY_PRIORITY_GROUPS, PRIORITY_WEIGHTS
from core.Constantes.constraints import PlanningConstraints
from core.Constantes.day_type import DayType
from core.Constantes.data_persistence import DataPersistence
from core.Constantes.custom_post import CustomPost
from core.Constantes.QuotasTracking import QuotaTracker
from core.Analyzer.availability_matrix import AvailabilityMatrix
from workalendar.europe import France

logger = logging.getLogger(__name__)


class WeekdayGenerator:
    def __init__(self, doctors: List[Doctor], cats: List[CAT], planning: Planning,
                 post_configuration, pre_attributions=None):
        """
        Générateur pour les postes de semaine.
        Ne doit être utilisé qu'après validation des weekends.
        
        Args:
            doctors: Liste des médecins
            cats: Liste des CAT
            planning: Planning à générer
            post_configuration: Configuration des postes
            pre_attributions: Dictionnaire des pré-attributions {person_name: {(date, period): post_type}}
        """
        self.doctors = doctors
        self.cats = cats
        self.planning = planning
        self.post_configuration = post_configuration
        # Filtrer les pré-attributions pour ne garder que la semaine
        self.pre_attributions = self._filter_weekday_pre_attributions(pre_attributions or {})
        self.constraints = PlanningConstraints()
        self.cal = France()

        # Initialisation des compteurs
        self.weekday_counts = {
            doctor.name: {
                'posts': defaultdict(int),  # Compteurs par type de poste
                'groups': defaultdict(int),  # Compteurs par groupe
                'simple_posts': []  # Liste des posts simples à compléter
            } for doctor in self.doctors
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
        
        
    def _initialize_weekday_counts(self) -> None:
        """
        Initialise ou réinitialise les compteurs de semaine.
        Prend en compte les pré-attributions et postes déjà attribués.
        """
        try:
            logger.info("\nINITIALISATION DES COMPTEURS SEMAINE")
            
            # Réinitialiser tous les compteurs
            for doctor_name in self.weekday_counts:
                self.weekday_counts[doctor_name] = {
                    'posts': defaultdict(int),
                    'groups': defaultdict(int),
                    'simple_posts': []
                }
            
            # 1. Compter les pré-attributions
            for person_name, attributions in self.pre_attributions.items():
                if person_name not in self.weekday_counts:
                    continue
                    
                counts = self.weekday_counts[person_name]
                for (date, period), post_type in attributions.items():
                    day = self.planning.get_day(date)
                    if not day or day.is_weekend or day.is_holiday_or_bridge:
                        continue
                        
                    # Incrémenter le compteur de poste
                    counts['posts'][post_type] += 1
                    
                    # Mettre à jour le groupe si nécessaire
                    group = self._get_post_group(post_type, date)
                    if group:
                        counts['groups'][group] += 1
                        
                    # Ajouter aux posts simples si nécessaire
                    if post_type in ["ML", "CM", "CA", "CS", "NM", "NC"]:
                        counts['simple_posts'].append({
                            'date': date,
                            'period': period,
                            'post': post_type
                        })

            # 2. Compter les postes déjà attribués dans le planning
            for day in self.planning.days:
                if day.is_weekend or day.is_holiday_or_bridge:
                    continue
                    
                for slot in day.slots:
                    if not slot.assignee or slot.assignee not in self.weekday_counts:
                        continue
                        
                    counts = self.weekday_counts[slot.assignee]
                    
                    # Ne pas compter deux fois les pré-attributions
                    period = self._get_slot_period(slot)
                    if self._is_pre_attribution(day.date, slot):
                        continue
                        
                    # Incrémenter le compteur de poste
                    counts['posts'][slot.abbreviation] += 1
                    
                    # Mettre à jour le groupe
                    group = self._get_post_group(slot.abbreviation, day.date)
                    if group:
                        counts['groups'][group] += 1

            # Log des compteurs initialisés
            logger.info("\nCompteurs initialisés:")
            for doctor_name, counts in self.weekday_counts.items():
                if any(counts['posts'].values()) or counts['simple_posts']:
                    logger.info(f"\n{doctor_name}:")
                    # Posts individuels
                    for post, count in counts['posts'].items():
                        if count > 0:
                            logger.info(f"{post}: {count}")
                    # Groupes
                    for group, count in counts['groups'].items():
                        if count > 0:
                            logger.info(f"Groupe {group}: {count}")
                    # Posts simples
                    if counts['simple_posts']:
                        logger.info(f"Posts simples: {len(counts['simple_posts'])}")
                        
        except Exception as e:
            logger.error(f"Erreur initialisation compteurs: {e}")
            raise
  

    def _apply_pre_attributions(self) -> bool:
        """
        Applique les pré-attributions au planning avant la génération de semaine.
        Initialise les compteurs et identifie les possibilités de combinaisons.
        """
        try:
            logger.info("\nTRAITEMENT DES PRÉ-ATTRIBUTIONS SEMAINE")
            logger.info("=" * 80)

            # Structure pour suivre les compteurs
            self.weekday_counts = {
                doctor.name: {
                    'posts': defaultdict(int),  # Compteurs par type de poste
                    'groups': defaultdict(int),  # Compteurs par groupe
                    'simple_posts': []  # Liste des posts simples à compléter
                } for doctor in self.doctors
            }

            # Traiter les pré-attributions par date
            success = True
            for person_name, attributions in self.pre_attributions.items():
                person = next((p for p in self.doctors + self.cats if p.name == person_name), None)
                if not person:
                    logger.warning(f"Personne non trouvée : {person_name}")
                    continue

                # Traiter chaque attribution
                for (date, period), post_type in sorted(attributions.items()):
                    day = self.planning.get_day(date)
                    if not day or day.is_weekend or day.is_holiday_or_bridge:
                        continue  # Ignorer weekend/fériés

                    success &= self._process_single_pre_attribution(
                        person, date, period, post_type, day
                    )

            # Log des compteurs initiaux
            self._log_initial_counts()

            # Tenter de compléter les pré-attributions simples
            if success:
                success &= self._complete_pre_attributions()

            return success

        except Exception as e:
            logger.error(f"Erreur dans l'application des pré-attributions: {e}")
            return False

    def _process_single_pre_attribution(self, person, date, period, post_type, day) -> bool:
        """Traite une pré-attribution individuelle."""
        try:
            logger.info(f"\nTraitement pré-attribution: {person.name} - {post_type} - {date}")

            # 1. Trouver le slot correspondant
            matching_slots = [
                slot for slot in day.slots
                if slot.abbreviation == post_type and not slot.assignee
                and self._get_slot_period(slot) == period
            ]

            if not matching_slots:
                logger.error(f"Pas de slot disponible pour {post_type}")
                return False

            slot = matching_slots[0]

            # 2. Vérifier les contraintes
            if not self.constraints.can_assign_to_assignee(person, date, slot, self.planning):
                logger.error(f"Contraintes non respectées")
                return False

            # 3. Mettre à jour les compteurs
            if isinstance(person, Doctor):
                counts = self.weekday_counts[person.name]
                counts['posts'][post_type] += 1

                # Identifier le groupe et mettre à jour
                group = self._get_post_group(post_type, date)
                if group:
                    counts['groups'][group] += 1
                    logger.info(f"Groupe {group} incrémenté")

                # Vérifier si c'est un post simple qui peut être complété
                if post_type in ["ML", "CM", "CA", "CS", "NM", "NC"]:
                    counts['simple_posts'].append({
                        'date': date,
                        'period': period,
                        'post': post_type
                    })
                    logger.info(f"Post simple identifié pour complétion potentielle")

            # 4. Attribuer le slot
            slot.assignee = person.name
            logger.info(f"Attribution réussie")
            return True

        except Exception as e:
            logger.error(f"Erreur traitement pré-attribution: {e}")
            return False

    def _complete_pre_attributions(self) -> bool:
        """
        Tente de compléter les pré-attributions simples en combinaisons.
        Priorité à la complétion avant la distribution générale.
        """
        try:
            logger.info("\nCOMPLÉTION DES PRÉ-ATTRIBUTIONS SIMPLES")
            logger.info("=" * 80)

            success = True
            for doctor_name, counts in self.weekday_counts.items():
                if not counts['simple_posts']:
                    continue

                doctor = next(d for d in self.doctors if d.name == doctor_name)
                logger.info(f"\nTraitement des posts simples pour {doctor_name}")

                # Traiter chaque post simple
                for post_info in counts['simple_posts']:
                    date = post_info['date']
                    period = post_info['period']
                    post = post_info['post']

                    completed = self._try_complete_combination(
                        doctor, date, period, post, counts
                    )
                    if completed:
                        logger.info(f"Combinaison complétée pour {post}")
                    else:
                        logger.warning(f"Impossible de compléter {post}")
                        # Non bloquant - le post reste simple
                        
            return success

        except Exception as e:
            logger.error(f"Erreur complétion pré-attributions: {e}")
            return False

    def _try_complete_combination(self, doctor, date, period, post, counts) -> bool:
        """Tente de compléter un post simple en combinaison valide."""
        try:
            day = self.planning.get_day(date)
            if not day:
                return False

            # Identifier les combinaisons possibles avec ce post
            possible_combos = []
            for combo in WEEKDAY_COMBINATIONS:
                if post in combo[:2]:  # Post en première position
                    second_post = combo[2:]
                    possible_combos.append((second_post, combo))
                elif post in combo[2:]:  # Post en deuxième position
                    first_post = combo[:2]
                    possible_combos.append((first_post, combo))

            # Vérifier les slots disponibles pour chaque possibilité
            for completing_post, combo in possible_combos:
                matching_slots = [
                    slot for slot in day.slots
                    if slot.abbreviation == completing_post 
                    and not slot.assignee
                ]

                for slot in matching_slots:
                    # Vérifier les contraintes et quotas
                    if self._can_complete_combination(
                        doctor, date, slot, completing_post, counts
                    ):
                        # Attribuer le slot complémentaire
                        slot.assignee = doctor.name
                        counts['posts'][completing_post] += 1
                        
                        # Mettre à jour le groupe
                        group = self._get_post_group(completing_post, date)
                        if group:
                            counts['groups'][group] += 1
                            
                        logger.info(f"Combinaison {combo} complétée")
                        return True

            return False

        except Exception as e:
            logger.error(f"Erreur tentative de complétion: {e}")
            return False

    def _can_complete_combination(self, doctor, date, slot, post_type, counts) -> bool:
        """Vérifie si un post peut compléter une combinaison."""
        try:
            # 1. Vérifier les contraintes de base
            if not self.constraints.can_assign_to_assignee(
                doctor, date, slot, self.planning
            ):
                return False

            # 2. Vérifier les quotas de groupe
            group = self._get_post_group(post_type, date)
            if group:
                current = counts['groups'][group]
                intervals = self._get_doctor_weekday_intervals()
                doctor_intervals = intervals.get(doctor.name, {})
                max_allowed = doctor_intervals.get('groups', {}).get(
                    group, {}
                ).get('max', float('inf'))
                
                if current >= max_allowed:
                    return False

            return True

        except Exception as e:
            logger.error(f"Erreur vérification complétion: {e}")
            return False

    def _log_initial_counts(self):
        """Log détaillé des compteurs après pré-attributions."""
        logger.info("\nCOMPTEURS APRÈS PRÉ-ATTRIBUTIONS")
        logger.info("=" * 60)

        for doctor_name, counts in self.weekday_counts.items():
            if any(counts['posts'].values()) or counts['simple_posts']:
                logger.info(f"\n{doctor_name}:")
                
                # Posts individuels
                for post, count in counts['posts'].items():
                    if count > 0:
                        logger.info(f"{post}: {count}")
                        
                # Groupes
                for group, count in counts['groups'].items():
                    if count > 0:
                        logger.info(f"Groupe {group}: {count}")
                        
                # Posts simples à compléter
                if counts['simple_posts']:
                    logger.info("Posts simples à compléter:")
                    for post_info in counts['simple_posts']:
                        logger.info(f"- {post_info['post']} le {post_info['date']}")
                        
    def reset_weekday_slots(self) -> None:
        """
        Réinitialise les slots de semaine avant une nouvelle génération.
        Préserve les NLv du vendredi et les pré-attributions.
        """
        try:
            logger.info("\nRÉINITIALISATION DES SLOTS DE SEMAINE")
            logger.info("=" * 60)
            
            # Initialisation des compteurs
            slots_cleared = 0
            pre_attributions_preserved = 0
            nlv_preserved = 0
            
            # Debug des pré-attributions déjà filtrées
            logger.info("\nContenu des pré-attributions semaine:")
            if not self.pre_attributions:
                logger.warning("Aucune pré-attribution trouvée")
            for person_name, attributions in self.pre_attributions.items():
                logger.info(f"\n{person_name}:")
                for (date, period), post_type in attributions.items():
                    logger.info(f"  - {post_type} le {date} (période {period})")

            # Parcours des jours
            for day in self.planning.days:
                if day.is_weekend or day.is_holiday_or_bridge:
                    continue

                is_friday = day.date.weekday() == 4
                logger.debug(f"\nTraitement du {day.date}:")

                for slot in day.slots:
                    if not slot.assignee:
                        continue

                    # Conserver les NLv du vendredi
                    if is_friday and slot.abbreviation == "NL":
                        nlv_preserved += 1
                        logger.debug(f"NLv préservé pour {slot.assignee}")
                        continue

                    # Vérifier si c'est une pré-attribution
                    period = self._get_slot_period(slot)
                    is_pre_attributed = False

                    if slot.assignee in self.pre_attributions:
                        person_attrs = self.pre_attributions[slot.assignee]
                        if (day.date, period) in person_attrs:
                            expected_post = person_attrs[(day.date, period)]
                            if expected_post == slot.abbreviation:
                                is_pre_attributed = True
                                pre_attributions_preserved += 1
                                logger.debug(f"Pré-attribution préservée: {slot.assignee} - "
                                        f"{slot.abbreviation} le {day.date} (période {period})")

                    if not is_pre_attributed:
                        slot.assignee = None
                        slots_cleared += 1
                        logger.debug(f"Slot réinitialisé: {slot.abbreviation}")

            # Log des résultats
            logger.info(f"Slots réinitialisés: {slots_cleared}")
            logger.info(f"NLv préservés: {nlv_preserved}")
            logger.info(f"Pré-attributions préservées: {pre_attributions_preserved}")

            # Vérification de cohérence
            expected_pre_attributions = sum(
                1 for attributions in self.pre_attributions.values()
                for _ in attributions.items()
            )

            if pre_attributions_preserved != expected_pre_attributions:
                logger.warning(
                    f"Incohérence dans les pré-attributions préservées: "
                    f"{pre_attributions_preserved} vs {expected_pre_attributions} attendues"
                )

                # Log détaillé des manques
                for person_name, attributions in self.pre_attributions.items():
                    for (date, period), post_type in attributions.items():
                        day = self.planning.get_day(date)
                        is_preserved = any(
                            slot.assignee == person_name and 
                            slot.abbreviation == post_type and 
                            self._get_slot_period(slot) == period
                            for slot in day.slots
                        )
                        if not is_preserved:
                            logger.warning(f"Pré-attribution non préservée: {person_name} - "
                                    f"{post_type} le {date} (période {period})")

        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation des slots: {e}")
            raise

    def _get_slot_period(self, slot: TimeSlot) -> int:
        """
        Détermine la période d'un slot (1:matin, 2:après-midi, 3:soir).
        Aligné avec la logique de pre_attribution_view.py.
        """
        try:
            # Poste personnalisé
            if slot.abbreviation in self.custom_posts:
                custom_post = self.custom_posts[slot.abbreviation]
                start_hour = custom_post.start_time.hour
                
                if 7 <= start_hour < 13 and slot.abbreviation != "CT":  # CT toujours en après-midi
                    return 1
                elif (13 <= start_hour < 18) or slot.abbreviation == "CT":
                    return 2
                else:
                    return 3
            
            # Posts du matin (7h-12h59)
            if slot.abbreviation in ["MM", "CM", "HM", "SM", "RM", "ML", "MC"]:
                return 1
            # Posts de l'après-midi (13h-17h59)
            elif slot.abbreviation in ["CA", "HA", "SA", "RA", "AL", "AC", "CT"]:  # CT inclus ici
                return 2
            # Posts du soir (18h-6h59)
            elif slot.abbreviation in ["CS", "HS", "SS", "RS", "NA", "NM", "NC", "NL"]:
                return 3
                    
            logger.warning(f"Période indéterminée pour le poste: {slot.abbreviation}")
            return 3  # Par défaut période soir
            
        except Exception as e:
            logger.error(f"Erreur détermination période: {e}")
            return 3  # Par défaut période soir
            
    def reset_distribution_state(self) -> None:
        """
        Réinitialise les compteurs de distribution pour les médecins.
        Conserve les compteurs de weekends et pré-attributions.
        """
        try:
            logger.info("Réinitialisation des compteurs de distribution")
            
            # Réinitialiser pour chaque médecin
            for doctor in self.doctors:
                # Compter les postes actuels (incluant les pré-attributions)
                current_counts = self._get_doctor_weekday_counts(doctor, self.planning)
                
                # Calculer les compteurs de groupe
                group_counts = defaultdict(int)
                for post_type, count in current_counts.items():
                    group = self._get_post_group(post_type, datetime.now().date())
                    if group:
                        group_counts[group] += count
                
                logger.debug(f"Compteurs réinitialisés pour {doctor.name}:")
                logger.debug(f"Postes: {dict(current_counts)}")
                logger.debug(f"Groupes: {dict(group_counts)}")
                
        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation des compteurs: {e}")
    
    def _get_doctor_weekday_counts(self, doctor: Doctor, planning: Planning) -> Dict[str, int]:
        """
        Compte les postes de semaine actuellement attribués à un médecin.
        
        Args:
            doctor: Le médecin à vérifier
            planning: Le planning à analyser
            
        Returns:
            Dict[str, int]: Nombre de postes par type
        """
        counts = defaultdict(int)
        for day in planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge):
                for slot in day.slots:
                    if slot.assignee == doctor.name:
                        counts[slot.abbreviation] += 1
        return dict(counts)


    def _filter_weekday_pre_attributions(self, pre_attributions: Dict) -> Dict:
        """
        Filtre les pré-attributions pour ne garder que celles de la semaine.
        Exclut les weekends et jours fériés.
        """
        weekday_pre_attributions = {}
        for person_name, attributions in pre_attributions.items():
            weekday_attrs = {}
            for (date, period), post_type in attributions.items():
                day = self.planning.get_day(date)
                if day and not (day.is_weekend or day.is_holiday_or_bridge):
                    weekday_attrs[(date, period)] = post_type
            if weekday_attrs:
                weekday_pre_attributions[person_name] = weekday_attrs
                
        logger.info(f"\nPré-attributions semaine filtrées:")
        for person, attrs in weekday_pre_attributions.items():
            logger.info(f"\n{person}:")
            for (date, period), post_type in attrs.items():
                logger.info(f"  - {post_type} le {date} (période {period})")
                
        return weekday_pre_attributions

    def full_weekday_reset(self) -> None:
        """
        Effectue une réinitialisation complète de la partie semaine.
        """
        try:
            # 1. Initialiser les compteurs
            self._initialize_weekday_counts()
            
            # 2. Réinitialiser les slots
            self.reset_weekday_slots()
            
            # 3. Vérifier les compteurs après reset
            total_pre_attrs = sum(
                1 for counts in self.weekday_counts.values()
                for count in counts['posts'].values()
            )
            logger.info(f"Pré-attributions comptabilisées après reset: {total_pre_attrs}")
            
        except Exception as e:
            logger.error(f"Erreur reset semaine: {e}")
            raise

    def _is_pre_attribution(self, date: date, slot: TimeSlot) -> bool:
        """
        Vérifie si un slot correspond à une pré-attribution.
        """
        period = self._get_slot_period(slot)
        return any(
            slot.assignee == person_name and
            (date, period) in attributions and
            attributions[(date, period)] == slot.abbreviation
            for person_name, attributions in self.pre_attributions.items()
        )

    def distribute_weekday_nl(self) -> bool:
        try:
            logger.info("\nDISTRIBUTION DES NL SEMAINE")
            logger.info("=" * 80)

            # 1. Get quotas from pre-analysis
            pre_analysis = self.planning.pre_analysis_results
            if not pre_analysis:
                logger.error("Pré-analyse manquante")
                return False

            # 2. Calculate adjusted quotas for each doctor
            doctor_nl_quotas = {}
            for doctor in self.doctors:
                # Get intervals from pre-analysis
                intervals = pre_analysis['ideal_distribution'].get(doctor.name, {})
                nl_interval = intervals.get('weekday_posts', {}).get('NL', {})
                
                # Count pre-attributed NLs
                pre_attributed = self.weekday_counts[doctor.name]['posts'].get('NL', 0)
                
                # Calculate remaining quota
                min_required = nl_interval.get('min', 0)
                max_allowed = nl_interval.get('max', float('inf'))
                
                # Important: Check if pre-attributions already exceed maximum
                if pre_attributed > max_allowed:
                    logger.error(f"{doctor.name}: Pré-attributions ({pre_attributed}) "
                            f"dépassent le maximum autorisé ({max_allowed})")
                    return False
                
                doctor_nl_quotas[doctor.name] = {
                    'min': max(0, min_required - pre_attributed),
                    'max': max(0, max_allowed - pre_attributed),
                    'current': pre_attributed,
                    'absolute_max': max_allowed  # Store absolute maximum for verification
                }
                
                logger.info(f"\n{doctor.name}:")
                logger.info(f"NL pré-attribuées: {pre_attributed}")
                logger.info(f"Maximum absolu: {max_allowed}")
                logger.info(f"Quota restant: [{doctor_nl_quotas[doctor.name]['min']}-"
                        f"{doctor_nl_quotas[doctor.name]['max']}]")

            # 3. Collect available NL slots
            nl_slots = []
            for day in self.planning.days:
                if day.is_weekend or day.is_holiday_or_bridge or day.date.weekday() == 4:
                    continue
                    
                for slot in day.slots:
                    if slot.abbreviation == "NL" and not slot.assignee:
                        nl_slots.append((day.date, slot))

            logger.info(f"\nSlots NL disponibles: {len(nl_slots)}")

            # 4. Priority distribution to doctors under minimum
            for doctor in sorted(self.doctors, 
                            key=lambda d: (doctor_nl_quotas[d.name]['min'], -d.half_parts),
                            reverse=True):
                quotas = doctor_nl_quotas[doctor.name]
                
                if quotas['min'] <= 0:  # Minimum already reached
                    continue
                    
                logger.info(f"\nDistribution minimum pour {doctor.name}")
                nl_needed = quotas['min']
                
                slots_tried = 0
                while nl_needed > 0 and slots_tried < len(nl_slots):
                    date, slot = nl_slots[slots_tried]
                    
                    # Strict maximum check
                    if quotas['current'] >= quotas['absolute_max']:
                        logger.warning(f"{doctor.name}: Maximum absolu atteint ({quotas['absolute_max']})")
                        break
                    
                    if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                        # Attribution and counter update
                        slot.assignee = doctor.name
                        self.weekday_counts[doctor.name]['posts']['NL'] += 1
                        quotas['current'] += 1
                        nl_needed -= 1
                        nl_slots.pop(slots_tried)
                        logger.info(f"NL attribuée le {date} ({quotas['current']}/{quotas['absolute_max']})")
                    else:
                        slots_tried += 1

            # 5. Balanced distribution of remaining slots
            while nl_slots:
                random.shuffle(self.doctors)
                assigned = False
                
                for doctor in self.doctors:
                    quotas = doctor_nl_quotas[doctor.name]
                    
                    # Strict maximum check
                    if quotas['current'] >= quotas['absolute_max']:
                        continue
                        
                    date, slot = nl_slots[0]
                    if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                        slot.assignee = doctor.name
                        self.weekday_counts[doctor.name]['posts']['NL'] += 1
                        quotas['current'] += 1
                        nl_slots.pop(0)
                        assigned = True
                        logger.info(f"{doctor.name}: NL attribuée le {date} "
                                f"(total: {quotas['current']}/{quotas['absolute_max']})")
                        break
                        
                if not assigned:
                    logger.warning("Plus d'attribution possible")
                    break

            # 6. Final verification
            for doctor_name, quotas in doctor_nl_quotas.items():
                if quotas['current'] > quotas['absolute_max']:
                    logger.error(f"{doctor_name}: Maximum dépassé "
                            f"({quotas['current']}/{quotas['absolute_max']})")
                    return False

            return True

        except Exception as e:
            logger.error(f"Erreur distribution NL semaine: {e}", exc_info=True)
            return False

    def _collect_weekday_nl_slots(self) -> List[Tuple[date, TimeSlot]]:
        """Collecte tous les slots NL de semaine disponibles."""
        nl_slots = []

        for day in self.planning.days:
            # Ne prendre que lundi à jeudi
            if (day.is_weekend or day.is_holiday_or_bridge or
                day.date.weekday() == 4):  # Exclure vendredi
                continue

            for slot in day.slots:
                if slot.abbreviation == "NL" and not slot.assignee:
                    nl_slots.append((day.date, slot))

        logger.info(f"\nSlots NL semaine disponibles: {len(nl_slots)}")
        return nl_slots

    def _distribute_nl_to_cats(self, nl_slots: List[Tuple[date, TimeSlot]], 
                             total_quota: int) -> bool:
        """Distribution des NL de semaine aux CAT."""
        try:
            logger.info("\nDISTRIBUTION NL SEMAINE AUX CAT")
            quota_per_cat = total_quota // len(self.cats)
            available_slots = nl_slots.copy()
            
            # Distribution par CAT
            for cat in self.cats:
                slots_assigned = 0
                
                while slots_assigned < quota_per_cat and available_slots:
                    random.shuffle(available_slots)
                    assigned = False
                    
                    for slot_index in range(len(available_slots)):
                        date, slot = available_slots[slot_index]
                        
                        if self.constraints.can_assign_to_assignee(cat, date, slot, 
                                                                 self.planning):
                            slot.assignee = cat.name
                            available_slots.pop(slot_index)
                            slots_assigned += 1
                            assigned = True
                            logger.info(f"CAT {cat.name}: NL attribué le {date} "
                                      f"({slots_assigned}/{quota_per_cat})")
                            break
                            
                    if not assigned:
                        logger.warning(f"Impossible d'attribuer plus de NL à {cat.name}")
                        break
                        
                if slots_assigned < quota_per_cat:
                    logger.warning(f"CAT {cat.name}: quota non atteint "
                                 f"({slots_assigned}/{quota_per_cat})")
                    
            return True
            
        except Exception as e:
            logger.error(f"Erreur distribution NL CAT: {e}")
            return False

    def _distribute_nl_to_doctors(self, nl_slots: List[Tuple[date, TimeSlot]], 
                                total_quota: int) -> bool:
        try:
            logger.info("\nDISTRIBUTION NL SEMAINE AUX MÉDECINS")
            
            # Récupérer les intervalles depuis la distribution idéale
            pre_analysis = self.planning.pre_analysis_results
            if not pre_analysis or 'ideal_distribution' not in pre_analysis:
                logger.error("Pré-analyse ou distribution idéale manquante")
                return False

            # Initialiser les compteurs avec les intervalles de la pré-analyse
            doctor_counts = {}
            for doctor in self.doctors:
                # Récupérer les intervalles de la pré-analyse
                intervals = pre_analysis['ideal_distribution'][doctor.name]['weekday_posts'].get('NL', {})
                
                # Compter les NL déjà attribués (pré-attributions)
                current_nl = self.weekday_counts[doctor.name]['posts'].get('NL', 0)
                
                doctor_counts[doctor.name] = {
                    "NL": current_nl,  # Partir des NL déjà attribués
                    "min": intervals.get('min', 0),
                    "max": intervals.get('max', float('inf')),
                    "remaining_min": max(0, intervals.get('min', 0) - current_nl),
                    "remaining_max": max(0, intervals.get('max', float('inf')) - current_nl)
                }

            logger.info("\nIntervalles NL semaine par médecin:")
            for doctor in self.doctors:
                counts = doctor_counts[doctor.name]
                logger.info(f"{doctor.name}: "
                        f"Actuel: {counts['NL']}, "
                        f"Intervalle: [{counts['min']}-{counts['max']}], "
                        f"Restant: [{counts['remaining_min']}-{counts['remaining_max']}]")

            def get_doctor_score(doctor_name, date):
                """Calcule un score pour un médecin à une date donnée."""
                counts = doctor_counts[doctor_name]
                if counts['NL'] >= counts['max']:
                    return -float('inf')  # Exclure si maximum atteint
                    
                # Score basé sur l'écart au minimum
                if counts['NL'] < counts['min']:
                    score = 3 * (counts['min'] - counts['NL'])  # Priorité haute si sous minimum
                else:
                    score = counts['max'] - counts['NL']  # Score normal sinon

                # Pénalité pour les NL proches
                for day in self.planning.days:
                    if day.date == date:
                        continue
                    delta_days = abs((date - day.date).days)
                    for slot in day.slots:
                        if slot.assignee == doctor_name and slot.abbreviation == "NL":
                            if delta_days < 7:
                                score -= (7 - delta_days) * 2

                score += random.uniform(0, 1)  # Facteur aléatoire réduit
                return max(0, score)

            # Phase 1: Distribution du minimum requis
            logger.info("\nPHASE 1: Distribution minimale")
            available_slots = [s for s in nl_slots if not s[1].assignee]
            
            while available_slots and any(counts['NL'] < counts['min'] 
                                        for counts in doctor_counts.values()):
                best_assignment = None
                best_score = -float('inf')
                
                sample_size = min(5, len(available_slots))
                sample_slots = random.sample(available_slots, sample_size)
                
                for date, slot in sample_slots:
                    for doctor in self.doctors:
                        counts = doctor_counts[doctor.name]
                        if counts['NL'] >= counts['min'] or counts['NL'] >= counts['max']:
                            continue
                            
                        if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                            score = get_doctor_score(doctor.name, date)
                            if score > best_score:
                                best_score = score
                                best_assignment = (doctor, date, slot)
                
                if best_assignment:
                    doctor, date, slot = best_assignment
                    slot.assignee = doctor.name
                    doctor_counts[doctor.name]['NL'] += 1
                    available_slots.remove((date, slot))
                    logger.info(f"{doctor.name}: NL attribué le {date} "
                            f"({doctor_counts[doctor.name]['NL']}/{doctor_counts[doctor.name]['min']})")
                else:
                    if available_slots:
                        available_slots.pop(0)

            # Phase 2: Distribution équilibrée avec respect strict des maximums
            logger.info("\nPHASE 2: Distribution équilibrée")
            while available_slots:
                doctors_list = list(self.doctors)
                random.shuffle(doctors_list)
                assigned = False
                
                for doctor in doctors_list:
                    counts = doctor_counts[doctor.name]
                    if counts['NL'] >= counts['max']:
                        continue
                    
                    for slot_index in range(len(available_slots)):
                        date, slot = available_slots[slot_index]
                        if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                            slot.assignee = doctor.name
                            counts['NL'] += 1
                            available_slots.pop(slot_index)
                            assigned = True
                            logger.info(f"{doctor.name}: NL attribué le {date} "
                                    f"(total: {counts['NL']}/{counts['max']})")
                            break
                            
                    if assigned:
                        break
                        
                if not assigned:
                    logger.warning("Plus aucune attribution possible")
                    break

            # Vérification finale détaillée
            success = True
            for doctor_name, counts in doctor_counts.items():
                logger.info(f"\n{doctor_name}:")
                logger.info(f"NL attribués: {counts['NL']}")
                logger.info(f"Intervalle: [{counts['min']}-{counts['max']}]")
                
                if counts['NL'] < counts['min']:
                    logger.warning(f"Minimum non atteint: {counts['NL']}/{counts['min']}")
                    success = False
                elif counts['NL'] > counts['max']:
                    logger.error(f"Maximum dépassé: {counts['NL']}/{counts['max']}")
                    success = False
                else:
                    logger.info("Distribution OK")
                    
            return success
                
        except Exception as e:
            logger.error(f"Erreur distribution NL médecins: {e}")
            return False
    
    def _verify_nl_distribution(self, quotas: Dict):
        """Vérification finale de la distribution NL."""
        logger.info("\nVÉRIFICATION DISTRIBUTION NL")
        logger.info("=" * 60)
        
        for doctor_name, quota in quotas.items():
            logger.info(f"\n{doctor_name}:")
            if quota['current'] < quota['min']:
                logger.warning(f"Minimum non atteint: {quota['current']}/{quota['min']}")
            elif quota['current'] > quota['max']:
                logger.error(f"Maximum dépassé: {quota['current']}/{quota['max']}")
            else:
                logger.info(f"OK: {quota['current']} [{quota['min']}-{quota['max']}]")
                
                

    def distribute_weekday_nanm(self) -> bool:
        """
        Distribution des NA, NM et NC de semaine avec une logique améliorée.
        """
        try:
            logger.info("\nDISTRIBUTION DES NA/NM/NC SEMAINE")
            logger.info("=" * 80)

            # 1. Récupération et initialisation des intervalles
            intervals = self._get_doctor_weekday_intervals()
            if not intervals:
                return False

            # 2. Récupération des quotas
            quotas = self._get_nanm_quotas()
            if not quotas:
                return False

            # 3. Organisation des slots
            available_slots = self._collect_and_organize_nanm_slots()
            if not available_slots:
                logger.error("Aucun slot NANM disponible")
                return False

            # 4. Distribution aux CAT
            if not self._distribute_weekday_nanm_to_cats(available_slots, quotas['cats']):
                logger.warning("Distribution CAT incomplète - continuation")

            # 5. Distribution médecins en trois phases
            # Phase 1: Veille des NL - Passage des intervals
            self._distribute_nam_before_nl(available_slots, intervals)
            
            # Phase 2: Distribution minimale
            if not self._distribute_nanm_minimum_to_doctors(
                available_slots, quotas['doctors'], intervals
            ):
                logger.warning("Distribution minimale médecins incomplète")

            # Phase 3: Distribution équilibrée
            if not self._distribute_remaining_nanm_to_doctors(available_slots, intervals):
                logger.warning("Distribution équilibrée incomplète")

            # 6. Vérification finale
            unassigned = self._count_unassigned_nanm(available_slots)
            if unassigned > 0:
                logger.warning(f"{unassigned} slots NANM non attribués")

            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution NANM: {e}", exc_info=True)
            return False
    
    def _get_nanm_quotas(self) -> Optional[Dict]:
        """
        Récupère et ajuste les quotas NANM en tenant compte des pré-attributions.
        """
        try:
            pre_analysis = self.planning.pre_analysis_results
            if not pre_analysis:
                logger.error("Pré-analyse manquante")
                return None

            # Quotas CAT
            cat_count = len(self.cats)
            cat_quotas = {
                post_type: pre_analysis["cat_posts"]["weekday"].get(post_type, 0) * cat_count
                for post_type in ["NA", "NM", "NC"]
            }

            # Quotas médecins
            med_quotas = {
                post_type: pre_analysis["adjusted_posts"]["weekday"].get(post_type, 0)
                for post_type in ["NA", "NM", "NC"]
            }

            # Déduire les pré-attributions
            for doctor_name, counts in self.weekday_counts.items():
                for post_type in ["NA", "NM", "NC"]:
                    pre_attributed = counts['posts'].get(post_type, 0)
                    if pre_attributed > 0:
                        med_quotas[post_type] = max(0, med_quotas[post_type] - pre_attributed)
                        logger.info(f"{doctor_name}: {pre_attributed} {post_type} pré-attribué(s)")

            # Log des quotas ajustés
            logger.info("\nQUOTAS NANM AJUSTÉS:")
            for post_type in ["NA", "NM", "NC"]:
                logger.info(f"{post_type} CAT: {cat_quotas[post_type]}")
                logger.info(f"{post_type} MED: {med_quotas[post_type]}")

            return {'cats': cat_quotas, 'doctors': med_quotas}

        except Exception as e:
            logger.error(f"Erreur récupération quotas: {e}")
            return None

    
        
    def _collect_and_organize_nanm_slots(self) -> Dict:
        """
        Collecte et organise les slots NANM par criticité.
        """
        slots = {
            post_type: {
                'critical': [],    # < 40% médecins disponibles
                'standard': [],    # >= 40% médecins disponibles
                'all': []          # Tous les slots
            }
            for post_type in ["NA", "NM", "NC"]
        }

        # Parcourir les jours du planning
        for day in self.planning.days:
            if day.is_weekend or day.is_holiday_or_bridge:
                continue

            # Calculer le pourcentage de médecins disponibles
            available_doctors = sum(
                1 for doctor in self.doctors
                if self._is_doctor_available_for_weekday(doctor, day.date)
            )
            availability = (available_doctors / len(self.doctors)) * 100

            for slot in day.slots:
                if slot.abbreviation in ["NA", "NM", "NC"] and not slot.assignee:
                    slots[slot.abbreviation]['all'].append((day.date, slot))
                    
                    if availability < 40:
                        slots[slot.abbreviation]['critical'].append((day.date, slot))
                    else:
                        slots[slot.abbreviation]['standard'].append((day.date, slot))

        # Log des slots disponibles
        for post_type in ["NA", "NM", "NC"]:
            logger.info(f"\nSlots {post_type}:")
            logger.info(f"Critique: {len(slots[post_type]['critical'])}")
            logger.info(f"Standard: {len(slots[post_type]['standard'])}")
            logger.info(f"Total: {len(slots[post_type]['all'])}")

        return slots
    
    
    def _distribute_weekday_nanm_to_cats(self, available_slots: Dict, quotas: Dict) -> bool:
        """
        Distribution améliorée des NA, NM et NC de semaine aux CAT.
        Priorise les périodes critiques.
        """
        try:
            logger.info("\nDISTRIBUTION NANM SEMAINE AUX CAT")
            logger.info("=" * 60)

            # Pour chaque type de poste
            for post_type in ["NA", "NM", "NC"]:
                quota_per_cat = quotas[post_type] // len(self.cats)
                if quota_per_cat == 0:
                    continue

                logger.info(f"\nDistribution {post_type}:")
                logger.info(f"Quota par CAT: {quota_per_cat}")

                # Phase 1: Distribution sur les périodes critiques
                self._distribute_critical_nanm_to_cats(
                    post_type,
                    available_slots[post_type]['critical'],
                    quota_per_cat
                )

                # Phase 2: Distribution sur les périodes standard
                self._distribute_standard_nanm_to_cats(
                    post_type,
                    available_slots[post_type]['standard'],
                    quota_per_cat
                )

            return True

        except Exception as e:
            logger.error(f"Erreur distribution NANM CAT: {e}")
            return False

    def _distribute_critical_nanm_to_cats(self, post_type: str, 
                                        critical_slots: List[Tuple[date, TimeSlot]],
                                        quota_per_cat: int) -> None:
        """Distribution des slots critiques aux CAT."""
        if not critical_slots:
            return

        logger.info(f"\nDistribution des slots critiques {post_type}")
        cats = list(self.cats)
        random.shuffle(cats)  # Ordre aléatoire des CAT

        for cat in cats:
            slots_assigned = 0
            slots_to_process = critical_slots.copy()
            random.shuffle(slots_to_process)

            while slots_assigned < quota_per_cat and slots_to_process:
                date, slot = slots_to_process.pop(0)
                
                if not slot.assignee and self.constraints.can_assign_to_assignee(
                    cat, date, slot, self.planning
                ):
                    slot.assignee = cat.name
                    slots_assigned += 1
                    critical_slots.remove((date, slot))
                    logger.info(f"CAT {cat.name}: {post_type} critique attribué le {date}")

    def _distribute_standard_nanm_to_cats(self, post_type: str,
                                        standard_slots: List[Tuple[date, TimeSlot]],
                                        quota_per_cat: int) -> None:
        """Distribution des slots standard aux CAT."""
        if not standard_slots:
            return

        logger.info(f"\nDistribution des slots standard {post_type}")
        cats = list(self.cats)
        random.shuffle(cats)

        for cat in cats:
            # Compter les slots déjà attribués
            current_count = sum(
                1 for day in self.planning.days
                for slot in day.slots
                if slot.assignee == cat.name and slot.abbreviation == post_type
            )

            # Continuer l'attribution si nécessaire
            remaining = quota_per_cat - current_count
            if remaining <= 0:
                continue

            slots_to_process = standard_slots.copy()
            random.shuffle(slots_to_process)

            for date, slot in slots_to_process:
                if remaining <= 0:
                    break

                if not slot.assignee and self.constraints.can_assign_to_assignee(
                    cat, date, slot, self.planning
                ):
                    slot.assignee = cat.name
                    standard_slots.remove((date, slot))
                    remaining -= 1
                    logger.info(f"CAT {cat.name}: {post_type} standard attribué le {date}")



    def _distribute_nam_before_nl(self, available_slots: Dict, intervals: Dict) -> None:
        """
        Distribution prioritaire des NA/NM/NC la veille des NL.
        Prend en compte les pré-attributions existantes.
        """
        try:
            logger.info("\nDISTRIBUTION NAM AVANT NL")
            logger.info("=" * 60)

            # Liste des noms des médecins pour vérification rapide
            doctor_names = {doctor.name for doctor in self.doctors}
            
            # Parcourir les jours du planning
            for day in self.planning.days:
                if day.is_weekend or day.is_holiday_or_bridge:
                    continue

                # Chercher les NL du lendemain
                next_day = self.planning.get_day(day.date + timedelta(days=1))
                if not next_day:
                    continue

                # Ne traiter que les NL attribuées aux médecins
                nl_slots = [
                    slot for slot in next_day.slots 
                    if slot.abbreviation == "NL" 
                    and slot.assignee 
                    and slot.assignee in doctor_names
                ]

                if not nl_slots:
                    continue

                # Pour chaque NL trouvée
                for nl_slot in nl_slots:
                    doctor_name = nl_slot.assignee
                    doctor = next(d for d in self.doctors if d.name == doctor_name)
                    doctor_intervals = intervals[doctor.name]

                    # Vérifier d'abord les compteurs existants
                    current_counts = doctor_intervals['current_counts'].copy()
                    if doctor_name in self.weekday_counts:
                        # Intégrer les pré-attributions dans les compteurs actuels
                        for post_type, count in self.weekday_counts[doctor_name]['posts'].items():
                            current_counts['posts'][post_type] = current_counts['posts'].get(post_type, 0) + count
                        for group, count in self.weekday_counts[doctor_name]['groups'].items():
                            current_counts['groups'][group] = current_counts['groups'].get(group, 0) + count

                    # Vérifier si on peut encore ajouter au groupe NMC
                    current_nmc = current_counts['groups'].get('NMC', 0)
                    max_nmc = doctor_intervals['groups'].get('NMC', {}).get('max', float('inf'))
                    
                    if current_nmc >= max_nmc:
                        logger.info(f"{doctor_name}: Maximum du groupe NMC atteint ({current_nmc}/{max_nmc})")
                        continue

                    # Log de l'état actuel avant attribution
                    logger.info(f"\nAnalyse pour {doctor_name} avant NL du {next_day.date}:")
                    logger.info(f"Compteur NMC actuel: {current_nmc}/{max_nmc}")
                    for post_type in ["NM", "NA", "NC"]:
                        current = current_counts['posts'].get(post_type, 0)
                        logger.info(f"{post_type}: {current}")

                    # Chercher un slot NAM disponible la veille
                    assigned = False
                    for post_type in ["NM", "NA", "NC"]:  # Ordre de priorité
                        # Vérifier le maximum individuel du type de poste
                        current = current_counts['posts'].get(post_type, 0)
                        max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
                        
                        if current >= max_allowed:
                            logger.info(f"{doctor_name}: Maximum atteint pour {post_type} "
                                    f"({current}/{max_allowed})")
                            continue

                        # Chercher un slot disponible
                        available = [
                            (date, slot) for date, slot 
                            in available_slots[post_type]['all']
                            if date == day.date and not slot.assignee
                        ]

                        # Vérification et attribution
                        for date, slot in available:
                            if self._can_assign_nam_post(doctor, date, slot, post_type, intervals[doctor.name]):
                                # Attribution sûre
                                slot.assignee = doctor_name
                                
                                # Mise à jour des compteurs d'intervalles
                                doctor_intervals['current_counts']['posts'][post_type] += 1
                                doctor_intervals['current_counts']['groups']['NMC'] += 1
                                
                                # Mise à jour des compteurs de pré-attribution
                                if doctor_name in self.weekday_counts:
                                    self.weekday_counts[doctor_name]['posts'][post_type] = \
                                        self.weekday_counts[doctor_name]['posts'].get(post_type, 0) + 1
                                    self.weekday_counts[doctor_name]['groups']['NMC'] = \
                                        self.weekday_counts[doctor_name]['groups'].get('NMC', 0) + 1
                                
                                # Mise à jour des listes
                                if (date, slot) in available_slots[post_type]['all']:
                                    available_slots[post_type]['all'].remove((date, slot))
                                for category in ['critical', 'standard']:
                                    if (date, slot) in available_slots[post_type][category]:
                                        available_slots[post_type][category].remove((date, slot))
                                
                                assigned = True
                                logger.info(f"{doctor_name}: {post_type} attribué le {date} "
                                        f"(veille de NL)")
                                break

                            if assigned:
                                break

                        if assigned:
                            break

        except Exception as e:
            logger.error(f"Erreur distribution NAM avant NL: {e}")

    def _distribute_nanm_minimum_to_doctors(self, available_slots: Dict,
                                        quotas: Dict,
                                        intervals: Dict) -> bool:
        """
        Distribution des minimums NAM avec prise en compte des pré-attributions.
        """
        try:
            # Identifier les médecins sous leur minimum
            doctors_with_need = []
            for doctor in self.doctors:
                intervals = intervals[doctor.name]
                missing_posts = {}
                total_gap = 0

                # Inclure les pré-attributions dans les compteurs actuels
                current_counts = intervals['current_counts'].copy()
                if doctor.name in self.weekday_counts:
                    for post_type, count in self.weekday_counts[doctor.name]['posts'].items():
                        current_counts['posts'][post_type] = count

                # Vérifier d'abord la limite du groupe NMC
                current_nmc = current_counts['groups'].get('NMC', 0)
                max_nmc = intervals['groups'].get('NMC', {}).get('max', float('inf'))
                
                if current_nmc < max_nmc:
                    space_left_in_group = max_nmc - current_nmc
                    
                    for post_type in ["NA", "NM", "NC"]:
                        current = current_counts['posts'].get(post_type, 0)
                        min_required = intervals['posts'].get(post_type, {}).get('min', 0)
                        
                        if current < min_required:
                            gap = min(min_required - current, space_left_in_group)
                            if gap > 0:
                                missing_posts[post_type] = gap
                                total_gap += gap
                                space_left_in_group -= gap

                if missing_posts:
                    doctors_with_need.append({
                        'doctor': doctor,
                        'intervals': intervals,
                        'missing': missing_posts,
                        'gap': total_gap,
                        'space_in_group': space_left_in_group
                    })

            # Trier par écart au minimum décroissant
            doctors_with_need.sort(key=lambda x: x['gap'], reverse=True)

            # Distribution prioritaire
            progress_made = True
            while progress_made and doctors_with_need:
                progress_made = False
                
                for doc_info in doctors_with_need[:]:
                    if not doc_info['missing']:
                        doctors_with_need.remove(doc_info)
                        continue

                    success = self._try_assign_nanm_minimum(
                        doc_info, available_slots, intervals
                    )
                    if success:
                        progress_made = True

                if not progress_made:
                    break

            return True

        except Exception as e:
            logger.error(f"Erreur distribution minimum NANM: {e}")
            return False

    def _try_assign_nanm_minimum(self, doc_info: Dict, available_slots: Dict,
                            intervals: Dict) -> bool:
        """Tente d'attribuer un slot NANM pour atteindre le minimum."""
        try:
            doctor = doc_info['doctor']
            doctor_intervals = doc_info['intervals']

            # Pour chaque type de poste manquant
            for post_type in ["NM", "NA", "NC"]:
                if post_type not in doc_info['missing']:
                    continue

                if not available_slots[post_type]['all']:
                    continue

                # Essayer d'abord les slots critiques
                for category in ['critical', 'standard']:
                    slots = available_slots[post_type][category]
                    if not slots:
                        continue

                    for date, slot in slots[:]:
                        if self._can_assign_nam_post(
                            doctor, date, slot, post_type, doctor_intervals
                        ):
                            # Attribution et mise à jour des compteurs
                            slot.assignee = doctor.name
                            doc_info['missing'][post_type] -= 1
                            if doc_info['missing'][post_type] <= 0:
                                del doc_info['missing'][post_type]
                                
                            # Mettre à jour les compteurs
                            intervals[doctor.name]['current_counts']['posts'][post_type] += 1
                            intervals[doctor.name]['current_counts']['groups']['NMC'] += 1
                            
                            # Mettre à jour les compteurs de pré-attribution
                            if doctor.name in self.weekday_counts:
                                self.weekday_counts[doctor.name]['posts'][post_type] += 1
                                if 'NMC' not in self.weekday_counts[doctor.name]['groups']:
                                    self.weekday_counts[doctor.name]['groups']['NMC'] = 0
                                self.weekday_counts[doctor.name]['groups']['NMC'] += 1
                            
                            # Retirer le slot des disponibles
                            slots.remove((date, slot))
                            if (date, slot) in available_slots[post_type]['all']:
                                available_slots[post_type]['all'].remove((date, slot))
                                
                            logger.info(f"{doctor.name}: {post_type} attribué le {date} "
                                    f"(minimum)")
                            return True

            return False

        except Exception as e:
            logger.error(f"Erreur attribution minimum NANM: {e}")
            return False
        
    def _can_assign_nam_post(self, doctor: Doctor, date: date,
                            slot: TimeSlot, post_type: str,
                            doctor_intervals: Dict) -> bool:
        """
        Vérifie si un poste NAM peut être attribué en tenant compte
        des pré-attributions et des maximums de groupe.
        """
        try:
            # 1. Vérifier les contraintes de base
            if not self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                return False

            # 2. Obtenir les compteurs actuels en incluant les pré-attributions
            current_counts = doctor_intervals['current_counts'].copy()
            if doctor.name in self.weekday_counts:
                for post_type, count in self.weekday_counts[doctor.name]['posts'].items():
                    current_counts['posts'][post_type] = current_counts['posts'].get(post_type, 0) + count
                for group, count in self.weekday_counts[doctor.name]['groups'].items():
                    current_counts['groups'][group] = current_counts['groups'].get(group, 0) + count

            # 3. Vérifier le maximum du type de poste
            current = current_counts['posts'].get(post_type, 0)
            max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
            if current >= max_allowed:
                logger.debug(f"{doctor.name}: Maximum atteint pour {post_type} ({current}/{max_allowed})")
                return False

            # 4. Vérifier le maximum du groupe NMC
            current_nmc = current_counts['groups'].get('NMC', 0)
            max_nmc = doctor_intervals['groups'].get('NMC', {}).get('max', float('inf'))
            if current_nmc >= max_nmc:
                logger.debug(f"{doctor.name}: Maximum atteint pour groupe NMC ({current_nmc}/{max_nmc})")
                return False

            # 5. Vérifier les contraintes temporelles
            if not self._verify_nam_timing_constraints(doctor, date, post_type):
                return False

            return True

        except Exception as e:
            logger.error(f"Erreur vérification attribution NAM: {e}")
            return False

    def _verify_nam_timing_constraints(self, doctor: Doctor, 
                                    date: date, post_type: str) -> bool:
        """
        Vérifie les contraintes temporelles spécifiques aux postes NAM.
        """
        try:
            # 1. Vérifier les jours précédents et suivants
            for delta in [-1, 1]:  # Jour précédent et suivant
                check_date = date + timedelta(days=delta)
                day = self.planning.get_day(check_date)
                
                if day:
                    for slot in day.slots:
                        if slot.assignee == doctor.name:
                            # Pas de NAM après une nuit
                            if delta == -1 and post_type in ["NA", "NM", "NC"]:
                                if slot.abbreviation in ["NL", "NM", "NC"]:
                                    return False
                            # Pas de matin après un NAM
                            elif delta == 1 and slot.abbreviation in self.morning_posts:
                                return False

            return True

        except Exception as e:
            logger.error(f"Erreur vérification contraintes temporelles NAM: {e}")
            return False
        
    def _distribute_remaining_nanm_to_doctors(self, available_slots: Dict,
                                            doctor_intervals: Dict) -> bool:
        """
        Distribution équilibrée des slots NANM restants.
        Utilise un système de score avancé pour une meilleure répartition.
        """
        try:
            logger.info("\nDISTRIBUTION ÉQUILIBRÉE NANM")
            progress_made = True
            max_iterations = 3
            current_iteration = 0

            while progress_made and current_iteration < max_iterations:
                progress_made = False
                current_iteration += 1

                # Calculer les scores d'éligibilité des médecins
                eligible_doctors = []
                for doctor in self.doctors:
                    intervals = doctor_intervals[doctor.name]
                    
                    # Vérifier le maximum du groupe NMC
                    current_nmc = intervals['current_counts']['groups'].get('NMC', 0)
                    max_nmc = intervals['groups'].get('NMC', {}).get('max', float('inf'))
                    
                    if current_nmc >= max_nmc:
                        continue

                    # Calculer le score avec plus de critères
                    score = self._calculate_advanced_nam_score(
                        doctor, intervals, current_nmc, max_nmc
                    )
                    if score > 0:
                        eligible_doctors.append((doctor, score))

                # Trier par score décroissant
                eligible_doctors.sort(key=lambda x: x[1], reverse=True)

                # Distribution par priorité
                for post_type in ["NM", "NA", "NC"]:
                    slots = available_slots.get(post_type, {})
                    if not slots:
                        continue

                    for doctor, score in eligible_doctors:
                        intervals = doctor_intervals[doctor.name]
                        
                        # Vérifier le maximum du type de poste
                        current = intervals['current_counts']['posts'].get(post_type, 0)
                        max_allowed = intervals['posts'].get(post_type, {}).get('max', float('inf'))
                        
                        if current >= max_allowed:
                            continue

                        for slot_category in ['critical', 'standard']:
                            slots_to_try = slots[slot_category].copy()
                            random.shuffle(slots_to_try)

                            for date, slot in slots_to_try:
                                if self._can_assign_nam_post(doctor, date, slot, post_type, intervals):
                                    # Attribution sûre
                                    slot.assignee = doctor.name
                                    
                                    # Mise à jour des compteurs
                                    intervals['current_counts']['posts'][post_type] = current + 1
                                    intervals['current_counts']['groups']['NMC'] = \
                                        intervals['current_counts']['groups'].get('NMC', 0) + 1
                                    
                                    # Mise à jour des listes
                                    slots[slot_category].remove((date, slot))
                                    if (date, slot) in slots['all']:
                                        slots['all'].remove((date, slot))
                                        
                                    progress_made = True
                                    logger.info(f"{doctor.name}: {post_type} attribué le {date} "
                                            f"(distribution équilibrée)")
                                    break

                            if progress_made:
                                break

                if not progress_made:
                    logger.info("Aucun progrès possible dans cette itération")
                    break

            return True

        except Exception as e:
            logger.error(f"Erreur distribution équilibrée NANM: {e}")
            return False

    def _calculate_advanced_nam_score(self, doctor: Doctor, intervals: Dict,
                                    current_nmc: int, max_nmc: float) -> float:
        """
        Calcule un score avancé pour la distribution équilibrée.
        Prend en compte plus de facteurs pour une meilleure répartition.
        """
        try:
            score = 1.0

            # 1. Distance au maximum du groupe NMC
            if max_nmc < float('inf'):
                group_ratio = current_nmc / max_nmc
                score *= (1 - group_ratio)  # Plus bas si proche du maximum

            # 2. Équilibre entre types de postes
            post_ratios = []
            for post_type in ["NA", "NM", "NC"]:
                current = intervals['current_counts']['posts'].get(post_type, 0)
                max_val = intervals['posts'].get(post_type, {}).get('max', float('inf'))
                if max_val < float('inf'):
                    post_ratios.append(current / max_val)
                    
            if post_ratios:
                # Favoriser une distribution équilibrée entre types
                avg_ratio = sum(post_ratios) / len(post_ratios)
                score *= (1 - avg_ratio)

            # 3. Charge de travail globale
            total_posts = sum(intervals['current_counts']['posts'].values())
            expected_total = sum(interval.get('min', 0) 
                            for interval in intervals['posts'].values())
            if expected_total > 0:
                workload_ratio = total_posts / expected_total
                score *= max(0.5, 1 - (workload_ratio - 1))  # Pénalité si surcharge

            # 4. Facteur aléatoire réduit
            score *= 1 + (random.random() * 0.1 - 0.05)  # ±5%

            return max(0.1, score)

        except Exception as e:
            logger.error(f"Erreur calcul score avancé: {e}")
            return 0.1
    def _calculate_nanm_score(self, doctor: Doctor, intervals: Dict) -> float:
        """
        Calcule un score d'éligibilité pour la distribution NANM.
        """
        try:
            score = 1.0

            # 1. Vérification groupe NMC
            current_nmc = intervals['current_counts']['groups'].get('NMC', 0)
            max_nmc = intervals['groups'].get('NMC', {}).get('max', float('inf'))
            if doctor.half_parts == 1:
                max_nmc = max(1, max_nmc // 2)
                
            if max_nmc < float('inf'):
                # Score plus élevé si loin du maximum
                group_ratio = current_nmc / max_nmc
                score *= (1 - group_ratio)

            # 2. Ajustement selon les demi-parts
            if doctor.half_parts == 1:
                score *= 0.8  # Pénalité légère pour les mi-temps
            else:
                score *= 1.2  # Bonus pour les pleins temps

            # 3. Facteur aléatoire (±10%)
            score *= 1 + (random.random() * 0.2 - 0.1)

            return max(0.1, score)

        except Exception as e:
            logger.error(f"Erreur calcul score NANM: {e}")
            return 0.1


    
        
    def _verify_post_limits(self, doctor: Doctor, post_type: str, doctor_intervals: Dict) -> bool:
        """
        Vérifie les limites pour un type de poste donné.
        """
        try:
            # S'assurer que les compteurs existent
            if 'current_counts' not in doctor_intervals:
                doctor_intervals['current_counts'] = {
                    'posts': defaultdict(int),
                    'groups': defaultdict(int)
                }

            # Vérifier les limites de poste
            current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
            post_interval = doctor_intervals.get('posts', {}).get(post_type, {})
            max_allowed = post_interval.get('max', float('inf'))
            
            if current >= max_allowed:
                return False

            # Vérifier les limites de groupe
            group = self._get_post_group(post_type, datetime.now().date())
            if group:
                current_group = doctor_intervals['current_counts']['groups'].get(group, 0)
                group_max = doctor_intervals.get('groups', {}).get(group, {}).get('max', float('inf'))
                if current_group >= group_max:
                    return False

            return True

        except Exception as e:
            logger.error(f"Erreur vérification limites: {str(e)}")
            return False

    def _count_unassigned_posts(self, remaining_posts: Dict) -> int:
        """Compte précis des postes non attribués."""
        total = 0
        for post_type, slots in remaining_posts.items():
            unassigned = sum(1 for _, slot in slots if not slot.assignee)
            if unassigned > 0:
                logger.debug(f"Postes {post_type} non attribués: {unassigned}")
            total += unassigned
        return total
        
    def _get_doctor_nanm_intervals(self) -> Dict:
        """
        Récupère les intervalles NAM pour chaque médecin depuis la pré-analyse.
        """
        intervals = {}
        pre_analysis = self.planning.pre_analysis_results
        
        for doctor in self.doctors:
            # Récupérer la distribution idéale du médecin
            doctor_dist = pre_analysis['ideal_distribution'].get(doctor.name, {})
            
            # Récupérer les intervalles de posts et groupes
            weekday_posts = doctor_dist.get('weekday_posts', {})
            weekday_groups = doctor_dist.get('weekday_groups', {})
            
            intervals[doctor.name] = {
                'posts': {
                    post_type: weekday_posts.get(post_type, {'min': 0, 'max': float('inf')})
                    for post_type in ["NA", "NM", "NC"]
                },
                'groups': {
                    'NMC': weekday_groups.get('NMC', {'min': 0, 'max': float('inf')})
                }
            }
            
            logger.debug(f"Intervalles pour {doctor.name}:")
            for post_type, interval in intervals[doctor.name]['posts'].items():
                logger.debug(f"{post_type}: [{interval['min']}-{interval['max']}]")
            logger.debug(f"NMC: [{intervals[doctor.name]['groups']['NMC']['min']}-"
                        f"{intervals[doctor.name]['groups']['NMC']['max']}]")
        
        return intervals

    def _count_unassigned_nanm(self, available_slots: Dict) -> int:
        """
        Compte le nombre total de slots NAM non attribués.
        """
        total_unassigned = 0
        
        # Pour chaque type de garde
        for post_type in ["NA", "NM", "NC"]:
            # Compter les slots non assignés dans tous les slots
            unassigned = sum(
                1 for date, slot in available_slots[post_type]['all']
                if not slot.assignee
            )
            
            if unassigned > 0:
                logger.info(f"Slots {post_type} non attribués: {unassigned}")
            total_unassigned += unassigned
        
        return total_unassigned

    def _initialize_doctor_nanm_counts(self) -> Dict:
        """
        Initialise les compteurs NANM pour chaque médecin.
        """
        doctor_counts = {}
        pre_analysis = self.planning.pre_analysis_results

        for doctor in self.doctors:
            intervals = pre_analysis['ideal_distribution'].get(doctor.name, {})
            weekday_posts = intervals.get('weekday_posts', {})
            
            doctor_counts[doctor.name] = {}
            for post_type in ["NA", "NM", "NC"]:
                doctor_counts[doctor.name][post_type] = {
                    'count': self._count_current_nam(doctor, post_type),
                    'min': weekday_posts.get(post_type, {}).get('min', 0),
                    'max': weekday_posts.get(post_type, {}).get('max', float('inf'))
                }

        return doctor_counts

    def _count_current_nam(self, doctor: Doctor, post_type: str) -> int:
        """
        Compte le nombre de postes NAM déjà attribués à un médecin.
        """
        count = 0
        for day in self.planning.days:
            if not day.is_weekend and not day.is_holiday_or_bridge:
                count += sum(
                    1 for slot in day.slots
                    if slot.assignee == doctor.name and slot.abbreviation == post_type
                )
        return count

    def _try_assign_nam_to_doctor(self, doctor: Doctor, post_type: str,
                            slot_lists: Dict[str, List], slot_stats: Dict) -> bool:
        """
        Tente d'attribuer un slot NAM à un médecin.
        Essaie d'abord les slots critiques, puis les standards.
        """
        # Essayer d'abord les slots critiques
        for category in ['critical', 'standard']:
            available = slot_lists[category]
            if not available:
                continue

            slots_to_try = available.copy()
            random.shuffle(slots_to_try)

            for date, slot in slots_to_try:
                if not slot.assignee and self.constraints.can_assign_to_assignee(
                    doctor, date, slot, self.planning
                ):
                    slot.assignee = doctor.name
                    slot_stats['count'] += 1
                    
                    # Retirer le slot des deux listes
                    slot_lists[category].remove((date, slot))
                    if (date, slot) in slot_lists['all']:
                        slot_lists['all'].remove((date, slot))
                    
                    logger.info(f"{doctor.name}: {post_type} attribué le {date} "
                            f"({category}, count: {slot_stats['count']})")
                    return True

        return False

    def _check_minimum_reached(self, doctor_counts: Dict) -> bool:
        """
        Vérifie si tous les médecins ont atteint leur minimum pour tous les types.
        """
        for doctor_name, counts in doctor_counts.items():
            for post_type, stats in counts.items():
                if stats['count'] < stats['min']:
                    return False
        return True

    def _can_take_additional_nam(self, doctor: Doctor, post_type: str,
                            date: date, slot: TimeSlot,
                            intervals: Dict) -> bool:
        """
        Vérifie si un médecin peut prendre un slot NAM supplémentaire.
        """
        # 1. Vérifier les contraintes de base
        if not self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
            return False

        # 2. Vérifier les limites de type de poste
        current = self._count_current_nam(doctor, post_type)
        max_allowed = (intervals.get(doctor.name, {})
                    .get('weekday_posts', {})
                    .get(post_type, {})
                    .get('max', float('inf')))
        
        if current >= max_allowed:
            return False

        # 3. Vérifier les limites de groupe (NMC)
        group = "NMC"  # Groupe pour NA, NM, NC
        current_group = sum(
            1 for day in self.planning.days
            if not day.is_weekend and not day.is_holiday_or_bridge
            for slot in day.slots
            if slot.assignee == doctor.name 
            and slot.abbreviation in ["NA", "NM", "NC"]
        )
        
        group_max = (intervals.get(doctor.name, {})
                    .get('weekday_groups', {})
                    .get(group, {})
                    .get('max', float('inf')))
        
        return current_group < group_max


    def _is_doctor_available_for_weekday(self, doctor: Doctor, date: date) -> bool:
        """
        Vérifie si un médecin est disponible pour une date donnée.
        Prend en compte les desiderata et les contraintes de repos.

        Args:
            doctor: Le médecin à vérifier
            date: La date à vérifier

        Returns:
            bool: True si le médecin est disponible, False sinon
        """
        try:
            # 1. Vérifier les desiderata
            for desiderata in doctor.desiderata:
                if desiderata.start_date <= date <= desiderata.end_date:
                    return False

            # 2. Vérifier si le médecin a déjà des postes ce jour
            day = self.planning.get_day(date)
            if day and any(slot.assignee == doctor.name for slot in day.slots):
                return False

            # 3. Vérifier les contraintes de repos
            prev_day = self.planning.get_day(date - timedelta(days=1))
            if prev_day:
                # Pas de poste après une garde de nuit
                night_posts = ["NM", "NC", "NL"]
                if any(slot.assignee == doctor.name and slot.abbreviation in night_posts 
                    for slot in prev_day.slots):
                    return False

            # 4. Vérifier le nombre de jours consécutifs
            consecutive_days = 0
            check_date = date - timedelta(days=1)
            while consecutive_days < 6:  # Limite de 6 jours consécutifs
                day = self.planning.get_day(check_date)
                if not day or not any(slot.assignee == doctor.name for slot in day.slots):
                    break
                consecutive_days += 1
                check_date -= timedelta(days=1)

            if consecutive_days >= 6:
                return False

            return True

        except Exception as e:
            logger.error(f"Erreur lors de la vérification de disponibilité pour {doctor.name}: {e}")
            return False



    def _log_unassigned_posts(self, remaining_posts: Dict) -> None:
        """
        Log détaillé des postes restants non attribués en semaine.
        
        Args:
            remaining_posts: Dictionnaire des postes restants organisés par type
                Format: {post_type: [(date, slot), ...]}
        """
        try:
            total_unassigned = 0
            unassigned_by_type = defaultdict(list)
            unassigned_by_date = defaultdict(lambda: defaultdict(int))
            
            # 1. Collecte des informations
            for post_type, slots in remaining_posts.items():
                for date, slot in slots:
                    if not slot.assignee:
                        total_unassigned += 1
                        unassigned_by_type[post_type].append(date)
                        unassigned_by_date[date][post_type] += 1

            if total_unassigned == 0:
                logger.info("Tous les postes ont été attribués avec succès")
                return

            # 2. Log du résumé global
            logger.warning(f"\nPOSTES NON ATTRIBUÉS: {total_unassigned} au total")
            logger.warning("=" * 60)

            # 3. Log par type de poste
            logger.warning("\nDétail par type de poste:")
            for post_type, dates in sorted(unassigned_by_type.items()):
                count = len(dates)
                logger.warning(f"{post_type}: {count} poste(s) non attribué(s)")
                # Détail des dates pour chaque type
                for date in sorted(dates):
                    logger.warning(f"  - {date.strftime('%Y-%m-%d')}")

            # 4. Log par date
            logger.warning("\nDétail par date:")
            for date in sorted(unassigned_by_date.keys()):
                logger.warning(f"\n{date.strftime('%Y-%m-%d')}:")
                day_total = sum(unassigned_by_date[date].values())
                
                # Vérifier si c'est un jour particulier
                is_friday = date.weekday() == 4
                is_bridge = DayType.is_bridge_day(date, self.cal)
                
                special_note = ""
                if is_friday:
                    special_note = " (Vendredi)"
                elif is_bridge:
                    special_note = " (Jour de pont)"
                    
                logger.warning(f"Total: {day_total} poste(s){special_note}")
                
                # Détail des postes non attribués pour cette date
                for post_type, count in sorted(unassigned_by_date[date].items()):
                    logger.warning(f"  - {post_type}: {count}")

                # 5. Analyse des causes possibles
                available_doctors = sum(
                    1 for doctor in self.doctors
                    if self._is_doctor_available_for_weekday(doctor, date)
                )
                doctor_percentage = (available_doctors / len(self.doctors)) * 100
                
                if doctor_percentage < 40:
                    logger.warning(f"  Note: Faible disponibilité ({doctor_percentage:.1f}% des médecins disponibles)")

        except Exception as e:
            logger.error(f"Erreur lors du log des postes non attribués: {e}")










    def distribute_weekday_combinations(self) -> bool:
        """
        Distribution des combinaisons de semaine avec conservation de la partie CAT
        et nouvelle implémentation pour les médecins.
        Retourne True pour indiquer que le processus s'est déroulé, même si incomplet.
        """
        try:
            logger.info("\nDISTRIBUTION DES COMBINAISONS SEMAINE")
            logger.info("=" * 80)

            # Phase 1: Distribution aux CAT
            logger.info("\nPHASE 1: DISTRIBUTION AUX CAT")
            if not self._distribute_weekday_cat_combinations():
                logger.warning("Distribution CAT semaine incomplète - continuation")

            # Phase 2: Préparation de la distribution médecins
            logger.info("\nPHASE 2: PRÉPARATION DISTRIBUTION MÉDECINS")
            
            # Initialisation de la matrice de disponibilité
            availability_matrix = AvailabilityMatrix(
                self.planning.start_date,
                self.planning.end_date,
                self.doctors,
                self.cats
            )

            # Récupération des périodes critiques
            critical_periods = sorted(
                availability_matrix.critical_periods,
                key=lambda x: (x[2], -x[3])  # Par indisponibilité décroissante
            )

            # Organisation des dates en critique et normale
            weekdays = self._get_weekdays(self.planning)
            critical_dates = {period[0] for period in critical_periods}
            normal_dates = [d for d in weekdays if d not in critical_dates]
            random.shuffle(normal_dates)  # Mélange aléatoire

            # Récupération des intervalles depuis la pré-analyse
            intervals = self._get_doctor_weekday_intervals()
            if not intervals:
                logger.error("Impossible de récupérer les intervalles - poursuite avec la distribution restante")
                return True

            # Phase 3: Distribution aux médecins
            logger.info("\nPHASE 3: DISTRIBUTION AUX MÉDECINS")
            distribution_result = self._distribute_weekday_combinations_to_doctors(
                critical_dates,
                normal_dates,
                intervals,
                availability_matrix
            )

            if not distribution_result:
                logger.warning("Distribution des combinaisons semaine incomplète")
            else:
                logger.info("Distribution des combinaisons semaine terminée")

            # On continue le processus même si la distribution est incomplète
            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution semaine: {e}", exc_info=True)
            # On retourne True pour continuer le processus malgré l'erreur
            return True


    
    

    def _distribute_weekday_cat_combinations(self) -> bool:
        """
        Distribution des combinaisons de semaine aux CAT avec gestion stricte des quotas.
        Utilise le QuotaTracker pour garantir le respect des limites.
        """
        try:
            logger.info("\nDISTRIBUTION DES COMBINAISONS SEMAINE AUX CAT")
            logger.info("=" * 60)

            # Initialisation du tracker de quotas
            quota_tracker = QuotaTracker(self.planning, self.cats, "weekday")
            
            # Initialisation de la matrice de disponibilité
            availability_matrix = AvailabilityMatrix(
                self.planning.start_date,
                self.planning.end_date,
                self.doctors,
                self.cats
            )
            
            # Organisation des dates par criticité
            weekdays = self._get_weekdays(self.planning)
            dates_by_criticality = self._organize_dates_by_criticality(weekdays, availability_matrix)
            
            # Statistiques de distribution
            distribution_stats = {
                'critical': {'success': 0, 'failed': 0},
                'normal': {'success': 0, 'failed': 0}
            }

            # Distribution par niveau de criticité
            for criticality in ['critical', 'normal']:
                logger.info(f"\nTraitement des périodes {criticality}")
                for current_date in dates_by_criticality[criticality]:
                    self._process_cat_distribution_for_date(
                        current_date,
                        quota_tracker,
                        distribution_stats[criticality],
                        is_critical=(criticality == 'critical')
                    )

            # Log des résultats
            self._log_cat_distribution_results(distribution_stats, quota_tracker)
            return True

        except Exception as e:
            logger.error(f"Erreur distribution CAT semaine: {e}", exc_info=True)
            return False

    def _process_cat_distribution_for_date(self, date: date, quota_tracker: QuotaTracker,
                                        stats: Dict, is_critical: bool) -> None:
        """
        Traite la distribution pour une date donnée.
        Essaie d'attribuer des combinaisons à tous les CAT disponibles.
        """
        try:
            # Traitement des CAT dans un ordre aléatoire
            cats = list(self.cats)
            random.shuffle(cats)
            
            for cat in cats:
                if not self._is_cat_available_for_weekday(cat, date):
                    continue
                
                # Récupérer et filtrer les combinaisons possibles
                combinations = self._get_filtered_combinations(cat, date, quota_tracker)
                if not combinations:
                    continue
                    
                # Tenter l'attribution
                assigned = False
                for combo, weight in combinations:
                    if self._try_assign_cat_combination(cat, combo, date, quota_tracker):
                        assigned = True
                        stats['success'] += 1
                        break
                        
                if not assigned:
                    stats['failed'] += 1

        except Exception as e:
            logger.error(f"Erreur traitement {date}: {e}")

    def _get_filtered_combinations(self, cat: CAT, date: date, 
                            quota_tracker: QuotaTracker) -> List[Tuple[str, float]]:
        """
        Retourne les combinaisons possibles pour un CAT, filtrées et pondérées.
        """
        possible_combinations = []
        
        # Récupérer toutes les combinaisons de base
        all_combinations = self._get_cat_possible_weekday_combinations(cat)
        
        # Filtrer selon les quotas disponibles
        for combo, base_weight in all_combinations:
            if quota_tracker.can_assign_combination(cat, combo, date):
                # Calcul du poids final
                remaining = quota_tracker.get_remaining_quotas(cat)
                weight = self._calculate_combination_weight(combo, remaining, base_weight)
                possible_combinations.append((combo, weight))
        
        # Trier par poids décroissant
        possible_combinations.sort(key=lambda x: x[1], reverse=True)
        return possible_combinations

    def _try_assign_cat_combination(self, cat: CAT, combo: str, date: date,
                                quota_tracker: QuotaTracker) -> bool:
        """
        Tente d'attribuer une combinaison à un CAT en respectant toutes les contraintes.
        """
        try:
            day = self.planning.get_day(date)
            if not day:
                return False

            # Extraire les postes de la combinaison
            first_post, second_post = self._get_posts_from_weekday_combo(combo)
            
            # Vérification finale des quotas
            if not quota_tracker.can_assign_combination(cat, combo, date):
                return False
            
            # Trouver les slots disponibles
            first_slot = next((s for s in day.slots 
                            if s.abbreviation == first_post and not s.assignee), None)
            second_slot = next((s for s in day.slots 
                            if s.abbreviation == second_post and not s.assignee), None)
            
            if not (first_slot and second_slot):
                return False

            # Vérifier les contraintes
            if not (self.constraints.can_assign_to_assignee(cat, date, first_slot, self.planning) and
                    self.constraints.can_assign_to_assignee(cat, date, second_slot, self.planning)):
                return False

            # Attribuer les slots
            first_slot.assignee = cat.name
            second_slot.assignee = cat.name
            
            # Mettre à jour les compteurs
            quota_tracker.update_assignment(cat, first_post, date, combo)
            quota_tracker.update_assignment(cat, second_post, date)
            
            logger.info(f"Attribution {combo} à {cat.name} le {date}")
            logger.debug(f"Quotas restants: {quota_tracker.get_remaining_quotas(cat)}")
            
            return True

        except Exception as e:
            logger.error(f"Erreur attribution {combo} à {cat.name}: {e}")
            return False

    def _calculate_combination_weight(self, combo: str, remaining_quotas: Dict,
                                base_weight: float = 1.0) -> float:
        """
        Calcule le poids d'une combinaison en fonction des quotas restants.
        """
        first_post, second_post = self._get_posts_from_weekday_combo(combo)
        
        # Récupérer les quotas restants pour chaque poste
        first_remaining = remaining_quotas['posts'].get(first_post, 0)
        second_remaining = remaining_quotas['posts'].get(second_post, 0)
        
        # Le poids diminue si on s'approche des limites
        weight = base_weight
        if first_remaining + second_remaining > 0:
            weight *= (first_remaining + second_remaining) / 2
            
        # Facteur aléatoire pour éviter la monotonie
        weight *= 1 + (random.random() * 0.2 - 0.1)  # ±10%
        
        return max(0.1, weight)

    def _log_cat_distribution_results(self, stats: Dict, quota_tracker: QuotaTracker):
        """
        Affiche les résultats détaillés de la distribution.
        """
        logger.info("\nRÉSULTATS DE LA DISTRIBUTION CAT SEMAINE")
        logger.info("=" * 60)
        
        # Statistiques par type de période
        for period_type, period_stats in stats.items():
            logger.info(f"\nPériodes {period_type}:")
            total = period_stats['success'] + period_stats['failed']
            if total > 0:
                success_rate = (period_stats['success'] / total) * 100
                logger.info(f"Succès: {period_stats['success']}")
                logger.info(f"Échecs: {period_stats['failed']}")
                logger.info(f"Taux de réussite: {success_rate:.1f}%")
        
        # État des quotas de manière concise
        logger.info("\nVÉRIFICATION DES QUOTAS:")
        for cat in self.cats:
            remaining = quota_tracker.get_remaining_quotas(cat)
            critical_quotas = {
                post: quota for post, quota in remaining['posts'].items()
                if quota > 0
            }
            if critical_quotas:
                logger.info(f"\n{cat.name} - Quotas restants:")
                for post, quota in critical_quotas.items():
                    logger.info(f"  {post}: {quota}")
            else:
                logger.info(f"\n{cat.name}: Tous les quotas respectés")
    

    def _distribute_critical_periods_to_cats(
        self, critical_periods: List[Tuple], 
        cat_quotas: Dict[str, int],
        cat_stats: Dict[str, Dict]) -> Dict[str, int]:
        """Distribution prioritaire pour les périodes critiques."""
        
        remaining_quotas = cat_quotas.copy()
        cats_list = list(self.cats)

        for date, period, unavailability, _ in critical_periods:
            logger.info(f"\nTraitement période critique: {date} "
                    f"(indisponibilité: {unavailability:.1f}%)")
            
            # Mélanger les CAT pour distribution aléatoire
            random.shuffle(cats_list)
            
            # Filtrer les CAT disponibles
            available_cats = [
                cat for cat in cats_list
                if self._is_cat_available_for_weekday(cat, date)
            ]
            
            if not available_cats:
                logger.info("Aucun CAT disponible pour cette période")
                continue

            # Essayer d'attribuer une combinaison prioritaire
            for cat in available_cats:
                # Filtrer et mélanger les combinaisons disponibles
                available_combos = [
                    combo for combo, quota in remaining_quotas.items()
                    if quota > 0 and combo in WEEKDAY_PRIORITY_GROUPS['high_priority']
                ]
                random.shuffle(available_combos)
                
                for combo in available_combos:
                    if remaining_quotas[combo] > 0:
                        if self._assign_weekday_combo_to_cat(cat, combo, date, cat_stats[cat.name]):
                            remaining_quotas[combo] -= 1
                            logger.info(f"{cat.name}: {combo} attribué le {date} "
                                    f"(période critique)")
                            break

        return remaining_quotas
    def _get_remaining_weekday_slots(self) -> List[Tuple[date, str]]:
        """
        Retourne la liste des slots de semaine non attribués
        """
        remaining = []
        
        for day in self.planning.days:
            # Ignorer les weekends et jours fériés
            if day.is_weekend or day.is_holiday_or_bridge:
                continue
                
            for slot in day.slots:
                if not slot.assignee:
                    remaining.append((day.date, slot.abbreviation))
                    
        return remaining
    def _distribute_remaining_periods_to_cats(
        self, normal_dates: List[date],
        remaining_quotas: Dict[str, int],
        cat_stats: Dict[str, Dict]) -> bool:
        """Distribution des combinaisons restantes sur les périodes normales."""
        
        # Mélanger les dates pour distribution aléatoire
        dates_to_process = normal_dates.copy()
        random.shuffle(dates_to_process)
        
        # Traiter chaque combinaison restante
        for combo, quota in list(remaining_quotas.items()):
            while quota > 0:
                assigned = False
                
                # Mélanger les CAT pour chaque tentative
                cats_list = list(self.cats)
                random.shuffle(cats_list)
                
                for date in dates_to_process:
                    # Essayer chaque CAT disponible
                    for cat in cats_list:
                        if not self._is_cat_available_for_weekday(cat, date):
                            continue
                            
                        if self._assign_weekday_combo_to_cat(cat, combo, date, cat_stats[cat.name]):
                            quota -= 1
                            remaining_quotas[combo] = quota
                            logger.info(f"{cat.name}: {combo} attribué le {date}")
                            assigned = True
                            break
                            
                    if assigned:
                        break
                        
                if not assigned:
                    logger.warning(f"Impossible d'attribuer {combo} (quota restant: {quota})")
                    break  # Éviter une boucle infinie
                    
        return True

    def _verify_cat_distribution(self, cat_stats: Dict, quotas: Dict[str, int]) -> bool:
        """Vérifie la distribution finale des CAT."""
        all_ok = True
        
        logger.info("\nVÉRIFICATION DE LA DISTRIBUTION CAT")
        logger.info("=" * 60)
        
        for cat_name, stats in cat_stats.items():
            logger.info(f"\n{cat_name}:")
            
            # Vérifier les quotas de postes
            for post, count in stats['posts'].items():
                quota = quotas.get(post, 0)
                status = "OK" if count <= quota else "DÉPASSEMENT"
                logger.info(f"{post}: {count}/{quota} ({status})")
                if count > quota:
                    all_ok = False
                    
            # Afficher les combinaisons utilisées
            logger.info("\nCombinaisons attribuées:")
            for combo, count in stats['combinations'].items():
                logger.info(f"{combo}: {count}")
                
        return all_ok
    
    def _verify_cat_post_quotas(self, cat: CAT, first_post: str, second_post: str) -> bool:
        """
        Vérifie strictement que le CAT n'a pas dépassé ses quotas pour les postes individuels.
        
        Args:
            cat: Le CAT à vérifier
            first_post: Premier poste de la combinaison
            second_post: Deuxième poste de la combinaison
            
        Returns:
            bool: True si l'attribution est possible, False sinon
        """
        try:
            # Récupérer les quotas depuis la pré-analyse
            quotas = self.planning.pre_analysis_results["cat_posts"]["weekday"]
            
            # Compter les postes déjà attribués (hors weekend/férié)
            current_counts = defaultdict(int)
            for day in self.planning.days:
                if not (day.is_weekend or day.is_holiday_or_bridge):
                    for slot in day.slots:
                        if slot.assignee == cat.name:
                            current_counts[slot.abbreviation] += 1
            
            # Vérifier les limites pour chaque poste
            for post_type in [first_post, second_post]:
                quota = quotas.get(post_type, 0)
                current = current_counts[post_type]
                
                if current >= quota:
                    logger.warning(f"{cat.name}: Quota atteint pour {post_type} "
                                f"({current}/{quota})")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur vérification quotas {cat.name}: {e}")
            return False

    def _calculate_cat_combination_quotas(self, quotas: Dict[str, int]) -> Dict[str, int]:
        """
        Calcule les quotas de combinaisons pour les CAT en respectant strictement 
        les quotas individuels des postes et les priorités définies.
        
        Args:
            quotas (Dict[str, int]): Quotas par type de poste
            
        Returns:
            Dict[str, int]: Quotas par combinaison respectant les limites individuelles
        """
        combination_quotas = {}
        used_posts = {post: 0 for post in quotas.keys()}
        
        # Log des quotas initiaux
        logger.info("\nQuotas initiaux par poste:")
        for post, quota in quotas.items():
            logger.info(f"{post}: {quota}")
        
        # Traiter les combinaisons par niveau de priorité
        priority_groups = [
            ('high_priority', WEEKDAY_PRIORITY_GROUPS['high_priority']),
            ('medium_priority', WEEKDAY_PRIORITY_GROUPS['medium_priority']),
            ('low_priority', WEEKDAY_PRIORITY_GROUPS['low_priority'])
        ]
        
        for priority_level, combinations in priority_groups:
            logger.info(f"\nTraitement des combinaisons {priority_level}")
            priority_weight = PRIORITY_WEIGHTS[priority_level]
            
            for combo in combinations:
                first_post, second_post = self._get_posts_from_weekday_combo(combo)
                
                # Vérifier si les deux postes ont des quotas définis
                if (first_post not in quotas) or (second_post not in quotas):
                    continue
                    
                # Calculer les quotas restants pour chaque poste
                remaining_first = quotas[first_post] - used_posts[first_post]
                remaining_second = quotas[second_post] - used_posts[second_post]
                
                if remaining_first <= 0 or remaining_second <= 0:
                    continue
                
                # Calculer le quota de base pour cette combinaison
                base_quota = min(remaining_first, remaining_second)
                
                # Appliquer le poids de priorité et les limites
                if priority_level == 'high_priority':
                    # Haute priorité : jusqu'à 60% des quotas restants
                    quota = int(base_quota * 0.6 * priority_weight)
                elif priority_level == 'medium_priority':
                    # Priorité moyenne : jusqu'à 40% des quotas restants
                    quota = int(base_quota * 0.4 * priority_weight)
                else:  # low_priority
                    # Basse priorité : jusqu'à 20% des quotas restants
                    quota = int(base_quota * 0.2 * priority_weight)
                
                # Assurer un minimum de 1 si possible tout en respectant les limites
                quota = min(max(1, quota), base_quota) if base_quota > 0 else 0
                
                if quota > 0:
                    # Vérifier une dernière fois que nous ne dépassons pas les quotas
                    if (used_posts[first_post] + quota <= quotas[first_post] and 
                        used_posts[second_post] + quota <= quotas[second_post]):
                        
                        combination_quotas[combo] = quota
                        used_posts[first_post] += quota
                        used_posts[second_post] += quota
                        
                        logger.info(f"Attribution {combo}: {quota}")
                        logger.info(f"  - {first_post}: {used_posts[first_post]}/{quotas[first_post]}")
                        logger.info(f"  - {second_post}: {used_posts[second_post]}/{quotas[second_post]}")
        
        # Vérification finale des quotas
        quota_violations = False
        logger.info("\nVérification finale des quotas:")
        for post, used in used_posts.items():
            if used > quotas[post]:
                logger.error(f"Dépassement pour {post}: {used}/{quotas[post]}")
                quota_violations = True
            else:
                logger.info(f"{post}: {used}/{quotas[post]} (OK)")
                
        if quota_violations:
            logger.error("Violations de quotas détectées - annulation de la distribution")
            return {}
        
        # Résumé des attributions
        logger.info("\nRésumé des combinaisons attribuées:")
        high_priority_count = sum(1 for combo in WEEKDAY_PRIORITY_GROUPS['high_priority'] 
                                if combo in combination_quotas)
        med_priority_count = sum(1 for combo in WEEKDAY_PRIORITY_GROUPS['medium_priority'] 
                            if combo in combination_quotas)
        low_priority_count = sum(1 for combo in WEEKDAY_PRIORITY_GROUPS['low_priority'] 
                            if combo in combination_quotas)
        
        logger.info(f"Combinaisons haute priorité: {high_priority_count}")
        logger.info(f"Combinaisons priorité moyenne: {med_priority_count}")
        logger.info(f"Combinaisons basse priorité: {low_priority_count}")
        
        return combination_quotas

    def _get_posts_from_weekday_combo(self, combo: str) -> Tuple[str, str]:
        """
        Extrait les deux postes d'une combinaison de semaine.
        Gère les postes personnalisés et standards.
        
        Args:
            combo (str): Code de la combinaison (ex: "MLCA")
            
        Returns:
            Tuple[str, str]: Tuple des deux codes de poste
        """
        # 1. Vérifier les combinaisons de postes personnalisés
        for custom_post in self.custom_posts.values():
            if combo in custom_post.possible_combinations.values():
                for post, combo_name in custom_post.possible_combinations.items():
                    if combo_name == combo:
                        return custom_post.name, post
        
        # 2. Combinaison standard (ex: "MLCA" -> ("ML", "CA"))
        return combo[:2], combo[2:]

    

    

    def _get_weekdays(self, planning: Planning) -> List[date]:
        """Récupère les jours de semaine (hors weekend et fériés)."""
        weekdays = []
        current_date = planning.start_date
        
        while current_date <= planning.end_date:
            if (current_date.weekday() < 5 and 
                not self.cal.is_holiday(current_date) and 
                not DayType.is_bridge_day(current_date, self.cal)):  # Utilisation de DayType
                weekdays.append(current_date)
            current_date += timedelta(days=1)
        
        return weekdays


    def _calculate_weekday_availability(self, weekdays: List[date]) -> Dict[date, float]:
        """Calcule le pourcentage de médecins disponibles pour chaque jour."""
        availability = {}
        for current_date in weekdays:
            # Compter les médecins disponibles
            available_doctors = sum(
                1 for doctor in self.doctors
                if not any(
                    desiderata.start_date <= current_date <= desiderata.end_date 
                    for desiderata in doctor.desiderata
                )
            )
            availability[current_date] = (available_doctors / len(self.doctors)) * 100
            
        return availability

    def _try_assign_weekday_combination_to_cat(self, cat: CAT, date: date,
                                            combinations: List[Tuple[str, int]],
                                            used_posts: Dict[str, int],
                                            combo_assignments: Dict[str, int],
                                            availability: float = 100.0) -> bool:
        """Tente d'attribuer une combinaison de semaine à un CAT avec vérification stricte des quotas."""
        quotas = self.planning.pre_analysis_results["cat_posts"]["weekday"]
        
        # 1. Filtrer les combinaisons disponibles en vérifiant les quotas de postes individuels
        available_combinations = []
        for combo, max_count in combinations:
            first_post, second_post = self._get_posts_from_weekday_combo(combo)
            
            # Vérifier les quotas restants pour chaque poste
            first_remaining = quotas.get(first_post, 0) - self._count_cat_post_usage(cat, first_post)
            second_remaining = quotas.get(second_post, 0) - self._count_cat_post_usage(cat, second_post)
            
            if (first_remaining > 0 and second_remaining > 0 and
                combo_assignments[combo] < max_count and
                self._can_assign_weekday_combo_to_cat(cat, combo, date)):
                available_combinations.append((combo, max_count))
        
        if available_combinations:
            # 2. Calculer les poids avec facteurs de priorité et disponibilité
            weighted_combinations = []
            for combo, max_count in available_combinations:
                base_weight = max_count + 1 - combo_assignments[combo]
                availability_factor = 2.0 - (availability / 100)
                random_factor = 1 + (random.random() * 0.4 - 0.2)
                final_weight = int(base_weight * availability_factor * random_factor)
                
                if final_weight > 0:
                    weighted_combinations.extend([combo] * final_weight)
            
            # 3. Sélectionner et attribuer une combinaison
            if weighted_combinations:
                selected_combo = random.choice(weighted_combinations)
                return self._assign_weekday_combo_to_cat(cat, selected_combo, date, used_posts, combo_assignments)
                    
        return False

    def _count_cat_post_usage(self, cat: CAT, post_type: str) -> int:
        """
        Compte l'utilisation actuelle d'un type de poste par un CAT dans le planning de semaine.
        
        Args:
            cat: Le CAT dont on veut compter les postes
            post_type: Le type de poste à compter
            
        Returns:
            int: Nombre d'utilisations du poste par le CAT
        """
        count = 0
        for day in self.planning.days:
            # Ne compter que les jours de semaine
            if not (day.is_weekend or day.is_holiday_or_bridge):
                for slot in day.slots:
                    if slot.assignee == cat.name and slot.abbreviation == post_type:
                        count += 1
        return count

    def _assign_weekday_combo_to_cat(self, cat: CAT, combo: str, date: date, stats: Dict) -> bool:
        """Attribution d'une combinaison à un CAT avec vérification stricte des quotas."""
        try:
            day = self.planning.get_day(date)
            if not day:
                return False

            # 1. Extraire les postes de la combinaison
            first_post, second_post = self._get_posts_from_weekday_combo(combo)
            
            # 2. Vérifier les quotas individuels
            if not self._verify_cat_post_quotas(cat, first_post, second_post):
                return False
            
            # 3. Trouver les slots disponibles
            first_slot = next((s for s in day.slots 
                            if s.abbreviation == first_post and not s.assignee), None)
            second_slot = next((s for s in day.slots 
                            if s.abbreviation == second_post and not s.assignee), None)
            
            if not (first_slot and second_slot):
                return False

            # 4. Vérifier les contraintes
            if not (self.constraints.can_assign_to_assignee(cat, date, first_slot, self.planning) and
                    self.constraints.can_assign_to_assignee(cat, date, second_slot, self.planning)):
                return False

            # 5. Effectuer l'attribution
            first_slot.assignee = cat.name
            second_slot.assignee = cat.name

            # 6. Mettre à jour les statistiques
            stats['combinations'][combo] = stats['combinations'].get(combo, 0) + 1
            stats['posts'][first_post] = stats['posts'].get(first_post, 0) + 1
            stats['posts'][second_post] = stats['posts'].get(second_post, 0) + 1

            logger.info(f"Attribution {combo} à {cat.name} le {date}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'attribution de {combo} à {cat.name}: {e}")
            return False
    

    def _get_posts_from_weekday_combo(self, combo: str) -> Tuple[str, str]:
        """Extrait les deux postes d'une combinaison de semaine."""
        # Vérifier si c'est une combinaison personnalisée
        for custom_post in self.custom_posts.values():
            if combo in custom_post.possible_combinations.values():
                for post, combo_name in custom_post.possible_combinations.items():
                    if combo_name == combo:
                        return custom_post.name, post
        
        # Combinaison standard
        return combo[:2], combo[2:]

    def _can_assign_weekday_combo_to_cat(self, cat: CAT, combo: str, date: date) -> bool:
        """Vérifie si une combinaison de semaine peut être attribuée à un CAT."""
        # 1. Vérifier l'existence du jour
        day = self.planning.get_day(date)
        if not day:
            return False
        
        # 2. Extraire les postes
        first_post, second_post = self._get_posts_from_weekday_combo(combo)
        
        # 3. Vérifier la disponibilité des slots
        first_slot = next((s for s in day.slots 
                        if s.abbreviation == first_post and not s.assignee), None)
        second_slot = next((s for s in day.slots 
                        if s.abbreviation == second_post and not s.assignee), None)
                        
        if not (first_slot and second_slot):
            return False
        
        # 4. Vérifier les contraintes
        return (self.constraints.can_assign_to_assignee(cat, date, first_slot, self.planning) and
                self.constraints.can_assign_to_assignee(cat, date, second_slot, self.planning))
        
    def _get_cat_possible_weekday_combinations(self, cat: CAT) -> List[Tuple[str, int]]:
        """
        Détermine les combinaisons possibles pour un CAT en semaine.
        
        Args:
            cat (CAT): Le CAT pour lequel on cherche les combinaisons
            
        Returns:
            List[Tuple[str, int]]: Liste des tuples (combinaison, nombre_max)
        """
        combinations = []
        quotas = self.planning.pre_analysis_results["cat_posts"]["weekday"]
        
        # Debug des quotas
        logger.debug(f"Quotas semaine disponibles pour {cat.name}:")
        for post_type, quota in quotas.items():
            if quota > 0:
                logger.debug(f"  {post_type}: {quota}")
        
        # 1. Ajout des combinaisons standards de semaine
        for combo in WEEKDAY_COMBINATIONS:
            first_post, second_post = combo[:2], combo[2:]
            
            if quotas.get(first_post, 0) > 0 and quotas.get(second_post, 0) > 0:
                max_count = min(quotas[first_post], quotas[second_post])
                if max_count > 0:
                    combinations.append((combo, max_count))
                    logger.debug(f"  Ajout combinaison standard: {combo} (max={max_count})")
                        
        # 2. Ajout des combinaisons des postes personnalisés
        for post_name, custom_post in self.custom_posts.items():
            # Vérifier si le poste peut être attribué aux CAT
            if (custom_post.assignment_type in ['cats', 'both'] and
                'weekday' in custom_post.day_types):
                
                quota_custom = quotas.get(post_name, 0)
                if quota_custom > 0:
                    # Pour chaque combinaison possible du poste personnalisé
                    for other_post, combo_name in custom_post.possible_combinations.items():
                        quota_other = quotas.get(other_post, 0)
                        if quota_other > 0:
                            max_count = min(quota_custom, quota_other)
                            combinations.append((combo_name, max_count))
                            logger.debug(f"  Ajout combinaison personnalisée: {combo_name} "
                                    f"({post_name}+{other_post}, max={max_count})")
                                
        # Log final des combinaisons disponibles
        if combinations:
            logger.info(f"Combinaisons semaine disponibles pour {cat.name}:")
            for combo, max_count in combinations:
                logger.info(f"  - {combo} (max: {max_count})")
        else:
            logger.warning(f"Aucune combinaison semaine disponible pour {cat.name}")
        
        return combinations
    
    def _is_cat_available_for_weekday(self, cat: CAT, date: date) -> bool:
        """
        Vérifie si un CAT est disponible pour un jour de semaine donné.
        
        Args:
            cat (CAT): Le CAT à vérifier
            date (date): La date du jour à vérifier
            
        Returns:
            bool: True si le CAT est disponible, False sinon
        """
        try:
            # 1. Vérifier les desiderata
            for desiderata in cat.desiderata:
                if desiderata.start_date <= date <= desiderata.end_date:
                    logger.debug(f"{cat.name} indisponible le {date} (desiderata)")
                    return False
                    
            # 2. Vérifier si le CAT a déjà des postes ce jour
            day = self.planning.get_day(date)
            if day:
                for slot in day.slots:
                    if slot.assignee == cat.name:
                        logger.debug(f"{cat.name} déjà assigné le {date} ({slot.abbreviation})")
                        return False
            else:
                logger.debug(f"Jour {date} non trouvé dans le planning")
                return False  # Jour non trouvé dans le planning
                
            # CAT disponible
            logger.debug(f"{cat.name} disponible le {date}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de disponibilité de {cat.name}: {e}")
            return False

    def _log_weekday_cat_distribution(self, cat: CAT, stats: Dict):
        """Log détaillé des résultats de distribution pour un CAT."""
        logger.info(f"\nRésultats de distribution semaine pour {cat.name}:")

        # Log des combinaisons utilisées
        if stats['combinations']:
            logger.info("\nCombinaisons attribuées:")
            for combo, count in sorted(stats['combinations'].items()):
                logger.info(f"{combo}: {count}")

        # Log des postes individuels
        if stats['posts']:
            logger.info("\nPostes utilisés:")
            for post, count in sorted(stats['posts'].items()):
                logger.info(f"{post}: {count}")
            
            
    
    
    
    
    
    


    def _get_doctor_weekday_intervals(self) -> Dict:
        """
        Récupère les intervalles de postes et groupes des médecins depuis la pré-analyse.
        """
        try:
            pre_analysis = self.planning.pre_analysis_results
            if not pre_analysis or 'ideal_distribution' not in pre_analysis:
                logger.error("Pré-analyse ou distribution idéale manquante")
                return None

            intervals = {}
            for doctor in self.doctors:
                doctor_dist = pre_analysis['ideal_distribution'].get(doctor.name, {})
                
                intervals[doctor.name] = {
                    'posts': doctor_dist.get('weekday_posts', {}),
                    'groups': doctor_dist.get('weekday_groups', {}),
                    'current_counts': {
                        'posts': defaultdict(int),
                        'groups': defaultdict(int)
                    }
                }

            return intervals

        except Exception as e:
            logger.error(f"Erreur récupération intervalles: {e}")
            return None

    def _distribute_weekday_combinations_to_doctors(
        self, critical_dates: Set[date], normal_dates: List[date],
        intervals: Dict, availability_matrix: AvailabilityMatrix) -> bool:
        """
        Distribution principale des combinaisons aux médecins.
        """
        try:
            # Phase 1: Distribution sur périodes critiques
            logger.info("\nDistribution périodes critiques")
            for date in sorted(critical_dates):
                availability = availability_matrix.get_period_availability
                self._distribute_day_combinations(date, intervals, availability, True)

            # Phase 2: Distribution sur périodes normales
            logger.info("\nDistribution périodes normales")
            for date in normal_dates:
                availability = availability_matrix.get_period_availability
                self._distribute_day_combinations(date, intervals, availability, False)

            # Vérification finale
            return self._verify_doctor_distribution(intervals)

        except Exception as e:
            logger.error(f"Erreur distribution médecins: {e}")
            return False
        
        

    def _distribute_day_combinations(self, date: date, intervals: Dict,
                                    availability: float, is_critical: bool) -> None:
        """
        Distribution des combinaisons avec gestion équitable des demi-parts.
        """
        try:
            logger.info(f"\nDistribution pour le {date}")

            # 1. Récupérer les combinaisons disponibles
            all_combinations = []
            for priority_level, combinations in WEEKDAY_PRIORITY_GROUPS.items():
                available = self._get_available_combinations_for_priority(
                    date, combinations, priority_level
                )
                if available:
                    all_combinations.extend(available)

            if not all_combinations:
                return

            # 2. Boucle principale
            progress_made = True
            max_iterations = 3
            remaining_combos = all_combinations.copy()

            while progress_made and max_iterations > 0:
                progress_made = False
                max_iterations -= 1

                # 2.1 Identifier les médecins sous leur minimum de groupe
                doctors_under_min = []
                for doctor in self.doctors:
                    if not self._is_doctor_available_for_weekday(doctor, date):
                        continue

                    doctor_intervals = intervals[doctor.name]
                    missing_groups = []

                    # Vérifier chaque groupe
                    for group, interval in doctor_intervals['groups'].items():
                        current = doctor_intervals['current_counts']['groups'].get(group, 0)
                        # Ajuster le minimum requis selon les demi-parts
                        min_required = interval.get('min', 0)
                        if doctor.half_parts == 1:
                            # Pour les demi-parts, on ajuste le minimum à 50%
                            min_required = max(1, min_required // 2)
                        
                        if current < min_required:
                            gap = min_required - current
                            missing_groups.append((group, gap))

                    if missing_groups:
                        # Score ajusté pour les demi-parts
                        total_gap = sum(gap for _, gap in missing_groups)
                        # Les demi-parts ont un score de base réduit mais pas pénalisé
                        base_score = total_gap * (1.0 if doctor.half_parts == 1 else 1.2)
                        # Ajout d'un petit facteur aléatoire pour éviter la monotonie
                        score = base_score * (1 + random.uniform(-0.1, 0.1))
                        doctors_under_min.append((doctor, missing_groups, score))

                if not doctors_under_min:
                    logger.info("Tous les minimums de groupe ajustés sont atteints")
                    break

                # 2.2 Trier les médecins avec un peu d'aléatoire pour varier les attributions
                random.shuffle(doctors_under_min)  # Mélange initial
                doctors_under_min.sort(key=lambda x: x[2], reverse=True)

                # 2.3 Distribution aux médecins
                for doctor, missing_groups, score in doctors_under_min:
                    # Filtrer les combinaisons pertinentes
                    relevant_combos = []
                    for combo in remaining_combos:
                        first_post = combo['first_post']
                        second_post = combo['second_post']
                        
                        first_group = self._get_post_group(first_post, date)
                        second_group = self._get_post_group(second_post, date)
                        
                        missing_group_names = [group for group, _ in missing_groups]
                        if (first_group in missing_group_names or 
                            second_group in missing_group_names):
                            # Calculer un score pour la combinaison
                            combo_score = combo['weight']
                            if doctor.half_parts == 1:
                                # Ajuster le score pour les demi-parts mais garder possible
                                combo_score *= 0.8
                            relevant_combos.append((combo, combo_score))

                    if not relevant_combos:
                        continue

                    # Trier les combinaisons par score
                    relevant_combos.sort(key=lambda x: x[1], reverse=True)

                    # Essayer d'attribuer la meilleure combinaison possible
                    for combo, _ in relevant_combos:
                        if self._can_assign_combination(doctor, date, combo, intervals[doctor.name]):
                            if self._assign_combination(doctor, date, combo, intervals[doctor.name]):
                                remaining_combos.remove(combo)
                                progress_made = True
                                logger.info(f"Attribution à {doctor.name}: {combo['combo']} "
                                        f"({'demi-part' if doctor.half_parts == 1 else 'plein temps'}, "
                                        f"score: {score:.2f})")
                                break

                if not progress_made:
                    logger.info("Aucune progression possible dans cette itération")

            # 3. Log des résultats
            self._log_distribution_results(intervals, date)

        except Exception as e:
            logger.error(f"Erreur distribution jour {date}: {e}")

    

    def _get_available_combinations_for_priority(self, date: date, 
                                            combinations: List[str],
                                            priority_level: str) -> List[Dict]:
        """
        Récupère les combinaisons disponibles pour un niveau de priorité donné.
        """
        available_combinations = []
        day = self.planning.get_day(date)
        if not day:
            return []

        # Collecter les slots non assignés
        unassigned_slots = defaultdict(list)
        for slot in day.slots:
            if not slot.assignee:
                unassigned_slots[slot.abbreviation].append(slot)

        # Pour chaque combinaison de ce niveau de priorité
        for combo in combinations:
            # Vérifier si c'est une combinaison personnalisée
            first_post, second_post = self._get_combo_posts(combo)

            if (first_post in unassigned_slots and second_post in unassigned_slots):
                weight = PRIORITY_WEIGHTS.get(priority_level, 1.0)
                available_combinations.append({
                    'combo': combo,
                    'first_post': first_post,
                    'second_post': second_post,
                    'priority': priority_level,
                    'weight': weight
                })

        return available_combinations

    def _get_combo_posts(self, combo: str) -> Tuple[str, str]:
        """Extrait les postes d'une combinaison standard ou personnalisée."""
        for custom_post in self.custom_posts.values():
            if combo in custom_post.possible_combinations.values():
                for post, combo_name in custom_post.possible_combinations.items():
                    if combo_name == combo:
                        return custom_post.name, post
        return combo[:2], combo[2:]

    def _get_doctors_under_minimum(self, intervals: Dict) -> List[Tuple[Doctor, Dict, float]]:
        """Version modifiée qui prend en compte les demi-parts pour les minimums"""
        doctors_under_min = []
        
        for doctor in self.doctors:
            doctor_intervals = intervals[doctor.name]
            min_gaps = []
            
            # Ajustement des minimums selon les demi-parts
            adjustment_factor = 0.6 if doctor.half_parts == 1 else 1.0
            
            # Vérifier les minimums de groupe
            for group, interval in doctor_intervals['groups'].items():
                current = doctor_intervals['current_counts']['groups'].get(group, 0)
                min_val = interval.get('min', 0)
                # Ajuster le minimum selon les demi-parts
                adjusted_min = min_val * adjustment_factor
                if current < adjusted_min:
                    gap_ratio = (adjusted_min - current) / adjusted_min
                    min_gaps.append(gap_ratio)

            # Vérifier les minimums de poste
            for post, interval in doctor_intervals['posts'].items():
                current = doctor_intervals['current_counts']['posts'].get(post, 0)
                min_val = interval.get('min', 0)
                # Ajuster le minimum selon les demi-parts
                adjusted_min = min_val * adjustment_factor
                if current < adjusted_min:
                    gap_ratio = (adjusted_min - current) / adjusted_min
                    min_gaps.append(gap_ratio)

            if min_gaps:
                avg_gap = sum(min_gaps) / len(min_gaps)
                doctors_under_min.append((doctor, doctor_intervals, avg_gap))

        return sorted(doctors_under_min, key=lambda x: x[2], reverse=True)

    def _get_single_indispo_doctors(self, date: date) -> List[Tuple[Doctor, int]]:
        """
        Identifie les médecins ayant une seule période d'indisponibilité.
        Retourne une liste de tuples (médecin, période_indisponible).
        """
        try:
            single_indispo_doctors = []

            for doctor in self.doctors:
                # Initialiser les périodes indisponibles
                indispo_periods = {1: False, 2: False, 3: False}  # Matin, AM, Soir
                
                # Vérifier chaque desiderata
                for desiderata in doctor.desiderata:
                    if desiderata.start_date <= date <= desiderata.end_date:
                        # Ne prendre en compte que les desiderata primaires
                        if not hasattr(desiderata, 'priority') or desiderata.priority == "primary":
                            period = desiderata.period
                            if 1 <= period <= 3:  # Vérifier que la période est valide
                                indispo_periods[period] = True

                # Compter le nombre de périodes indisponibles
                total_indispo = sum(1 for indispo in indispo_periods.values() if indispo)
                
                # Si exactement une période indisponible
                if total_indispo == 1:
                    # Trouver la période indisponible
                    indispo_period = next(period for period, is_indispo in indispo_periods.items() if is_indispo)
                    single_indispo_doctors.append((doctor, indispo_period))
                    logger.info(f"Médecin détecté avec une seule indisponibilité: {doctor.name} "
                            f"(période {indispo_period})")

            return single_indispo_doctors

        except Exception as e:
            logger.error(f"Erreur détection médecins indisponibles: {e}")
            return []
    
    def _distribute_to_single_indispo_doctors(self, date: date,
                                        available_combos: List[Dict],
                                        single_indispo_doctors: List[Tuple[Doctor, int]],
                                        intervals: Dict) -> List[Dict]:
        """
        Distribution aux médecins avec une seule indisponibilité.
        """
        try:
            remaining_combos = available_combos.copy()
            if not remaining_combos or not single_indispo_doctors:
                return remaining_combos

            logger.info(f"\nDistribution aux médecins indisponibles pour le {date}")

            # Pour chaque médecin avec une indisponibilité
            for doctor, indispo_period in single_indispo_doctors:
                if not self._is_doctor_available_for_weekday(doctor, date):
                    continue

                doctor_intervals = intervals[doctor.name]
                logger.info(f"\nTraitement {doctor.name} - indispo période {indispo_period}")

                # Trouver les combinaisons compatibles
                compatible_combos = self._filter_compatible_combinations(
                    doctor, date, remaining_combos, indispo_period
                )

                if compatible_combos:
                    # Trier par priorité
                    for priority_level in ['high_priority', 'medium_priority', 'low_priority']:
                        priority_combos = [
                            combo for combo in compatible_combos 
                            if combo['priority'] == priority_level
                        ]

                        if priority_combos:
                            # Trouver la meilleure combinaison
                            best_combo = self._find_best_combination(
                                doctor, date, priority_combos,
                                doctor_intervals
                            )

                            if best_combo and self._can_assign_combination(
                                doctor, date, best_combo, doctor_intervals
                            ):
                                # Attribuer la combinaison
                                if self._assign_combination(
                                    doctor, date, best_combo, doctor_intervals
                                ):
                                    remaining_combos.remove(best_combo)
                                    logger.info(f"Attribution réussie à {doctor.name}: "
                                            f"{best_combo['combo']} (indispo période {indispo_period})")
                                    break

            return remaining_combos

        except Exception as e:
            logger.error(f"Erreur distribution médecins indispo: {e}")
            return available_combos

    def _is_combo_compatible_with_indispo(self, combo: Dict, 
                                    indispo_period: int,
                                    period_mapping: Dict) -> bool:
        """
        Vérifie si une combinaison est compatible avec une période d'indisponibilité.
        """
        try:
            def get_post_period(post_type: str) -> Optional[int]:
                # Posts du matin
                if post_type in ["MM", "CM", "HM", "SM", "RM", "ML"]:
                    return 1
                # Posts de l'après-midi
                elif post_type in ["CA", "HA", "SA", "RA", "AL", "AC"]:
                    return 2
                # Posts du soir
                elif post_type in ["CS", "HS", "SS", "RS", "NA", "NM", "NC"]:
                    return 3
                
                # Poste personnalisé
                if post_type in self.custom_posts:
                    custom_post = self.custom_posts[post_type]
                    start_hour = custom_post.start_time.hour
                    
                    # Déterminer la période selon l'heure de début
                    if 7 <= start_hour < 13:
                        return 1
                    elif 13 <= start_hour < 18:
                        return 2
                    else:
                        return 3
                        
                return None

            first_period = get_post_period(combo['first_post'])
            second_period = get_post_period(combo['second_post'])

            # La combinaison est compatible si aucun des postes n'est dans la période indisponible
            return first_period != indispo_period and second_period != indispo_period

        except Exception as e:
            logger.error(f"Erreur vérification compatibilité: {e}")
            return False

    def _find_best_combination_for_indispo(self, doctor: Doctor, date: date,
                                        combos: List[Dict], doctor_intervals: Dict,
                                        indispo_period: int,
                                        period_mapping: Dict) -> Optional[Dict]:
        """
        Trouve la meilleure combinaison pour un médecin avec une indisponibilité.
        Prend en compte:
        - La compatibilité avec l'indisponibilité
        - La priorité de la combinaison
        - L'écart aux minimums
        - La répartition des périodes
        """
        try:
            best_combo = None
            best_score = float('-inf')

            for combo in combos:
                if not self._is_combo_compatible_with_indispo(
                    combo, indispo_period, period_mapping
                ):
                    continue

                # Calculer un score pour cette combinaison
                score = combo['weight']  # Score de base selon la priorité

                # Bonus si la combinaison aide à atteindre les minimums
                min_bonus = 0
                for post in [combo['first_post'], combo['second_post']]:
                    current = doctor_intervals['current_counts']['posts'].get(post, 0)
                    min_val = doctor_intervals['posts'].get(post, {}).get('min', 0)
                    if min_val > 0 and current < min_val:
                        min_bonus += (min_val - current) / min_val

                score += min_bonus * 0.5  # Bonus modéré pour les minimums

                # Vérifier si la combinaison est possible
                if self._can_assign_combination(doctor, date, combo, doctor_intervals):
                    # Facteur aléatoire (±10%)
                    score *= 1 + (random.random() * 0.2 - 0.1)

                    if score > best_score:
                        best_score = score
                        best_combo = combo

            return best_combo

        except Exception as e:
            logger.error(f"Erreur recherche meilleure combinaison indispo: {e}")
            return None

    def _get_eligible_doctors(self, date: date, available_combos: List[str],
                        intervals: Dict, is_critical: bool) -> List[Tuple[Doctor, float]]:
        """
        Identifie et score les médecins éligibles pour un jour donné.
        """
        try:
            eligible_doctors = []

            for doctor in self.doctors:
                # Vérifier la disponibilité de base
                if not self._is_doctor_available_for_weekday(doctor, date):
                    continue

                # Calculer le score d'éligibilité
                score = self._calculate_eligibility_score(
                    doctor, date, intervals[doctor.name],
                    is_critical
                )

                if score > 0:
                    eligible_doctors.append((doctor, score))

            # Trier par score décroissant
            return sorted(eligible_doctors, key=lambda x: x[1], reverse=True)

        except Exception as e:
            logger.error(f"Erreur calcul éligibilité: {e}")
            return []

    def _calculate_eligibility_score(self, doctor: Doctor, date: date,
                                    doctor_intervals: Dict, is_critical: bool) -> float:
        """
        Calcule un score d'éligibilité pour un médecin avec gestion équitable des demi-parts.
        """
        try:
            # Score de base standard pour tous les médecins
            base_score = 1.0

            # 1. Écart aux minimums de groupe
            min_scores = []
            for group, interval in doctor_intervals['groups'].items():
                current = doctor_intervals['current_counts']['groups'].get(group, 0)
                min_val = interval.get('min', 0)
                if min_val > 0:  # Pour éviter la division par zéro
                    if current < min_val:
                        gap_ratio = (min_val - current) / min_val
                        min_scores.append(gap_ratio)

            if min_scores:
                # Bonus pour les minimums non atteints
                min_bonus = sum(min_scores) / len(min_scores)
                base_score *= (1 + min_bonus)

            # 2. Équilibrage des attributions
            total_assignments = sum(
                doctor_intervals['current_counts']['groups'].get(group, 0)
                for group in doctor_intervals['groups']
            )
            if total_assignments < len(doctor_intervals['groups']):
                base_score *= 1.2  # Bonus pour sous-utilisation

            # 3. Bonus période critique
            if is_critical:
                base_score *= 1.3  # +30% pour les périodes critiques

            # 4. Facteur aléatoire réduit (±5% au lieu de ±10%)
            base_score *= 1 + (random.random() * 0.1 - 0.05)

            return max(0.1, base_score)  # Score minimum de 0.1

        except Exception as e:
            logger.error(f"Erreur calcul score éligibilité: {e}")
            return 0.1  # Score par défaut en cas d'erreur


    def _count_indispo_periods(self, doctor: Doctor, date: date) -> int:
        """
        Compte le nombre de périodes d'indisponibilité pour un médecin à une date donnée.
        """
        periods_indispo = 0
        morning_indispo = False
        afternoon_indispo = False
        evening_indispo = False

        for desiderata in doctor.desiderata:
            if desiderata.start_date <= date <= desiderata.end_date:
                if desiderata.period == 1:  # Matin
                    morning_indispo = True
                elif desiderata.period == 2:  # Après-midi
                    afternoon_indispo = True
                elif desiderata.period == 3:  # Soir
                    evening_indispo = True

        return sum([morning_indispo, afternoon_indispo, evening_indispo])

    def _distribute_to_doctors_under_minimum(self, date: date, 
                                        available_combos: List[Dict],
                                        doctors_under_min: List[Tuple[Doctor, Dict, float]],
                                        intervals: Dict) -> List[Dict]:
        """
        Distribution prioritaire aux médecins sous leur minimum.
        Respecte strictement l'ordre de priorité des combinaisons.
        """
        remaining_combos = available_combos.copy()
        
        # Grouper les combinaisons par niveau de priorité
        priority_groups = defaultdict(list)
        for combo in remaining_combos:
            priority_groups[combo['priority']].append(combo)

        # Pour chaque niveau de priorité, dans l'ordre
        for priority_level in ['high_priority', 'medium_priority', 'low_priority']:
            priority_combos = priority_groups[priority_level]
            if not priority_combos:
                continue

            # Pour chaque médecin sous minimum
            for doctor, doctor_intervals, gap in doctors_under_min:
                if not self._is_doctor_available_for_weekday(doctor, date):
                    continue

                # Trouver la meilleure combinaison de ce niveau pour ce médecin
                best_combo = self._find_best_combination(
                    doctor, date, priority_combos, doctor_intervals
                )

                if best_combo and self._assign_combination(
                    doctor, date, best_combo, doctor_intervals
                ):
                    remaining_combos.remove(best_combo)
                    priority_combos.remove(best_combo)
                    logger.info(f"Attribution prioritaire à {doctor.name}: "
                            f"{best_combo['combo']} (sous minimum, gap: {gap:.2f})")

        return remaining_combos

    def _verify_doctor_distribution(self, intervals: Dict) -> bool:
        """
        Vérifie que la distribution finale respecte les contraintes.
        """
        all_ok = True
        logger.info("\nVÉRIFICATION FINALE DISTRIBUTION MÉDECINS")

        for doctor_name, doctor_intervals in intervals.items():
            logger.info(f"\n{doctor_name}:")
            
            # Vérifier les minimums de groupe
            for group, interval in doctor_intervals['groups'].items():
                current = doctor_intervals['current_counts']['groups'][group]
                min_val = interval.get('min', 0)
                max_val = interval.get('max', float('inf'))
                
                status = "OK"
                if current < min_val:
                    status = "SOUS MIN"
                    all_ok = False
                elif current > max_val:
                    status = "SUR MAX"
                    all_ok = False
                    
                logger.info(f"Groupe {group}: {current} [{min_val}-{max_val}] ({status})")

            # Vérifier les postes individuels
            for post, count in doctor_intervals['current_counts']['posts'].items():
                interval = doctor_intervals['posts'].get(post, {})
                min_val = interval.get('min', 0)
                max_val = interval.get('max', float('inf'))
                
                status = "OK"
                if count < min_val:
                    status = "SOUS MIN"
                    all_ok = False
                elif count > max_val:
                    status = "SUR MAX"
                    all_ok = False
                    
                logger.info(f"Poste {post}: {count} [{min_val}-{max_val}] ({status})")

        return all_ok
        
        
        
    def _get_available_combinations(self, date: date) -> List[Dict]:
        """
        Récupère toutes les combinaisons disponibles pour un jour donné.
        Retourne une liste de dictionnaires contenant :
        - combo: code de la combinaison
        - first_post: premier poste
        - second_post: deuxième poste
        - priority: niveau de priorité
        - weight: poids de la combinaison
        """
        try:
            available_combinations = []
            day = self.planning.get_day(date)
            if not day:
                return []

            # Récupérer les slots non assignés
            unassigned_slots = defaultdict(list)
            for slot in day.slots:
                if not slot.assignee:
                    unassigned_slots[slot.abbreviation].append(slot)

            # Pour chaque niveau de priorité
            for priority_level, combinations in WEEKDAY_PRIORITY_GROUPS.items():
                for combo in combinations:
                    # Vérifier si c'est une combinaison personnalisée
                    is_custom = False
                    for custom_post in self.custom_posts.values():
                        if combo in custom_post.possible_combinations.values():
                            is_custom = True
                            for post, combo_name in custom_post.possible_combinations.items():
                                if combo_name == combo:
                                    first_post = custom_post.name
                                    second_post = post
                                    break
                            break

                    # Si ce n'est pas personnalisé, extraire les postes standard
                    if not is_custom:
                        first_post, second_post = combo[:2], combo[2:]

                    # Vérifier la disponibilité des deux slots
                    if (first_post in unassigned_slots and second_post in unassigned_slots):
                        # Calculer le poids selon la priorité
                        weight = PRIORITY_WEIGHTS.get(priority_level, 1.0)
                        
                        available_combinations.append({
                            'combo': combo,
                            'first_post': first_post,
                            'second_post': second_post,
                            'priority': priority_level,
                            'weight': weight
                        })

            return available_combinations

        except Exception as e:
            logger.error(f"Erreur récupération combinaisons disponibles: {e}")
            return []

    def _find_best_combination(self, doctor: Doctor, date: date,
                            available_combos: List[Dict],
                            doctor_intervals: Dict) -> Optional[Dict]:
        """
        Trouve la meilleure combinaison en tenant compte des demi-parts.
        """
        try:
            best_combo = None
            best_score = -float('inf')

            for combo_info in available_combos:
                if not self._can_assign_combination(doctor, date, combo_info, doctor_intervals):
                    continue

                # Score de base selon la priorité
                score = combo_info['weight']

                # Bonus pour les minimums non atteints
                for post in [combo_info['first_post'], combo_info['second_post']]:
                    current = doctor_intervals['current_counts']['posts'].get(post, 0)
                    min_val = doctor_intervals['posts'].get(post, {}).get('min', 0)
                    
                    if min_val > 0 and current < min_val:
                        score *= 1.2  # Bonus de 20% pour les postes sous minimum

                # Facteur aléatoire réduit pour plus de stabilité
                score *= 1 + (random.random() * 0.1 - 0.05)  # ±5%

                if score > best_score:
                    best_score = score
                    best_combo = combo_info

            return best_combo

        except Exception as e:
            logger.error(f"Erreur recherche meilleure combinaison: {e}")
            return None

    def _can_assign_combination(self, doctor: Doctor, date: date,
                            combo_info: Dict, doctor_intervals: Dict) -> bool:
        """
        Vérifie si une combinaison peut être attribuée en respectant strictement
        les limites de groupe pour chaque poste.
        """
        try:
            day = self.planning.get_day(date)
            if not day:
                return False

            first_post = combo_info['first_post']
            second_post = combo_info['second_post']

            # 1. Vérification stricte des limites de groupe pour chaque poste
            first_group = self._get_post_group(first_post, date)
            second_group = self._get_post_group(second_post, date)

            # Vérifier le premier poste
            if first_group:
                current_first = doctor_intervals['current_counts']['groups'].get(first_group, 0)
                max_first = doctor_intervals['groups'].get(first_group, {}).get('max', float('inf'))
                if current_first >= max_first:
                    logger.debug(f"Limite de groupe {first_group} atteinte pour {doctor.name}")
                    return False

            # Vérifier le second poste
            if second_group:
                # Si même groupe que le premier poste, compter l'impact cumulé
                if second_group == first_group:
                    current = doctor_intervals['current_counts']['groups'].get(second_group, 0)
                    max_allowed = doctor_intervals['groups'].get(second_group, {}).get('max', float('inf'))
                    if current + 2 > max_allowed:  # +2 car deux postes du même groupe
                        logger.debug(f"Limite cumulée de groupe {second_group} dépassée pour {doctor.name}")
                        return False
                else:
                    current_second = doctor_intervals['current_counts']['groups'].get(second_group, 0)
                    max_second = doctor_intervals['groups'].get(second_group, {}).get('max', float('inf'))
                    if current_second >= max_second:
                        logger.debug(f"Limite de groupe {second_group} atteinte pour {doctor.name}")
                        return False

            # 2. Vérifier les limites de poste individuels
            for post in [first_post, second_post]:
                current = doctor_intervals['current_counts']['posts'].get(post, 0)
                max_allowed = doctor_intervals['posts'].get(post, {}).get('max', float('inf'))
                if current >= max_allowed:
                    logger.debug(f"Limite de poste {post} atteinte pour {doctor.name}")
                    return False

            # 3. Vérifier la disponibilité des slots
            first_slot = next((s for s in day.slots 
                            if s.abbreviation == first_post and not s.assignee), None)
            second_slot = next((s for s in day.slots 
                            if s.abbreviation == second_post and not s.assignee), None)

            if not (first_slot and second_slot):
                return False

            # 4. Vérifier les contraintes générales
            return (self.constraints.can_assign_to_assignee(doctor, date, first_slot, self.planning) and
                    self.constraints.can_assign_to_assignee(doctor, date, second_slot, self.planning))

        except Exception as e:
            logger.error(f"Erreur vérification attribution: {e}")
            return False

    def _calculate_combination_score(self, doctor: Doctor,
                                combo_info: Dict,
                                doctor_intervals: Dict) -> float:
        """
        Calcule un score pour une combinaison.
        """
        try:
            score = combo_info['weight']  # Score de base selon la priorité

            # 1. Bonus pour les postes sous minimum
            for post in [combo_info['first_post'], combo_info['second_post']]:
                current = doctor_intervals['current_counts']['posts'].get(post, 0)
                min_required = doctor_intervals['posts'].get(post, {}).get('min', 0)
                if current < min_required:
                    score *= 1.2  # +20% si sous minimum

            # 2. Bonus pour les groupes sous minimum
            affected_groups = set()
            for post in [combo_info['first_post'], combo_info['second_post']]:
                group = self._get_post_group(post, datetime.now().date())
                if group:
                    affected_groups.add(group)

            for group in affected_groups:
                current = doctor_intervals['current_counts']['groups'].get(group, 0)
                min_required = doctor_intervals['groups'].get(group, {}).get('min', 0)
                if current < min_required:
                    score *= 1.3  # +30% si groupe sous minimum

            # 3. Malus si proche du maximum
            for post in [combo_info['first_post'], combo_info['second_post']]:
                current = doctor_intervals['current_counts']['posts'].get(post, 0)
                max_allowed = doctor_intervals['posts'].get(post, {}).get('max', float('inf'))
                if max_allowed < float('inf'):  # Si un maximum est défini
                    ratio = current / max_allowed
                    if ratio > 0.8:  # À plus de 80% du maximum
                        score *= (1 - (ratio - 0.8))  # Réduction progressive

            # 4. Facteur aléatoire (±10%)
            score *= 1 + (random.random() * 0.2 - 0.1)

            return max(0.1, score)

        except Exception as e:
            logger.error(f"Erreur calcul score combinaison: {e}")
            return 0.0

    def _assign_combination(self, doctor: Doctor, date: date,
                            combo_info: Dict, doctor_intervals: Dict) -> bool:
        """
        Attribue une combinaison à un médecin avec vérification stricte des limites de groupe.
        Double vérification avant attribution pour éviter tout dépassement.
        """
        try:
            # 1. Double vérification des limites avant attribution
            if not self._can_assign_combination(doctor, date, combo_info, doctor_intervals):
                return False

            day = self.planning.get_day(date)
            first_post = combo_info['first_post']
            second_post = combo_info['second_post']

            # 2. Récupération et vérification des slots
            first_slot = next((s for s in day.slots 
                            if s.abbreviation == first_post and not s.assignee), None)
            second_slot = next((s for s in day.slots 
                            if s.abbreviation == second_post and not s.assignee), None)

            if not (first_slot and second_slot):
                return False

            # 3. Vérification finale des limites de groupe
            first_group = self._get_post_group(first_post, date)
            second_group = self._get_post_group(second_post, date)

            # Vérifier une dernière fois les limites de groupe
            current_counts = doctor_intervals['current_counts']['groups']
            if first_group:
                current_first = current_counts.get(first_group, 0)
                max_first = doctor_intervals['groups'].get(first_group, {}).get('max', float('inf'))
                if current_first >= max_first:
                    logger.debug(f"Limite finale de groupe {first_group} atteinte pour {doctor.name}")
                    return False

            if second_group:
                if second_group == first_group:
                    # Vérification spéciale si même groupe
                    current = current_counts.get(second_group, 0)
                    max_allowed = doctor_intervals['groups'].get(second_group, {}).get('max', float('inf'))
                    if current + 2 > max_allowed:
                        logger.debug(f"Limite finale cumulée de groupe {second_group} dépassée pour {doctor.name}")
                        return False
                else:
                    current_second = current_counts.get(second_group, 0)
                    max_second = doctor_intervals['groups'].get(second_group, {}).get('max', float('inf'))
                    if current_second >= max_second:
                        logger.debug(f"Limite finale de groupe {second_group} atteinte pour {doctor.name}")
                        return False

            # 4. Attribution des slots
            first_slot.assignee = doctor.name
            second_slot.assignee = doctor.name

            # 5. Mise à jour des compteurs de postes
            doctor_intervals['current_counts']['posts'][first_post] = \
                doctor_intervals['current_counts']['posts'].get(first_post, 0) + 1
            doctor_intervals['current_counts']['posts'][second_post] = \
                doctor_intervals['current_counts']['posts'].get(second_post, 0) + 1

            # 6. Mise à jour des compteurs de groupe
            if first_group:
                current_counts[first_group] = current_counts.get(first_group, 0) + 1
            if second_group and second_group != first_group:
                current_counts[second_group] = current_counts.get(second_group, 0) + 1

            logger.info(f"Attribution à {doctor.name}: {combo_info['combo']} le {date} "
                    f"(groupes: {first_group}, {second_group})")
            return True

        except Exception as e:
            logger.error(f"Erreur attribution combinaison: {e}")
            return False

    def _get_post_group(self, post_type: str, date: date) -> Optional[str]:
        """
        Détermine le groupe de semaine d'un poste.
        """
        # Si c'est un poste personnalisé
        if post_type in self.custom_posts:
            return self.custom_posts[post_type].statistic_group

        # Groupes de consultation en fonction de l'heure
        if post_type in ["CM", "HM"]:
            return "XM"  # Consultation matin à partir de 9h
        elif post_type in ["MM", "SM", "RM"]:
            return "XmM"  # Consultation matin à partir de 7h
        elif post_type in ["CA", "HA", "SA", "RA", "CT"]:
            return "XA"  # Consultation après-midi
        elif post_type in ["CS", "HS", "SS", "RS"]:
            return "XS"  # Consultation soir

        # Groupes de visites
        elif post_type in ["ML"]:
            return "Vm"  # Visites matin
        elif post_type in ["AL", "AC"]:
            return "Va"  # Visites après-midi

        # Groupe nuit
        elif post_type in ["NM", "NC", "NA"]:
            return "NMC"  # Groupe nuit

        return None
        
        
        
    def _distribute_remaining_combinations(self, date: date,
                                        remaining_combos: List[Dict],
                                        eligible_doctors: List[Tuple[Doctor, float]],
                                        intervals: Dict) -> None:
        """
        Distribution équilibrée des combinaisons restantes.
        """
        try:
            if not remaining_combos or not eligible_doctors:
                return

            # Trier les médecins par score d'éligibilité
            sorted_doctors = sorted(eligible_doctors, key=lambda x: x[1], reverse=True)

            # Distribution équilibrée
            max_iterations = 3
            progress_made = True

            while remaining_combos and progress_made and max_iterations > 0:
                progress_made = False
                random.shuffle(sorted_doctors)  # Mélanger pour plus d'équité

                for doctor, base_score in sorted_doctors:
                    if self._has_assignment_for_day(doctor, date):
                        continue

                    adjusted_score = self._calculate_current_need_score(
                        doctor, intervals[doctor.name], remaining_combos
                    )

                    if adjusted_score > 0:
                        # Filtrer les combinaisons compatibles en vérifiant toutes les indisponibilités
                        compatible_combos = self._filter_compatible_combinations(
                            doctor, date, remaining_combos
                        )

                        if compatible_combos:
                            best_combo = self._find_best_combination(
                                doctor, date, compatible_combos, intervals[doctor.name]
                            )

                            if best_combo and self._assign_combination(
                                doctor, date, best_combo, intervals[doctor.name]
                            ):
                                remaining_combos.remove(best_combo)
                                progress_made = True
                                break  

                max_iterations -= 1

            if remaining_combos:
                logger.warning(f"Combinaisons non attribuées pour {date}: "
                            f"{[c['combo'] for c in remaining_combos]}")

        except Exception as e:
            logger.error(f"Erreur distribution restante: {e}")

    def _filter_compatible_combinations(self, doctor: Doctor, date: date,
                                    available_combos: List[Dict],
                                    indispo_period: Optional[int] = None) -> List[Dict]:
        """
        Filtre les combinaisons compatibles avec les indisponibilités d'un médecin.
        Si indispo_period est fourni, ne vérifie que cette période spécifique.
        Sinon, vérifie toutes les indisponibilités du médecin.
        """
        try:
            # Mapping des postes par période
            post_periods = {
                # Période 1 : Matin (7h-12h59)
                1: ["MM", "CM", "HM", "SM", "RM", "ML"],
                # Période 2 : Après-midi (13h-17h59)
                2: ["CA", "HA", "SA", "RA", "AL", "AC"],
                # Période 3 : Soir (18h-7h)
                3: ["CS", "HS", "SS", "RS", "NA", "NM", "NC"]
            }

            def get_post_period(post: str) -> Optional[int]:
                # Vérifier d'abord si c'est un poste personnalisé
                if post in self.custom_posts:
                    custom_post = self.custom_posts[post]
                    start_hour = custom_post.start_time.hour
                    if 7 <= start_hour < 13:
                        return 1
                    elif 13 <= start_hour < 18:
                        return 2
                    else:
                        return 3
                
                # Sinon chercher dans les postes standards
                for period, posts in post_periods.items():
                    if post in posts:
                        return period
                return None

            # Si une période spécifique est fournie, utiliser uniquement celle-ci
            if indispo_period is not None:
                indispo_periods = {indispo_period}
            else:
                # Sinon, détecter toutes les périodes indisponibles
                indispo_periods = set()
                for desiderata in doctor.desiderata:
                    if desiderata.start_date <= date <= desiderata.end_date:
                        if not hasattr(desiderata, 'priority') or desiderata.priority == "primary":
                            if 1 <= desiderata.period <= 3:
                                indispo_periods.add(desiderata.period)

            # Filtrer les combinaisons
            compatible_combos = []
            for combo in available_combos:
                first_post = combo['first_post']
                second_post = combo['second_post']
                
                first_period = get_post_period(first_post)
                second_period = get_post_period(second_post)
                
                if first_period is None or second_period is None:
                    continue
                    
                # Une combinaison est compatible si aucun de ses postes
                # n'est dans une période indisponible
                if not any(period in indispo_periods 
                        for period in [first_period, second_period]):
                    compatible_combos.append(combo)
                    if indispo_period is not None:
                        logger.debug(f"Combinaison compatible trouvée: {combo['combo']} "
                                f"pour {doctor.name} avec indispo période {indispo_period}")

            return compatible_combos

        except Exception as e:
            logger.error(f"Erreur filtrage combinaisons: {e}")
            return []
    def _has_assignment_for_day(self, doctor: Doctor, date: date) -> bool:
        """
        Vérifie si un médecin a déjà une attribution pour ce jour.
        """
        day = self.planning.get_day(date)
        if not day:
            return False

        return any(slot.assignee == doctor.name for slot in day.slots)

    def _calculate_current_need_score(self, doctor: Doctor, doctor_intervals: Dict,
                                    remaining_combos: List[Dict]) -> float:
        """
        Calcule un score de besoin actuel pour un médecin.
        Prend en compte:
        - Distance aux minimums non atteints
        - Nombre de demi-parts
        - Équilibre entre les différents types de poste
        """
        try:
            score = 1.0

            # 1. Score basé sur les minimums non atteints
            group_min_scores = []
            for group, interval in doctor_intervals['groups'].items():
                current = doctor_intervals['current_counts']['groups'].get(group, 0)
                min_val = interval.get('min', 0)
                if min_val > 0:
                    ratio = current / min_val
                    if ratio < 1:
                        group_min_scores.append(1 - ratio)

            if group_min_scores:
                score *= (1 + sum(group_min_scores) / len(group_min_scores))

            # 2. Bonus pour les pleins temps sous-utilisés
            if doctor.half_parts == 2:
                total_assignments = sum(
                    doctor_intervals['current_counts']['groups'].get(group, 0)
                    for group in doctor_intervals['groups']
                )
                if total_assignments < len(doctor_intervals['groups']):
                    score *= 1.2

            # 3. Malus si proche des maximums
            max_ratios = []
            for group, interval in doctor_intervals['groups'].items():
                current = doctor_intervals['current_counts']['groups'].get(group, 0)
                max_val = interval.get('max', float('inf'))
                if max_val < float('inf'):
                    ratio = current / max_val
                    if ratio > 0.8:  # À plus de 80% du maximum
                        max_ratios.append(ratio)

            if max_ratios:
                avg_max_ratio = sum(max_ratios) / len(max_ratios)
                score *= (1 - (avg_max_ratio - 0.8))

            # 4. Facteur aléatoire (±10%)
            score *= 1 + (random.random() * 0.2 - 0.1)

            return max(0.1, score)

        except Exception as e:
            logger.error(f"Erreur calcul score besoin: {e}")
            return 0.0
        
        
        
        
        
        
        
        
        
        
        
    def distribute_remaining_weekday_posts(self) -> bool:
        """
        Distribution des postes restants de semaine après la distribution des combinaisons.
        """
        try:
            logger.info("\nDISTRIBUTION DES POSTES RESTANTS SEMAINE")
            logger.info("=" * 80)

            # 1. Collecter et analyser les postes restants
            remaining_posts = self._collect_remaining_weekday_posts()
            if not remaining_posts:
                logger.info("Aucun poste restant à distribuer")
                return True

            # Log des postes à distribuer
            total_slots = sum(len(slots) for slots in remaining_posts.values())
            logger.info(f"Postes restants à distribuer: {total_slots}")

            # 2. Préparation de la matrice de disponibilité
            availability_matrix = AvailabilityMatrix(
                self.planning.start_date,
                self.planning.end_date,
                self.doctors,
                self.cats
            )

            # 3. Organisation et tri des dates
            weekdays = self._get_weekdays(self.planning)
            dates_by_criticality = self._organize_dates_by_criticality(
                weekdays, 
                availability_matrix
            )

            # 4. Phase 1 - Distribution aux CAT
            logger.info("\nPHASE 1: DISTRIBUTION AUX CAT")
            self._distribute_remaining_to_cats(
                remaining_posts,
                dates_by_criticality
            )

            # 5. Préparation distribution médecins
            intervals = self._get_doctor_weekday_intervals()
            if not intervals:
                logger.error("Impossible de récupérer les intervalles - arrêt distribution")
                return True
                
            # 6. Phase 2 - Distribution aux médecins en plusieurs étapes
            logger.info("\nPHASE 2: DISTRIBUTION AUX MÉDECINS")
            quota_tracker = QuotaTracker(self.planning, self.doctors, "weekday")
            
            # 6.1 Distribution des minimums
            remaining_posts = self._distribute_doctor_minimums(
                remaining_posts,
                dates_by_criticality,
                quota_tracker,
                intervals
            )

            # 6.2 Distribution avec flexibilité de type
            if remaining_posts:
                remaining_posts = self._distribute_with_type_flexibility(
                    remaining_posts,
                    dates_by_criticality,
                    quota_tracker,
                    intervals
                )

            # 6.3 Distribution équilibrée
            if remaining_posts:
                remaining_posts = self._distribute_remaining_balanced(
                    remaining_posts,
                    dates_by_criticality,
                    quota_tracker,
                    intervals
                )

            # 6.4 Distribution avec contraintes assouplies
            if remaining_posts:
                self._distribute_with_relaxed_constraints(
                    remaining_posts,
                    dates_by_criticality,
                    quota_tracker,
                    intervals
                )

            # 7. Vérification finale
            unassigned = sum(
                len([slot for date, slot in slots if not slot.assignee])
                for slots in remaining_posts.values()
            )

            if unassigned > 0:
                logger.warning(f"\nDistribution incomplète: {unassigned} postes non attribués")
                self._log_unassigned_posts(remaining_posts)
            else:
                logger.info("\nDistribution complète - tous les postes ont été attribués")

            return True

        except Exception as e:
            logger.error(f"Erreur dans la distribution des postes restants: {e}", 
                        exc_info=True)
            return True

    def _collect_remaining_weekday_posts(self) -> Dict[str, List[Tuple[date, TimeSlot]]]:
        """
        Collecte tous les postes non attribués de la semaine, y compris les vendredis
        sauf NLv qui sont gérés séparément.
        
        Returns:
            Dict[str, List[Tuple[date, TimeSlot]]]: Postes non attribués organisés par type
        """
        remaining = defaultdict(list)
        total_slots = 0

        for day in self.planning.days:
            # On vérifie chaque jour sauf weekend et fériés
            if day.is_weekend or day.is_holiday_or_bridge:
                continue

            # Pour le vendredi, prendre tous les postes SAUF NLv
            is_friday = day.date.weekday() == 4
                
            for slot in day.slots:
                # Ne pas inclure NLv le vendredi
                if is_friday and slot.abbreviation == "NL":
                    continue
                    
                if not slot.assignee:
                    remaining[slot.abbreviation].append((day.date, slot))
                    total_slots += 1

        # Log détaillé pour vérification
        logger.info("\nPostes restants à distribuer:")
        logger.info(f"Total: {total_slots} slots")
        for post_type, slots in remaining.items():
            if slots:
                # Log par type
                day_counts = defaultdict(int)
                for date, _ in slots:
                    if date.weekday() == 4:
                        day_counts['vendredi'] += 1
                    else:
                        day_counts['semaine'] += 1
                        
                logger.info(f"{post_type}: {len(slots)} slots "
                        f"(semaine: {day_counts['semaine']}, "
                        f"vendredi: {day_counts['vendredi']})")

        return remaining

    def _organize_dates_by_criticality(self, weekdays: List[date],
                                    availability_matrix: AvailabilityMatrix) -> Dict:
        """
        Organise les dates de semaine par niveau de criticité basé sur la disponibilité du personnel.
        
        Args:
            weekdays: Liste des dates de semaine à organiser
            availability_matrix: Matrice de disponibilité pour l'analyse
        
        Returns:
            Dict avec deux clés 'critical' et 'normal' contenant les listes de dates
        """
        organized_dates = {
            'critical': [],
            'normal': []
        }
        
        for date in weekdays:
            # Calculer la disponibilité pour cette date
            available_count = sum(
                1 for person in self.doctors + self.cats
                if availability_matrix.get_period_availability(person.name, date, "morning")
            )
            total_personnel = len(self.doctors) + len(self.cats)
            
            if total_personnel == 0:
                continue
                
            availability = (available_count / total_personnel) * 100
            
            # Classifier la date selon la disponibilité
            if availability < 40:  # Période critique si moins de 40% de disponibilité
                organized_dates['critical'].append(date)
            else:
                organized_dates['normal'].append(date)
                
        # Mélanger les dates dans chaque catégorie pour plus d'équité
        random.shuffle(organized_dates['critical'])
        random.shuffle(organized_dates['normal'])
        
        # Log de la répartition
        logger.info("\nRépartition des dates de semaine:")
        logger.info(f"Périodes critiques: {len(organized_dates['critical'])} dates")
        logger.info(f"Périodes normales: {len(organized_dates['normal'])} dates")
        
        return organized_dates

    def _distribute_remaining_to_cats(self, remaining_posts: Dict, dates_by_criticality: Dict) -> None:
        """Distribution des postes restants aux CAT avec gestion correcte des quotas."""
        try:
            logger.info("\nDISTRIBUTION DES POSTES RESTANTS AUX CAT")
            
            # Initialisation du tracker de quotas
            quota_tracker = QuotaTracker(self.planning, self.cats, "weekday")
            
            # Pour chaque niveau de criticité
            for criticality in ['critical', 'normal']:
                logger.info(f"\nTraitement des périodes {criticality}")
                dates = dates_by_criticality[criticality]
                
                if not dates:
                    continue
                    
                # Pour chaque date du niveau actuel
                for current_date in dates:
                    # Récupérer les postes disponibles pour cette date
                    available_posts = self._get_available_posts_for_date(
                        current_date, remaining_posts
                    )
                    
                    if not available_posts:
                        continue
                        
                    # Traiter chaque CAT dans un ordre aléatoire
                    cats = list(self.cats)
                    random.shuffle(cats)
                    
                    for cat in cats:
                        if not self._is_cat_available_for_weekday(cat, current_date):
                            continue
                            
                        # Récupérer les quotas restants pour ce CAT
                        remaining_quotas = quota_tracker.get_remaining_quotas(cat)
                        if not remaining_quotas:
                            continue

                        # Pour chaque type de poste disponible
                        for post_type, slots in available_posts.items():
                            # Vérifier le quota restant avec la nouvelle méthode
                            quota_left = self._get_remaining_quota(remaining_quotas, post_type)
                            if quota_left <= 0:
                                continue

                            for day, slot in slots[:]:  # Copie pour itération sûre
                                if slot.assignee:  # Déjà attribué
                                    continue
                                    
                                # Vérifier les contraintes
                                if self.constraints.can_assign_to_assignee(
                                    cat, current_date, slot, self.planning
                                ):
                                    # Attribution
                                    slot.assignee = cat.name
                                    quota_tracker.update_assignment(
                                        cat, post_type, current_date
                                    )
                                    logger.info(f"Attribution {post_type} à {cat.name} "
                                            f"le {current_date}")
                                    break

            # Log des quotas finaux
            self._log_cat_quotas_status(quota_tracker)

        except Exception as e:
            logger.error(f"Erreur distribution CAT: {e}")
            
    def _get_remaining_quota(self, remaining_quotas: Dict, post_type: str) -> int:
        """Extrait correctement la valeur du quota restant."""
        try:
            posts_quotas = remaining_quotas.get('posts', {})
            quota = posts_quotas.get(post_type, 0)
            
            # Si c'est un PostConfig, extraire la valeur total
            if hasattr(quota, 'total'):
                return quota.total
            return quota

        except Exception as e:
            logger.error(f"Erreur extraction quota: {e}")
            return 0
    
    def _log_cat_quotas_status(self, quota_tracker: QuotaTracker) -> None:
            """Log détaillé de l'état final des quotas CAT."""
            logger.info("\nBilan des quotas CAT:")
            
            for cat in self.cats:
                logger.info(f"\n{cat.name}:")
                remaining = quota_tracker.get_remaining_quotas(cat)
                if not remaining:
                    continue
                    
                posts_quotas = remaining.get('posts', {})
                for post_type in sorted(ALL_POST_TYPES):
                    quota = self._get_remaining_quota(remaining, post_type)
                    if quota > 0:
                        logger.info(f"{post_type}: {quota} restants")
            
    def _get_available_posts_for_date(self, date: date, 
                                    remaining_posts: Dict) -> Dict[str, List[Tuple[date, TimeSlot]]]:
        """
        Récupère les postes disponibles pour une date donnée.
        
        Args:
            date: Date à vérifier
            remaining_posts: Dictionnaire des postes restants
            
        Returns:
            Dict des postes disponibles avec leurs slots pour cette date
        """
        available = {}
        
        # Pour chaque type de poste
        for post_type, post_slots in remaining_posts.items():
            # Filtrer les slots pour cette date
            date_slots = [(d, s) for d, s in post_slots if d == date and not s.assignee]
            if date_slots:
                available[post_type] = date_slots
                
        return available

    def _calculate_remaining_need(self, cat_quotas: Dict) -> int:
        """
        Calcule le nombre total de postes restant à attribuer.
        """
        total_remaining = 0
        for cat_quotas in cat_quotas.values():
            for quota in cat_quotas.values():
                if quota > 0:  # Ne compter que les quotas positifs
                    total_remaining += quota
        return total_remaining

    def _get_cat_quotas(self) -> Dict[str, Dict[str, int]]:
        """
        Récupère les quotas restants pour chaque CAT en tenant compte
        de toutes les attributions précédentes.
        """
        total_quotas = self.planning.pre_analysis_results["cat_posts"]["weekday"]

        # Compter tous les postes déjà attribués (hors weekend/férié/vendredi)
        current_assignments = defaultdict(lambda: defaultdict(int))
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge or day.date.weekday() == 4):
                for slot in day.slots:
                    if slot.assignee:
                        for cat in self.cats:
                            if slot.assignee == cat.name:
                                current_assignments[cat.name][slot.abbreviation] += 1

        # Calculer les quotas restants
        remaining_quotas = defaultdict(lambda: defaultdict(int))
        for cat in self.cats:
            for post_type, total in total_quotas.items():
                if post_type == "NLv":  # Ignorer les NLv
                    continue

                # Vérifier si le quota est déjà dépassé
                assigned = current_assignments[cat.name].get(post_type, 0)
                if assigned > total:
                    logger.error(f"ALERTE: {cat.name} a dépassé son quota de {post_type} "
                            f"({assigned}/{total})")
                    continue

                # Calculer le quota restant
                remaining = total - assigned
                if remaining > 0:
                    remaining_quotas[cat.name][post_type] = remaining

        # Log des quotas et postes attribués
        logger.info("\nQuotas et attributions CAT:")
        for cat_name in remaining_quotas:
            logger.info(f"\n{cat_name}:")
            for post_type in sorted(total_quotas.keys()):
                if post_type != "NLv":
                    total = total_quotas[post_type]
                    assigned = current_assignments[cat_name].get(post_type, 0)
                    remaining = remaining_quotas[cat_name].get(post_type, 0)
                    logger.info(f"{post_type}: {assigned} attribués / {total} total "
                            f"({remaining} restants)")

        return remaining_quotas
    def _calculate_remaining_cat_quotas(self, cat_quotas: Dict) -> Dict:
        """Calcule les quotas restants pour chaque CAT."""
        remaining_quotas = defaultdict(lambda: defaultdict(int))

        # D'abord, compter ce qui est déjà attribué à chaque CAT
        current_assignments = defaultdict(lambda: defaultdict(int))
        for day in self.planning.days:
            if not (day.is_weekend or day.is_holiday_or_bridge or day.date.weekday() == 4):
                for slot in day.slots:
                    if slot.assignee:
                        for cat in self.cats:
                            if slot.assignee == cat.name:
                                current_assignments[cat.name][slot.abbreviation] += 1

        # Pour chaque type de poste
        for post_type, total_quota in cat_quotas.items():
            if post_type == "NLv":
                continue

            # Quota théorique par CAT
            quota_per_cat = total_quota  # Pas de division, on prend le quota total

            # Pour chaque CAT
            for cat in self.cats:
                current = current_assignments[cat.name].get(post_type, 0)
                remaining = max(0, quota_per_cat - current)
                
                if remaining > 0:
                    remaining_quotas[cat.name][post_type] = remaining
                    logger.info(f"{cat.name}: {remaining} {post_type} restants "
                            f"(quota: {quota_per_cat}, actuel: {current})")

        return remaining_quotas
    def _can_assign_to_cat(self, cat: CAT, post_type: str, date: date,
                        slot: TimeSlot, remaining_quotas: Dict,
                        respect_secondary: bool = True) -> bool:
        """
        Vérifie si l'attribution est possible en respectant strictement les quotas.
        """
        # 1. Vérifier le quota restant
        if remaining_quotas[cat.name].get(post_type, 0) <= 0:
            return False

        # 2. Vérifier les contraintes de base
        if not self.constraints.can_assign_to_assignee(
            cat, date, slot, self.planning, respect_secondary=respect_secondary
        ):
            return False

        return True

    def _distribute_cat_posts_for_date(self, date: date, remaining_posts: Dict,
                                    cat_quotas: Dict, is_critical: bool,
                                    respect_secondary: bool) -> None:
        """
        Distribution des postes pour une date donnée.
        Respecte strictement les quotas et gère l'assouplissement des desiderata.
        """
        try:
            # 1. Collecter les slots disponibles pour cette date
            slots_by_type = defaultdict(list)
            for post_type, slots in remaining_posts.items():
                slots_by_type[post_type] = [
                    (d, s) for d, s in slots 
                    if d == date and not s.assignee
                ]

            if not slots_by_type:
                return

            # 2. Trier les types de poste par priorité
            priority_posts = self._prioritize_posts(slots_by_type, cat_quotas)

            # 3. Pour chaque type de poste prioritaire
            for post_type in priority_posts:
                if not slots_by_type[post_type]:
                    continue

                # Trier les CAT par quota restant décroissant
                eligible_cats = [
                    (cat, cat_quotas[cat.name][post_type])
                    for cat in self.cats
                    if cat_quotas[cat.name].get(post_type, 0) > 0
                ]
                eligible_cats.sort(key=lambda x: x[1], reverse=True)

                # Pour chaque CAT éligible
                for cat, remaining_quota in eligible_cats:
                    if remaining_quota <= 0:
                        continue

                    # Vérifier les desiderata
                    if not self._is_cat_available(cat, date, respect_secondary):
                        continue

                    # Pour chaque slot disponible
                    for d, slot in list(slots_by_type[post_type]):
                        # Double vérification des contraintes
                        if self.constraints.can_assign_to_assignee(
                            cat, date, slot, self.planning,
                            respect_secondary=respect_secondary
                        ):
                            # Attribution du slot
                            slot.assignee = cat.name
                            cat_quotas[cat.name][post_type] -= 1
                            
                            # Retirer le slot des disponibles
                            slots_by_type[post_type].remove((d, slot))
                            remaining_posts[post_type].remove((d, slot))

                            mode = "critique" if is_critical else "standard"
                            constraints = "" if respect_secondary else " (assoupli)"
                            logger.info(f"{cat.name}: {post_type} attribué le {date}"
                                    f" [{mode}{constraints}] - "
                                    f"restant: {cat_quotas[cat.name][post_type]}")
                            break

        except Exception as e:
            logger.error(f"Erreur lors de la distribution pour {date}: {e}")

    def _is_cat_available(self, cat: CAT, date: date, respect_secondary: bool) -> bool:
        """
        Vérifie si un CAT est disponible pour une date, avec gestion des desiderata.
        """
        for desiderata in cat.desiderata:
            if desiderata.start_date <= date <= desiderata.end_date:
                # Toujours respecter les desiderata primaires
                if not hasattr(desiderata, 'priority') or desiderata.priority == "primary":
                    return False
                # Desiderata secondaires selon le mode
                if respect_secondary and desiderata.priority == "secondary":
                    return False
        return True

    def _prioritize_posts(self, slots_by_type: Dict, cat_quotas: Dict) -> List[str]:
        """
        Priorise les types de poste basé sur le besoin total et la disponibilité.
        """
        post_scores = {}
        for post_type, slots in slots_by_type.items():
            if not slots:
                continue

            # Calculer le besoin total pour ce type
            total_need = sum(
                quotas.get(post_type, 0)
                for quotas in cat_quotas.values()
            )

            if total_need <= 0:
                continue

            # Score basé sur le ratio besoin/disponibilité
            availability = len(slots)
            urgency_score = total_need / availability
            
            # Ajouter un facteur aléatoire (±10%)
            random_factor = 1 + (random.random() * 0.2 - 0.1)
            post_scores[post_type] = urgency_score * random_factor

        # Retourner les types triés par score décroissant
        return sorted(post_scores.keys(), key=lambda p: post_scores[p], reverse=True)

    
    def _log_final_distribution_results(self, initial_quotas: Dict, final_quotas: Dict) -> None:
        """
        Log détaillé des résultats de la distribution.
        """
        logger.info("\nRÉSULTATS FINAUX DE LA DISTRIBUTION CAT:")
        logger.info("=" * 60)
        
        for cat_name in initial_quotas:
            logger.info(f"\n{cat_name}:")
            
            # Comparer chaque type de poste
            for post_type in initial_quotas[cat_name]:
                initial = initial_quotas[cat_name][post_type]
                final = final_quotas[cat_name].get(post_type, 0)
                attributed = initial - final
                
                if initial > 0:  # Ne log que les postes pertinents
                    status = "OK" if final == 0 else f"INCOMPLET ({final} restants)"
                    logger.info(f"{post_type}: {attributed}/{initial} attribués - {status}")
                    
    def _verify_cat_quotas(self, cat_quotas: Dict) -> None:
        """Vérifie les quotas restants et l'impossibilité de distribution."""
        logger.info("\nVérification finale des quotas CAT:")
        
        for cat_name, quotas in cat_quotas.items():
            logger.info(f"\n{cat_name}:")
            for post_type, remaining in quotas.items():
                if remaining > 0:
                    logger.warning(f"{post_type}: {remaining} non attribués")
                    
                    
                    
    
    
    def _initialize_doctor_intervals(self, intervals: Dict) -> Dict:
        """
        Initialise les intervalles des médecins en comptant TOUS les postes déjà attribués,
        y compris ceux des combinaisons et des phases précédentes.
        """
        try:
            for doctor_name, doctor_intervals in intervals.items():
                # Réinitialiser les compteurs
                doctor_intervals['current_counts'] = {
                    'posts': defaultdict(int),
                    'groups': defaultdict(int)
                }
                
                # Compter TOUS les postes de semaine attribués
                for day in self.planning.days:
                    # Ignorer les weekends et jours fériés
                    if day.is_weekend or day.is_holiday_or_bridge:
                        continue
                        
                    for slot in day.slots:
                        if slot.assignee == doctor_name:
                            post_type = slot.abbreviation
                            doctor_intervals['current_counts']['posts'][post_type] += 1
                            
                            # Mettre à jour aussi les compteurs de groupe
                            group = self._get_post_group(post_type, day.date)
                            if group:
                                doctor_intervals['current_counts']['groups'][group] += 1

                # Log des compteurs initiaux pour vérification
                logger.info(f"\nCompteurs initiaux pour {doctor_name}:")
                logger.info("Postes:")
                for post_type, count in doctor_intervals['current_counts']['posts'].items():
                    if count > 0:
                        logger.info(f"  {post_type}: {count}")
                logger.info("Groupes:")
                for group, count in doctor_intervals['current_counts']['groups'].items():
                    if count > 0:
                        logger.info(f"  {group}: {count}")

            return intervals

        except Exception as e:
            logger.error(f"Erreur initialisation intervalles: {e}")
            return intervals
    
    
    def _distribute_remaining_to_doctors(self, remaining_posts: Dict, 
                                        dates_by_criticality: Dict,
                                        intervals: Dict) -> None:
        """
        Distribution des postes restants de semaine aux médecins.
        Processus en plusieurs passes pour garantir les minimums et l'équité.
        """
        try:
            logger.info("\nDISTRIBUTION DES POSTES RESTANTS AUX MÉDECINS")
            logger.info("=" * 80)
            
            # Initialiser les intervalles avec les postes existants
            intervals = self._initialize_doctor_intervals(intervals)
            # Initialisation du tracker de quotas pour les médecins
            quota_tracker = QuotaTracker(self.planning, self.doctors, "weekday")

            # Phase 1: Distribution pour atteindre les minimums
            logger.info("\nPhase 1: Distribution des minimums")
            remaining_posts = self._distribute_doctor_minimums(
                remaining_posts,
                dates_by_criticality,
                quota_tracker,
                intervals
            )

            # Phase 2: Distribution équilibrée des postes restants
            if any(posts for posts in remaining_posts.values()):
                logger.info("\nPhase 2: Distribution équilibrée")
                remaining_posts = self._distribute_remaining_balanced(
                    remaining_posts,
                    dates_by_criticality,
                    quota_tracker,
                    intervals
                )

            # Phase 3: Distribution avec assouplissement des desiderata secondaires
            if any(posts for posts in remaining_posts.values()):
                logger.info("\nPhase 3: Distribution avec assouplissement")
                self._distribute_with_relaxed_constraints(
                    remaining_posts,
                    dates_by_criticality,
                    quota_tracker,
                    intervals
                )

        except Exception as e:
            logger.error(f"Erreur distribution médecins: {e}", exc_info=True)

    def _distribute_doctor_minimums(self, remaining_posts: Dict,
                                    dates_by_criticality: Dict,
                                    quota_tracker: QuotaTracker,
                                    intervals: Dict) -> Dict:
        """
        Distribution des postes restants pour atteindre les minimums requis pour chaque médecin.
        Cette méthode prend en compte tous les postes déjà attribués (combinaisons incluses)
        et respecte strictement les maximums de groupe.

        Args:
            remaining_posts: Dictionnaire des postes restants à attribuer
            dates_by_criticality: Dates classées par niveau de criticité
            quota_tracker: Gestionnaire des quotas
            intervals: Intervalles min/max pour chaque médecin
            
        Returns:
            Dict: Postes restants après distribution
        """
        
        # Au début de _distribute_doctor_minimums :
        total_slots = sum(len(slots) for slots in remaining_posts.values())
        total_available = 0
        friday_slots = 0

        for day in self.planning.days:
            if day.is_weekend or day.is_holiday_or_bridge:
                continue
                
            for slot in day.slots:
                if not slot.assignee:
                    if day.date.weekday() == 4:
                        if slot.abbreviation != "NL":  # Ne pas compter NLv
                            friday_slots += 1
                    else:
                        total_available += 1

        logger.info(f"\nVérification des postes disponibles:")
        logger.info(f"Total selon remaining_posts: {total_slots}")
        logger.info(f"Total réel: {total_available + friday_slots}")
        logger.info(f"  - Jours de semaine: {total_available}")
        logger.info(f"  - Vendredis: {friday_slots}")

        if total_slots != (total_available + friday_slots):
            logger.warning(f"Incohérence dans le nombre de postes: "
                        f"{total_slots} ≠ {total_available + friday_slots}")
        try:
            # 1. Initialisation et réinitialisation des compteurs avec tous les postes existants
            intervals = self._initialize_doctor_intervals(intervals)
            remaining = remaining_posts.copy()
            max_iterations = 3  # Protection contre les boucles infinies
            
            while max_iterations > 0:
                max_iterations -= 1
                progress_made = False

                # 2. Identification des médecins sous leur minimum
                doctors_under_min = []
                for doctor in self.doctors:
                    doctor_intervals = intervals[doctor.name]
                    missing_posts = {}
                    total_gap = 0
                    
                    # 2.1 Calcul des postes manquants par type
                    for post_type, interval in doctor_intervals['posts'].items():
                        current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
                        min_required = interval.get('min', 0)
                        if current < min_required:
                            gap = min_required - current
                            missing_posts[post_type] = gap
                            total_gap += gap
                            
                    # 2.2 Ajouter le médecin s'il lui manque des postes
                    if missing_posts:
                        doctors_under_min.append({
                            'doctor': doctor,
                            'intervals': doctor_intervals,
                            'missing': missing_posts,
                            'gap': total_gap
                        })
                        # Log détaillé des manques
                        logger.info(f"\n{doctor.name} sous minimum:")
                        for post_type, gap in missing_posts.items():
                            logger.info(f"  {post_type}: manque {gap} postes")

                # 3. Arrêt si tous les minimums sont atteints
                if not doctors_under_min:
                    logger.info("Tous les médecins ont atteint leurs minimums")
                    break

                # 4. Tri des médecins par écart au minimum décroissant
                doctors_under_min.sort(key=lambda x: x['gap'], reverse=True)

                # 5. Distribution pour chaque médecin sous minimum
                for doc_info in doctors_under_min:
                    doctor = doc_info['doctor']
                    doctor_intervals = doc_info['intervals']
                    missing_posts = doc_info['missing']

                    # 5.1 Distribution prioritaire sur les périodes critiques
                    for criticality in ['critical', 'normal']:
                        if not missing_posts:  # Arrêt si minimums atteints
                            break
                            
                        dates = dates_by_criticality[criticality]
                        random.shuffle(dates)  # Ordre aléatoire

                        for date in dates:
                            if not missing_posts:
                                break

                            # 5.2 Récupération des postes disponibles pour cette date
                            available = self._get_available_posts_for_date(date, remaining)
                            if not available:
                                continue

                            # 5.3 Filtrage des postes selon les besoins et maximums
                            filtered_posts = {}
                            for post_type, slots in available.items():
                                # Ne garder que les postes manquants respectant les maximums
                                if (post_type in missing_posts and
                                    self._can_assign_post_to_doctor(doctor, post_type, doctor_intervals)):
                                    filtered_posts[post_type] = slots

                            if not filtered_posts:
                                continue

                            # 5.4 Recherche du meilleur poste à attribuer
                            best_post = self._find_best_post_for_minimum(
                                doctor, filtered_posts, doctor_intervals
                            )

                            if best_post:
                                post_type, slot = best_post
                                # 5.5 Attribution du poste
                                if self._assign_post_to_doctor(
                                    doctor, date, post_type, slot,
                                    doctor_intervals, quota_tracker
                                ):
                                    # Mise à jour des compteurs
                                    missing_posts[post_type] -= 1
                                    if missing_posts[post_type] <= 0:
                                        del missing_posts[post_type]
                                        
                                    # Retrait du slot des disponibles
                                    slots = remaining[post_type]
                                    slots.remove((date, slot))
                                    if not slots:
                                        del remaining[post_type]
                                        
                                    progress_made = True
                                    
                                    logger.info(f"{doctor.name}: {post_type} attribué le {date} "
                                            f"(période {criticality})")

                # 6. Arrêt si aucun progrès sur cette itération
                if not progress_made:
                    logger.warning("Aucun progrès possible dans cette itération")
                    break

            # 7. Log final
            remaining_count = sum(len(slots) for slots in remaining.values())
            logger.info(f"\nFin distribution minimums - {remaining_count} postes restants")
            
            return remaining

        except Exception as e:
            logger.error(f"Erreur distribution minimums: {e}", exc_info=True)
            return remaining_posts
        
    def _can_assign_post_to_doctor(self, doctor: Doctor, post_type: str,
                            doctor_intervals: Dict) -> bool:
        """
        Vérifie si un poste peut être attribué en respectant les maximums.
        """
        # Vérifier le maximum du type de poste
        current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
        max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
        if current >= max_allowed:
            logger.debug(f"{doctor.name}: Maximum atteint pour {post_type} ({current}/{max_allowed})")
            return False
            
        # Vérifier le maximum du groupe
        group = self._get_post_group(post_type, datetime.now().date())
        if group:
            group_current = doctor_intervals['current_counts']['groups'].get(group, 0)
            group_max = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
            if group_current >= group_max:
                logger.debug(f"{doctor.name}: Maximum atteint pour groupe {group} ({group_current}/{group_max})")
                return False
                
        return True

    def _try_minimum_distribution(self, date: date, remaining_posts: Dict,
                                doctors_under_min: List[Tuple],
                                quota_tracker: QuotaTracker,
                                intervals: Dict) -> bool:
        """Tente d'attribuer des postes aux médecins sous leur minimum."""
        try:
            # Postes disponibles pour cette date
            available = self._get_available_posts_for_date(date, remaining_posts)
            if not available:
                return False

            # Pour chaque médecin sous minimum
            for doctor, doctor_intervals, gap in doctors_under_min:
                if not self._is_doctor_available_for_weekday(doctor, date):
                    continue

                # Trouver le meilleur poste pour ce médecin
                best_post = self._find_best_post_for_minimum(
                    doctor, available, doctor_intervals
                )

                if best_post:
                    post_type, slot = best_post
                    if self._assign_post_to_doctor(
                        doctor, date, post_type, slot,
                        intervals[doctor.name], quota_tracker
                    ):
                        # Mettre à jour les listes disponibles
                        slots = remaining_posts[post_type]
                        slots.remove((date, slot))
                        if not slots:
                            del remaining_posts[post_type]
                        return True

            return False

        except Exception as e:
            logger.error(f"Erreur distribution minimum: {e}")
            return False

    def _find_best_post_for_minimum(self, doctor: Doctor, available_posts: Dict, doctor_intervals: Dict) -> Optional[Tuple]:
        best_score = -float('inf')
        best_post = None

        # Vérification préalable des maximums de groupe
        group_counts = defaultdict(int)
        for post_type, count in doctor_intervals['current_counts']['posts'].items():
            group = self._get_post_group(post_type, datetime.now().date())
            if group:
                group_counts[group] += count

        for post_type, slots in available_posts.items():
            # Vérifier d'abord le groupe
            group = self._get_post_group(post_type, datetime.now().date())
            if group:
                current_group = group_counts[group]
                max_allowed = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                if current_group >= max_allowed:
                    continue

        for post_type, slots in available_posts.items():
            # Vérifier l'écart au minimum
            current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
            min_required = doctor_intervals['posts'].get(post_type, {}).get('min', 0)

            if current >= min_required:
                continue

            score = (min_required - current) / min_required if min_required > 0 else 0
            
            # Bonus pour les pleins temps
            if doctor.half_parts == 2:
                score *= 1.2

            # Facteur aléatoire
            score *= 1 + (random.random() * 0.2 - 0.1)

            if score > best_score:
                for date, slot in slots:
                    if self.constraints.can_assign_to_assignee(
                        doctor, date, slot, self.planning
                    ):
                        best_score = score
                        best_post = (post_type, slot)
                        break

        return best_post

    def _distribute_remaining_balanced(self, remaining_posts: Dict,
                                    dates_by_criticality: Dict,
                                    quota_tracker: QuotaTracker,
                                    intervals: Dict) -> Dict:
        """Distribution équilibrée avec suivi strict des progrès."""
        try:
            remaining = remaining_posts.copy()
            total_before = self._count_unassigned_posts(remaining)
            logger.info(f"Début distribution équilibrée: {total_before} postes à attribuer")
            
            max_attempts = 3
            current_attempt = 0

            while current_attempt < max_attempts:
                doctor_scores = self._calculate_equity_scores()
                posts_attributed = 0

                for criticality in ['critical', 'normal']:
                    dates = dates_by_criticality[criticality]
                    random.shuffle(dates)

                    for date in dates:
                        if self._try_balanced_distribution(
                            date, remaining, doctor_scores,
                            quota_tracker, intervals
                        ):
                            posts_attributed += 1

                total_after = self._count_unassigned_posts(remaining)
                if posts_attributed == 0 or total_after >= total_before:
                    logger.info(f"Arrêt distribution équilibrée: plus de progrès possible")
                    break

                logger.info(f"Passe {current_attempt + 1}: {posts_attributed} postes attribués")
                total_before = total_after
                current_attempt += 1

            return remaining

        except Exception as e:
            logger.error(f"Erreur distribution équilibrée: {e}")
            return remaining_posts

    def _calculate_equity_scores(self) -> Dict[str, float]:
        """
        Calcule un score d'équité pour chaque médecin basé sur:
        - Le ratio actuel par rapport aux maximums pour chaque type de poste
        - Le ratio actuel par rapport aux maximums pour chaque groupe
        - Le nombre de demi-parts du médecin
        
        Returns:
            Dict[str, float]: Dictionnaire des scores par médecin
        """
        scores = {}
        
        for doctor in self.doctors:
            # 1. Analyse des ratios de postes
            posts_by_type = defaultdict(int)
            for day in self.planning.days:
                if day.is_weekend or day.is_holiday_or_bridge:
                    continue
                for slot in day.slots:
                    if slot.assignee == doctor.name:
                        posts_by_type[slot.abbreviation] += 1
            
            # 2. Calcul des ratios par rapport aux maximums
            type_ratios = []
            doctor_state = self._get_doctor_weekday_intervals()[doctor.name]
            
            for post_type, count in posts_by_type.items():
                max_allowed = doctor_state['posts'].get(post_type, {}).get('max', float('inf'))
                if max_allowed < float('inf'):
                    ratio = count / max_allowed
                    type_ratios.append(ratio)
            
            # 3. Calcul des ratios de groupe
            group_ratios = []
            for group, interval in doctor_state['groups'].items():
                max_allowed = interval.get('max', float('inf'))
                current = doctor_state['current_counts']['groups'].get(group, 0)
                if max_allowed < float('inf'):
                    ratio = current / max_allowed
                    group_ratios.append(ratio)
            
            # 4. Score final : plus le ratio est faible, meilleur est le score
            score = 1.0
            if type_ratios:
                type_score = 1.0 - (sum(type_ratios) / len(type_ratios))
                score *= type_score
                
            if group_ratios:
                group_score = 1.0 - (sum(group_ratios) / len(group_ratios))
                score *= group_score
                
            # 5. Bonus pour les pleins temps et facteur aléatoire
            score *= 1.2 if doctor.half_parts == 2 else 1.0
            score *= 1 + (random.random() * 0.2 - 0.1)  # ±10% aléatoire
            
            scores[doctor.name] = max(0.1, score)  # Score minimum de 0.1
            
        return scores

    def _distribute_with_relaxed_constraints(self, remaining_posts: Dict,
                                        dates_by_criticality: Dict,
                                        quota_tracker: QuotaTracker,
                                        intervals: Dict) -> None:
        try:
            # Comptage précis des postes restants avant distribution
            initial_unassigned = self._count_unassigned_posts(remaining_posts)
            logger.info(f"Postes non attribués avant assouplissement: {initial_unassigned}")

            # 1. Identifier les médecins sous minimum (posts ET groupes)
            doctors_under_min = []
            for doctor in self.doctors:
                doctor_intervals = intervals[doctor.name]
                is_under_min = False
                
                # Vérifier minimums de posts
                for post_type, interval in doctor_intervals['posts'].items():
                    current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
                    if current < interval.get('min', 0):
                        is_under_min = True
                        break
                        
                # Vérifier minimums de groupes
                for group, interval in doctor_intervals['groups'].items():
                    current = doctor_intervals['current_counts']['groups'].get(group, 0)
                    if current < interval.get('min', 0):
                        is_under_min = True
                        break
                        
                if is_under_min:
                    doctors_under_min.append(doctor)

            # Attribution prioritaire aux médecins sous minimum
            for doctor in doctors_under_min:
                self._try_relaxed_distribution(
                    doctor, remaining_posts, dates_by_criticality,
                    quota_tracker, intervals[doctor.name], True
                )

            # Distribution du reste avec assouplissement
            other_doctors = [d for d in self.doctors if d not in doctors_under_min]
            for doctor in other_doctors:
                if self._verify_doctor_has_space(doctor, intervals[doctor.name]):
                    self._try_relaxed_distribution(
                        doctor, remaining_posts, dates_by_criticality,
                        quota_tracker, intervals[doctor.name], False
                    )

            # Comptage final
            final_unassigned = self._count_unassigned_posts(remaining_posts)
            logger.info(f"Postes restants après assouplissement: {final_unassigned}")

        except Exception as e:
            logger.error(f"Erreur distribution assouplie: {e}")
    
    def _find_best_post_for_minimum(self, doctor: Doctor,
                                available_posts: Dict,
                                doctor_intervals: Dict) -> Optional[Tuple]:
        best_score = -float('inf')
        best_post = None

        for post_type, slots in available_posts.items():
            current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
            min_required = doctor_intervals['posts'].get(post_type, {}).get('min', 0)
            max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))

            # Vérifier le groupe
            group = self._get_post_group(post_type, datetime.now().date())
            if group:
                group_current = doctor_intervals['current_counts']['groups'].get(group, 0)
                group_max = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                group_min = doctor_intervals['groups'].get(group, {}).get('min', 0)
                
                # Ignorer si max groupe déjà atteint
                if group_current >= group_max:
                    continue
                
                # Bonus si groupe sous minimum
                if group_current < group_min:
                    score = (min_required - current) / min_required if min_required > 0 else 0
                    score *= 1.5 # Bonus pour groupe sous minimum

            if current >= max_allowed:
                continue

            score = (min_required - current) / min_required if min_required > 0 else 0
            
            if doctor.half_parts == 2:
                score *= 1.2

            if score > best_score:
                for date, slot in slots:
                    if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                        best_score = score
                        best_post = (post_type, slot)
                        break

        return best_post
            
            
     # Nouvelle méthode de distribution intermédiaire
    def _distribute_with_type_flexibility(self, remaining_posts: Dict,
                                        dates_by_criticality: Dict,
                                        quota_tracker: QuotaTracker,
                                        intervals: Dict) -> Dict:
        """
        Distribution intermédiaire des postes restants avec flexibilité sur les maximums de type
        tout en respectant strictement les maximums de groupe.
        Vise à équilibrer la charge totale entre les médecins.
        """
        try:
            logger.info("\nDISTRIBUTION AVEC FLEXIBILITÉ SUR LES TYPES")
            logger.info("=" * 60)
            remaining = remaining_posts.copy()

            # 1. Analyse de la situation actuelle
            total_slots = sum(len(slots) for slots in remaining.values())
            logger.info(f"Postes restants à distribuer: {total_slots}")

            # Calcul des charges actuelles
            doctor_stats = self._calculate_current_doctor_stats(intervals)
            avg_load = sum(stats['total_posts'] for stats in doctor_stats.values()) / len(self.doctors)
            logger.info(f"Charge moyenne actuelle: {avg_load:.1f} postes")

            # 2. Préparation de la distribution
            flexibility_margin = 0.2  # Permet 20% de dépassement des maximums de type
            priority_groups = self._group_doctors_by_priority(doctor_stats, avg_load)

            # 3. Distribution par priorité
            progress_made = True
            max_iterations = 3
            while progress_made and max_iterations > 0:
                progress_made = False
                max_iterations -= 1

                # Traiter d'abord les périodes critiques
                for criticality in ['critical', 'normal']:
                    if not remaining:
                        break

                    dates = dates_by_criticality[criticality]
                    random.shuffle(dates)

                    # Pour chaque groupe de priorité
                    for priority_level, doctors in priority_groups.items():
                        if not remaining:
                            break

                        for doctor in doctors:
                            doctor_intervals = intervals[doctor.name]
                            stats = doctor_stats[doctor.name]

                            for date in dates:
                                if not remaining:
                                    break

                                # Récupérer les postes disponibles
                                available = self._get_available_posts_for_date(date, remaining)
                                if not available:
                                    continue

                                # Évaluer chaque poste disponible
                                best_assignment = self._find_best_flexible_assignment(
                                    doctor, 
                                    date, 
                                    available, 
                                    doctor_intervals,
                                    stats,
                                    flexibility_margin
                                )

                                if best_assignment:
                                    post_type, slot = best_assignment
                                    if self._assign_with_flexibility(
                                        doctor,
                                        date,
                                        post_type,
                                        slot,
                                        doctor_intervals,
                                        quota_tracker,
                                        flexibility_margin
                                    ):
                                        # Mise à jour des statistiques
                                        stats['total_posts'] += 1
                                        stats['posts_by_type'][post_type] = (
                                            stats['posts_by_type'].get(post_type, 0) + 1
                                        )

                                        # Retirer le slot des disponibles
                                        slots = remaining[post_type]
                                        slots.remove((date, slot))
                                        if not slots:
                                            del remaining[post_type]

                                        progress_made = True
                                        logger.info(
                                            f"{doctor.name}: {post_type} attribué le {date} "
                                            f"(total: {stats['total_posts']}, "
                                            f"niveau: {priority_level})"
                                        )

                # Recalculer les priorités si on continue
                if progress_made and max_iterations > 0:
                    doctor_stats = self._calculate_current_doctor_stats(intervals)
                    avg_load = sum(
                        stats['total_posts'] for stats in doctor_stats.values()
                    ) / len(self.doctors)
                    priority_groups = self._group_doctors_by_priority(doctor_stats, avg_load)

            return remaining

        except Exception as e:
            logger.error(f"Erreur distribution flexible: {e}", exc_info=True)
            return remaining_posts

    def _calculate_current_doctor_stats(self, intervals: Dict) -> Dict[str, Dict]:
        """
        Calcule les statistiques actuelles pour chaque médecin.
        """
        stats = {}
        
        for doctor in self.doctors:
            doctor_intervals = intervals[doctor.name]
            current_counts = doctor_intervals['current_counts']
            
            # Comptage des postes par type et par groupe
            total_posts = sum(current_counts['posts'].values())
            posts_by_type = current_counts['posts'].copy()
            groups_by_type = {}
            
            for post_type, count in posts_by_type.items():
                group = self._get_post_group(post_type, datetime.now().date())
                if group:
                    groups_by_type[group] = groups_by_type.get(group, 0) + count
            
            # Calcul des ratios par rapport aux maximums
            type_ratios = {}
            for post_type, count in posts_by_type.items():
                max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
                if max_allowed < float('inf'):
                    type_ratios[post_type] = count / max_allowed
                    
            group_ratios = {}
            for group, count in groups_by_type.items():
                max_allowed = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                if max_allowed < float('inf'):
                    group_ratios[group] = count / max_allowed
            
            stats[doctor.name] = {
                'total_posts': total_posts,
                'posts_by_type': posts_by_type,
                'groups_by_type': groups_by_type,
                'type_ratios': type_ratios,
                'group_ratios': group_ratios,
                'half_parts': doctor.half_parts
            }
            
        return stats

    def _group_doctors_by_priority(self, doctor_stats: Dict[str, Dict],
                                avg_load: float) -> Dict[str, List[Doctor]]:
        """
        Groupe les médecins par priorité selon leur charge actuelle.
        """
        priority_groups = {
            'under_min': [],    # Sous leur minimum
            'under_avg': [],    # Sous la moyenne
            'balanced': [],     # Proche de la moyenne
            'over_avg': []      # Au-dessus de la moyenne
        }
        
        for doctor in self.doctors:
            stats = doctor_stats[doctor.name]
            total_posts = stats['total_posts']
            
            # Ajuster l'objectif selon les demi-parts
            target = avg_load * (1.2 if doctor.half_parts == 2 else 0.8)
            
            # Calculer l'écart à la cible
            gap = target - total_posts
            
            if gap > target * 0.2:  # Plus de 20% sous la cible
                priority_groups['under_min'].append(doctor)
            elif gap > 0:  # Sous la cible
                priority_groups['under_avg'].append(doctor)
            elif abs(gap) <= target * 0.1:  # ±10% de la cible
                priority_groups['balanced'].append(doctor)
            else:  # Au-dessus de la cible
                priority_groups['over_avg'].append(doctor)
        
        return priority_groups

    def _find_best_flexible_assignment(self, doctor: Doctor, date: date,
                                    available_posts: Dict,
                                    doctor_intervals: Dict,
                                    doctor_stats: Dict,
                                    flexibility_margin: float) -> Optional[Tuple[str, TimeSlot]]:
        """
        Trouve la meilleure attribution possible avec flexibilité sur les maximums de type.
        
        Args:
            doctor: Le médecin à qui attribuer un poste
            date: La date d'attribution
            available_posts: Dictionnaire des postes disponibles
            doctor_intervals: Intervalles du médecin
            doctor_stats: Statistiques actuelles du médecin
            flexibility_margin: Marge de flexibilité sur les maximums
            
        Returns:
            Optional[Tuple[str, TimeSlot]]: Le meilleur poste trouvé (type, slot) ou None
        """
        try:
            best_score = -float('inf')
            best_assignment = None
            
            for post_type, slots_list in available_posts.items():
                # 1. Vérifier d'abord les maximums de groupe (pas de flexibilité)
                group = self._get_post_group(post_type, date)
                if group:
                    group_current = doctor_intervals['current_counts']['groups'].get(group, 0)
                    group_max = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                    if group_current >= group_max:
                        continue
                        
                # 2. Vérifier le maximum de type avec flexibilité
                current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
                max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
                if max_allowed < float('inf'):
                    flexible_max = max_allowed * (1 + flexibility_margin)
                    if current >= flexible_max:
                        continue
                
                # 3. Calculer le score pour ce type de poste
                for slot_date, slot in slots_list:
                    # S'assurer que nous sommes sur la bonne date
                    if slot_date != date:
                        continue
                        
                    # Vérifier si le slot peut être attribué
                    if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                        score = self._calculate_flexible_assignment_score(
                            doctor,
                            post_type,
                            current,
                            max_allowed,
                            group_current if group else 0,
                            group_max if group else float('inf'),
                            doctor_stats
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_assignment = (post_type, slot)
            
            if best_assignment:
                logger.debug(f"Meilleure attribution trouvée pour {doctor.name}: "
                            f"{best_assignment[0]} (score: {best_score:.2f})")
            
            return best_assignment

        except Exception as e:
            logger.error(f"Erreur recherche meilleure attribution flexible: {e}")
            return None

    def _calculate_flexible_assignment_score(self, doctor: Doctor,
                                        post_type: str,
                                        current_count: int,
                                        max_allowed: float,
                                        group_current: int,
                                        group_max: float,
                                        doctor_stats: Dict) -> float:
        """
        Calcule un score pour une attribution potentielle en tenant compte
        de multiples facteurs.
        """
        score = 1.0
        
        # 1. Pénalité basée sur le ratio au maximum de type
        if max_allowed < float('inf'):
            type_ratio = current_count / max_allowed
            score *= (1 - type_ratio)
        
        # 2. Pénalité basée sur le ratio au maximum de groupe
        if group_max < float('inf'):
            group_ratio = group_current / group_max
            score *= (1 - group_ratio)
        
        # 3. Bonus pour équilibrage
        total_posts = doctor_stats['total_posts']
        posts_by_type = doctor_stats['posts_by_type']
        if total_posts > 0:
            # Favoriser les types moins utilisés
            type_frequency = posts_by_type.get(post_type, 0) / total_posts
            score *= (1 - type_frequency)
        
        # 4. Ajustement selon les demi-parts
        score *= 1.2 if doctor.half_parts == 2 else 0.8
        
        # 5. Facteur aléatoire pour éviter la monotonie
        score *= 1 + (random.random() * 0.2 - 0.1)
        
        return max(0.1, score)

    def _assign_with_flexibility(self, doctor: Doctor, date: date,
                            post_type: str, slot: TimeSlot,
                            doctor_intervals: Dict,
                            quota_tracker: QuotaTracker,
                            flexibility_margin: float) -> bool:
        """
        Tente une attribution avec flexibilité sur les maximums de type.
        """
        try:
            # 1. Vérifier les contraintes de base
            if not self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                return False
                
            # 2. Vérifier le maximum de groupe (strict)
            group = self._get_post_group(post_type, date)
            if group:
                group_current = doctor_intervals['current_counts']['groups'].get(group, 0)
                group_max = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                if group_current >= group_max:
                    return False
            
            # 3. Vérifier le maximum de type avec flexibilité
            current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
            max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
            if max_allowed < float('inf'):
                flexible_max = max_allowed * (1 + flexibility_margin)
                if current >= flexible_max:
                    return False
            
            # 4. Attribution et mise à jour des compteurs
            slot.assignee = doctor.name
            doctor_intervals['current_counts']['posts'][post_type] = current + 1
            if group:
                doctor_intervals['current_counts']['groups'][group] = group_current + 1
                
            # 5. Mise à jour du quota tracker
            quota_tracker.update_assignment(doctor, post_type, date)
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur attribution flexible: {e}")
            return False       
            

    def _assign_post_to_doctor(self, doctor: Doctor, date: date, 
                                post_type: str, slot: TimeSlot,
                                doctor_intervals: Dict, quota_tracker: QuotaTracker) -> bool:
        """
        Attribution d'un poste à un médecin avec mise à jour des compteurs.
        """
        try:
            # Vérifier les contraintes de base
            if not self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                return False

            # Vérifier les limites de groupe
            group = self._get_post_group(post_type, date)
            if group:
                current_group = doctor_intervals['current_counts']['groups'].get(group, 0)
                max_allowed = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                if current_group >= max_allowed:
                    return False

            # Attribution du poste
            slot.assignee = doctor.name

            # Mise à jour des compteurs
            doctor_intervals['current_counts']['posts'][post_type] = doctor_intervals['current_counts']['posts'].get(post_type, 0) + 1
            if group:
                doctor_intervals['current_counts']['groups'][group] += 1

            # Mise à jour du quota tracker
            quota_tracker.update_assignment(doctor, post_type, date)

            logger.info(f"{doctor.name}: {post_type} attribué le {date}")
            return True

        except Exception as e:
            logger.error(f"Erreur attribution {post_type} à {doctor.name}: {e}")
            return False

    def _try_balanced_distribution(self, date: date, remaining_posts: Dict,
                                doctor_scores: Dict[str, float],
                                quota_tracker: QuotaTracker,
                                intervals: Dict) -> bool:
        """Distribution équilibrée avec vérification stricte des maximums."""
        try:
            available = self._get_available_posts_for_date(date, remaining_posts)
            if not available:
                return False

            attributed = False
            sorted_doctors = sorted(
                [(doc, doctor_scores[doc.name]) for doc in self.doctors],
                key=lambda x: x[1],
                reverse=True
            )

            for doctor, score in sorted_doctors:
                if not self._is_doctor_available_for_weekday(doctor, date):
                    continue

                for post_type, slots in available.items():
                    # Vérifier le maximum avant toute tentative
                    if not self._verify_post_limits(doctor, post_type, intervals[doctor.name]):
                        continue

                    for slot_idx, (_, slot) in enumerate(slots):
                        if not slot.assignee and self._assign_post_to_doctor(
                            doctor, date, post_type, slot,
                            intervals[doctor.name], quota_tracker
                        ):
                            # Mettre à jour les listes disponibles
                            slots.pop(slot_idx)
                            if not slots:
                                del remaining_posts[post_type]
                            attributed = True
                            break

                    if attributed:
                        break

                if attributed:
                    break

            return attributed

        except Exception as e:
            logger.error(f"Erreur distribution équilibrée: {e}")
            return False

    def _find_balanced_post(self, doctor: Doctor, available_posts: Dict,
                        doctor_intervals: Dict, quota_tracker: QuotaTracker) -> Optional[Tuple]:
        """Trouve le meilleur poste pour une distribution équilibrée."""
        best_score = -float('inf')
        best_post = None

        for post_type, slots in available_posts.items():
            # Vérifier si on peut encore attribuer ce type de poste
            if not quota_tracker.can_assign_post(doctor, post_type):
                continue

            # Vérifier le groupe
            group = self._get_post_group(post_type, datetime.now().date())
            if group:
                current_group = doctor_intervals['current_counts']['groups'].get(group, 0)
                max_allowed = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                if current_group >= max_allowed:
                    continue

            # Calculer un score pour ce type de poste
            score = self._calculate_balanced_post_score(
                doctor, post_type, doctor_intervals
            )

            if score > best_score:
                for date, slot in slots:
                    if self.constraints.can_assign_to_assignee(doctor, date, slot, self.planning):
                        best_score = score
                        best_post = (post_type, slot)
                        break

        return best_post

    def _calculate_balanced_post_score(self, doctor: Doctor, post_type: str,
                                    doctor_intervals: Dict) -> float:
        """Calcule un score pour un poste dans le contexte d'une distribution équilibrée."""
        score = 1.0

        # 1. Prise en compte de l'historique des posts
        current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
        total_posts = sum(doctor_intervals['current_counts']['posts'].values())
        if total_posts > 0:
            usage_ratio = current / total_posts
            score *= (1 - usage_ratio)  # Favoriser les types peu utilisés

        # 2. Bonus pour les pleins temps
        if doctor.half_parts == 2:
            score *= 1.2

        # 3. Prise en compte des groupes
        group = self._get_post_group(post_type, datetime.now().date())
        if group:
            group_current = doctor_intervals['current_counts']['groups'].get(group, 0)
            group_max = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
            if group_max < float('inf'):
                group_ratio = group_current / group_max
                score *= (1 - group_ratio)

        # 4. Facteur aléatoire pour éviter la monotonie
        score *= 1 + (random.random() * 0.2 - 0.1)

        return max(0.1, score)

    def _try_relaxed_distribution(self, doctor: Doctor, remaining_posts: Dict,
                                dates_by_criticality: Dict,
                                quota_tracker: QuotaTracker,
                                doctor_intervals: Dict,
                                is_under_minimum: bool) -> None:
        """
        Tente une distribution avec contraintes assouplies mais maintient les limites de groupe.
        
        Args:
            doctor: Médecin à qui attribuer des postes
            remaining_posts: Postes restants à attribuer
            dates_by_criticality: Dates organisées par criticité
            quota_tracker: Suivi des quotas
            doctor_intervals: Intervalles du médecin
            is_under_minimum: Si le médecin est sous son minimum requis
        """
        try:
            # 1. Initialisation du suivi des groupes
            group_counts = defaultdict(int)
            for post_type, count in doctor_intervals['current_counts']['posts'].items():
                group = self._get_post_group(post_type, datetime.now().date())
                if group:
                    group_counts[group] += count
                    
            # 2. Pour chaque niveau de criticité
            for criticality in ['critical', 'normal']:
                for date in dates_by_criticality[criticality]:
                    # 3. Récupérer les postes disponibles pour cette date
                    available = self._get_available_posts_for_date(date, remaining_posts)
                    if not available:
                        continue
                        
                    # 4. Vérifier uniquement les desiderata primaires
                    if not self._check_primary_desiderata(doctor, date):
                        continue
                        
                    # 5. Prioriser les postes selon le besoin
                    post_types = list(available.keys())
                    if is_under_minimum:
                        # Si sous minimum, prioriser les postes les plus manquants
                        post_types.sort(key=lambda post: (
                            doctor_intervals['current_counts']['posts'].get(post, 0) -
                            doctor_intervals['posts'].get(post, {}).get('min', 0)
                        ))
                        
                    # 6. Pour chaque type de poste disponible
                    for post_type in post_types:
                        slots = available[post_type]
                        
                        # 7. Vérification stricte des maximums de poste
                        current = doctor_intervals['current_counts']['posts'].get(post_type, 0)
                        max_allowed = doctor_intervals['posts'].get(post_type, {}).get('max', float('inf'))
                        if current >= max_allowed:
                            continue
                            
                        # 8. Vérification stricte des maximums de groupe
                        group = self._get_post_group(post_type, date)
                        if group:
                            group_current = group_counts[group]
                            group_max = doctor_intervals['groups'].get(group, {}).get('max', float('inf'))
                            if group_current >= group_max:
                                continue
                                
                        # 9. Attribution avec vérification des contraintes de base
                        for slot_idx, (_, slot) in enumerate(slots[:]):
                            if not slot.assignee and self._assign_post_to_doctor(
                                doctor, date, post_type, slot,
                                doctor_intervals, quota_tracker
                            ):
                                # Mise à jour des compteurs de groupe
                                if group:
                                    group_counts[group] += 1
                                    
                                # Retrait du slot des disponibles
                                slots.pop(slot_idx)
                                if not slots:
                                    del remaining_posts[post_type]
                                break

        except Exception as e:
            logger.error(f"Erreur distribution assouplie pour {doctor.name}: {e}")

    def _check_primary_desiderata(self, doctor: Doctor, date: date) -> bool:
        """Vérifie uniquement les desiderata primaires."""
        for desiderata in doctor.desiderata:
            if (desiderata.start_date <= date <= desiderata.end_date and
                (not hasattr(desiderata, 'priority') or desiderata.priority == "primary")):
                return False
        return True
