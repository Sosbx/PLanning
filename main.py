# © 2024 HILAL Arkane. Tous droits réservés.
# main.py

import os
import logging
import sys
from PyQt6.QtCore import Qt
from logger_config import setup_logger
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from gui.Interface.main_window import MainWindow
from gui.splash_screen import SplashScreen
from gui.landing_page import LandingPage
from core.Constantes.models import Doctor, CAT, create_default_post_configuration
from core.Constantes.data_persistence import DataPersistence
from gui.styles import color_system, GLOBAL_STYLE

# Variables globales pour les fenêtres
landing_page_instance = None
main_window_instance = None

def set_application_style(app):
    """Configure le style global de l'application de manière robuste pour toutes les plateformes"""
    app.setStyle("Fusion")  # Style Fusion est bien supporté sur toutes les plateformes
    
    # Palette de couleurs adaptative
    palette = QPalette()
    
    # Utiliser la classe PlatformHelper pour ajuster les couleurs selon la plateforme
    from gui.styles import PlatformHelper
    
    # Couleurs de base depuis le système de styles
    window_bg = color_system.get_color('window_background')
    window_text = color_system.get_color('text', 'primary')
    base_color = QColor(255, 255, 255)  # Couleur de base toujours blanche
    alt_base = color_system.get_color('table', 'alternate')
    tooltip_base = QColor(255, 255, 225)  # Jaune très pâle pour les tooltips
    text_color = color_system.get_color('text', 'primary')
    button_color = color_system.get_color('primary')
    button_text = color_system.get_color('text', 'light')
    highlight = color_system.get_color('primary')
    highlight_text = color_system.get_color('text', 'light')
    
    # Application des couleurs à la palette
    palette.setColor(QPalette.ColorRole.Window, window_bg)
    palette.setColor(QPalette.ColorRole.WindowText, window_text)
    palette.setColor(QPalette.ColorRole.Base, base_color)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, tooltip_base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    palette.setColor(QPalette.ColorRole.Text, text_color)
    palette.setColor(QPalette.ColorRole.Button, button_color)
    palette.setColor(QPalette.ColorRole.ButtonText, button_text)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, highlight_text)
    
    # Pour une meilleure compatibilité Windows, définir également ces rôles
    if PlatformHelper.get_platform() == 'Windows':
        # Ces rôles supplémentaires sont nécessaires sur Windows
        palette.setColor(QPalette.ColorRole.Light, window_bg.lighter(120))
        palette.setColor(QPalette.ColorRole.Midlight, window_bg.lighter(110))
        palette.setColor(QPalette.ColorRole.Mid, window_bg.darker(120))
        palette.setColor(QPalette.ColorRole.Dark, window_bg.darker(160))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(0, 0, 0, 100))
        
        # Paramètres spécifiques à Windows pour les contrôles
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link, color_system.get_color('primary'))
        palette.setColor(QPalette.ColorRole.LinkVisited, color_system.get_color('primary').darker(120))
        
        # S'assurer que les boutons et widgets ont un arrière-plan bien défini
        app.setStyleSheet(app.styleSheet() + """
            QPushButton, QComboBox, QLineEdit, QSpinBox, QDateEdit, QTimeEdit {
                background-color: """ + color_system.get_hex_color('container', 'background') + """;
            }
            
            QTableView, QTableWidget {
                background-color: """ + color_system.get_hex_color('table', 'background') + """;
                alternate-background-color: """ + color_system.get_hex_color('table', 'alternate') + """;
            }
        """)

    # Appliquer la palette
    app.setPalette(palette)
    
    # Appliquer le style global
    app.setStyleSheet(GLOBAL_STYLE)
    
    # Pour Windows, forcer la mise à jour du style
    if PlatformHelper.get_platform() == 'Windows':
        app.style().unpolish(app)
        app.style().polish(app)

class LoaderThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(tuple)

    def run(self):
        self.update_signal.emit("Chargement des données...")
        data_persistence = DataPersistence()
        doctors, cats, post_configuration, pre_attributions = data_persistence.load_data()

        if not doctors and not cats:
            self.update_signal.emit("Création des données par défaut...")
            doctors = [
                Doctor("Dr. Smith", 2),
                Doctor("Dr. Johnson", 1),
                Doctor("Dr. Williams", 2),
            ]
            cats = [
                CAT("CAT 1"),
                CAT("CAT 2"),
            ]

        if post_configuration is None:
            self.update_signal.emit("Création de la configuration par défaut...")
            post_configuration = create_default_post_configuration()

        self.update_signal.emit("Initialisation de l'interface...")
        self.finished_signal.emit((doctors, cats, post_configuration, pre_attributions))

def on_navigate_to_tab(tab_index):
    """Fonction appelée quand on clique sur une carte de la landing page"""
    global landing_page_instance, main_window_instance
    if main_window_instance:
        # Définir l'onglet actif
        main_window_instance.tab_widget.setCurrentIndex(tab_index)
        # Cacher la landing page et montrer la fenêtre principale
        if landing_page_instance:
            landing_page_instance.hide()
        main_window_instance.show()
        print(f"Navigation vers l'onglet {tab_index}")

def on_return_to_landing():
    """Fonction appelée quand on clique sur le bouton Accueil"""
    global landing_page_instance, main_window_instance
    if landing_page_instance and main_window_instance:
        # Cacher la fenêtre principale et montrer la landing page
        main_window_instance.hide()
        landing_page_instance.show()
        print("Retour à la landing page")

def main():
    global landing_page_instance, main_window_instance
    
    logger = setup_logger()
    app = QApplication(sys.argv)
    set_application_style(app)

    splash = SplashScreen()
    splash.show()

    loader_thread = LoaderThread()
    loader_thread.update_signal.connect(splash.update_message)
    
    def on_load_finished(data):
        global landing_page_instance, main_window_instance
        
        doctors, cats, post_configuration, pre_attributions = data
        
        # Créer les fenêtres
        landing_page_instance = LandingPage()
        main_window_instance = MainWindow(doctors, cats, post_configuration, pre_attributions)
        
        # Connecter les signaux
        landing_page_instance.navigate_to_tab.connect(on_navigate_to_tab)
        if hasattr(main_window_instance, 'return_to_landing'):
            main_window_instance.return_to_landing.connect(on_return_to_landing)
            print("Signal return_to_landing connecté")
        else:
            print("ERREUR: Signal return_to_landing non trouvé!")
        
        # Afficher la landing page après le splash screen
        def show_landing():
            splash.finish(landing_page_instance)
            landing_page_instance.show()
            print("Landing page affichée")
        
        QTimer.singleShot(800, show_landing)
    
    loader_thread.finished_signal.connect(on_load_finished)
    loader_thread.start()

    logging.basicConfig(level=logging.DEBUG, 
                     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    sys.exit(app.exec())

if __name__ == "__main__":
    main()