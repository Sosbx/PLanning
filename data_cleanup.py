import os
import pickle
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DataCleanup:
    """Utilitaire pour nettoyer et vérifier les données persistantes."""
    
    def __init__(self):
        # Chemins des fichiers de données
        self.app_data_dir = os.path.expanduser("~/Library/Application Support/SosMedecins")
        self.data_files = [
            'app_data.pkl',
            'custom_posts.pkl',
            'planning_data.pkl',
            'post_config.pkl'
        ]

    def list_all_data(self):
        """Liste le contenu de tous les fichiers de données."""
        logger.info("\nCONTENU DES FICHIERS DE DONNÉES:")
        logger.info("=" * 60)
        
        for filename in self.data_files:
            filepath = os.path.join(self.app_data_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                    logger.info(f"\nContenu de {filename}:")
                    logger.info("-" * 40)
                    self._print_data_structure(data)
                except Exception as e:
                    logger.error(f"Erreur lecture {filename}: {e}")
            else:
                logger.info(f"\n{filename} n'existe pas")

    def clean_custom_posts(self):
        """Nettoie spécifiquement les postes personnalisés."""
        custom_posts_file = os.path.join(self.app_data_dir, 'custom_posts.pkl')
        if os.path.exists(custom_posts_file):
            try:
                os.remove(custom_posts_file)
                logger.info("custom_posts.pkl supprimé avec succès")
            except Exception as e:
                logger.error(f"Erreur suppression custom_posts.pkl: {e}")
        else:
            logger.info("custom_posts.pkl n'existe pas")

    def backup_data(self):
        """Crée une sauvegarde des données actuelles."""
        backup_dir = os.path.join(self.app_data_dir, 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        
        for filename in self.data_files:
            src = os.path.join(self.app_data_dir, filename)
            if os.path.exists(src):
                dst = os.path.join(backup_dir, filename)
                try:
                    shutil.copy2(src, dst)
                    logger.info(f"Sauvegarde créée: {filename}")
                except Exception as e:
                    logger.error(f"Erreur sauvegarde {filename}: {e}")

    def reset_all_data(self):
        """Réinitialise toutes les données persistantes."""
        # Créer d'abord une sauvegarde
        self.backup_data()
        
        # Supprimer les fichiers
        for filename in self.data_files:
            filepath = os.path.join(self.app_data_dir, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"{filename} supprimé")
                except Exception as e:
                    logger.error(f"Erreur suppression {filename}: {e}")

    def _print_data_structure(self, data, level=0):
        """Affiche la structure des données de manière récursive."""
        indent = "  " * level
        
        if isinstance(data, dict):
            for key, value in data.items():
                logger.info(f"{indent}{key}:")
                self._print_data_structure(value, level + 1)
        elif isinstance(data, (list, tuple, set)):
            for item in data:
                self._print_data_structure(item, level + 1)
        else:
            logger.info(f"{indent}{data}")

def main():
    """Point d'entrée pour utiliser l'utilitaire."""
    logging.basicConfig(level=logging.INFO,
                       format='%(message)s')
    
    cleanup = DataCleanup()
    
    print("\nQue souhaitez-vous faire ?")
    print("1: Lister toutes les données")
    print("2: Nettoyer les postes personnalisés")
    print("3: Créer une sauvegarde")
    print("4: Réinitialiser toutes les données")
    print("0: Quitter")
    
    choice = input("\nVotre choix (0-4): ")
    
    if choice == "1":
        cleanup.list_all_data()
    elif choice == "2":
        cleanup.clean_custom_posts()
    elif choice == "3":
        cleanup.backup_data()
    elif choice == "4":
        confirm = input("Cette action est irréversible. Confirmer ? (o/n): ")
        if confirm.lower() == 'o':
            cleanup.reset_all_data()
    
if __name__ == "__main__":
    main()