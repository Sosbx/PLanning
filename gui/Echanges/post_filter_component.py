# © 2024 HILAL Arkane. Tous droits réservés.
# gui/post_filter_component.py

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QScrollArea, 
                             QFrame, QButtonGroup, QToolButton, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor

class PostFilterComponent(QWidget):
    """
    Composant pour filtrer les types de postes dans les plannings.
    Permet de sélectionner/désélectionner visuellement les types de postes à afficher.
    """
    filter_changed = pyqtSignal(list)  # Signal émis lorsque les filtres changent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.post_types = [
            # Postes du matin
            "ML", "MC", "MM", "CM", "HM", "SM", "RM",
            # Postes d'après-midi
            "CA", "HA", "SA", "RA", "AL", "AC", "CT",
            # Postes du soir
            "CS", "HS", "SS", "RS", "NA", "NM", "NC", "NL"
        ]
        self.post_groups = {
            "Matin": ["ML", "MC", "MM", "CM", "HM", "SM", "RM"],
            "Après-midi": ["CA", "HA", "SA", "RA", "AL", "AC", "CT"],
            "Soir/Nuit": ["CS", "HS", "SS", "RS", "NA", "NM", "NC", "NL"]
        }
        self.post_colors = {
            "Matin": "#D8E1ED",      # Bleu clair
            "Après-midi": "#E6D4B8",  # Orange clair
            "Soir/Nuit": "#DFD8ED"    # Violet clair
        }
        
        # État des filtres (True = affiché, False = masqué)
        self.filters = {post_type: True for post_type in self.post_types}
        
        self.init_ui()
    
    def init_ui(self):
        """Initialise l'interface utilisateur du composant de filtrage."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        
        # Créer un widget défilable
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMaximumHeight(80)  # Hauteur maximale pour éviter de prendre trop de place
        
        # Conteneur pour les boutons
        filter_container = QWidget()
        grid_layout = QGridLayout(filter_container)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(2)
        
        # Créer les groupes de boutons
        self.button_groups = {}
        self.group_toggle_buttons = {}
        self.filter_buttons = {}
        
        # Créer un bouton pour tout sélectionner/désélectionner
        select_all_button = QPushButton("Tout")
        select_all_button.setCheckable(True)
        select_all_button.setChecked(True)
        select_all_button.clicked.connect(self.toggle_all_filters)
        select_all_button.setFixedWidth(40)
        select_all_button.setStyleSheet("""
            QPushButton {
                background-color: #B8C7DB;
                border-radius: 3px;
                padding: 2px;
                font-size: 8pt;
            }
            QPushButton:checked {
                background-color: #7691B4;
                color: white;
            }
        """)
        grid_layout.addWidget(select_all_button, 0, 0)
        
        col_offset = 1
        
        # Créer les boutons de groupe et les boutons de filtre
        for group_idx, (group_name, post_types) in enumerate(self.post_groups.items()):
            # Bouton de groupe
            group_button = QPushButton(group_name)
            group_button.setCheckable(True)
            group_button.setChecked(True)
            group_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.post_colors[group_name]};
                    border-radius: 3px;
                    padding: 2px;
                    font-size: 8pt;
                }}
                QPushButton:checked {{
                    background-color: {self.darker_color(self.post_colors[group_name])};
                    color: white;
                }}
            """)
            group_button.clicked.connect(lambda checked, g=group_name: self.toggle_group(g, checked))
            grid_layout.addWidget(group_button, 0, group_idx + col_offset)
            self.group_toggle_buttons[group_name] = group_button
            
            # Boutons pour chaque type de poste dans le groupe
            for i, post_type in enumerate(post_types):
                post_button = QPushButton(post_type)
                post_button.setCheckable(True)
                post_button.setChecked(True)
                post_button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.post_colors[group_name]};
                        border-radius: 3px;
                        padding: 2px;
                        font-size: 8pt;
                    }}
                    QPushButton:checked {{
                        background-color: {self.darker_color(self.post_colors[group_name])};
                        color: white;
                    }}
                """)
                post_button.clicked.connect(lambda checked, pt=post_type: self.toggle_filter(pt, checked))
                grid_layout.addWidget(post_button, 1, i + group_idx + col_offset)
                self.filter_buttons[post_type] = post_button
            
            col_offset += len(post_types) - 1
        
        scroll_area.setWidget(filter_container)
        main_layout.addWidget(scroll_area)
    
    def darker_color(self, hex_color, factor=0.7):
        """Retourne une version plus foncée de la couleur."""
        color = QColor(hex_color)
        darker = color.darker(int(100/factor))
        return darker.name()
    
    def toggle_filter(self, post_type, checked):
        """Active ou désactive l'affichage d'un type de poste spécifique."""
        self.filters[post_type] = checked
        
        # Mettre à jour l'état du bouton de groupe
        for group_name, posts in self.post_groups.items():
            if post_type in posts:
                # Vérifier si tous les posts de ce groupe sont dans le même état
                all_same = all(self.filters[pt] == checked for pt in posts)
                if all_same:
                    self.group_toggle_buttons[group_name].setChecked(checked)
        
        # Émettre le signal de changement
        self.filter_changed.emit(self.get_active_filters())
    
    def toggle_group(self, group_name, checked):
        """Active ou désactive l'affichage de tous les postes d'un groupe."""
        for post_type in self.post_groups[group_name]:
            self.filters[post_type] = checked
            self.filter_buttons[post_type].setChecked(checked)
        
        # Émettre le signal de changement
        self.filter_changed.emit(self.get_active_filters())
    
    def toggle_all_filters(self, checked):
        """Active ou désactive l'affichage de tous les postes."""
        # Mettre à jour tous les filtres
        for post_type in self.post_types:
            self.filters[post_type] = checked
            self.filter_buttons[post_type].setChecked(checked)
        
        # Mettre à jour tous les boutons de groupe
        for group_name in self.post_groups:
            self.group_toggle_buttons[group_name].setChecked(checked)
        
        # Émettre le signal de changement
        self.filter_changed.emit(self.get_active_filters())
    
    def get_active_filters(self):
        """Retourne la liste des types de postes actifs."""
        return [post_type for post_type, active in self.filters.items() if active]