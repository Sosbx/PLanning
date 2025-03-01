# © 2024 HILAL Arkane. Tous droits réservés.
# gui/harmonization_dialog.py

from PyQt6.QtWidgets import (QDialog,QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                           QTableWidget, QTableWidgetItem, QMessageBox, QProgressBar,
                           QGroupBox, QHeaderView, QTextEdit, QCheckBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QColor

from utils.harmonization import ConfigHarmonizer
import logging

logger = logging.getLogger(__name__)

class HarmonizationDialog(QDialog):
    """
    Dialogue d'harmonisation des configurations de postes.
    Permet d'identifier et de corriger les incohérences dans les configurations.
    """
    
    def __init__(self, post_configuration, parent=None):
        super().__init__(parent)
        self.post_configuration = post_configuration
        self.harmonizer = ConfigHarmonizer(post_configuration)
        self.issues = []
        self.setWindowTitle("Harmonisation des configurations")
        self.setMinimumSize(850, 600)
        self.init_ui()
    
    def init_ui(self):
        """Initialise l'interface utilisateur du dialogue."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # En-tête avec titre et description
        header_layout = QVBoxLayout()
        title = QLabel("Analyse et correction des incohérences")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        
        description = QLabel(
            "Cet outil vous aide à identifier et corriger les problèmes potentiels "
            "dans vos configurations de postes. Il vérifie notamment la cohérence "
            "des types de jour, des dates et des chevauchements."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #555; margin-bottom: 15px;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(description)
        layout.addLayout(header_layout)
        
        # Tableau des problèmes
        issues_group = QGroupBox("Problèmes détectés")
        issues_layout = QVBoxLayout(issues_group)
        
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(3)
        self.issues_table.setHorizontalHeaderLabels(["Type", "Description", "Actions"])
        self.issues_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.issues_table.horizontalHeader().setMinimumSectionSize(150)
        self.issues_table.setAlternatingRowColors(True)
        self.issues_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTableWidget::item:selected {
                background-color: #e8f0fe;
                color: #333;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e1e4e8;
                font-weight: bold;
                color: #333;
            }
            QLabel {
                padding: 3px;
                line-height: 1.4;
            }
        """)
        
        # Définir le comportement de redimensionnement
        self.issues_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.issues_table.setWordWrap(True)
        
        issues_layout.addWidget(self.issues_table)
        
        # Options de correction automatique
        options_layout = QHBoxLayout()
        self.auto_fix_check = QCheckBox("Appliquer les corrections automatiques")
        self.auto_fix_check.setChecked(True)
        options_layout.addWidget(self.auto_fix_check)
        options_layout.addStretch()
        
        issues_layout.addLayout(options_layout)
        layout.addWidget(issues_group)
        
        # Zone de rapport
        report_group = QGroupBox("Rapport")
        report_layout = QVBoxLayout(report_group)
        
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-family: Consolas, Monaco, monospace;
                color: #333;
            }
        """)
        report_layout.addWidget(self.report_text)
        
        layout.addWidget(report_group)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v/%m étapes")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                width: 10px;
                margin: 0.5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Boutons d'action
        buttons_layout = QHBoxLayout()
        
        self.analyze_button = QPushButton("Analyser")
        self.analyze_button.setIcon(QIcon("icons/analyze.png"))
        self.analyze_button.clicked.connect(self.analyze)
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2475a8;
            }
        """)
        
        self.fix_button = QPushButton("Corriger")
        self.fix_button.setIcon(QIcon("icons/fix.png"))
        self.fix_button.clicked.connect(self.fix_issues)
        self.fix_button.setEnabled(False)
        self.fix_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #219653;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a33025;
            }
        """)
        
        buttons_layout.addWidget(self.analyze_button)
        buttons_layout.addWidget(self.fix_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
    
    def analyze(self):
        """Lance l'analyse des configurations."""
        self.analyze_button.setEnabled(False)
        self.fix_button.setEnabled(False)
        self.progress_bar.setValue(10)
        
        # Utiliser un timer pour rendre l'interface plus réactive
        QTimer.singleShot(100, self._perform_analysis)
    
    def _perform_analysis(self):
        """Effectue l'analyse et met à jour l'interface."""
        try:
            self.progress_bar.setValue(30)
            
            # Exécuter l'analyse
            self.issues = self.harmonizer.check_all()
            
            self.progress_bar.setValue(60)
            
            # Mettre à jour le tableau
            self.update_issues_table()
            
            self.progress_bar.setValue(80)
            
            # Mettre à jour le rapport
            if not self.issues:
                self.report_text.setHtml(
                    "<p style='color:#2ecc71;'><b>Aucun problème détecté</b></p>"
                    "<p>Vos configurations sont cohérentes.</p>"
                )
            else:
                self.report_text.setHtml(
                    f"<p style='color:#e74c3c;'><b>{len(self.issues)} problème(s) détecté(s)</b></p>"
                    "<p>Consultez la liste pour plus de détails. "
                    "Vous pouvez appliquer les corrections automatiques ou fermer ce dialogue "
                    "pour effectuer les modifications manuellement.</p>"
                )
            
            # Activation du bouton de correction si des problèmes sont détectés
            self.fix_button.setEnabled(len(self.issues) > 0)
            
            self.progress_bar.setValue(100)
            
            # Appliquer automatiquement les corrections si l'option est sélectionnée
            if self.auto_fix_check.isChecked() and self.issues:
                QTimer.singleShot(500, self.fix_issues)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'analyse: {str(e)}"
            )
        finally:
            self.analyze_button.setEnabled(True)
    
    def update_issues_table(self):
        """Met à jour le tableau des problèmes détectés avec prise en charge de l'affichage multilignes."""
        self.issues_table.setRowCount(len(self.issues))
        
        for row, issue in enumerate(self.issues):
            # Type de problème
            type_item = QTableWidgetItem(self.get_issue_type_label(issue['type']))
            type_item.setBackground(self.get_issue_type_color(issue['type']))
            type_item.setToolTip(self.get_issue_type_tooltip(issue['type']))
            self.issues_table.setItem(row, 0, type_item)
            
            # Description - utiliser QLabel pour permettre l'affichage multilignes
            message_cell = QWidget()
            cell_layout = QVBoxLayout(message_cell)
            cell_layout.setContentsMargins(5, 5, 5, 5)
            message_label = QLabel(issue['message'])
            message_label.setWordWrap(True)
            message_label.setTextFormat(Qt.TextFormat.PlainText)  # Important pour gérer correctement les \n
            cell_layout.addWidget(message_label)
            self.issues_table.setCellWidget(row, 1, message_cell)
            
            # Boutons d'action (à implémenter si nécessaire)
            # Pour l'instant, laissons cette colonne vide
        
        # Après avoir rempli la table, ajuster les hauteurs de ligne
        for row in range(self.issues_table.rowCount()):
            self.issues_table.resizeRowToContents(row)
    
    def fix_issues(self):
        """Corrige les problèmes détectés."""
        if not self.issues:
            return
        
        confirm = QMessageBox.question(
            self,
            "Confirmation",
            f"Voulez-vous corriger automatiquement les {len(self.issues)} problème(s) détecté(s) ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.fix_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.progress_bar.setValue(10)
            
            # Utiliser un timer pour rendre l'interface plus réactive
            QTimer.singleShot(100, self._perform_fixes)
    
    def _perform_fixes(self):
        """Effectue les corrections et met à jour l'interface."""
        try:
            self.progress_bar.setValue(30)
            
            # Exécuter les corrections
            report = self.harmonizer.fix_all()
            
            self.progress_bar.setValue(60)
            
            # Mettre à jour le rapport
            report_html = "<p style='color:#2ecc71;'><b>Rapport de correction</b></p>"
            report_html += f"<p>Problèmes corrigés: {report['fixed_issues']}</p>"
            if report['remaining_issues'] > 0:
                report_html += f"<p style='color:#e74c3c;'>Problèmes restants: {report['remaining_issues']}</p>"
            
            if report['details']:
                report_html += "<ul>"
                for detail in report['details']:
                    report_html += f"<li>{detail}</li>"
                report_html += "</ul>"
            
            self.report_text.setHtml(report_html)
            
            self.progress_bar.setValue(80)
            
            # Mettre à jour le tableau des problèmes
            self.issues = self.harmonizer.check_all()
            self.update_issues_table()
            
            self.progress_bar.setValue(100)
            
            # Notification à l'utilisateur
            if report['fixed_issues'] > 0:
                QMessageBox.information(
                    self,
                    "Corrections appliquées",
                    f"{report['fixed_issues']} problème(s) ont été corrigés.\n"
                    f"{report['remaining_issues']} problème(s) subsistent et "
                    f"nécessitent une correction manuelle."
                )
            else:
                QMessageBox.information(
                    self,
                    "Aucune correction",
                    "Aucun problème n'a pu être corrigé automatiquement.\n"
                    "Une correction manuelle est nécessaire."
                )
            
        except Exception as e:
            logger.error(f"Erreur lors de la correction: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erreur",
                f"Une erreur est survenue lors de la correction: {str(e)}"
            )
        finally:
            self.analyze_button.setEnabled(True)
            self.fix_button.setEnabled(len(self.issues) > 0)
    
    def get_issue_type_label(self, issue_type):
        """Retourne un libellé convivial pour le type de problème."""
        labels = {
            'date_order': "Dates invalides",
            'invalid_day_type': "Type de jour invalide",
            'day_type_mismatch': "Type inapproprié",
            'holiday_wrong_type': "Jour férié mal configuré",
            'bridge_day_wrong_type': "Jour de pont mal configuré",
            'unknown_post_type': "Poste inconnu",
            'overlapping_configs': "Chevauchement"
        }
        return labels.get(issue_type, issue_type)
    
    def get_issue_type_color(self, issue_type):
        """Retourne une couleur de fond pour le type de problème."""
        colors = {
            'date_order': QColor(255, 235, 235),  # Rouge clair
            'invalid_day_type': QColor(255, 235, 235),  # Rouge clair
            'day_type_mismatch': QColor(255, 248, 225),  # Jaune clair
            'holiday_wrong_type': QColor(255, 248, 225),  # Jaune clair
            'bridge_day_wrong_type': QColor(255, 248, 225),  # Jaune clair
            'unknown_post_type': QColor(232, 245, 233),  # Vert clair
            'overlapping_configs': QColor(232, 240, 254)   # Bleu clair
        }
        return colors.get(issue_type, QColor(255, 255, 255))  # Blanc par défaut
    
    def get_issue_type_tooltip(self, issue_type):
        """Retourne une infobulle explicative pour le type de problème."""
        tooltips = {
            'date_order': "La date de début est postérieure à la date de fin",
            'invalid_day_type': "Le type de jour n'est pas valide (Semaine, Samedi, Dimanche/Férié)",
            'day_type_mismatch': "Le type de jour configuré ne correspond pas au type réel du jour",
            'holiday_wrong_type': "Un jour férié devrait être configuré comme 'Dimanche/Férié'",
            'bridge_day_wrong_type': "Un jour de pont devrait être configuré comme 'Dimanche/Férié'",
            'unknown_post_type': "Le type de poste n'existe pas dans la configuration standard",
            'overlapping_configs': "Deux configurations ou plus se chevauchent pour le même type de jour"
        }
        return tooltips.get(issue_type, "")