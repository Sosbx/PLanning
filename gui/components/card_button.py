# © 2024 HILAL Arkane. Tous droits réservés.
# gui/components/card_button.py

from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint
from PyQt6.QtGui import QFont, QIcon, QColor, QPixmap, QLinearGradient, QPainter, QBrush, QPalette

class CardButton(QPushButton):
    """
    Widget de bouton stylisé comme une carte avec icône et description.
    Version améliorée avec meilleure gestion des couleurs pour Windows.
    """
    
    def __init__(self, title, icon_path, description="", bg_color=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.icon_path = icon_path
        self.description = description
        
        # Utiliser color_system pour obtenir les couleurs standards
        from gui.styles import color_system
        
        # Permettre une couleur personnalisée ou utiliser la couleur par défaut
        if bg_color and bg_color.startswith('#'):
            self.bg_color = bg_color
        else:
            # Utiliser le système de couleurs centralisé
            self.bg_color = color_system.get_hex_color('container', 'background')
        
        # Obtenir les couleurs du système
        self.primary_color = color_system.get_hex_color('primary')
        self.border_color = color_system.get_hex_color('container', 'border')
        self.text_secondary_color = color_system.get_hex_color('text', 'secondary')
        
        self.hovered = False
        
        # Configuration du bouton
        self.setFixedSize(220, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Définir directement la couleur de fond à l'initialisation pour Windows
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.bg_color))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.bg_color))
        self.setPalette(palette)
        
        # Création du contenu
        self.setup_ui()
        
        # Configuration des effets et animations
        self.setup_effects()
    
    def setup_ui(self):
        """Configure l'interface du bouton"""
        # Créer un layout vertical pour organiser le contenu
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(5)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Ajouter l'icône
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QIcon(self.icon_path)
        pixmap = icon.pixmap(64, 64)
        self.icon_label.setPixmap(pixmap)
        self.layout.addWidget(self.icon_label)
        
        # Ajouter le titre
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {self.primary_color};")
        self.layout.addWidget(self.title_label)
        
        # Ajouter la description si fournie
        if self.description:
            self.desc_label = QLabel(self.description)
            self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.desc_label.setWordWrap(True)
            self.desc_label.setFont(QFont("Arial", 10, QFont.Weight.Normal))
            self.desc_label.setStyleSheet(f"color: {self.text_secondary_color};")
            self.layout.addWidget(self.desc_label)
        
        # Appliquer le style initial
        self.update_style()
    
    def setup_effects(self):
        """Configure les effets visuels et animations"""
        # Effet d'ombre
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 60))
        self.shadow.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow)
        
        # Animations au survol
        self.hover_animations = QParallelAnimationGroup(self)
        
        # Animation pour le rayon de flou de l'ombre
        self.shadow_blur_anim = QPropertyAnimation(self.shadow, b"blurRadius")
        self.shadow_blur_anim.setDuration(200)
        self.shadow_blur_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_animations.addAnimation(self.shadow_blur_anim)
        
        # Animation pour le décalage de l'ombre
        self.shadow_offset_anim = QPropertyAnimation(self.shadow, b"offset")
        self.shadow_offset_anim.setDuration(200)
        self.shadow_offset_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_animations.addAnimation(self.shadow_offset_anim)
    
    def update_style(self):
        """
        Met à jour le style du bouton de manière compatible avec Windows et macOS.
        Utilise à la fois styleSheet et QPalette pour une compatibilité maximale.
        """
        border_radius = "10px"
        
        # Assurer que le fond auto-remplissage est activé
        self.setAutoFillBackground(True)
        
        # Obtenir la plateforme
        from gui.styles import PlatformHelper
        platform = PlatformHelper.get_platform()
        
        if self.hovered:
            # Style au survol
            lighter_color = self._lighten_color(self.bg_color, 0.9)
            
            # Utiliser styleSheet pour tous les styles
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {lighter_color};
                    border: 2px solid {self.primary_color};
                    border-radius: {border_radius};
                    padding: 10px;
                }}
            """)
            
            # Appliquer aussi via QPalette pour Windows
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Button, QColor(lighter_color))
            palette.setColor(QPalette.ColorRole.Window, QColor(lighter_color))
            self.setPalette(palette)
            
            # Pour Windows, définir explicitement le fond
            if platform == 'Windows':
                self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        else:
            # Style normal
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.bg_color};
                    border: 1px solid {self.border_color};
                    border-radius: {border_radius};
                    padding: 10px;
                }}
            """)
            
            # Appliquer via QPalette pour Windows
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Button, QColor(self.bg_color))
            palette.setColor(QPalette.ColorRole.Window, QColor(self.bg_color))
            self.setPalette(palette)
            
            # Pour Windows, définir explicitement le fond
            if platform == 'Windows':
                self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    
    def _lighten_color(self, color, factor=0.7):
        """Éclaircit une couleur hexadécimale"""
        qcolor = QColor(color)
        lighter_color = qcolor.lighter(int(100 + (factor * 100)))
        return lighter_color.name()
    
    def enterEvent(self, event):
        """Gère l'événement d'entrée de la souris"""
        self.hovered = True
        
        # Animation de l'ombre
        self.shadow_blur_anim.setStartValue(15)
        self.shadow_blur_anim.setEndValue(25)
        
        # Animation du décalage de l'ombre
        self.shadow_offset_anim.setStartValue(QPoint(0, 4))
        self.shadow_offset_anim.setEndValue(QPoint(0, 2))
        
        # Démarrer les animations
        self.hover_animations.start()
        
        # Mettre à jour le style
        self.update_style()
        
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Gère l'événement de sortie de la souris"""
        self.hovered = False
        
        # Animation de l'ombre
        self.shadow_blur_anim.setStartValue(25)
        self.shadow_blur_anim.setEndValue(15)
        
        # Animation du décalage de l'ombre
        self.shadow_offset_anim.setStartValue(QPoint(0, 2))
        self.shadow_offset_anim.setEndValue(QPoint(0, 4))
        
        # Démarrer les animations
        self.hover_animations.start()
        
        # Mettre à jour le style
        self.update_style()
        
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """Personnalise le rendu avec des effets visuels supplémentaires"""
        super().paintEvent(event)
        
        # Application de l'effet visuel après le rendu de base
        if not self.isDown() and not self.hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Ajouter un léger dégradé en haut pour l'effet 3D
            gradient_height = int(self.height() * 0.4)
            gradient = QLinearGradient(0, 0, 0, gradient_height)
            gradient.setColorAt(0, QColor(255, 255, 255, 80))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, self.width(), gradient_height, 10, 10)
    
    def mousePressEvent(self, event):
        """Gère l'événement de clic de souris"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Effet visuel de pression
            self.shadow.setBlurRadius(10)
            self.shadow.setOffset(0, 2)
            
            # Style de clic
            darker_color = QColor(self.bg_color).darker(110).name()
            
            # Appliquer via styleSheet
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {darker_color};
                    border: 2px solid {self.primary_color};
                    border-radius: 10px;
                    padding: 10px;
                }}
            """)
            
            # Appliquer aussi via QPalette pour Windows
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Button, QColor(darker_color))
            palette.setColor(QPalette.ColorRole.Window, QColor(darker_color))
            self.setPalette(palette)
            
            # Pour Windows, définir explicitement le fond
            from gui.styles import PlatformHelper
            if PlatformHelper.get_platform() == 'Windows':
                self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Gère l'événement de relâchement du clic de souris"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(event.position().toPoint()):
                # Si toujours sur le bouton, revenir au style survol
                self.shadow.setBlurRadius(25)
                self.shadow.setOffset(0, 2)
                self.hovered = True
                self.update_style()
            else:
                # Sinon, revenir au style normal
                self.shadow.setBlurRadius(15)
                self.shadow.setOffset(0, 4)
                self.hovered = False
                self.update_style()
        
        super().mouseReleaseEvent(event)