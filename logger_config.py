# logger_config.py

import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Créer un logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Format pour les logs - plus concis
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )

    # Handler pour le fichier - taille réduite, moins de backups
    file_handler = RotatingFileHandler(
        'app.log',
        maxBytes=5242880,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)  # Niveau augmenté à INFO
    file_handler.setFormatter(formatter)

    # Handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Ajouter les handlers au logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
