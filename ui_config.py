# UI Configuration for MeasureLines Application
# All size and layout parameters in one place for easy adjustment

class UIConfig:
    """Configuration class for UI dimensions and layout"""
    
    # Panel Heights (percentage of screen height)
    TOP_PANEL_HEIGHT = 5
    SETTINGS_AREA_HEIGHT = 30  # Height of settings scroll area
    
    # Panel Widths (percentage of screen width)
    RIGHT_PANEL_WIDTH = 32  # Width of right control panel
    
    # Button Sizes
    # Tab buttons
    TAB_BUTTON_WIDTH = 15
    TAB_BUTTON_HEIGHT = 1
    TAB_BUTTON_FONT_SIZE = 2.5
    
    # Numpad buttons
    NUMPAD_BUTTON_WIDTH = 9
    NUMPAD_BUTTON_HEIGHT = 2
    NUMPAD_BUTTON_FONT_SIZE = 2.2
    
    # Control buttons (Submit, Cancel, Reset) - aligned with numpad
    CONTROL_BUTTON_WIDTH = 9  # Same as numpad buttons (with shorter "Reset" text)
    CONTROL_BUTTON_HEIGHT = 2
    CONTROL_BUTTON_FONT_SIZE = 2.2
    
    # Settings entry fields
    ENTRY_LABEL_WIDTH = 25
    ENTRY_FIELD_WIDTH = 18
    ENTRY_FONT_SIZE = 2.2
    
    # Status labels
    STATUS_FONT_SIZE = 2.5
    MEASUREMENT_FONT_SIZE = 2.2
    DATETIME_FONT_SIZE = 1.3  # Date/time display font size (reduced from 3.9 to 1.3)
    
    # Spacing and Padding (percentage of screen dimension)
    PADDING_SMALL = 0.2   # Small padding
    PADDING_MEDIUM = 0.5  # Medium padding
    PADDING_LARGE = 1.0   # Large padding
    
    # Numpad layout spacing
    NUMPAD_BUTTON_PADX = 0.1
    NUMPAD_BUTTON_PADY = 0.1
    NUMPAD_CONTAINER_PADY = 0.5
    
    # Control buttons spacing - aligned with numpad
    CONTROL_BUTTON_PADX = 0.1  # Same as numpad buttons
    CONTROL_FRAME_PADY = 0.3
    
    # Main container spacing
    MAIN_CONTAINER_PADY = 0.8
    STATUS_FRAME_PADY = 0.5
    
    # System Info tab
    SYSTEM_INFO_FONT_SIZE = 2.2
    SYSTEM_INFO_TITLE_FONT_SIZE = 3.5
    SYSTEM_INFO_PADDING = 1.0
    
    @classmethod
    def get_font_size_pixels(cls, percentage, screen_height):
        """Convert font size percentage to pixels based on screen height"""
        return int(screen_height * percentage / 100)
    
    @classmethod
    def get_padding_pixels_x(cls, percentage, screen_width):
        """Convert horizontal padding percentage to pixels"""
        return int(screen_width * percentage / 100)
    
    @classmethod
    def get_padding_pixels_y(cls, percentage, screen_height):
        """Convert vertical padding percentage to pixels"""
        return int(screen_height * percentage / 100)