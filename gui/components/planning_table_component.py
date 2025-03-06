# © 2024 HILAL Arkane. Tous droits réservés.
# gui/components/planning_table_component.py

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QBrush, QColor
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from workalendar.europe import France
from typing import Dict, List, Optional, Tuple, Callable, Any
from ..styles import StyleConstants, PlatformHelper


class PlanningTableComponent(QTableWidget):
    """
    Composant réutilisable pour l'affichage d'un tableau de planning
    avec en-têtes de mois au-dessus des colonnes
    """
    # Signaux
    cell_clicked = pyqtSignal(date, int)  # Date, période (1=matin, 2=après-midi, 3=soir, None=jour)
    cell_double_clicked = pyqtSignal(date, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialisation du calendrier français pour les jours fériés
        self._calendar = France()
        
        # Variables d'état
        self.start_date = None
        self.end_date = None
        self.current_colors = {}
        self.cell_renderer = None  # Fonction pour personnaliser le rendu des cellules
        
        # Dimensions des cellules
        self.min_row_height = 20    # Hauteur minimale des lignes en pixels
        self.max_row_height = 30    # Hauteur maximale des lignes en pixels
        self.min_col_widths = {
            "day": 30,             # Largeur minimale pour la colonne des jours
            "weekday": 35,         # Largeur minimale pour les colonnes des jours de la semaine
            "period": 40           # Largeur minimale pour les colonnes des périodes (M, AM, S)
        }
        self.max_col_widths = {
            "day": 40,             # Largeur maximale pour la colonne des jours
            "weekday": 50,         # Largeur maximale pour les colonnes des jours de la semaine
            "period": 80           # Largeur maximale pour les colonnes des périodes (M, AM, S)
        }
        
        # Paramètres de police avec ajustements spécifiques à la plateforme
        font_adjustments = StyleConstants.FONT_ADJUSTMENTS
        self._font_settings = {
            'family': None,        # Police utilisée (None = police système par défaut)
            'base_size': int(12 * font_adjustments['base_size_factor']),       # Taille du texte des postes dans les cellules 
            'header_size': int(14 * font_adjustments['header_size_factor']),   # Taille des en-têtes de mois
            'period_size': int(10 * font_adjustments['period_size_factor']),   # Taille des en-têtes de période (J, M, AM, S)
            'weekday_size': int(9 * font_adjustments['weekday_size_factor']),  # Taille des jours de la semaine (L, M, M, J, V, S, D)
            'bold_posts': True     # Activation/désactivation du gras pour les postes
        }
        
        # Configuration de base
        self.init_table()
        
    def init_table(self):
        """Initialise les propriétés de base du tableau"""
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        
        # Configurer les hauteurs des en-têtes
        self.horizontalHeader().setMinimumHeight(30)
        
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Connecter les signaux d'événements
        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        
    def adapt_dimensions_to_date_range(self):
        """
        Adapte automatiquement les dimensions en fonction de la plage de dates à afficher.
        Plus la période est longue, plus les cellules sont compactes.
        """
        if not self.start_date or not self.end_date:
            return
        
        # Calculer la durée totale en jours
        total_days = (self.end_date - self.start_date).days + 1
        
        # Calculer le nombre de mois
        total_months = (self.end_date.year - self.start_date.year) * 12 + self.end_date.month - self.start_date.month + 1
        
        # Adapter les hauteurs de ligne en fonction du nombre de jours à afficher
        if total_days <= 31:  # Un seul mois
            self.min_row_height = 20
            self.max_row_height = 25
        elif total_days <= 62:  # Deux mois
            self.min_row_height = 18
            self.max_row_height = 22
        else:  # Plus de deux mois
            self.min_row_height = 16
            self.max_row_height = 20
        
        # Adapter les largeurs de colonne en fonction du nombre de mois à afficher
        if total_months <= 3:  # Trimestre
            self.min_col_widths = {"day": 30, "weekday": 35, "period": 40}
            self.max_col_widths = {"day": 40, "weekday": 45, "period": 70}
        elif total_months <= 6:  # Semestre
            self.min_col_widths = {"day": 25, "weekday": 30, "period": 35}
            self.max_col_widths = {"day": 35, "weekday": 40, "period": 60}
        else:  # Année ou plus
            self.min_col_widths = {"day": 20, "weekday": 25, "period": 30}
            self.max_col_widths = {"day": 30, "weekday": 35, "period": 50}
        
        # Réoptimiser les dimensions
        self.optimize_dimensions()

    def setup_planning_dates(self, start_date: date, end_date: date):
        """
        Configure les dates du planning et initialise le tableau
        
        Args:
            start_date (date): Date de début du planning
            end_date (date): Date de fin du planning
        """
        self.start_date = start_date
        self.end_date = end_date
        
        # Calculer le nombre de mois
        total_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
        
        # Configuration initiale du tableau
        self.setRowCount(31)  # Maximum de jours dans un mois
        
        # +1 pour la colonne Jour et +1 pour la ligne d'Année/Mois
        self.setColumnCount(total_months * 4 + 1)
        
        # Configurer les en-têtes
        self._setup_headers(total_months)
        
        # Adapter automatiquement les dimensions à la plage de dates
        self.adapt_dimensions_to_date_range()
        
    def _setup_headers(self, total_months):
        """
        Configure les en-têtes du tableau avec un regroupement visuel par mois.
        Crée deux lignes d'en-têtes distinctes: une pour les mois et une pour les périodes.
        """
        # Configurer l'en-tête horizontal pour avoir une hauteur réduite
        self.horizontalHeader().setMinimumHeight(32)  # Réduit de 48 à 32 pixels
        
        # Créer les étiquettes de base pour les colonnes
        headers = ["Jour"]
        for _ in range(total_months):
            headers.extend(["J", "M", "AM", "S"])
        
        # Définir les étiquettes des colonnes (périodes)
        self.setHorizontalHeaderLabels(headers)
        
        # Style des en-têtes de période (J, M, AM, S)
        period_font = QFont()
        period_font.setBold(True)
        period_font.setPointSize(self._font_settings['period_size'])  # Taille réduite pour les périodes
        
        # Appliquer le style aux en-têtes de période
        for col in range(self.columnCount()):
            header_item = self.horizontalHeaderItem(col)
            if header_item:
                header_item.setFont(period_font)
                
                # Appliquer une couleur de fond légère pour les en-têtes de période
                if col > 0:  # Toutes les colonnes sauf "Jour"
                    header_item.setBackground(QBrush(QColor(245, 245, 245)))  # Gris très clair
        
        # Style des en-têtes de mois
        month_font = QFont()
        month_font.setBold(True)
        month_font.setPointSize(self._font_settings['header_size'])
        
        # Créer une première ligne pour les mois (utiliser la première ligne du tableau)
        # Réserver la première ligne du tableau pour les en-têtes de mois
        current_date = self.start_date.replace(day=1)
        month_color = QColor(230, 230, 240)  # Couleur bleutée claire pour les mois
        
        # Vérifier si la ligne d'en-tête des mois existe déjà
        header_row_exists = False
        if self.rowCount() > 0:
            # Vérifier si la première cellule de la première ligne est une cellule d'en-tête de mois
            first_cell = self.item(0, 0)
            if first_cell and first_cell.background().color() == QColor(255, 255, 255):
                header_row_exists = True
        
        # Ajouter une ligne au tableau pour les en-têtes de mois seulement si elle n'existe pas déjà
        if not header_row_exists:
            self.insertRow(0)
        
        # Définir une hauteur plus grande pour la ligne des mois
        self.setRowHeight(0, 30)  # Hauteur fixe pour la ligne des mois
        
        # Cellule vide pour la colonne "Jour"
        month_header_item = QTableWidgetItem("")
        month_header_item.setBackground(QBrush(QColor(255, 255, 255)))  # Blanc
        self.setItem(0, 0, month_header_item)
        
        # Pour chaque mois, créer une cellule fusionnée
        for month_idx in range(total_months):
            # Obtenir le nom du mois
            month_name = current_date.strftime("%b %Y")
            
            # Créer l'item pour l'en-tête de mois
            month_header_item = QTableWidgetItem(month_name)
            month_header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            month_header_item.setBackground(QBrush(month_color))
            month_header_item.setFont(month_font)
            
            # Colonne de début pour ce mois
            start_col = month_idx * 4 + 1
            
            # Vérifier que la colonne est dans les limites
            if start_col < self.columnCount():
                # Placer l'item dans la première cellule du mois
                self.setItem(0, start_col, month_header_item)
                
                # Fusionner les cellules pour couvrir les 4 colonnes du mois
                end_col = min(start_col + 3, self.columnCount() - 1)
                self.setSpan(0, start_col, 1, end_col - start_col + 1)
                
                # Ajouter une bordure à droite pour séparer visuellement les mois
                if month_idx < total_months - 1:  # Pas de bordure pour le dernier mois
                    # Appliquer une bordure à la dernière colonne du mois
                    for row in range(1, self.rowCount()):
                        border_cell = self.item(row, end_col)
                        if border_cell:
                            # Utiliser un style de bordure via une feuille de style
                            border_cell.setData(
                                Qt.ItemDataRole.UserRole + 1,  # Rôle personnalisé pour le style
                                "border-right: 1px solid #999999;"  # Bordure grise
                            )
            
            # Passer au mois suivant
            current_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        
        # Optimiser les largeurs des colonnes
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Colonne Jour
        for col in range(1, self.columnCount()):
            self.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

    def set_colors(self, colors: Dict[str, Dict[str, QColor]]):
        """
        Définit les couleurs à utiliser pour le tableau
        
        Args:
            colors: Dictionnaire de couleurs {type: {contexte: couleur}}
                   Doit inclure les clés "base", "primary", "secondary"
                   Chaque type doit avoir les contextes "normal" et "weekend"
        """
        # Appliquer les ajustements de couleur spécifiques à la plateforme
        adjusted_colors = {}
        for color_type, contexts in colors.items():
            adjusted_colors[color_type] = {}
            for context, color in contexts.items():
                adjusted_colors[color_type][context] = PlatformHelper.adjust_color_for_platform(color)
        
        self.current_colors = adjusted_colors
        
    def set_cell_renderer(self, renderer: Callable[[date, int, Any], Tuple[str, Dict]]):
        """
        Définit une fonction de rendu personnalisée pour les cellules
        
        Args:
            renderer: Fonction qui prend (date, période, contexte) et retourne
                     (texte à afficher, dict de propriétés)
        """
        self.cell_renderer = renderer
        
    def populate_days(self):
        """Remplit le tableau avec les jours du planning"""
        if not self.start_date or not self.end_date:
            return
            
        current_date = self.start_date
        while current_date <= self.end_date:
            self._add_day_to_table(current_date)
            current_date += timedelta(days=1)
            
        # Appliquer les paramètres de police
        self._apply_font_settings()
            
        # Ajuster les dimensions après le remplissage
        self.optimize_dimensions()
        
    def _add_day_to_table(self, day_date: date):
        """Ajoute un jour au tableau"""
        # Décaler l'indice de ligne pour tenir compte de la ligne d'en-tête des mois
        day_row = day_date.day - 1 + 1  # +1 pour la ligne d'en-tête des mois
        if day_row >= self.rowCount():
            return  # Éviter l'accès hors limite
            
        month_col = (day_date.year - self.start_date.year) * 12 + day_date.month - self.start_date.month
        col_offset = month_col * 4 + 1
        
        # Jour du mois (première colonne)
        self._set_day_cell(day_row, 0, str(day_date.day))
        
        # Vérifier si la colonne J existe
        if col_offset < self.columnCount():
            # Jour de la semaine avec numéro de jour
            weekday_names = ["L", "M", "M", "J", "V", "S", "D"]
            weekday_text = f"{weekday_names[day_date.weekday()]}{day_date.day}"
            self._set_weekday_cell(day_row, col_offset, weekday_text, day_date)
            
            # Cellules vides pour les périodes (à remplir par la méthode update_cell)
            for i in range(3):  # Matin, Après-midi, Soir
                period = i + 1
                col = col_offset + period
                if col < self.columnCount():  # Vérifier que la colonne existe
                    item = QTableWidgetItem("")
                    is_weekend = day_date.weekday() >= 5 or self._calendar.is_holiday(day_date)
                    background_color = self.current_colors.get("base", {}).get(
                        "weekend" if is_weekend else "normal", 
                        QColor(220, 220, 220) if is_weekend else QColor(255, 255, 255)
                    )
                    item.setBackground(QBrush(background_color))
                    
                    # Stocker la date et la période dans les données de l'élément
                    item.setData(Qt.ItemDataRole.UserRole, {"date": day_date, "period": period})
                    
                    self.setItem(day_row, col, item)
            
    def _set_day_cell(self, row: int, col: int, text: str):
        """Configure une cellule de jour"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, col, item)
        
    def _set_weekday_cell(self, row: int, col: int, text: str, day_date: date):
        """
        Configure une cellule de jour de la semaine avec le numéro du jour en gras
        
        Format exemple: L15 où L est le jour de la semaine et 15 est le jour du mois en gras
        """
        # Créer un QTableWidgetItem
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Appliquer le texte formaté
        item.setText(text)
        
        # Police pour le jour de la semaine
        font = QFont()
        font.setPointSize(self._font_settings['weekday_size'])
        
        # Coloration spécifique pour les week-ends et jours fériés
        is_weekend = day_date.weekday() >= 5
        is_holiday = self._calendar.is_holiday(day_date)
        
        if is_weekend or is_holiday:
            font.setBold(True)
            item.setFont(font)
            
            if is_holiday:
                item.setForeground(QBrush(QColor(180, 0, 0)))  # Rouge pour les jours fériés
            else:
                item.setForeground(QBrush(QColor(0, 0, 180)))  # Bleu pour les week-ends
        else:
            font.setBold(True)  # Mettre toute la cellule en gras pour simplifier
            item.setFont(font)
        
        # Stocker la date dans les données de l'élément
        item.setData(Qt.ItemDataRole.UserRole, {"date": day_date, "period": None})
        
        self.setItem(row, col, item)

    def set_min_row_height(self, height: int):
        """Configure la hauteur minimale des lignes"""
        self.min_row_height = height
        self.optimize_dimensions()

    def set_max_row_height(self, height: int):
        """Configure la hauteur maximale des lignes"""
        self.max_row_height = height
        self.optimize_dimensions()

    def set_min_column_widths(self, day_width: int = None, weekday_width: int = None, period_width: int = None):
        """Configure les largeurs minimales des colonnes"""
        if day_width is not None:
            self.min_col_widths["day"] = day_width
        if weekday_width is not None:
            self.min_col_widths["weekday"] = weekday_width
        if period_width is not None:
            self.min_col_widths["period"] = period_width
        self.optimize_dimensions()

    def set_max_column_widths(self, day_width: int = None, weekday_width: int = None, period_width: int = None):
        """Configure les largeurs maximales des colonnes"""
        if day_width is not None:
            self.max_col_widths["day"] = day_width
        if weekday_width is not None:
            self.max_col_widths["weekday"] = weekday_width
        if period_width is not None:
            self.max_col_widths["period"] = period_width
        self.optimize_dimensions()
        
    def update_cell(self, day_date: date, period: int, text: str, 
                    background_color: Optional[QColor] = None,
                    foreground_color: Optional[QColor] = None,
                    font: Optional[QFont] = None,
                    tooltip: Optional[str] = None,
                    custom_data: Optional[Any] = None):
        """
        Met à jour une cellule spécifique du tableau
        
        Args:
            day_date: Date du jour
            period: Période (1=Matin, 2=Après-midi, 3=Soir)
            text: Texte à afficher
            background_color: Couleur de fond (optionnel)
            foreground_color: Couleur du texte (optionnel)
            font: Police du texte (optionnel)
            tooltip: Info-bulle (optionnel)
            custom_data: Données personnalisées à stocker (optionnel)
        """
        if not self.start_date or not self.end_date:
            return
            
        if day_date < self.start_date or day_date > self.end_date:
            return
            
        if period < 1 or period > 3:
            return
            
        # Décaler l'indice de ligne pour tenir compte de la ligne d'en-tête des mois
        day_row = day_date.day - 1 + 1  # +1 pour la ligne d'en-tête des mois
        if day_row >= self.rowCount():
            return  # Éviter l'accès hors limite
        
        month_col = (day_date.year - self.start_date.year) * 12 + day_date.month - self.start_date.month
        col_offset = month_col * 4 + 1
        col = col_offset + period
        
        # Vérifier que la colonne existe
        if col >= self.columnCount():
            return
        
        item = self.item(day_row, col)
        if not item:
            item = QTableWidgetItem()
            self.setItem(day_row, col, item)
            
        # Mettre à jour les propriétés de base
        item.setText(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Mettre à jour les couleurs si spécifiées
        if background_color:
            item.setBackground(QBrush(background_color))
        
        if foreground_color:
            item.setForeground(QBrush(foreground_color))
            
        # Mettre à jour la police avec les paramètres de base si aucune police n'est spécifiée
        if not font:
            custom_font = QFont()
            if self._font_settings.get('family'):
                custom_font.setFamily(self._font_settings['family'])
            custom_font.setPointSize(self._font_settings['base_size'])
            
            # Mettre les postes en gras si l'option est activée
            if self._font_settings.get('bold_posts', True) and text.strip():
                custom_font.setBold(True)
                
            item.setFont(custom_font)
        else:
            item.setFont(font)
                
        # Mettre à jour l'infobulle si spécifiée
        if tooltip:
            item.setToolTip(tooltip)
                
        # Stocker les données utilisateur
        data = {"date": day_date, "period": period}
        if custom_data:
            data["custom"] = custom_data
                
        item.setData(Qt.ItemDataRole.UserRole, data)
        
    def set_bold_posts(self, enable: bool):
        """Active ou désactive la mise en gras des abréviations de postes"""
        self._font_settings['bold_posts'] = enable
        self._apply_font_settings()
        
    def clear_period_cells(self):
        """Efface le contenu de toutes les cellules de période"""
        for row in range(self.rowCount()):
            for col in range(1, self.columnCount()):
                if col % 4 != 1:  # Ne pas effacer les colonnes J
                    item = self.item(row, col)
                    if item:
                        item.setText("")
                        
    def optimize_cell_text(self, text: str, max_length: int = 15) -> Tuple[str, str]:
        """
        Optimise le texte d'une cellule pour l'affichage
        
        Args:
            text: Texte original
            max_length: Longueur maximale avant troncature
            
        Returns:
            Tuple (texte_affiché, tooltip)
        """
        if len(text) > max_length:
            display_text = text[:max_length] + "..."
            tooltip = text
        else:
            display_text = text
            tooltip = None
            
        return display_text, tooltip
        
    def optimize_dimensions(self):
        """
        Optimise les dimensions des lignes et colonnes en fonction du contenu
        et de l'espace disponible dans la fenêtre
        """
        # Vérifier que les dimensions du tableau sont valides
        if self.rowCount() == 0 or self.columnCount() == 0:
            return
            
        # Récupérer les dimensions disponibles
        available_width = max(1, self.viewport().width())
        available_height = max(1, self.viewport().height())
        
        # Calculer le nombre de mois
        if self.start_date and self.end_date:
            total_months = (self.end_date.year - self.start_date.year) * 12 + self.end_date.month - self.start_date.month + 1
        else:
            total_months = 1
        
        # Calculer la hauteur idéale des lignes
        ideal_row_height = min(max(available_height / 31, self.min_row_height), self.max_row_height)
        
        # Calculer les largeurs cibles des colonnes en fonction de l'espace disponible
        day_col_weight = 0.8
        weekday_col_weight = 1.0
        period_col_weight = 1.2
        
        total_weight = day_col_weight + (weekday_col_weight + 3 * period_col_weight) * total_months
        if total_weight <= 0:
            total_weight = 1.0  # Éviter la division par zéro
            
        unit_width = available_width / total_weight
        
        target_day_width = unit_width * day_col_weight
        target_weekday_width = unit_width * weekday_col_weight
        target_period_width = unit_width * period_col_weight
        
        # Appliquer les limites min/max aux valeurs cibles
        day_width = max(min(target_day_width, self.max_col_widths["day"]), self.min_col_widths["day"])
        weekday_width = max(min(target_weekday_width, self.max_col_widths["weekday"]), self.min_col_widths["weekday"])
        period_width = max(min(target_period_width, self.max_col_widths["period"]), self.min_col_widths["period"])
        
        # Appliquer les dimensions calculées
        
        # Hauteurs des lignes
        for row in range(self.rowCount()):
            self.setRowHeight(row, int(ideal_row_height))
        
        # Largeurs des colonnes
        for col in range(self.columnCount()):
            if col == 0:
                # Colonne des jours
                self.setColumnWidth(col, int(day_width))
            elif (col - 1) % 4 == 0:
                # Colonnes J (jours de la semaine)
                self.setColumnWidth(col, int(weekday_width))
            else:
                # Colonnes M, AM, S
                self.setColumnWidth(col, int(period_width))
    
    def resizeEvent(self, event):
        """Gère le redimensionnement du tableau"""
        super().resizeEvent(event)
        # Réoptimiser les dimensions lors du redimensionnement
        self.optimize_dimensions()
        
    def get_date_period_from_cell(self, row: int, col: int) -> Tuple[Optional[date], Optional[int]]:
        """
        Récupère la date et la période à partir d'une cellule
        
        Args:
            row: Ligne de la cellule
            col: Colonne de la cellule
            
        Returns:
            Tuple (date, période)
        """
        # Vérifier que les indices sont valides
        if row < 0 or row >= self.rowCount() or col < 0 or col >= self.columnCount():
            return None, None
            
        item = self.item(row, col)
        if not item:
            return None, None
            
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            return None, None
            
        return data.get("date"), data.get("period")
    
    def get_period_from_column(self, col: int) -> Optional[int]:
        """
        Détermine la période à partir d'une colonne
        
        Args:
            col: Numéro de colonne
            
        Returns:
            1 pour Matin, 2 pour Après-midi, 3 pour Soir, None pour Jour ou autre
        """
        if col <= 0 or col >= self.columnCount():
            return None
            
        column_in_group = (col - 1) % 4
        
        if column_in_group == 0:  # Colonne J
            return None
        else:
            return column_in_group  # 1, 2 ou 3
    
    def _on_cell_clicked(self, row: int, col: int):
        """Gère le clic sur une cellule"""
        date_val, period = self.get_date_period_from_cell(row, col)
        if date_val:
            # Émettre -1 au lieu de None pour éviter les problèmes de conversion de type
            self.cell_clicked.emit(date_val, -1 if period is None else period)
    
    def _on_cell_double_clicked(self, row: int, col: int):
        """Gère le double-clic sur une cellule"""
        date_val, period = self.get_date_period_from_cell(row, col)
        if date_val:
            # Émettre -1 au lieu de None pour éviter les problèmes de conversion de type
            self.cell_double_clicked.emit(date_val, -1 if period is None else period)
    
    def set_font_settings(self, font_family=None, base_size=None, header_size=None, period_size=None, weekday_size=None):
        """
        Configure les paramètres de police pour le tableau
        
        Args:
            font_family (str): Famille de police à utiliser
            base_size (int): Taille de base pour le texte normal
            header_size (int): Taille pour les en-têtes de mois
            period_size (int): Taille pour les en-têtes de période (J, M, AM, S)
            weekday_size (int): Taille pour les jours de la semaine
        """
        # Stocker les paramètres
        self._font_settings = {
            'family': font_family or self._font_settings.get('family', None),
            'base_size': base_size or self._font_settings.get('base_size', 12),
            'header_size': header_size or self._font_settings.get('header_size', 14),
            'period_size': period_size or self._font_settings.get('period_size', 10),
            'weekday_size': weekday_size or self._font_settings.get('weekday_size', 9),
            'bold_posts': self._font_settings.get('bold_posts', True)
        }
        
        # Appliquer les paramètres aux cellules existantes
        self._apply_font_settings()

    def _apply_font_settings(self):
        """Applique les paramètres de police à toutes les cellules"""
        # Créer les fonts avec les paramètres configurés
        base_font = QFont()
        if self._font_settings.get('family'):
            base_font.setFamily(self._font_settings['family'])
        base_font.setPointSize(self._font_settings['base_size'])
        
        # Police pour les en-têtes de mois
        month_font = QFont(base_font)
        month_font.setPointSize(self._font_settings['header_size'])
        month_font.setBold(True)
        
        # Police pour les en-têtes de période (J, M, AM, S)
        period_font = QFont(base_font)
        period_font.setPointSize(self._font_settings['period_size'])
        period_font.setBold(True)
        
        # Police pour les jours de la semaine
        weekday_font = QFont(base_font)
        weekday_font.setPointSize(self._font_settings['weekday_size'])
        
        # Appliquer aux en-têtes de période (J, M, AM, S)
        for col in range(self.columnCount()):
            header_item = self.horizontalHeaderItem(col)
            if header_item:
                header_item.setFont(period_font)
        
        # Appliquer aux en-têtes de mois (première ligne du tableau)
        for col in range(self.columnCount()):
            month_item = self.item(0, col)
            if month_item:
                month_item.setFont(month_font)
        
        # Appliquer aux cellules de jour
        for row in range(1, self.rowCount()):  # Commencer à 1 pour sauter la ligne des mois
            day_item = self.item(row, 0)
            if day_item:
                day_item.setFont(base_font)
        
        # Appliquer aux cellules de jour de la semaine et de périodes
        for row in range(1, self.rowCount()):  # Commencer à 1 pour sauter la ligne des mois
            for col in range(1, self.columnCount()):
                item = self.item(row, col)
                if not item:
                    continue
                    
                if (col - 1) % 4 == 0:  # Colonne J (jour de la semaine)
                    item.setFont(weekday_font)
                else:  # Colonnes M, AM, S
                    custom_font = QFont(base_font)
                    if self._font_settings.get('bold_posts', True) and item.text().strip():
                        custom_font.setBold(True)
                    item.setFont(custom_font)
