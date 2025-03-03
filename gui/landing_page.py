# © 2024 HILAL Arkane. Tous droits réservés.
# gui/landing_page.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QGridLayout, QSpacerItem, QSizePolicy, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QPauseAnimation
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QLinearGradient, QPainter, QPalette, QBrush
from .components.card_button import CardButton
from .styles import StyleConstants, color_system, GLOBAL_STYLE
from core.utils import resource_path

class LandingPage(QMainWindow):
    """
    Page d'accueil avec cartes interactives pour accéder aux différentes fonctionnalités.
    Cette page s'affiche après l'écran de démarrage et avant l'interface principale.
    """
    # Signal émis lorsqu'une carte est cliquée, avec l'index de l'onglet à ouvrir
    navigate_to_tab = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MedHora - Planification médicale")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(GLOBAL_STYLE)
        
        # Définition des cartes à afficher (titre, icône, description, index d'onglet, couleur)
        self.cards_data = [
            ("Planning", "icons/planning.png", "Générer le planning général", 3, "#E3F2FD"),
            ("Personnel", "icons/personnel.png", "Gérez les médecins et les postes", 1, "#E8F5E9"),
            ("Desiderata", "icons/desiderata.png", "Gérez les préférences des médecins", 2, "#FFF8E1"),
            ("Planning Médecin", "icons/doctor_planning.png", "Consultez le planning par médecin", 4, "#F3E5F5"),
            ("Statistiques", "icons/statistics.png", "Analysez la répartition des postes", 5, "#E1F5FE"),
            ("Comparaison", "icons/comparaison.png", "Comparez différentes versions de planning", 6, "#E0F2F1"),
            ("Exporter", "icons/export.png", "Exportez et partagez les plannings", 7, "#F1F8E9")
        ]
        
        # Création d'un arrière-plan avec dégradé subtil
        self.setup_background()
        
        # Initialisation de l'interface utilisateur
        self.init_ui()
    
    def setup_background(self):
        """Configure l'arrière-plan avec un dégradé subtil"""
        # Créer un widget de fond personnalisé avec dégradé
        self.bg_widget = QWidget(self)
        self.bg_widget.setGeometry(0, 0, self.width(), self.height())
        self.bg_widget.setAutoFillBackground(True)
        
        # Définir le dégradé de couleur comme fond
        palette = self.bg_widget.palette()
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(235, 242, 250))  # Couleur de base légèrement plus claire
        gradient.setColorAt(1, QColor(218, 226, 240))  # Couleur légèrement plus foncée en bas
        palette.setBrush(QPalette.ColorRole.Window, QBrush(gradient))
        self.bg_widget.setPalette(palette)
        
        # S'assurer que le widget de fond reste derrière tous les autres widgets
        self.bg_widget.lower()
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        # Widget central
        central_widget = QWidget()
        central_widget.setAutoFillBackground(False)
        central_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(
            StyleConstants.SPACING['xl'],
            StyleConstants.SPACING['xl'],
            StyleConstants.SPACING['xl'],
            StyleConstants.SPACING['xl']
        )
        main_layout.setSpacing(StyleConstants.SPACING['xl'])
        
        # En-tête avec titre
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.setSpacing(10)
        
        # Titre principal
        title_label = QLabel("MedHora")
        title_label.setObjectName("title_label")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Arial", 48, QFont.Weight.Bold)
        title_label.setFont(title_font)
        
        # Style du titre avec QGraphicsDropShadowEffect au lieu de text-shadow
        title_shadow = QGraphicsDropShadowEffect()
        title_shadow.setBlurRadius(4)
        title_shadow.setColor(QColor(0, 0, 0, 50))  # 20% d'opacité
        title_shadow.setOffset(2, 2)
        title_label.setGraphicsEffect(title_shadow)
        
        title_label.setStyleSheet(f"""
            color: {color_system.colors['primary'].name()};
            letter-spacing: 4px;
            margin-top: 20px;
            margin-bottom: 20px;
        """)
        header_layout.addWidget(title_label)
        
        # Sous-titre
        subtitle_label = QLabel("Planification médicale simplifiée")
        subtitle_label.setObjectName("subtitle_label")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont("Arial", 20, QFont.Weight.Normal)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet(f"""
            color: {color_system.colors['text']['secondary'].name()};
            letter-spacing: 1px;
            margin-top: 10px;
            margin-bottom: 20px;
        """)
        header_layout.addWidget(subtitle_label)
        
        # Ligne de séparation
        separator = QWidget()
        separator.setObjectName("separator")
        separator.setFixedHeight(2)
        separator.setMinimumWidth(100)
        separator.setMaximumWidth(200)
        separator.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        separator.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 transparent,
                stop:0.4 {color_system.colors['primary'].name()},
                stop:0.6 {color_system.colors['primary'].name()},
                stop:1 transparent
            );
            margin-top: 10px;
            margin-bottom: 10px;
        """)
        
        # Ajouter l'en-tête au layout principal
        main_layout.addLayout(header_layout)
        
        # Conteneur centré pour le séparateur
        separator_layout = QHBoxLayout()
        separator_layout.addStretch()
        separator_layout.addWidget(separator)
        separator_layout.addStretch()
        main_layout.addLayout(separator_layout)
        
        # Espacement avant les cartes
        main_layout.addSpacing(StyleConstants.SPACING['md'])
        
        # Conteneur pour les cartes
        self.cards_container = QWidget()
        self.cards_container.setObjectName("cards_container")
        self.cards_container.setStyleSheet("background-color: transparent;")
        
        # Créer la grille de cartes
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(StyleConstants.SPACING['xl'])
        self.cards_grid.setContentsMargins(
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md'],
            StyleConstants.SPACING['md']
        )
        
        # Créer et ajouter les cartes à la grille
        self.create_card_buttons()
        
        # Centrer la grille de cartes
        center_layout = QHBoxLayout()
        center_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        center_layout.addWidget(self.cards_container)
        center_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        main_layout.addLayout(center_layout)
        
        # Ajouter un espaceur vertical en bas pour pousser le contenu vers le haut
        main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # Pied de page
        footer_label = QLabel("© 2024 HILAL Arkane. Tous droits réservés.")
        footer_label.setObjectName("footer_label")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet(f"""
            color: {color_system.colors['text']['secondary'].name()};
            font-size: {int(StyleConstants.FONT['size']['sm'][:-2]) - 1}px;
        """)
        main_layout.addWidget(footer_label)
    
    def create_card_buttons(self):
        """Crée les boutons-cartes et les ajoute à la grille"""
        # Déterminer le nombre de colonnes en fonction de la largeur
        width = self.width()
        if width < 800:
            max_cols = 2
        elif width < 1100:
            max_cols = 3
        else:
            max_cols = 4
            
        # Créer les cartes
        self.cards = []
        row, col = 0, 0
        
        # Supprimer d'abord tous les widgets existants de la grille
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Créer et ajouter les nouvelles cartes
        for title, icon_path, description, tab_index, bg_color in self.cards_data:
            # Créer un bouton-carte
            card = CardButton(title, resource_path(icon_path), description, bg_color=bg_color)
            
            # Stocker la référence à l'index d'onglet dans le bouton
            card.setProperty("tab_index", tab_index)
            
            # Connecter le signal clicked
            card.clicked.connect(self.on_card_clicked)
            
            # Ajouter à la liste et à la grille
            self.cards.append(card)
            self.cards_grid.addWidget(card, row, col)
            
            # Passer à la colonne suivante ou à la ligne suivante
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def on_card_clicked(self):
        """Gère le clic sur une carte"""
        # Récupérer l'index d'onglet stocké dans la propriété du bouton
        button = self.sender()
        if button:
            tab_index = button.property("tab_index")
            if tab_index is not None:
                self.navigate_to_tab.emit(tab_index)
    
    def resizeEvent(self, event):
        """Redimensionne l'arrière-plan et réorganise les cartes"""
        # Redimensionner l'arrière-plan
        self.bg_widget.setGeometry(0, 0, self.width(), self.height())
        
        # Recréer les cartes avec une nouvelle disposition
        self.create_card_buttons()
        
        super().resizeEvent(event)
    
    def showEvent(self, event):
        """Géré lorsque la fenêtre est affichée"""
        super().showEvent(event)
        
        # Appliquer les animations après l'affichage initial
        self.animate_elements()
    
    def animate_elements(self):
        """Anime les éléments de la page avec un effet de fondu enchaîné"""
        # Créer un groupe d'animations séquentielles
        animation_group = QSequentialAnimationGroup(self)
        
        # Animation du titre
        title_label = self.findChild(QLabel, "title_label")
        if title_label:
            title_label.setGraphicsEffect(None)  # Temporairement retirer l'effet d'ombre
            title_label.setStyleSheet(title_label.styleSheet() + "opacity: 0;")
            title_anim = QPropertyAnimation(title_label, b"windowOpacity")
            title_anim.setDuration(500)
            title_anim.setStartValue(0.0)
            title_anim.setEndValue(1.0)
            title_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation_group.addAnimation(title_anim)
        
        # Animation du sous-titre
        subtitle_label = self.findChild(QLabel, "subtitle_label")
        if subtitle_label:
            subtitle_label.setStyleSheet(subtitle_label.styleSheet() + "opacity: 0;")
            subtitle_anim = QPropertyAnimation(subtitle_label, b"windowOpacity")
            subtitle_anim.setDuration(500)
            subtitle_anim.setStartValue(0.0)
            subtitle_anim.setEndValue(1.0)
            subtitle_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation_group.addAnimation(subtitle_anim)
        
        # Animation du séparateur
        separator = self.findChild(QWidget, "separator")
        if separator:
            separator.setStyleSheet(separator.styleSheet() + "opacity: 0;")
            separator_anim = QPropertyAnimation(separator, b"windowOpacity")
            separator_anim.setDuration(500)
            separator_anim.setStartValue(0.0)
            separator_anim.setEndValue(1.0)
            separator_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation_group.addAnimation(separator_anim)
        
        # Pause avant l'animation des cartes
        animation_group.addAnimation(QPauseAnimation(100))
        
        # Animation des cartes
        for i, card in enumerate(self.cards):
            # Rendre la carte initialement transparente
            card.setWindowOpacity(0.0)
            
            # Créer l'animation
            card_anim = QPropertyAnimation(card, b"windowOpacity")
            card_anim.setDuration(300)
            card_anim.setStartValue(0.0)
            card_anim.setEndValue(1.0)
            card_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            
            # Ajouter une pause entre les cartes
            if i > 0:
                animation_group.addAnimation(QPauseAnimation(50))
                
            animation_group.addAnimation(card_anim)
        
        # Animation du pied de page
        footer_label = self.findChild(QLabel, "footer_label")
        if footer_label:
            footer_label.setStyleSheet(footer_label.styleSheet() + "opacity: 0;")
            footer_anim = QPropertyAnimation(footer_label, b"windowOpacity")
            footer_anim.setDuration(500)
            footer_anim.setStartValue(0.0)
            footer_anim.setEndValue(1.0)
            footer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation_group.addAnimation(footer_anim)
        
        # Remettre l'effet d'ombre au titre après l'animation
        def on_animations_finished():
            if title_label:
                title_shadow = QGraphicsDropShadowEffect()
                title_shadow.setBlurRadius(4)
                title_shadow.setColor(QColor(0, 0, 0, 50))
                title_shadow.setOffset(2, 2)
                title_label.setGraphicsEffect(title_shadow)
        
        animation_group.finished.connect(on_animations_finished)
        
        # Démarrer les animations
        animation_group.start()
