# © 2024 HILAL Arkane. Tous droits réservés.
# # core/Constantes/data_persistence.py
import logging
import datetime
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
        logger.info("Starting save_data process")
        
        # Charger les pré-attributions existantes
        existing_pre_attributions = {}
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'rb') as file:
                    existing_data = pickle.load(file)
                    if 'pre_attributions' in existing_data:
                        existing_pre_attributions = existing_data['pre_attributions']
        except Exception as e:
            logger.error(f"Error loading existing pre-attributions: {e}")
        
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
        logger.info("Data saved successfully")

    def save_custom_posts(self, custom_posts_data):
        """Sauvegarde les postes personnalisés dans un fichier séparé"""
        try:
            with open(self.custom_posts_filename, 'wb') as file:
                pickle.dump(custom_posts_data, file)
            logger.info("Custom posts saved successfully")
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
                            logger.info(f"Poste personnalisé chargé: {name}")
                        except Exception as e:
                            logger.error(f"Erreur lors de la conversion du poste {name}: {e}")
                            continue
                    return custom_posts
            return {}
        except Exception as e:
            logger.error(f"Erreur lors du chargement des postes personnalisés: {e}")
            return {}

    def load_data(self):
        logger.info("Starting load_data process")
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'rb') as file:
                    data = pickle.load(file)
                
                logger.debug(f"Raw loaded data: {data}")
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
                    logger.info("Pre-attributions loaded successfully")

                logger.info("Data loaded successfully")
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

    def save_pre_attributions(self, pre_attributions):
        """Sauvegarde les pré-attributions dans le fichier de données"""
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
            
            # Sauvegarder les données mises à jour
            with open(self.filename, 'wb') as file:
                pickle.dump(data, file)
            
            logger.info("Pre-attributions saved successfully")
        except Exception as e:
            logger.error(f"Error saving pre-attributions: {e}")
            raise
    
    def load_pre_attributions(self):
        """Charge les pré-attributions depuis le fichier de données"""
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
                    for (date_str, period), post in attributions.items():
                        # Convertir la string ISO en objet date
                        d = datetime.date.fromisoformat(date_str)
                        person_attributions[(d, period)] = post
                    pre_attributions[person_name] = person_attributions
                
                return pre_attributions
            return {}
        except Exception as e:
            logger.error(f"Error loading pre-attributions: {e}")
            return {}

    def debug_dates(self, doctors, cats):
        print("Debugging dates:")
        for doctor in doctors:
            for des in doctor.desiderata:
                print(f"{doctor.name}: {des}")
        for cat in cats:
            for des in cat.desiderata:
                print(f"{cat.name}: {des}")
