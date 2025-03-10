# © 2024 HILAL Arkane. Tous droits réservés.
# gui/stats_view.py
import sys
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QTabWidget, QPushButton,
                            QMenu, QAbstractItemView)
from PyQt6.QtGui import QBrush, QFont, QColor, QIcon, QAction, QPainter, QPen, QFontMetrics, QRegion
from PyQt6.QtCore import (Qt, QPropertyAnimation, QEasingCurve, QTimer, QSize, QRect,QPoint,
                         pyqtSignal, pyqtSlot)
from gui.styles import color_system, ACTION_BUTTON_STYLE
from core.Constantes.models import ALL_POST_TYPES
from core.Constantes.data_persistence import DataPersistence
from gui.Gestion.post_configuration import PostConfig   
import numpy as np
from datetime import datetime, time, date
from typing import List, Dict, Optional, Tuple, Union
from workalendar.europe import France

# Initialiser le logger
logger = logging.getLogger(__name__)

class CustomHeaderView(QHeaderView):
    """En-tête personnalisé permettant de différencier les clics droits et gauches"""
    rightClicked = pyqtSignal(int)  # Signal pour le clic droit sur un en-tête
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Activer le tri interactif explicitement
        self.setSectionsClickable(True)
        self.setSortIndicatorShown(True)
        
        # Logger pour faciliter le débogage
        self.logger = logging.getLogger(__name__)
        self.logger.debug("CustomHeaderView initialisé avec tri interactif activé")
    
    def mousePressEvent(self, event):
        """Gère les événements de clic sur les en-têtes"""
        index = self.logicalIndexAt(event.pos())
        
        # Clic droit pour expansion
        if event.button() == Qt.MouseButton.RightButton:
            self.logger.debug(f"Clic droit sur la section {index}")
            self.rightClicked.emit(index)
            event.accept()
        # Clic gauche pour tri (comportement standard)
        else:
            self.logger.debug(f"Clic gauche sur la section {index}, transmission à QHeaderView")
            super().mousePressEvent(event)

