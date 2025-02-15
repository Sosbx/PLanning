# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

from PyQt6.QtGui import QColor

class ColorSystem:
    def __init__(self):
        self.styles = {
            'button': {
                'success': """
                    QPushButton {
                        background-color: #98C1A9;
                        color: #2D3748;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #7DAD8C;
                    }
                    QPushButton:pressed {
                        background-color: #689A78;
                    }
                """,
                'danger': """
                    QPushButton {
                        background-color: #D4A5A5;
                        color: #2D3748;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #C28E8E;
                    }
                    QPushButton:pressed {
                        background-color: #B07979;
                    }
                """
            }
        }
        
        self.colors = {
            'primary': QColor('#8BA6C9'),
            'secondary': QColor('#A3B8CC'),
            'success': QColor('#98C1A9'),
            'danger': QColor('#D4A5A5'),
            'warning': QColor('#E6C095'),
            'info': QColor('#95B8D4'),
            'light': QColor('#F5F8FA'),
            'dark': QColor('#2D3748'),
            'window_background': QColor('#E1E9F4'),
            
            'text': {
                'primary': QColor('#2D3748'),
                'secondary': QColor('#64748B'),
                'light': QColor('#F5F8FA'),
                'dark': QColor('#1A202C')
            },
            
            'container': {
                'background': QColor('#F5F8FA'),
                'border': QColor('#D8E2E9'),
                'hover': QColor('#EDF2F7')
            },
            
            'table': {
                'header': QColor('#E9ECF0'),
                'border': QColor('#DFE3E8'),
                'hover': QColor('#EDF2F7'),
                'selected': QColor('#E2E8F0'),
                'alternate': QColor('#F7F9FB')
            },
            
            'focus': {
                'outline': QColor('#8BA6C9')
            },
            
            'weekend': QColor('#D1D9E6'),
            'weekday': QColor('#F5F8FA'),
            'available': QColor('#E6F0E9'),
            
            'desiderata': {
                'primary': {
                    'normal': QColor('#F0E6D4'),
                    'weekend': QColor('#D1D9E6')
                },
                'secondary': {
                    'normal': QColor('#E1E9F4'),
                    'weekend': QColor('#D1D9E6')
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
            'matin': QColor('#E1E9F4'),      # Light blue
            'apresMidi': QColor('#F0E6D4'),  # Light orange
            'soirNuit': QColor('#E6E6F0')    # Light purple
        }
    
    def get_weekend_group_colors(self):
        """Get colors for weekend groups."""
        return {
            'gardes': QColor('#E1E9F4'),     # Light blue
            'visites': QColor('#F0E6D4'),    # Light orange
            'consultations': QColor('#E6E6F0') # Light purple
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
        background-color: #E1E9F4;
    }
    
    QPushButton {
        padding: 8px 12px;
        border-radius: 4px;
        border: 1px solid #D8E2E9;
        background-color: #F5F8FA;
    }
    
    QPushButton:hover {
        background-color: #EDF2F7;
    }
    
    QPushButton:pressed {
        background-color: #D8E2E9;
    }
    
    QLineEdit, QTextEdit, QComboBox {
        padding: 8px;
        border: 1px solid #D8E2E9;
        border-radius: 4px;
        background-color: #F5F8FA;
    }
    
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
        border: 2px solid #8BA6C9;
        outline: none;
    }
"""

# Action button style (primary actions)
ACTION_BUTTON_STYLE = """
    QPushButton {
        background-color: #8BA6C9;
        color: #2D3748;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #7691B4;
    }
    
    QPushButton:pressed {
        background-color: #64748B;
    }
    
    QPushButton:disabled {
        background-color: #A3B8CC;
        color: #64748B;
    }
"""

# Add button style (success actions)
ADD_BUTTON_STYLE = """
    QPushButton {
        background-color: #98C1A9;
        color: #2D3748;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #7DAD8C;
    }
    
    QPushButton:pressed {
        background-color: #64748B;
    }
"""

# Edit/Delete button style (danger actions)
EDIT_DELETE_BUTTON_STYLE = """
    QPushButton {
        background-color: #D4A5A5;
        color: #2D3748;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #C28E8E;
    }
    
    QPushButton:pressed {
        background-color: #64748B;
    }
"""
