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
from gui.styles import GLOBAL_STYLE

def resource_path(relative_path):
    """Get the absolute path to the resource, works for development and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def set_application_style(app):
    # High DPI support is enabled by default in PyQt6
    app.setStyle("Fusion")
    
    # Palette de couleurs adaptative
    is_windows = sys.platform == 'win32'
    palette = QPalette()
    
    # Couleurs adaptées selon le système
    window_bg = QColor(235, 240, 245) if is_windows else QColor(240, 242, 245)
    text_color = QColor(40, 40, 40) if is_windows else QColor(50, 50, 50)
    button_bg = QColor(215, 220, 225) if is_windows else QColor(225, 225, 230)
    highlight = QColor(75, 115, 150) if is_windows else QColor(85, 125, 160)
    
    palette.setColor(QPalette.ColorRole.Window, window_bg)
    palette.setColor(QPalette.ColorRole.WindowText, text_color)
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, window_bg)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 225))
    palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    palette.setColor(QPalette.ColorRole.Text, text_color)
    palette.setColor(QPalette.ColorRole.Button, button_bg)
    palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    app.setPalette(palette)

    # Application du style global et des styles spécifiques
    # Styles adaptés selon le système d'exploitation
    is_windows = sys.platform == 'win32'
    button_bg = "#2C5E90" if is_windows else "#3C6EA0"
    button_hover = "#407AAD" if is_windows else "#508CBB"
    button_pressed = "#1A4270" if is_windows else "#2A5280"
    
    app.setStyleSheet(GLOBAL_STYLE + f"""
    QPushButton {{
        background-color: {button_bg};
        color: white;
        border: none;
        padding: 8px 18px;
        border-radius: 4px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton:pressed {{
        background-color: {button_pressed};
    }}
    QTableWidget, QTreeWidget, QListWidget {{
        background-color: white;
        alternate-background-color: {"#F0F2F5" if is_windows else "#F8F8FA"};
    }}
    QHeaderView::section {{
        background-color: {"#D6D6E1" if is_windows else "#E6E6EB"};
        color: {"#202020" if is_windows else "#323232"};
        padding: 5px;
        border: none;
        border-right: 1px solid {"#C0C0C8" if is_windows else "#D0D0D8"};
        border-bottom: 1px solid {"#C0C0C8" if is_windows else "#D0D0D8"};
        font-weight: bold;
    }}
    QTabWidget::pane {{
        border: 1px solid {"#C0C0C8" if is_windows else "#D0D0D8"};
        background-color: {"#EFF0F5" if is_windows else "#F5F5FA"};
    }}
    QTabBar::tab {{
        background-color: {"#D6D6E1" if is_windows else "#E6E6EB"};
        color: {"#202020" if is_windows else "#323232"};
        padding: 8px 16px;
        border: 1px solid {"#C0C0C8" if is_windows else "#D0D0D8"};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {"#EFF0F5" if is_windows else "#F5F5FA"};
        border-bottom: 2px solid {"#456D90" if is_windows else "#557DA0"};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {"#E8E8F0" if is_windows else "#F2F2F5"};
    }}
    QComboBox, QDateEdit {{
        background-color: {"#FAFAFA" if is_windows else "#FFFFFF"};
        color: {"#202020" if is_windows else "#323232"};
        border: 1px solid {"#C0C0C8" if is_windows else "#D0D0D8"};
        padding: 6px;
        border-radius: 6px;
    }}
    QScrollBar:vertical {{
        background-color: {"#E8E8F0" if is_windows else "#F2F2F5"};
        width: 12px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {"#B0B0B8" if is_windows else "#C0C0C8"};
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {"#909098" if is_windows else "#A0A0A8"};
    }}
    QGroupBox {{
        border: 1px solid {"#C0C0C8" if is_windows else "#D0D0D8"};
        border-radius: 6px;
        padding-top: 10px;
    }}
    QGroupBox::title {{
        color: {"#456D90" if is_windows else "#557DA0"};
        font-weight: bold;
    }}
    """)

class LoaderThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(tuple)

    def run(self):
        self.update_signal.emit("Chargement des données...")
        data_persistence = DataPersistence()
        doctors, cats, post_configuration = data_persistence.load_data()

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
        self.finished_signal.emit((doctors, cats, post_configuration))


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

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    sys.exit(app.exec())

def on_load_finished(data, splash):
    doctors, cats, post_configuration = data
    window = MainWindow(doctors, cats, post_configuration)
    
    def show_main_window():
        splash.finish(window)  # Ceci fermera le splash screen
        window.show()

    QTimer.singleShot(1000, show_main_window)  # Attendre au moins 3 secondes

if __name__ == "__main__":
    main()
