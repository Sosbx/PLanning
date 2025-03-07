# © 2024 HILAL Arkane. Tous droits réservés.
# gui/Interface/Settings/settings_view.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
                            QSlider, QCheckBox, QPushButton, QGroupBox, QGridLayout,
                            QSpinBox, QDoubleSpinBox, QColorDialog, QFrame, QDialog,
                            QDialogButtonBox, QMessageBox, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon

from gui.styles import color_system, StyleConstants, GLOBAL_STYLE
from gui.Interface.Settings.settings_manager import SettingsManager

class ColorPreview(QFrame):
    """Widget pour prévisualiser une couleur avec texte d'étiquette"""
    def __init__(self, color_name, color=None, parent=None):
        super().__init__(parent)
        self.color_name = color_name
        self.color = color or QColor(255, 255, 255)
        self.setMinimumHeight(30)
        self.setMinimumWidth(80)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.update_color(self.color)
        
    def update_color(self, color):
        """Met à jour la couleur du widget"""
        self.color = color
        self.setStyleSheet(f"""
            background-color: {color.name()};
            border: 1px solid #999;
        """)
        
class SettingsDialog(QDialog):
    """
    Fenêtre de dialogue pour la configuration des paramètres de l'application.
    Permet d'ajuster l'interface utilisateur, les couleurs et les tailles de police.
    """
    # Signal émis lorsque les paramètres sont appliqués
    settings_applied = pyqtSignal()
    
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.current_settings = settings_manager.get_all_settings()
        self.modified = False
        
        self.setWindowTitle("Paramètres d'affichage")
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)
        
        self.init_ui()
        self.load_current_settings()
        
    def init_ui(self):
        """Initialise l'interface utilisateur du dialogue"""
        main_layout = QVBoxLayout(self)
        
        # Créer un widget à onglets
        self.tab_widget = QTabWidget()
        
        # Onglet 1: Paramètres généraux de l'interface
        ui_tab = QWidget()
        ui_layout = QVBoxLayout(ui_tab)
        
        # Groupe Apparence
        appearance_group = QGroupBox("Apparence de l'interface")
        appearance_layout = QGridLayout(appearance_group)
        
        # Saturation
        appearance_layout.addWidget(QLabel("Saturation des couleurs:"), 0, 0)
        self.saturation_slider = QSlider(Qt.Orientation.Horizontal)
        self.saturation_slider.setRange(50, 150)
        self.saturation_slider.setValue(100)
        self.saturation_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.saturation_slider.setTickInterval(10)
        self.saturation_slider.valueChanged.connect(self.on_setting_changed)
        appearance_layout.addWidget(self.saturation_slider, 0, 1)
        self.saturation_value = QLabel("1.0")
        appearance_layout.addWidget(self.saturation_value, 0, 2)
        
        # Luminosité
        appearance_layout.addWidget(QLabel("Luminosité:"), 1, 0)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(80, 120)
        self.brightness_slider.setValue(100)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_slider.setTickInterval(5)
        self.brightness_slider.valueChanged.connect(self.on_setting_changed)
        appearance_layout.addWidget(self.brightness_slider, 1, 1)
        self.brightness_value = QLabel("1.0")
        appearance_layout.addWidget(self.brightness_value, 1, 2)
        
        # Contraste
        appearance_layout.addWidget(QLabel("Contraste:"), 2, 0)
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(80, 120)
        self.contrast_slider.setValue(100)
        self.contrast_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.contrast_slider.setTickInterval(5)
        self.contrast_slider.valueChanged.connect(self.on_setting_changed)
        appearance_layout.addWidget(self.contrast_slider, 2, 1)
        self.contrast_value = QLabel("1.0")
        appearance_layout.addWidget(self.contrast_value, 2, 2)
        
        # Taille de police générale
        appearance_layout.addWidget(QLabel("Taille de police générale:"), 3, 0)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(80, 120)
        self.font_size_slider.setValue(100)
        self.font_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.font_size_slider.setTickInterval(5)
        self.font_size_slider.valueChanged.connect(self.on_setting_changed)
        appearance_layout.addWidget(self.font_size_slider, 3, 1)
        self.font_size_value = QLabel("1.0")
        appearance_layout.addWidget(self.font_size_value, 3, 2)
        
        ui_layout.addWidget(appearance_group)
        
        # Onglet 2: Paramètres des tableaux
        tables_tab = QWidget()
        tables_layout = QVBoxLayout(tables_tab)
        
        # Groupe Tableaux
        tables_group = QGroupBox("Affichage des tableaux")
        tables_grid = QGridLayout(tables_group)
        
        # Taille de police des tableaux
        tables_grid.addWidget(QLabel("Taille de police:"), 0, 0)
        self.table_font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.table_font_size_slider.setRange(70, 130)
        self.table_font_size_slider.setValue(100)
        self.table_font_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.table_font_size_slider.setTickInterval(10)
        self.table_font_size_slider.valueChanged.connect(self.on_setting_changed)
        tables_grid.addWidget(self.table_font_size_slider, 0, 1)
        self.table_font_size_value = QLabel("1.0")
        tables_grid.addWidget(self.table_font_size_value, 0, 2)
        
        # Hauteur des lignes
        tables_grid.addWidget(QLabel("Hauteur des lignes:"), 1, 0)
        self.row_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.row_height_slider.setRange(80, 120)
        self.row_height_slider.setValue(100)
        self.row_height_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.row_height_slider.setTickInterval(5)
        self.row_height_slider.valueChanged.connect(self.on_setting_changed)
        tables_grid.addWidget(self.row_height_slider, 1, 1)
        self.row_height_value = QLabel("1.0")
        tables_grid.addWidget(self.row_height_value, 1, 2)
        
        # Largeur des colonnes
        tables_grid.addWidget(QLabel("Largeur des colonnes:"), 2, 0)
        self.column_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.column_width_slider.setRange(80, 120)
        self.column_width_slider.setValue(100)
        self.column_width_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.column_width_slider.setTickInterval(5)
        self.column_width_slider.valueChanged.connect(self.on_setting_changed)
        tables_grid.addWidget(self.column_width_slider, 2, 1)
        self.column_width_value = QLabel("1.0")
        tables_grid.addWidget(self.column_width_value, 2, 2)
        
        tables_layout.addWidget(tables_group)
        
        # Onglet 3: Couleurs principales
        colors_tab = QWidget()
        colors_layout = QVBoxLayout(colors_tab)
        
        # Activer/désactiver les couleurs personnalisées
        self.enable_custom_colors = QCheckBox("Activer les couleurs personnalisées")
        self.enable_custom_colors.setChecked(False)
        self.enable_custom_colors.stateChanged.connect(self.on_custom_colors_toggled)
        colors_layout.addWidget(self.enable_custom_colors)
        
        # Couleurs personnalisables
        colors_group = QGroupBox("Couleurs principales")
        colors_grid = QGridLayout(colors_group)
        
        # Couleur primaire
        colors_grid.addWidget(QLabel("Couleur primaire:"), 0, 0)
        self.primary_color_preview = ColorPreview("primary", color_system.get_color('primary'))
        colors_grid.addWidget(self.primary_color_preview, 0, 1)
        self.primary_color_button = QPushButton("Changer...")
        self.primary_color_button.clicked.connect(lambda: self.pick_color('primary'))
        self.primary_color_button.setEnabled(False)
        colors_grid.addWidget(self.primary_color_button, 0, 2)
        
        # Couleur secondaire
        colors_grid.addWidget(QLabel("Couleur secondaire:"), 1, 0)
        self.secondary_color_preview = ColorPreview("secondary", color_system.get_color('secondary'))
        colors_grid.addWidget(self.secondary_color_preview, 1, 1)
        self.secondary_color_button = QPushButton("Changer...")
        self.secondary_color_button.clicked.connect(lambda: self.pick_color('secondary'))
        self.secondary_color_button.setEnabled(False)
        colors_grid.addWidget(self.secondary_color_button, 1, 2)
        
        # Couleur weekend
        colors_grid.addWidget(QLabel("Couleur weekend:"), 2, 0)
        self.weekend_color_preview = ColorPreview("weekend", color_system.get_color('weekend'))
        colors_grid.addWidget(self.weekend_color_preview, 2, 1)
        self.weekend_color_button = QPushButton("Changer...")
        self.weekend_color_button.clicked.connect(lambda: self.pick_color('weekend'))
        self.weekend_color_button.setEnabled(False)
        colors_grid.addWidget(self.weekend_color_button, 2, 2)
        
        # Couleur jour de semaine
        colors_grid.addWidget(QLabel("Couleur jour de semaine:"), 3, 0)
        self.weekday_color_preview = ColorPreview("weekday", color_system.get_color('weekday'))
        colors_grid.addWidget(self.weekday_color_preview, 3, 1)
        self.weekday_color_button = QPushButton("Changer...")
        self.weekday_color_button.clicked.connect(lambda: self.pick_color('weekday'))
        self.weekday_color_button.setEnabled(False)
        colors_grid.addWidget(self.weekday_color_button, 3, 2)
        
        colors_layout.addWidget(colors_group)
        
        # Bouton de réinitialisation
        reset_colors_button = QPushButton("Réinitialiser les couleurs principales")
        reset_colors_button.clicked.connect(self.reset_colors)
        colors_layout.addWidget(reset_colors_button)
        
        # Onglet 4: Couleurs avancées (nouveau)
        advanced_tab = QWidget()
        
        # Utiliser un scroll area pour les nombreuses options
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        advanced_content = QWidget()
        advanced_layout = QVBoxLayout(advanced_content)
        
        # Activer/désactiver les couleurs avancées
        self.enable_advanced_colors = QCheckBox("Activer les couleurs avancées personnalisées")
        self.enable_advanced_colors.setChecked(False)
        self.enable_advanced_colors.stateChanged.connect(self.on_advanced_colors_toggled)
        advanced_layout.addWidget(self.enable_advanced_colors)
        
        # Groupe des couleurs de désidératas
        desiderata_group = QGroupBox("Couleurs des désidératas")
        desiderata_grid = QGridLayout(desiderata_group)
        
        # Désidératas primaires - Jour normal
        desiderata_grid.addWidget(QLabel("Primaire - Jour normal:"), 0, 0)
        self.desiderata_primary_normal_preview = ColorPreview(
            "desiderata_primary_normal", 
            color_system.colors['desiderata']['primary']['normal']
        )
        desiderata_grid.addWidget(self.desiderata_primary_normal_preview, 0, 1)
        self.desiderata_primary_normal_button = QPushButton("Changer...")
        self.desiderata_primary_normal_button.clicked.connect(
            lambda: self.pick_advanced_color('desiderata_primary_normal')
        )
        self.desiderata_primary_normal_button.setEnabled(False)
        desiderata_grid.addWidget(self.desiderata_primary_normal_button, 0, 2)
        
        # Désidératas primaires - Weekend
        desiderata_grid.addWidget(QLabel("Primaire - Weekend:"), 1, 0)
        self.desiderata_primary_weekend_preview = ColorPreview(
            "desiderata_primary_weekend", 
            color_system.colors['desiderata']['primary']['weekend']
        )
        desiderata_grid.addWidget(self.desiderata_primary_weekend_preview, 1, 1)
        self.desiderata_primary_weekend_button = QPushButton("Changer...")
        self.desiderata_primary_weekend_button.clicked.connect(
            lambda: self.pick_advanced_color('desiderata_primary_weekend')
        )
        self.desiderata_primary_weekend_button.setEnabled(False)
        desiderata_grid.addWidget(self.desiderata_primary_weekend_button, 1, 2)
        
        # Désidératas secondaires - Jour normal
        desiderata_grid.addWidget(QLabel("Secondaire - Jour normal:"), 2, 0)
        self.desiderata_secondary_normal_preview = ColorPreview(
            "desiderata_secondary_normal", 
            color_system.colors['desiderata']['secondary']['normal']
        )
        desiderata_grid.addWidget(self.desiderata_secondary_normal_preview, 2, 1)
        self.desiderata_secondary_normal_button = QPushButton("Changer...")
        self.desiderata_secondary_normal_button.clicked.connect(
            lambda: self.pick_advanced_color('desiderata_secondary_normal')
        )
        self.desiderata_secondary_normal_button.setEnabled(False)
        desiderata_grid.addWidget(self.desiderata_secondary_normal_button, 2, 2)
        
        # Désidératas secondaires - Weekend
        desiderata_grid.addWidget(QLabel("Secondaire - Weekend:"), 3, 0)
        self.desiderata_secondary_weekend_preview = ColorPreview(
            "desiderata_secondary_weekend", 
            color_system.colors['desiderata']['secondary']['weekend']
        )
        desiderata_grid.addWidget(self.desiderata_secondary_weekend_preview, 3, 1)
        self.desiderata_secondary_weekend_button = QPushButton("Changer...")
        self.desiderata_secondary_weekend_button.clicked.connect(
            lambda: self.pick_advanced_color('desiderata_secondary_weekend')
        )
        self.desiderata_secondary_weekend_button.setEnabled(False)
        desiderata_grid.addWidget(self.desiderata_secondary_weekend_button, 3, 2)
        
        advanced_layout.addWidget(desiderata_group)
        
        # Groupe des couleurs de types de postes
        post_types_group = QGroupBox("Couleurs des types de postes")
        post_types_grid = QGridLayout(post_types_group)
        
        # Type Consultation
        post_types_grid.addWidget(QLabel("Consultation:"), 0, 0)
        self.post_type_consultation_preview = ColorPreview(
            "post_type_consultation", 
            color_system.colors['post_types']['consultation']
        )
        post_types_grid.addWidget(self.post_type_consultation_preview, 0, 1)
        self.post_type_consultation_button = QPushButton("Changer...")
        self.post_type_consultation_button.clicked.connect(
            lambda: self.pick_advanced_color('post_type_consultation')
        )
        self.post_type_consultation_button.setEnabled(False)
        post_types_grid.addWidget(self.post_type_consultation_button, 0, 2)
        
        # Type Visite
        post_types_grid.addWidget(QLabel("Visite:"), 1, 0)
        self.post_type_visite_preview = ColorPreview(
            "post_type_visite", 
            color_system.colors['post_types']['visite']
        )
        post_types_grid.addWidget(self.post_type_visite_preview, 1, 1)
        self.post_type_visite_button = QPushButton("Changer...")
        self.post_type_visite_button.clicked.connect(
            lambda: self.pick_advanced_color('post_type_visite')
        )
        self.post_type_visite_button.setEnabled(False)
        post_types_grid.addWidget(self.post_type_visite_button, 1, 2)
        
        # Type Garde
        post_types_grid.addWidget(QLabel("Garde:"), 2, 0)
        self.post_type_garde_preview = ColorPreview(
            "post_type_garde", 
            color_system.colors['post_types']['garde']
        )
        post_types_grid.addWidget(self.post_type_garde_preview, 2, 1)
        self.post_type_garde_button = QPushButton("Changer...")
        self.post_type_garde_button.clicked.connect(
            lambda: self.pick_advanced_color('post_type_garde')
        )
        self.post_type_garde_button.setEnabled(False)
        post_types_grid.addWidget(self.post_type_garde_button, 2, 2)
        
        advanced_layout.addWidget(post_types_group)
        
        # Groupe des couleurs de statistiques
        stats_group = QGroupBox("Couleurs des statistiques")
        stats_grid = QGridLayout(stats_group)
        
        # Couleur pour les valeurs sous le minimum
        stats_grid.addWidget(QLabel("Valeurs sous le minimum:"), 0, 0)
        self.stats_under_min_preview = ColorPreview("stats_under_min", QColor('#28a745'))
        stats_grid.addWidget(self.stats_under_min_preview, 0, 1)
        self.stats_under_min_button = QPushButton("Changer...")
        self.stats_under_min_button.clicked.connect(lambda: self.pick_advanced_color('stats_under_min'))
        self.stats_under_min_button.setEnabled(False)
        stats_grid.addWidget(self.stats_under_min_button, 0, 2)
        
        # Couleur pour les valeurs au-dessus du maximum
        stats_grid.addWidget(QLabel("Valeurs au-dessus du maximum:"), 2, 0)
        self.stats_over_max_preview = ColorPreview("stats_over_max", QColor('#dc3545'))
        stats_grid.addWidget(self.stats_over_max_preview, 2, 1)
        self.stats_over_max_button = QPushButton("Changer...")
        self.stats_over_max_button.clicked.connect(lambda: self.pick_advanced_color('stats_over_max'))
        self.stats_over_max_button.setEnabled(False)
        stats_grid.addWidget(self.stats_over_max_button, 2, 2)
        
        advanced_layout.addWidget(stats_group)
        
        # Bouton de réinitialisation des couleurs avancées
        reset_advanced_button = QPushButton("Réinitialiser les couleurs avancées")
        reset_advanced_button.clicked.connect(self.reset_advanced_colors)
        advanced_layout.addWidget(reset_advanced_button)
        
        # Ajouter un espaceur pour éviter que les widgets ne soient étirés
        advanced_layout.addStretch()
        
        # Configurer le scroll area
        scroll_area.setWidget(advanced_content)
        
        # Layout principal de l'onglet avancé
        advanced_tab_layout = QVBoxLayout(advanced_tab)
        advanced_tab_layout.addWidget(scroll_area)
        
        # Ajouter les onglets
        self.tab_widget.addTab(ui_tab, "Interface")
        self.tab_widget.addTab(tables_tab, "Tableaux")
        self.tab_widget.addTab(colors_tab, "Couleurs principales")
        self.tab_widget.addTab(advanced_tab, "Couleurs avancées")
        
        main_layout.addWidget(self.tab_widget)
        
        # Boutons OK/Annuler
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Reset)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset_settings)
        
        main_layout.addWidget(button_box)
        
    def load_current_settings(self):
        """Charge les paramètres actuels dans l'interface"""
        # Interface générale
        ui_settings = self.current_settings.get('ui', {})
        
        saturation = ui_settings.get('saturation_factor', 1.0) * 100
        self.saturation_slider.setValue(int(saturation))
        self.saturation_value.setText(f"{ui_settings.get('saturation_factor', 1.0):.2f}")
        
        brightness = ui_settings.get('brightness_factor', 1.0) * 100
        self.brightness_slider.setValue(int(brightness))
        self.brightness_value.setText(f"{ui_settings.get('brightness_factor', 1.0):.2f}")
        
        contrast = ui_settings.get('contrast_factor', 1.0) * 100
        self.contrast_slider.setValue(int(contrast))
        self.contrast_value.setText(f"{ui_settings.get('contrast_factor', 1.0):.2f}")
        
        font_size = ui_settings.get('font_size_factor', 1.0) * 100
        self.font_size_slider.setValue(int(font_size))
        self.font_size_value.setText(f"{ui_settings.get('font_size_factor', 1.0):.2f}")
        
        # Tableaux
        table_settings = self.current_settings.get('tables', {})
        
        table_font_size = table_settings.get('font_size_factor', 1.0) * 100
        self.table_font_size_slider.setValue(int(table_font_size))
        self.table_font_size_value.setText(f"{table_settings.get('font_size_factor', 1.0):.2f}")
        
        row_height = table_settings.get('row_height_factor', 1.0) * 100
        self.row_height_slider.setValue(int(row_height))
        self.row_height_value.setText(f"{table_settings.get('row_height_factor', 1.0):.2f}")
        
        column_width = table_settings.get('column_width_factor', 1.0) * 100
        self.column_width_slider.setValue(int(column_width))
        self.column_width_value.setText(f"{table_settings.get('column_width_factor', 1.0):.2f}")
        
        # Couleurs personnalisées
        color_settings = self.current_settings.get('custom_colors', {})
        
        enabled = color_settings.get('enabled', False)
        self.enable_custom_colors.setChecked(enabled)
        self.on_custom_colors_toggled(enabled)
        
        # Mettre à jour les aperçus de couleur
        for color_name in ['primary', 'secondary', 'weekend', 'weekday']:
            color_hex = color_settings.get(color_name, '')
            if color_hex:
                preview = getattr(self, f"{color_name}_color_preview")
                preview.update_color(QColor(color_hex))
        
        # Couleurs avancées
        advanced_settings = self.current_settings.get('advanced_colors', {})
        
        advanced_enabled = advanced_settings.get('enabled', False)
        self.enable_advanced_colors.setChecked(advanced_enabled)
        self.on_advanced_colors_toggled(advanced_enabled)
        
        # Couleurs de désidératas
        for color_name in ['desiderata_primary_normal', 'desiderata_primary_weekend',
                          'desiderata_secondary_normal', 'desiderata_secondary_weekend']:
            color_hex = advanced_settings.get(color_name, '')
            if color_hex:
                preview = getattr(self, f"{color_name}_preview")
                preview.update_color(QColor(color_hex))
        
        # Couleurs de types de postes
        for color_name in ['post_type_consultation', 'post_type_visite', 'post_type_garde']:
            color_hex = advanced_settings.get(color_name, '')
            if color_hex:
                preview = getattr(self, f"{color_name}_preview")
                preview.update_color(QColor(color_hex))
        
        # Couleurs de statistiques
        for color_name in ['stats_under_min', 'stats_over_max']:
            color_hex = advanced_settings.get(color_name, '')
            if color_hex:
                preview = getattr(self, f"{color_name}_preview")
                preview.update_color(QColor(color_hex))
        
    def on_setting_changed(self):
        """Gérer le changement des paramètres"""
        # Mettre à jour les étiquettes
        self.saturation_value.setText(f"{self.saturation_slider.value() / 100:.2f}")
        self.brightness_value.setText(f"{self.brightness_slider.value() / 100:.2f}")
        self.contrast_value.setText(f"{self.contrast_slider.value() / 100:.2f}")
        self.font_size_value.setText(f"{self.font_size_slider.value() / 100:.2f}")
        self.table_font_size_value.setText(f"{self.table_font_size_slider.value() / 100:.2f}")
        self.row_height_value.setText(f"{self.row_height_slider.value() / 100:.2f}")
        self.column_width_value.setText(f"{self.column_width_slider.value() / 100:.2f}")
        
        self.modified = True
        
        # Appliquer immédiatement les changements pour une prévisualisation en temps réel
        self.apply_settings(preview=True)
    
    def on_custom_colors_toggled(self, state):
        """Activer/désactiver les contrôles de couleurs personnalisées"""
        enabled = bool(state)
        self.primary_color_button.setEnabled(enabled)
        self.secondary_color_button.setEnabled(enabled)
        self.weekend_color_button.setEnabled(enabled)
        self.weekday_color_button.setEnabled(enabled)
        
        self.modified = True
        
        # Appliquer immédiatement les changements
        self.apply_settings(preview=True)
    
    def on_advanced_colors_toggled(self, state):
        """Activer/désactiver les contrôles de couleurs avancées"""
        enabled = bool(state)
        
        # Activer/désactiver les boutons de désidératas
        self.desiderata_primary_normal_button.setEnabled(enabled)
        self.desiderata_primary_weekend_button.setEnabled(enabled)
        self.desiderata_secondary_normal_button.setEnabled(enabled)
        self.desiderata_secondary_weekend_button.setEnabled(enabled)
        
        # Activer/désactiver les boutons de types de postes
        self.post_type_consultation_button.setEnabled(enabled)
        self.post_type_visite_button.setEnabled(enabled)
        self.post_type_garde_button.setEnabled(enabled)
        
        # Activer/désactiver les boutons de statistiques
        self.stats_under_min_button.setEnabled(enabled)
        self.stats_over_max_button.setEnabled(enabled)
        
        self.modified = True
        
        # Appliquer immédiatement les changements
        self.apply_settings(preview=True)
    
    def pick_color(self, color_name):
        """Ouvre le sélecteur de couleur"""
        preview = getattr(self, f"{color_name}_color_preview")
        current_color = preview.color
        
        new_color = QColorDialog.getColor(current_color, self, f"Choisir la couleur {color_name}")
        if new_color.isValid():
            preview.update_color(new_color)
            self.modified = True
            
            # Mettre à jour immédiatement les paramètres de couleur
            color_settings = self.current_settings.get('custom_colors', {}).copy()
            color_settings['enabled'] = self.enable_custom_colors.isChecked()
            color_settings[color_name] = new_color.name()
            
            # Mettre à jour les paramètres
            self.settings_manager.set_setting('custom_colors', color_name, new_color.name())
            
            # Appliquer immédiatement les changements
            self.apply_settings()
    
    def reset_colors(self):
        """Réinitialise les couleurs personnalisées"""
        # Utiliser la méthode reset_colors de color_system pour réinitialiser toutes les couleurs
        color_system.reset_colors()
        
        # Mettre à jour les aperçus de couleur avec les couleurs réinitialisées
        self.primary_color_preview.update_color(color_system.get_color('primary'))
        self.secondary_color_preview.update_color(color_system.get_color('secondary'))
        self.weekend_color_preview.update_color(color_system.get_color('weekend'))
        self.weekday_color_preview.update_color(color_system.get_color('weekday'))
        
        # Réinitialiser les paramètres de couleur dans les settings
        color_settings = self.current_settings.get('custom_colors', {}).copy()
        color_settings['enabled'] = False  # Désactiver les couleurs personnalisées
        self.enable_custom_colors.setChecked(False)
        
        # Mettre à jour les boutons
        self.primary_color_button.setEnabled(False)
        self.secondary_color_button.setEnabled(False)
        self.weekend_color_button.setEnabled(False)
        self.weekday_color_button.setEnabled(False)
        
        # Mettre à jour les paramètres
        self.settings_manager.set_setting('custom_colors', 'enabled', False)
        for color_name in ['primary', 'secondary', 'weekend', 'weekday']:
            color_hex = color_system.get_color(color_name).name()
            self.settings_manager.set_setting('custom_colors', color_name, color_hex)
        
        self.modified = True
        
        # Appliquer immédiatement les changements
        self.apply_settings()
    
    def reset_settings(self):
        """Réinitialise tous les paramètres aux valeurs par défaut"""
        reply = QMessageBox.question(self, "Réinitialiser les paramètres",
                                    "Êtes-vous sûr de vouloir réinitialiser tous les paramètres ?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # Réinitialiser les paramètres dans le gestionnaire
            self.settings_manager.reset_settings()
            
            # Réinitialiser les paramètres dans l'interface
            self.current_settings = self.settings_manager.get_all_settings()
            
            # Bloquer temporairement les signaux pour éviter des mises à jour multiples
            old_state = self.blockSignals(True)
            
            # Charger les paramètres dans l'interface
            self.load_current_settings()
            
            # Réactiver les signaux
            self.blockSignals(old_state)
            
            # Marquer comme non modifié
            self.modified = False
            
            # Appliquer immédiatement les changements
            self.apply_settings(preview=True)
            
            # Afficher une confirmation
            QMessageBox.information(self, "Paramètres réinitialisés", 
                                "Tous les paramètres ont été réinitialisés avec succès.")
    
    def collect_settings(self):
        """Collecte les paramètres depuis l'interface"""
        settings = self.current_settings.copy()
        
        # Interface générale
        settings['ui'] = {
            'saturation_factor': self.saturation_slider.value() / 100,
            'brightness_factor': self.brightness_slider.value() / 100,
            'contrast_factor': self.contrast_slider.value() / 100,
            'font_size_factor': self.font_size_slider.value() / 100
        }
        
        # Tableaux
        settings['tables'] = {
            'font_size_factor': self.table_font_size_slider.value() / 100,
            'row_height_factor': self.row_height_slider.value() / 100,
            'column_width_factor': self.column_width_slider.value() / 100
        }
        
        # Couleurs personnalisées
        settings['custom_colors'] = {
            'enabled': self.enable_custom_colors.isChecked(),
            'primary': self.primary_color_preview.color.name(),
            'secondary': self.secondary_color_preview.color.name(),
            'weekend': self.weekend_color_preview.color.name(),
            'weekday': self.weekday_color_preview.color.name()
        }
        
        # Couleurs avancées
        advanced_settings = settings.get('advanced_colors', {})
        advanced_settings['enabled'] = self.enable_advanced_colors.isChecked()
        
        # Couleurs de désidératas
        for color_name in ['desiderata_primary_normal', 'desiderata_primary_weekend',
                        'desiderata_secondary_normal', 'desiderata_secondary_weekend']:
            preview = getattr(self, f"{color_name}_preview")
            advanced_settings[color_name] = preview.color.name()
        
        # Couleurs de types de postes
        for color_name in ['post_type_consultation', 'post_type_visite', 'post_type_garde']:
            preview = getattr(self, f"{color_name}_preview")
            advanced_settings[color_name] = preview.color.name()
        
        # Couleurs de statistiques
        for color_name in ['stats_under_min', 'stats_over_max']:
            preview = getattr(self, f"{color_name}_preview")
            advanced_settings[color_name] = preview.color.name()
        
        settings['advanced_colors'] = advanced_settings
        
        return settings
    
    def apply_settings(self, preview=False):
        """
        Applique les paramètres sans fermer le dialogue
        
        Args:
            preview (bool): Si True, n'affiche pas de message de confirmation
        """
        if not self.modified and not preview:
            return
            
        settings = self.collect_settings()
        
        # Mettre à jour les paramètres
        for category, values in settings.items():
            for key, value in values.items():
                self.settings_manager.set_setting(category, key, value)
        
        if not preview:
            self.modified = False
            # Afficher un message de confirmation seulement pour les applications finales
            QMessageBox.information(self, "Paramètres appliqués", 
                                "Les paramètres ont été appliqués avec succès.")
        
        self.settings_applied.emit()
    
    def accept(self):
        """Applique les paramètres et ferme le dialogue"""
        if self.modified:
            self.apply_settings()
        super().accept()
        
    def pick_advanced_color(self, color_name):
        """Ouvre le sélecteur de couleur pour les couleurs avancées"""
        preview = getattr(self, f"{color_name}_preview")
        current_color = preview.color
        
        # Déterminer un titre approprié pour la boîte de dialogue
        title_map = {
            'desiderata_primary_normal': 'Désidérata primaire (jour normal)',
            'desiderata_primary_weekend': 'Désidérata primaire (weekend)',
            'desiderata_secondary_normal': 'Désidérata secondaire (jour normal)',
            'desiderata_secondary_weekend': 'Désidérata secondaire (weekend)',
            'post_type_consultation': 'Type de poste: Consultation',
            'post_type_visite': 'Type de poste: Visite',
            'post_type_garde': 'Type de poste: Garde',
            'stats_under_min': 'Statistique: Valeurs sous le minimum',
            'stats_over_max': 'Statistique: Valeurs au-dessus du maximum'
        }
        dialog_title = f"Choisir la couleur: {title_map.get(color_name, color_name)}"
        
        new_color = QColorDialog.getColor(current_color, self, dialog_title)
        if new_color.isValid():
            preview.update_color(new_color)
            self.modified = True
            
            # Mettre à jour immédiatement les paramètres de couleur avancée
            advanced_settings = self.current_settings.get('advanced_colors', {}).copy()
            advanced_settings['enabled'] = self.enable_advanced_colors.isChecked()
            advanced_settings[color_name] = new_color.name()
            
            # Mettre à jour les paramètres
            self.settings_manager.set_setting('advanced_colors', color_name, new_color.name())
            
            # Appliquer immédiatement les changements
            self.apply_settings(preview=True)

    def reset_advanced_colors(self):
        """Réinitialise les couleurs avancées"""
        # Demander confirmation
        reply = QMessageBox.question(
            self, 
            "Réinitialiser les couleurs avancées", 
            "Êtes-vous sûr de vouloir réinitialiser toutes les couleurs avancées aux valeurs par défaut ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Récupérer les couleurs par défaut du système
        default_colors = {
            # Désidératas
            'desiderata_primary_normal': color_system.colors['desiderata']['primary']['normal'],
            'desiderata_primary_weekend': color_system.colors['desiderata']['primary']['weekend'],
            'desiderata_secondary_normal': color_system.colors['desiderata']['secondary']['normal'],
            'desiderata_secondary_weekend': color_system.colors['desiderata']['secondary']['weekend'],
            
            # Types de postes
            'post_type_consultation': color_system.colors['post_types']['consultation'],
            'post_type_visite': color_system.colors['post_types']['visite'],
            'post_type_garde': color_system.colors['post_types']['garde'],
            
            # Statistiques
            'stats_under_min': QColor('#28a745'),
            'stats_over_max': QColor('#dc3545')
        }
        
        # Mettre à jour les aperçus de couleur
        for color_name, color in default_colors.items():
            preview = getattr(self, f"{color_name}_preview")
            preview.update_color(color)
        
        # Réinitialiser les paramètres
        advanced_settings = self.current_settings.get('advanced_colors', {}).copy()
        advanced_settings['enabled'] = False
        self.enable_advanced_colors.setChecked(False)
        
        # Désactiver les boutons
        for color_name in default_colors:
            button = getattr(self, f"{color_name}_button")
            button.setEnabled(False)
        
        # Mettre à jour les paramètres
        self.settings_manager.set_setting('advanced_colors', 'enabled', False)
        for color_name, color in default_colors.items():
            self.settings_manager.set_setting('advanced_colors', color_name, color.name())
        
        self.modified = True
        
        # Appliquer immédiatement les changements
        self.apply_settings(preview=True)
    
    
    
    def reject(self):
        """Ferme le dialogue sans appliquer les modifications en cours"""
        if self.modified:
            reply = QMessageBox.question(
                self,
                "Modifications non sauvegardées",
                "Des modifications n'ont pas été sauvegardées. Voulez-vous vraiment quitter ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
                
            # Restaurer les paramètres originaux avant de quitter
            original_settings = self.settings_manager.get_all_settings()
            for category, values in original_settings.items():
                for key, value in values.items():
                    self.settings_manager.set_setting(category, key, value)
            
            # Émettre le signal pour forcer une mise à jour de l'interface
            self.settings_applied.emit()
            
        super().reject()
