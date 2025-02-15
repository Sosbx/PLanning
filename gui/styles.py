# © 2024 HILAL Arkane. Tous droits réservés.
# gui/styles.py

from PyQt6.QtGui import QColor

class ColorSystem:
    def __init__(self):
        self.styles = {
            'button': {
                'success': f"""
                    QPushButton {{
                        background-color: #28a745;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background-color: #218838;
                    }}
                    QPushButton:pressed {{
                        background-color: #1e7e34;
                    }}
                """,
                'danger': f"""
                    QPushButton {{
                        background-color: #dc3545;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background-color: #c82333;
                    }}
                    QPushButton:pressed {{
                        background-color: #bd2130;
                    }}
                """
            }
        }
        
        self.colors = {
            'primary': QColor('#007bff'),
            'secondary': QColor('#6c757d'),
            'success': QColor('#28a745'),
            'danger': QColor('#dc3545'),
            'warning': QColor('#ffc107'),
            'info': QColor('#17a2b8'),
            'light': QColor('#f8f9fa'),
            'dark': QColor('#343a40'),
            'window_background': QColor('#ffffff'),
            
            'text': {
                'primary': QColor('#212529'),
                'secondary': QColor('#6c757d'),
                'light': QColor('#ffffff'),
                'dark': QColor('#000000')
            },
            
            'container': {
                'background': QColor('#ffffff'),
                'border': QColor('#dee2e6'),
                'hover': QColor('#f8f9fa')
            },
            
            'table': {
                'header': QColor('#f8f9fa'),
                'border': QColor('#dee2e6'),
                'hover': QColor('#f5f5f5'),
                'selected': QColor('#e9ecef'),
                'alternate': QColor('#f8f9fa')
            },
            
            'focus': {
                'outline': QColor('#80bdff')
            },
            
            'weekend': QColor('#f8d7da'),
            'weekday': QColor('#ffffff'),
            'available': QColor('#d4edda'),
            
            'desiderata': {
                'primary': {
                    'normal': QColor('#fff3cd'),
                    'weekend': QColor('#ffe5d0')
                },
                'secondary': {
                    'normal': QColor('#cce5ff'),
                    'weekend': QColor('#b8daff')
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
            'matin': QColor('#e3f2fd'),      # Light blue
            'apresMidi': QColor('#fff3e0'),  # Light orange
            'soirNuit': QColor('#ede7f6')    # Light purple
        }
    
    def get_weekend_group_colors(self):
        """Get colors for weekend groups."""
        return {
            'gardes': QColor('#e3f2fd'),     # Light blue
            'visites': QColor('#fff3e0'),    # Light orange
            'consultations': QColor('#ede7f6') # Light purple
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
GLOBAL_STYLE = f"""
    QWidget {{
        font-family: {StyleConstants.FONT['family']['primary']};
        font-size: {StyleConstants.FONT['size']['md']};
        color: {color_system.colors['text']['primary'].name()};
    }}
    
    QPushButton {{
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['sm']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        border: 1px solid {color_system.colors['container']['border'].name()};
        background-color: {color_system.colors['container']['background'].name()};
    }}
    
    QPushButton:hover {{
        background-color: {color_system.colors['container']['hover'].name()};

    }}
    
    QPushButton:pressed {{
        background-color: {color_system.colors['container']['border'].name()};
    }}
    
    QLineEdit, QTextEdit, QComboBox {{
        padding: {StyleConstants.SPACING['xs']}px;
        border: 1px solid {color_system.colors['container']['border'].name()};
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        background-color: {color_system.colors['container']['background'].name()};
    }}
    
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 2px solid {color_system.colors['focus']['outline'].name()};
        outline: none;
    }}
"""

# Action button style (primary actions)
ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['primary'].name()};
        color: {color_system.colors['text']['light'].name()};
        border: none;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        font-weight: {StyleConstants.FONT['weight']['medium']};
    }}
    
    QPushButton:hover {{
        background-color: {color_system.colors['info'].name()};

    }}
    
    QPushButton:pressed {{
        background-color: {color_system.colors['secondary'].name()};
    }}
    
    QPushButton:disabled {{
        background-color: {color_system.colors['secondary'].name()};
        color: {color_system.colors['text']['secondary'].name()};
    }}
"""

# Add button style (success actions)
ADD_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['success'].name()};
        color: {color_system.colors['text']['light'].name()};
        border: none;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        font-weight: {StyleConstants.FONT['weight']['medium']};
    }}
    
    QPushButton:hover {{
        background-color: {color_system.colors['info'].name()};

    }}
    
    QPushButton:pressed {{
        background-color: {color_system.colors['secondary'].name()};
    }}
"""

# Edit/Delete button style (danger actions)
EDIT_DELETE_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {color_system.colors['danger'].name()};
        color: {color_system.colors['text']['light'].name()};
        border: none;
        padding: {StyleConstants.SPACING['xs']}px {StyleConstants.SPACING['md']}px;
        border-radius: {StyleConstants.BORDER_RADIUS['sm']}px;
        font-weight: {StyleConstants.FONT['weight']['medium']};
    }}
    
    QPushButton:hover {{
        background-color: {color_system.colors['warning'].name()};

    }}
    
    QPushButton:pressed {{
        background-color: {color_system.colors['secondary'].name()};
    }}
"""
