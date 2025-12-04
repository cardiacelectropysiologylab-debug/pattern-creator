import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk
import math
import random
import os
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors

# MatTek well sizes
MATTEK_SIZES = {
    "35mm dish (10mm well)": 10.0,
    "35mm dish (8mm well)": 8.0,
    "12-well plate": 3.7,
    "24-well plate": 2.6,
    "96-well plate": 0.8,
}

# ========== INTERSTITIAL PATTERN (RECTANGULAR MESH) ==========
def add_interstitial(c, cx, cy, radius_pt, coverage, rect_length_mm, rect_width_mm, 
                     spacing_along_mm, spacing_across_mm, angle_deg=0, indentation=0.0):
    """Add rectangular mesh pattern (interstitial fibrosis)
    
    Creates a grid of rectangles with:
    - Fixed rectangle dimensions (length x width)
    - Fixed spacing along and across rectangles
    - Coverage controlled by rectangle size and spacing
    - Optional indentation of alternating rows
    """
    if coverage <= 0:
        return
    
    rect_length_pt = rect_length_mm * mm
    rect_width_pt = rect_width_mm * mm
    spacing_along_pt = spacing_along_mm * mm
    spacing_across_pt = spacing_across_mm * mm
    
    # Calculate actual coverage based on rectangle and spacing
    area_per_unit = (rect_length_pt + spacing_along_pt) * (rect_width_pt + spacing_across_pt)
    area_rect = rect_length_pt * rect_width_pt
    actual_coverage = area_rect / area_per_unit if area_per_unit > 0 else 0
    
    # Adjust rectangle size to match target coverage
    if actual_coverage > 0 and actual_coverage < 0.99:
        scale_factor = math.sqrt(coverage / actual_coverage)
        adjusted_length_pt = rect_length_pt * scale_factor
        adjusted_width_pt = rect_width_pt * scale_factor
    else:
        adjusted_length_pt = rect_length_pt
        adjusted_width_pt = rect_width_pt
    
    # Create grid of rectangles
    period_along = adjusted_length_pt + spacing_along_pt
    period_across = adjusted_width_pt + spacing_across_pt
    
    # Calculate how many rectangles fit
    diag = radius_pt * 3
    num_along = int(math.ceil(diag * 2 / period_along)) + 4
    num_across = int(math.ceil(diag * 2 / period_across)) + 4
    
    # Center the grid
    start_along = -num_along * period_along / 2.0
    start_across = -num_across * period_across / 2.0
    
    c.saveState()
    c.translate(cx, cy)
    c.rotate(angle_deg)
    c.translate(-cx, -cy)
    c.setFillColor(colors.black)
    
    # Draw rectangles in grid
    for i in range(num_along):
        for j in range(num_across):
            x = cx + start_along + i * period_along
            y = cy + start_across + j * period_across
            
            # Apply indentation to every other row
            if j % 2 == 1:
                x += period_along * (indentation / 100.0)
            
            # Only draw if within circle (rough check)
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist <= radius_pt + adjusted_length_pt:
                c.rect(x - adjusted_length_pt / 2.0, y - adjusted_width_pt / 2.0,
                       adjusted_length_pt, adjusted_width_pt, stroke=0, fill=1)
    
    c.restoreState()

def add_interstitial_preview(draw, cx, cy, radius_px, coverage, rect_length_px, rect_width_px,
                             spacing_along_px, spacing_across_px, angle_deg, indentation=0.0):
    """Preview for interstitial rectangular mesh pattern"""
    if coverage <= 0:
        return
    
    spacing_along_px = max(1.0, spacing_along_px)
    spacing_across_px = max(1.0, spacing_across_px)
    
    # Calculate actual coverage
    area_per_unit = (rect_length_px + spacing_along_px) * (rect_width_px + spacing_across_px)
    area_rect = rect_length_px * rect_width_px
    actual_coverage = area_rect / area_per_unit if area_per_unit > 0 else 0
    
    # Adjust rectangle size to match target coverage
    if actual_coverage > 0 and actual_coverage < 0.99:
        scale_factor = math.sqrt(coverage / actual_coverage)
        adjusted_length_px = rect_length_px * scale_factor
        adjusted_width_px = rect_width_px * scale_factor
    else:
        adjusted_length_px = rect_length_px
        adjusted_width_px = rect_width_px
    
    # Create grid
    period_along = adjusted_length_px + spacing_along_px
    period_across = adjusted_width_px + spacing_across_px
    
    diag = radius_px * 3
    num_along = int(math.ceil(diag * 2 / period_along)) + 4
    num_across = int(math.ceil(diag * 2 / period_across)) + 4
    
    start_along = -num_along * period_along / 2.0
    start_across = -num_across * period_across / 2.0
    
    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    
    # Draw rectangles
    for i in range(num_along):
        for j in range(num_across):
            x = start_along + i * period_along
            y = start_across + j * period_across
            
            # Apply indentation to every other row
            if j % 2 == 1:
                x += period_along * (indentation / 100.0)
            
            # Rotate around center
            x_rot = cx + x * cos_a - y * sin_a
            y_rot = cy + x * sin_a + y * cos_a
            
            # Only draw if within circle
            dist = math.sqrt((x_rot - cx) ** 2 + (y_rot - cy) ** 2)
            if dist <= radius_px + adjusted_length_px:
                # Rectangle corners
                half_length = adjusted_length_px / 2.0
                half_width = adjusted_width_px / 2.0
                
                corners = [
                    (-half_length, -half_width),
                    (half_length, -half_width),
                    (half_length, half_width),
                    (-half_length, half_width)
                ]
                
                # Rotate corners
                points = []
                for dx, dy in corners:
                    px = x_rot + dx * cos_a - dy * sin_a
                    py = y_rot + dx * sin_a + dy * cos_a
                    points.append((px, py))
                
                draw.polygon(points, fill=0, outline=0)

