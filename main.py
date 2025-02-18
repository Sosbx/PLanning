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
from gui.main_window import MainWindow
from gui.splash_screen import SplashScreen
from core.Constantes.models import Doctor, CAT, create_default_post_configuration
from core.Constantes.data_persistence import DataPersistence
from gui.styles import color_system, GLOBAL_STYLE

def set_application_style(app):
    """Configure le style global de l'application"""
    app.setStyle("Fusion")
    
    # Palette de couleurs adaptative
    palette = QPalette()
    
    # Couleurs de base depuis le système de styles
    palette.setColor(QPalette.ColorRole.Window, color_system.colors['window_background'])
    palette.setColor(QPalette.ColorRole.WindowText, color_system.colors['text']['primary'])
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, color_system.colors['table']['alternate'])
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 225))
    palette.setColor(QPalette.ColorRole.ToolTipText, color_system.colors['text']['primary'])
    palette.setColor(QPalette.ColorRole.Text, color_system.colors['text']['primary'])
    palette.setColor(QPalette.ColorRole.Button, color_system.colors['primary'])
    palette.setColor(QPalette.ColorRole.ButtonText, color_system.colors['text']['light'])
    palette.setColor(QPalette.ColorRole.Highlight, color_system.colors['primary'])
    palette.setColor(QPalette.ColorRole.HighlightedText, color_system.colors['text']['light'])

    app.setPalette(palette)
    app.setStyleSheet(GLOBAL_STYLE)

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

def main():
    logger = setup_logger()
    app = QApplication(sys.argv)
    set_application_style(app)

    splash = SplashScreen()
    splash.show()

    loader_thread = LoaderThread()
    loader_thread.update_signal.connect(splash.update_message)
    loader_thread.finished_signal.connect(lambda data: on_load_finished(data, splash))
    loader_thread.start()

    logging.basicConfig(level=logging.DEBUG, 
                     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    sys.exit(app.exec())

def on_load_finished(data, splash):
    doctors, cats, post_configuration, pre_attributions = data
    window = MainWindow(doctors, cats, post_configuration, pre_attributions)
    
    def show_main_window():
        splash.finish(window)
        window.show()

    QTimer.singleShot(1000, show_main_window)

if __name__ == "__main__":
    main()
