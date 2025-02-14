# © 2024 HILAL Arkane. Tous droits réservés.
# gui/stats_view.py
import sys
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QPushButton
from PyQt6.QtGui import QBrush, QFont, QColor, QIcon
from gui.styles import color_system, ACTION_BUTTON_STYLE
from PyQt6.QtCore import Qt
from core.Constantes.models import ALL_POST_TYPES
from core.Constantes.data_persistence import DataPersistence
from gui.post_configuration import PostConfig   
import numpy as np
from datetime import datetime, time, date
from typing import List, Dict, Optional, Tuple, Union
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt, QSize
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPainter, QFontMetrics
from workalendar.europe import France
# Initialiser le logger
logger = logging.getLogger(__name__)


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
        
        # Récupération des couleurs depuis le système centralisé
        self.post_groups_colors = color_system.get_post_group_colors()

        # Définition des groupes de postes comme attribut de classe
        self.post_groups = {
            'matin': {
                'label': 'Matin',
                'posts': ['MM', 'CM', 'HM', 'SM', 'RM', 'ML', 'MC'],
                'color': self.post_groups_colors['matin']
            },
            'apresMidi': {
                'label': 'Après-midi',
                'posts': ['CA', 'HA', 'SA', 'RA', 'AL', 'AC'],
                'color': self.post_groups_colors['apresMidi']
            },
            'soirNuit': {
                'label': 'Soir/Nuit',
                'posts': ['CS', 'HS', 'SS', 'RS', 'NL', 'NM', 'NA', 'NC'],
                'color': self.post_groups_colors['soirNuit']
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

    def init_ui(self):
        """Initialise l'interface utilisateur complète"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Conteneur du bouton de détachement
        detach_container = QWidget()
        detach_layout = QHBoxLayout(detach_container)
        detach_layout.setContentsMargins(5, 5, 5, 5)
        
        # Bouton de détachement avec style
        detach_button = QPushButton("Détacher les statistiques")
        detach_button.setStyleSheet(ACTION_BUTTON_STYLE)
        detach_button.setMinimumHeight(35)
        detach_button.setIcon(QIcon("icons/detach.png"))
        detach_button.clicked.connect(self.on_detach_clicked)
        
        detach_layout.addStretch(1)
        detach_layout.addWidget(detach_button)
        main_layout.addWidget(detach_container)
        
        # Création des tableaux de statistiques
        self.stats_table = QTableWidget()
        self.weekend_stats_table = QTableWidget()
        self.detailed_stats_table = QTableWidget()
        self.weekly_stats_table = QTableWidget()
        self.weekday_group_stats_table = QTableWidget()
        
        # Conteneur des boutons de filtre
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
        
        # Configuration des onglets
        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        
        def setup_table_in_tab(table, title):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.addWidget(table)
            
            # Configuration commune des tableaux
            table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
            table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
            table.horizontalHeader().setFixedHeight(30)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setShowGrid(True)
            table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #E0E0E0;
                    border: none;
                }
                QHeaderView::section {
                    background-color: #F5F5F5;
                    border: 1px solid #E0E0E0;
                    padding: 5px;
                }
            """)
            
            tab_widget.addTab(container, title)
        
        # Configuration des onglets avec leurs tableaux respectifs
        setup_table_in_tab(self.stats_table, "Statistiques générales")
        setup_table_in_tab(self.weekend_stats_table, "Statistiques weekend")
        setup_table_in_tab(self.detailed_stats_table, "Groupes Weekend")
        setup_table_in_tab(self.weekly_stats_table, "Statistiques semaine")
        setup_table_in_tab(self.weekday_group_stats_table, "Groupes semaine")
        
        main_layout.addWidget(tab_widget)
        
        # Configuration de la synchronisation du défilement
        self.setup_scroll_sync()
        
        # Initialisation des données si disponibles
        if self.planning and self.doctors and self.cats:
            self.update_stats()
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
        # Utilisation du système de couleurs centralisé
        weekend_group_colors = color_system.get_weekend_group_colors()

        # Réinitialisation des listes de postes dans les groupes
        self.post_groups = {
            'matin': {
                'label': 'Matin',
                'posts': ['MM', 'CM', 'HM', 'SM', 'RM', 'ML', 'MC'],
                'color': self.post_groups_colors['matin']
            },
            'apresMidi': {
                'label': 'Après-midi',
                'posts': ['CA', 'HA', 'SA', 'RA', 'AL', 'AC','CT'],
                'color': self.post_groups_colors['apresMidi']
            },
            'soirNuit': {
                'label': 'Soir/Nuit',
                'posts': ['CS', 'HS', 'SS', 'RS', 'NL', 'NM', 'NA', 'NC'],
                'color': self.post_groups_colors['soirNuit']
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




    def update_stats_table(self, stats, table):
        sorted_doctors = sorted([d.name for d in self.doctors], key=str.lower)
        sorted_cats = sorted([c.name for c in self.cats], key=str.lower)
        sorted_assignees = sorted_doctors + sorted_cats + ["Non attribué"]
        all_posts = self.get_all_post_types()

        table.setRowCount(len(sorted_assignees) + 1)
        table.setColumnCount(len(all_posts) + 2)

        headers = ["Assigné à"] + all_posts + ["Total"]
        table.setHorizontalHeaderLabels(headers)

        total_row = {post_type: 0 for post_type in all_posts}
        total_row["Total"] = 0

        for row, assignee in enumerate(sorted_assignees):
            table.setItem(row, 0, QTableWidgetItem(str(assignee)))
            assignee_stats = stats.get(assignee, {})

            assignee_total = 0
            for col, post_type in enumerate(all_posts, start=1):
                count = assignee_stats.get(post_type, 0)
                item = QTableWidgetItem(str(count))
                
                # Appliquer la couleur de fond pour les postes personnalisés en gérant les erreurs
                if hasattr(self, 'custom_posts') and post_type in self.custom_posts:
                    custom_post = self.custom_posts[post_type]
                    if hasattr(custom_post, 'color'):
                        item.setBackground(QBrush(custom_post.color))
                    elif isinstance(custom_post, dict) and 'color' in custom_post:
                        # Si c'est encore un dictionnaire, créer la couleur à partir de la valeur
                        item.setBackground(QBrush(QColor(custom_post['color'])))
                    else:
                        # Couleur par défaut si aucune n'est définie
                        item.setBackground(QBrush(QColor("#E6F3FF")))
                
                table.setItem(row, col, item)
                assignee_total += count
                total_row[post_type] += count

            table.setItem(row, len(all_posts) + 1, QTableWidgetItem(str(assignee_total)))
            total_row["Total"] += assignee_total

            # Griser les lignes des médecins à 1 demi-part
            doctor = next((d for d in self.doctors if d.name == assignee), None)
            if doctor and doctor.half_parts == 1:
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(QBrush(QColor(240, 240, 240)))

        self.add_total_row(table, total_row, all_posts)
    
    def add_total_row(self, table, total_row, all_posts):
        """Ajoute la ligne des totaux au tableau"""
        last_row = table.rowCount() - 1
        table.setItem(last_row, 0, QTableWidgetItem("Total"))
        for col, post_type in enumerate(all_posts, start=1):
            table.setItem(last_row, col, QTableWidgetItem(str(total_row[post_type])))
        table.setItem(last_row, len(all_posts) + 1, QTableWidgetItem(str(total_row["Total"])))
        
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
        """Version modifiée de create_stats_table utilisant les intervalles combinés"""
        stats = self.calculate_stats()
        self.stats_table.clear()

        # Initialisation du tableau avec toutes les colonnes
        all_posts = []
        for group in self.post_groups.values():
            all_posts.extend(group['posts'])

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
            # Nom avec badge CAT si nécessaire
            name_item = QTableWidgetItem(person.name)
            if not hasattr(person, 'half_parts'):  # C'est un CAT
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))
            elif person.half_parts == 1:  # Mi-temps
                name_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
            self.stats_table.setItem(row, 0, name_item)

            # Pour les médecins, récupérer les intervalles combinés
            combined_intervals = {}
            if hasattr(person, 'half_parts'):
                combined_intervals = self._get_combined_intervals(person.name)

            # Valeurs des postes
            row_total = 0
            for col, post_type in enumerate(all_posts, start=1):
                count = stats.get(person.name, {}).get(post_type, 0)
                item = QTableWidgetItem(str(count))
                
                # Gestion de la coloration
                if hasattr(person, 'half_parts'):
                    if person.half_parts == 1:
                        item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                        
                    # Coloration selon les intervalles combinés pour les médecins
                    if post_type in combined_intervals:
                        min_val = combined_intervals[post_type]['min']
                        max_val = combined_intervals[post_type]['max']
                        if count < min_val:
                            item.setBackground(QColor(200, 255, 200, 255))  # Vert plus vif
                        elif max_val != float('inf') and count > max_val:
                            item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif
                    
                if post_type in self.custom_posts:
                    item.setBackground(self.custom_posts[post_type].color)
                    
                self.stats_table.setItem(row, col, item)
                row_total += count

            # Total de la ligne
            total_item = QTableWidgetItem(str(row_total))
            if hasattr(person, 'half_parts') and person.half_parts == 1:
                total_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
            self.stats_table.setItem(row, len(all_posts) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row(len(all_personnel), stats, all_posts)
        self._add_total_row(len(all_personnel) + 1, stats, all_posts)

        # Configuration de l'affichage
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setAlternatingRowColors(False)

        # Application du filtre actuel
        self._apply_filter_to_table(self.stats_table)

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

    def _filter_posts(self, group_key):
        """Filtre les colonnes affichées selon le groupe sélectionné"""
        # Mise à jour des boutons
        for key, btn in self.filter_buttons.items():
            btn.setChecked(key == group_key)

        # Affichage/masquage des colonnes
        for col in range(1, self.stats_table.columnCount() - 1):  # Exclure la colonne nom et total
            header_item = self.stats_table.horizontalHeaderItem(col)
            post = header_item.text()
            
            if group_key == 'all':
                self.stats_table.setColumnHidden(col, False)
            else:
                # Vérifier si le poste appartient au groupe sélectionné
                visible = False
                if group_key in self.post_groups and post in self.post_groups[group_key]['posts']:
                    visible = True
                self.stats_table.setColumnHidden(col, not visible)

        # Recalcul des totaux visibles
        self._update_visible_totals
        
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
                total_item = QTableWidgetItem(str(visible_total))
                total_item.setBackground(background)
                total_item.setFont(font)
                table.setItem(row, table.columnCount() - 1, total_item)

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
    def _add_unassigned_row(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des postes non attribués"""
        unassigned_stats = stats.get("Non attribué", {})
        unassigned_total = 0
        
        # Cellule du nom
        name_item = QTableWidgetItem("Non attribué")
        name_item.setBackground(QColor('#F5F5F5'))
        self.stats_table.setItem(row_index, 0, name_item)
        
        # Valeurs par poste
        for col, post_type in enumerate(all_posts, start=1):
            count = unassigned_stats.get(post_type, 0)
            item = QTableWidgetItem(str(count))
            item.setBackground(QColor('#F5F5F5'))
            self.stats_table.setItem(row_index, col, item)
            unassigned_total += count
        
        # Total
        total_item = QTableWidgetItem(str(unassigned_total))
        total_item.setBackground(QColor('#F5F5F5'))
        self.stats_table.setItem(row_index, len(all_posts) + 1, total_item)

    def _add_total_row(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des totaux"""
        # Cellule du nom
        name_item = QTableWidgetItem("Total")
        name_item.setBackground(QColor('#EEEEEE'))
        name_item.setFont(QFont("", -1, QFont.Weight.Bold))
        self.stats_table.setItem(row_index, 0, name_item)
        
        # Calcul des totaux par poste
        grand_total = 0
        for col, post_type in enumerate(all_posts, start=1):
            total = sum(person_stats.get(post_type, 0) 
                    for person_stats in stats.values())
            item = QTableWidgetItem(str(total))
            item.setBackground(QColor('#EEEEEE'))
            item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.stats_table.setItem(row_index, col, item)
            grand_total += total
        
        # Total général
        final_total = QTableWidgetItem(str(grand_total))
        final_total.setBackground(QColor('#EEEEEE'))
        final_total.setFont(QFont("", -1, QFont.Weight.Bold))
        self.stats_table.setItem(row_index, len(all_posts) + 1, final_total)


    def update_detailed_stats_table(self, detailed_stats):
        """Mise à jour de l'onglet des groupes weekend avec fonctionnalité d'expansion"""
        self.detailed_stats_table.clear()
        self.expanded_group = None
        self.component_columns.clear()

        # Mettre à jour les composants des groupes avec les postes personnalisés
        self._update_group_components()

        # Configuration des couleurs selon le système d'exploitation
        if sys.platform == 'win32':
            weekend_group_colors = {
                'gardes': QColor(180, 220, 255, 255),      # Bleu plus vif
                'visites': QColor(255, 200, 150, 255),     # Orange plus vif
                'consultations': QColor(220, 180, 255, 255) # Violet plus vif
            }
        else:
            weekend_group_colors = {
                'gardes': QColor('#E3F2FD'),
                'visites': QColor('#FFF3E0'),
                'consultations': QColor('#EDE7F6')
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
        
        # Modifier la création des en-têtes pour utiliser AnimatedDetailedGroupHeader
        for col, group in enumerate(all_groups, start=1):
            header_item = AnimatedDetailedGroupHeader(
                group, 
                self.group_details.get(group, {}).get('components', [])
            )
            self.detailed_stats_table.setHorizontalHeaderItem(col, header_item)
        
            
            # Coloration selon la catégorie
            for category in weekend_groups.values():
                if group in category['groups']:
                    header_item.setBackground(category['color'])
                    
                    # Ajout d'une infobulle explicative
                    tooltip = self.get_group_tooltip(group)
                    header_item.setToolTip(tooltip)
                    break
                # Configuration des événements d'en-tête
        self.detailed_stats_table.horizontalHeader().sectionClicked.connect(self._handle_header_click)


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
            base_color = QColor('#E8F5E9') if is_cat else (QColor('#F3F4F6') if is_half_time else None)
            
            # Nom avec distinction CAT/mi-temps
            name_item = QTableWidgetItem(person.name)
            if is_cat:
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
            if base_color:
                name_item.setBackground(base_color)
            self.detailed_stats_table.setItem(row, 0, name_item)

            # Valeurs des groupes
            row_total = 0
            for col, group in enumerate(all_groups, start=1):
                count = detailed_stats.get(person.name, {}).get(group, 0)
                item = QTableWidgetItem(str(count))
                
                # Appliquer la couleur de base pour CAT ou mi-temps
                if base_color:
                    item.setBackground(base_color)
                # Pour les médecins à temps plein uniquement, appliquer la coloration conditionnelle
                elif hasattr(person, 'half_parts') and person.half_parts == 2:
                    intervals = ideal_intervals.get(person.name, {}).get('weekend_groups', {}).get(group, {})
                    if intervals:
                        min_val = intervals.get('min', 0)
                        max_val = intervals.get('max', float('inf'))
                        if count < min_val:
                            item.setBackground(QColor(200, 255, 200, 255))  # Vert plus vif pour Windows
                        elif count > max_val:
                            item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif pour Windows
                        else:
                            item.setBackground(QBrush())  # Blanc si dans l'intervalle
                
                self.detailed_stats_table.setItem(row, col, item)
                row_total += count

            # Total de la ligne avec la même coloration de base
            total_item = QTableWidgetItem(str(row_total))
            if base_color:
                total_item.setBackground(base_color)
            self.detailed_stats_table.setItem(row, len(all_groups) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row_detailed(len(all_personnel), detailed_stats, all_groups)
        self._add_total_row_detailed(len(all_personnel) + 1, detailed_stats, all_groups)

        # Configuration de l'affichage
        self.detailed_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.detailed_stats_table.verticalHeader().setVisible(False)
        self.detailed_stats_table.setAlternatingRowColors(False)

        # Application du filtre actuel
        self._apply_filter_to_table(self.detailed_stats_table)

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
        """Gère le clic sur un en-tête de colonne"""
        if logical_index == 0 or logical_index == self.detailed_stats_table.columnCount() - 1:
            return  # Ignorer les clics sur 'Assigné à' et 'Total'

        header_item = self.detailed_stats_table.horizontalHeaderItem(logical_index)
        if not isinstance(header_item, DetailedGroupHeader):
            return

        if self.expanded_group == header_item.group_name:
            # Cacher les composants du groupe actuel
            self._collapse_group(header_item.group_name)
            self.expanded_group = None
        else:
            # Cacher les composants du groupe précédent s'il y en a un
            if self.expanded_group:
                self._collapse_group(self.expanded_group)
            
            # Montrer les composants du nouveau groupe
            self._expand_group(header_item.group_name)
            self.expanded_group = header_item.group_name

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
        """Version améliorée de l'expansion de groupe avec animation"""
        components = self.group_details[group_name]['components']
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

        # Insérer et préparer les colonnes des composants
        current_column = group_index + 1
        self.component_columns[group_name] = []
        stats = self.calculate_weekend_component_stats()

        # Créer les colonnes masquées initialement
        for component in components:
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
                base_color = QColor('#E8F5E9') if is_cat else (QColor('#F3F4F6') if is_half_time else None)
                
                # Appliquer la couleur de base pour CAT ou mi-temps, sans condition
                if is_half_time:
                    item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                elif is_cat:
                    item.setBackground(QColor('#E8F5E9'))
                
                self.detailed_stats_table.setItem(row, current_column, item)
            
            self.component_columns[group_name].append(current_column)
            current_column += 1

        # Lancer l'animation d'expansion
        animation = ColumnAnimation(
            self.detailed_stats_table,
            group_index + 1,
            group_index + len(components)
        )
        animation.expand()

    def _collapse_group(self, group_name):
        """Version améliorée de la réduction de groupe avec animation"""
        if group_name not in self.component_columns:
            return

        # Mettre à jour l'indicateur
        group_index = -1
        for i in range(self.detailed_stats_table.columnCount()):
            header = self.detailed_stats_table.horizontalHeaderItem(i)
            if isinstance(header, AnimatedDetailedGroupHeader) and header.group_name == group_name:
                group_index = i
                header.toggle_expansion()
                break

        # Lancer l'animation de réduction
        columns = self.component_columns[group_name]
        animation = ColumnAnimation(
            self.detailed_stats_table,
            min(columns),
            max(columns)
        )
        animation.collapse()
        
        # Supprimer les colonnes après l'animation
        def remove_columns():
            for column in sorted(self.component_columns[group_name], reverse=True):
                self.detailed_stats_table.removeColumn(column)
            self.component_columns.pop(group_name)

        QTimer.singleShot(animation.duration + 50, remove_columns)

    
    def _add_unassigned_row_detailed(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des postes non attribués pour les groupes weekend"""
        unassigned_stats = stats.get("Non attribué", {})
        unassigned_total = 0
        
        # Cellule du nom
        name_item = QTableWidgetItem("Non attribué")
        name_item.setBackground(QColor('#F5F5F5'))
        self.detailed_stats_table.setItem(row_index, 0, name_item)
        
        # Valeurs par groupe
        for col, group in enumerate(all_groups, start=1):
            count = unassigned_stats.get(group, 0)
            item = QTableWidgetItem(str(count))
            item.setBackground(QColor('#F5F5F5'))
            self.detailed_stats_table.setItem(row_index, col, item)
            unassigned_total += count
        
        # Total
        total_item = QTableWidgetItem(str(unassigned_total))
        total_item.setBackground(QColor('#F5F5F5'))
        self.detailed_stats_table.setItem(row_index, len(all_groups) + 1, total_item)

    def _add_total_row_detailed(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des totaux pour les groupes weekend"""
        # Cellule du nom
        name_item = QTableWidgetItem("Total")
        name_item.setBackground(QColor('#EEEEEE'))
        name_item.setFont(QFont("", -1, QFont.Weight.Bold))
        self.detailed_stats_table.setItem(row_index, 0, name_item)
        
        # Calcul des totaux par groupe
        grand_total = 0
        for col, group in enumerate(all_groups, start=1):
            # Exclure "Non attribué" du calcul s'il existe
            total = sum(person_stats.get(group, 0) 
                    for name, person_stats in stats.items() 
                    if name != "Non attribué")
            
            item = QTableWidgetItem(str(total))
            item.setBackground(QColor('#EEEEEE'))
            item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.detailed_stats_table.setItem(row_index, col, item)
            grand_total += total
        
        # Total général
        final_total = QTableWidgetItem(str(grand_total))
        final_total.setBackground(QColor('#EEEEEE'))
        final_total.setFont(QFont("", -1, QFont.Weight.Bold))
        self.detailed_stats_table.setItem(row_index, len(all_groups) + 1, final_total)

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
        """Met à jour le tableau des statistiques des groupes de semaine"""
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
                name_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                
            self.weekday_group_stats_table.setItem(row, 0, name_item)

            intervals = self._get_doctor_weekday_intervals(person.name)
            row_total = 0
            
            for col, group in enumerate(all_groups, start=1):
                count = weekday_group_stats.get(person.name, {}).get(group, 0)
                item = QTableWidgetItem(str(count))
                
                # Appliquer la coloration grise pour les médecins en demi-part
                if is_half_time:
                    item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                
                # Appliquer la coloration selon les intervalles
                self._apply_interval_coloring(item, count, intervals.get(group, {}), is_cat, group)
                
                self.weekday_group_stats_table.setItem(row, col, item)
                row_total += count

            # Total avec tooltip
            total_item = QTableWidgetItem(str(row_total))
            total_intervals = {"target": sum(intervals.get(g, {}).get('target', 0) for g in all_groups)}
            
            # Appliquer la coloration grise pour les médecins en demi-part
            if is_half_time:
                total_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                
            self._apply_interval_coloring(total_item, row_total, total_intervals, is_cat, "Total")
            self.weekday_group_stats_table.setItem(row, len(all_groups) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row_weekday_groups(len(all_personnel), weekday_group_stats, all_groups)
        self._add_total_row_weekday_groups(len(all_personnel) + 1, weekday_group_stats, all_groups)

        # Configuration de l'affichage
        self.weekday_group_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        """Ajoute la ligne des postes non attribués pour les groupes de semaine"""
        unassigned_stats = stats.get("Non attribué", {})
        unassigned_total = 0
        
        # Cellule du nom
        name_item = QTableWidgetItem("Non attribué")
        name_item.setBackground(QColor('#F5F5F5'))
        self.weekday_group_stats_table.setItem(row_index, 0, name_item)
        
        # Valeurs par groupe
        for col, group in enumerate(all_groups, start=1):
            count = unassigned_stats.get(group, 0)
            item = QTableWidgetItem(str(count))
            item.setBackground(QColor('#F5F5F5'))
            self.weekday_group_stats_table.setItem(row_index, col, item)
            unassigned_total += count
        
        # Total
        total_item = QTableWidgetItem(str(unassigned_total))
        total_item.setBackground(QColor('#F5F5F5'))
        self.weekday_group_stats_table.setItem(row_index, len(all_groups) + 1, total_item)

    def _add_total_row_weekday_groups(self, row_index: int, stats: dict, all_groups: list):
        """Ajoute la ligne des totaux pour les groupes de semaine"""
        # Cellule du nom
        name_item = QTableWidgetItem("Total")
        name_item.setBackground(QColor('#EEEEEE'))
        name_item.setFont(QFont("", -1, QFont.Weight.Bold))
        self.weekday_group_stats_table.setItem(row_index, 0, name_item)
        
        # Calcul des totaux par groupe
        grand_total = 0
        for col, group in enumerate(all_groups, start=1):
            total = sum(person_stats.get(group, 0) 
                    for person_stats in stats.values())
            item = QTableWidgetItem(str(total))
            item.setBackground(QColor('#EEEEEE'))
            item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.weekday_group_stats_table.setItem(row_index, col, item)
            grand_total += total
        
        # Total général
        final_total = QTableWidgetItem(str(grand_total))
        final_total.setBackground(QColor('#EEEEEE'))
        final_total.setFont(QFont("", -1, QFont.Weight.Bold))
        self.weekday_group_stats_table.setItem(row_index, len(all_groups) + 1, final_total)

    def update_weekly_stats_table(self, weekly_stats):
        """Met à jour le tableau des statistiques de semaine avec une présentation améliorée"""
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
            if not hasattr(person, 'half_parts'):  # C'est un CAT
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))
            elif person.half_parts == 1:  # Mi-temps
                name_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
            self.weekly_stats_table.setItem(row, 0, name_item)

            # Valeurs des postes
            row_total = 0
            person_intervals = ideal_intervals.get(person.name, {}).get('weekday_posts', {})

            for col, post in enumerate(all_posts, start=1):
                count = stats.get(person.name, {}).get(post, 0)
                item = QTableWidgetItem(str(count))
                
                # Gestion de la coloration
                if hasattr(person, 'half_parts'):
                    if person.half_parts == 1:  # Mi-temps
                        item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                        
                    # Coloration selon les intervalles pour les médecins
                    intervals = person_intervals.get(post, {})
                    if intervals:
                        min_val = intervals.get('min', 0)
                        max_val = intervals.get('max', float('inf'))
                        if count < min_val:
                            item.setBackground(QColor(200, 255, 200, 255))  # Vert plus vif
                        elif count > max_val:
                            item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif
                
                if post in self.custom_posts:
                    item.setBackground(self.custom_posts[post].color)
                    
                self.weekly_stats_table.setItem(row, col, item)
                row_total += count

            # Total de la ligne
            total_item = QTableWidgetItem(str(row_total))
            if hasattr(person, 'half_parts') and person.half_parts == 1:
                total_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
            self.weekly_stats_table.setItem(row, len(all_posts) + 1, total_item)

        # Ajout des lignes "Non attribué" et "Total"
        self._add_unassigned_row_weekly(len(all_personnel), stats, all_posts)
        self._add_total_row_weekly(len(all_personnel) + 1, stats, all_posts)

        # Configuration de l'affichage
        self.weekly_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.weekly_stats_table.verticalHeader().setVisible(False)
        self.weekly_stats_table.setAlternatingRowColors(False)

        # Application du filtre actuel
        self._apply_filter_to_table(self.weekly_stats_table)

    def _add_unassigned_row_weekly(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des postes non attribués pour les statistiques semaine"""
        unassigned_stats = stats.get("Non attribué", {})
        unassigned_total = 0
        
        # Cellule du nom
        name_item = QTableWidgetItem("Non attribué")
        name_item.setBackground(QColor('#F5F5F5'))
        self.weekly_stats_table.setItem(row_index, 0, name_item)
        
        # Valeurs par poste
        for col, post_type in enumerate(all_posts, start=1):
            count = unassigned_stats.get(post_type, 0)
            item = QTableWidgetItem(str(count))
            item.setBackground(QColor('#F5F5F5'))
            self.weekly_stats_table.setItem(row_index, col, item)
            unassigned_total += count
        
        # Total
        total_item = QTableWidgetItem(str(unassigned_total))
        total_item.setBackground(QColor('#F5F5F5'))
        self.weekly_stats_table.setItem(row_index, len(all_posts) + 1, total_item)

    def _add_total_row_weekly(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des totaux pour les statistiques semaine"""
        # Cellule du nom
        name_item = QTableWidgetItem("Total")
        name_item.setBackground(QColor('#EEEEEE'))
        name_item.setFont(QFont("", -1, QFont.Weight.Bold))
        self.weekly_stats_table.setItem(row_index, 0, name_item)
        
        # Calcul des totaux par poste
        grand_total = 0
        for col, post_type in enumerate(all_posts, start=1):
            total = sum(person_stats.get(post_type, 0) 
                    for person_stats in stats.values())
            item = QTableWidgetItem(str(total))
            item.setBackground(QColor('#EEEEEE'))
            item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.weekly_stats_table.setItem(row_index, col, item)
            grand_total += total
        
        # Total général
        final_total = QTableWidgetItem(str(grand_total))
        final_total.setBackground(QColor('#EEEEEE'))
        final_total.setFont(QFont("", -1, QFont.Weight.Bold))
        self.weekly_stats_table.setItem(row_index, len(all_posts) + 1, final_total)

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

        # Remplissage des données
        for row, person in enumerate(all_personnel):
            # Configuration du nom
            name_item = QTableWidgetItem(person.name)
            if not hasattr(person, 'half_parts'):  # CAT
                name_item.setFont(QFont("", -1, QFont.Weight.Bold))
                name_item.setBackground(QColor('#E8F5E9'))
            elif person.half_parts == 1:  # Mi-temps
                name_item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
            self.weekend_stats_table.setItem(row, 0, name_item)

            # Récupération des intervalles spécifiques à la personne
            person_intervals = ideal_intervals.get(person.name, {})
            weekend_group_intervals = person_intervals.get('weekend_groups', {})
            weekend_post_intervals = person_intervals.get('weekend_posts', {})

            # Calcul du total des NL (incluant NLv)
            nl_total = weekend_stats.get(person.name, {}).get('NL', 0)

            row_total = 0
            for col, post in enumerate(all_posts, start=1):
                count = weekend_stats.get(person.name, {}).get(post, 0)
                item = QTableWidgetItem(str(count))
                
                # Gestion de la coloration
                if hasattr(person, 'half_parts'):
                    if person.half_parts == 1:  # Mi-temps
                        item.setBackground(QColor(230, 230, 230, 255))  # Gris plus prononcé
                    elif post == 'NL':  # Cas spécial pour NL
                        nlw_intervals = weekend_group_intervals.get('NLw', {})
                        min_val = nlw_intervals.get('min', 0)
                        max_val = nlw_intervals.get('max', float('inf'))
                        
                        if nl_total < min_val:
                            item.setBackground(QColor(200, 255, 200, 255))  # Vert plus vif
                        elif nl_total > max_val:
                            item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif
                    else:  # Autres postes
                        intervals = weekend_post_intervals.get(post, {})
                        min_val = intervals.get('min', 0)
                        max_val = intervals.get('max', float('inf'))
                        if count < min_val:
                            item.setBackground(QColor(200, 255, 200, 255))  # Vert plus vif
                        elif count > max_val:
                            item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif
                
                if post in self.custom_posts:
                    item.setBackground(self.custom_posts[post].color)
                    
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
        self._apply_filter_to_table(self.weekend_stats_table)
    
    def _add_unassigned_row_weekend(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des postes non attribués pour les statistiques weekend"""
        unassigned_stats = stats.get("Non attribué", {})
        unassigned_total = 0
        
        # Cellule du nom
        name_item = QTableWidgetItem("Non attribué")
        name_item.setBackground(QColor('#F5F5F5'))
        self.weekend_stats_table.setItem(row_index, 0, name_item)
        
        # Valeurs par poste
        for col, post_type in enumerate(all_posts, start=1):
            count = unassigned_stats.get(post_type, 0)
            item = QTableWidgetItem(str(count))
            item.setBackground(QColor('#F5F5F5'))
            self.weekend_stats_table.setItem(row_index, col, item)
            unassigned_total += count
        
        # Total
        total_item = QTableWidgetItem(str(unassigned_total))
        total_item.setBackground(QColor('#F5F5F5'))
        self.weekend_stats_table.setItem(row_index, len(all_posts) + 1, total_item)

    def _add_total_row_weekend(self, row_index: int, stats: dict, all_posts: list):
        """Ajoute la ligne des totaux pour les statistiques weekend"""
        # Cellule du nom
        name_item = QTableWidgetItem("Total")
        name_item.setBackground(QColor('#EEEEEE'))
        name_item.setFont(QFont("", -1, QFont.Weight.Bold))
        self.weekend_stats_table.setItem(row_index, 0, name_item)
        
        # Calcul des totaux par poste
        grand_total = 0
        for col, post_type in enumerate(all_posts, start=1):
            total = sum(person_stats.get(post_type, 0) 
                    for person_stats in stats.values())
            item = QTableWidgetItem(str(total))
            item.setBackground(QColor('#EEEEEE'))
            item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.weekend_stats_table.setItem(row_index, col, item)
            grand_total += total
        
        # Total général
        final_total = QTableWidgetItem(str(grand_total))
        final_total.setBackground(QColor('#EEEEEE'))
        final_total.setFont(QFont("", -1, QFont.Weight.Bold))
        self.weekend_stats_table.setItem(row_index, len(all_posts) + 1, final_total)

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
        Pour les CAT, utilise la target de la pré-analyse comme quota.
        Rouge si différent du quota prévu, blanc sinon.
        """
        if not intervals:
            return

        if is_cat:
            target = intervals.get('target', 0)
            if target == 0:  # Pas de quota défini
                item.setBackground(QBrush())  # Laisser en blanc
                return
                
            if value != target:  # Différent du quota prévu
                item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif
            else:
                item.setBackground(QBrush())  # Blanc si quota exact
        else:
            min_val = intervals.get('min', 0)
            max_val = intervals.get('max', float('inf'))
            
            if value < min_val:
                item.setBackground(QColor(200, 255, 200, 255))  # Vert plus vif
            elif max_val != float('inf') and value > max_val:
                item.setBackground(QColor(255, 200, 200, 255))  # Rouge plus vif
            else:
                item.setBackground(QBrush())  # Blanc si dans l'intervalle

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
    """Gère l'animation des colonnes lors de l'expansion/réduction"""
    def __init__(self, table, start_col, end_col):
        self.table = table
        self.start_col = start_col
        self.end_col = end_col
        self.animations = []
        self.original_widths = {}
        # Durée de base + 50ms par colonne
        self.base_duration = 200
        self.duration = self.base_duration + (end_col - start_col + 1) * 50

    def expand(self):
        """Anime l'expansion des colonnes avec un effet cascade fluide"""
        header = self.table.horizontalHeader()
        font_metrics = QFontMetrics(header.font())
        
        # Calcul des largeurs optimales
        target_widths = {}
        for col in range(self.start_col, self.end_col + 1):
            # Sauvegarder la largeur originale
            self.original_widths[col] = self.table.columnWidth(col)
            
            # Calculer la largeur nécessaire
            max_width = max(
                (font_metrics.horizontalAdvance(self.table.horizontalHeaderItem(col).text()) + 20),
                max((font_metrics.horizontalAdvance(self.table.item(row, col).text()) + 10 
                     for row in range(self.table.rowCount()) 
                     if self.table.item(row, col)), default=0)
            )
            target_widths[col] = min(max_width, 400)  # Limite à 400px

        # Créer les animations avec effet cascade
        for idx, col in enumerate(range(self.start_col, self.end_col + 1)):
            anim = QPropertyAnimation(self.table.horizontalHeader(), b"sectionSize")
            anim.setDuration(self.duration)
            anim.setStartValue(0)
            anim.setEndValue(target_widths[col])
            anim.setEasingCurve(QEasingCurve.Type.OutBack)
            
            # Décalage progressif pour effet cascade
            delay = idx * 50
            QTimer.singleShot(delay, anim.start)
            self.animations.append(anim)

    def collapse(self):
        """Anime la réduction des colonnes avec effet cascade inversé"""
        # Créer les animations en ordre inverse
        for idx, col in enumerate(reversed(range(self.start_col, self.end_col + 1))):
            anim = QPropertyAnimation(self.table.horizontalHeader(), b"sectionSize")
            anim.setDuration(self.base_duration + idx * 30)
            anim.setStartValue(self.table.columnWidth(col))
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.Type.InBack)
            
            # Restaurer la largeur originale après l'animation
            def restore_width(col):
                if col in self.original_widths:
                    self.table.setColumnWidth(col, self.original_widths[col])
                    self.table.setColumnHidden(col, True)
            
            # Décalage progressif pour effet cascade
            delay = idx * 40
            QTimer.singleShot(delay, lambda col=col: [anim.start(), restore_width(col)])
            self.animations.append(anim)