# ========== PATCHY PATTERN (IRREGULAR ISLANDS) ==========
def add_patchy(c, cx, cy, radius_pt, coverage, island_size_mm, num_islands, density=1.0):
    """Add patchy pattern with irregular island shapes
    
    Based on research: Creates fibrosis as distinct islands/patches with:
    - Irregular, organic island boundaries (using Fourier harmonics)
    - Random distribution of islands within tissue
    - Variable island sizes based on density parameter
    - Realistic fibrotic remodeling appearance
    """
    if coverage <= 0 or num_islands <= 0:
        return
    
    c.setFillColor(colors.black)
    
    # Calculate island size based on desired coverage
    area_total = math.pi * radius_pt ** 2
    area_per_island = (coverage * area_total) / num_islands
    base_radius_pt = math.sqrt(area_per_island / math.pi)
    
    # Generate islands
    for _ in range(int(num_islands)):
        # Random position within circle (weighted toward center by density)
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** (1.0 / max(0.1, density))
        r = radius_pt * r_factor
        island_cx = cx + r * math.cos(angle)
        island_cy = cy + r * math.sin(angle)
        
        # Variable island size
        size_variation = random.uniform(0.6, 1.4) * density
        island_radius_pt = base_radius_pt * size_variation
        
        # Create irregular island boundary using Fourier harmonics
        # This creates organic, realistic fibrotic island shapes
        n_points = 32  # Number of points to define the boundary
        points = []
        
        # Fourier harmonics for realistic irregularity
        num_harmonics = 4
        amplitudes = [random.uniform(0.15, 0.4) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            angle_point = (2 * math.pi * i) / n_points
            
            # Calculate radial variation using Fourier series
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * angle_point + phases[h])
            r_variation = r_variation / num_harmonics
            
            # Apply variation to radius (creates wavy boundary)
            r_local = island_radius_pt * (1.0 + 0.6 * r_variation)
            x_local = r_local * math.cos(angle_point)
            y_local = r_local * math.sin(angle_point)
            
            points.append((island_cx + x_local, island_cy + y_local))
        
        # Draw the irregular island
        if len(points) > 0:
            p = c.beginPath()
            p.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                p.lineTo(x, y)
            p.close()
            c.drawPath(p, stroke=0, fill=1)

def add_patchy_preview(draw, cx, cy, radius_px, coverage, island_size_px, num_islands, density=1.0):
    """Preview for patchy irregular island pattern"""
    if coverage <= 0 or num_islands <= 0:
        return
    
    # Calculate island size based on coverage
    area_total = math.pi * radius_px ** 2
    area_per_island = (coverage * area_total) / num_islands
    base_radius_px = math.sqrt(area_per_island / math.pi)
    
    # Generate islands
    for _ in range(int(num_islands)):
        # Random position within circle
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** (1.0 / max(0.1, density))
        r = radius_px * r_factor
        island_cx = cx + r * math.cos(angle)
        island_cy = cy + r * math.sin(angle)
        
        # Variable island size
        size_variation = random.uniform(0.6, 1.4) * density
        island_radius_px = base_radius_px * size_variation
        
        # Create irregular boundary
        n_points = 32
        points = []
        
        num_harmonics = 4
        amplitudes = [random.uniform(0.15, 0.4) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            angle_point = (2 * math.pi * i) / n_points
            
            # Fourier series for boundary variation
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * angle_point + phases[h])
            r_variation = r_variation / num_harmonics
            
            # Apply variation
            r_local = island_radius_px * (1.0 + 0.6 * r_variation)
            x_local = r_local * math.cos(angle_point)
            y_local = r_local * math.sin(angle_point)
            
            points.append((island_cx + x_local, island_cy + y_local))
        
        # Draw the island
        if len(points) > 0:
            draw.polygon(points, fill=0, outline=0)

# ========== COMPACT PATTERN (CENTRAL SCAR) ==========
def add_compact(c, cx, cy, radius_pt, coverage, irregularity, offset_x_mm, offset_y_mm, 
                split_scar=False, split_distance_mm=0.0, left_offset_x_mm=0.0, left_offset_y_mm=0.0,
                split_rotation_left=0.0, right_offset_x_mm=0.0, right_offset_y_mm=0.0, split_rotation_right=0.0):
    """Add solid central region with irregular shape (compact fibrosis)
    
    With optional split into two independently movable circles for arrhythmia development
    """
    if coverage <= 0:
        return
    
    scar_radius_pt = radius_pt * math.sqrt(coverage / (2.0 if split_scar else 1.0))
    
    offset_x_pt = offset_x_mm * mm
    offset_y_pt = offset_y_mm * mm
    
    c.setFillColor(colors.black)
    
    if split_scar:
        # Two independently positioned circles
        split_dist_pt = split_distance_mm * mm
        
        # Left circle
        left_cx = cx + (left_offset_x_mm * mm)
        left_cy = cy + (left_offset_y_mm * mm)
        draw_irregular_circle(c, left_cx, left_cy, scar_radius_pt, irregularity, split_rotation_left)
        
        # Right circle
        right_cx = cx + (right_offset_x_mm * mm)
        right_cy = cy + (right_offset_y_mm * mm)
        draw_irregular_circle(c, right_cx, right_cy, scar_radius_pt, irregularity, split_rotation_right)
    else:
        # Single circle
        scar_cx = cx + offset_x_pt
        scar_cy = cy + offset_y_pt
        draw_irregular_circle(c, scar_cx, scar_cy, scar_radius_pt, irregularity, 0.0)

def draw_irregular_circle(c, cx, cy, radius_pt, irregularity, rotation_deg=0.0):
    """Helper function to draw a single irregular circle with rotation"""
    if irregularity <= 0.01:
        c.circle(cx, cy, radius_pt, stroke=0, fill=1)
    else:
        n_points = 64
        points = []
        
        num_harmonics = 5
        amplitudes = [random.uniform(0.5, 1.0) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            angle = (2 * math.pi * i) / n_points
            
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * angle + phases[h])
            
            r_variation = r_variation / num_harmonics
            r_factor = 1.0 + irregularity * r_variation
            
            # Apply rotation to angle
            rotated_angle = angle + math.radians(rotation_deg)
            
            r = radius_pt * r_factor
            x = cx + r * math.cos(rotated_angle)
            y = cy + r * math.sin(rotated_angle)
            points.append((x, y))
        
        p = c.beginPath()
        p.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            p.lineTo(x, y)
        p.close()
        c.drawPath(p, stroke=0, fill=1)

