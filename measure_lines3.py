import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import ttk, Frame, Label, Entry, Button, Canvas
from PIL import Image, ImageTk
import threading

class MeasureLinesIntegratedGUI:
    def __init__(self):
        # Default configuration values
        self.config = {
            'VIDEO_SOURCE': 0,
            'NUM_ROWS': 5,
            'COLOR_THRESH': 220.0,
            'TARGET_FPS': 20,
            'TOP_MARGIN_RATIO': 0.2,
            'BOTTOM_MARGIN_RATIO': 0.6,
            'WIDTH_THRESHOLD': 5.0
        }
        
        # GUI variables
        self.root = tk.Tk()
        self.root.title("OpenCV Measure Lines - Live Control")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='black')
        
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
        
        # Measurement state
        self.bg_mean = None
        self.initial_width = 0
        self.avg_width_1s = 0
        self.width_buffer = []
        self.last_time = time.time()
        
        self.setup_gui()
        self.start_measurement()
        
    def setup_gui(self):
        # Main container
        main_frame = Frame(self.root, bg='black')
        main_frame.pack(fill='both', expand=True)
        
        # Left side - Video display (takes most of the space)
        video_frame = Frame(main_frame, bg='black')
        video_frame.pack(side='left', fill='both', expand=True)
        
        # Video canvas
        self.video_canvas = Canvas(video_frame, bg='black')
        self.video_canvas.pack(fill='both', expand=True)
        
        # Right side - Controls (fixed width)
        control_frame = Frame(main_frame, bg='darkgray', width=300)
        control_frame.pack(side='right', fill='y', padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # Title
        title_label = Label(control_frame, text="Live Controls", 
                           font=('Arial', 16, 'bold'), bg='darkgray')
        title_label.pack(pady=(10, 20))
        
        # Settings section
        settings_label = Label(control_frame, text="Settings", 
                              font=('Arial', 14, 'bold'), bg='darkgray')
        settings_label.pack(pady=(0, 10))
        
        # Settings frame with scrolling
        settings_canvas = Canvas(control_frame, bg='lightgray', height=200)
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
            
            # Label
            label = Label(setting_frame, text=f"{key}:", width=15, anchor='w',
                         bg='lightgray', font=('Arial', 9))
            label.pack(side='left')
            
            # Entry
            entry = Entry(setting_frame, font=('Arial', 10), width=10)
            entry.insert(0, str(value))
            entry.bind('<Button-1>', lambda e, k=key: self.select_entry(k))
            entry.pack(side='right')
            
            self.entries[key] = entry
    
    def setup_numpad(self, parent):
        """Create compact numpad"""
        numpad_frame = Frame(parent, bg='darkgray')
        numpad_frame.pack(fill='x', pady=10)
        
        # Number buttons (compact 4x3 grid)
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
                    btn = Button(button_row, text=btn_text, width=4, height=1,
                                font=('Arial', 10), bg='orange',
                                command=self.clear_input)
                else:
                    btn = Button(button_row, text=btn_text, width=4, height=1,
                                font=('Arial', 10), bg='lightblue',
                                command=lambda t=btn_text: self.numpad_input(t))
                btn.pack(side='left', padx=1, pady=1)
        
        # Action buttons (smaller)
        action_frame = Frame(numpad_frame, bg='darkgray')
        action_frame.pack(pady=5)
        
        submit_btn = Button(action_frame, text="Submit", width=8, height=1,
                           font=('Arial', 10), bg='lightgreen',
                           command=self.submit_value)
        submit_btn.pack(side='left', padx=2)
        
        cancel_btn = Button(action_frame, text="Cancel", width=8, height=1,
                           font=('Arial', 10), bg='lightcoral',
                           command=self.cancel_input)
        cancel_btn.pack(side='left', padx=2)
    
    def select_entry(self, key):
        """Select an entry field for editing"""
        self.current_entry = key
        self.current_value = ""
        self.input_display.config(text=f"Editing {key}: ", bg='yellow')
        
        # Highlight selected entry
        for k, entry in self.entries.items():
            if k == key:
                entry.config(bg='yellow')
            else:
                entry.config(bg='white')
    
    def numpad_input(self, digit):
        """Handle numpad input"""
        if self.current_entry is None:
            return
            
        self.current_value += digit
        self.input_display.config(text=f"Editing {self.current_entry}: {self.current_value}")
    
    def clear_input(self):
        """Clear current input"""
        self.current_value = ""
        if self.current_entry:
            self.input_display.config(text=f"Editing {self.current_entry}: ")
    
    def submit_value(self):
        """Submit the entered value and apply immediately"""
        if self.current_entry is None or self.current_value == "":
            return
            
        try:
            # Convert to appropriate type
            if self.current_entry == 'VIDEO_SOURCE':
                try:
                    value = int(self.current_value)
                except ValueError:
                    value = self.current_value
            elif self.current_entry in ['NUM_ROWS', 'TARGET_FPS']:
                value = int(self.current_value)
            else:
                value = float(self.current_value)
            
            # Update config and entry
            self.config[self.current_entry] = value
            self.entries[self.current_entry].delete(0, tk.END)
            self.entries[self.current_entry].insert(0, str(value))
            self.entries[self.current_entry].config(bg='lightgreen')
            
            # Clear selection
            self.current_entry = None
            self.current_value = ""
            self.input_display.config(text="Value updated! Taking effect...", bg='lightgreen')
            
            # Reset entry color after 1 second
            self.root.after(1000, self.reset_entry_colors)
            
        except ValueError:
            self.input_display.config(text="Invalid value! Try again.", bg='red')
    
    def reset_entry_colors(self):
        """Reset entry box colors"""
        for entry in self.entries.values():
            entry.config(bg='white')
        self.input_display.config(text="Click field to edit", bg='lightblue')
    
    def cancel_input(self):
        """Cancel current input"""
        if self.current_entry:
            self.entries[self.current_entry].config(bg='white')
        self.current_entry = None
        self.current_value = ""
        self.input_display.config(text="Click field to edit", bg='lightblue')
    
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
        
        # Compute initial width
        top_m = int(h * self.config['TOP_MARGIN_RATIO'])
        bottom_m = int(h * self.config['BOTTOM_MARGIN_RATIO'])
        sample_ys = np.linspace(top_m, h - bottom_m - 1, self.config['NUM_ROWS'], dtype=int)
        
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

            # Recalculate margins with current config
            h, w = frame.shape[:2]
            top_m = int(h * self.config['TOP_MARGIN_RATIO'])
            bottom_m = int(h * self.config['BOTTOM_MARGIN_RATIO'])
            sample_ys = np.linspace(top_m, h - bottom_m - 1, self.config['NUM_ROWS'], dtype=int)
            
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

            # Display in canvas
            self.display_frame(vis)
            
            # Update status labels
            self.measurement_label.config(text=f"Width: {self.avg_width_1s:.1f}px ({status})", 
                                         fg=status_color)
            
            # Control frame rate
            time.sleep(1.0 / self.config['TARGET_FPS'])

        if self.cap:
            self.cap.release()
        self.running = False
    
    def display_frame(self, frame):
        """Display frame in the canvas"""
        try:
            # Get canvas dimensions
            canvas_width = self.video_canvas.winfo_width()
            canvas_height = self.video_canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
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
            photo = ImageTk.PhotoImage(image=pil_image)
            
            # Calculate position to center image
            x = (canvas_width - new_w) // 2
            y = (canvas_height - new_h) // 2
            
            # Clear canvas and display image
            self.video_canvas.delete("all")
            self.video_canvas.create_image(x, y, anchor='nw', image=photo)
            self.video_canvas.image = photo  # Keep a reference
            
        except Exception as e:
            pass  # Ignore display errors
    
    def exit_app(self):
        """Exit the application"""
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