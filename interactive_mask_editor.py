"""
Interactive Mask Editor
========================
Load video, extract pattern from PDF, manually align and edit mask
"""

import numpy as np
import tifffile
import cv2
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io


class MaskEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive Mask Editor")
        self.root.geometry("1400x900")
        
        # Data
        self.video = None
        self.frame_idx = 0
        self.current_frame = None
        self.pattern_mask = None  # Original pattern from PDF
        self.working_mask = None  # Current working mask
        self.pattern_offset_x = 0.0
        self.pattern_offset_y = 0.0
        self.pattern_scale = 1.0  # Pattern zoom/scale factor
        self.pattern_rotation = 0.0  # Rotation in degrees
        self.pattern_flip_horizontal = False  # Mirror/flip the pattern horizontally
        self.px_per_mm_x = 1.0  # Calibration: pixels per mm (width)
        self.px_per_mm_y = 1.0  # Calibration: pixels per mm (height)
        
        # Drawing state
        self.drawing = False
        self.dragging_pattern = False
        self.rotating_pattern = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.brush_radius = 5
        self.mode = "move"  # "move", "add", or "remove"
        
        # Create UI
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI layout"""
        # Top toolbar
        toolbar = tk.Frame(self.root, bg="lightgray")
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Button(toolbar, text="Load Video", command=self.load_video).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Load PDF Pattern", command=self.load_pdf).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Calibration", command=self.show_calibration).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Save Mask", command=self.save_mask).pack(side=tk.LEFT, padx=5)
        
        tk.Label(toolbar, text="Frame:").pack(side=tk.LEFT, padx=5)
        self.frame_scale = tk.Scale(toolbar, from_=0, to=100, orient=tk.HORIZONTAL, 
                                    command=self.on_frame_change, length=150)
        self.frame_scale.pack(side=tk.LEFT, padx=5)
        
        tk.Label(toolbar, text="Brush:").pack(side=tk.LEFT, padx=5)
        self.brush_scale = tk.Scale(toolbar, from_=1, to=20, orient=tk.HORIZONTAL, 
                                    command=self.on_brush_change, length=100)
        self.brush_scale.set(5)
        self.brush_scale.pack(side=tk.LEFT, padx=5)
        
        tk.Label(toolbar, text="Pattern Scale:").pack(side=tk.LEFT, padx=5)
        self.pattern_scale_widget = tk.Scale(toolbar, from_=0.5, to=3.0, orient=tk.HORIZONTAL, 
                                            command=self.on_pattern_scale_change, resolution=0.1, length=100)
        self.pattern_scale_widget.set(1.0)
        self.pattern_scale_widget.pack(side=tk.LEFT, padx=5)
        
        tk.Label(toolbar, text="Rotation:").pack(side=tk.LEFT, padx=5)
        self.pattern_rotation_widget = tk.Scale(toolbar, from_=0, to=360, orient=tk.HORIZONTAL, 
                                               command=self.on_pattern_rotation_change, length=100)
        self.pattern_rotation_widget.set(0)
        self.pattern_rotation_widget.pack(side=tk.LEFT, padx=5)
        
        tk.Button(toolbar, text="Move Pattern", command=lambda: self.set_mode("move"),
                 bg="lightyellow", relief=tk.SUNKEN).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Add Mode", command=lambda: self.set_mode("add"),
                 bg="lightgreen").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Remove Mode", command=lambda: self.set_mode("remove"),
                 bg="lightcoral").pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Flip Pattern", command=self.toggle_flip,
                 bg="lightblue").pack(side=tk.LEFT, padx=2)
        
        # Main content area
        content = tk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel: Image with pattern
        left_panel = tk.Frame(content)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(left_panel, text="Video Frame + Pattern").pack()
        self.canvas_frame = tk.Frame(left_panel)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Right panel: Controls and info
        right_panel = tk.Frame(content, bg="lightyellow", width=250)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)
        right_panel.pack_propagate(False)
        
        tk.Label(right_panel, text="Instructions:", font=("Arial", 12, "bold"), 
                bg="lightyellow").pack(anchor=tk.W, padx=5, pady=5)
        
        info_text = """
STEP 1: Load Video
- Choose TIFF file
- Use Frame slider

STEP 2: Calibration
- Click "Calibration"
- Enter actual tissue size
- Set video frame size

STEP 3: Load PDF Pattern
- Choose PDF file
- Pattern scaled correctly

STEP 4: Align Pattern
- Click "Move Pattern"
- Drag to position

