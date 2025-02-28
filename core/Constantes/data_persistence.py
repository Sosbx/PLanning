# © 2024 HILAL Arkane. Tous droits réservés.
# # core/Constantes/data_persistence.py
import logging
import datetime
from datetime import date
import pickle
import os
from core.Constantes.models import Doctor, CAT, DailyPostConfiguration, PostConfig, create_default_post_configuration, Desiderata, SpecificPostConfig
from core.Constantes.custom_post import CustomPost

logger = logging.getLogger(__name__)

class DataPersistence:
    def __init__(self, filename='app_data.pkl'):
        self.filename = filename
        self.custom_posts_filename = 'custom_posts.pkl'
        

    def save_data(self, doctors, cats, post_configuration):
        try:
            # Charger les pré-attributions existantes
            existing_pre_attributions = {}
            if os.path.exists(self.filename):
                with open(self.filename, 'rb') as file:
                    existing_data = pickle.load(file)
                    if 'pre_attributions' in existing_data:
                        existing_pre_attributions = existing_data['pre_attributions']
        except Exception as e:
            logger.error(f"Erreur chargement pré-attributions: {e}")
        
        data = {
            'version': 1,
            'pre_attributions': existing_pre_attributions,  # Préserver les pré-attributions
            'doctors': [{
                'name': d.name,
                'half_parts': d.half_parts,
                'desiderata': [{
                    'start_date': des.start_date.isoformat(),
                    'end_date': des.end_date.isoformat(),
                    'type': des.type,
                    'period': des.period,
                    'priority': getattr(des, 'priority', 'primary')  # Sauvegarde de la priorité
                } for des in d.desiderata]
            } for d in doctors],
            'cats': [{
                'name': c.name,
                'desiderata': [{
                    'start_date': des.start_date.isoformat(),
                    'end_date': des.end_date.isoformat(),
                    'type': des.type,
                    'period': des.period,
                    'priority': getattr(des, 'priority', 'primary')  # Sauvegarde de la priorité
                } for des in c.desiderata]
            } for c in cats],
            'post_configuration': self.serialize_post_configuration(post_configuration)
        }
        
        with open(self.filename, 'wb') as file:
            pickle.dump(data, file)
        logger.info("Données sauvegardées")

    def save_custom_posts(self, custom_posts_data):
        """Sauvegarde les postes personnalisés dans un fichier séparé"""
        try:
            with open(self.custom_posts_filename, 'wb') as file:
                pickle.dump(custom_posts_data, file)
            logger.info("Postes personnalisés sauvegardés")
        except Exception as e:
            logger.error(f"Error saving custom posts: {e}")

    def load_custom_posts(self):
        """Charge les postes personnalisés"""
        try:
            if os.path.exists(self.custom_posts_filename):
                with open(self.custom_posts_filename, 'rb') as file:
                    custom_posts_data = pickle.load(file)
                    # Conversion explicite en objets CustomPost
                    custom_posts = {}
                    for name, data in custom_posts_data.items():
                        try:
                            if isinstance(data, dict):
                                # Si c'est un dictionnaire, convertir en CustomPost
                                custom_posts[name] = CustomPost.from_dict(data)
                            else:
                                # Si c'est déjà un CustomPost, l'utiliser tel quel
                                custom_posts[name] = data
                        except Exception as e:
                            logger.error(f"Erreur lors de la conversion du poste {name}: {e}")
                            continue
                    return custom_posts
            return {}
        except Exception as e:
            logger.error(f"Erreur lors du chargement des postes personnalisés: {e}")
            return {}

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'rb') as file:
                    data = pickle.load(file)
                data = self.migrate_data(data)
                
                # Chargement des médecins
                doctors = [Doctor(d['name'], d['half_parts'], [
                    Desiderata(
                        datetime.date.fromisoformat(des['start_date']),
                        datetime.date.fromisoformat(des['end_date']),
                        des['type'],
                        des['period'],
                        des.get('priority', 'primary')  # Ajout de la gestion de la priorité
                    )
                    for des in d.get('desiderata', [])
                ]) for d in data.get('doctors', [])]
                
                # Chargement des CATs
                cats = [CAT(
                    c['name'],
                    desiderata=[
                        Desiderata(
                            datetime.date.fromisoformat(des['start_date']),
                            datetime.date.fromisoformat(des['end_date']),
                            des['type'],
                            des['period'],
                            des.get('priority', 'primary')  # Ajout de la gestion de la priorité
                        )
                        for des in c.get('desiderata', [])
                    ]
                ) for c in data.get('cats', [])]
                
                # Chargement de la configuration des postes
                post_config_data = data.get('post_configuration', {})
                post_configuration = DailyPostConfiguration()
                
                if isinstance(post_config_data, dict):
                    post_configuration.weekday = self._deserialize_post_config(post_config_data.get('weekday', {}))
                    post_configuration.saturday = self._deserialize_post_config(post_config_data.get('saturday', {}))
                    post_configuration.sunday_holiday = self._deserialize_post_config(post_config_data.get('sunday_holiday', {}))
                    post_configuration.cat_weekday = self._deserialize_post_config(post_config_data.get('cat_weekday', {}))
                    post_configuration.cat_saturday = self._deserialize_post_config(post_config_data.get('cat_saturday', {}))
                    post_configuration.cat_sunday_holiday = self._deserialize_post_config(post_config_data.get('cat_sunday_holiday', {}))

                    # Chargement des configurations spécifiques
                    specific_configs = []
                    for config in post_config_data.get('specific_configs', []):
                        try:
                            start_date = datetime.date.fromisoformat(config['start_date'])
                            end_date = datetime.date.fromisoformat(config['end_date'])
                            
                            # Vérification et correction des dates
                            if end_date < start_date:
                                start_date, end_date = end_date, start_date
                                logger.warning(f"Dates inversées corrigées : {start_date} - {end_date}")
                            
                            specific_configs.append(
                                SpecificPostConfig(
                                    start_date=start_date,
                                    end_date=end_date,
                                    apply_to=config.get('apply_to', config.get('day_type')),
                                    post_counts=config['post_counts']
                                )
                            )
                        except ValueError as e:
                            logger.error(f"Erreur lors du chargement d'une configuration spécifique : {e}")
                            logger.error(f"Configuration ignorée : {config}")
                            continue

                    post_configuration.specific_configs = specific_configs

                # Chargement des pré-attributions
                pre_attributions = {}
                if 'pre_attributions' in data:
                    pre_attributions = self.load_pre_attributions()
                logger.info("Données chargées")
                return doctors, cats, post_configuration, pre_attributions

            except Exception as e:
                logger.error(f"Erreur lors du chargement des données : {e}")
                logger.warning("Création d'une nouvelle configuration par défaut")
                return [], [], create_default_post_configuration()

        logger.warning("No data file found, returning default values")
        return [], [], create_default_post_configuration(), {}

    def parse_date(self, date_input):
        if isinstance(date_input, datetime.date):
            return date_input
        elif isinstance(date_input, str):
            try:
                return datetime.date.fromisoformat(date_input)
            except ValueError:
                try:
                    return datetime.date.fromtimestamp(float(date_input))
                except ValueError:
                    print(f"Impossible de parser la date: {date_input}. Utilisation de la date actuelle.")
                    return datetime.date.today()
        else:
            print(f"Type de date inattendu: {type(date_input)}. Utilisation de la date actuelle.")
            return datetime.date.today()
            
    def migrate_data(self, data):
        version = data.get('version', 0)
        if version < 1:
            # Migration vers la version 1
            for doctor in data.get('doctors', []):
                for des in doctor.get('desiderata', []):
                    if 'period' not in des:
                        des['period'] = 1  # Valeur par défaut
            for cat in data.get('cats', []):
                for des in cat.get('desiderata', []):
                    if 'period' not in des:
                        des['period'] = 1  # Valeur par défaut
            data['version'] = 1
            
            # Ajout de la structure pour les postes personnalisés si elle n'existe pas
            if 'custom_posts' not in data:
                data['custom_posts'] = {}
                
        return data
    
    def serialize_post_configuration(self, post_configuration):
        """Sérialise la configuration des postes"""
        config_data = {
            'weekday': self._serialize_post_config(post_configuration.weekday),
            'saturday': self._serialize_post_config(post_configuration.saturday),
            'sunday_holiday': self._serialize_post_config(post_configuration.sunday_holiday),
            'cat_weekday': self._serialize_post_config(post_configuration.cat_weekday),
            'cat_saturday': self._serialize_post_config(post_configuration.cat_saturday),
            'cat_sunday_holiday': self._serialize_post_config(post_configuration.cat_sunday_holiday),
            'specific_configs': []
        }

        # Sérialisation des configurations spécifiques
        if hasattr(post_configuration, 'specific_configs'):
            config_data['specific_configs'] = [{
                'start_date': config.start_date.isoformat(),
                'end_date': config.end_date.isoformat(),
                'apply_to': config.apply_to,
                'post_counts': config.post_counts
            } for config in post_configuration.specific_configs]

        return config_data

    def deserialize_post_configuration(self, config_data):
        """Désérialise la configuration des postes"""
        post_configuration = DailyPostConfiguration()
        
        if isinstance(config_data, dict):
            # Configuration standard
            post_configuration.weekday = self._deserialize_post_config(config_data.get('weekday', {}))
            post_configuration.saturday = self._deserialize_post_config(config_data.get('saturday', {}))
            post_configuration.sunday_holiday = self._deserialize_post_config(config_data.get('sunday_holiday', {}))
            post_configuration.cat_weekday = self._deserialize_post_config(config_data.get('cat_weekday', {}))
            post_configuration.cat_saturday = self._deserialize_post_config(config_data.get('cat_saturday', {}))
            post_configuration.cat_sunday_holiday = self._deserialize_post_config(config_data.get('cat_sunday_holiday', {}))
            
            # Désérialisation des configurations spécifiques
            post_configuration.specific_configs = []
            for config in config_data.get('specific_configs', []):
                try:
                    specific_config = SpecificPostConfig(
                        start_date=datetime.date.fromisoformat(config['start_date']),
                        end_date=datetime.date.fromisoformat(config['end_date']),
                        apply_to=config['apply_to'],
                        post_counts=config['post_counts']
                    )
                    post_configuration.specific_configs.append(specific_config)
                except (ValueError, KeyError) as e:
                    self.logger.error(f"Erreur lors de la désérialisation d'une configuration spécifique : {e}")
                    self.logger.error(f"Configuration ignorée : {config}")
                    continue

        return post_configuration

    def _serialize_post_config(self, config):
        """Sérialise une configuration de poste simple"""
        return {post_type: post_config.total for post_type, post_config in config.items()}

    def _deserialize_post_config(self, data):
        """Désérialise une configuration de poste simple"""
        return {post_type: PostConfig(total=total) for post_type, total in data.items()}

    def save_pre_attributions(self, pre_attributions, history=None):
        """Sauvegarde les pré-attributions et leur historique dans le fichier de données"""
        try:
            # Charger les données existantes
            with open(self.filename, 'rb') as file:
                data = pickle.load(file)
            
            # Convertir les dates en format ISO pour la sérialisation
            serialized_pre_attributions = {}
            for person_name, attributions in pre_attributions.items():
                serialized_attributions = {}
                for (d, period), post in attributions.items():
                    # Convertir la date en string ISO
                    date_str = d.isoformat()
                    serialized_attributions[(date_str, period)] = post
                serialized_pre_attributions[person_name] = serialized_attributions
            
            # Ajouter ou mettre à jour les pré-attributions
            data['pre_attributions'] = serialized_pre_attributions
            
            # Sauvegarder l'historique si fourni
            if history is not None:
                serialized_history = []
                for timestamp, action_type, details in history:
                    serialized_history.append((timestamp.isoformat(), action_type, details))
                data['pre_attribution_history'] = serialized_history
            
            # Sauvegarder les données mises à jour
            with open(self.filename, 'wb') as file:
                pickle.dump(data, file)
            
            logger.info("Pré-attributions sauvegardées")
        except Exception as e:
            logger.error(f"Error saving pre-attributions: {e}")
            raise
    
    def load_pre_attributions(self, load_history=True):
        """
        Charge les pré-attributions et leur historique depuis le fichier de données
        
        Args:
            load_history (bool): Si True, charge aussi l'historique
            
        Returns:
            dict ou tuple: Dictionnaire des pré-attributions si load_history=False, 
                        sinon tuple (pre_attributions, history)
        """
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'rb') as file:
                    data = pickle.load(file)
                
                # Récupérer les pré-attributions
                serialized_pre_attributions = data.get('pre_attributions', {})
                
                # Convertir les dates string en objets date
                pre_attributions = {}
                for person_name, attributions in serialized_pre_attributions.items():
                    person_attributions = {}
                    for key, post in attributions.items():
                        try:
                            # Gérer les différents formats possibles
                            if isinstance(key, tuple) and len(key) == 2:
                                date_str, period = key
                                if isinstance(date_str, str):
                                    d = date.fromisoformat(date_str)
                                elif isinstance(date_str, date):
                                    d = date_str
                                else:
                                    # Ignorer les entrées invalides
                                    logger.warning(f"Format de date invalide ignoré : {date_str}")
                                    continue
                                
                                if isinstance(period, int):
                                    person_attributions[(d, period)] = post
                                else:
                                    # Tenter de convertir en entier
                                    try:
                                        period_int = int(period)
                                        person_attributions[(d, period_int)] = post
                                    except (ValueError, TypeError):
                                        logger.warning(f"Format de période invalide ignoré : {period}")
                                        continue
                        except Exception as e:
                            logger.warning(f"Erreur lors de la conversion d'une attribution : {e}")
                            continue
                    
                    if person_attributions:  # N'ajouter que s'il y a des attributions valides
                        pre_attributions[person_name] = person_attributions
                
                if load_history:
                    # Charger l'historique
                    history = []
                    serialized_history = data.get('pre_attribution_history', [])
                    
                    for entry in serialized_history:
                        try:
                            if isinstance(entry, tuple) and len(entry) >= 3:
                                timestamp_str, action_type, details = entry
                                
                                # Conversion du timestamp
                                if isinstance(timestamp_str, str):
                                    try:
                                        # Utiliser datetime.fromisoformat()
                                        from datetime import datetime
                                        timestamp = datetime.fromisoformat(timestamp_str)
                                    except ValueError:
                                        # Utiliser l'heure actuelle en cas d'erreur
                                        from datetime import datetime
                                        timestamp = datetime.now()
                                        logger.warning(f"Timestamp invalide, utilisation de l'heure actuelle : {timestamp_str}")
                                elif hasattr(timestamp_str, 'timestamp'):  # Si c'est un objet datetime ou date
                                    timestamp = timestamp_str
                                else:
                                    from datetime import datetime
                                    timestamp = datetime.now()
                                    logger.warning(f"Type de timestamp non pris en charge : {type(timestamp_str)}")
                                
                                history.append((timestamp, action_type, details))
                        except Exception as e:
                            logger.warning(f"Erreur lors du chargement d'une entrée d'historique : {e}")
                            continue
                    
                    return pre_attributions, history
                
                return pre_attributions
            
            # Retourner des structures vides si le fichier n'existe pas
            if load_history:
                return {}, []
            return {}
        except Exception as e:
            logger.error(f"Erreur lors du chargement des pré-attributions : {e}")
            # Retourner des structures vides en cas d'erreur
            if load_history:
                return {}, []
            return {}

    def debug_dates(self, doctors, cats):
        print("Debugging dates:")
        for doctor in doctors:
            for des in doctor.desiderata:
                print(f"{doctor.name}: {des}")
        for cat in cats:
            for des in cat.desiderata:
                print(f"{cat.name}: {des}")


    def save_post_attributions(self, post_attributions):
        """
        Sauvegarde les post-attributions dans un fichier.
        
        Args:
            post_attributions (dict): Dictionnaire des post-attributions {date: {assignee: {period: post_type}}}
        """
        try:
            # Charger les données existantes
            if os.path.exists(self.filename):
                with open(self.filename, 'rb') as file:
                    data = pickle.load(file)
            else:
                # Créer un nouveau dictionnaire si le fichier n'existe pas
                data = {'version': 1, 'doctors': [], 'cats': [], 'post_configuration': {}}
            
            # Conversion des dates (objets) en chaînes
            serializable_data = {}
            for date_obj, assignees in post_attributions.items():
                date_str = date_obj.isoformat()
                serializable_data[date_str] = {}
                for assignee, periods in assignees.items():
                    serializable_data[date_str][assignee] = {str(p): pt for p, pt in periods.items()}
            
            # Ajouter ou mettre à jour les post-attributions
            data['post_attributions'] = serializable_data
            
            # Sauvegarder les données mises à jour
            with open(self.filename, 'wb') as file:
                pickle.dump(data, file)
            
            logger.info("Post-attributions sauvegardées")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des post-attributions: {e}")
            raise

    def load_post_attributions(self):
        """
        Charge les post-attributions depuis un fichier.
        
        Returns:
            dict: Dictionnaire des post-attributions {date: {assignee: {period: post_type}}}
        """
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'rb') as file:
                    data = pickle.load(file)
                
                # Récupérer les post-attributions
                serialized_data = data.get('post_attributions', {})
                
                # Conversion des chaînes en dates (objets)
                post_attributions = {}
                for date_str, assignees in serialized_data.items():
                    date_obj = datetime.date.fromisoformat(date_str)
                    post_attributions[date_obj] = {}
                    for assignee, periods in assignees.items():
                        post_attributions[date_obj][assignee] = {int(p): pt for p, pt in periods.items()}
                
                return post_attributions
            return {}
        except Exception as e:
            logger.error(f"Erreur lors du chargement des post-attributions: {e}")
            return {}
