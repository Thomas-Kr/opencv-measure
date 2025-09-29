import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import ttk, Frame, Label, Entry, Button, Canvas
from PIL import Image, ImageTk
import threading
import json
import os
import datetime
import subprocess
from ui_config import UIConfig

SOURCE = 'sources/test3.mp4'

class MeasureLinesIntegratedGUI:
    def __init__(self):
        # Settings file path
        self.settings_file = "measure_lines_settings.json"
        
        # Default configuration values (keep backup for reset)
        self.default_config = {
            'NUM_ROWS': 5,
            'COLOR_THRESH': 220.0,
            'TARGET_FPS': 20,
            'TOP_MARGIN_RATIO': 0.2,
            'BOTTOM_MARGIN_RATIO': 0.6,
            'WIDTH_THRESHOLD': 5.0
        }
        
        # Load saved settings or use defaults
        self.config = self.load_settings()
        
        # GUI variables
        self.root = tk.Tk()
        self.root.title("OpenCV Measure Lines - Live Control")
        
        # Get screen dimensions for proper fullscreen on X server
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Set fullscreen properly for X server
        self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.configure(bg='black')
        self.root.focus_set()  # Ensure focus
        
        # Set up close handler to save settings
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        
        # Video processing variables
        self.cap = None
        self.running = False
        self.video_thread = None
        
        # Current input field
        self.current_entry = None
        self.current_value = ""
        
        # Current active tab
        self.current_tab = "settings"  # "settings" or "system_info"
        
        # Initialize entries dictionary
        self.entries = {}
        
        # Video display variables
        self.video_canvas = None
        self.video_label = None
        self.current_photo = None  # Keep reference to prevent garbage collection
        self.update_pending = False  # Prevent multiple updates
        
        # Measurement state
        self.bg_mean = None
        self.initial_width = 0
        self.avg_width_1s = 0
        self.width_buffer = []
        self.last_time = time.time()
        
        self.setup_gui()
        self.start_measurement()
    
    def p_to_pixels_x(self, percentage):
        """Convert percentage to pixels for horizontal (width) dimension"""
        return int(self.screen_width * percentage / 100)
    
    def p_to_pixels_y(self, percentage):
        """Convert percentage to pixels for vertical (height) dimension"""
        return int(self.screen_height * percentage / 100)
    
    def load_settings(self):
        """Load settings from JSON file or return defaults"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    saved_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.default_config.copy()
                    config.update(saved_config)
                    print(f"Settings loaded from {self.settings_file}")
                    return config
            else:
                print("No saved settings found, using defaults")
                return self.default_config.copy()
        except Exception as e:
            print(f"Error loading settings: {e}, using defaults")
            return self.default_config.copy()
    
    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"Settings saved to {self.settings_file}")
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
        
    def setup_gui(self):
        # Main container
        main_frame = Frame(self.root, bg='black')
        main_frame.pack(fill='both', expand=True)
        
        # Top panel with controls and datetime
        top_panel = Frame(main_frame, bg='darkblue', height=self.p_to_pixels_y(UIConfig.TOP_PANEL_HEIGHT))
        top_panel.pack(fill='x', pady=(0, self.p_to_pixels_y(0.7)))
        top_panel.pack_propagate(False)
        
        # Left side of top panel - Control buttons
        left_top_frame = Frame(top_panel, bg='darkblue')
        left_top_frame.pack(side='left', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.7))
        
        # RESTART button (1.5x bigger for touchscreen)
        self.restart_btn = Button(left_top_frame, text="RESTART", width=15, height=2,
                                 font=('Arial', self.p_to_pixels_y(2.5), 'bold'), bg='yellow', fg='black',
                                 command=self.restart_measurement)
        self.restart_btn.pack(side='left', padx=self.p_to_pixels_x(0.5))
        
        # POWEROFF button (next to RESTART, 1.5x bigger)
        self.poweroff_btn = Button(left_top_frame, text="POWEROFF", width=15, height=2,
                                  font=('Arial', self.p_to_pixels_y(2.5), 'bold'), bg='red', fg='white',
                                  command=self.ask_poweroff_confirmation)
        self.poweroff_btn.pack(side='left', padx=self.p_to_pixels_x(0.5))
        
        # Center - Confirmation area (initially hidden)
        self.confirm_frame = Frame(top_panel, bg='darkblue')
        self.confirm_frame.pack(side='left', padx=self.p_to_pixels_x(2), pady=self.p_to_pixels_y(0.7))
        
        self.confirm_label = Label(self.confirm_frame, text="Are you sure?", 
                                  font=('Arial', self.p_to_pixels_y(2.5), 'bold'), bg='darkblue', fg='yellow')
        
        self.yes_btn = Button(self.confirm_frame, text="YES", width=9, height=2,
                             font=('Arial', self.p_to_pixels_y(2.2), 'bold'), bg='darkred', fg='white',
                             command=self.poweroff_confirmed)
        
        self.no_btn = Button(self.confirm_frame, text="NO", width=9, height=2,
                            font=('Arial', self.p_to_pixels_y(2.2), 'bold'), bg='green', fg='white',
                            command=self.poweroff_cancelled)
        
        # Initially hide confirmation elements
        self.hide_confirmation()
        
        # Right side of top panel - Date/Time
        right_top_frame = Frame(top_panel, bg='darkblue')
        right_top_frame.pack(side='right', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.7))
        
        # Date and Time (doubled font size)
        self.datetime_label = Label(right_top_frame, text="Loading...", 
                                   font=('Arial', self.p_to_pixels_y(1.6), 'bold'), bg='darkblue', fg='white')
        self.datetime_label.pack()
        
        # Start datetime update
        self.update_datetime()
        
        # Content frame for video and controls
        content_frame = Frame(main_frame, bg='black')
        content_frame.pack(fill='both', expand=True)
        
        # Left side - Video display (takes most of the space - about 70%)
        video_frame = Frame(content_frame, bg='black')
        video_frame.pack(side='left', fill='both', expand=True)
        
        # Video canvas
        self.video_canvas = Canvas(video_frame, bg='black')
        self.video_canvas.pack(fill='both', expand=True)
        
        # Right side - Controls (fixed width - about 30% of screen width)
        control_frame = Frame(content_frame, bg='darkgray', width=self.p_to_pixels_x(UIConfig.RIGHT_PANEL_WIDTH))
        control_frame.pack(side='right', fill='y', padx=self.p_to_pixels_x(0.2), pady=self.p_to_pixels_y(0.3))
        control_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Tab buttons frame
        tab_frame = Frame(control_frame, bg='darkgray')
        tab_frame.pack(fill='x', pady=(0, self.p_to_pixels_y(1)))
        
        # Tab buttons
        self.settings_tab_btn = Button(tab_frame, text="Settings", 
                                      width=UIConfig.TAB_BUTTON_WIDTH, height=UIConfig.TAB_BUTTON_HEIGHT,
                                      font=('Arial', self.p_to_pixels_y(UIConfig.TAB_BUTTON_FONT_SIZE), 'bold'), 
                                      bg='lightblue', fg='black',
                                      command=lambda: self.switch_tab("settings"))
        self.settings_tab_btn.pack(side='left', padx=self.p_to_pixels_x(0.5))
        
        self.system_info_tab_btn = Button(tab_frame, text="System Info", 
                                         width=UIConfig.TAB_BUTTON_WIDTH, height=UIConfig.TAB_BUTTON_HEIGHT,
                                         font=('Arial', self.p_to_pixels_y(UIConfig.TAB_BUTTON_FONT_SIZE), 'bold'), 
                                         bg='white', fg='black',
                                         command=lambda: self.switch_tab("system_info"))
        self.system_info_tab_btn.pack(side='left', padx=self.p_to_pixels_x(0.5))
        
        # Content area for tabs
        self.tab_content_frame = Frame(control_frame, bg='darkgray')
        self.tab_content_frame.pack(fill='both', expand=True)
        
        # Settings content frame
        self.settings_content = Frame(self.tab_content_frame, bg='darkgray')
        
        # Settings section with optimized height
        settings_canvas = Canvas(self.settings_content, bg='lightgray', height=self.p_to_pixels_y(UIConfig.SETTINGS_AREA_HEIGHT))
        settings_canvas.pack(fill='x', pady=(0, self.p_to_pixels_y(0.5)))
        
        settings_scroll_frame = Frame(settings_canvas, bg='lightgray')
        settings_canvas.create_window((0, 0), window=settings_scroll_frame, anchor='nw')
        
        # Create entry boxes for each config value
        self.entries = {}
        self.setup_config_entries(settings_scroll_frame)
        
        # Update scroll region
        settings_scroll_frame.update_idletasks()
        settings_canvas.configure(scrollregion=settings_canvas.bbox('all'))
        
        # Numpad frame (in settings content)
        self.setup_numpad(self.settings_content)
        
        # System Info content frame
        self.system_info_content = Frame(self.tab_content_frame, bg='darkgray')
        self.setup_system_info_tab(self.system_info_content)
        
        # Show settings tab by default
        self.switch_tab("settings")
        
        # Bind ESC key for exit
        self.root.bind('<Escape>', lambda e: self.exit_app())
    
    def switch_tab(self, tab_name):
        """Switch between Settings and System Info tabs"""
        self.current_tab = tab_name
        
        # Hide all content frames
        self.settings_content.pack_forget()
        self.system_info_content.pack_forget()
        
        # Update tab button colors
        if tab_name == "settings":
            self.settings_tab_btn.config(bg='lightblue', fg='black')
            self.system_info_tab_btn.config(bg='white', fg='black')
            self.settings_content.pack(fill='both', expand=True)
        elif tab_name == "system_info":
            self.settings_tab_btn.config(bg='white', fg='black')
            self.system_info_tab_btn.config(bg='lightblue', fg='black')
            self.system_info_content.pack(fill='both', expand=True)
    
    def setup_system_info_tab(self, parent):
        """Create system information tab content"""
        # Title
        title_label = Label(parent, text="System Information", 
                           font=('Arial', self.p_to_pixels_y(3.5), 'bold'), 
                           bg='darkgray', fg='white')
        title_label.pack(pady=(self.p_to_pixels_y(2), self.p_to_pixels_y(1.5)))
        
        # System info container with better layout
        info_container = Frame(parent, bg='darkslategray')
        info_container.pack(fill='both', expand=True, padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(1))
        
        # CPU Temperature
        self.cpu_temp_label = Label(info_container, text="CPU Temp: N/A", 
                                   font=('Arial', self.p_to_pixels_y(2.2)), 
                                   bg='darkslategray', fg='lightgreen')
        self.cpu_temp_label.pack(anchor='w', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.5))
        
        # CPU Usage
        self.cpu_usage_label = Label(info_container, text="CPU Usage: N/A", 
                                    font=('Arial', self.p_to_pixels_y(2.2)), 
                                    bg='darkslategray', fg='lightblue')
        self.cpu_usage_label.pack(anchor='w', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.5))
        
        # Memory Usage
        self.memory_label = Label(info_container, text="Memory: N/A", 
                                 font=('Arial', self.p_to_pixels_y(2.2)), 
                                 bg='darkslategray', fg='lightyellow')
        self.memory_label.pack(anchor='w', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.5))
        
        # Disk Usage
        self.disk_label = Label(info_container, text="Disk: N/A", 
                               font=('Arial', self.p_to_pixels_y(2.2)), 
                               bg='darkslategray', fg='lightcoral')
        self.disk_label.pack(anchor='w', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.5))
        
        # Uptime (time since last reboot)
        self.uptime_label = Label(info_container, text="Uptime (since boot): N/A", 
                                 font=('Arial', self.p_to_pixels_y(2.2)), 
                                 bg='darkslategray', fg='lightgray')
        self.uptime_label.pack(anchor='w', padx=self.p_to_pixels_x(1), pady=self.p_to_pixels_y(0.5))
        
        # Start system monitoring
        self.update_system_info()
        
    def setup_config_entries(self, parent):
        """Create entry boxes for configuration values"""
        # Entry boxes container
        entries_frame = Frame(parent, bg='lightgray')
        entries_frame.pack(fill='both', expand=True, padx=self.p_to_pixels_x(0.3))
        
        for i, (key, value) in enumerate(self.config.items()):
            # Frame for each setting
            setting_frame = Frame(entries_frame, bg='lightgray')
            setting_frame.pack(fill='x')
            
            # Label (optimized width and font size for balanced layout)
            label = Label(setting_frame, text=f"{key}:", width=UIConfig.ENTRY_LABEL_WIDTH, anchor='w',
                         bg='lightgray', font=('Arial', self.p_to_pixels_y(UIConfig.ENTRY_FONT_SIZE)))
            label.pack(side='left')
            
            # Entry (optimized width and font size for balanced layout) with character limit
            entry = Entry(setting_frame, font=('Arial', self.p_to_pixels_y(UIConfig.ENTRY_FONT_SIZE)), 
                         width=UIConfig.ENTRY_FIELD_WIDTH)
            entry.insert(0, str(value))  # Insert value while enabled
            entry.config(state='disabled')  # Then disable
            entry.bind('<Button-1>', lambda e, k=key: self.select_entry(k))
            # Add character limit validation
            entry.bind('<KeyPress>', lambda e: self.validate_entry_length(e))
            entry.pack(side='right')
            
            self.entries[key] = entry
        
        # Error message display (below entry boxes)
        self.error_display_label = Label(entries_frame, text="", 
                                         font=('Arial', self.p_to_pixels_y(1.8)), bg='lightgray', fg='red', 
                                         wraplength=self.p_to_pixels_x(30), anchor='w', justify='left')
        self.error_display_label.pack(fill='x', pady=(self.p_to_pixels_y(1), 0))
    
    def setup_numpad(self, parent):
        """Create compact numpad with controls below it"""
        # Main container for numpad and controls
        numpad_main_container = Frame(parent, bg='darkgray')
        numpad_main_container.pack(fill='both', expand=True, pady=self.p_to_pixels_y(UIConfig.MAIN_CONTAINER_PADY))
        
        # Numpad container (centered)
        numpad_container = Frame(numpad_main_container, bg='darkgray')
        numpad_container.pack(pady=(0, self.p_to_pixels_y(UIConfig.NUMPAD_CONTAINER_PADY)))
        
        # Numpad buttons
        numpad_frame = Frame(numpad_container, bg='darkgray')
        numpad_frame.pack()
        
        # Number buttons (larger for touch)
        buttons = [
            ['7', '8', '9'],
            ['4', '5', '6'],
            ['1', '2', '3'],
            ['C', '0', '.']
        ]
        
        for row in buttons:
            button_row = Frame(numpad_frame, bg='darkgray')
            button_row.pack()
            
            for btn_text in row:
                if btn_text == 'C':
                    btn = Button(button_row, text=btn_text, 
                                width=UIConfig.NUMPAD_BUTTON_WIDTH, height=UIConfig.NUMPAD_BUTTON_HEIGHT,
                                font=('Arial', self.p_to_pixels_y(UIConfig.NUMPAD_BUTTON_FONT_SIZE), 'bold'), 
                                bg='orange', command=self.clear_input)
                else:
                    btn = Button(button_row, text=btn_text, 
                                width=UIConfig.NUMPAD_BUTTON_WIDTH, height=UIConfig.NUMPAD_BUTTON_HEIGHT,
                                font=('Arial', self.p_to_pixels_y(UIConfig.NUMPAD_BUTTON_FONT_SIZE), 'bold'), 
                                bg='lightblue', command=lambda t=btn_text: self.numpad_input(t))
                btn.pack(side='left', 
                        padx=self.p_to_pixels_x(UIConfig.NUMPAD_BUTTON_PADX), 
                        pady=self.p_to_pixels_y(UIConfig.NUMPAD_BUTTON_PADY))
        
        # Control buttons frame (below numpad)
        controls_frame = Frame(numpad_main_container, bg='darkgray')
        controls_frame.pack(fill='x', pady=self.p_to_pixels_y(UIConfig.CONTROL_FRAME_PADY))
        
        # Action buttons in horizontal layout
        action_frame = Frame(controls_frame, bg='darkgray')
        action_frame.pack()
        
        submit_btn = Button(action_frame, text="Submit", 
                           width=UIConfig.CONTROL_BUTTON_WIDTH, height=UIConfig.CONTROL_BUTTON_HEIGHT,
                           font=('Arial', self.p_to_pixels_y(UIConfig.CONTROL_BUTTON_FONT_SIZE), 'bold'), 
                           bg='lightgreen', command=self.submit_value)
        submit_btn.pack(side='left', padx=self.p_to_pixels_x(UIConfig.CONTROL_BUTTON_PADX))
        
        cancel_btn = Button(action_frame, text="Cancel", 
                           width=UIConfig.CONTROL_BUTTON_WIDTH, height=UIConfig.CONTROL_BUTTON_HEIGHT,
                           font=('Arial', self.p_to_pixels_y(UIConfig.CONTROL_BUTTON_FONT_SIZE), 'bold'), 
                           bg='lightcoral', command=self.cancel_input)
        cancel_btn.pack(side='left', padx=self.p_to_pixels_x(UIConfig.CONTROL_BUTTON_PADX))
        
        reset_btn = Button(action_frame, text="Reset All", 
                          width=UIConfig.CONTROL_BUTTON_WIDTH, height=UIConfig.CONTROL_BUTTON_HEIGHT,
                          font=('Arial', self.p_to_pixels_y(UIConfig.CONTROL_BUTTON_FONT_SIZE), 'bold'), 
                          bg='orange', fg='white', command=self.reset_all_settings)
        reset_btn.pack(side='left', padx=self.p_to_pixels_x(UIConfig.CONTROL_BUTTON_PADX))
        
        # Status display (at bottom)
        status_frame = Frame(numpad_main_container, bg='darkgray')
        status_frame.pack(fill='x', pady=(self.p_to_pixels_y(UIConfig.STATUS_FRAME_PADY), 0))
        
        self.status_label = Label(status_frame, text="Status: Starting...", 
                                 font=('Arial', self.p_to_pixels_y(UIConfig.STATUS_FONT_SIZE), 'bold'), 
                                 bg='darkgray', fg='white')
        self.status_label.pack()
    
    def validate_entry_length(self, event):
        """Limit entry box input to maximum 20 characters"""
        entry = event.widget
        current_text = entry.get()
        if len(current_text) >= 20:
            return "break"  # Prevent further input
    
    def show_error_message(self, key, message):
        """Show error message in status area"""
        self.error_display_label.config(text=f"{key}: {message}")
    
    def clear_error_message(self, key):
        """Clear error message"""
        self.error_display_label.config(text="")
    
    def clear_all_error_messages(self):
        """Clear all error messages"""
        self.error_display_label.config(text="")
    
    def get_system_info(self):
        """Get current system information"""
        try:
            import psutil
            import platform
            
            # CPU temperature - focus on Linux, simple fallback for Windows
            cpu_temp = "N/A"
            try:
                if platform.system() == "Linux":
                    # Method 1: Try psutil sensors (most reliable on Linux)
                    if hasattr(psutil, 'sensors_temperatures'):
                        temps = psutil.sensors_temperatures()
                        if temps:
                            # Try common Linux temperature sensors
                            for sensor_name in ['coretemp', 'k10temp', 'cpu_thermal', 'acpi']:
                                if sensor_name in temps and temps[sensor_name]:
                                    cpu_temp = f"{temps[sensor_name][0].current:.1f}"
                                    break
                            
                            # If no common sensor found, use first available
                            if cpu_temp == "N/A":
                                for sensor_list in temps.values():
                                    if sensor_list and hasattr(sensor_list[0], 'current'):
                                        cpu_temp = f"{sensor_list[0].current:.1f}"
                                        break
                    
                    # Method 2: Direct file reading (fallback for Linux)
                    if cpu_temp == "N/A":
                        import os
                        thermal_zones = [f"/sys/class/thermal/thermal_zone{i}/temp" for i in range(10)]
                        for zone_file in thermal_zones:
                            if os.path.exists(zone_file):
                                try:
                                    with open(zone_file, 'r') as f:
                                        temp_raw = int(f.read().strip())
                                        # Usually in millidegrees Celsius
                                        if temp_raw > 1000:
                                            cpu_temp = f"{temp_raw / 1000.0:.1f}"
                                            break
                                except:
                                    continue
                else:
                    # For Windows, just show N/A as requested
                    cpu_temp = "N/A"
                
            except Exception as e:
                print(f"Temperature detection error: {e}")
                cpu_temp = "N/A"
            
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=None)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used / (1024**3)  # GB
            memory_total = memory.total / (1024**3)  # GB
            
            # Disk usage (use '/' for Linux, 'C:' for Windows)
            disk_path = '/' if platform.system() != "Windows" else 'C:\\'
            disk = psutil.disk_usage(disk_path)
            disk_percent = (disk.used / disk.total) * 100
            disk_free = disk.free / (1024**3)  # GB
            
            # Uptime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_hours = int(uptime_seconds // 3600)
            uptime_minutes = int((uptime_seconds % 3600) // 60)
            
            return {
                'cpu_temp': cpu_temp,
                'cpu_usage': cpu_usage,
                'memory_percent': memory_percent,
                'memory_used': memory_used,
                'memory_total': memory_total,
                'disk_percent': disk_percent,
                'disk_free': disk_free,
                'uptime_hours': uptime_hours,
                'uptime_minutes': uptime_minutes
            }
        except ImportError:
            # psutil not available
            return None
        except Exception as e:
            print(f"Error getting system info: {e}")
            return None
    
    def update_system_info(self):
        """Update system information display"""
        try:
            info = self.get_system_info()
            if info:
                # Update labels with current info
                self.cpu_temp_label.config(text=f"CPU Temp: {info['cpu_temp']}°C")
                self.cpu_usage_label.config(text=f"CPU Usage: {info['cpu_usage']:.1f}%")
                self.memory_label.config(text=f"Memory: {info['memory_percent']:.1f}% ({info['memory_used']:.1f}/{info['memory_total']:.1f} GB)")
                self.disk_label.config(text=f"Disk: {info['disk_percent']:.1f}% ({info['disk_free']:.1f} GB free)")
                self.uptime_label.config(text=f"Uptime (since boot): {info['uptime_hours']}h {info['uptime_minutes']}m")
                
                # Color coding for CPU temperature (only if it's a number)
                if info['cpu_temp'] not in ["--", "N/A", "N/A (Windows)"]:
                    try:
                        temp_val = float(info['cpu_temp'])
                        if temp_val > 80:
                            self.cpu_temp_label.config(fg='red')
                        elif temp_val > 60:
                            self.cpu_temp_label.config(fg='orange')
                        else:
                            self.cpu_temp_label.config(fg='lightgreen')
                    except ValueError:
                        self.cpu_temp_label.config(fg='white')
                else:
                    self.cpu_temp_label.config(fg='white')
                    
                # Color coding for CPU usage
                if info['cpu_usage'] > 90:
                    self.cpu_usage_label.config(fg='red')
                elif info['cpu_usage'] > 70:
                    self.cpu_usage_label.config(fg='orange')
                else:
                    self.cpu_usage_label.config(fg='lightgreen')
                    
                # Color coding for memory usage
                if info['memory_percent'] > 90:
                    self.memory_label.config(fg='red')
                elif info['memory_percent'] > 80:
                    self.memory_label.config(fg='orange')
                else:
                    self.memory_label.config(fg='lightgreen')
                    
            else:
                # psutil not available, show alternative info
                self.cpu_temp_label.config(text="CPU Temp: N/A (install psutil)")
                self.cpu_usage_label.config(text="CPU Usage: N/A")
                self.memory_label.config(text="Memory: N/A")
                self.disk_label.config(text="Disk: N/A")
                self.uptime_label.config(text="Uptime (since boot): N/A")
        except Exception as e:
            print(f"Error updating system info: {e}")
        
        # Schedule next update (every 5 seconds)
        self.root.after(5000, self.update_system_info)
    
    def update_datetime(self):
        """Update datetime display every second"""
        try:
            now = datetime.datetime.now()
            datetime_str = now.strftime("%Y-%m-%d %H:%M:%S")
            self.datetime_label.config(text=datetime_str)
        except Exception as e:
            self.datetime_label.config(text="Time Error")
        
        # Schedule next update
        self.root.after(1000, self.update_datetime)
    
    def show_confirmation(self):
        """Show the confirmation dialog in the top panel"""
        self.confirm_label.pack(side='left', padx=5)
        self.yes_btn.pack(side='left', padx=2)
        self.no_btn.pack(side='left', padx=2)
    
    def hide_confirmation(self):
        """Hide the confirmation dialog"""
        self.confirm_label.pack_forget()
        self.yes_btn.pack_forget()
        self.no_btn.pack_forget()
    
    def ask_poweroff_confirmation(self):
        """Show poweroff confirmation dialog"""
        self.show_confirmation()
        # Auto-hide after 10 seconds if no response
        self.root.after(10000, self.poweroff_cancelled)
    
    def poweroff_confirmed(self):
        """User confirmed poweroff"""
        self.hide_confirmation()
        self.poweroff_system()
    
    def poweroff_cancelled(self):
        """User cancelled poweroff"""
        self.hide_confirmation()
    
    def restart_measurement(self):
        """Restart measurement with new background calculation"""
        try:
            # Stop current measurement
            was_running = self.running
            if self.running:
                self.running = False
                if self.cap:
                    # Give time for thread to stop
                    time.sleep(0.5)
            
            # Reset measurement state
            self.bg_mean = None
            self.initial_width = 0
            self.avg_width_1s = 0
            self.width_buffer = []
            self.last_time = time.time()
            
            # Start measurement again if it was running
            if was_running:
                self.start_measurement()
                
        except Exception as e:
            print(f"Error restarting measurement: {e}")
    
    def poweroff_system(self):
        """Safely power off the Linux system"""
        try:
            # Save settings before shutdown
            self.save_settings()
            print("Powering off Linux system...")
            
            # Show countdown
            for i in range(3, 0, -1):
                if hasattr(self, 'datetime_label'):
                    self.datetime_label.config(text=f"SHUTTING DOWN IN {i}...")
                self.root.update()
                time.sleep(1)
            
            # Stop application
            self.running = False
            if self.cap:
                self.cap.release()
            
            # Linux shutdown command
            try:
                # Try different shutdown commands for various Linux systems
                shutdown_commands = [
                    ['sudo', 'shutdown', '-h', 'now'],  # Most common
                    ['sudo', 'poweroff'],                # systemd systems  
                    ['sudo', 'halt', '-p'],             # SysV systems
                    ['shutdown', '-h', 'now']            # If running as root
                ]
                
                for cmd in shutdown_commands:
                    try:
                        print(f"Trying: {' '.join(cmd)}")
                        subprocess.run(cmd, check=True, timeout=5)
                        break
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                        continue
                else:
                    # All commands failed - just exit
                    print("Could not shutdown system - no sudo access or wrong commands")
                    print("Please run manually: sudo shutdown -h now")
                    self.root.destroy()
                    
            except Exception as e:
                print(f"Shutdown command failed: {e}")
                self.root.destroy()
                
        except Exception as e:
            print(f"Error during poweroff: {e}")
            self.root.destroy()
    
    def select_entry(self, key):
        """Select an entry field for editing"""
        self.current_entry = key
        
        # Clear any previous error messages
        self.clear_all_error_messages()
        
        # Highlight and activate selected entry
        for k, entry in self.entries.items():
            if k == key:
                entry.config(bg='yellow', state='normal')
                # Initialize current_value with what's already in the field
                self.current_value = entry.get()
                entry.focus_set()  # Focus on the entry
            else:
                entry.config(bg='white', state='disabled')
    
    def numpad_input(self, digit):
        """Handle numpad input - append to existing text in entry box"""
        if self.current_entry is None:
            return
            
        entry = self.entries[self.current_entry]
        # Get current text from entry box
        current_text = entry.get()
        
        # Check character limit (10 characters max)
        if len(current_text) >= 10:
            self.show_error_message(self.current_entry, "Maximum 10 characters allowed")
            return
            
        # Append new digit
        new_text = current_text + digit
        
        # Update entry box
        entry.delete(0, tk.END)
        entry.insert(0, new_text)
        
        # Update current_value to match what's in the box
        self.current_value = new_text
    
    def clear_input(self):
        """Clear current input in entry box completely"""
        self.current_value = ""
        if self.current_entry:
            entry = self.entries[self.current_entry]
            entry.delete(0, tk.END)
            # Leave field empty instead of restoring original value
    
    def submit_value(self):
        """Submit the entered value and apply immediately with validation"""
        if self.current_entry is None:
            return
            
        # Get value from entry box instead of current_value
        entry = self.entries[self.current_entry]
        input_value = entry.get().strip()
        
        if input_value == "":
            return
            
        try:
            # Store old value for rollback
            old_value = self.config[self.current_entry]
            
            # Convert to appropriate type with validation
            if self.current_entry == 'NUM_ROWS':
                value = int(input_value)
                if value < 1 or value > 100:
                    raise ValueError("NUM_ROWS must be between 1 and 100")
            elif self.current_entry == 'TARGET_FPS':
                value = int(input_value)
                if value < 1 or value > 60:
                    raise ValueError("TARGET_FPS must be between 1 and 60")
            elif self.current_entry in ['TOP_MARGIN_RATIO', 'BOTTOM_MARGIN_RATIO']:
                value = float(input_value)
                if value < 0.0 or value > 0.9:
                    raise ValueError("Margin ratios must be between 0.0 and 0.9")
            elif self.current_entry == 'COLOR_THRESH':
                value = float(input_value)
                if value < 1.0 or value > 500.0:
                    raise ValueError("COLOR_THRESH must be between 1.0 and 500.0")
            elif self.current_entry == 'WIDTH_THRESHOLD':
                value = float(input_value)
                if value < 0.1 or value > 100.0:
                    raise ValueError("WIDTH_THRESHOLD must be between 0.1 and 100.0")
            else:
                value = float(input_value)
            
            # Additional validation: check if margins make sense together
            if self.current_entry in ['TOP_MARGIN_RATIO', 'BOTTOM_MARGIN_RATIO']:
                temp_config = self.config.copy()
                temp_config[self.current_entry] = value
                if temp_config['TOP_MARGIN_RATIO'] + temp_config['BOTTOM_MARGIN_RATIO'] >= 1.0:
                    raise ValueError("Combined margins must be < 1.0")
            
            # Update config and entry
            self.config[self.current_entry] = value
            entry = self.entries[self.current_entry]
            entry.delete(0, tk.END)
            entry.insert(0, str(value))
            entry.config(bg='lightgreen', state='disabled')  # Disable after successful submit
            
            # Save settings immediately after successful update
            self.save_settings()
            
            # Clear selection
            self.current_entry = None
            self.current_value = ""
            
            # Reset entry color after 1 second
            self.root.after(1000, self.reset_entry_colors)
            
        except ValueError as e:
            # Show error message under the field
            if self.current_entry:
                self.show_error_message(self.current_entry, str(e))
                # Restore the old value in the entry box
                self.entries[self.current_entry].delete(0, tk.END)
                self.entries[self.current_entry].insert(0, str(self.config[self.current_entry]))
                self.entries[self.current_entry].config(bg='lightcoral')
            
            # Clear input but keep field selected for retry
            self.current_value = ""
            
            # Reset after 3 seconds
            self.root.after(3000, self.reset_entry_colors)
    
    def reset_entry_colors(self):
        """Reset entry box colors and states"""
        for entry in self.entries.values():
            entry.config(bg='white', state='disabled')  # All fields disabled by default
        self.clear_all_error_messages()  # Clear all error messages
    
    def cancel_input(self):
        """Cancel current input"""
        if self.current_entry:
            entry = self.entries[self.current_entry]
            # Restore original value
            entry.delete(0, tk.END)
            entry.insert(0, str(self.config[self.current_entry]))
            entry.config(bg='white', state='disabled')
            
        self.current_entry = None
        self.current_value = ""
    
    def reset_all_settings(self):
        """Reset all settings to default values"""
        try:
            # Reset config to defaults
            self.config = self.default_config.copy()
            
            # Update all entry boxes
            for key, entry in self.entries.items():
                entry.config(state='normal')  # Enable to update
                entry.delete(0, tk.END)
                entry.insert(0, str(self.config[key]))
                entry.config(bg='lightblue', state='disabled')  # Show reset and disable
            
            # Clear current selection
            self.current_entry = None
            self.current_value = ""
            self.error_display_label.config(text="All settings reset to defaults!", fg='blue', bg='lightgray')
            
            # Reset colors after 2 seconds
            self.root.after(2000, self.reset_entry_colors)
            
        except Exception as e:
            self.error_display_label.config(text=f"Reset failed: {str(e)}", fg='red', bg='lightgray')
    
    def estimate_bg_from_row(self, frame):
        """Estimate background color from center row"""
        h, w = frame.shape[:2]
        y = h // 2
        row = frame[y, :, :].reshape(-1, 3).astype(np.float32)
        intensities = cv2.cvtColor(row.reshape(1, -1, 3), cv2.COLOR_BGR2GRAY).reshape(-1,1)
        _, labels, centers = cv2.kmeans(intensities, 2, None,
                                        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                                        3, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(labels.flatten())
        bg_label = np.argmax(counts)
        bg_mask = (labels.flatten() == bg_label)
        bg_pixels = row[bg_mask]
        return bg_pixels.mean(axis=0)
    
    def start_measurement(self):
        """Start the measurement process"""
        if self.running:
            return
            
        self.running = True
        # Wait for previous thread to finish if it exists
        if hasattr(self, 'video_thread') and self.video_thread and self.video_thread.is_alive():
            self.video_thread.join(timeout=1.0)
            
        self.video_thread = threading.Thread(target=self.run_measurement)
        self.video_thread.daemon = True
        self.video_thread.start()
    
    def run_measurement(self):
        """Run measurement with live video display in canvas"""
        self.cap = cv2.VideoCapture(SOURCE)  # Fixed to camera 0
        ret, first = self.cap.read()
        if not ret:
            self.status_label.config(text="Status: Failed to open video", fg='red')
            return

        h, w = first.shape[:2]
        
        # Initialize measurement
        self.bg_mean = self.estimate_bg_from_row(first).astype(np.float32)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
        
        # Compute initial width with bounds checking
        top_m = max(0, int(h * self.config['TOP_MARGIN_RATIO']))
        bottom_m = max(0, int(h * self.config['BOTTOM_MARGIN_RATIO']))
        
        # Ensure we have valid region
        available_height = h - top_m - bottom_m
        if available_height < self.config['NUM_ROWS']:
            # Fallback to simple division if margins too large
            top_m = 10
            bottom_m = 10
            available_height = h - 20
            if available_height < self.config['NUM_ROWS']:
                available_height = h - 2
                top_m = 1
                bottom_m = 1
        
        end_y = h - bottom_m - 1
        if end_y <= top_m:
            end_y = h - 1
            top_m = 0
            
        sample_ys = np.linspace(top_m, end_y, min(self.config['NUM_ROWS'], available_height), dtype=int)
        # Ensure all indices are valid
        sample_ys = np.clip(sample_ys, 0, h-1)
        
        thresh2 = self.config['COLOR_THRESH']**2
        diff2 = np.sum((first.astype(np.float32) - self.bg_mean)**2, axis=2)
        mask0 = diff2 > thresh2
        mask0 = cv2.morphologyEx(mask0.astype(np.uint8)*255, cv2.MORPH_OPEN, kernel)
        mask0 = cv2.morphologyEx(mask0, cv2.MORPH_CLOSE, kernel)
        mask0 = mask0.astype(bool)

        initial_widths = []
        for y in sample_ys:
            row = mask0[y, :]
            if row.any():
                xs = np.where(row)[0]
                initial_widths.append(xs[-1] - xs[0])
            else:
                initial_widths.append(0)
        self.initial_width = float(np.mean(initial_widths))
        self.avg_width_1s = self.initial_width
        
        self.status_label.config(text="Status: Running", fg='green')
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # Recalculate margins with current config and bounds checking
            h, w = frame.shape[:2]
            top_m = max(0, int(h * self.config['TOP_MARGIN_RATIO']))
            bottom_m = max(0, int(h * self.config['BOTTOM_MARGIN_RATIO']))
            
            # Ensure we have valid region
            available_height = h - top_m - bottom_m
            if available_height < self.config['NUM_ROWS']:
                # Fallback to simple division if margins too large
                top_m = 10
                bottom_m = 10
                available_height = h - 20
                if available_height < self.config['NUM_ROWS']:
                    available_height = h - 2
                    top_m = 1
                    bottom_m = 1
            
            end_y = h - bottom_m - 1
            if end_y <= top_m:
                end_y = h - 1
                top_m = 0
                
            sample_ys = np.linspace(top_m, end_y, min(self.config['NUM_ROWS'], available_height), dtype=int)
            # Ensure all indices are valid
            sample_ys = np.clip(sample_ys, 0, h-1)
            
            # Process frame
            thresh2 = self.config['COLOR_THRESH']**2
            diff2 = np.sum((frame.astype(np.float32) - self.bg_mean)**2, axis=2)
            mask_full = diff2 > thresh2
            m = cv2.morphologyEx(mask_full.astype(np.uint8)*255, cv2.MORPH_OPEN, kernel)
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
            mask_full = m.astype(bool)

            vis = frame.copy()
            per_widths = []

            for y in sample_ys:
                # Additional safety check
                if y < 0 or y >= h:
                    continue
                    
                row = mask_full[y, :].copy()
                if row.any():
                    xs = np.where(row)[0]
                    row[xs[0]:xs[-1]+1] = True
                    width = xs[-1] - xs[0]
                else:
                    width = 0
                per_widths.append(width)
                vis[y, row] = (0, 255, 0)
                vis[y, ~row] = (255, 255, 255)

            frame_avg = float(np.mean(per_widths))
            self.width_buffer.append(frame_avg)

            now = time.time()
            if now - self.last_time >= 1.0:
                self.avg_width_1s = float(np.mean(self.width_buffer)) if self.width_buffer else 0.0
                self.width_buffer.clear()
                self.last_time = now

            dev = abs(self.avg_width_1s - self.initial_width)
            if dev <= self.config['WIDTH_THRESHOLD']:
                status = f"OK Dev={dev:.1f}px"
                col = (0,255,0)
            else:
                status = f"ALERT Dev={dev:.1f}px"
                col = (0,0,255)

            # Add text to video
            cv2.putText(vis, f"Init: {self.initial_width:.1f}px", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(vis, f"Avg1s: {self.avg_width_1s:.1f}px", (10,60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
            cv2.putText(vis, status, (10,90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

            # Display in canvas (use root.after for smooth updates)
            self.root.after_idle(lambda: self.display_frame(vis))
            
            # Better frame rate control
            target_frame_time = 1.0 / max(1, self.config['TARGET_FPS'])  # Prevent division by zero
            elapsed = time.time() - now
            sleep_time = max(0, target_frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

        if self.cap:
            self.cap.release()
        self.running = False
    
    def display_frame(self, frame):
        """Display frame in the canvas without flickering"""
        if self.update_pending:
            return
            
        try:
            self.update_pending = True
            
            # Get canvas dimensions
            canvas_width = self.video_canvas.winfo_width()
            canvas_height = self.video_canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                self.update_pending = False
                return
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Calculate scaling to fit canvas while maintaining aspect ratio
            h, w = frame_rgb.shape[:2]
            scale_x = canvas_width / w
            scale_y = canvas_height / h
            scale = min(scale_x, scale_y)
            
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Resize frame
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
            
            # Convert to PIL Image and then to ImageTk
            pil_image = Image.fromarray(frame_resized)
            new_photo = ImageTk.PhotoImage(image=pil_image)
            
            # Calculate position to center image
            x = (canvas_width - new_w) // 2
            y = (canvas_height - new_h) // 2
            
            # Update canvas only if we have a valid photo
            if new_photo:
                # Don't clear canvas, just update the image
                if hasattr(self, 'canvas_image_id'):
                    self.video_canvas.itemconfig(self.canvas_image_id, image=new_photo)
                    self.video_canvas.coords(self.canvas_image_id, x, y)
                else:
                    self.canvas_image_id = self.video_canvas.create_image(x, y, anchor='nw', image=new_photo)
                
                # Keep reference to prevent garbage collection
                self.current_photo = new_photo
                
        except Exception as e:
            pass  # Ignore display errors
        finally:
            self.update_pending = False
    
    def exit_app(self):
        """Exit the application and save settings"""
        print("Saving settings before exit...")
        self.save_settings()
        
        self.running = False
        if self.cap:
            self.cap.release()
        self.root.destroy()
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

def main():
    app = MeasureLinesIntegratedGUI()
    app.run()

if __name__ == "__main__":
    main()