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
    - Optional indentation for staggered rows
    """
    if coverage <= 0:
        return
    
    rect_length_pt = rect_length_mm * mm
    rect_width_pt = rect_width_mm * mm
    spacing_along_pt = spacing_along_mm * mm
    spacing_across_pt = spacing_across_mm * mm
    
    # Calculate actual coverage based on rectangle and spacing
    # coverage = rect_area / (rect_length + spacing_along) * (rect_width + spacing_across)
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

# ========== DIFFUSE PATTERN (RANDOMIZED RECTANGLES) ==========
def add_diffuse(c, cx, cy, radius_pt, coverage, rect_length_mm, rect_width_mm, 
                randomness=0.5, angle_deg=0):
    """Add diffuse pattern with randomized rectangles"""
    if coverage <= 0:
        return
    
    rect_length_pt = rect_length_mm * mm
    rect_width_pt = rect_width_mm * mm
    
    area_total = math.pi * radius_pt ** 2
    area_single_rect = rect_length_pt * rect_width_pt
    
    n_rectangles = int((coverage * area_total) / area_single_rect)
    
    c.saveState()
    c.translate(cx, cy)
    c.rotate(angle_deg)
    c.translate(-cx, -cy)
    c.setFillColor(colors.black)
    
    for _ in range(n_rectangles):
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** 0.5
        r = radius_pt * r_factor
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
    
    c.restoreState()

def add_diffuse_preview(draw, cx, cy, radius_px, coverage, rect_length_px, rect_width_px,
                        randomness=0.5, angle_deg=0):
    """Preview for diffuse randomized rectangle pattern"""
    if coverage <= 0:
        return
    
    area_total = math.pi * radius_px ** 2
    area_single_rect = rect_length_px * rect_width_px
    
    n_rectangles = int((coverage * area_total) / area_single_rect)
    
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    for _ in range(n_rectangles):
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** 0.5
        r = radius_px * r_factor
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        
        scatter = randomness * rect_length_px
        px += random.uniform(-scatter, scatter)
        py += random.uniform(-scatter, scatter)
        
        rect_angle_deg = random.uniform(0, 180)
        rect_angle_rad = math.radians(rect_angle_deg)
        rect_cos = math.cos(rect_angle_rad)
        rect_sin = math.sin(rect_angle_rad)
        
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
            rx = dx * rect_cos - dy * rect_sin
            ry = dx * rect_sin + dy * rect_cos
            
            x = cx + (px - cx + rx) * cos_a - (py - cy + ry) * sin_a
            y = cy + (px - cx + rx) * sin_a + (py - cy + ry) * cos_a
            
            points.append((x, y))
        
        draw.polygon(points, fill=0, outline=0)

# ========== PATCHY PATTERN (IRREGULAR ISLANDS) ==========
def add_patchy(c, cx, cy, radius_pt, coverage, island_size_mm, num_islands, density=1.0):
    """Add patchy pattern with irregular island shapes"""
    if coverage <= 0 or num_islands <= 0:
        return
    
    c.setFillColor(colors.black)
    
    area_total = math.pi * radius_pt ** 2
    area_per_island = (coverage * area_total) / num_islands
    base_radius_pt = math.sqrt(area_per_island / math.pi)
    
    for _ in range(int(num_islands)):
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** (1.0 / density) if density > 0 else random.uniform(0, 1)
        r = radius_pt * r_factor
        island_cx = cx + r * math.cos(angle)
        island_cy = cy + r * math.sin(angle)
        
        size_variation = random.uniform(0.6, 1.4) * density
        island_radius_pt = base_radius_pt * size_variation
        
        n_points = 16
        points = []
        
        num_harmonics = 4
        amplitudes = [random.uniform(0.2, 0.5) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            a = (2 * math.pi * i) / n_points
            
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * a + phases[h])
            r_variation = r_variation / num_harmonics
            
            r_local = island_radius_pt * (1.0 + 0.5 * r_variation)
            x_local = r_local * math.cos(a)
            y_local = r_local * math.sin(a)
            
            points.append((island_cx + x_local, island_cy + y_local))
        
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
    
    area_total = math.pi * radius_px ** 2
    area_per_island = (coverage * area_total) / num_islands
    base_radius_px = math.sqrt(area_per_island / math.pi)
    
    for _ in range(int(num_islands)):
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** (1.0 / density) if density > 0 else random.uniform(0, 1)
        r = radius_px * r_factor
        island_cx = cx + r * math.cos(angle)
        island_cy = cy + r * math.sin(angle)
        
        size_variation = random.uniform(0.6, 1.4) * density
        island_radius_px = base_radius_px * size_variation
        
        n_points = 16
        points = []
        
        num_harmonics = 4
        amplitudes = [random.uniform(0.2, 0.5) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            a = (2 * math.pi * i) / n_points
            
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * a + phases[h])
            r_variation = r_variation / num_harmonics
            
            r_local = island_radius_px * (1.0 + 0.5 * r_variation)
            x_local = r_local * math.cos(a)
            y_local = r_local * math.sin(a)
            
            points.append((island_cx + x_local, island_cy + y_local))
        
        draw.polygon(points, fill=0, outline=0)

    def generate_pattern(self):
        """Generate pattern and display in canvas"""
        self.update_preview()
        self.status.set("Pattern generated")
    
    def save_pattern(self):
        """Save pattern to file"""
        pattern_type = self.var_pattern_type.get()
        coverage = self.var_coverage.get() / 100.0
        circle_diameter = self.var_circle_diameter.get()
        white_border = self.var_white_border.get() / 100.0
        
        filename = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                 filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not filename:
            return
        
        generate_pattern(filename, pattern_type, coverage, circle_diameter, white_border,
                        rect_length_mm=self.var_rect_length.get(),
                        rect_width_mm=self.var_rect_width.get(),
                        spacing_along_mm=self.var_spacing_along.get(),
                        spacing_across_mm=self.var_spacing_across.get(),
                        angle_deg=self.var_angle.get(),
                        indentation=self.var_indentation.get(),
                        randomness=self.var_randomness.get() / 100.0,
                        num_islands=int(self.var_num_islands.get()),
                        island_size_mm=self.var_island_size.get() / 1000.0,
                        density=self.var_density.get())
        
        self.status.set(f"Pattern saved: {filename}")

def generate_pdf_pattern(filename, pattern_type, coverage, circle_diameter_mm, white_border_fraction=0.15, seed=None, **kwargs):
    """Generate PDF pattern"""
    if seed is not None:
        random.seed(seed)
    
    dummy_size = circle_diameter_mm * mm + 4 * mm
    c = canvas.Canvas(filename, pagesize=(dummy_size, dummy_size))
    
    cx, cy = dummy_size / 2.0, dummy_size / 2.0
    radius_pt = circle_diameter_mm * mm / 2.0
    
    c.setFillColor(colors.white)
    c.rect(0, 0, dummy_size, dummy_size, stroke=0, fill=1)
    c.circle(cx, cy, radius_pt, stroke=0, fill=1)
    
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, radius_pt)
    c.clipPath(p, stroke=0, fill=0)
    
    pattern_radius_pt = radius_pt * (1.0 - max(0.0, min(0.9, white_border_fraction)))
    
    area_ratio = (pattern_radius_pt / radius_pt) ** 2
    inner_coverage = coverage / area_ratio if area_ratio > 0 else 0
    inner_coverage = min(0.99, inner_coverage)
    
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, pattern_radius_pt)
    c.clipPath(p, stroke=0, fill=0)
    
    if pattern_type == "Interstitial":
        rect_length_mm = kwargs.get("rect_length_mm", 0.5)
        rect_width_mm = kwargs.get("rect_width_mm", 0.2)
        spacing_along_mm = kwargs.get("spacing_along_mm", 0.2)
        spacing_across_mm = kwargs.get("spacing_across_mm", 0.2)
        angle_deg = kwargs.get("angle_deg", 0)
        indentation = kwargs.get("indentation", 0.0)
        
        add_interstitial(c, cx, cy, pattern_radius_pt, inner_coverage,
                        rect_length_mm, rect_width_mm, spacing_along_mm, spacing_across_mm, angle_deg, indentation)
    
    elif pattern_type == "Diffuse":
        rect_length_mm = kwargs.get("rect_length_mm", 0.5)
        rect_width_mm = kwargs.get("rect_width_mm", 0.2)
        randomness = kwargs.get("randomness", 0.5)
        angle_deg = kwargs.get("angle_deg", 0)
        
        add_diffuse(c, cx, cy, pattern_radius_pt, inner_coverage,
                   rect_length_mm, rect_width_mm, randomness, angle_deg)
    
    elif pattern_type == "Patchy":
        num_islands = kwargs.get("num_islands", 5)
        density = kwargs.get("density", 1.0)
        
        add_patchy(c, cx, cy, pattern_radius_pt, inner_coverage,
                  None, num_islands, density)
    
    c.restoreState()
    c.restoreState()
    c.showPage()
    c.save()

def render_pattern_image(size_px, pattern_type, coverage, circle_diameter_mm, white_border_fraction=0.15, **kwargs):
    """Render preview image"""
    base = Image.new("L", (size_px, size_px), 0)
    draw_base = ImageDraw.Draw(base)
    cx = cy = size_px / 2.0
    radius_px = size_px * 0.45
    
    draw_base.ellipse((cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px), fill=255)
    
    pattern_radius_px = radius_px * (1.0 - max(0.0, min(0.9, white_border_fraction)))
    
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
        
        add_diffuse_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage,
                           rect_length_px, rect_width_px, randomness, angle_deg)
    
    elif pattern_type == "Patchy":
        num_islands = kwargs.get("num_islands", 5)
        density = kwargs.get("density", 1.0)
        
        add_patchy_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage,
                          None, num_islands, density)
    
    mask = Image.new("L", (size_px, size_px), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.ellipse((cx - pattern_radius_px, cy - pattern_radius_px, 
                   cx + pattern_radius_px, cy + pattern_radius_px), fill=255)
    base.paste(tissue, (0, 0), mask)
    
    return base.convert("RGB")

# ========== GUI CLASS ==========
class PatternDesignerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pattern Designer - Fibrosis Patterns")
        self.root.geometry("1000x700")
        
        self.var_pattern_type = tk.StringVar(value="Interstitial")
        self.var_coverage = tk.DoubleVar(value=20.0)
        self.var_circle_diameter = tk.DoubleVar(value=10.0)
        self.var_white_border = tk.DoubleVar(value=15.0)
        
        self.var_rect_length = tk.DoubleVar(value=500.0)
        self.var_rect_width = tk.DoubleVar(value=200.0)
        self.var_spacing_along = tk.DoubleVar(value=200.0)
        self.var_spacing_across = tk.DoubleVar(value=200.0)
        self.var_angle = tk.DoubleVar(value=0.0)
        self.var_indentation = tk.DoubleVar(value=0.0)
        
        self.var_randomness = tk.DoubleVar(value=50.0)
        
        self.var_num_islands = tk.DoubleVar(value=8.0)
        self.var_island_size = tk.DoubleVar(value=800.0)
        self.var_density = tk.DoubleVar(value=1.0)
        
        self.status = tk.StringVar(value="Ready")
        self.last_seed = None
        
        self._build_widgets()
        self.update_preview()
    
    def _build_widgets(self):
        """Build GUI widgets"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)
        
        ttk.Label(left_frame, text="Pattern Type:").grid(row=0, column=0, sticky="w", pady=5)
        pattern_menu = ttk.Combobox(left_frame, textvariable=self.var_pattern_type,
                                    values=["Interstitial", "Diffuse", "Patchy"],
                                    state="readonly", width=20)
        pattern_menu.grid(row=0, column=1, sticky="ew", pady=5)
        pattern_menu.bind("<<ComboboxSelected>>", lambda e: self.update_pattern_type())
        
        ttk.Label(left_frame, text="Coverage (%):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Scale(left_frame, from_=0, to=95, variable=self.var_coverage, orient="horizontal",
                 command=lambda x: self.update_preview()).grid(row=1, column=1, sticky="ew", pady=5)
        
        ttk.Label(left_frame, text="Circle diameter (mm):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(left_frame, textvariable=self.var_circle_diameter).grid(row=2, column=1, sticky="ew", pady=5)
        
        ttk.Label(left_frame, text="White border (%):").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Scale(left_frame, from_=0, to=40, variable=self.var_white_border, orient="horizontal",
                 command=lambda x: self.update_preview()).grid(row=3, column=1, sticky="ew", pady=5)
        
        self.params_frame = ttk.LabelFrame(left_frame, text="Pattern Parameters", padding=5)
        self.params_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        
        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Button(btn_frame, text="Update Preview", command=self.update_preview).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Save as PDF", command=self.save_pattern).pack(fill="x", pady=2)
        
        ttk.Label(left_frame, textvariable=self.status, relief="sunken").grid(row=6, column=0, columnspan=2, sticky="ew", pady=5)
        
        self.canvas = tk.Canvas(right_frame, width=400, height=400, bg="white")
        self.canvas.pack(fill="both", expand=True)
        
        self.update_pattern_type()
    
    def update_pattern_type(self):
        """Update UI for selected pattern type"""
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        
        pattern_type = self.var_pattern_type.get()
        
        if pattern_type == "Interstitial":
            ttk.Label(self.params_frame, text="Rect length (µm):").grid(row=0, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_rect_length).grid(row=0, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Rect width (µm):").grid(row=1, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_rect_width).grid(row=1, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Spacing along (µm):").grid(row=2, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_spacing_along).grid(row=2, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Spacing across (µm):").grid(row=3, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_spacing_across).grid(row=3, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Rotation (°):").grid(row=4, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_angle).grid(row=4, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Indentation (%):").grid(row=5, column=0, sticky="w", pady=2)
            ttk.Scale(self.params_frame, from_=0, to=100, variable=self.var_indentation, orient="horizontal",
                     command=lambda x: self.update_preview()).grid(row=5, column=1, sticky="ew", pady=2)
        
        elif pattern_type == "Diffuse":
            ttk.Label(self.params_frame, text="Rect length (µm):").grid(row=0, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_rect_length).grid(row=0, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Rect width (µm):").grid(row=1, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_rect_width).grid(row=1, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Randomness (%):").grid(row=2, column=0, sticky="w", pady=2)
            ttk.Scale(self.params_frame, from_=0, to=100, variable=self.var_randomness, orient="horizontal",
                     command=lambda x: self.update_preview()).grid(row=2, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Rotation (°):").grid(row=3, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_angle).grid(row=3, column=1, sticky="ew", pady=2)
        
        elif pattern_type == "Patchy":
            ttk.Label(self.params_frame, text="Num islands:").grid(row=0, column=0, sticky="w", pady=2)
            ttk.Scale(self.params_frame, from_=1, to=50, variable=self.var_num_islands, orient="horizontal",
                     command=lambda x: self.update_preview()).grid(row=0, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Island size (µm):").grid(row=1, column=0, sticky="w", pady=2)
            ttk.Entry(self.params_frame, textvariable=self.var_island_size).grid(row=1, column=1, sticky="ew", pady=2)
            
            ttk.Label(self.params_frame, text="Density:").grid(row=2, column=0, sticky="w", pady=2)
            ttk.Scale(self.params_frame, from_=0.2, to=2.0, variable=self.var_density, orient="horizontal",
                     command=lambda x: self.update_preview()).grid(row=2, column=1, sticky="ew", pady=2)
        
        self.update_preview()
    
    def update_preview(self):
        """Update preview image"""
        self.last_seed = random.randint(0, 10**9)
        random.seed(self.last_seed)
        
        pattern_type = self.var_pattern_type.get()
        coverage = self.var_coverage.get() / 100.0
        circle_diameter = self.var_circle_diameter.get()
        white_border = self.var_white_border.get() / 100.0
        
        kwargs = {
            "rect_length_mm": self.var_rect_length.get() / 1000.0,
            "rect_width_mm": self.var_rect_width.get() / 1000.0,
            "spacing_along_mm": self.var_spacing_along.get() / 1000.0,
            "spacing_across_mm": self.var_spacing_across.get() / 1000.0,
            "angle_deg": self.var_angle.get(),
            "indentation": self.var_indentation.get(),
            "randomness": self.var_randomness.get() / 100.0,
            "num_islands": int(self.var_num_islands.get()),
            "island_size_mm": self.var_island_size.get() / 1000.0,
            "density": self.var_density.get(),
        }
        
        img = render_pattern_image(400, pattern_type, coverage, circle_diameter, white_border, **kwargs)
        
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(200, 200, image=self.photo)
        self.status.set("Preview updated")
    
    def save_pattern(self):
        """Save pattern to PDF"""
        filename = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                 filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not filename:
            return
        
        pattern_type = self.var_pattern_type.get()
        coverage = self.var_coverage.get() / 100.0
        circle_diameter = self.var_circle_diameter.get()
        white_border = self.var_white_border.get() / 100.0
        
        kwargs = {
            "rect_length_mm": self.var_rect_length.get() / 1000.0,
            "rect_width_mm": self.var_rect_width.get() / 1000.0,
            "spacing_along_mm": self.var_spacing_along.get() / 1000.0,
            "spacing_across_mm": self.var_spacing_across.get() / 1000.0,
            "angle_deg": self.var_angle.get(),
            "indentation": self.var_indentation.get(),
            "randomness": self.var_randomness.get() / 100.0,
            "num_islands": int(self.var_num_islands.get()),
            "island_size_mm": self.var_island_size.get() / 1000.0,
            "density": self.var_density.get(),
        }
        
        generate_pdf_pattern(filename, pattern_type, coverage, circle_diameter, white_border,
                            seed=self.last_seed, **kwargs)
        self.status.set(f"Saved: {filename}")

def main():
    root = tk.Tk()
    app = PatternDesignerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
