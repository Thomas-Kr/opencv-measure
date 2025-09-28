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

class MeasureLinesIntegratedGUI:
    def __init__(self):
        # Settings file path
        self.settings_file = "measure_lines_settings.json"
        
        # Default configuration values (keep backup for reset)
        self.default_config = {
            'VIDEO_SOURCE': 0,
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
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Set fullscreen properly for X server
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
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
        top_panel = Frame(main_frame, bg='darkblue', height=50)
        top_panel.pack(fill='x', pady=(0, 5))
        top_panel.pack_propagate(False)
        
        # Left side of top panel - Control buttons
        left_top_frame = Frame(top_panel, bg='darkblue')
        left_top_frame.pack(side='left', padx=10, pady=5)
        
        # RESTART button
        self.restart_btn = Button(left_top_frame, text="RESTART", width=10, height=1,
                                 font=('Arial', 12, 'bold'), bg='yellow', fg='black',
                                 command=self.restart_measurement)
        self.restart_btn.pack(side='left', padx=5)
        
        # POWEROFF button (next to RESTART)
        self.poweroff_btn = Button(left_top_frame, text="POWEROFF", width=10, height=1,
                                  font=('Arial', 12, 'bold'), bg='red', fg='white',
                                  command=self.ask_poweroff_confirmation)
        self.poweroff_btn.pack(side='left', padx=5)
        
        # Center - Confirmation area (initially hidden)
        self.confirm_frame = Frame(top_panel, bg='darkblue')
        self.confirm_frame.pack(side='left', padx=20, pady=5)
        
        self.confirm_label = Label(self.confirm_frame, text="Are you sure?", 
                                  font=('Arial', 12, 'bold'), bg='darkblue', fg='yellow')
        
        self.yes_btn = Button(self.confirm_frame, text="YES", width=6, height=1,
                             font=('Arial', 11, 'bold'), bg='darkred', fg='white',
                             command=self.poweroff_confirmed)
        
        self.no_btn = Button(self.confirm_frame, text="NO", width=6, height=1,
                            font=('Arial', 11, 'bold'), bg='green', fg='white',
                            command=self.poweroff_cancelled)
        
        # Initially hide confirmation elements
        self.hide_confirmation()
        
        # Right side of top panel - Date/Time
        right_top_frame = Frame(top_panel, bg='darkblue')
        right_top_frame.pack(side='right', padx=10, pady=5)
        
        # Date and Time
        self.datetime_label = Label(right_top_frame, text="Loading...", 
                                   font=('Arial', 14, 'bold'), bg='darkblue', fg='white')
        self.datetime_label.pack()
        
        # Start datetime update
        self.update_datetime()
        
        # Content frame for video and controls
        content_frame = Frame(main_frame, bg='black')
        content_frame.pack(fill='both', expand=True)
        
        # Left side - Video display (takes most of the space)
        video_frame = Frame(content_frame, bg='black')
        video_frame.pack(side='left', fill='both', expand=True)
        
        # Video canvas
        self.video_canvas = Canvas(video_frame, bg='black')
        self.video_canvas.pack(fill='both', expand=True)
        
        # Right side - Controls (expanded width for better label visibility)
        control_frame = Frame(content_frame, bg='darkgray', width=400)
        control_frame.pack(side='right', fill='y', padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # Reset All button at the top right
        reset_top_btn = Button(control_frame, text="Reset All", width=12, height=1,
                              font=('Arial', 12, 'bold'), bg='orange', fg='white',
                              command=self.reset_all_settings)
        reset_top_btn.pack(pady=(10, 20), anchor='ne')
        
        # Settings section
        settings_label = Label(control_frame, text="Settings", 
                              font=('Arial', 14, 'bold'), bg='darkgray')
        settings_label.pack(pady=(0, 10))
        
        # Settings frame with scrolling (expanded height)
        settings_canvas = Canvas(control_frame, bg='lightgray', height=250)
        settings_canvas.pack(fill='x', pady=(0, 10))
        
        settings_scroll_frame = Frame(settings_canvas, bg='lightgray')
        settings_canvas.create_window((0, 0), window=settings_scroll_frame, anchor='nw')
        
        # Create entry boxes for each config value
        self.entries = {}
        self.setup_config_entries(settings_scroll_frame)
        
        # Update scroll region
        settings_scroll_frame.update_idletasks()
        settings_canvas.configure(scrollregion=settings_canvas.bbox('all'))
        
        # Current input display
        self.input_display = Label(control_frame, text="Click field to edit", 
                                  font=('Arial', 12), bg='lightblue', relief='sunken')
        self.input_display.pack(fill='x', pady=(10, 5))
        
        # Numpad
        self.setup_numpad(control_frame)
        
        # Status display
        status_frame = Frame(control_frame, bg='darkgray')
        status_frame.pack(fill='x', pady=(10, 0))
        
        self.status_label = Label(status_frame, text="Status: Starting...", 
                                 font=('Arial', 12, 'bold'), bg='darkgray', fg='white')
        self.status_label.pack()
        
        self.measurement_label = Label(status_frame, text="Width: --", 
                                      font=('Arial', 11), bg='darkgray', fg='yellow')
        self.measurement_label.pack()
        
        # Exit button
        exit_btn = Button(control_frame, text="EXIT (ESC)", 
                         command=self.exit_app,
                         bg='red', fg='white', font=('Arial', 12, 'bold'))
        exit_btn.pack(side='bottom', fill='x', pady=10)
        
        # Bind ESC key
        self.root.bind('<Escape>', lambda e: self.exit_app())
        
    def setup_config_entries(self, parent):
        """Create entry boxes for configuration values"""
        for i, (key, value) in enumerate(self.config.items()):
            # Frame for each setting
            setting_frame = Frame(parent, bg='lightgray')
            setting_frame.pack(fill='x', pady=2, padx=5)
            
            # Label (increased width and better font)
            label = Label(setting_frame, text=f"{key}:", width=20, anchor='w',
                         bg='lightgray', font=('Arial', 10))
            label.pack(side='left')
            
            # Entry (increased width, initially disabled but with default values)
            entry = Entry(setting_frame, font=('Arial', 10), width=12)
            entry.insert(0, str(value))  # Insert value while enabled
            entry.config(state='disabled')  # Then disable
            entry.bind('<Button-1>', lambda e, k=key: self.select_entry(k))
            entry.pack(side='right')
            
            self.entries[key] = entry
    
    def setup_numpad(self, parent):
        """Create compact numpad"""
        numpad_frame = Frame(parent, bg='darkgray')
        numpad_frame.pack(fill='x', pady=10)
        
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
                    btn = Button(button_row, text=btn_text, width=6, height=2,
                                font=('Arial', 14, 'bold'), bg='orange',
                                command=self.clear_input)
                else:
                    btn = Button(button_row, text=btn_text, width=6, height=2,
                                font=('Arial', 14, 'bold'), bg='lightblue',
                                command=lambda t=btn_text: self.numpad_input(t))
                btn.pack(side='left', padx=2, pady=2)
        
        # Action buttons (larger for touch)
        action_frame = Frame(numpad_frame, bg='darkgray')
        action_frame.pack(pady=8)
        
        submit_btn = Button(action_frame, text="Submit", width=10, height=2,
                           font=('Arial', 12, 'bold'), bg='lightgreen',
                           command=self.submit_value)
        submit_btn.pack(side='left', padx=3)
        
        cancel_btn = Button(action_frame, text="Cancel", width=10, height=2,
                           font=('Arial', 12, 'bold'), bg='lightcoral',
                           command=self.cancel_input)
        cancel_btn.pack(side='left', padx=3)
    
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
            
            # Show feedback
            if hasattr(self, 'input_display'):
                self.input_display.config(text="Measurement restarted! New background calculated.", bg='lightgreen')
                self.root.after(3000, lambda: self.input_display.config(text="Click field to edit", bg='lightblue'))
                
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
        self.current_value = ""
        self.input_display.config(text=f"Editing {key} - use numpad below", bg='yellow')
        
        # Highlight and activate selected entry
        for k, entry in self.entries.items():
            if k == key:
                entry.config(bg='yellow', state='normal')
                entry.delete(0, tk.END)  # Clear for new input
                entry.focus_set()  # Focus on the entry
            else:
                entry.config(bg='white', state='disabled')
    
    def numpad_input(self, digit):
        """Handle numpad input - write directly to entry box"""
        if self.current_entry is None:
            return
            
        self.current_value += digit
        # Write directly to the selected entry box
        entry = self.entries[self.current_entry]
        entry.delete(0, tk.END)
        entry.insert(0, self.current_value)
    
    def clear_input(self):
        """Clear current input in entry box"""
        self.current_value = ""
        if self.current_entry:
            entry = self.entries[self.current_entry]
            entry.delete(0, tk.END)
    
    def submit_value(self):
        """Submit the entered value and apply immediately with validation"""
        if self.current_entry is None or self.current_value == "":
            return
            
        try:
            # Store old value for rollback
            old_value = self.config[self.current_entry]
            
            # Convert to appropriate type with validation
            if self.current_entry == 'VIDEO_SOURCE':
                try:
                    value = int(self.current_value)
                    if value < 0:
                        raise ValueError("Video source must be >= 0")
                except ValueError:
                    # Try as string (file path)
                    value = self.current_value
                    if not value.strip():
                        raise ValueError("Video source cannot be empty")
            elif self.current_entry == 'NUM_ROWS':
                value = int(self.current_value)
                if value < 1 or value > 20:
                    raise ValueError("NUM_ROWS must be between 1 and 20")
            elif self.current_entry == 'TARGET_FPS':
                value = int(self.current_value)
                if value < 1 or value > 60:
                    raise ValueError("TARGET_FPS must be between 1 and 60")
            elif self.current_entry in ['TOP_MARGIN_RATIO', 'BOTTOM_MARGIN_RATIO']:
                value = float(self.current_value)
                if value < 0.0 or value > 0.9:
                    raise ValueError("Margin ratios must be between 0.0 and 0.9")
            elif self.current_entry == 'COLOR_THRESH':
                value = float(self.current_value)
                if value < 1.0 or value > 500.0:
                    raise ValueError("COLOR_THRESH must be between 1.0 and 500.0")
            elif self.current_entry == 'WIDTH_THRESHOLD':
                value = float(self.current_value)
                if value < 0.1 or value > 100.0:
                    raise ValueError("WIDTH_THRESHOLD must be between 0.1 and 100.0")
            else:
                value = float(self.current_value)
            
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
            self.input_display.config(text="Value updated & saved! Click field to edit another", bg='lightgreen')
            
            # Reset entry color after 1 second
            self.root.after(1000, self.reset_entry_colors)
            
        except ValueError as e:
            # Show error and restore old value
            self.input_display.config(text=f"Error: {str(e)}", bg='red')
            # Restore the old value in the entry box
            if self.current_entry:
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
        self.input_display.config(text="Click field to edit", bg='lightblue')
    
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
        self.input_display.config(text="Click field to edit", bg='lightblue')
    
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
            self.input_display.config(text="All settings reset to defaults!", bg='lightblue')
            
            # Reset colors after 2 seconds
            self.root.after(2000, self.reset_entry_colors)
            
        except Exception as e:
            self.input_display.config(text=f"Reset failed: {str(e)}", bg='red')
    
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
        self.cap = cv2.VideoCapture(self.config['VIDEO_SOURCE'])
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
                status = f"OK Δ={dev:.1f}px"
                col = (0,255,0)
                status_color = 'green'
            else:
                status = f"ALERT Δ={dev:.1f}px"
                col = (0,0,255)
                status_color = 'red'

            # Add text to video
            cv2.putText(vis, f"Init: {self.initial_width:.1f}px", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(vis, f"Avg1s: {self.avg_width_1s:.1f}px", (10,60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
            cv2.putText(vis, status, (10,90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

            # Display in canvas (use root.after for smooth updates)
            self.root.after_idle(lambda: self.display_frame(vis))
            
            # Update status labels (less frequently to reduce flicker)
            if hasattr(self, 'last_status_update'):
                if now - self.last_status_update > 0.5:  # Update every 500ms
                    self.measurement_label.config(text=f"Width: {self.avg_width_1s:.1f}px ({status})", 
                                                 fg=status_color)
                    self.last_status_update = now
            else:
                self.last_status_update = now
                self.measurement_label.config(text=f"Width: {self.avg_width_1s:.1f}px ({status})", 
                                             fg=status_color)
            
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