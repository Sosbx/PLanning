# © 2024 HILAL Arkane. Tous droits réservés.
# gui/components/card_button.py

from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint
from PyQt6.QtGui import QFont, QIcon, QColor, QPixmap, QLinearGradient, QPainter, QBrush
from ..styles import PlatformHelper, StyleConstants

class CardButton(QPushButton):
    """
    Widget de bouton stylisé comme une carte avec icône et description.
    Version améliorée avec compatibilité multiplateforme.
    """
    
    def __init__(self, title, icon_path, description="", bg_color=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.icon_path = icon_path
        self.description = description
        self.bg_color = bg_color or "#FFFFFF"
        self.hovered = False
        self.pressed = False
        
        # Détecter la plateforme
        self.platform = PlatformHelper.get_platform()
        
        # Couleurs par défaut avec ajustements spécifiques à la plateforme
        primary_color = QColor("#1A5A96")  # Bleu primaire
        border_color = QColor("#CBD5E1")   # Gris clair pour bordures
        text_secondary_color = QColor("#505A64")  # Gris foncé pour texte secondaire
        
        # Appliquer les ajustements de couleur spécifiques à la plateforme
        self.primary_color = PlatformHelper.adjust_color_for_platform(primary_color).name()
        self.border_color = PlatformHelper.adjust_color_for_platform(border_color).name()
        self.text_secondary_color = PlatformHelper.adjust_color_for_platform(text_secondary_color).name()
        
        # Ajuster la couleur de fond si fournie
        if bg_color:
            bg_qcolor = QColor(bg_color)
            adjusted_bg = PlatformHelper.adjust_color_for_platform(bg_qcolor)
            self.bg_color = adjusted_bg.name()
            self.rgb_bg_color = f"rgb({adjusted_bg.red()}, {adjusted_bg.green()}, {adjusted_bg.blue()})"
        else:
            self.bg_color = "#FFFFFF"
            self.rgb_bg_color = "rgb(255, 255, 255)"
        
        # Configuration du bouton
        self.setFixedSize(220, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("card_button")
        
        # Création du contenu
        self.setup_ui()
        
        # Configuration des effets et animations
        self.setup_effects()
    
    def setup_ui(self):
        """Configure l'interface du bouton avec prise en compte de la plateforme"""
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
        
        # Ajouter le titre (avec adaptation de police pour Windows)
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Arial", 12, QFont.Weight.Bold)
        
        # Adapter la police pour Windows
        if self.platform == 'Windows':
            title_font = PlatformHelper.adjust_font(title_font, 'header_size')
        
        self.title_label.setFont(title_font)
        
        # Utiliser des couleurs RGB explicites sur Windows
        if self.platform == 'Windows':
            primary_color = QColor(self.primary_color)
            self.title_label.setStyleSheet(
                f"color: rgb({primary_color.red()}, {primary_color.green()}, {primary_color.blue()});"
            )
        else:
            self.title_label.setStyleSheet(f"color: {self.primary_color};")
        
        self.layout.addWidget(self.title_label)
        
        # Ajouter la description si fournie (avec adaptation de police pour Windows)
        if self.description:
            self.desc_label = QLabel(self.description)
            self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.desc_label.setWordWrap(True)
            desc_font = QFont("Arial", 10, QFont.Weight.Normal)
            
            # Adapter la police pour Windows
            if self.platform == 'Windows':
                desc_font = PlatformHelper.adjust_font(desc_font, 'base_size')
            
            self.desc_label.setFont(desc_font)
            
            # Utiliser des couleurs RGB explicites sur Windows
            if self.platform == 'Windows':
                text_color = QColor(self.text_secondary_color)
                self.desc_label.setStyleSheet(
                    f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()});"
                )
            else:
                self.desc_label.setStyleSheet(f"color: {self.text_secondary_color};")
            
            self.layout.addWidget(self.desc_label)
        
        # Style initial
        self.update_style()
    
    def setup_effects(self):
        """Configure les effets visuels et animations avec adaptations pour Windows"""
        # Effet d'ombre (réduit sur Windows pour éviter les problèmes de rendu)
        self.shadow = QGraphicsDropShadowEffect(self)
        
        if self.platform == 'Windows':
            self.shadow.setBlurRadius(10)  # Réduit pour Windows
            self.shadow.setColor(QColor(0, 0, 0, 50))  # Moins opaque
            self.shadow.setOffset(0, 3)  # Plus petit offset
        else:
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
        """Met à jour le style du bouton avec compatibilité Windows"""
        border_radius = "10px"
        force_explicit = self.platform == 'Windows'
        
        if self.hovered:
            # Style au survol avec couleurs adaptées à la plateforme
            if force_explicit:
                # Sur Windows, utiliser une couleur solide ou un dégradé avec RGB explicite
                if PlatformHelper.should_use_solid_colors():
                    # Version couleur solide pour Windows
                    bg_color = QColor(self.bg_color)
                    lighter_bg = bg_color.lighter(110)
                    primary_color = QColor(self.primary_color)
                    
                    self.setStyleSheet(f"""
                        #card_button {{
                            background-color: rgb({lighter_bg.red()}, {lighter_bg.green()}, {lighter_bg.blue()});
                            border: 2px solid rgb({primary_color.red()}, {primary_color.green()}, {primary_color.blue()});
                            border-radius: {border_radius};
                            padding: 10px;
                        }}
                    """)
                else:
                    # Version dégradé avec RGB explicite pour Windows
                    bg_color = QColor(self.bg_color)
                    lighter_bg = bg_color.lighter(110)
                    primary_color = QColor(self.primary_color)
                    
                    self.setStyleSheet(f"""
                        #card_button {{
                            background-color: qlineargradient(
                                x1:0, y1:0, x2:0, y2:1,
                                stop:0 rgb({bg_color.red()}, {bg_color.green()}, {bg_color.blue()}), 
                                stop:1 rgb({lighter_bg.red()}, {lighter_bg.green()}, {lighter_bg.blue()})
                            );
                            border: 2px solid rgb({primary_color.red()}, {primary_color.green()}, {primary_color.blue()});
                            border-radius: {border_radius};
                            padding: 10px;
                        }}
                    """)
            else:
                # Version pour macOS et autres plateformes
                gradient_start = self.bg_color
                gradient_end = self._lighten_color(self.bg_color, 0.9)
                
                self.setStyleSheet(f"""
                    #card_button {{
                        background-color: qlineargradient(
                            x1:0, y1:0, x2:0, y2:1,
                            stop:0 {gradient_start}, 
                            stop:1 {gradient_end}
                        );
                        border: 2px solid {self.primary_color};
                        border-radius: {border_radius};
                        padding: 10px;
                    }}
                """)
        else:
            # Style normal avec couleurs adaptées à la plateforme
            if force_explicit:
                # Sur Windows, utiliser des couleurs RGB explicites
                bg_color = QColor(self.bg_color)
                border_color = QColor(self.border_color)
                
                self.setStyleSheet(f"""
                    #card_button {{
                        background-color: rgb({bg_color.red()}, {bg_color.green()}, {bg_color.blue()});
                        border: 1px solid rgb({border_color.red()}, {border_color.green()}, {border_color.blue()});
                        border-radius: {border_radius};
                        padding: 10px;
                    }}
                """)
            else:
                # Version pour macOS et autres plateformes
                self.setStyleSheet(f"""
                    #card_button {{
                        background-color: {self.bg_color};
                        border: 1px solid {self.border_color};
                        border-radius: {border_radius};
                        padding: 10px;
                    }}
                """)
    
    def _lighten_color(self, color, factor=0.7):
        """Éclaircit une couleur hexadécimale"""
        qcolor = QColor(color)
        lighter_color = qcolor.lighter(int(100 + (factor * 100)))
        return lighter_color.name()
    
    def enterEvent(self, event):
        """Gère l'événement d'entrée de la souris avec adaptations par plateforme"""
        self.hovered = True
        
        # Valeurs d'animation adaptées à la plateforme
        start_blur = 10 if self.platform == 'Windows' else 15
        end_blur = 15 if self.platform == 'Windows' else 25
        
        # Animation de l'ombre
        self.shadow_blur_anim.setStartValue(start_blur)
        self.shadow_blur_anim.setEndValue(end_blur)
        
        # Animation du décalage de l'ombre
        start_offset = QPoint(0, 3) if self.platform == 'Windows' else QPoint(0, 4)
        end_offset = QPoint(0, 1) if self.platform == 'Windows' else QPoint(0, 2)
        
        self.shadow_offset_anim.setStartValue(start_offset)
        self.shadow_offset_anim.setEndValue(end_offset)
        
        # Démarrer les animations
        self.hover_animations.start()
        
        # Mettre à jour le style
        self.update_style()
        
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Gère l'événement de sortie de la souris avec adaptations par plateforme"""
        self.hovered = False
        
        # Valeurs d'animation adaptées à la plateforme
        start_blur = 15 if self.platform == 'Windows' else 25
        end_blur = 10 if self.platform == 'Windows' else 15
        
        # Animation de l'ombre
        self.shadow_blur_anim.setStartValue(start_blur)
        self.shadow_blur_anim.setEndValue(end_blur)
        
        # Animation du décalage de l'ombre
        start_offset = QPoint(0, 1) if self.platform == 'Windows' else QPoint(0, 2)
        end_offset = QPoint(0, 3) if self.platform == 'Windows' else QPoint(0, 4)
        
        self.shadow_offset_anim.setStartValue(start_offset)
        self.shadow_offset_anim.setEndValue(end_offset)
        
        # Démarrer les animations
        self.hover_animations.start()
        
        # Mettre à jour le style
        self.update_style()
        
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """
        Personnalise le rendu avec des effets visuels supplémentaires,
        simplifiés pour Windows
        """
        super().paintEvent(event)
        
        # Sur Windows, éviter les effets supplémentaires qui peuvent mal se rendre
        if self.platform != 'Windows' and not self.isDown() and not self.hovered:
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
        """Gère l'événement de clic de souris avec compatibilité Windows"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = True
            
            # Effet visuel de pression
            shadow_radius = 5 if self.platform == 'Windows' else 10
            shadow_offset = 1 if self.platform == 'Windows' else 2
            
            self.shadow.setBlurRadius(shadow_radius)
            self.shadow.setOffset(0, shadow_offset)
            
            # Style de clic avec couleurs adaptées à la plateforme
            if self.platform == 'Windows':
                # Utiliser des couleurs RGB explicites sur Windows
                darker_color = QColor(self.bg_color).darker(110)
                primary_color = QColor(self.primary_color)
                
                self.setStyleSheet(f"""
                    #card_button {{
                        background-color: rgb({darker_color.red()}, {darker_color.green()}, {darker_color.blue()});
                        border: 2px solid rgb({primary_color.red()}, {primary_color.green()}, {primary_color.blue()});
                        border-radius: 10px;
                        padding: 10px;
                    }}
                """)
            else:
                # Version pour macOS et autres plateformes
                darker_color = QColor(self.bg_color).darker(110)
                
                self.setStyleSheet(f"""
                    #card_button {{
                        background-color: {darker_color.name()};
                        border: 2px solid {self.primary_color};
                        border-radius: 10px;
                        padding: 10px;
                    }}
                """)
        
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Gère l'événement de relâchement du clic avec compatibilité Windows"""
        self.pressed = False
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.rect().contains(event.position().toPoint()):
                # Si toujours sur le bouton, revenir au style survol
                shadow_radius = 15 if self.platform == 'Windows' else 25
                shadow_offset = 1 if self.platform == 'Windows' else 2
                
                self.shadow.setBlurRadius(shadow_radius)
                self.shadow.setOffset(0, shadow_offset)
                self.hovered = True
                self.update_style()
            else:
                # Sinon, revenir au style normal
                shadow_radius = 10 if self.platform == 'Windows' else 15
                shadow_offset = 3 if self.platform == 'Windows' else 4
                
                self.shadow.setBlurRadius(shadow_radius)
                self.shadow.setOffset(0, shadow_offset)
                self.hovered = False
                self.update_style()
        
        super().mouseReleaseEvent(event)