def add_compact_preview(draw, cx, cy, radius_px, coverage, irregularity, offset_x_px, offset_y_px,
                        split_scar=False, split_distance_px=0.0, left_offset_x_px=0.0, left_offset_y_px=0.0,
                        split_rotation_left=0.0, right_offset_x_px=0.0, right_offset_y_px=0.0, split_rotation_right=0.0):
    """Preview for compact pattern with optional split and independent rotation"""
    if coverage <= 0:
        return
    
    scar_radius_px = radius_px * math.sqrt(coverage / (2.0 if split_scar else 1.0))
    
    if split_scar:
        # Two circles
        split_dist_px = split_distance_px
        
        left_cx = cx + left_offset_x_px
        left_cy = cy + left_offset_y_px
        draw_irregular_circle_preview(draw, left_cx, left_cy, scar_radius_px, irregularity, split_rotation_left)
        
        right_cx = cx + right_offset_x_px
        right_cy = cy + right_offset_y_px
        draw_irregular_circle_preview(draw, right_cx, right_cy, scar_radius_px, irregularity, split_rotation_right)
    else:
        # Single circle
        scar_cx = cx + offset_x_px
        scar_cy = cy + offset_y_px
        draw_irregular_circle_preview(draw, scar_cx, scar_cy, scar_radius_px, irregularity, 0.0)

def draw_irregular_circle_preview(draw, cx, cy, radius_px, irregularity, rotation_deg=0.0):
    """Helper function to draw a single irregular circle in preview with rotation"""
    if irregularity <= 0.01:
        draw.ellipse((cx - radius_px, cy - radius_px,
                     cx + radius_px, cy + radius_px), fill=0)
    else:
        n_points = 64
        points = []
        
        num_harmonics = 5
        amplitudes = [random.uniform(0.5, 1.0) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            angle = (2 * math.pi * i) / n_points
            
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * angle + phases[h])
            
            r_variation = r_variation / num_harmonics
            r_factor = 1.0 + irregularity * r_variation
            
            # Apply rotation to angle
            rotated_angle = angle + math.radians(rotation_deg)
            
            r = radius_px * r_factor
            x = cx + r * math.cos(rotated_angle)
            y = cy + r * math.sin(rotated_angle)
            points.append((x, y))
        
        draw.polygon(points, fill=0, outline=0)