class StatsView(QWidget):
    def __init__(self, planning=None, doctors=None, cats=None):
        super().__init__()
        self.planning = planning
        self.doctors = doctors
        self.cats = cats
        self.data_persistence = DataPersistence()
        self.custom_posts = {}
        self.custom_posts = self.load_custom_posts()
        
        # Référence au parent pour le détachement
        self.parent_window = None
        
        # Initialisation des attributs pour la gestion de l'expansion
        self.expanded_group = None
        self.component_columns = {}
        
        # Définition des groupes de postes comme attribut de classe
        self.post_groups = {
            'matin': {
                'label': 'Matin',
                'posts': ['MM', 'CM', 'HM', 'SM', 'RM', 'ML', 'MC'],
                'color': QColor('#E3F2FD')  # Bleu clair
            },
            'apresMidi': {
                'label': 'Après-midi',
                'posts': ['CA', 'HA', 'SA', 'RA', 'AL', 'AC'],
                'color': QColor('#FFF3E0')  # Orange clair
            },
            'soirNuit': {
                'label': 'Soir/Nuit',
                'posts': ['CS', 'HS', 'SS', 'RS', 'NL', 'NM', 'NA', 'NC'],
                'color': QColor('#EDE7F6')  # Violet clair
            }
        }

        # Initialize filter_buttons dictionary
        self.filter_buttons = {}
        
        # Ajout des postes personnalisés aux groupes
        for post_name, custom_post in self.custom_posts.items():
            start_hour = custom_post.start_time.hour
            if 7 <= start_hour < 13:
                self.post_groups['matin']['posts'].append(post_name)
            elif 13 <= start_hour < 18:
                self.post_groups['apresMidi']['posts'].append(post_name)
            else:
                self.post_groups['soirNuit']['posts'].append(post_name)
        
        self.current_filter = 'all'  # Pour suivre le filtre actif
        
        # Initialisation des structures pour les groupes
        self.group_details = {
            'NLw': {
                'components': ['NLv', 'NLs', 'NLd'],
                'description': 'Nuits longues weekend'
            },
            'NAMw': {
                'components': ['NAs', 'NAd', 'NMs', 'NMd'],
                'description': 'Nuits courtes et moyennes weekend'
            },
            'VmS': {
                'components': ['ML', 'MC'],
                'description': 'Visites matin samedi'
            },
            'VmD': {
                'components': ['ML', 'MC'],
                'description': 'Visites matin dimanche'
            },
            'VaSD': {
                'components': ['AL', 'AC'],
                'description': 'Visites après-midi weekend'
            },
            'CmS': {
                'components': ['CM', 'HM', 'SM', 'RM'],
                'description': 'Consultations matin samedi'
            },
            'CmD': {
                'components': ['CM', 'HM', 'SM', 'RM'],
                'description': 'Consultations matin dimanche'
            },
            'CaSD': {
                'components': ['CA', 'HA', 'SA', 'RA'],
                'description': 'Consultations après-midi weekend'
            },
            'CsSD': {
                'components': ['CS', 'HS', 'SS', 'RS'],
                'description': 'Consultations soir weekend'
            }
        }
        
        # Variables pour le tri et la mise en surbrillance
        self.highlighted_row = -1
        self.highlighted_col = -1
        self.sort_order = {}  # {table_id: {column: order}}
        
        # Couleurs d'intervalle par défaut
        self.interval_colors = {
            'under_min': QColor(200, 255, 200, 255),  # Vert plus vif (sous le minimum)
            'over_max': QColor(255, 200, 200, 255)    # Rouge plus vif (au-dessus du maximum)
        }
        
        self.init_ui()

    def set_parent_window(self, window):
        """Définit la fenêtre parente pour le détachement"""
        self.parent_window = window

    def on_detach_clicked(self):
        """Gère le détachement des statistiques"""
        if self.parent_window:
            self.parent_window.detach_stats()
        else:
            logging.warning("Parent window not set for detachment")
    
    def initialize_custom_header(self):
        """Configure l'en-tête personnalisé pour la table de groupes détaillés"""
        try:
            # Créer et configurer l'en-tête personnalisé pour le tableau détaillé
            custom_header = CustomHeaderView(Qt.Orientation.Horizontal, self.detailed_stats_table)
            self.detailed_stats_table.setHorizontalHeader(custom_header)
            
            # Activer explicitement le tri
            custom_header.setSortIndicatorShown(True)
            custom_header.setSectionsClickable(True)
            
            # Connecter les signaux avec des logs de débogage
            custom_header.rightClicked.connect(self._handle_header_right_click)
            logger.debug("Signal rightClicked connecté à _handle_header_right_click")
            
            custom_header.sectionClicked.connect(self._handle_header_left_click)
            logger.debug("Signal sectionClicked connecté à _handle_header_left_click")
            
            # Déconnecter l'ancien gestionnaire s'il existe
            try:
                if hasattr(self, '_old_section_clicked_connection'):
                    self.detailed_stats_table.horizontalHeader().sectionClicked.disconnect(self._old_section_clicked_connection)
                    logger.debug("Ancien signal sectionClicked déconnecté")
            except Exception as e:
                logger.debug(f"Pas d'ancien signal à déconnecter: {e}")
            
            logger.debug("En-tête personnalisé configuré avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de l'en-tête personnalisé: {e}")
            import traceback
            logger.error(traceback.format_exc())


    def init_ui(self):
        """Initialise l'interface utilisateur complète avec gestion des erreurs améliorée"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Attribut pour protéger contre les opérations concurrentes
        self._header_click_in_progress = False
        
        # Création des tableaux de statistiques personnalisés
        self.stats_table = CustomTableWidget()
        self.weekend_stats_table = CustomTableWidget()
        self.detailed_stats_table = CustomTableWidget()
        self.weekly_stats_table = CustomTableWidget()
        self.weekday_group_stats_table = CustomTableWidget()
        
        # Configuration des tables pour le tri et la mise en surbrillance
        tables = [self.stats_table, self.weekend_stats_table, self.detailed_stats_table, 
                self.weekly_stats_table, self.weekday_group_stats_table]
        
        for i, table in enumerate(tables):
            try:
                # Pour la table detailed_stats_table, on configurera l'en-tête personnalisé plus tard
                if table != self.detailed_stats_table:
                    table.horizontalHeader().sectionClicked.connect(lambda col, t=table: self.sort_table(t, col))
                table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
                table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
                # Identifiant unique pour chaque table
                table.setProperty("table_id", i)
                self.sort_order[i] = {}
                
                # Ajustement de la hauteur des lignes
                table.verticalHeader().setDefaultSectionSize(28)
                
                # Améliorer l'apparence des en-têtes
                header = table.horizontalHeader()
                header.setMinimumHeight(36)  # Hauteur minimale des en-têtes
                header.setStyleSheet("""
                    QHeaderView::section {
                        background-color: #EDF2F7;
                        color: #2C3E50;
                        padding: 6px 8px;
                        border: 1px solid #CBD5E1;
                        border-top-left-radius: 4px;
                        border-top-right-radius: 4px;
                        font-weight: bold;
                    }
                """)
                
            except Exception as e:
                logger.error(f"Erreur lors de la configuration du tableau {i}: {e}")
        
        # Conteneur des boutons de filtre avec style amélioré
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 10)
        
        # Création des boutons de filtre pour chaque groupe
        self.filter_buttons = {}
        for group_key, group in self.post_groups.items():
            btn = QPushButton(group['label'])
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=group_key: self.apply_filter(k))
            btn.setStyleSheet(ACTION_BUTTON_STYLE)
            filter_layout.addWidget(btn)
            self.filter_buttons[group_key] = btn
        
        # Bouton "Tous" pour le filtre
        all_btn = QPushButton("Tous")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.clicked.connect(lambda: self.apply_filter('all'))
        all_btn.setStyleSheet(ACTION_BUTTON_STYLE)
        filter_layout.addWidget(all_btn)
        self.filter_buttons['all'] = all_btn
        
        main_layout.addWidget(filter_widget)
        
        # Configuration des onglets avec une apparence améliorée
        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CBD5E1;
                background-color: #FFFFFF;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #F5F7FA;
                color: #505A64;
                padding: 8px 16px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 150px;  /* Augmenter la largeur minimale des onglets */
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background-color: #1A5A96;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #D0E2F3;
            }
        """)
        # Configuration des onglets avec une apparence améliorée
        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CBD5E1;
                background-color: #FFFFFF;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #F5F7FA;
                color: #505A64;
                padding: 8px 16px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 150px;  /* Augmenter la largeur minimale des onglets */
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background-color: #1A5A96;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #D0E2F3;
            }
        """)
        
        def setup_table_in_tab(table, title):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(8, 8, 8, 8)  # Ajouter des marges pour plus d'espace
            container_layout.addWidget(table)
            
            # Configuration commune des tableaux
            table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
            table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
            table.horizontalHeader().setFixedHeight(36)  # Augmenter la hauteur de l'en-tête
            table.verticalHeader().setVisible(True)
            
            # Style de la sélection amélioré mais préservant les couleurs de fond
            table.setStyleSheet("""
                QTableView::item:selected {
                    background-color: rgba(26, 90, 150, 0.15);
                    color: #2C3E50;
                }
                QTableView::item:focus {
                    background-color: rgba(26, 90, 150, 0.25);
                    color: #2C3E50;
                }
                QTableView::item:selected:focus {
                    background-color: rgba(26, 90, 150, 0.35);
                    color: #2C3E50;
                }
            """)
            
            # Configuration de la grille
            table.setShowGrid(True)
            table.setGridStyle(Qt.PenStyle.SolidLine)
            table.setAlternatingRowColors(True)
            
            tab_widget.addTab(container, title)
        
        # Configuration des onglets avec leurs tableaux respectifs
        setup_table_in_tab(self.stats_table, "Statistiques générales")
        setup_table_in_tab(self.weekend_stats_table, "Statistiques weekend")
        setup_table_in_tab(self.detailed_stats_table, "Groupes Weekend")
        setup_table_in_tab(self.weekly_stats_table, "Statistiques semaine")
        setup_table_in_tab(self.weekday_group_stats_table, "Groupes semaine")
        
        main_layout.addWidget(tab_widget)
    
        # Connecter le signal de changement d'onglet pour optimiser les colonnes
        tab_widget.currentChanged.connect(lambda: QTimer.singleShot(100, self.optimize_all_tables))
        
        
        # Configuration de la synchronisation du défilement
        self.setup_scroll_sync()
        
        # Initialiser l'en-tête personnalisé pour le tableau détaillé
        self.initialize_custom_header()
        
        # Initialisation des données si disponibles
        if self.planning and self.doctors and self.cats:
            try:
                self.update_stats()
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation des statistiques: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.set_empty_table_message(self.stats_table)
                self.set_empty_table_message(self.detailed_stats_table)
                self.set_empty_table_message(self.weekly_stats_table)
                self.set_empty_table_message(self.weekend_stats_table)
                self.set_empty_table_message(self.weekday_group_stats_table)
        else:
            self.set_empty_table_message(self.stats_table)
            self.set_empty_table_message(self.detailed_stats_table)
            self.set_empty_table_message(self.weekly_stats_table)
            self.set_empty_table_message(self.weekend_stats_table)
            self.set_empty_table_message(self.weekday_group_stats_table)

    def apply_filter(self, group_key):
        """Applique le filtre à tous les tableaux"""
        # Mise à jour des boutons
        self.current_filter = group_key
        for key, btn in self.filter_buttons.items():
            btn.setChecked(key == group_key)
        
        # Application du filtre à chaque tableau
        self._apply_filter_to_table(self.stats_table)
        self._apply_filter_to_table(self.weekend_stats_table)
        self._apply_filter_to_table(self.weekly_stats_table)
        self._apply_filter_to_table(self.detailed_stats_table)
        self._apply_filter_to_table(self.weekday_group_stats_table)
    
    def initialize_table(self, table):
        """Initialise un tableau avec des paramètres optimaux, incluant la fixation de la première colonne"""
        # Configuration de base du tableau
        table.setWordWrap(False)  # Désactiver le retour à la ligne automatique
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setAlternatingRowColors(True)
        
        # Adapter la hauteur des lignes et en-têtes
        table.verticalHeader().setDefaultSectionSize(28)  # Hauteur uniforme des lignes
        table.horizontalHeader().setMinimumHeight(36)     # Hauteur minimale des en-têtes
        
        # Configurer la première colonne (Assigné à) pour qu'elle reste fixe lors du défilement
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnWidth(0, max(150, table.columnWidth(0)))  # Largeur minimale garantie
        
        # Fixation de la première colonne pour qu'elle reste visible lors du défilement horizontal
        table.horizontalHeader().setSectionsMovable(False)  # Empêcher le déplacement des colonnes
        table.setCornerButtonEnabled(False)                # Désactiver le bouton de coin
        
        # Rendre la première colonne (Assigné à) toujours visible lors du défilement
        # En utilisant la fonction interne de Qt
        if hasattr(table, "setFrozenColumns"):
            # Méthode directe si disponible (Qt 6.3+)
            table.setFrozenColumns(1)
        else:
            # Méthode alternative pour les versions antérieures de Qt
            table.horizontalHeader().setFirstSectionMovable(False)
            # Ajouter une sous-classe de QTableView avec scrollé spécifique
            self._configure_frozen_columns_workaround(table)

    def _configure_frozen_columns_workaround(self, table):
        """Configure un tableau pour maintenir la première colonne toujours visible, même avec les versions antérieures de Qt"""
        # Sous-classer dynamiquement le viewport du tableau
        original_viewport = table.viewport()
        
        # Créer une nouvelle classe de viewport qui modifie le comportement de défilement
        class FrozenColumnViewport(type(original_viewport)):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._parent_table = parent
                
            def paintEvent(self, event):
                super().paintEvent(event)
                # Après avoir dessiné le viewport normal, redessiner la première colonne
                self._redraw_frozen_column()
                
            def _redraw_frozen_column(self):
                if not hasattr(self, "_parent_table") or not self._parent_table:
                    return
                    
                painter = QPainter(self)
                table = self._parent_table
                
                # Position horizontale de départ du viewport (pour savoir combien le tableau a défilé)
                h_scroll = table.horizontalScrollBar().value()
                
                # Ne redessiner que si le tableau a été défilé
                if h_scroll > 0:
                    # Récupérer la largeur de la première colonne
                    col_width = table.columnWidth(0)
                    
                    # Zone à redessiner (première colonne)
                    clip_rect = QRect(0, 0, col_width, self.height())
                    
                    # Sauvegarder la position actuelle du viewport
                    painter.save()
                    painter.setClipRect(clip_rect)
                    
                    # Décaler le dessin pour compenser le défilement
                    painter.translate(h_scroll, 0)
                    
                    # Redessiner le tableau dans la zone clippée (première colonne uniquement)
                    table.render(painter, QPoint(0, 0), QRegion(clip_rect))
                    
                    # Restaurer l'état du painter
                    painter.restore()
                    
                    # Tracer une ligne de séparation pour la colonne figée
                    painter.setPen(QPen(QColor("#CBD5E1"), 2))
                    painter.drawLine(col_width, 0, col_width, self.height())
        
        # Remplacer le viewport du tableau par notre version personnalisée
        try:
            new_viewport = FrozenColumnViewport(table)
            table.setViewport(new_viewport)
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de la colonne figée: {e}")

    def load_custom_posts(self):
        """Charge les postes personnalisés"""
        custom_posts_data = self.data_persistence.load_custom_posts()
        logger.info(f"Chargement des postes personnalisés: {custom_posts_data}")
        if custom_posts_data:
            try:
                if isinstance(next(iter(custom_posts_data.values())), dict):
                    from core.Constantes.custom_post import CustomPost
                    self.custom_posts = {
                        name: CustomPost.from_dict(data) 
                        for name, data in custom_posts_data.items()
                    }
                    logger.info(f"Postes personnalisés chargés: {list(self.custom_posts.keys())}")
                else:
                    self.custom_posts = custom_posts_data
                # Mise à jour des groupes après chargement
                self.update_post_groups()
                return self.custom_posts
            except Exception as e:
                logger.error(f"Erreur lors du chargement des postes personnalisés: {e}")
        return {}
    
    def update_post_groups(self):
        """Met à jour les groupes avec les postes personnalisés"""
        # Réinitialisation des listes de postes dans les groupes
        self.post_groups = {
            'matin': {
                'label': 'Matin',
                'posts': ['MM', 'CM', 'HM', 'SM', 'RM', 'ML', 'MC'],
                'color': QColor('#E3F2FD')  # Bleu clair
            },
            'apresMidi': {
                'label': 'Après-midi',
                'posts': ['CA', 'HA', 'SA', 'RA', 'AL', 'AC','CT'],
                'color': QColor('#FFF3E0')  # Orange clair
            },
            'soirNuit': {
                'label': 'Soir/Nuit',
                'posts': ['CS', 'HS', 'SS', 'RS', 'NL', 'NM', 'NA', 'NC'],
                'color': QColor('#EDE7F6')  # Violet clair
            }
        }

        # Ajout des postes personnalisés aux groupes appropriés
        logger.info("Mise à jour des groupes avec les postes personnalisés")
        for post_name, custom_post in self.custom_posts.items():
            logger.info(f"Traitement du poste {post_name}")
            start_hour = custom_post.start_time.hour
            if 7 <= start_hour < 13:
                self.post_groups['matin']['posts'].append(post_name)
                logger.info(f"- Ajouté au groupe matin")
            elif 13 <= start_hour < 18:
                self.post_groups['apresMidi']['posts'].append(post_name)
                logger.info(f"- Ajouté au groupe après-midi")
            else:
                self.post_groups['soirNuit']['posts'].append(post_name)
                logger.info(f"- Ajouté au groupe soir/nuit")

    def get_all_post_types(self):
        """Retourne tous les types de postes standards et personnalisés"""
        all_posts = set(ALL_POST_TYPES)
        if self.custom_posts:
            all_posts.update(self.custom_posts.keys())
        return sorted(list(all_posts))
    
    def get_post_group(self, post_type: str, day_info: Union[date, int]) -> str:
        """Détermine le groupe statistique d'un poste, y compris les postes personnalisés"""
        if post_type in self.custom_posts:
            custom_post = self.custom_posts[post_type]
            return custom_post.statistic_group if custom_post.statistic_group else "Other"
            
    def set_empty_table_message(self, table):
        table.setRowCount(1)
        table.setColumnCount(1)
        table.setItem(0, 0, QTableWidgetItem("Aucun planning généré"))

    def update_stats(self, planning=None, doctors=None, cats=None):
        """Mise à jour de tous les tableaux de statistiques"""
        if planning is not None:
            self.planning = planning
        if doctors is not None:
            self.doctors = doctors
        if cats is not None:
            self.cats = cats
        
        # Recharger les postes personnalisés et mettre à jour les groupes
        self.custom_posts = self.load_custom_posts()
        
        if self.planning and self.doctors and self.cats:
            self.create_stats_table()
            detailed_stats = self.calculate_detailed_stats()
            self.update_detailed_stats_table(detailed_stats)
            weekly_stats = self.calculate_weekday_stats()
            self.update_weekly_stats_table(weekly_stats)
            weekend_stats = self.calculate_weekend_stats()
            self.update_weekend_stats_table(weekend_stats)
            weekday_group_stats = self.calculate_weekday_group_stats()
            self.update_weekday_group_stats_table(weekday_group_stats)
        else:
            self.set_empty_table_message(self.stats_table)
            self.set_empty_table_message(self.detailed_stats_table)
            self.set_empty_table_message(self.weekly_stats_table)
            self.set_empty_table_message(self.weekend_stats_table)
            self.set_empty_table_message(self.weekday_group_stats_table)
    
    def _get_combined_intervals(self, doctor_name: str) -> Dict:
        """
        Calcule les intervalles combinés (semaine + weekend) pour tous les types de postes.
        Utilisé dans l'onglet des statistiques générales.
        
        Args:
            doctor_name: Nom du médecin
        
        Returns:
            Dict: Dictionnaire des intervalles combinés pour chaque type de poste
        """
        combined_intervals = {}
        pre_analysis = self.planning.pre_analysis_results
        if not pre_analysis or 'ideal_distribution' not in pre_analysis:
            return {}

        doctor_dist = pre_analysis['ideal_distribution'].get(doctor_name, {})
        weekday_posts = doctor_dist.get('weekday_posts', {})
        weekend_posts = doctor_dist.get('weekend_posts', {})

        # Pour chaque type de poste, combiner les intervalles
        all_post_types = set(weekday_posts.keys()) | set(weekend_posts.keys())
        for post_type in all_post_types:
            weekday_interval = weekday_posts.get(post_type, {'min': 0, 'max': float('inf')})
            weekend_interval = weekend_posts.get(post_type, {'min': 0, 'max': float('inf')})

            # Calculer la somme des minimums
            combined_min = weekday_interval['min'] + weekend_interval['min']

            # Calculer la somme des maximums, en gérant le cas float('inf')
            if weekday_interval['max'] == float('inf') and weekend_interval['max'] == float('inf'):
                combined_max = float('inf')
            elif weekday_interval['max'] == float('inf'):
                combined_max = float('inf')
            elif weekend_interval['max'] == float('inf'):
                combined_max = float('inf')
            else:
                combined_max = weekday_interval['max'] + weekend_interval['max']

            combined_intervals[post_type] = {
                'min': combined_min,
                'max': combined_max
            }

        return combined_intervals

    def create_stats_table(self):
        """Crée le tableau des statistiques générales avec priorité pour la coloration conditionnelle"""
        stats = self.calculate_stats()
        self.stats_table.clear()

        # Initialisation du tableau avec toutes les colonnes
        all_posts = self.get_all_post_types()

        self.stats_table.setColumnCount(len(all_posts) + 2)  # +2 pour nom et total
        headers = ['Assigné à'] + all_posts + ['Total']
        self.stats_table.setHorizontalHeaderLabels(headers)

        # Tri des médecins et CATs
        sorted_doctors = sorted([d for d in self.doctors if d.half_parts == 2], key=lambda x: x.name)
        sorted_half_doctors = sorted([d for d in self.doctors if d.half_parts == 1], key=lambda x: x.name)
        sorted_cats = sorted(self.cats, key=lambda x: x.name)
        all_personnel = sorted_doctors + sorted_half_doctors + sorted_cats

        # Configuration des lignes
        self.stats_table.setRowCount(len(all_personnel) + 2)  # +2 pour Non attribué et Total

        # Remplissage des données
        for row, person in enumerate(all_personnel):
            # Nom avec distinction appropriée
            name_item = QTableWidgetItem(person.name)
            
            # Style du nom selon le type (médecin plein temps, mi-temps, CAT)
            is_cat = not hasattr(person, 'half_parts')
            is_half_time = hasattr(person, 'half_parts') and person.half_parts == 1
            
            if is_cat:
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))  # Vert clair pour CAT
            elif is_half_time:
                name_item.setBackground(QColor(230, 230, 230, 255))  # Gris pour mi-temps
                
            self.stats_table.setItem(row, 0, name_item)

            # Récupérer les intervalles combinés pour tous les types d'utilisateurs
            combined_intervals = {}
            if hasattr(person, 'half_parts'):
                combined_intervals = self._get_combined_intervals(person.name)

            # Valeurs des postes
            row_total = 0
            for col, post_type in enumerate(all_posts, start=1):
                count = stats.get(person.name, {}).get(post_type, 0)
                item = QTableWidgetItem(str(count))
                
                # MODIFICATION: Priorité à la coloration conditionnelle sur les couleurs d'utilisateur
                color_applied = False
                
                # Vérifier d'abord les conditions min/max pour tous les utilisateurs
                if post_type in combined_intervals:
                    min_val = combined_intervals[post_type]['min']
                    max_val = combined_intervals[post_type]['max']
                    
                    if count < min_val:
                        item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                        color_applied = True
                    elif max_val != float('inf') and count > max_val:
                        item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                        color_applied = True
                
                # Si aucune coloration conditionnelle n'a été appliquée, appliquer les couleurs par type d'utilisateur
                if not color_applied:
                    if is_cat:
                        item.setBackground(QColor('#E8F5E9'))  # Vert clair pour CAT
                    elif is_half_time:
                        item.setBackground(QColor(230, 230, 230, 255))  # Gris pour mi-temps
                
                # Poste personnalisé - ne s'applique que si aucune autre coloration n'est prioritaire
                if post_type in self.custom_posts and not color_applied:
                    item.setBackground(self.custom_posts[post_type].color)
                    
                self.stats_table.setItem(row, col, item)
                row_total += count

            # Total de la ligne
            total_item = QTableWidgetItem(str(row_total))
            if is_cat:
                total_item.setBackground(QColor('#E8F5E9'))  # Vert clair pour CAT
            elif is_half_time:
                total_item.setBackground(QColor(230, 230, 230, 255))  # Gris pour mi-temps
                
            self.stats_table.setItem(row, len(all_posts) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self.add_unassigned_row(self.stats_table, len(all_personnel), stats, all_posts)
        self.add_total_row(self.stats_table, len(all_personnel) + 1, stats, all_posts)
        
        # Ajout des gestionnaires d'événements pour la mise en surbrillance
        self.setup_highlighting(self.stats_table)

        # Configuration de l'affichage
        self.optimize_column_widths(self.stats_table)
        
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setAlternatingRowColors(True)

        # Application du filtre actuel
        self._apply_filter_to_table(self.stats_table)

    
    # 3. Ajout d'une méthode pour optimiser l'affichage des colonnes
    def optimize_column_widths(self, table):
        """Optimise la largeur des colonnes en fonction du contenu avec un traitement spécial pour la colonne des noms"""
        # Première passe pour calculer les largeurs de contenu
        content_widths = {}
        font_metrics = QFontMetrics(table.font())
        
        # Largeur minimale garantie pour chaque type de colonne
        min_widths = {
            'name': 120,  # Augmenter la largeur minimale pour les noms
            'group': 70,  # Colonnes de groupes
            'post': 50,   # Colonnes de postes
            'total': 60   # Colonne total
        }
        
        # Vérifier s'il s'agit d'un tableau de groupes
        is_group_table = table == self.detailed_stats_table or table == self.weekday_group_stats_table
        
        # Traiter la première colonne (noms des assignés) de manière spéciale
        # pour s'assurer qu'elle est suffisamment large pour le plus long nom
        max_name_width = min_widths['name']
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item:
                name_text = item.text()
                text_width = font_metrics.horizontalAdvance(name_text)
                # Ajouter un padding plus généreux pour les noms
                text_width += 30
                max_name_width = max(max_name_width, text_width)
        
        # Limiter la largeur maximale des noms pour éviter qu'elle ne prenne trop de place
        max_name_width = min(max_name_width, 250)
        
        # Appliquer la largeur optimale à la colonne des noms
        table.setColumnWidth(0, max_name_width)
        
        
        # Évaluer la largeur nécessaire pour chaque colonne
        for col in range(table.columnCount()):
            col_type = 'name' if col == 0 else ('total' if col == table.columnCount() - 1 else 
                                            ('group' if is_group_table else 'post'))
            
            # Largeur de l'en-tête
            header_item = table.horizontalHeaderItem(col)
            if header_item:
                header_text = header_item.text()
                # Donner plus d'espace aux en-têtes de groupes qui peuvent être plus longs
                padding = 30 if col_type == 'group' else 20
                header_width = font_metrics.horizontalAdvance(header_text) + padding
            else:
                header_width = min_widths[col_type]
            
            # Largeur du contenu (échantillon des premières lignes pour performance)
            sample_rows = min(30, table.rowCount())
            content_width = header_width
            
            for row in range(sample_rows):
                item = table.item(row, col)
                if item:
                    item_text = item.text()
                    text_width = font_metrics.horizontalAdvance(item_text)
                    # Ajouter de l'espace pour le padding et les icônes éventuelles
                    padding = 20
                    this_width = text_width + padding
                    content_width = max(content_width, this_width)
            
            # Garantir une largeur minimale selon le type de colonne
            content_width = max(content_width, min_widths[col_type])
            
            # Limiter la largeur maximale selon le type de colonne
            max_width = 200 if col_type == 'name' else (120 if col_type == 'group' else 100)
            content_widths[col] = min(content_width, max_width)
        
        # Calculer l'espace disponible et répartir proportionnellement
        viewport_width = table.viewport().width()
        margins = 20  # Marge pour les barres de défilement etc.
        available_width = max(0, viewport_width - margins)
        
        # Calculer la largeur totale nécessaire
        total_content_width = sum(content_widths.values())
        
        # Si le contenu est plus large que l'espace disponible
        if total_content_width > available_width:
            # Réduire les colonnes proportionnellement, en préservant les colonnes essentielles
            # Calculer le facteur de réduction
            reduction_factor = available_width / total_content_width
            
            # Appliquer le facteur aux colonnes, en respectant les minimums
            for col in range(table.columnCount()):
                col_type = 'name' if col == 0 else ('total' if col == table.columnCount() - 1 else 
                                                ('group' if is_group_table else 'post'))
                adjusted_width = max(min_widths[col_type], int(content_widths[col] * reduction_factor))
                table.setColumnWidth(col, adjusted_width)
        else:
            # Si suffisamment d'espace, ajuster les colonnes en fonction de leur contenu
            # Répartir l'espace supplémentaire proportionnellement
            extra_space = available_width - total_content_width
            for col in range(table.columnCount()):
                col_type = 'name' if col == 0 else ('total' if col == table.columnCount() - 1 else 
                                                ('group' if is_group_table else 'post'))
                
                # Proportion de l'espace supplémentaire à ajouter
                proportion = content_widths[col] / total_content_width if total_content_width > 0 else 0
                extra = int(extra_space * proportion)
                
                # Largeur finale avec bonus
                final_width = content_widths[col] + extra
                table.setColumnWidth(col, final_width)
        
        # Ajustement final pour garantir que toutes les colonnes sont visibles
        # et que leur largeur est adaptée à leur importance
        # CORRECTION: Convertir explicitement en int pour éviter l'erreur de type
        name_col_width = int(max(table.columnWidth(0), min_widths['name'] * 1.5))
        table.setColumnWidth(0, name_col_width)
        
        # Garantir que les groupes ont suffisamment d'espace
        if is_group_table:
            for col in range(1, table.columnCount() - 1):
                table.setColumnWidth(col, max(table.columnWidth(col), min_widths['group']))

    # Ajout d'une méthode pour optimiser tous les tableaux après un changement d'onglet
    def optimize_all_tables(self):
        """Optimise la largeur des colonnes de tous les tableaux"""
        self.optimize_column_widths(self.stats_table)
        self.optimize_column_widths(self.weekend_stats_table)
        self.optimize_column_widths(self.detailed_stats_table)
        self.optimize_column_widths(self.weekly_stats_table)
        self.optimize_column_widths(self.weekday_group_stats_table)
        
    def _optimize_visible_tables(self):
        """Optimise les tableaux actuellement visibles"""
        # Identifier et optimiser uniquement les tableaux visibles
        for table in [self.stats_table, self.weekend_stats_table, self.detailed_stats_table, 
                    self.weekly_stats_table, self.weekday_group_stats_table]:
            if table.isVisible():
                self.optimize_column_widths(table)

    # 5. Améliorer le rendu des tableaux avec une méthode de stylisation unifiée
    def apply_unified_table_style(self, table, style_category=None):
        """Applique un style unifié et amélioré au tableau"""
        base_style = """
            QTableView {
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                background-color: #FFFFFF;
                gridline-color: #E2E8F0;
                selection-background-color: rgba(26, 90, 150, 0.15);
                selection-color: #2C3E50;
            }
            QHeaderView::section {
                background-color: #EDF2F7;
                color: #2C3E50;
                padding: 6px 8px;
                border: 1px solid #CBD5E1;
                font-weight: bold;
            }
            QTableView::item {
                padding: 4px 6px;
                border-bottom: 1px solid #EDF2F7;
            }
        """
        
        # Styles spécifiques par catégorie
        category_styles = {
            'general': """
                QHeaderView::section {
                    background-color: #D0E2F3;
                }
            """,
            'weekend': """
                QHeaderView::section {
                    background-color: #E2D4ED;
                }
            """,
            'detailed': """
                QHeaderView::section {
                    background-color: #F8D57E;
                }
            """
        }
        
        # Appliquer le style de base + le style spécifique si applicable
        style = base_style
        if style_category and style_category in category_styles:
            style += category_styles[style_category]
        
        table.setStyleSheet(style)
        
        # Configurer les dimensions
        table.verticalHeader().setDefaultSectionSize(28)  # Hauteur de ligne
        table.horizontalHeader().setMinimumHeight(36)    # Hauteur minimale des en-têtes
        
        # Améliorer l'affichage des en-têtes (text wrap)
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            if header_item:
                header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
        # Optimiser les largeurs des colonnes
        self.optimize_column_widths(table)
        
        
    def _apply_filter_to_table(self, table):
        """Applique le filtre actuel à un tableau donné"""
        if not table:
            return

        for col in range(1, table.columnCount() - 1):  # Exclure nom et total
            header_item = table.horizontalHeaderItem(col)
            if not header_item:
                continue
                
            post = header_item.text()
            is_visible = self.current_filter == 'all'
            
            if not is_visible:
                # Vérifier si le poste appartient au groupe actif
                is_visible = post in self.post_groups.get(self.current_filter, {}).get('posts', [])
            
            table.setColumnHidden(col, not is_visible)
        
        # Mise à jour des totaux
        self._update_visible_totals(table)
    
    def _handle_header_left_click(self, logical_index):
        """Gère le clic gauche sur un en-tête (tri de colonne)"""
        # Debug pour voir si la méthode est appelée
        logger.debug(f"Clic gauche sur la colonne {logical_index}")
        
        # Vérifier que ce n'est pas la colonne "Assigné à" ou "Total"
        if logical_index == 0 or logical_index == self.detailed_stats_table.columnCount() - 1:
            return
        
        try:
            # Déterminer l'identifiant de la table
            table_id = self.detailed_stats_table.property("table_id")
            if table_id is None:
                table_id = 2  # L'ID par défaut pour detailed_stats_table
            
            # Déterminer l'ordre de tri
            if logical_index in self.sort_order.get(table_id, {}):
                # Inverser l'ordre actuel
                order = not self.sort_order[table_id][logical_index]
            else:
                # Par défaut: tri ascendant
                order = True
                
            # Mettre à jour l'ordre de tri pour cette colonne
            if table_id not in self.sort_order:
                self.sort_order[table_id] = {}
            self.sort_order[table_id] = {logical_index: order}  # Réinitialiser pour n'avoir qu'une colonne triée
            
            # Trier la table directement
            self._sort_table_data(self.detailed_stats_table, logical_index, order)
            
            # Mettre à jour les en-têtes pour montrer l'ordre de tri
            self._update_sort_indicators(self.detailed_stats_table, logical_index, order)
            
            logger.debug(f"Tri effectué sur la colonne {logical_index}, ordre: {'ascendant' if order else 'descendant'}")
        except Exception as e:
            logger.error(f"Erreur lors du tri de la colonne {logical_index}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _sort_table_data(self, table, col, ascending=True):
        """Trie les données de la table selon la colonne spécifiée"""
        # Obtenir les données à trier (uniquement les lignes des utilisateurs)
        data = []
        # Toujours exclure "Non attribué" et "Total" du tri
        sort_range = table.rowCount() - 2
        
        # Sauvegarder les lignes "Non attribué" et "Total"
        unassigned_data = {}
        total_data = {}
        for c in range(table.columnCount()):
            unassigned_item = table.item(table.rowCount() - 2, c)
            total_item = table.item(table.rowCount() - 1, c)
            if unassigned_item:
                unassigned_data[c] = {
                    'text': unassigned_item.text(),
                    'background': unassigned_item.background(),
                    'font': unassigned_item.font(),
                    'tooltip': unassigned_item.toolTip()
                }
            if total_item:
                total_data[c] = {
                    'text': total_item.text(),
                    'background': total_item.background(),
                    'font': total_item.font(),
                    'tooltip': total_item.toolTip()
                }
        
        # Trier uniquement les lignes des utilisateurs
        for row in range(sort_range):
            # Obtenir la valeur de la cellule
            item = table.item(row, col)
            if item:
                try:
                    value = int(item.text())
                except ValueError:
                    value = item.text()
                    
                # Enregistrer toutes les données de la ligne
                row_data = {}
                for c in range(table.columnCount()):
                    cell = table.item(row, c)
                    if cell:
                        row_data[c] = {
                            'text': cell.text(),
                            'background': cell.background(),
                            'font': cell.font(),
                            'tooltip': cell.toolTip()
                        }
                data.append((row, value, row_data))
        
        # Trier les données
        data.sort(key=lambda x: x[1], reverse=not ascending)
        
        # Réorganiser les lignes selon le tri
        for new_idx, (old_idx, _, row_data) in enumerate(data):
            for c, cell_data in row_data.items():
                new_item = QTableWidgetItem(cell_data['text'])
                new_item.setBackground(cell_data['background'])
                new_item.setFont(cell_data['font'])
                new_item.setToolTip(cell_data['tooltip'])
                table.setItem(new_idx, c, new_item)
                
        # Restaurer les lignes "Non attribué" et "Total"
        for c, cell_data in unassigned_data.items():
            new_item = QTableWidgetItem(cell_data['text'])
            new_item.setBackground(cell_data['background'])
            new_item.setFont(cell_data['font'])
            new_item.setToolTip(cell_data['tooltip'])
            table.setItem(table.rowCount() - 2, c, new_item)
            
        for c, cell_data in total_data.items():
            new_item = QTableWidgetItem(cell_data['text'])
            new_item.setBackground(cell_data['background'])
            new_item.setFont(cell_data['font'])
            new_item.setToolTip(cell_data['tooltip'])
            table.setItem(table.rowCount() - 1, c, new_item)

    def _update_sort_indicators(self, table, sorted_column, ascending):
        """Met à jour les en-têtes pour indiquer la colonne triée et l'ordre"""
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            if header_item:
                # Récupérer le texte de base (sans flèche)
                base_text = header_item.text().replace(" ▲", "").replace(" ▼", "")
                
                # Ajouter la flèche uniquement à la colonne triée
                if col == sorted_column:
                    arrow = " ▲" if ascending else " ▼"
                    header_item.setText(base_text + arrow)
                else:
                    header_item.setText(base_text)

    def _handle_header_right_click(self, logical_index):
        """Gère le clic droit sur un en-tête (expansion de groupe)"""
        # Vérifier si c'est un en-tête de groupe et pas les colonnes spéciales
        if logical_index <= 0 or logical_index >= self.detailed_stats_table.columnCount() - 1:
            return
        
        header_item = self.detailed_stats_table.horizontalHeaderItem(logical_index)
        if not isinstance(header_item, AnimatedDetailedGroupHeader):
            return
        
        group_name = header_item.group_name
        
        # Protection contre les opérations multiples
        if hasattr(self, '_header_click_in_progress') and self._header_click_in_progress:
            return
        self._header_click_in_progress = True
        
        try:
            if self.expanded_group == group_name:
                # Fermer le groupe actuel
                self._collapse_group(group_name)
                self.expanded_group = None
            else:
                # Si un autre groupe est ouvert, le fermer d'abord
                if self.expanded_group and self.expanded_group in self.component_columns:
                    self._collapse_group(self.expanded_group)
                
                # Ouvrir le nouveau groupe après un court délai
                def expand_after_delay():
                    self._expand_group(group_name)
                    self.expanded_group = group_name
                    self._header_click_in_progress = False
                
                QTimer.singleShot(200, expand_after_delay)
                return
        except Exception as e:
            logger.error(f"Erreur lors du traitement du clic droit: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        self._header_click_in_progress = False

    def _update_visible_totals(self, table):
        """Met à jour les totaux en fonction des colonnes visibles"""
        if not table:
            return

        # Pour chaque ligne du tableau
        for row in range(table.rowCount()):
            visible_total = 0
            
            # Calcul du total sur les colonnes visibles uniquement
            for col in range(1, table.columnCount() - 1):  # Exclure nom et total
                if not table.isColumnHidden(col):
                    item = table.item(row, col)
                    if item:
                        try:
                            visible_total += int(item.text())
                        except ValueError:
                            continue

            # Mise à jour de la cellule total
            total_item = table.item(row, table.columnCount() - 1)
            if total_item:
                # Conserver le style existant
                background = total_item.background()
                font = total_item.font()
                
                # Mise à jour du total
                new_total_item = QTableWidgetItem(str(visible_total))
                new_total_item.setBackground(background)
                new_total_item.setFont(font)
                table.setItem(row, table.columnCount() - 1, new_total_item)

    def _calculate_row_total(self, table, row):
        """Calcule le total d'une ligne en ne prenant en compte que les colonnes visibles"""
        total = 0
        for col in range(1, table.columnCount() - 1):
            if not table.isColumnHidden(col):
                item = table.item(row, col)
                if item:
                    try:
                        total += int(item.text())
                    except ValueError:
                        continue
        return total
    def add_unassigned_row(self, table, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des postes non attribués avec un style uniformisé"""
        unassigned_stats = stats.get("Non attribué", {})
        unassigned_total = 0
        
        # Cellule du nom
        name_item = QTableWidgetItem("Non attribué")
        name_item.setBackground(QColor('#F5F5F5'))
        table.setItem(row_index, 0, name_item)
        
        # Valeurs par poste
        for col, post_type in enumerate(all_posts, start=1):
            count = unassigned_stats.get(post_type, 0)
            item = QTableWidgetItem(str(count))
            item.setBackground(QColor('#F5F5F5'))
            table.setItem(row_index, col, item)
            unassigned_total += count
        
        # Total
        total_item = QTableWidgetItem(str(unassigned_total))
        total_item.setBackground(QColor('#F5F5F5'))
        table.setItem(row_index, len(all_posts) + 1, total_item)

    def add_total_row(self, table, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des totaux avec un style uniformisé"""
        # Cellule du nom
        name_item = QTableWidgetItem("Total")
        name_item.setBackground(QColor('#EEEEEE'))
        name_item.setFont(QFont("", -1, QFont.Weight.Bold))
        table.setItem(row_index, 0, name_item)
        
        # Calcul des totaux par poste
        grand_total = 0
        for col, post_type in enumerate(all_posts, start=1):
            total = sum(person_stats.get(post_type, 0) 
                    for person_stats in stats.values())
            item = QTableWidgetItem(str(total))
            item.setBackground(QColor('#EEEEEE'))
            item.setFont(QFont("", -1, QFont.Weight.Bold))
            table.setItem(row_index, col, item)
            grand_total += total
        
        # Total général
        final_total = QTableWidgetItem(str(grand_total))
        final_total.setBackground(QColor('#EEEEEE'))
        final_total.setFont(QFont("", -1, QFont.Weight.Bold))
        table.setItem(row_index, len(all_posts) + 1, final_total)

    def update_detailed_stats_table(self, detailed_stats):
        """Mise à jour de l'onglet des groupes weekend avec priorité pour la coloration conditionnelle"""
        try:
            self.detailed_stats_table.clear()
            self.expanded_group = None
            self.component_columns.clear()

            # Mettre à jour les composants des groupes avec les postes personnalisés
            self._update_group_components()

            # Configuration des couleurs des groupes
            weekend_group_colors = {
                'gardes': QColor(180, 220, 255, 255),      # Bleu plus vif
                'visites': QColor(255, 200, 150, 255),     # Orange plus vif
                'consultations': QColor(220, 180, 255, 255) # Violet plus vif
            }

            # Configuration des données de base
            weekend_groups = {
                'gardes': {
                    'label': 'Gardes',
                    'groups': ['NLw', 'NAMw'],
                    'color': weekend_group_colors['gardes']
                },
                'visites': {
                    'label': 'Visites',
                    'groups': ['VmS', 'VmD', 'VaSD'],
                    'color': weekend_group_colors['visites']
                },
                'consultations': {
                    'label': 'Consultations',
                    'groups': ['CmS', 'CmD', 'CaSD', 'CsSD'],
                    'color': weekend_group_colors['consultations']
                }
            }
            
            # Collecte des groupes principaux
            all_groups = []
            for category in weekend_groups.values():
                all_groups.extend(category['groups'])

            # Configuration initiale du tableau
            self.detailed_stats_table.setColumnCount(len(all_groups) + 2)  # +2 pour nom et total
            headers = ['Assigné à'] + all_groups + ['Total']
            self.detailed_stats_table.setHorizontalHeaderItem(0, QTableWidgetItem('Assigné à'))
            self.detailed_stats_table.setHorizontalHeaderItem(len(all_groups) + 1, QTableWidgetItem('Total'))
            
            # Modifier la création des en-têtes pour utiliser AnimatedDetailedGroupHeader
            for col, group in enumerate(all_groups, start=1):
                try:
                    components = self.group_details.get(group, {}).get('components', [])
                    logger.debug(f"Création d'en-tête pour {group} avec composants: {components}")
                    header_item = AnimatedDetailedGroupHeader(group, components)
                    self.detailed_stats_table.setHorizontalHeaderItem(col, header_item)
                
                    # Coloration selon la catégorie
                    for category in weekend_groups.values():
                        if group in category['groups']:
                            header_item.setBackground(category['color'])
                            
                            # Ajout d'une infobulle explicative
                            tooltip = self.get_group_tooltip(group)
                            if tooltip:
                                header_item.setToolTip(tooltip + "\n\nCliquez droit pour développer les composants")
                            else:
                                header_item.setToolTip("Cliquez droit pour développer les composants")
                            break
                except Exception as e:
                    logger.error(f"Erreur lors de la création de l'en-tête pour {group}: {e}")
                    # Utiliser un en-tête standard en cas d'erreur
                    self.detailed_stats_table.setHorizontalHeaderItem(col, QTableWidgetItem(group))
            
            # Récupération des intervalles depuis la pré-analyse
            ideal_intervals = {}
            if self.planning and hasattr(self.planning, 'pre_analysis_results'):
                ideal_intervals = self.planning.pre_analysis_results.get('ideal_distribution', {})

            # Tri des médecins et CATs
            sorted_doctors = sorted([d for d in self.doctors if d.half_parts == 2], key=lambda x: x.name)
            sorted_half_doctors = sorted([d for d in self.doctors if d.half_parts == 1], key=lambda x: x.name)
            sorted_cats = sorted(self.cats, key=lambda x: x.name)
            all_personnel = sorted_doctors + sorted_half_doctors + sorted_cats

            # Configuration des lignes
            self.detailed_stats_table.setRowCount(len(all_personnel) + 2)  # +2 pour Non attribué et Total

            # Remplissage des données
            for row, person in enumerate(all_personnel):
                # Déterminer le style de base pour la personne
                is_cat = not hasattr(person, 'half_parts')
                is_half_time = hasattr(person, 'half_parts') and person.half_parts == 1
                
                # Nom avec distinction CAT/mi-temps
                name_item = QTableWidgetItem(person.name)
                if is_cat:
                    name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                    name_item.setBackground(QColor('#E8F5E9'))
                elif is_half_time:
                    name_item.setBackground(QColor('#F3F4F6'))
                self.detailed_stats_table.setItem(row, 0, name_item)

                # Valeurs des groupes
                row_total = 0
                for col, group in enumerate(all_groups, start=1):
                    count = detailed_stats.get(person.name, {}).get(group, 0)
                    item = QTableWidgetItem(str(count))
                    
                    # MODIFICATION: Priorité à la coloration conditionnelle
                    color_applied = False
                    
                    # Vérifier d'abord les conditions min/max pour tous les utilisateurs
                    intervals = ideal_intervals.get(person.name, {}).get('weekend_groups', {}).get(group, {})
                    if intervals:
                        min_val = intervals.get('min', 0)
                        max_val = intervals.get('max', float('inf'))
                        if count < min_val:
                            item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                            color_applied = True
                        elif max_val != float('inf') and count > max_val:
                            item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                            color_applied = True
                    
                    # Si aucune coloration conditionnelle n'a été appliquée, appliquer les couleurs par type d'utilisateur
                    if not color_applied:
                        if is_cat:
                            item.setBackground(QColor('#E8F5E9'))
                        elif is_half_time:
                            item.setBackground(QColor('#F3F4F6'))
                    
                    self.detailed_stats_table.setItem(row, col, item)
                    row_total += count

                # Total de la ligne
                total_item = QTableWidgetItem(str(row_total))
                if is_cat:
                    total_item.setBackground(QColor('#E8F5E9'))
                elif is_half_time:
                    total_item.setBackground(QColor('#F3F4F6'))
                self.detailed_stats_table.setItem(row, len(all_groups) + 1, total_item)

            # Ajout des lignes "Non attribué" et "Total"
            self._add_unassigned_row_detailed(len(all_personnel), detailed_stats, all_groups)
            self._add_total_row_detailed(len(all_personnel) + 1, detailed_stats, all_groups)

            # Configuration de l'affichage
            self.optimize_column_widths(self.detailed_stats_table)
            self.detailed_stats_table.verticalHeader().setVisible(False)
            self.detailed_stats_table.setAlternatingRowColors(False)

            # Application du filtre actuel
            self.setup_highlighting(self.detailed_stats_table)
            self._apply_filter_to_table(self.detailed_stats_table)

        except Exception as e:
            logger.error(f"Erreur dans update_detailed_stats_table: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_group_tooltip(self, group):
        """Retourne l'infobulle explicative pour chaque groupe"""
        tooltips = {
            'NLw': "Gardes de nuit longues weekend (NLv + NLs + NLd)",
            'NAMw': "Gardes de nuit courtes et moyennes weekend (NA + NM)",
            'VmS': "Visites du matin samedi",
            'VmD': "Visites du matin dimanche/férié",
            'VaSD': "Visites après-midi samedi et dimanche/férié",
            'CmS': "Consultations matin samedi",
            'CmD': "Consultations matin dimanche/férié",
            'CaSD': "Consultations après-midi samedi et dimanche/férié",
            'CsSD': "Consultations soir samedi et dimanche/férié"
        }
        return tooltips.get(group, "")
    
    def _handle_header_click(self, logical_index):
        """Gère le clic sur un en-tête de colonne de manière robuste"""
        if logical_index <= 0 or logical_index >= self.detailed_stats_table.columnCount() - 1:
            return  # Ignorer les clics sur 'Assigné à' et 'Total'

        header_item = self.detailed_stats_table.horizontalHeaderItem(logical_index)
        if not isinstance(header_item, AnimatedDetailedGroupHeader):
            return

        group_name = header_item.group_name

        # Protection contre les opérations multiples
        if hasattr(self, '_header_click_in_progress') and self._header_click_in_progress:
            return
        self._header_click_in_progress = True

        try:
            if self.expanded_group == group_name:
                # Cacher les composants du groupe actuel
                self._collapse_group(group_name)
                self.expanded_group = None
            else:
                # Cacher les composants du groupe précédent s'il y en a un
                if self.expanded_group and self.expanded_group in self.component_columns:
                    self._collapse_group(self.expanded_group)
                
                # Délai avant d'ouvrir le nouveau groupe pour éviter les conflits
                def expand_after_delay():
                    # Montrer les composants du nouveau groupe
                    self._expand_group(group_name)
                    self.expanded_group = group_name
                    self._header_click_in_progress = False
                
                QTimer.singleShot(200, expand_after_delay)
        except Exception as e:
            logger.error(f"Erreur lors du traitement du clic sur l'en-tête: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._header_click_in_progress = False

    def _update_group_components(self):
        """Met à jour les composants des groupes en incluant les postes personnalisés"""
        # Copie des composants standards
        updated_details = self.group_details.copy()
        
        # Parcourir tous les postes personnalisés
        for post_name, custom_post in self.custom_posts.items():
            if custom_post.statistic_group:
                # Si le poste appartient à un groupe
                group = custom_post.statistic_group
                if group in updated_details:
                    # Ajouter le poste personnalisé aux composants du groupe
                    if 'components' not in updated_details[group]:
                        updated_details[group]['components'] = []
                    updated_details[group]['components'].append(post_name)
                    
                    # Log pour le débogage
                    logger.info(f"Ajout du poste personnalisé {post_name} au groupe {group}")
        
        self.group_details = updated_details

    def calculate_weekend_component_stats(self):
        """
        Calcule les statistiques détaillées des composants pour les groupes weekend.
        Retourne un dictionnaire avec les stats de chaque composant par personne.
        """
        stats = {}
        if not self.planning:
            return stats

        # Initialiser les statistiques pour tout le personnel
        for person in self.doctors + self.cats:
            stats[person.name] = {}
            # Initialiser les composants pour chaque groupe
            for group_name, details in self.group_details.items():
                stats[person.name][group_name] = 0  # Total du groupe
                for component in details['components']:
                    stats[person.name][component] = 0  # Composants individuels

        # Ajouter "Non attribué"
        stats["Non attribué"] = {}
        for group_name, details in self.group_details.items():
            stats["Non attribué"][group_name] = 0
            for component in details['components']:
                stats["Non attribué"][component] = 0

        for day in self.planning.days:
            is_friday = day.date.weekday() == 4
            is_saturday = day.date.weekday() == 5
            is_sunday = day.date.weekday() == 6
            is_holiday = day.is_holiday_or_bridge

            for slot in day.slots:
                assignee = slot.assignee if slot.assignee in stats else "Non attribué"
                
                # Traitement spécial pour NLw et ses composants
                if slot.abbreviation == "NL":
                    stats[assignee]["NLw"] = stats[assignee].get("NLw", 0) + 1
                    if is_friday:
                        stats[assignee]["NLv"] = stats[assignee].get("NLv", 0) + 1
                    elif is_saturday:
                        stats[assignee]["NLs"] = stats[assignee].get("NLs", 0) + 1
                    elif is_sunday or is_holiday:
                        stats[assignee]["NLd"] = stats[assignee].get("NLd", 0) + 1
                        
                # Traitement pour NAMw
                elif slot.abbreviation in ["NA", "NM"] and (is_saturday or is_sunday or is_holiday):
                    stats[assignee]["NAMw"] = stats[assignee].get("NAMw", 0) + 1
                    if is_saturday:
                        if slot.abbreviation == "NA":
                            stats[assignee]["NAs"] = stats[assignee].get("NAs", 0) + 1
                        else:  # NM
                            stats[assignee]["NMs"] = stats[assignee].get("NMs", 0) + 1
                    else:  # Dimanche ou férié
                        if slot.abbreviation == "NA":
                            stats[assignee]["NAd"] = stats[assignee].get("NAd", 0) + 1
                        else:  # NM
                            stats[assignee]["NMd"] = stats[assignee].get("NMd", 0) + 1

                # Traitement pour les autres groupes selon group_details
                for group_name, details in self.group_details.items():
                    if slot.abbreviation in details['components']:
                        # Mettre à jour le composant individuel
                        stats[assignee][slot.abbreviation] = stats[assignee].get(slot.abbreviation, 0) + 1
                        
                        # Mettre à jour le total du groupe selon les conditions spécifiques
                        if group_name in ["VmS", "CmS"] and is_saturday:
                            stats[assignee][group_name] = stats[assignee].get(group_name, 0) + 1
                        elif group_name in ["VmD", "CmD"] and (is_sunday or is_holiday):
                            stats[assignee][group_name] = stats[assignee].get(group_name, 0) + 1
                        elif group_name in ["VaSD", "CaSD", "CsSD"] and (is_saturday or is_sunday or is_holiday):
                            stats[assignee][group_name] = stats[assignee].get(group_name, 0) + 1

        return stats
    def _expand_group(self, group_name):
        """Version améliorée de l'expansion de groupe avec animation plus robuste"""
        components = self.group_details.get(group_name, {}).get('components', [])
        if not components:
            return

        # Trouver la colonne du groupe
        group_index = -1
        for i in range(self.detailed_stats_table.columnCount()):
            header = self.detailed_stats_table.horizontalHeaderItem(i)
            if isinstance(header, AnimatedDetailedGroupHeader) and header.group_name == group_name:
                group_index = i
                break

        if group_index == -1:
            return

        # Mettre à jour l'indicateur
        header = self.detailed_stats_table.horizontalHeaderItem(group_index)
        header.toggle_expansion()

        # Insérer les colonnes des composants
        current_column = group_index + 1
        self.component_columns[group_name] = []
        stats = self.calculate_weekend_component_stats()

        # Vérifier si les colonnes existent déjà (important pour la stabilité)
        existing_columns = []
        for i in range(self.detailed_stats_table.columnCount()):
            header = self.detailed_stats_table.horizontalHeaderItem(i)
            if header and header.text() in components:
                existing_columns.append(header.text())

        # Créer les colonnes pour les composants qui n'existent pas déjà
        for component in components:
            if component in existing_columns:
                continue  # Sauter les colonnes qui existent déjà
                
            self.detailed_stats_table.insertColumn(current_column)
            header_item = QTableWidgetItem(component)
            self.detailed_stats_table.setHorizontalHeaderItem(current_column, header_item)
            
            # Remplir les données
            for row in range(self.detailed_stats_table.rowCount()):
                person_name = self.detailed_stats_table.item(row, 0).text()
                value = stats.get(person_name, {}).get(component, 0)
                item = QTableWidgetItem(str(value))
                
                # Déterminer le style de base pour la personne
                doctor = next((d for d in self.doctors if d.name == person_name), None)
                is_cat = person_name in [cat.name for cat in self.cats]
                is_half_time = doctor and doctor.half_parts == 1
                
                # Appliquer la couleur de base pour CAT ou mi-temps, sans condition
                if is_half_time:
                    item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                elif is_cat:
                    item.setBackground(QColor('#E8F5E9'))
                
                self.detailed_stats_table.setItem(row, current_column, item)
            
            self.component_columns[group_name].append(current_column)
            current_column += 1

        # S'assurer que component_columns contient des valeurs valides avant l'animation
        if self.component_columns.get(group_name, []):
            # Lancer l'animation d'expansion
            animation = ColumnAnimation(
                self.detailed_stats_table,
                min(self.component_columns[group_name]),
                max(self.component_columns[group_name])
            )
            animation.expand()

    def _collapse_group(self, group_name):
        """Version améliorée de la réduction de groupe avec animation plus robuste"""
        if group_name not in self.component_columns or not self.component_columns[group_name]:
            return

        # Mettre à jour l'indicateur
        group_index = -1
        for i in range(self.detailed_stats_table.columnCount()):
            header = self.detailed_stats_table.horizontalHeaderItem(i)
            if isinstance(header, AnimatedDetailedGroupHeader) and header.group_name == group_name:
                group_index = i
                if header.is_expanded:  # Vérifier si déjà réduit
                    header.toggle_expansion()
                break

        # Capturer une copie de la liste des colonnes à supprimer
        columns_to_remove = list(self.component_columns[group_name])
        
        if not columns_to_remove:
            # Pas de colonnes à supprimer
            return
            
        # Lancer l'animation de réduction
        animation = ColumnAnimation(
            self.detailed_stats_table,
            min(columns_to_remove),
            max(columns_to_remove)
        )
        animation.collapse()
        
        # Supprimer les colonnes après un délai correspondant à la durée de l'animation
        def remove_columns():
            # Protection contre les erreurs si le groupe n'existe plus
            if group_name in self.component_columns:
                for column in sorted(self.component_columns[group_name], reverse=True):
                    try:
                        self.detailed_stats_table.removeColumn(column)
                    except Exception as e:
                        logger.error(f"Erreur lors de la suppression de la colonne {column}: {e}")
                # Supprimer la référence aux colonnes après leur suppression
                self.component_columns.pop(group_name, None)

        # Utiliser un timer pour s'assurer que l'animation est terminée
        QTimer.singleShot(animation.duration + 100, remove_columns)

    
    def _add_unassigned_row_detailed(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des postes non attribués pour les groupes weekend avec style uniformisé"""
        self.add_unassigned_row(self.detailed_stats_table, row_index, stats, all_groups)

    def _add_total_row_detailed(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des totaux pour les groupes weekend avec style uniformisé"""
        self.add_total_row(self.detailed_stats_table, row_index, stats, all_groups)

    def update_detailed_stats_with_custom_posts(self):
        """Mise à jour des statistiques détaillées pour inclure les postes personnalisés"""
        stats = self.calculate_detailed_stats()
        
        # Ajouter les groupes statistiques des postes personnalisés
        custom_groups = set()
        for post in self.custom_posts.values():
            if post.statistic_group:
                custom_groups.add(post.statistic_group)

        # Mettre à jour les en-têtes avec les nouveaux groupes
        headers = self.get_detailed_stats_headers()
        headers.extend(list(custom_groups))

        self.detailed_stats_table.setColumnCount(len(headers))
        self.detailed_stats_table.setHorizontalHeaderLabels(headers)

        # Mise à jour des données
        self.update_detailed_stats_table(stats)

    def update_weekday_group_stats_table(self, weekday_group_stats):
        """Met à jour le tableau des statistiques des groupes de semaine avec priorité de coloration et largeur optimisée"""
        self.weekday_group_stats_table.clear()

        # Configuration des colonnes et en-têtes
        group_categories = {
            'consultations': {
                'label': 'Consultations',
                'groups': ['XmM', 'XM', 'XA', 'XS'],
            },
            'visites': {
                'label': 'Visites',
                'groups': ['Vm', 'Va'],
            },
            'gardes': {
                'label': 'Gardes',
                'groups': ['NMC', 'NL'],
            }
        }

        # Collecte des groupes
        all_groups = []
        for category in group_categories.values():
            all_groups.extend(category['groups'])

        # Configuration du tableau
        self.weekday_group_stats_table.setColumnCount(len(all_groups) + 2)
        headers = ['Assigné à'] + all_groups + ['Total']
        self.weekday_group_stats_table.setHorizontalHeaderLabels(headers)
        
        # Améliorer l'apparence des en-têtes
        for col, group_name in enumerate(all_groups, start=1):
            header_item = self.weekday_group_stats_table.horizontalHeaderItem(col)
            if header_item:
                # Ajout d'un tooltip amélioré pour chaque groupe
                tooltip = self.get_weekday_group_tooltip(group_name)
                if tooltip:
                    header_item.setToolTip(tooltip)

        # Tri et préparation du personnel
        sorted_doctors = sorted([d for d in self.doctors if d.half_parts == 2], key=lambda x: x.name)
        sorted_half_doctors = sorted([d for d in self.doctors if d.half_parts == 1], key=lambda x: x.name)
        sorted_cats = sorted(self.cats, key=lambda x: x.name)
        all_personnel = sorted_doctors + sorted_half_doctors + sorted_cats

        self.weekday_group_stats_table.setRowCount(len(all_personnel) + 2)

        # Remplissage des données
        for row, person in enumerate(all_personnel):
            is_cat = not hasattr(person, 'half_parts')
            is_half_time = hasattr(person, 'half_parts') and person.half_parts == 1
            
            # Configuration du nom
            name_item = QTableWidgetItem(person.name)
            
            # Tooltip pour le nom avec informations générales
            name_tooltip = f"{'CAT' if is_cat else 'Médecin'}\n"
            if not is_cat:
                name_tooltip += f"Demi-parts : {person.half_parts}"
            name_item.setToolTip(name_tooltip)
            
            # Appliquer le style selon le type (CAT ou demi-part)
            if is_cat:
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))
            elif is_half_time:
                name_item.setBackground(QColor(230, 230, 230, 255))
                
            self.weekday_group_stats_table.setItem(row, 0, name_item)

            intervals = self._get_doctor_weekday_intervals(person.name)
            row_total = 0
            
            for col, group in enumerate(all_groups, start=1):
                count = weekday_group_stats.get(person.name, {}).get(group, 0)
                item = QTableWidgetItem(str(count))
                
                # MODIFICATION: Priorité à la coloration conditionnelle
                color_applied = False
                
                # Vérifier d'abord les conditions min/max pour tous les types d'utilisateurs
                group_intervals = intervals.get(group, {})
                if group_intervals:
                    min_val = group_intervals.get('min', 0)
                    max_val = group_intervals.get('max', float('inf'))
                    if count < min_val:
                        item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                        color_applied = True
                    elif max_val != float('inf') and count > max_val:
                        item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                        color_applied = True
                
                # Si aucune coloration conditionnelle n'a été appliquée, appliquer les couleurs par type d'utilisateur
                if not color_applied:
                    if is_cat:
                        item.setBackground(QColor('#E8F5E9'))
                    elif is_half_time:
                        item.setBackground(QColor(230, 230, 230, 255))
                
                # Toujours ajouter le tooltip avec les informations d'intervalles
                tooltip = self._get_tooltip_text(count, group_intervals, is_cat, group)
                item.setToolTip(tooltip)
                
                self.weekday_group_stats_table.setItem(row, col, item)
                row_total += count

            # Total avec tooltip
            total_item = QTableWidgetItem(str(row_total))
            total_intervals = {"target": sum(intervals.get(g, {}).get('target', 0) for g in all_groups)}
            
            # Appliquer les couleurs de base seulement si pas de dépassement d'intervalles
            if is_cat:
                total_item.setBackground(QColor('#E8F5E9'))
            elif is_half_time:
                total_item.setBackground(QColor(230, 230, 230, 255))
                
            self.weekday_group_stats_table.setItem(row, len(all_groups) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row_weekday_groups(len(all_personnel), weekday_group_stats, all_groups)
        self._add_total_row_weekday_groups(len(all_personnel) + 1, weekday_group_stats, all_groups)

        # Configuration de l'affichage avec largeur optimisée
        self.optimize_column_widths(self.weekday_group_stats_table)
        self.setup_highlighting(self.weekday_group_stats_table)
        self.weekday_group_stats_table.verticalHeader().setVisible(False)

    def get_weekday_group_tooltip(self, group: str) -> str:
        """Version enrichie de la méthode existante avec intervalles"""
        base_tooltips = {
            'XmM': "Consultations du matin (MM, SM, RM)",
            'XM': "Consultations du matin (CM, HM)",
            'XA': "Consultations après-midi (CA, HA, SA, RA, CT)",
            'XS': "Consultations du soir (CS, HS, SS, RS)",
            'NAC': "Gardes de nuit courtes (NA, NC)",
            'VsM': "Visites du matin (ML, MC)",
            'VsA': "Visites après-midi (AL, AC)",
            'NMC': "visites de nuit (NM, NC)",
            'NL': "NL Lun-Jeu"}
        
        base_tooltip = base_tooltips.get(group, "")
        full_time_intervals = self.get_intervals_tooltip_text(group, "full_time")
        half_time_intervals = self.get_intervals_tooltip_text(group, "half_time")
        
        tooltip_parts = [base_tooltip]
        if full_time_intervals:
            tooltip_parts.append(full_time_intervals)
        if half_time_intervals:
            tooltip_parts.append(half_time_intervals)
            
        return "\n\n".join(tooltip_parts)

    def _add_unassigned_row_weekday_groups(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des postes non attribués pour les groupes de semaine avec style uniformisé"""
        self.add_unassigned_row(self.weekday_group_stats_table, row_index, stats, all_groups)

    def _add_total_row_weekday_groups(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des totaux pour les groupes de semaine avec style uniformisé"""
        self.add_total_row(self.weekday_group_stats_table, row_index, stats, all_groups)

    def update_weekly_stats_table(self, weekly_stats):
        """Met à jour le tableau des statistiques de semaine avec priorité de coloration et largeur optimisée"""
        self.weekly_stats_table.clear()

        # Récupération des statistiques de semaine
        stats = self.calculate_weekday_stats()

        # Récupérer les configurations de semaine depuis le planning
        weekday_config = {}
        if self.planning and hasattr(self.planning, 'pre_analysis_results'):
            weekday_config = self.planning.pre_analysis_results.get('total_posts', {}).get('weekday', {})

        # Créer un set pour collecter tous les postes configurés
        active_posts = set()

        # Vérification des postes configurés ou utilisés
        for group in self.post_groups.values():
            for post in group['posts']:
                weekday_count = weekday_config.get(post, 0)
                
                # Si le poste est configuré ou utilisé dans les stats
                if (weekday_count > 0 or
                    any(stats[person.name].get(post, 0) > 0 for person in self.doctors + self.cats)):
                    active_posts.add(post)

        # Organisation des postes selon l'ordre des groupes
        all_posts = []
        for group in self.post_groups.values():
            # Ajouter uniquement les postes actifs de ce groupe, dans l'ordre du groupe
            group_posts = [post for post in group['posts'] if post in active_posts]
            all_posts.extend(group_posts)

        # Configuration du tableau
        self.weekly_stats_table.setColumnCount(len(all_posts) + 2)
        headers = ['Assigné à'] + all_posts + ['Total']
        self.weekly_stats_table.setHorizontalHeaderLabels(headers)

        # Coloration des en-têtes selon les groupes
        for col, post in enumerate(all_posts, start=1):
            header_item = self.weekly_stats_table.horizontalHeaderItem(col)
            weekday_count = weekday_config.get(post, 0)
            base_tooltip = f"Configuration semaine : {weekday_count}"
            enhanced_tooltip = self.get_enhanced_post_tooltip(post, base_tooltip)
            header_item.setToolTip(enhanced_tooltip)


        # Récupération des intervalles depuis la pré-analyse
        ideal_intervals = {}
        if self.planning and hasattr(self.planning, 'pre_analysis_results'):
            ideal_intervals = self.planning.pre_analysis_results.get('ideal_distribution', {})

        # Tri des médecins et CATs
        sorted_doctors = sorted([d for d in self.doctors if d.half_parts == 2], key=lambda x: x.name)
        sorted_half_doctors = sorted([d for d in self.doctors if d.half_parts == 1], key=lambda x: x.name)
        sorted_cats = sorted(self.cats, key=lambda x: x.name)
        all_personnel = sorted_doctors + sorted_half_doctors + sorted_cats

        # Configuration des lignes du tableau
        self.weekly_stats_table.setRowCount(len(all_personnel) + 2)  # +2 pour Non attribué et Total

        # Remplissage des données
        for row, person in enumerate(all_personnel):
            # Nom avec distinction CAT/mi-temps
            name_item = QTableWidgetItem(person.name)
            is_cat = not hasattr(person, 'half_parts')
            is_half_time = hasattr(person, 'half_parts') and person.half_parts == 1
            
            if is_cat:
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))
            elif is_half_time:
                name_item.setBackground(QColor(230, 230, 230, 255))
            self.weekly_stats_table.setItem(row, 0, name_item)

            # Valeurs des postes
            row_total = 0
            person_intervals = ideal_intervals.get(person.name, {}).get('weekday_posts', {})

            for col, post in enumerate(all_posts, start=1):
                count = stats.get(person.name, {}).get(post, 0)
                item = QTableWidgetItem(str(count))
                
                # MODIFICATION: Priorité à la coloration conditionnelle
                color_applied = False
                
                # Vérifier d'abord les intervalles pour tous les types d'utilisateurs
                intervals = person_intervals.get(post, {})
                if intervals:
                    min_val = intervals.get('min', 0)
                    max_val = intervals.get('max', float('inf'))
                    if count < min_val:
                        item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                        color_applied = True
                    elif max_val != float('inf') and count > max_val:
                        item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                        color_applied = True
                
                # Si aucune coloration conditionnelle n'a été appliquée, appliquer les couleurs par type d'utilisateur
                if not color_applied:
                    if is_cat:
                        item.setBackground(QColor('#E8F5E9'))
                    elif is_half_time:
                        item.setBackground(QColor(230, 230, 230, 255))
                    elif post in self.custom_posts:
                        item.setBackground(self.custom_posts[post].color)
                        
                self.weekly_stats_table.setItem(row, col, item)
                row_total += count

            # Total de la ligne
            total_item = QTableWidgetItem(str(row_total))
            if is_cat:
                total_item.setBackground(QColor('#E8F5E9'))
            elif is_half_time:
                total_item.setBackground(QColor(230, 230, 230, 255))
            self.weekly_stats_table.setItem(row, len(all_posts) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row_weekly(len(all_personnel), stats, all_posts)
        self._add_total_row_weekly(len(all_personnel) + 1, stats, all_posts)

        # Configuration de l'affichage avec largeur optimisée
        self.optimize_column_widths(self.weekly_stats_table)
        self.weekly_stats_table.verticalHeader().setVisible(False)
        self.weekly_stats_table.setAlternatingRowColors(False)

        # Application du filtre actuel
        self.setup_highlighting(self.weekly_stats_table)
        self._apply_filter_to_table(self.weekly_stats_table)

    def _add_unassigned_row_weekly(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des postes non attribués pour les statistiques semaine avec style uniformisé"""
        self.add_unassigned_row(self.weekly_stats_table, row_index, stats, all_posts)

    def _add_total_row_weekly(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des totaux pour les statistiques semaine avec style uniformisé"""
        self.add_total_row(self.weekly_stats_table, row_index, stats, all_posts)

    def update_weekend_stats_table(self, weekend_stats):
        """Met à jour le tableau des statistiques weekend"""
        self.weekend_stats_table.clear()

        # Récupération des statistiques weekend
        stats = self.calculate_weekend_stats()

        # Récupération des configurations weekend depuis le planning
        weekend_config = {}
        holiday_config = {}
        if self.planning and hasattr(self.planning, 'pre_analysis_results'):
            weekend_config = self.planning.pre_analysis_results.get('total_posts', {}).get('saturday', {})
            holiday_config = self.planning.pre_analysis_results.get('total_posts', {}).get('sunday_holiday', {})

        # Création d'un set pour collecter tous les postes configurés
        active_posts = set()

        # Vérification des postes configurés ou utilisés
        for group in self.post_groups.values():
            for post in group['posts']:
                saturday_count = weekend_config.get(post, 0)
                holiday_count = holiday_config.get(post, 0)
                
                # Si le poste est configuré ou utilisé dans les stats
                if (saturday_count > 0 or holiday_count > 0 or
                    any(stats[person.name].get(post, 0) > 0 for person in self.doctors + self.cats)):
                    active_posts.add(post)

        # Organisation des postes selon l'ordre des groupes
        all_posts = []
        for group in self.post_groups.values():
            # Ajouter uniquement les postes actifs de ce groupe, dans l'ordre du groupe
            group_posts = [post for post in group['posts'] if post in active_posts]
            all_posts.extend(group_posts)

        # Configuration du tableau
        self.weekend_stats_table.setColumnCount(len(all_posts) + 2)
        headers = ['Assigné à'] + all_posts + ['Total']
        self.weekend_stats_table.setHorizontalHeaderLabels(headers)

        # Coloration des en-têtes selon les groupes
        for col, post in enumerate(all_posts, start=1):
            header_item = self.weekend_stats_table.horizontalHeaderItem(col)
            saturday_count = weekend_config.get(post, 0)
            holiday_count = holiday_config.get(post, 0)
            base_tooltip = f"Configuration :\nSamedi : {saturday_count}\nDimanche/Férié : {holiday_count}"
            enhanced_tooltip = self.get_enhanced_post_tooltip(post, base_tooltip)
            header_item.setToolTip(enhanced_tooltip)

        # Récupération des intervalles depuis la pré-analyse
        ideal_intervals = {}
        if self.planning and hasattr(self.planning, 'pre_analysis_results'):
            ideal_intervals = self.planning.pre_analysis_results.get('ideal_distribution', {})

        # Tri et préparation du personnel
        sorted_doctors = sorted([d for d in self.doctors if d.half_parts == 2], key=lambda x: x.name)
        sorted_half_doctors = sorted([d for d in self.doctors if d.half_parts == 1], key=lambda x: x.name)
        sorted_cats = sorted(self.cats, key=lambda x: x.name)
        all_personnel = sorted_doctors + sorted_half_doctors + sorted_cats

        # Configuration des lignes du tableau
        self.weekend_stats_table.setRowCount(len(all_personnel) + 2)

        # Modification dans la boucle de remplissage des données
        for row, person in enumerate(all_personnel):
            # Configuration du nom
            name_item = QTableWidgetItem(person.name)
            is_cat = not hasattr(person, 'half_parts')
            is_half_time = hasattr(person, 'half_parts') and person.half_parts == 1
            
            if is_cat:
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))
            elif is_half_time:
                name_item.setBackground(QColor(230, 230, 230, 255))
            self.weekend_stats_table.setItem(row, 0, name_item)

            # Récupération des intervalles spécifiques à la personne
            person_intervals = ideal_intervals.get(person.name, {})
            weekend_group_intervals = person_intervals.get('weekend_groups', {})
            weekend_post_intervals = person_intervals.get('weekend_posts', {})

            # Calcul du total des NL (incluant NLv)
            nl_total = weekend_stats.get(person.name, {}).get('NL', 0)

            row_total = 0
            for col, post_type in enumerate(all_posts, start=1):
                count = weekend_stats.get(person.name, {}).get(post_type, 0)
                item = QTableWidgetItem(str(count))
                
                # MODIFICATION: Priorité à la coloration conditionnelle
                color_applied = False
                
                # Vérifier les conditions min/max
                if post_type == 'NL':  # Cas spécial pour NL
                    nlw_intervals = weekend_group_intervals.get('NLw', {})
                    min_val = nlw_intervals.get('min', 0)
                    max_val = nlw_intervals.get('max', float('inf'))
                    
                    if nl_total < min_val:
                        item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                        color_applied = True
                    elif nl_total > max_val:
                        item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                        color_applied = True
                else:  # Autres postes
                    intervals = weekend_post_intervals.get(post_type, {})
                    min_val = intervals.get('min', 0)
                    max_val = intervals.get('max', float('inf'))
                    if count < min_val:
                        item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                        color_applied = True
                    elif max_val != float('inf') and count > max_val:
                        item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                        color_applied = True
                
                # Appliquer les couleurs de base seulement si pas de coloration conditionnelle
                if not color_applied:
                    if is_cat:
                        item.setBackground(QColor('#E8F5E9'))
                    elif is_half_time:
                        item.setBackground(QColor(230, 230, 230, 255))
                    elif post_type in self.custom_posts:
                        item.setBackground(self.custom_posts[post_type].color)
                
                self.weekend_stats_table.setItem(row, col, item)
                row_total += count

            # Total de la ligne
            total_item = QTableWidgetItem(str(row_total))
            if hasattr(person, 'half_parts') and person.half_parts == 1:
                total_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
            self.weekend_stats_table.setItem(row, len(all_posts) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row_weekend(len(all_personnel), weekend_stats, all_posts)
        self._add_total_row_weekend(len(all_personnel) + 1, weekend_stats, all_posts)

        # Configuration de l'affichage
        self.weekend_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.weekend_stats_table.verticalHeader().setVisible(False)
        self.weekend_stats_table.setAlternatingRowColors(False)

        # Application du filtre actuel
        self.setup_highlighting(self.weekend_stats_table)
        self._apply_filter_to_table(self.weekend_stats_table)
    
    def _add_unassigned_row_weekend(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des postes non attribués pour les statistiques weekend avec style uniformisé"""
        self.add_unassigned_row(self.weekend_stats_table, row_index, stats, all_posts)

    def _add_total_row_weekend(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des totaux pour les statistiques weekend avec style uniformisé"""
        self.add_total_row(self.weekend_stats_table, row_index, stats, all_posts)

    def calculate_stats(self):
        # Récupérer tous les types de postes possibles
        all_post_types = set(ALL_POST_TYPES)  # Postes standards
        
        # Ajouter les postes personnalisés s'ils existent
        if hasattr(self, 'custom_posts'):
            all_post_types.update(self.custom_posts.keys())
        
        # Initialiser les stats avec tous les types de postes
        stats = {
            doctor.name: {post_type: 0 for post_type in all_post_types}
            for doctor in self.doctors
        }
        stats.update({
            cat.name: {post_type: 0 for post_type in all_post_types}
            for cat in self.cats
        })
        stats["Non attribué"] = {post_type: 0 for post_type in all_post_types}
        
        if not self.planning or not self.planning.days:
            return stats

        for day_planning in self.planning.days:
            for slot in day_planning.slots:
                # S'assurer que le type de poste existe dans les stats
                if slot.abbreviation not in stats["Non attribué"]:
                    # Ajouter le nouveau type de poste à tous les dictionnaires
                    for person_stats in stats.values():
                        person_stats[slot.abbreviation] = 0
                        
                if slot.assignee in stats:
                    stats[slot.assignee][slot.abbreviation] += 1
                else:
                    stats["Non attribué"][slot.abbreviation] += 1

        return stats
    
    def calculate_detailed_stats(self):
        """
        Calcule les statistiques détaillées des groupes weekend en prenant en compte
        correctement les jours fériés et les ponts, avec un traitement spécial pour les NLv.
        
        Les NLv (nuits longues du vendredi) sont toujours comptées dans le groupe NLw,
        indépendamment du fait que le vendredi soit un pont ou non. Cela permet de
        maintenir la cohérence dans le décompte des gardes de nuit du weekend.
        """
        stats = {person.name: {
            "NLv": 0, "NLs": 0, "NLd": 0, "NLw": 0, "NAMw": 0,
            "VmS": 0, "VmD": 0, "VaSD": 0,
            "CmS": 0, "CmD": 0, "CaSD": 0, "CsSD": 0,
            "WE Lib": 0
        } for person in self.doctors + self.cats}
        stats["Non attribué"] = {key: 0 for key in stats[self.doctors[0].name].keys()}

        if not self.planning or not self.planning.days:
            return stats

        from core.Constantes.day_type import DayType
        cal = France()

        for day in self.planning.days:
            # Déterminer le type de jour
            day_type = DayType.get_day_type(day.date, cal)
            is_friday = day.date.weekday() == 4
            is_bridge = DayType.is_bridge_day(day.date, cal)
            
            # Un samedi de pont est traité comme un dimanche/férié, sauf pour NLv
            is_saturday = day.date.weekday() == 5 and not is_bridge
            is_sunday_holiday = day_type == "sunday_holiday" or is_bridge

            for slot in day.slots:
                assignee = slot.assignee if slot.assignee in stats else "Non attribué"

                # 1. Traitement spécial des gardes de nuit longues
                if slot.abbreviation == "NL":
                    if is_friday:
                        # Les NLv sont toujours comptées séparément, même si c'est un pont
                        stats[assignee]["NLv"] += 1
                        stats[assignee]["NLw"] += 1
                    elif is_saturday:
                        stats[assignee]["NLs"] += 1
                        stats[assignee]["NLw"] += 1
                    elif is_sunday_holiday:
                        stats[assignee]["NLd"] += 1
                        stats[assignee]["NLw"] += 1

                # 2. Traitement des autres postes de garde
                elif slot.abbreviation in ["NM", "NA"] and (is_saturday or is_sunday_holiday):
                    stats[assignee]["NAMw"] += 1

                # 3. Traitement des visites matin avec prise en compte des ponts
                elif slot.abbreviation in ["ML", "MC"]:
                    if is_saturday:
                        stats[assignee]["VmS"] += 1
                    elif is_sunday_holiday:
                        stats[assignee]["VmD"] += 1

                # 4. Traitement des visites après-midi
                elif slot.abbreviation in ["AL", "AC"] and (is_saturday or is_sunday_holiday):
                    stats[assignee]["VaSD"] += 1

                # 5. Traitement des consultations matin
                elif slot.abbreviation in ["CM", "HM", "SM", "RM", "MM"]:
                    if is_saturday:
                        stats[assignee]["CmS"] += 1
                    elif is_sunday_holiday:
                        stats[assignee]["CmD"] += 1

                # 6. Traitement des consultations après-midi
                elif slot.abbreviation in ["CA", "HA", "SA", "RA"] and (is_saturday or is_sunday_holiday):
                    stats[assignee]["CaSD"] += 1

                # 7. Traitement des consultations soir
                elif slot.abbreviation in ["CS", "HS", "SS", "RS"] and (is_saturday or is_sunday_holiday):
                    stats[assignee]["CsSD"] += 1

            # Calculer les weekends libres pour chaque personne
            for person in self.doctors + self.cats:
                stats[person.name]["WE Lib"] = self.calculate_we_lib(person.name)

        return stats
    def calculate_weekday_group_stats(self):
        """
        Calcule les statistiques des groupes de semaine avec une gestion correcte du CT.
        """
        stats = {person.name: {
            "XmM": 0,  # Consultations matin à partir de 7h (MM, SM, RM)
            "XM": 0,   # Consultations matin à partir de 9h (CM, HM)
            "XA": 0,   # Consultations après-midi (CA, HA, RA, SA, CT)
            "XS": 0,   # Consultations soir
            "NMC": 0,  # Gardes de nuit courtes/moyennes
            "Vm": 0,   # Visites matin
            "Va": 0,   # Visites après-midi
            "NL": 0    # Nuits longues (hors vendredi)
        } for person in self.doctors + self.cats}
        stats["Non attribué"] = {key: 0 for key in stats[self.doctors[0].name].keys()}

        if not self.planning or not self.planning.days:
            return stats

        for day in self.planning.days:
            # Exclure weekends, fériés, ponts
            if day.is_weekend or day.is_holiday_or_bridge:
                continue

            # Vérifier si c'est un vendredi pour ignorer les NL
            is_friday = day.date.weekday() == 4

            for slot in day.slots:
                assignee = slot.assignee if slot.assignee in stats else "Non attribué"

                # Mapping explicite des postes vers les groupes
                post_group_mapping = {
                    # Groupe XmM
                    "MM": "XmM", "SM": "XmM", "RM": "XmM",
                    
                    # Groupe XM
                    "CM": "XM", "HM": "XM",
                    
                    # Groupe XA - Inclure explicitement CT
                    "CA": "XA", "HA": "XA", "SA": "XA", "RA": "XA", "CT": "XA",
                    
                    # Groupe XS
                    "CS": "XS", "HS": "XS", "SS": "XS", "RS": "XS",
                    
                    # Groupe NMC
                    "NM": "NMC", "NC": "NMC", "NA": "NMC",
                    
                    # Groupe Vm
                    "ML": "Vm", "MC": "Vm",
                    
                    # Groupe Va
                    "AL": "Va", "AC": "Va",
                    
                    # Groupe NL (hors vendredi)
                    "NL": "NL"
                }

                # Attribution au groupe approprié
                if slot.abbreviation in post_group_mapping and not (is_friday and slot.abbreviation == "NL"):
                    group = post_group_mapping[slot.abbreviation]
                    stats[assignee][group] += 1

                # Log détaillé pour le debugging des postes CT
                if slot.abbreviation == "CT":
                    logger.debug(f"CT attribué à {assignee} le {day.date} - comptabilisé dans XA")

        return stats

    def _get_doctor_weekday_intervals(self, person_name: str) -> Dict[str, Dict[str, int]]:
        """
        Récupère les intervalles de groupes de semaine pour un médecin ou CAT depuis la pré-analyse.
        
        Args:
            person_name: Nom du médecin ou du CAT
            
        Returns:
            Dict contenant les intervalles min/max pour chaque groupe
        """
        if not (hasattr(self, 'planning') and self.planning and 
                hasattr(self.planning, 'pre_analysis_results')):
            return {}

        pre_analysis = self.planning.pre_analysis_results
        ideal_distribution = pre_analysis.get('ideal_distribution', {})
        person_dist = ideal_distribution.get(person_name, {})

        is_cat = person_name in [cat.name for cat in self.cats]

        # Récupérer les intervalles de la pré-analyse
        weekday_groups = person_dist.get('weekday_groups', {})
        weekday_posts = person_dist.get('weekday_posts', {})

        # Pour les CAT, la target devient le quota exact
        if is_cat:
            intervals = {}
            for group, values in weekday_groups.items():
                target = values.get('target', 0)
                intervals[group] = {
                    'target': round(target),  # Arrondir pour avoir un quota entier
                    'min': round(target),     # Min et max égaux pour les CAT
                    'max': round(target)
                }
        else:
            # Pour les médecins, garder les intervalles min/max
            intervals = weekday_groups

        return intervals


    def _get_tooltip_text(self, value: int, intervals: Dict[str, Dict[str, int]], 
                        is_cat: bool = False, group: str = None) -> str:
        """
        Génère le tooltip avec les informations de la pré-analyse.
        Pour les CAT, met en évidence les différences avec le quota prévu.
        """
        if not intervals:
            return "Pas de quota/intervalle défini"

        if is_cat:
            target = intervals.get('target', 0)
            if target == 0:
                return f"CAT - {group}\nPas de quota défini pour ce groupe"
                
            tooltip = f"CAT - {group}\n"
            tooltip += f"Quota prévu : {target}\n"
            tooltip += f"Nombre actuel : {value}\n"
            
            diff = value - target
            if diff == 0:
                tooltip += "✓ Nombre de postes conforme au quota"
            else:
                tooltip += "⚠ Différence avec le quota prévu\n"
                if diff < 0:
                    tooltip += f"▼ Manque {abs(diff)} poste{'s' if abs(diff) > 1 else ''}"
                else:
                    tooltip += f"▲ Excès de {diff} poste{'s' if diff > 1 else ''}"
        else:
            min_val = intervals.get('min', 0)
            max_val = intervals.get('max', float('inf'))
            target = intervals.get('target', None)
            
            tooltip = f"Médecin - {group}\n"
            tooltip += f"Intervalle : [{min_val}"
            tooltip += f" - {max_val if max_val != float('inf') else '∞'}]\n"
            if target is not None:
                tooltip += f"Valeur optimale : {target:.1f}\n"
            tooltip += f"Valeur actuelle : {value}\n"
            
            if value < min_val:
                tooltip += f"⬇ Sous le minimum ({min_val - value} de moins)"
            elif max_val != float('inf') and value > max_val:
                tooltip += f"⬆ Au-dessus du maximum ({value - max_val} de plus)"
            else:
                tooltip += "✓ Dans l'intervalle"
                
        return tooltip

    def _apply_interval_coloring(self, item: QTableWidgetItem, value: int, intervals: Dict[str, Dict[str, int]], 
                            is_cat: bool = False, group: str = None):
        """
        Applique la coloration selon les intervalles ou quotas.
        Priorité à la coloration conditionnelle sur les couleurs d'utilisateur.
        """
        if not intervals:
            return
            
        # Variable pour suivre si une coloration a été appliquée
        color_applied = False

        # Pour les CATs, vérifier d'abord les quotas
        if is_cat:
            target = intervals.get('target', 0)
            if target > 0 and value != target:  # Différent du quota prévu
                item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                color_applied = True
        else:
            # Pour les médecins, vérifier les intervalles
            min_val = intervals.get('min', 0)
            max_val = intervals.get('max', float('inf'))
            
            if value < min_val:
                item.setBackground(self.interval_colors['under_min'])  # Vert plus vif
                color_applied = True
            elif max_val != float('inf') and value > max_val:
                item.setBackground(self.interval_colors['over_max'])  # Rouge plus vif
                color_applied = True
        
        # Si aucune coloration conditionnelle n'a été appliquée, appliquer la couleur de base
        if not color_applied:
            if is_cat:
                item.setBackground(QColor('#E8F5E9'))
            # Pour les médecins mi-temps, cela sera géré par l'appelant
        
        # Ajouter le tooltip dans tous les cas
        tooltip = self._get_tooltip_text(value, intervals, is_cat, group)
        item.setToolTip(tooltip)
            

      


    def calculate_weekday_stats(self):
        """
        Calcule les statistiques de semaine en excluant les NL du vendredi
        Retourne un dictionnaire avec les stats par personne et par type de poste
        """
        all_post_types = set(ALL_POST_TYPES)
        if self.custom_posts:
            all_post_types.update(self.custom_posts.keys())
        
        weekday_stats = {
            doctor.name: {post_type: 0 for post_type in all_post_types}
            for doctor in self.doctors
        }
        weekday_stats.update({
            cat.name: {post_type: 0 for post_type in all_post_types}
            for cat in self.cats
        })
        weekday_stats["Non attribué"] = {post_type: 0 for post_type in all_post_types}

        if not self.planning or not self.planning.days:
            return weekday_stats

        for day in self.planning.days:
            is_friday = day.date.weekday() == 4
            
            # Ne compter que les jours de semaine non fériés
            if day.date.weekday() < 5 and not day.is_holiday_or_bridge:
                for slot in day.slots:
                    # Ignorer les NL du vendredi
                    if is_friday and slot.abbreviation == "NL":
                        continue
                    
                    assignee = slot.assignee if slot.assignee in weekday_stats else "Non attribué"
                    weekday_stats[assignee][slot.abbreviation] += 1

        return weekday_stats

    def calculate_weekend_stats(self):
        """
        Calcule les statistiques du weekend en incluant les NLv du vendredi
        Retourne un dictionnaire avec les stats par personne et par type de poste
        """
        all_post_types = set(ALL_POST_TYPES)
        if self.custom_posts:
            all_post_types.update(self.custom_posts.keys())
            
        weekend_stats = {
            doctor.name: {post_type: 0 for post_type in all_post_types}
            for doctor in self.doctors
        }
        weekend_stats.update({
            cat.name: {post_type: 0 for post_type in all_post_types}
            for cat in self.cats
        })
        weekend_stats["Non attribué"] = {post_type: 0 for post_type in all_post_types}

        if not self.planning or not self.planning.days:
            return weekend_stats

        for day in self.planning.days:
            is_weekend = day.date.weekday() in [5, 6]
            is_friday = day.date.weekday() == 4
            is_holiday_or_bridge = day.is_holiday_or_bridge

            # Compter tous les postes du weekend/férié et les NL du vendredi
            if is_weekend or is_holiday_or_bridge or (is_friday and not is_holiday_or_bridge):
                for slot in day.slots:
                    # Pour les vendredis normaux, ne compter que les NL
                    if is_friday and not is_holiday_or_bridge and slot.abbreviation != "NL":
                        continue
                    
                    assignee = slot.assignee if slot.assignee in weekend_stats else "Non attribué"
                    weekend_stats[assignee][slot.abbreviation] += 1

        return weekend_stats

    def calculate_we_lib(self, person_name):
        we_lib = 0
        current_we_start = None
        consecutive_free_days = 0
        
        for day in self.planning.days:
            is_weekend_or_holiday = day.date.weekday() >= 5 or day.is_holiday_or_bridge
            
            if is_weekend_or_holiday:
                if current_we_start is None:
                    current_we_start = day.date
                
                # Vérifier si la personne travaille ce jour-là
                person_works = any(slot.assignee == person_name and
                                ((slot.start_time.time() >= time(3, 0) and day.date == current_we_start) or
                                    (slot.end_time.time() <= time(23, 59) and (day.date - current_we_start).days >= 1))
                                for slot in day.slots)
                
                if person_works:
                    current_we_start = None
                    consecutive_free_days = 0
                else:
                    consecutive_free_days += 1
                    if consecutive_free_days == 2:
                        we_lib += 1
                        current_we_start = None
                        consecutive_free_days = 0
            else:
                current_we_start = None
                consecutive_free_days = 0
        
        return we_lib
    
    
    
    def uniformize_table_style(self, table):
        # Définir une taille de police uniforme
        table.setStyleSheet("font-size: 12px;")

        # Appliquer une taille de ligne uniforme
        table.verticalHeader().setDefaultSectionSize(24)  # Par exemple, 24 pixels de hauteur

        # Appliquer une largeur uniforme pour chaque colonne
        table.horizontalHeader().setDefaultSectionSize(100)  # Largeur par défaut des colonnes

        # Ajuster les colonnes pour remplir l'espace
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
    def clear_stats(self):
        self.planning = None
        self.stats_table.setRowCount(0)
        self.stats_table.setColumnCount(0)
        self.weekend_stats_table.setRowCount(0)
        self.weekend_stats_table.setColumnCount(0)
        self.detailed_stats_table.setRowCount(0)
        self.detailed_stats_table.setColumnCount(0)
        self.weekly_stats_table.setRowCount(0)
        self.weekly_stats_table.setColumnCount(0)
        self.weekday_group_stats_table.setRowCount(0)
        self.weekday_group_stats_table.setColumnCount(0)


    def update_color_coding(self, item: QTableWidgetItem, post_type: str):
        """Met à jour la couleur de fond des cellules en fonction du type de poste"""
        if post_type in self.custom_posts:
            item.setBackground(self.custom_posts[post_type].color)
            
            
            
    
    
    
    
    def setup_scroll_sync(self):
        """Configure la synchronisation du scroll entre tous les tableaux de statistiques"""
        tables = [
            self.stats_table,
            self.weekend_stats_table,
            self.detailed_stats_table,
            self.weekly_stats_table,
            self.weekday_group_stats_table
        ]

        # Synchronisation du scroll vertical
        def sync_vertical_scroll(source_table):
            def _sync_scroll(value):
                # Synchroniser tous les autres tableaux avec la position de scroll de la source
                for table in tables:
                    if table != source_table and table.verticalScrollBar():
                        table.verticalScrollBar().setValue(value)
            return _sync_scroll

        # Synchronisation du scroll horizontal
        def sync_horizontal_scroll(source_table):
            def _sync_scroll(value):
                # Synchroniser tous les autres tableaux avec la position de scroll de la source
                for table in tables:
                    if table != source_table and table.horizontalScrollBar():
                        table.horizontalScrollBar().setValue(value)
            return _sync_scroll

        # Application de la synchronisation à tous les tableaux
        for table in tables:
            if table.verticalScrollBar():
                table.verticalScrollBar().valueChanged.connect(
                    sync_vertical_scroll(table)
                )
            if table.horizontalScrollBar():
                table.horizontalScrollBar().valueChanged.connect(
                    sync_horizontal_scroll(table)
                )
                
                
                
    def get_intervals_tooltip_text(self, post_type: str, doctor_type: str = "full_time") -> str:
        """
        Génère le texte de l'infobulle pour les intervalles d'un poste selon le type de médecin
        
        Args:
            post_type: Type de poste
            doctor_type: Type de médecin ("full_time" ou "half_time")
            
        Returns:
            str: Texte formaté des intervalles
        """
        if not self.planning or not hasattr(self.planning, 'pre_analysis_results'):
            return ""
            
        intervals = {}
        for doctor in self.doctors:
            if (doctor_type == "full_time" and doctor.half_parts == 2) or \
            (doctor_type == "half_time" and doctor.half_parts == 1):
                doctor_intervals = self.planning.pre_analysis_results.get('ideal_distribution', {}).get(doctor.name, {})
                weekday_intervals = doctor_intervals.get('weekday_posts', {}).get(post_type, {})
                weekend_intervals = doctor_intervals.get('weekend_posts', {}).get(post_type, {})
                
                if weekday_intervals or weekend_intervals:
                    intervals['weekday'] = weekday_intervals
                    intervals['weekend'] = weekend_intervals

        if not intervals:
            return ""

        tooltip_text = []
        if doctor_type == "full_time":
            tooltip_text.append("Intervalles temps plein:")
        else:
            tooltip_text.append("Intervalles mi-temps:")

        for period, data in intervals.items():
            if data:
                min_val = data.get('min', 0)
                max_val = data.get('max', float('inf'))
                if period == 'weekday':
                    text = f"  Semaine: {min_val}-{max_val if max_val != float('inf') else '∞'}"
                else:
                    text = f"  Weekend: {min_val}-{max_val if max_val != float('inf') else '∞'}"
                tooltip_text.append(text)

        return "\n".join(tooltip_text)

    def get_enhanced_post_tooltip(self, post_type: str, existing_tooltip: str = "") -> str:
        """
        Crée une infobulle enrichie combinant l'information existante et les intervalles
        """
        full_time_intervals = self.get_intervals_tooltip_text(post_type, "full_time")
        half_time_intervals = self.get_intervals_tooltip_text(post_type, "half_time")
        
        tooltip_parts = []
        if existing_tooltip:
            tooltip_parts.append(existing_tooltip)
        if full_time_intervals:
            tooltip_parts.append(full_time_intervals)
        if half_time_intervals:
            tooltip_parts.append(half_time_intervals)
            
        return "\n\n".join(tooltip_parts)



    def setup_highlighting(self, table):
        """Configure les gestionnaires d'événements pour la mise en surbrillance des lignes et colonnes"""
        table.setMouseTracking(True)
        table.cellEntered.connect(lambda row, col: self.highlight_cell(table, row, col))
        table.leaveEvent = lambda event: self.clear_highlights(table)
        
    def highlight_cell(self, table, row, col):
        """Met en surbrillance une ligne ou colonne lors du survol"""
        # Restaurer l'état normal des cellules
        self.clear_highlights(table)
        
        # Mémoriser la cellule actuelle pour le contexte de menu
        table.setProperty("current_row", row)
        table.setProperty("current_col", col)
        
    def clear_highlights(self, table):
        """Efface les mises en surbrillance du tableau"""
        table.setProperty("highlighted_row", -1)
        table.setProperty("highlighted_col", -1)
        # Forcer le rafraîchissement
        table.viewport().update()
        
    def set_row_highlight(self, table, row):
        """Active la mise en surbrillance permanente d'une ligne"""
        self.highlighted_row = row
        self.highlighted_col = -1
        
        # Appliquer le style de bordure à toutes les cellules de la ligne
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, "highlighted_row")
                
        # Forcer le rafraîchissement
        table.viewport().update()
        
    def set_column_highlight(self, table, col):
        """Active la mise en surbrillance permanente d'une colonne"""
        self.highlighted_col = col
        self.highlighted_row = -1
        
        # Appliquer le style de bordure à toutes les cellules de la colonne
        for row in range(table.rowCount()):
            item = table.item(row, col)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, "highlighted_col")
                
        # Forcer le rafraîchissement
        table.viewport().update()
        
    def clear_all_highlights(self):
        """Efface toutes les mises en surbrillance de tous les tableaux"""
        self.highlighted_row = -1
        self.highlighted_col = -1
        
        tables = [self.stats_table, self.weekend_stats_table, 
                self.detailed_stats_table, self.weekly_stats_table, 
                self.weekday_group_stats_table]
                
        for table in tables:
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        item.setData(Qt.ItemDataRole.UserRole, None)
            
            # Forcer le rafraîchissement
            table.viewport().update()
            
    def sort_table(self, table, col):
        """Trie le tableau selon la colonne cliquée avec un indicateur de tri amélioré"""
        table_id = table.property("table_id")
        
        # Vérifier si c'est la colonne "Assigné à"
        if col == 0:
            # Réinitialiser l'ordre de tri et retourner à l'ordre original
            self.sort_order[table_id] = {}
            self._restore_original_order(table)
            return
            
        # Déterminer l'ordre de tri
        if col in self.sort_order.get(table_id, {}):
            # Inverser l'ordre actuel
            order = not self.sort_order[table_id][col]
        else:
            # Par défaut: tri ascendant
            order = True
            
        # Mettre à jour l'ordre de tri pour cette colonne
        if table_id not in self.sort_order:
            self.sort_order[table_id] = {}
        self.sort_order[table_id] = {col: order}  # Réinitialiser pour n'avoir qu'une colonne triée
        
        # Obtenir les données à trier (uniquement les lignes des utilisateurs)
        data = []
        # Toujours exclure "Non attribué" et "Total" du tri
        sort_range = table.rowCount() - 2
        
        # Sauvegarder les lignes "Non attribué" et "Total"
        unassigned_data = {}
        total_data = {}
        for c in range(table.columnCount()):
            unassigned_item = table.item(table.rowCount() - 2, c)
            total_item = table.item(table.rowCount() - 1, c)
            if unassigned_item:
                unassigned_data[c] = {
                    'text': unassigned_item.text(),
                    'background': unassigned_item.background(),
                    'font': unassigned_item.font(),
                    'tooltip': unassigned_item.toolTip()
                }
            if total_item:
                total_data[c] = {
                    'text': total_item.text(),
                    'background': total_item.background(),
                    'font': total_item.font(),
                    'tooltip': total_item.toolTip()
                }
        
        # Trier uniquement les lignes des utilisateurs
        for row in range(sort_range):
            # Obtenir la valeur de la cellule
            item = table.item(row, col)
            if item:
                try:
                    value = int(item.text())
                except ValueError:
                    value = item.text()
                    
                # Enregistrer la valeur avec son index de ligne et toutes les données de la ligne
                row_data = {}
                for c in range(table.columnCount()):
                    cell = table.item(row, c)
                    if cell:
                        row_data[c] = {
                            'text': cell.text(),
                            'background': cell.background(),
                            'font': cell.font(),
                            'tooltip': cell.toolTip()
                        }
                data.append((row, value, row_data))
        
        # Trier les données
        data.sort(key=lambda x: x[1], reverse=not order)
        
        # Réorganiser les lignes des utilisateurs selon le tri
        for new_idx, (old_idx, _, row_data) in enumerate(data):
            for c, cell_data in row_data.items():
                new_item = QTableWidgetItem(cell_data['text'])
                new_item.setBackground(cell_data['background'])
                new_item.setFont(cell_data['font'])
                new_item.setToolTip(cell_data['tooltip'])
                table.setItem(new_idx, c, new_item)
                
        # Restaurer les lignes "Non attribué" et "Total" à leur position
        for c, cell_data in unassigned_data.items():
            new_item = QTableWidgetItem(cell_data['text'])
            new_item.setBackground(cell_data['background'])
            new_item.setFont(cell_data['font'])
            new_item.setToolTip(cell_data['tooltip'])
            table.setItem(table.rowCount() - 2, c, new_item)
            
        for c, cell_data in total_data.items():
            new_item = QTableWidgetItem(cell_data['text'])
            new_item.setBackground(cell_data['background'])
            new_item.setFont(cell_data['font'])
            new_item.setToolTip(cell_data['tooltip'])
            table.setItem(table.rowCount() - 1, c, new_item)
            for c, cell_data in row_data.items():
                new_item = QTableWidgetItem(cell_data['text'])
                new_item.setBackground(cell_data['background'])
                new_item.setFont(cell_data['font'])
                new_item.setToolTip(cell_data['tooltip'])
                table.setItem(new_idx, c, new_item)
        
        # Mettre à jour les en-têtes
        for c in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(c)
            if header_item:
                # Récupérer le texte de base (sans flèche)
                base_text = header_item.text().replace(" ▲", "").replace(" ▼", "")
                
                # Ajouter la flèche uniquement à la colonne triée
                if c == col:
                    arrow = " ▲" if order else " ▼"
                    header_item.setText(base_text + arrow)
                else:
                    header_item.setText(base_text)
                    
    def _restore_original_order(self, table):
        """Restaure l'ordre original du tableau"""
        # Récupérer toutes les données du tableau
        data = []
        for row in range(table.rowCount()):
            row_data = {}
            name_item = table.item(row, 0)
            if name_item:
                # Déterminer la priorité de tri
                if name_item.text() == "Total":
                    priority = 3
                elif name_item.text() == "Non attribué":
                    priority = 2
                else:
                    # Médecins temps plein, puis mi-temps, puis CATs
                    is_cat = name_item.font().bold()
                    is_half_time = name_item.background().color() == QColor(230, 230, 230, 255)
                    if is_cat:
                        priority = 1.3
                    elif is_half_time:
                        priority = 1.2
                    else:
                        priority = 1.1
                        
                # Sauvegarder les données de la ligne
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        row_data[col] = {
                            'text': item.text(),
                            'background': item.background(),
                            'font': item.font(),
                            'tooltip': item.toolTip()
                        }
                data.append((priority, name_item.text(), row_data))
        
        # Trier les données
        data.sort(key=lambda x: (x[0], x[1]))
        
        # Réappliquer les données triées
        for new_idx, (_, _, row_data) in enumerate(data):
            for col, cell_data in row_data.items():
                new_item = QTableWidgetItem(cell_data['text'])
                new_item.setBackground(cell_data['background'])
                new_item.setFont(cell_data['font'])
                new_item.setToolTip(cell_data['tooltip'])
                table.setItem(new_idx, col, new_item)
        
        # Nettoyer tous les indicateurs de tri
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            if header_item:
                base_text = header_item.text().replace(" ▲", "").replace(" ▼", "")
                header_item.setText(base_text)

class CustomTableWidget(QTableWidget):
    """Widget de tableau personnalisé avec système de réticule et tri amélioré"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_reticle = {'row': -1, 'col': -1}
        self.fixed_reticles = []  # Pour les réticules "figés"
        self.hover_reticle = {'row': -1, 'col': -1}  # Pour le réticule au survol
        
        # Configuration de base
        self.setMouseTracking(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Désactiver l'édition
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)  # Désactiver la sélection standard
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Désactiver le focus visuel
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Connexion des signaux
        self.cellClicked.connect(self.handle_cell_click)
        self.cellDoubleClicked.connect(self.handle_cell_double_click)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, pos):
        """Affiche le menu contextuel avec l'option de supprimer les réticules"""
        menu = QMenu(self)
        clear_action = QAction("Supprimer les réticules", self)
        clear_action.triggered.connect(self.clear_all_reticles)
        menu.addAction(clear_action)
        menu.exec(self.mapToGlobal(pos))
        
    def clear_all_reticles(self):
        """Supprime tous les réticules fixes"""
        self.fixed_reticles = []
        self.current_reticle = {'row': -1, 'col': -1}
        self.viewport().update()
        
    def handle_cell_click(self, row, col):
        """Gère le clic sur une cellule"""
        # Ignorer les clics sur les en-têtes
        if row == 0:
            return
            
        # Si on clique sur une cellule avec un réticule fixe, on le supprime
        if any(r['row'] == row and r['col'] == col for r in self.fixed_reticles):
            self.fixed_reticles = [r for r in self.fixed_reticles if not (r['row'] == row and r['col'] == col)]
        else:
            # Sinon, on remplace le réticule courant
            self.current_reticle = {'row': row, 'col': col}
        self.viewport().update()
        
    def handle_cell_double_click(self, row, col):
        """Gère le double-clic pour figer le réticule courant"""
        # Ignorer les double-clics sur les en-têtes
        if row == 0:
            return
            
        # Si un réticule fixe existe déjà à cet endroit, le supprimer
        if any(r['row'] == row and r['col'] == col for r in self.fixed_reticles):
            self.fixed_reticles = [r for r in self.fixed_reticles if not (r['row'] == row and r['col'] == col)]
        else:
            # Sinon, ajouter un nouveau réticule fixe
            self.fixed_reticles.append({'row': row, 'col': col})
        
        # Réinitialiser le réticule courant
        self.current_reticle = {'row': -1, 'col': -1}
        self.viewport().update()
        
    def leaveEvent(self, event):
        """Gère la sortie du widget"""
        self.hover_reticle = {'row': -1, 'col': -1}
        self.viewport().update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Gère le survol des cellules"""
        row = self.rowAt(int(event.position().y()))
        col = self.columnAt(int(event.position().x()))
        if row >= 0 and col >= 0:
            self.hover_reticle = {'row': row, 'col': col}
        else:
            self.hover_reticle = {'row': -1, 'col': -1}
        self.viewport().update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        """Surcharge de l'événement de dessin pour ajouter les réticules"""
        super().paintEvent(event)
        
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dessiner le réticule de survol (le plus discret)
        if self.hover_reticle['row'] > 0 and self.hover_reticle['col'] >= 0:
            self._draw_reticle(painter, self.hover_reticle['row'], self.hover_reticle['col'], 
                             QColor(0, 120, 215, 30), 1)  # Bleu très transparent et fin
        
        # Dessiner les réticules fixes
        for reticle in self.fixed_reticles:
            if reticle['row'] > 0:  # Ne pas dessiner sur les en-têtes
                self._draw_reticle(painter, reticle['row'], reticle['col'], 
                                 QColor(0, 120, 215, 120), 2)  # Bleu semi-transparent
            
        # Dessiner le réticule courant (le plus visible)
        if self.current_reticle['row'] > 0 and self.current_reticle['col'] >= 0:
            self._draw_reticle(painter, self.current_reticle['row'], self.current_reticle['col'], 
                             QColor(0, 120, 215, 180), 2)  # Bleu plus visible
            
        painter.end()
        
    def _draw_reticle(self, painter, row, col, color, width=2):
        """Dessine un réticule comme un cadre autour de la ligne et de la colonne"""
        pen = QPen(color, width)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        
        # Obtenir les dimensions complètes du viewport
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        # Calculer les rectangles pour la ligne et la colonne
        # Pour la ligne, prendre toute la largeur du viewport
        row_rect = self.visualItemRect(self.item(row, 0))
        row_rect.setLeft(0)
        row_rect.setWidth(viewport_width)
        
        # Pour la colonne, prendre toute la hauteur du viewport
        col_rect = self.visualItemRect(self.item(0, col))
        col_rect.setTop(0)
        col_rect.setHeight(viewport_height)
        
        # Ajuster les dimensions pour éviter la superposition avec la grille
        row_rect.setHeight(row_rect.height() - 1)
        col_rect.setWidth(col_rect.width() - 1)
        
        # Dessiner les rectangles
        painter.drawRect(row_rect)
        painter.drawRect(col_rect)

class DetailedGroupHeader(QTableWidgetItem):
    """Classe personnalisée pour les en-têtes de groupe avec fonctionnalité d'expansion"""
    def __init__(self, group_name, components=None):
        super().__init__(group_name)
        self.group_name = group_name
        self.components = components or []
        self.is_expanded = False
        
class AnimatedDetailedGroupHeader(DetailedGroupHeader):
    """En-tête de groupe amélioré avec indicateur d'expansion"""
    def __init__(self, group_name, components=None):
        super().__init__(group_name, components)
        self._arrow_expanded = "▼"
        self._arrow_collapsed = "►"
        self._update_text()

    def _update_text(self):
        """Met à jour le texte avec l'indicateur approprié"""
        arrow = self._arrow_expanded if self.is_expanded else self._arrow_collapsed
        self.setText(f"{arrow} {self.group_name}")

    def toggle_expansion(self):
        """Change l'état d'expansion et met à jour l'indicateur"""
        self.is_expanded = not self.is_expanded
        self._update_text()

class ColumnAnimation:
    """Gère l'animation des colonnes lors de l'expansion/réduction avec une approche compatible Qt6"""
    def __init__(self, table, start_col, end_col):
        self.table = table
        self.start_col = start_col
        self.end_col = end_col
        self.animations = []
        self.original_widths = {}
        self.base_duration = 200
        self.duration = self.base_duration + (end_col - start_col + 1) * 50
        self.timers = []  # Pour garder une référence aux timers

    def expand(self):
        """Anime l'expansion des colonnes sans utiliser sectionSize"""
        header = self.table.horizontalHeader()
        font_metrics = QFontMetrics(header.font())
        
        # Calcul des largeurs optimales et sauvegarde des largeurs originales
        target_widths = {}
        for col in range(self.start_col, self.end_col + 1):
            self.original_widths[col] = self.table.columnWidth(col)
            
            # Calculer une largeur raisonnable basée sur le contenu
            header_width = font_metrics.horizontalAdvance(self.table.horizontalHeaderItem(col).text()) + 20
            
            max_content_width = header_width
            for row in range(self.table.rowCount()):
                item = self.table.item(row, col)
                if item:
                    content_width = font_metrics.horizontalAdvance(item.text()) + 10
                    max_content_width = max(max_content_width, content_width)
            
            target_widths[col] = min(max_content_width, 150)  # Limite raisonnable

        # Animation progressive par étapes et timers
        steps = 10  # Nombre d'étapes pour l'animation
        
        def animate_step(col, current_step, total_steps, start_width, target_width):
            progress = current_step / total_steps
            # Fonction d'easing simple pour un effet plus naturel
            eased_progress = 1 - pow(1 - progress, 3)  # Easing cubique
            new_width = int(start_width + (target_width - start_width) * eased_progress)
            
            # Appliquer la nouvelle largeur
            self.table.setColumnWidth(col, new_width)
            
            # Si ce n'est pas la dernière étape, planifier la suivante
            if current_step < total_steps:
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(
                    lambda col=col, step=current_step+1: 
                    animate_step(col, step, total_steps, start_width, target_width)
                )
                # Convertir en entier pour éviter l'erreur
                timer_ms = int(self.duration / total_steps)
                timer.start(timer_ms)
                self.timers.append(timer)
        
        # Lancer l'animation pour chaque colonne avec un délai cascade
        for idx, col in enumerate(range(self.start_col, self.end_col + 1)):
            # Rendre la colonne visible avant d'animer
            self.table.setColumnHidden(col, False)
            
            # Configuration initiale
            start_width = 0
            self.table.setColumnWidth(col, start_width)
            
            # Créer un timer pour le délai en cascade
            start_timer = QTimer()
            start_timer.setSingleShot(True)
            start_timer.timeout.connect(
                lambda col=col, width=start_width, target=target_widths[col]: 
                animate_step(col, 1, steps, width, target)
            )
            start_timer.start(idx * 50)  # Délai en cascade (déjà un entier)
            self.timers.append(start_timer)

    def collapse(self):
        """Anime la réduction des colonnes sans utiliser sectionSize"""
        steps = 8  # Moins d'étapes pour la réduction
        
        def animate_step(col, current_step, total_steps, start_width):
            progress = current_step / total_steps
            # Fonction d'easing simple
            eased_progress = pow(progress, 2)  # Easing quadratique
            new_width = int(start_width * (1 - eased_progress))
            
            # Appliquer la nouvelle largeur
            self.table.setColumnWidth(col, new_width)
            
            # Si c'est la dernière étape, masquer la colonne
            if current_step == total_steps:
                self.table.setColumnHidden(col, True)
                # Restaurer la largeur originale pour la prochaine utilisation
                if col in self.original_widths:
                    self.table.setColumnWidth(col, self.original_widths[col])
            elif current_step < total_steps:
                # Sinon planifier la prochaine étape
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(
                    lambda col=col, step=current_step+1: 
                    animate_step(col, step, total_steps, start_width)
                )
                # Convertir en entier pour éviter l'erreur
                timer_ms = int(self.duration / total_steps)
                timer.start(timer_ms)
                self.timers.append(timer)
        
        # Lancer l'animation pour chaque colonne avec un délai cascade inversé
        for idx, col in enumerate(reversed(range(self.start_col, self.end_col + 1))):
            start_width = self.table.columnWidth(col)
            
            # Créer un timer pour le délai en cascade
            start_timer = QTimer()
            start_timer.setSingleShot(True)
            start_timer.timeout.connect(
                lambda col=col, width=start_width: 
                animate_step(col, 1, steps, width)
            )
            start_timer.start(idx * 40)  # Délai en cascade inversé (déjà un entier)
            self.timers.append(start_timer)