STEP 5: Edit Mask
- Add Mode / Remove Mode
- Paint to adjust

STEP 6: Save
- Click "Save Mask"
        """
        
        tk.Label(right_panel, text=info_text, bg="lightyellow", 
                justify=tk.LEFT, font=("Courier", 9)).pack(anchor=tk.W, padx=5, pady=5)
        
        tk.Label(right_panel, text="Status:", font=("Arial", 10, "bold"),
                bg="lightyellow").pack(anchor=tk.W, padx=5, pady=(10, 0))
        self.status_label = tk.Label(right_panel, text="Ready", bg="lightyellow",
                                    fg="blue", wraplength=220, justify=tk.LEFT)
        self.status_label.pack(anchor=tk.W, padx=5, pady=5)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('scroll_event', self.on_mouse_wheel)
        
    def load_video(self):
        """Load TIFF video file"""
        filepath = filedialog.askopenfilename(
            filetypes=[("TIFF files", "*.tif *.tiff"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            self.video = tifffile.imread(filepath)
            if self.video.ndim != 3:
                messagebox.showerror("Error", "Video must be 3D array (frames, height, width)")
                return
            
            n_frames = self.video.shape[0]
            self.frame_scale.config(to=n_frames-1)
            self.frame_idx = 0
            self.frame_scale.set(0)
            
            self.status_label.config(text=f"✓ Video loaded: {n_frames} frames, "
                                        f"{self.video.shape[1]}×{self.video.shape[2]} px")
            self.update_display()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load video: {str(e)}")
    
    def load_pdf(self):
        """Load PDF pattern"""
        filepath = filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            # Open PDF and render first page
            doc = fitz.open(filepath)
            page = doc[0]
            
            # Get page size in mm (for reference)
            rect = page.rect
            page_width_mm = rect.width / 2.834645669  # 72 DPI conversion
            page_height_mm = rect.height / 2.834645669
            
            # Render to image (high resolution)
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            
            # Convert to grayscale
            if img_array.shape[2] >= 3:
                img_gray = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2GRAY)
            else:
                img_gray = img_array[:, :, 0]
            
            # Extract pattern (white regions)
            _, pattern = cv2.threshold(img_gray, 200, 255, cv2.THRESH_BINARY)
            
            # Scale pattern proportionally - don't force 128x128
            # Fit to canvas while preserving aspect ratio
            if self.video is not None:
                h, w = self.video.shape[1:3]
                # Scale so pattern fits well in frame (use ~80% of frame)
                max_size = int(min(h, w) * 0.8)
                scale_factor = max_size / max(pattern.shape[0], pattern.shape[1])
                
                if scale_factor < 1:  # Only downscale if needed
                    new_h = int(pattern.shape[0] * scale_factor)
                    new_w = int(pattern.shape[1] * scale_factor)
                    pattern = cv2.resize(pattern, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            self.pattern_mask = pattern.astype(bool)
            self.working_mask = None  # Will be created on first transform
            self.pattern_offset_x = 0.0
            self.pattern_offset_y = 0.0
            self.pattern_scale = 1.0
            self.pattern_rotation = 0.0
            self.pattern_flip_horizontal = False
            self.pattern_scale_widget.set(1.0)
            self.pattern_rotation_widget.set(0)
            
            self.status_label.config(text=f"✓ PDF loaded: {pattern.shape[1]}×{pattern.shape[0]} px\n"
                                        f"Page: {page_width_mm:.2f}×{page_height_mm:.2f} mm")
            self.update_display()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PDF: {str(e)}")
    
    def on_frame_change(self, value):
        """Frame slider changed"""
        if self.video is None:
            return
        self.frame_idx = int(value)
        self.update_display()
    
    def on_brush_change(self, value):
        """Brush size changed"""
        self.brush_radius = int(value)
    
    def on_pattern_scale_change(self, value):
        """Pattern scale changed"""
        self.pattern_scale = float(value)
        self.update_display()
    
    def on_pattern_rotation_change(self, value):
        """Pattern rotation changed"""
        self.pattern_rotation = float(value)
        self.update_display()
    
    def toggle_flip(self):
        """Toggle horizontal flip of the pattern"""
        if self.pattern_mask is None:
            messagebox.showwarning("Warning", "No pattern loaded")
            return
        
        self.pattern_flip_horizontal = not self.pattern_flip_horizontal
        flip_status = "ON" if self.pattern_flip_horizontal else "OFF"
        self.status_label.config(text=f"Pattern flip: {flip_status}")
        
        # Reset working mask to apply transform
        self.working_mask = None
        self.update_display()
    
    def show_calibration(self):
        """Show calibration dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibration")
        dialog.geometry("400x300")
        
        tk.Label(dialog, text="Tissue Calibration", font=("Arial", 14, "bold")).pack(pady=10)
        
        tk.Label(dialog, text="Enter the actual physical size of tissue sample:").pack(pady=5)
        
        tk.Label(dialog, text="Sample width (mm):").pack()
        width_entry = tk.Entry(dialog, width=20)
        width_entry.insert(0, "9.0")
        width_entry.pack()
        
        tk.Label(dialog, text="Sample height (mm):").pack(pady=(10, 0))
        height_entry = tk.Entry(dialog, width=20)
        height_entry.insert(0, "9.0")
        height_entry.pack()
        
        tk.Label(dialog, text="Video frame size (pixels):").pack(pady=(10, 0))
        tk.Label(dialog, text=f"{self.video.shape[2]} × {self.video.shape[1]} px" if self.video is not None else "No video loaded").pack()
        
        def apply_calibration():
            try:
                width_mm = float(width_entry.get())
                height_mm = float(height_entry.get())
                
                if self.video is not None:
                    video_w = self.video.shape[2]
                    video_h = self.video.shape[1]
                    
                    # Calculate pixel to mm conversion
                    self.px_per_mm_x = video_w / width_mm
                    self.px_per_mm_y = video_h / height_mm
                    
                    msg = f"Calibration set:\n{self.px_per_mm_x:.2f} px/mm (X)\n{self.px_per_mm_y:.2f} px/mm (Y)"
                    self.status_label.config(text=f"✓ {msg}")
                    messagebox.showinfo("Success", msg)
                    dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid input")
        
        tk.Button(dialog, text="Apply", command=apply_calibration, bg="lightgreen").pack(pady=10)
    
    def set_mode(self, new_mode):
        """Set mode (move, add, or remove)"""
        self.mode = new_mode
        # Initialize working mask when entering paint mode
        if new_mode in ["add", "remove"]:
            if self.working_mask is None:
                self.working_mask = self.apply_pattern_transform()
        self.status_label.config(text=f"Mode: {new_mode.upper()}")
    
    def on_mouse_press(self, event):
        """Mouse pressed on canvas"""
        if event.xdata is None or event.ydata is None:
            return
        
        self.last_mouse_x = event.xdata
        self.last_mouse_y = event.ydata
        
        if event.button == 1:  # Left click - drag pattern
            if self.mode == "move":
                if self.pattern_mask is not None:
                    current_mask = self.apply_pattern_transform()
                    if current_mask is not None:
                        x, y = int(event.xdata), int(event.ydata)
                        if 0 <= y < current_mask.shape[0] and 0 <= x < current_mask.shape[1]:
                            if current_mask[int(y), int(x)]:
                                self.dragging_pattern = True
            else:
                self.drawing = True
                self.paint_on_mask(event.xdata, event.ydata)
        
        elif event.button == 3:  # Right click - rotate pattern
            if self.mode == "move":
                self.rotating_pattern = True
    
    def on_mouse_release(self, event):
        """Mouse released"""
        self.drawing = False
        self.dragging_pattern = False
        self.rotating_pattern = False
    
    def on_mouse_move(self, event):
        """Mouse moved on canvas"""
        if event.xdata is None or event.ydata is None:
            return
        
        if self.dragging_pattern:
            # Move pattern with pixel-by-pixel precision
            delta_x = event.xdata - self.last_mouse_x
            delta_y = event.ydata - self.last_mouse_y
            
            self.pattern_offset_x += delta_x
            self.pattern_offset_y += delta_y
            
            self.last_mouse_x = event.xdata
            self.last_mouse_y = event.ydata
            
            # Reset working mask to apply transform
            self.working_mask = None
            self.update_display()
        
        elif self.rotating_pattern:
            # Rotate pattern based on vertical mouse movement
            delta_y = event.ydata - self.last_mouse_y
            
            # 1 pixel movement = 1 degree rotation
            self.pattern_rotation += delta_y
            
            # Normalize rotation to 0-360
            self.pattern_rotation = self.pattern_rotation % 360
            self.pattern_rotation_widget.set(int(self.pattern_rotation))
            
            self.last_mouse_y = event.ydata
            
            # Reset working mask to apply transform
            self.working_mask = None
            self.update_display()
        
        elif self.drawing and event.xdata is not None and event.ydata is not None:
            self.paint_on_mask(event.xdata, event.ydata)
    
    def apply_pattern_transform(self):
        """Apply offset, scale, and rotation to pattern mask"""
        if self.pattern_mask is None or self.video is None:
            return None
        
        h, w = self.video.shape[1:3]
        
        # Step 1: Scale pattern if needed
        if abs(self.pattern_scale - 1.0) > 0.01:
            new_h = int(self.pattern_mask.shape[0] * self.pattern_scale)
            new_w = int(self.pattern_mask.shape[1] * self.pattern_scale)
            pattern_scaled = cv2.resize(self.pattern_mask.astype(np.uint8), (new_w, new_h), 
                                       interpolation=cv2.INTER_LINEAR) > 0.5
        else:
            pattern_scaled = self.pattern_mask.copy()
        
        # Step 2: Apply flip if needed
        if self.pattern_flip_horizontal:
            pattern_flipped = cv2.flip(pattern_scaled.astype(np.uint8), 1) > 0.5  # 1 = flip horizontally
        else:
            pattern_flipped = pattern_scaled
        
        # Step 3: Apply rotation if needed
        if abs(self.pattern_rotation) > 0.1:
            rows, cols = pattern_flipped.shape
            center_y, center_x = rows / 2.0, cols / 2.0
            
            # getRotationMatrix2D expects (center_x, center_y) but it's (x, y) = (col, row)
            rotation_matrix = cv2.getRotationMatrix2D((center_x, center_y), self.pattern_rotation, 1.0)
            
            pattern_rotated = cv2.warpAffine(pattern_flipped.astype(np.uint8), rotation_matrix, 
                                            (cols, rows), borderValue=0, flags=cv2.INTER_LINEAR)
            pattern_rotated = pattern_rotated > 0.5
        else:
            pattern_rotated = pattern_flipped
        
        # Step 4: Create output mask and place pattern with offset
        output_mask = np.zeros((h, w), dtype=bool)
        
        ph, pw = pattern_rotated.shape
        
        # Center the pattern and apply offset
        y_start = int((h - ph) / 2.0 + self.pattern_offset_y)
        x_start = int((w - pw) / 2.0 + self.pattern_offset_x)
        
        y_end = y_start + ph
        x_end = x_start + pw
        
        # Crop to valid region
        y_start_clipped = max(0, y_start)
        x_start_clipped = max(0, x_start)
        y_end_clipped = min(h, y_end)
        x_end_clipped = min(w, x_end)
        
        # Calculate pattern region that fits
        py_start = max(0, -y_start)
        px_start = max(0, -x_start)
        py_end = ph - max(0, y_end - h)
        px_end = pw - max(0, x_end - w)
        
        if y_end_clipped > y_start_clipped and x_end_clipped > x_start_clipped:
            if py_end > py_start and px_end > px_start:
                output_mask[y_start_clipped:y_end_clipped, x_start_clipped:x_end_clipped] = \
                    pattern_rotated[py_start:py_end, px_start:px_end]
        
        return output_mask
    
    def on_mouse_wheel(self, event):
        """Resize pattern using mouse wheel scroll
        Scroll up = zoom in (larger)
        Scroll down = zoom out (smaller)
        """
        if self.pattern_mask is None:
            return
        
        scale_factor = 1.10  # 10% change per scroll
        
        if event.button == 'up':
            self.pattern_scale *= scale_factor
        elif event.button == 'down':
            self.pattern_scale /= scale_factor
        
        # Clamp to valid range [0.5, 3.0]
        self.pattern_scale = max(0.5, min(3.0, self.pattern_scale))
        
        # Update UI slider
        self.pattern_scale_widget.set(self.pattern_scale)
        
        # Force fresh transform and update display
        self.working_mask = None
        self.update_display()
        
        self.status_label.config(text=f"Pattern scale: {self.pattern_scale:.2f}x")
    
    def paint_on_mask(self, x, y):
        """Paint on the transformed pattern mask"""
        if self.pattern_mask is None or self.video is None:
            return
        
        # Use working mask if available, otherwise get fresh transform
        if self.working_mask is None:
            self.working_mask = self.apply_pattern_transform()
        
        current_mask = self.working_mask
        if current_mask is None:
            return
        
        x, y = int(x), int(y)
        h, w = current_mask.shape
        
        # Bounds check
        if not (0 <= y < h and 0 <= x < w):
            return
        
        # Create circle brush
        yy, xx = np.ogrid[-self.brush_radius:self.brush_radius+1, 
                          -self.brush_radius:self.brush_radius+1]
        circle = xx*xx + yy*yy <= self.brush_radius**2
        
        # Apply paint within bounds
        y_min = max(0, y - self.brush_radius)
        y_max = min(h, y + self.brush_radius + 1)
        x_min = max(0, x - self.brush_radius)
        x_max = min(w, x + self.brush_radius + 1)
        
        # Calculate which part of circle to use
        cy_min = self.brush_radius - (y - y_min)
        cy_max = self.brush_radius + (y_max - y)
        cx_min = self.brush_radius - (x - x_min)
        cx_max = self.brush_radius + (x_max - x)
        
        circle_trimmed = circle[cy_min:cy_max, cx_min:cx_max]
        
        # Apply the brush
        if self.mode == "add":
            current_mask[y_min:y_max, x_min:x_max][circle_trimmed] = True
        else:  # remove
            current_mask[y_min:y_max, x_min:x_max][circle_trimmed] = False
        
        # Save back
        self.working_mask = current_mask
        self.update_display()
    
    def update_display(self):
        """Update the display"""
        if self.video is None:
            return
        
        self.ax.clear()
        
        # Get current frame
        frame = self.video[self.frame_idx].astype(np.float32)
        
        # Normalize for display
        vmin, vmax = np.percentile(frame, (2, 98))
        frame_display = (frame - vmin) / (vmax - vmin)
        
        # Show frame
        self.ax.imshow(frame_display, cmap='gray')
        
        # Display the mask (use working_mask if available with edits, otherwise fresh transform)
        if self.pattern_mask is not None:
            # Use working_mask if we've done painting, otherwise use fresh transform
            if self.working_mask is not None:
                display_mask = self.working_mask
            else:
                display_mask = self.apply_pattern_transform()
            
            if display_mask is not None:
                overlay = np.zeros((*frame_display.shape, 4))
                overlay[display_mask] = [0, 1, 0, 0.5]  # Green for tissue
                self.ax.imshow(overlay)
        
        # Show offset and scale info if moving pattern
        info_text = ""
        if self.mode == "move":
            flip_indicator = " | Flipped" if self.pattern_flip_horizontal else ""
            info_text = f" | Pos: ({self.pattern_offset_x:.1f}, {self.pattern_offset_y:.1f}) | Scale: {self.pattern_scale:.2f}x | Rot: {self.pattern_rotation:.0f}°{flip_indicator}"
        
        self.ax.set_title(f"Frame {self.frame_idx}/{self.video.shape[0]-1} | "
                         f"Brush: {self.brush_radius}px | Mode: {self.mode.upper()}{info_text}")
        self.ax.axis('off')
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def save_mask(self):
        """Save the working mask"""
        # Use working mask if available (with edits), otherwise use fresh transform
        if self.working_mask is not None:
            save_mask_data = self.working_mask
        else:
            save_mask_data = self.apply_pattern_transform()
        
        if save_mask_data is None:
            messagebox.showwarning("Warning", "No mask to save")
            return
        
        # Ask user where to save
        output_path = filedialog.asksaveasfilename(
            defaultextension=".tif",
            filetypes=[("TIFF files", "*.tif *.tiff"), ("All files", "*.*")],
            initialfile="tissue_mask.tif"
        )
        
        if not output_path:
            return
        
        try:
            # Convert bool to uint8
            mask_save = (save_mask_data * 255).astype(np.uint8)
            
            tifffile.imwrite(output_path, mask_save)
            
            flip_status = "Yes" if self.pattern_flip_horizontal else "No"
            self.status_label.config(text=f"✓ Mask saved:\n{output_path}\n"
                                        f"Pos: ({self.pattern_offset_x:.1f}, {self.pattern_offset_y:.1f})\n"
                                        f"Scale: {self.pattern_scale:.2f}x | Rot: {self.pattern_rotation:.0f}° | Flipped: {flip_status}")
            flip_status = "Yes" if self.pattern_flip_horizontal else "No"
            messagebox.showinfo("Success", f"Mask saved!\n\n"
                                         f"Path: {output_path}\n"
                                         f"Position: ({self.pattern_offset_x:.1f}, {self.pattern_offset_y:.1f})\n"
                                         f"Scale: {self.pattern_scale:.2f}x\n"
                                         f"Rotation: {self.pattern_rotation:.0f}°\n"
                                         f"Flipped: {flip_status}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save mask: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    editor = MaskEditor(root)
    root.mainloop()