# ========== GUI ==========
class PatternCreatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pattern Creator - Interstitial Mesh")
        self.root.geometry("1000x700")
        
        self.preview_image_full = None
        self.zoom_level = 1.0
        self.last_seed = None
        
        self._build_widgets()
        self.on_preview()
    
    def _build_widgets(self):
        # Variables
        self.var_pattern_type = tk.StringVar(value="Interstitial")
        self.var_mattek_size = tk.StringVar(value="35mm dish (10mm well)")
        self.var_coverage = tk.DoubleVar(value=20.0)
        self.var_white_border = tk.DoubleVar(value=15.0)
        
        # Interstitial parameters
        self.var_rect_length = tk.DoubleVar(value=500.0)  # µm
        self.var_rect_width = tk.DoubleVar(value=200.0)   # µm
        self.var_spacing_along = tk.DoubleVar(value=200.0)  # µm
        self.var_spacing_across = tk.DoubleVar(value=200.0)  # µm
        self.var_angle = tk.DoubleVar(value=0.0)
        self.var_indentation = tk.DoubleVar(value=0.0)
        
        # Diffuse parameters
        self.var_randomness = tk.DoubleVar(value=50.0)  # 0-100%

        # Patchy parameters
        self.var_num_islands = tk.DoubleVar(value=10.0)
        self.var_density = tk.DoubleVar(value=1.0)
        
        # Compact parameters
        self.var_irregularity = tk.DoubleVar(value=0.5)
        self.var_offset_x = tk.DoubleVar(value=0.0)
        self.var_offset_y = tk.DoubleVar(value=0.0)
        self.var_split_scar = tk.BooleanVar(value=False)
        self.var_split_distance = tk.DoubleVar(value=2.0)
        self.var_split_rotation_left = tk.DoubleVar(value=0.0)
        self.var_split_rotation_right = tk.DoubleVar(value=0.0)
        # Independent offsets for split circles
        self.var_left_offset_x = tk.DoubleVar(value=0.0)
        self.var_left_offset_y = tk.DoubleVar(value=0.0)
        self.var_right_offset_x = tk.DoubleVar(value=0.0)
        self.var_right_offset_y = tk.DoubleVar(value=0.0)
        
        # Store canvas image ID for compact offset adjustment
        self.compact_offset_mode = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        controls = ttk.Frame(main)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        preview_frame = ttk.Frame(main)
        preview_frame.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        
        row = 0
        
        # Pattern type selector
        ttk.Label(controls, text="Pattern Type:").grid(row=row, column=0, sticky="w")
        pattern_menu = ttk.Combobox(controls, textvariable=self.var_pattern_type,
                                    values=["Interstitial", "Diffuse", "Patchy", "Compact"],
                                    state="readonly", width=20)
        pattern_menu.grid(row=row, column=1, sticky="ew", pady=2)
        pattern_menu.bind("<<ComboboxSelected>>", self.on_pattern_change)
        row += 1
        
        # MatTek size
        ttk.Label(controls, text="MatTek Well:").grid(row=row, column=0, sticky="w")
        mattek_menu = ttk.Combobox(controls, textvariable=self.var_mattek_size,
                                   values=list(MATTEK_SIZES.keys()),
                                   state="readonly", width=20)
        mattek_menu.grid(row=row, column=1, sticky="ew", pady=2)
        mattek_menu.bind("<<ComboboxSelected>>", self.on_preview)
        row += 1
        
        # Coverage
        self._add_slider(controls, row, "Total coverage (%):", self.var_coverage, 0, 95, "%",
                        callback=self.on_preview)
        ttk.Label(controls, text="  (of entire circle)", 
                 font=("TkDefaultFont", 8, "italic")).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        
        # White border
        self._add_slider(controls, row, "White border (% radius):", self.var_white_border, 0, 40, "%",
                        callback=self.on_preview)
        ttk.Label(controls, text="  (for electrical propagation)", 
                 font=("TkDefaultFont", 8, "italic")).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        
        # Coverage info display
        self.coverage_info_frame = ttk.LabelFrame(controls, text="Coverage Information", padding=5)
        self.coverage_info_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5, 10))
        row += 1
        
        self.total_coverage_label = ttk.Label(self.coverage_info_frame, text="Total coverage: 20.0%", 
                                              font=("TkDefaultFont", 9))
        self.total_coverage_label.pack(anchor="w", pady=2)
        
        self.inner_coverage_label = ttk.Label(self.coverage_info_frame, text="Inner pattern coverage: 0%", 
                                              font=("TkDefaultFont", 9, "italic"))
        self.inner_coverage_label.pack(anchor="w", pady=2)
        
        self.actual_rect_length_label = ttk.Label(self.coverage_info_frame, text="Adjusted rect length: 0 µm",
                                                  font=("TkDefaultFont", 9, "italic"))
        self.actual_rect_length_label.pack(anchor="w", pady=2)
        
        self.actual_rect_width_label = ttk.Label(self.coverage_info_frame, text="Adjusted rect width: 0 µm",
                                                 font=("TkDefaultFont", 9, "italic"))
        self.actual_rect_width_label.pack(anchor="w", pady=2)
        
        # Interstitial parameters frame
        self.params_frame = ttk.LabelFrame(controls, text="Rectangle Mesh Parameters", padding=5)
        self.params_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1
        
        self._add_entry(self.params_frame, 0, "Rectangle length (µm):", self.var_rect_length, "µm",
                       callback=self.on_preview)
        self._add_entry(self.params_frame, 1, "Rectangle width (µm):", self.var_rect_width, "µm",
                       callback=self.on_preview)
        self._add_entry(self.params_frame, 2, "Spacing along (µm):", self.var_spacing_along, "µm",
                       callback=self.on_preview)
        self._add_entry(self.params_frame, 3, "Spacing across (µm):", self.var_spacing_across, "µm",
                       callback=self.on_preview)
        self._add_entry(self.params_frame, 4, "Rotation angle (deg):", self.var_angle, "°",
                       callback=self.on_preview)
        self._add_slider(self.params_frame, 5, "Indentation (%):", self.var_indentation, 0.0, 100.0, "%",
                        callback=self.on_preview)
        ttk.Label(self.params_frame, text="  (offset of alternating rows, 0=aligned, 50=half-offset)", 
                 font=("TkDefaultFont", 8, "italic")).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        # Buttons
        btn_frame = ttk.Frame(controls)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        btn_generate = ttk.Button(btn_frame, text="Generate PDF", command=self.on_generate)
        btn_generate.pack(side="left", fill="x", expand=True)
        btn_frame.columnconfigure(0, weight=1)
        
        # Preview area with zoom controls
        preview_header = ttk.Frame(preview_frame)
        preview_header.pack(fill="x", pady=(0, 5))
        
        self.preview_label = ttk.Label(preview_header, text="Preview:")
        self.preview_label.pack(side="left")
        
        # Zoom controls
        zoom_frame = ttk.Frame(preview_header)
        zoom_frame.pack(side="right")
        
        ttk.Button(zoom_frame, text="-", width=3, command=self.zoom_out).pack(side="left", padx=2)
        self.zoom_label = ttk.Label(zoom_frame, text="100%", width=6)
        self.zoom_label.pack(side="left", padx=2)
        ttk.Button(zoom_frame, text="+", width=3, command=self.zoom_in).pack(side="left", padx=2)
        ttk.Button(zoom_frame, text="Reset", width=6, command=self.zoom_reset).pack(side="left", padx=2)
        
        # Preview canvas with scrollbars
        canvas_frame = ttk.Frame(preview_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal")
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical")
        
        self.preview_canvas = tk.Canvas(canvas_frame, bg="black",
                                       xscrollcommand=h_scroll.set,
                                       yscrollcommand=v_scroll.set)
        
        h_scroll.config(command=self.preview_canvas.xview)
        v_scroll.config(command=self.preview_canvas.yview)
        
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        
        # Bind mouse wheel for zoom
        self.preview_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.preview_canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.preview_canvas.bind("<Button-5>", self.on_mouse_wheel)
        
        # Bind mouse drag for compact pattern offset
        self.preview_canvas.bind("<Button-1>", self.on_canvas_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

    def on_pattern_change(self, event=None):
        """Update parameter controls based on selected pattern type"""
        # Clear existing parameter widgets
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        
        pattern_type = self.var_pattern_type.get()
        
        if pattern_type == "Interstitial":
            self._add_entry(self.params_frame, 0, "Rectangle length (µm):", self.var_rect_length, "µm",
                           callback=self.on_preview)
            self._add_entry(self.params_frame, 1, "Rectangle width (µm):", self.var_rect_width, "µm",
                           callback=self.on_preview)
            self._add_entry(self.params_frame, 2, "Spacing along (µm):", self.var_spacing_along, "µm",
                           callback=self.on_preview)
            self._add_entry(self.params_frame, 3, "Spacing across (µm):", self.var_spacing_across, "µm",
                           callback=self.on_preview)
            self._add_entry(self.params_frame, 4, "Rotation angle (deg):", self.var_angle, "°",
                           callback=self.on_preview)
            self._add_slider(self.params_frame, 5, "Indentation (%):", self.var_indentation, 0.0, 100.0, "%",
                            callback=self.on_preview)
            ttk.Label(self.params_frame, text="  (offset of alternating rows, 0=aligned, 50=half-offset)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        elif pattern_type == "Diffuse":
            self._add_entry(self.params_frame, 0, "Rectangle length (µm):", self.var_rect_length, "µm",
                           callback=self.on_preview)
            self._add_entry(self.params_frame, 1, "Rectangle width (µm):", self.var_rect_width, "µm",
                           callback=self.on_preview)
            self._add_slider(self.params_frame, 2, "Randomness (%):", self.var_randomness, 0.0, 100.0, "%",
                            callback=self.on_preview)
            ttk.Label(self.params_frame, text="  (0=grid, 50=scattered, 100=fully random)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))
            self._add_entry(self.params_frame, 4, "Rotation angle (deg):", self.var_angle, "°",
                           callback=self.on_preview)
        
        elif pattern_type == "Patchy":
            self._add_slider(self.params_frame, 0, "Number of islands:", self.var_num_islands, 1.0, 50.0, "",
                            callback=self.on_preview)
            self._add_slider(self.params_frame, 1, "Island density:", self.var_density, 0.2, 2.0, "",
                            callback=self.on_preview)
            ttk.Label(self.params_frame, text="  (0.2=sparse/large, 1.0=uniform, 2.0=dense/small)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        elif pattern_type == "Compact":
            self._add_slider(self.params_frame, 0, "Irregularity:", self.var_irregularity, 0.0, 1.0, "",
                            callback=self.on_preview)
            ttk.Label(self.params_frame, text="  (0=perfect circle, 1=very irregular)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
            
            # Split scar option
            split_check = ttk.Checkbutton(self.params_frame, text="Split scar for rotor development",
                                         variable=self.var_split_scar,
                                         command=self.on_pattern_change)
            split_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
            
            # Split controls (only show when split is enabled)
            if self.var_split_scar.get():
                self._add_entry(self.params_frame, 3, "Gap between circles (mm):", self.var_split_distance, "mm",
                               callback=self.on_preview)
                ttk.Label(self.params_frame, text="  (space where electrical conduction can develop)", 
                         font=("TkDefaultFont", 8, "italic")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 2))
                
                # Left circle controls
                ttk.Label(self.params_frame, text="Left Circle:", font=("TkDefaultFont", 9, "bold")).grid(
                    row=5, column=0, columnspan=2, sticky="w", pady=(5, 2))
                self._add_entry(self.params_frame, 6, "  Offset X (mm):", self.var_left_offset_x, "mm",
                               callback=self.on_preview)
                self._add_entry(self.params_frame, 7, "  Offset Y (mm):", self.var_left_offset_y, "mm",
                               callback=self.on_preview)
                self._add_entry(self.params_frame, 8, "  Rotation (°):", self.var_split_rotation_left, "°",
                               callback=self.on_preview)
                
                # Right circle controls
                ttk.Label(self.params_frame, text="Right Circle:", font=("TkDefaultFont", 9, "bold")).grid(
                    row=9, column=0, columnspan=2, sticky="w", pady=(5, 2))
                self._add_entry(self.params_frame, 10, "  Offset X (mm):", self.var_right_offset_x, "mm",
                               callback=self.on_preview)
                self._add_entry(self.params_frame, 11, "  Offset Y (mm):", self.var_right_offset_y, "mm",
                               callback=self.on_preview)
                self._add_entry(self.params_frame, 12, "  Rotation (°):", self.var_split_rotation_right, "°",
                               callback=self.on_preview)
                
                ttk.Label(self.params_frame, text="  (or drag each circle on preview to move independently)", 
                         font=("TkDefaultFont", 8, "italic")).grid(row=13, column=0, columnspan=2, sticky="w", pady=(0, 2))
            else:
                # Single circle controls
                self._add_entry(self.params_frame, 3, "Offset X (mm):", self.var_offset_x, "mm",
                               callback=self.on_preview)
                self._add_entry(self.params_frame, 4, "Offset Y (mm):", self.var_offset_y, "mm",
                               callback=self.on_preview)
                ttk.Label(self.params_frame, text="  (or drag the scar on preview to move it)", 
                         font=("TkDefaultFont", 8, "italic")).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        self.on_preview()

    def _add_entry(self, parent, row, label, var, unit, callback=None):
        """Add labeled entry field"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=2)
        
        entry = ttk.Entry(frame, textvariable=var, width=10)
        entry.pack(side="left", padx=(0, 5))
        
        # Bind callback on Enter key
        if callback:
            entry.bind("<Return>", lambda e: callback())
        
        ttk.Label(frame, text=unit, width=6).pack(side="left")
        
        return frame
    
    def _add_slider(self, parent, row, label, var, from_, to, unit, callback=None):
        """Add labeled slider"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=2)
        
        slider = ttk.Scale(frame, from_=from_, to=to, variable=var, orient="horizontal")
        slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        value_label = ttk.Label(frame, text=f"{var.get():.1f}{unit}", width=6)
        value_label.pack(side="left")
        
        def update_label(*args):
            value_label.config(text=f"{var.get():.1f}{unit}")
            if callback:
                self.root.after(100, callback)  # Debounce the callback
        
        var.trace_add("write", update_label)
        
        return frame
    
    def _update_coverage_info(self):
        """Update coverage information display"""
        total_coverage = self.var_coverage.get() / 100.0
        white_border = self.var_white_border.get() / 100.0
        
        # Update total coverage
        self.total_coverage_label.config(text=f"Total coverage: {self.var_coverage.get():.1f}%")
        
        # Calculate inner coverage
        pattern_radius_fraction = 1.0 - white_border
        area_ratio = pattern_radius_fraction ** 2
        if area_ratio > 0:
            inner_coverage = min(99, (total_coverage / area_ratio) * 100)
        else:
            inner_coverage = 0
        self.inner_coverage_label.config(text=f"Inner pattern coverage: {inner_coverage:.1f}%")
        
        # Calculate adjusted rectangle dimensions
        rect_length_mm = self.var_rect_length.get() / 1000.0
        rect_width_mm = self.var_rect_width.get() / 1000.0
        spacing_along_mm = self.var_spacing_along.get() / 1000.0
        spacing_across_mm = self.var_spacing_across.get() / 1000.0
        
        # Calculate coverage from current parameters
        area_per_unit = (rect_length_mm + spacing_along_mm) * (rect_width_mm + spacing_across_mm)
        area_rect = rect_length_mm * rect_width_mm
        actual_coverage = area_rect / area_per_unit if area_per_unit > 0 else 0
        
        # Calculate scale factor needed
        inner_coverage_fraction = inner_coverage / 100.0
        if actual_coverage > 0 and actual_coverage < 0.99:
            scale_factor = math.sqrt(inner_coverage_fraction / actual_coverage)
        else:
            scale_factor = 1.0
        
        adjusted_length_µm = rect_length_mm * scale_factor * 1000.0
        adjusted_width_µm = rect_width_mm * scale_factor * 1000.0
        
        self.actual_rect_length_label.config(
            text=f"Adjusted rect length: {adjusted_length_µm:.1f} µm (scale: {scale_factor:.2f}x)")
        self.actual_rect_width_label.config(
            text=f"Adjusted rect width: {adjusted_width_µm:.1f} µm (scale: {scale_factor:.2f}x)")
    
    def on_preview(self, event=None):
        """Generate preview image and update coverage info"""
        self._update_coverage_info()
        
        self.last_seed = random.randint(0, 10**9)
        params = self._current_params()
        
        self.preview_image_full = render_pattern_image(size_px=800, **params)
        self._update_canvas()

    def _current_params(self):
        """Get current pattern parameters"""
        diameter = MATTEK_SIZES[self.var_mattek_size.get()]
        coverage = self.var_coverage.get() / 100.0
        white_border = self.var_white_border.get() / 100.0
        
        params = {
            "pattern_type": self.var_pattern_type.get(),
            "coverage": coverage,
            "circle_diameter_mm": diameter,
            "white_border_fraction": white_border,
            "rect_length_mm": self.var_rect_length.get() / 1000.0,
            "rect_width_mm": self.var_rect_width.get() / 1000.0,
            "angle_deg": self.var_angle.get(),
        }
        
        if self.var_pattern_type.get() == "Interstitial":
            params["spacing_along_mm"] = self.var_spacing_along.get() / 1000.0
            params["spacing_across_mm"] = self.var_spacing_across.get() / 1000.0
            params["indentation"] = self.var_indentation.get()
        elif self.var_pattern_type.get() == "Diffuse":
            params["randomness"] = self.var_randomness.get() / 100.0
        elif self.var_pattern_type.get() == "Patchy":
            params["num_islands"] = int(self.var_num_islands.get())
            params["density"] = self.var_density.get()
        elif self.var_pattern_type.get() == "Compact":
            params["irregularity"] = self.var_irregularity.get()
            params["offset_x_mm"] = self.var_offset_x.get()
            params["offset_y_mm"] = self.var_offset_y.get()
            params["split_scar"] = self.var_split_scar.get()
            params["split_distance_mm"] = self.var_split_distance.get() if self.var_split_scar.get() else 0.0
            params["left_offset_x_mm"] = self.var_left_offset_x.get() if self.var_split_scar.get() else 0.0
            params["left_offset_y_mm"] = self.var_left_offset_y.get() if self.var_split_scar.get() else 0.0
            params["split_rotation_left"] = self.var_split_rotation_left.get() if self.var_split_scar.get() else 0.0
            params["right_offset_x_mm"] = self.var_right_offset_x.get() if self.var_split_scar.get() else 0.0
            params["right_offset_y_mm"] = self.var_right_offset_y.get() if self.var_split_scar.get() else 0.0
            params["split_rotation_right"] = self.var_split_rotation_right.get() if self.var_split_scar.get() else 0.0
            
        return params
    
    def on_generate(self):
        """Generate PDF file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=os.path.expanduser("~\Desktop")
        )
        
        if file_path:
            params = self._current_params()
            generate_pattern(file_path, **params, seed=self.last_seed)
            messagebox.showinfo("Success", f"Pattern saved to:\n{file_path}")
    
    def zoom_in(self):
        """Increase zoom"""
        self.zoom_level *= 1.2
        self._update_canvas()
    
    def zoom_out(self):
        """Decrease zoom"""
        self.zoom_level /= 1.2
        self._update_canvas()
    
    def zoom_reset(self):
        """Reset zoom to fit canvas"""
        self.zoom_level = 1.0
        self._update_canvas()
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel zoom"""
        if event.num == 5 or event.delta < 0:
            self.zoom_out()
        elif event.num == 4 or event.delta > 0:
            self.zoom_in()
    
    def _update_canvas(self):
        """Update canvas with zoomed image"""
        if self.preview_image_full is None:
            return
        
        img_width, img_height = self.preview_image_full.size
        new_width = int(img_width * self.zoom_level)
        new_height = int(img_height * self.zoom_level)
        
        img_resized = self.preview_image_full.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert PIL image to PhotoImage using ImageTk
        self.photo = ImageTk.PhotoImage(img_resized)
        
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.preview_canvas.config(scrollregion=self.preview_canvas.bbox("all"))
        
        zoom_percent = int(self.zoom_level * 100)
        self.zoom_label.config(text=f"{zoom_percent}%")

    def on_canvas_press(self, event):
        """Handle mouse press on canvas"""
        if self.var_pattern_type.get() == "Compact":
            self.compact_offset_mode = True
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
    
    def on_canvas_drag(self, event):
        """Handle mouse drag on canvas for compact pattern offset"""
        if self.compact_offset_mode and self.var_pattern_type.get() == "Compact":
            # Calculate movement in canvas pixels
            dx_canvas = event.x - self.last_mouse_x
            dy_canvas = event.y - self.last_mouse_y
            
            # Convert canvas pixels to mm
            diameter = MATTEK_SIZES[self.var_mattek_size.get()]
            circle_radius_mm = diameter / 2.0
            pixels_per_mm = 400 / circle_radius_mm
            dx_mm = dx_canvas / (pixels_per_mm * self.zoom_level)
            dy_mm = dy_canvas / (pixels_per_mm * self.zoom_level)
            
            # Determine which circle was clicked (if split mode)
            if self.var_split_scar.get():
                # Get circle centers in canvas pixels
                cx = self.preview_canvas.winfo_width() / 2.0
                cy = self.preview_canvas.winfo_height() / 2.0
                
                # Distance from center in mm
                left_cx_mm = self.var_left_offset_x.get()
                left_cy_mm = self.var_left_offset_y.get()
                right_cx_mm = self.var_right_offset_x.get()
                right_cy_mm = self.var_right_offset_y.get()
                
                # Convert to canvas pixels
                left_cx_px = cx + left_cx_mm * pixels_per_mm * self.zoom_level
                left_cy_px = cy + left_cy_mm * pixels_per_mm * self.zoom_level
                right_cx_px = cx + right_cx_mm * pixels_per_mm * self.zoom_level
                right_cy_px = cy + right_cy_mm * pixels_per_mm * self.zoom_level
                
                # Check which circle is closer to initial click
                dist_to_left = math.sqrt((self.last_mouse_x - left_cx_px) ** 2 + (self.last_mouse_y - left_cy_px) ** 2)
                dist_to_right = math.sqrt((self.last_mouse_x - right_cx_px) ** 2 + (self.last_mouse_y - right_cy_px) ** 2)
                
                if dist_to_left < dist_to_right:
                    # Moving left circle
                    self.var_left_offset_x.set(self.var_left_offset_x.get() + dx_mm)
                    self.var_left_offset_y.set(self.var_left_offset_y.get() + dy_mm)
                else:
                    # Moving right circle
                    self.var_right_offset_x.set(self.var_right_offset_x.get() + dx_mm)
                    self.var_right_offset_y.set(self.var_right_offset_y.get() + dy_mm)
            else:
                # Single circle mode
                self.var_offset_x.set(self.var_offset_x.get() + dx_mm)
                self.var_offset_y.set(self.var_offset_y.get() + dy_mm)
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            
            self.on_preview()
    
    def on_canvas_release(self, event):
        """Handle mouse release on canvas"""
        self.compact_offset_mode = False

# ========== RENDER AND GENERATE FUNCTIONS ==========
def render_pattern_image(size_px, pattern_type, coverage, circle_diameter_mm, white_border_fraction=0.15, seed=None, **kwargs):
    """Render preview image"""
    if seed is not None:
        random.seed(seed)
    
    base = Image.new("L", (size_px, size_px), 0)
    draw_base = ImageDraw.Draw(base)
    cx = cy = size_px / 2.0
    radius_px = size_px * 0.45
    
    # Draw outer white circle
    draw_base.ellipse((cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px), fill=255)
    
    # Calculate pattern region (with white border)
    pattern_radius_px = radius_px * (1.0 - max(0.0, min(0.9, white_border_fraction)))
    
    # Calculate inner coverage needed
    area_ratio = (pattern_radius_px / radius_px) ** 2
    inner_coverage = coverage / area_ratio if area_ratio > 0 else 0
    inner_coverage = min(0.99, inner_coverage)
    
    tissue = Image.new("L", (size_px, size_px), 255)
    draw_t = ImageDraw.Draw(tissue)
    
    if pattern_type == "Interstitial":
        rect_length_mm = kwargs.get("rect_length_mm", 0.5)
        rect_width_mm = kwargs.get("rect_width_mm", 0.2)
        spacing_along_mm = kwargs.get("spacing_along_mm", 0.2)
        spacing_across_mm = kwargs.get("spacing_across_mm", 0.2)
        angle_deg = kwargs.get("angle_deg", 0)
        indentation = kwargs.get("indentation", 0.0)
        
        rect_length_px = (rect_length_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        rect_width_px = (rect_width_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        spacing_along_px = (spacing_along_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        spacing_across_px = (spacing_across_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        
        add_interstitial_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage,
                                rect_length_px, rect_width_px, spacing_along_px, spacing_across_px, angle_deg, indentation)
    
    elif pattern_type == "Diffuse":
        rect_length_mm = kwargs.get("rect_length_mm", 0.5)
        rect_width_mm = kwargs.get("rect_width_mm", 0.2)
        randomness = kwargs.get("randomness", 0.5)
        angle_deg = kwargs.get("angle_deg", 0)
        
        rect_length_px = (rect_length_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        rect_width_px = (rect_width_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        
        # Create diffuse preview (randomized rectangles)
        for _ in range(int((inner_coverage * math.pi * pattern_radius_px ** 2) / (rect_length_px * rect_width_px))):
            angle = random.uniform(0, 2 * math.pi)
            r_factor = random.uniform(0, 1) ** 0.5
            r = pattern_radius_px * r_factor
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            
            rect_angle = random.uniform(0, 180)
            scatter = randomness * rect_length_px
            px += random.uniform(-scatter, scatter)
            py += random.uniform(-scatter, scatter)
            
            # Rotate and draw rectangle
            angle_rad = math.radians(rect_angle)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            
            half_length = rect_length_px / 2.0
            half_width = rect_width_px / 2.0
            
            corners = [
                (-half_length, -half_width),
                (half_length, -half_width),
                (half_length, half_width),
                (-half_length, half_width)
            ]
            
            points = []
            for dx, dy in corners:
                rx = dx * cos_a - dy * sin_a
                ry = dx * sin_a + dy * cos_a
                points.append((px + rx, py + ry))
            
            draw_t.polygon(points, fill=0, outline=0)
    
    elif pattern_type == "Patchy":
        num_islands = kwargs.get("num_islands", 8)
        density = kwargs.get("density", 1.0)
        
        add_patchy_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage,
                          None, num_islands, density)
    
    elif pattern_type == "Compact":
        irregularity = kwargs.get("irregularity", 0.5)
        offset_x_mm = kwargs.get("offset_x_mm", 0.0)
        offset_y_mm = kwargs.get("offset_y_mm", 0.0)
        split_scar = kwargs.get("split_scar", False)
        split_distance_mm = kwargs.get("split_distance_mm", 0.0)
        left_offset_x_mm = kwargs.get("left_offset_x_mm", 0.0)
        left_offset_y_mm = kwargs.get("left_offset_y_mm", 0.0)
        right_offset_x_mm = kwargs.get("right_offset_x_mm", 0.0)
        right_offset_y_mm = kwargs.get("right_offset_y_mm", 0.0)
        split_rotation_left = kwargs.get("split_rotation_left", 0.0)
        split_rotation_right = kwargs.get("split_rotation_right", 0.0)
        
        offset_x_px = (offset_x_mm / circle_diameter_mm) * (2 * pattern_radius_px) if circle_diameter_mm > 0 else 0
        offset_y_px = (offset_y_mm / circle_diameter_mm) * (2 * pattern_radius_px) if circle_diameter_mm > 0 else 0
        left_offset_x_px = (left_offset_x_mm / circle_diameter_mm) * (2 * pattern_radius_px) if circle_diameter_mm > 0 else 0
        left_offset_y_px = (left_offset_y_mm / circle_diameter_mm) * (2 * pattern_radius_px) if circle_diameter_mm > 0 else 0
        right_offset_x_px = (right_offset_x_mm / circle_diameter_mm) * (2 * pattern_radius_px) if circle_diameter_mm > 0 else 0
        right_offset_y_px = (right_offset_y_mm / circle_diameter_mm) * (2 * pattern_radius_px) if circle_diameter_mm > 0 else 0
        
        add_compact_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage,
                           irregularity, offset_x_px, offset_y_px, split_scar, split_distance_mm, 
                           left_offset_x_px, left_offset_y_px, split_rotation_left,
                           right_offset_x_px, right_offset_y_px, split_rotation_right)
    
    # Mask to pattern region
    mask = Image.new("L", (size_px, size_px), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.ellipse((cx - pattern_radius_px, cy - pattern_radius_px, 
                   cx + pattern_radius_px, cy + pattern_radius_px), fill=255)
    base.paste(tissue, (0, 0), mask)
    
    return base.convert("RGB")

def generate_pattern(filename, pattern_type, coverage, circle_diameter_mm, white_border_fraction=0.15, seed=None, **kwargs):
    """Generate PDF pattern"""
    if seed is not None:
        random.seed(seed)
    
    dummy_size = circle_diameter_mm * mm + 4 * mm
    c = canvas.Canvas(filename, pagesize=(dummy_size, dummy_size))
    
    cx, cy = dummy_size / 2.0, dummy_size / 2.0
    radius_pt = circle_diameter_mm * mm / 2.0
    
    # Black background
    c.setFillColor(colors.black)
    c.rect(0, 0, dummy_size, dummy_size, stroke=0, fill=1)
    
    # White circle (tissue region)
    c.setFillColor(colors.white)
    c.circle(cx, cy, radius_pt, stroke=0, fill=1)
    
    # Clip to circle for pattern
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, radius_pt)
    c.clipPath(p, stroke=0, fill=0)
    
    # Calculate pattern region
    pattern_radius_pt = radius_pt * (1.0 - max(0.0, min(0.9, white_border_fraction)))
    
    # Calculate inner coverage
    area_ratio = (pattern_radius_pt / radius_pt) ** 2
    inner_coverage = coverage / area_ratio if area_ratio > 0 else 0
    inner_coverage = min(0.99, inner_coverage)
    
    # Clip to pattern region
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, pattern_radius_pt)
    c.clipPath(p, stroke=0, fill=0)
    
    # Draw pattern
    if pattern_type == "Interstitial":
        rect_length_mm = kwargs.get("rect_length_mm", 0.5)
        rect_width_mm = kwargs.get("rect_width_mm", 0.2)
        spacing_along_mm = kwargs.get("spacing_along_mm", 0.2)
        spacing_across_mm = kwargs.get("spacing_across_mm", 0.2)
        angle_deg = kwargs.get("angle_deg", 0)
        indentation = kwargs.get("indentation", 0.0)
        
        add_interstitial(c, cx, cy, pattern_radius_pt, inner_coverage,
                        rect_length_mm, rect_width_mm, spacing_along_mm, spacing_across_mm, 
                        angle_deg, indentation)
    
    elif pattern_type == "Diffuse":
        rect_length_mm = kwargs.get("rect_length_mm", 0.5)
        rect_width_mm = kwargs.get("rect_width_mm", 0.2)
        randomness = kwargs.get("randomness", 0.5)
        angle_deg = kwargs.get("angle_deg", 0)
        
        rect_length_pt = rect_length_mm * mm
        rect_width_pt = rect_width_mm * mm
        
        c.setFillColor(colors.black)
        
        # Draw randomized rectangles
        num_rects = int((inner_coverage * math.pi * pattern_radius_pt ** 2) / (rect_length_pt * rect_width_pt))
        for _ in range(num_rects):
            angle = random.uniform(0, 2 * math.pi)
            r_factor = random.uniform(0, 1) ** 0.5
            r = pattern_radius_pt * r_factor
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            
            rect_angle = random.uniform(0, 180)
            scatter = randomness * rect_length_pt
            px += random.uniform(-scatter, scatter)
            py += random.uniform(-scatter, scatter)
            
            c.saveState()
            c.translate(px, py)
            c.rotate(rect_angle)
            c.rect(-rect_length_pt / 2.0, -rect_width_pt / 2.0,
                   rect_length_pt, rect_width_pt, stroke=0, fill=1)
            c.restoreState()
    
    elif pattern_type == "Patchy":
        num_islands = kwargs.get("num_islands", 8)
        density = kwargs.get("density", 1.0)
        
        add_patchy(c, cx, cy, pattern_radius_pt, inner_coverage,
                  None, num_islands, density)
    
    elif pattern_type == "Compact":
        irregularity = kwargs.get("irregularity", 0.5)
        offset_x_mm = kwargs.get("offset_x_mm", 0.0)
        offset_y_mm = kwargs.get("offset_y_mm", 0.0)
        split_scar = kwargs.get("split_scar", False)
        split_distance_mm = kwargs.get("split_distance_mm", 0.0)
        left_offset_x_mm = kwargs.get("left_offset_x_mm", 0.0)
        left_offset_y_mm = kwargs.get("left_offset_y_mm", 0.0)
        right_offset_x_mm = kwargs.get("right_offset_x_mm", 0.0)
        right_offset_y_mm = kwargs.get("right_offset_y_mm", 0.0)
        split_rotation_left = kwargs.get("split_rotation_left", 0.0)
        split_rotation_right = kwargs.get("split_rotation_right", 0.0)
        
        add_compact(c, cx, cy, pattern_radius_pt, inner_coverage,
                   irregularity, offset_x_mm, offset_y_mm, split_scar, split_distance_mm,
                   left_offset_x_mm, left_offset_y_mm, split_rotation_left,
                   right_offset_x_mm, right_offset_y_mm, split_rotation_right)
    
    c.restoreState()
    c.restoreState()
    c.showPage()
    c.save()

def main():
    root = tk.Tk()
    app = PatternCreatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()