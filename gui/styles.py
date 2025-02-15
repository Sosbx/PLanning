# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

from PyQt6.QtGui import QColor

class ColorSystem:
    def __init__(self):
        self.styles = {
            'button': {
                'success': """
                    QPushButton {
                        background-color: #7DAD8C;
                        color: #2D3748;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #689A78;
                    }
                    QPushButton:pressed {
                        background-color: #558A68;
                    }
                """,
                'danger': """
                    QPushButton {
                        background-color: #C28E8E;
                        color: #2D3748;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #B07979;
                    }
                    QPushButton:pressed {
                        background-color: #9E6767;
                    }
                """
            }
        }
        
        self.colors = {
            'primary': QColor('#7691B4'),
            'secondary': QColor('#8FA3B8'),
            'success': QColor('#7DAD8C'),
            'danger': QColor('#C28E8E'),
            'warning': QColor('#D1AC81'),
            'info': QColor('#7FA3BF'),
            'light': QColor('#EDF2F7'),
            'dark': QColor('#2D3748'),
            'window_background': QColor('#D8E1ED'),
            
            'text': {
                'primary': QColor('#2D3748'),
                'secondary': QColor('#64748B'),
                'light': QColor('#EDF2F7'),
                'dark': QColor('#1A202C')
            },
            
            'container': {
                'background': QColor('#EDF2F7'),
                'border': QColor('#CBD5E1'),
                'hover': QColor('#E2E8F0')
            },
            
            'table': {
                'header': QColor('#C6D1E1'),
                'border': QColor('#B4C2D3'),
                'hover': QColor('#D8E1ED'),
                'selected': QColor('#B8C7DB'),
                'alternate': QColor('#E2E8F0')
            },
            
            'focus': {
                'outline': QColor('#7691B4')
            },
            
            'weekend': QColor('#C6D0E1'),
            'weekday': QColor('#EDF2F7'),
            'available': QColor('#D1E6D6'),
            
            'desiderata': {
                'primary': {
                    'normal': QColor('#E6D4B8'),
                    'weekend': QColor('#C6D0E1')
                },
                'secondary': {
                    'normal': QColor('#D8E1ED'),
                    'weekend': QColor('#C6D0E1')
                }
            }
        }
    
    def get_color(self, key, context=None, priority=None):
        """Get a color from the system with optional context and priority."""
        if context and priority:
            return self.colors.get(key, {}).get(priority, {}).get(context)
        elif context:
            return self.colors.get(key, {}).get(context)
        else:
            return self.colors.get(key)
    
    def get_post_group_colors(self):
        """Get colors for post groups."""
        return {
            'matin': QColor('#D8E1ED'),      # Light blue
            'apresMidi': QColor('#E6D4B8'),  # Light orange
            'soirNuit': QColor('#DFD8ED')    # Light purple
        }
    
    def get_weekend_group_colors(self):
        """Get colors for weekend groups."""
        return {
            'gardes': QColor('#D8E1ED'),     # Light blue
            'visites': QColor('#E6D4B8'),    # Light orange
            'consultations': QColor('#DFD8ED') # Light purple
        }

class StyleConstants:
    """Constants for styling the application."""
    
    SPACING = {
        'xxs': 4,   # Extra extra small
        'xs': 8,    # Extra small
        'sm': 12,   # Small
        'md': 16,   # Medium
        'lg': 24,   # Large
        'xl': 32,   # Extra large
        'xxl': 48   # Extra extra large
    }
    
    BORDER_RADIUS = {
        'xs': 2,    # Extra small
        'sm': 4,    # Small
        'md': 6,    # Medium
        'lg': 8,    # Large
        'xl': 12    # Extra large
    }
    
    FONT = {
        'family': {
            'primary': 'Arial',
            'secondary': 'Helvetica'
        },
        'size': {
            'xs': '10px',   # Extra small
            'sm': '12px',   # Small
            'md': '14px',   # Medium
            'lg': '16px',   # Large
            'xl': '20px'    # Extra large
        },
        'weight': {
            'light': 300,
            'regular': 400,
            'medium': 500,
            'bold': 700
        }
    }
    
    ANIMATION = {
        'fast': 150,    # Fast transitions
        'normal': 300,  # Normal transitions
        'slow': 500     # Slow transitions
    }

# Initialize color system
color_system = ColorSystem()

# Global styles
GLOBAL_STYLE = """
    QWidget {
        font-family: Arial;
        font-size: 14px;
        color: #2D3748;
        background-color: #D8E1ED;
    }
    
    QPushButton {
        padding: 8px 12px;
        border-radius: 4px;
        border: 1px solid #CBD5E1;
        background-color: #EDF2F7;
    }
    
    QPushButton:hover {
        background-color: #E2E8F0;
    }
    
    QPushButton:pressed {
        background-color: #CBD5E1;
    }
    
    QLineEdit, QTextEdit, QComboBox {
        padding: 8px;
        border: 1px solid #CBD5E1;
        border-radius: 4px;
        background-color: #EDF2F7;
    }
    
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
        border: 2px solid #7691B4;
        outline: none;
    }

    QTableView {
        background-color: #EDF2F7;
        alternate-background-color: #E2E8F0;
        selection-background-color: #B8C7DB;
        border: 1px solid #B4C2D3;
        gridline-color: #B4C2D3;
    }

    QHeaderView::section {
        background-color: #C6D1E1;
        color: #2D3748;
        padding: 4px;
        border: 1px solid #B4C2D3;
        font-weight: 500;
    }

    QTableView::item:hover {
        background-color: #D8E1ED;
    }
"""

# Action button style (primary actions)
ACTION_BUTTON_STYLE = """
    QPushButton {
        background-color: #7691B4;
        color: #2D3748;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #617AA1;
    }
    
    QPushButton:pressed {
        background-color: #64748B;
    }
    
    QPushButton:disabled {
        background-color: #8FA3B8;
        color: #64748B;
    }
"""

# Add button style (success actions)
ADD_BUTTON_STYLE = """
    QPushButton {
        background-color: #7DAD8C;
        color: #2D3748;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #689A78;
    }
    
    QPushButton:pressed {
        background-color: #64748B;
    }
"""

# Edit/Delete button style (danger actions)
EDIT_DELETE_BUTTON_STYLE = """
    QPushButton {
        background-color: #C28E8E;
        color: #2D3748;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #B07979;
    }
    
    QPushButton:pressed {
        background-color: #64748B;
    }
"""
