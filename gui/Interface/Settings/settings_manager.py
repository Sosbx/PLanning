# © 2024 HILAL Arkane. Tous droits réservés.
# gui/settings_manager.py

import json
import os
from PyQt6.QtCore import QSettings, QObject, pyqtSignal

class SettingsManager(QObject):
    """
    Gestionnaire centralisé des paramètres de l'application.
    Gère le chargement, la sauvegarde et l'accès aux paramètres utilisateur.
    """
    # Signal émis lorsque les paramètres changent
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("SOSBX", "MedHora")
        self._default_settings = {
            # Paramètres d'interface
            "ui": {
                "saturation_factor": 1.0,       # Facteur de saturation (0.5 - 1.5)
                "contrast_factor": 1.0,         # Facteur de contraste (0.8 - 1.2)
                "brightness_factor": 1.0,       # Facteur de luminosité (0.8 - 1.2)
                "font_size_factor": 1.0         # Facteur de taille de police (0.8 - 1.2)
            },
            # Paramètres spécifiques aux tableaux
            "tables": {
                "font_size_factor": 1.0,        # Facteur de taille de police (0.7 - 1.3)
                "row_height_factor": 1.0,       # Facteur de hauteur de ligne (0.8 - 1.2)
                "column_width_factor": 1.0      # Facteur de largeur de colonne (0.8 - 1.2)
            },
            # Palette de couleurs personnalisée (vide par défaut)
            "custom_colors": {
                "enabled": False,
                "primary": "",
                "secondary": "",
                "weekend": "",
                "weekday": ""
            },
            # Couleurs avancées personnalisées (nouveau)
            "advanced_colors": {
                "enabled": False,
                
                # Couleurs des désidératas
                "desiderata_primary_normal": "",    # Rouge clair pour les jours normaux
                "desiderata_primary_weekend": "",   # Rouge plus foncé pour weekends
                "desiderata_secondary_normal": "",  # Bleu clair pour jours normaux
                "desiderata_secondary_weekend": "", # Bleu plus foncé pour weekends
                
                # Couleurs des types de postes
                "post_type_consultation": "",       # Couleur pour consultations
                "post_type_visite": "",             # Couleur pour visites
                "post_type_garde": "",              # Couleur pour gardes
                
                # Couleurs des statistiques
                "stats_under_min": "",              # Couleur pour les valeurs sous le minimum
                "stats_over_max": ""                # Couleur pour les valeurs au-dessus du maximum
            }
        }
        self._settings_cache = {}
        self.load_settings()
    
    def load_settings(self):
        """Charge les paramètres depuis QSettings"""
        if self.settings.contains("settings"):
            try:
                # Charger les paramètres sauvegardés
                settings_json = self.settings.value("settings")
                loaded_settings = json.loads(settings_json)
                
                # Fusionner avec les paramètres par défaut pour garantir que toutes les clés existent
                self._settings_cache = self._merge_settings(self._default_settings, loaded_settings)
            except Exception as e:
                print(f"Erreur lors du chargement des paramètres: {e}")
                self._settings_cache = self._default_settings.copy()
        else:
            # Utiliser les paramètres par défaut
            self._settings_cache = self._default_settings.copy()
    
    def save_settings(self):
        """Sauvegarde les paramètres actuels"""
        try:
            settings_json = json.dumps(self._settings_cache)
            self.settings.setValue("settings", settings_json)
            self.settings.sync()
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des paramètres: {e}")
    
    def get_setting(self, category, key=None):
        """
        Récupère un paramètre spécifique ou une catégorie entière
        
        Args:
            category (str): Catégorie du paramètre ('ui', 'tables', etc.)
            key (str, optional): Clé spécifique. Si None, retourne toute la catégorie.
            
        Returns:
            La valeur du paramètre ou le dictionnaire de la catégorie
        """
        if category not in self._settings_cache:
            return None
            
        if key is None:
            return self._settings_cache[category]
            
        return self._settings_cache[category].get(key)
    
    def set_setting(self, category, key, value):
        """
        Définit un paramètre spécifique
        
        Args:
            category (str): Catégorie du paramètre ('ui', 'tables', etc.)
            key (str): Clé du paramètre
            value: Nouvelle valeur du paramètre
        """
        if category not in self._settings_cache:
            self._settings_cache[category] = {}
            
        # Vérifier si la valeur a changé
        old_value = self._settings_cache[category].get(key)
        if old_value != value:
            self._settings_cache[category][key] = value
            self.save_settings()
            
            # Émettre le signal de changement
            self.settings_changed.emit(self._settings_cache)
    
    def reset_settings(self, category=None):
        """
        Réinitialise les paramètres aux valeurs par défaut
        
        Args:
            category (str, optional): Catégorie à réinitialiser. Si None, réinitialise tout.
        """
        if category is None:
            # Réinitialiser tous les paramètres
            self._settings_cache = self._default_settings.copy()
        elif category in self._settings_cache and category in self._default_settings:
            # Réinitialiser une catégorie spécifique
            self._settings_cache[category] = self._default_settings[category].copy()
        
        self.save_settings()
        self.settings_changed.emit(self._settings_cache)
    
    def _merge_settings(self, defaults, loaded):
        """
        Fusionne les paramètres chargés avec les paramètres par défaut
        pour garantir que toutes les clés nécessaires existent
        """
        result = defaults.copy()
        
        for category, values in loaded.items():
            if category in result:
                if isinstance(values, dict) and isinstance(result[category], dict):
                    # Fusionner les dictionnaires de niveau inférieur
                    for key, value in values.items():
                        if key in result[category]:
                            result[category][key] = value
                else:
                    # Remplacer les valeurs non-dictionnaires
                    result[category] = values
        
        return result
    
    def get_all_settings(self):
        """Retourne une copie de tous les paramètres"""
        return self._settings_cache.copy()
