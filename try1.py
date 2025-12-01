import math
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from PIL import Image, ImageDraw, ImageTk

# Common MatTek well diameters (mm)
MATTEK_SIZES = {
    "35mm dish (20mm well)": 20.0,
    "35mm dish (14mm well)": 14.0,
    "35mm dish (10mm well)": 10.0,
    "50mm dish (30mm well)": 30.0,
}

def draw_circle_background(c, diameter_mm):
    """Draw black background with white circle"""
    radius_pt = (diameter_mm / 2.0) * mm
    page_size = diameter_mm * mm + 4 * mm
    cx = cy = page_size / 2.0
    c.setFillColor(colors.black)
    c.rect(0, 0, page_size, page_size, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.circle(cx, cy, radius_pt, stroke=0, fill=1)
    return page_size, cx, cy, radius_pt

def clip_to_circle(c, cx, cy, radius_pt):
    """Clip drawing to circular region"""
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, radius_pt)
    c.clipPath(p, stroke=0, fill=0)

def end_clip(c):
    """End clipping"""
    c.restoreState()

# ========== INTERSTITIAL PATTERN ==========
def add_interstitial(c, cx, cy, radius_pt, coverage, stripe_width_mm, angle_deg=0):
    """Add parallel stripes (interstitial fibrosis) - uniform spacing, variable stripe width"""
    if coverage <= 0:
        return
    
    # Fixed spacing based on stripe width
    spacing_pt = stripe_width_mm * mm
    
    # Calculate stripe width based on coverage
    # coverage = stripe_width / (stripe_width + spacing)
    # stripe_width = coverage * spacing / (1 - coverage)
    if coverage >= 0.99:
        actual_stripe_width_pt = spacing_pt * 99  # Very wide stripes for near 100%
    else:
        actual_stripe_width_pt = spacing_pt * coverage / (1.0 - coverage)
    
    period = actual_stripe_width_pt + spacing_pt  # Distance between stripe starts
    
    # Calculate how many stripes we need - use larger diagonal for rotation
    diag = radius_pt * 3  # Increased to cover all rotations
    num_stripes = int(math.ceil(diag * 2 / period)) + 6  # More stripes
    
    # Center the stripes
    total_width = num_stripes * period
    x_start = cx - total_width / 2.0
    
    c.saveState()
    c.translate(cx, cy)
    c.rotate(angle_deg)
    c.translate(-cx, -cy)
    c.setFillColor(colors.black)
    
    # Draw stripes - make them much taller
    for i in range(num_stripes):
        x = x_start + i * period
        c.rect(x, cy - diag * 1.5, actual_stripe_width_pt, diag * 3, stroke=0, fill=1)
    
    c.restoreState()

def add_interstitial_preview(draw, cx, cy, radius_px, coverage, spacing_px, angle_deg):
    """Preview for interstitial pattern - uniform spacing, variable stripe width"""
    if coverage <= 0:
        return
    
    spacing_px = max(1.0, spacing_px)
    
    # Calculate stripe width based on coverage
    # More coverage = wider black stripes
    if coverage >= 0.99:
        actual_stripe_width_px = spacing_px * 99
    else:
        actual_stripe_width_px = spacing_px * coverage / (1.0 - coverage)
    
    actual_stripe_width_px = max(1.0, actual_stripe_width_px)
    period = actual_stripe_width_px + spacing_px
    
    # Calculate how many stripes we need - use larger diagonal for rotation
    diag = radius_px * 3  # Increased to cover all rotations
    num_stripes = int(math.ceil(diag * 2 / period)) + 6  # More stripes for safety
    
    # Center the stripes
    total_width = num_stripes * period
    x_start = -total_width / 2.0
    
    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    
    # Draw BLACK stripes - make them much longer to cover rotation
    for i in range(num_stripes):
        x = x_start + i * period
        xr0, xr1 = x, x + actual_stripe_width_px
        y_low, y_high = -diag * 1.5, diag * 1.5  # Extended height
        corners_r = [(xr0, y_low), (xr1, y_low), (xr1, y_high), (xr0, y_high)]
        pts = [(cx + xr * cos_a - yr * sin_a, cy + xr * sin_a + yr * cos_a) for xr, yr in corners_r]
        draw.polygon(pts, fill=0, outline=0)  # BLACK stripes on white background

# ========== DIFFUSE PATTERN ==========
def add_diffuse(c, cx, cy, radius_pt, coverage, spot_size_mm, spacing_mm):
    """Add randomly distributed spots (diffuse fibrosis)
    
    spots are randomly placed with:
    - Fixed spot size (diameter)
    - Average spacing between spots
    - Coverage determines number of spots
    """
    if coverage <= 0:
        return
    
    spot_radius_pt = (spot_size_mm / 2.0) * mm
    spacing_pt = spacing_mm * mm
    
    # Calculate number of spots based on spacing
    # Treat spacing as the average distance between spot centers
    # Area per spot ≈ spacing²
    area_total = math.pi * radius_pt ** 2
    area_per_spot = spacing_pt ** 2
    
    # Number of spots needed to fill the area with given spacing
    n_spots_for_spacing = int(area_total / area_per_spot)
    
    # Adjust based on coverage:
    # coverage determines what fraction of those spots are actually black
    # More spots needed if spots are small relative to spacing
    area_single_spot = math.pi * spot_radius_pt ** 2
    spot_fill_ratio = area_single_spot / area_per_spot
    
    # n_spots such that: n_spots * spot_area ≈ coverage * total_area
    n_spots = int((coverage * area_total) / area_single_spot)
    
    c.setFillColor(colors.black)
    for _ in range(n_spots):
        angle = random.uniform(0, 2 * math.pi)
        r = radius_pt * math.sqrt(random.uniform(0, 1))
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        c.circle(x, y, spot_radius_pt, stroke=0, fill=1)

def add_diffuse_preview(draw, cx, cy, radius_px, coverage, spot_size_px, spacing_px):
    """Preview for diffuse pattern"""
    if coverage <= 0:
        return
    
    spot_radius_px = max(1.0, spot_size_px / 2.0)
    spacing_px = max(1.0, spacing_px)
    
    area_total = math.pi * radius_px ** 2
    area_single_spot = math.pi * spot_radius_px ** 2
    
    # Calculate number of spots to achieve coverage
    n_spots = int((coverage * area_total) / area_single_spot)
    
    for _ in range(n_spots):
        angle = random.uniform(0, 2 * math.pi)
        r = radius_px * math.sqrt(random.uniform(0, 1))
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        draw.ellipse((x - spot_radius_px, y - spot_radius_px,
                     x + spot_radius_px, y + spot_radius_px), fill=0)

# ========== PATCHY PATTERN ==========
def add_patchy(c, cx, cy, radius_pt, coverage, patch_size_mm, dispersion):
    """Add scattered short stripe segments (patchy fibrosis) causing zig-zag conduction
    
    Creates rectangular stripe segments scattered throughout:
    - Short rectangles at various angles
    - Staggered/offset positions
    - Variable sizes creating irregular pattern
    """
    if coverage <= 0:
        return
    
    # Base rectangle dimensions
    base_length_pt = patch_size_mm * mm
    base_width_pt = patch_size_mm * mm * 0.3  # Rectangles are ~3:1 ratio
    
    area_total = math.pi * radius_pt ** 2
    area_single_rect = base_length_pt * base_width_pt
    
    # Calculate number of rectangles needed for coverage
    n_rectangles = int((coverage * area_total) / area_single_rect)
    
    c.setFillColor(colors.black)
    
    for _ in range(n_rectangles):
        # Random position within circle
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** (1.0 / dispersion)
        r = radius_pt * r_factor
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        
        # Variable size (some larger, some smaller)
        size_factor = random.uniform(0.5, 1.5)
        rect_length = base_length_pt * size_factor
        rect_width = base_width_pt * size_factor
        
        # Random rotation for each rectangle
        rotation_angle = random.uniform(0, 180)  # degrees
        
        # Create rectangle centered at origin
        half_length = rect_length / 2.0
        half_width = rect_width / 2.0
        
        # Four corners of rectangle
        corners = [
            (-half_length, -half_width),
            (half_length, -half_width),
            (half_length, half_width),
            (-half_length, half_width)
        ]
        
        # Rotate and translate corners
        angle_rad = math.radians(rotation_angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        points = []
        for x, y in corners:
            # Rotate
            x_rot = x * cos_a - y * sin_a
            y_rot = x * sin_a + y * cos_a
            # Translate to position
            points.append((px + x_rot, py + y_rot))
        
        # Draw filled rectangle
        p = c.beginPath()
        p.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            p.lineTo(x, y)
        p.close()
        c.drawPath(p, stroke=0, fill=1)

def add_patchy_preview(draw, cx, cy, radius_px, coverage, patch_size_px, dispersion):
    """Preview for patchy pattern"""
    if coverage <= 0:
        return
    
    # Base rectangle dimensions
    base_length_px = patch_size_px
    base_width_px = patch_size_px * 0.3
    
    area_total = math.pi * radius_px ** 2
    area_single_rect = base_length_px * base_width_px
    
    # Calculate number of rectangles
    n_rectangles = int((coverage * area_total) / area_single_rect)
    
    for _ in range(n_rectangles):
        # Random position
        angle = random.uniform(0, 2 * math.pi)
        r_factor = random.uniform(0, 1) ** (1.0 / dispersion)
        r = radius_px * r_factor
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        
        # Variable size
        size_factor = random.uniform(0.5, 1.5)
        rect_length = base_length_px * size_factor
        rect_width = base_width_px * size_factor
        
        # Random rotation
        rotation_angle = random.uniform(0, 180)
        
        # Create rectangle
        half_length = rect_length / 2.0
        half_width = rect_width / 2.0
        
        corners = [
            (-half_length, -half_width),
            (half_length, -half_width),
            (half_length, half_width),
            (-half_length, half_width)
        ]
        
        # Rotate and translate
        angle_rad = math.radians(rotation_angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        points = []
        for x, y in corners:
            x_rot = x * cos_a - y * sin_a
            y_rot = x * sin_a + y * cos_a
            points.append((px + x_rot, py + y_rot))
        
        # Draw filled rectangle
        draw.polygon(points, fill=0, outline=0)

# ========== COMPACT PATTERN ==========
def add_compact(c, cx, cy, radius_pt, coverage, border_width_mm, irregularity, offset_x_mm, offset_y_mm):
    """Add solid central region with irregular shape (compact fibrosis)"""
    if coverage <= 0:
        return
    
    # Calculate base radius for coverage
    scar_radius_pt = radius_pt * math.sqrt(coverage)
    
    # Apply offset
    offset_x_pt = offset_x_mm * mm
    offset_y_pt = offset_y_mm * mm
    scar_cx = cx + offset_x_pt
    scar_cy = cy + offset_y_pt
    
    c.setFillColor(colors.black)
    
    if irregularity <= 0.01:
        # Perfect circle
        c.circle(scar_cx, scar_cy, scar_radius_pt, stroke=0, fill=1)
    else:
        # Irregular blob using Perlin-noise-like smooth deformation
        n_points = 64  # More points for smoother shape
        points = []
        
        # Generate smooth random variations using sum of sinusoids
        num_harmonics = 5
        amplitudes = [random.uniform(0.5, 1.0) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            angle = (2 * math.pi * i) / n_points
            
            # Sum of sinusoids for smooth variation
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * angle + phases[h])
            
            # Normalize and scale by irregularity
            r_variation = r_variation / num_harmonics  # Range: -1 to 1
            r_factor = 1.0 + irregularity * r_variation
            
            r = scar_radius_pt * r_factor
            x = scar_cx + r * math.cos(angle)
            y = scar_cy + r * math.sin(angle)
            points.append((x, y))
        
        # Draw filled polygon (no gaps)
        p = c.beginPath()
        p.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            p.lineTo(x, y)
        p.close()
        c.drawPath(p, stroke=0, fill=1)

def add_compact_preview(draw, cx, cy, radius_px, coverage, border_width_px, irregularity, offset_x_px, offset_y_px):
    """Preview for compact pattern"""
    if coverage <= 0:
        return
    
    scar_radius_px = radius_px * math.sqrt(coverage)
    
    # Apply offset
    scar_cx = cx + offset_x_px
    scar_cy = cy + offset_y_px
    
    if irregularity <= 0.01:
        # Perfect circle
        draw.ellipse((scar_cx - scar_radius_px, scar_cy - scar_radius_px,
                     scar_cx + scar_radius_px, scar_cy + scar_radius_px), fill=0)
    else:
        # Irregular blob using smooth deformation
        n_points = 64  # More points for smoother shape
        points = []
        
        # Generate smooth random variations using sum of sinusoids
        num_harmonics = 5
        amplitudes = [random.uniform(0.5, 1.0) for _ in range(num_harmonics)]
        phases = [random.uniform(0, 2 * math.pi) for _ in range(num_harmonics)]
        
        for i in range(n_points):
            angle = (2 * math.pi * i) / n_points
            
            # Sum of sinusoids for smooth variation
            r_variation = 0
            for h in range(num_harmonics):
                freq = h + 1
                r_variation += amplitudes[h] * math.sin(freq * angle + phases[h])
            
            # Normalize and scale by irregularity
            r_variation = r_variation / num_harmonics  # Range: -1 to 1
            r_factor = 1.0 + irregularity * r_variation
            
            r = scar_radius_px * r_factor
            x = scar_cx + r * math.cos(angle)
            y = scar_cy + r * math.sin(angle)
            points.append((x, y))
        
        # Draw filled polygon (completely solid, no gaps)
        draw.polygon(points, fill=0, outline=0)

# ========== MAIN GENERATION FUNCTIONS ==========
def render_pattern_image(size_px, pattern_type, coverage, circle_diameter_mm, white_border_fraction=0.15, **kwargs):
    """Render preview image with white border for electrical propagation"""
    base = Image.new("L", (size_px, size_px), 0)
    draw_base = ImageDraw.Draw(base)
    cx = cy = size_px / 2.0
    radius_px = size_px * 0.45
    
    # Draw outer white circle
    draw_base.ellipse((cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px), fill=255)
    
    # Calculate pattern region (with white border)
    pattern_radius_px = radius_px * (1.0 - max(0.0, min(0.9, white_border_fraction)))
    
    # Calculate inner coverage needed to achieve desired total coverage
    area_ratio = (pattern_radius_px / radius_px) ** 2
    inner_coverage = coverage / area_ratio if area_ratio > 0 else 0
    inner_coverage = min(0.99, inner_coverage)
    
    tissue = Image.new("L", (size_px, size_px), 255)
    draw_t = ImageDraw.Draw(tissue)
    
    if pattern_type == "Interstitial":
        spacing_mm = kwargs.get("stripe_width_mm", 0.02)
        angle_deg = kwargs.get("angle_deg", 0)
        spacing_px = (spacing_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        add_interstitial_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage, spacing_px, angle_deg)
    
    elif pattern_type == "Diffuse":
        spot_size_mm = kwargs.get("spot_size_mm", 0.05)
        spacing_mm = kwargs.get("spacing_mm", 0.1)
        spot_size_px = (spot_size_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        spacing_px = (spacing_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        add_diffuse_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage, spot_size_px, spacing_px)
    
    elif pattern_type == "Patchy":
        patch_size_mm = kwargs.get("patch_size_mm", 0.5)
        dispersion = kwargs.get("dispersion", 1.0)
        patch_size_px = (patch_size_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        add_patchy_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage, patch_size_px, dispersion)
    
    elif pattern_type == "Compact":
        border_width_mm = kwargs.get("border_width_mm", 0.1)
        irregularity = kwargs.get("irregularity", 0.0)
        offset_x_mm = kwargs.get("offset_x_mm", 0.0)
        offset_y_mm = kwargs.get("offset_y_mm", 0.0)
        border_width_px = (border_width_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        offset_x_px = (offset_x_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        offset_y_px = (offset_y_mm / circle_diameter_mm) * (2 * pattern_radius_px)
        add_compact_preview(draw_t, cx, cy, pattern_radius_px, inner_coverage, border_width_px, 
                           irregularity, offset_x_px, offset_y_px)
    
    # Mask to pattern region
    mask = Image.new("L", (size_px, size_px), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.ellipse((cx - pattern_radius_px, cy - pattern_radius_px, 
                   cx + pattern_radius_px, cy + pattern_radius_px), fill=255)
    base.paste(tissue, (0, 0), mask)
    
    return base.convert("RGB")

def generate_pattern(filename, pattern_type, coverage, circle_diameter_mm, white_border_fraction=0.15, seed=None, **kwargs):
    """Generate PDF pattern with white border for electrical propagation"""
    if seed is not None:
        random.seed(seed)
    
    dummy_size = circle_diameter_mm * mm + 4 * mm
    c = canvas.Canvas(filename, pagesize=(dummy_size, dummy_size))
    page_size, cx, cy, radius_pt = draw_circle_background(c, circle_diameter_mm)
    clip_to_circle(c, cx, cy, radius_pt)
    
    # Calculate pattern region (with white border)
    pattern_radius_pt = radius_pt * (1.0 - max(0.0, min(0.9, white_border_fraction)))
    
    # Calculate inner coverage needed to achieve desired total coverage
    area_ratio = (pattern_radius_pt / radius_pt) ** 2
    inner_coverage = coverage / area_ratio if area_ratio > 0 else 0
    inner_coverage = min(0.99, inner_coverage)
    
    # Clip to pattern region
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, pattern_radius_pt)
    c.clipPath(p, stroke=0, fill=0)
    
    if pattern_type == "Interstitial":
        spacing_mm = kwargs.get("stripe_width_mm", 0.02)
        angle_deg = kwargs.get("angle_deg", 0)
        add_interstitial(c, cx, cy, pattern_radius_pt, inner_coverage, spacing_mm, angle_deg)
    
    elif pattern_type == "Diffuse":
        spot_size_mm = kwargs.get("spot_size_mm", 0.05)
        spacing_mm = kwargs.get("spacing_mm", 0.1)
        add_diffuse(c, cx, cy, pattern_radius_pt, inner_coverage, spot_size_mm, spacing_mm)
    
    elif pattern_type == "Patchy":
        patch_size_mm = kwargs.get("patch_size_mm", 0.5)
        dispersion = kwargs.get("dispersion", 1.0)
        add_patchy(c, cx, cy, pattern_radius_pt, inner_coverage, patch_size_mm, dispersion)
    
    elif pattern_type == "Compact":
        border_width_mm = kwargs.get("border_width_mm", 0.1)
        irregularity = kwargs.get("irregularity", 0.0)
        offset_x_mm = kwargs.get("offset_x_mm", 0.0)
        offset_y_mm = kwargs.get("offset_y_mm", 0.0)
        add_compact(c, cx, cy, pattern_radius_pt, inner_coverage, border_width_mm, 
                   irregularity, offset_x_mm, offset_y_mm)
    
    c.restoreState()
    end_clip(c)
    c.showPage()
    c.save()

# ========== GUI ==========
class FibrosisPatternGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PRIMO Myocardial Fibrosis Pattern Generator")
        self.preview_size = 400
        self.preview_image_tk = None
        self.preview_image_full = None  # Store full resolution image
        self.last_seed = None
        self.zoom_level = 1.0
        self.zoom_levels = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
        self.zoom_index = 2  # Start at 1.0
        self._build_widgets()
    
    def _build_widgets(self):
        # Variables
        self.var_pattern_type = tk.StringVar(value="Interstitial")
        self.var_mattek_size = tk.StringVar(value="35mm dish (10mm well)")
        self.var_coverage = tk.DoubleVar(value=20.0)
        self.var_white_border = tk.DoubleVar(value=15.0)  # White corridor for electrical propagation
        
        # Interstitial - Updated defaults
        self.var_stripe_width = tk.DoubleVar(value=50.0)  # 50 µm spacing
        self.var_stripe_angle = tk.DoubleVar(value=0.0)
        
        # Diffuse
        self.var_spot_size = tk.DoubleVar(value=50.0)
        self.var_spot_spacing = tk.DoubleVar(value=100.0)  # Average spacing
        
        # Patchy
        self.var_patch_size = tk.DoubleVar(value=500.0)
        self.var_dispersion = tk.DoubleVar(value=1.0)
        
        # Compact
        self.var_border_width = tk.DoubleVar(value=100.0)
        self.var_irregularity = tk.DoubleVar(value=0.2)  # 0 = circle, higher = more irregular
        self.var_offset_x = tk.DoubleVar(value=0.0)  # Horizontal offset in mm
        self.var_offset_y = tk.DoubleVar(value=0.0)  # Vertical offset in mm

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
        
        # Pattern type
        ttk.Label(controls, text="Pattern Type:").grid(row=row, column=0, sticky="w")
        pattern_menu = ttk.Combobox(controls, textvariable=self.var_pattern_type,
                                    values=["Interstitial", "Diffuse", "Patchy", "Compact"],
                                    state="readonly", width=15)
        pattern_menu.grid(row=row, column=1, sticky="ew", pady=2)
        pattern_menu.bind("<<ComboboxSelected>>", self._on_pattern_change)
        row += 1
        
        # MatTek size
        ttk.Label(controls, text="MatTek Well:").grid(row=row, column=0, sticky="w")
        mattek_menu = ttk.Combobox(controls, textvariable=self.var_mattek_size,
                                   values=list(MATTEK_SIZES.keys()),
                                   state="readonly", width=20)
        mattek_menu.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1
        
        # Coverage
        self._add_slider(controls, row, "Total coverage (%):", self.var_coverage, 0, 95, "%")
        ttk.Label(controls, text="  (of entire circle)", 
                 font=("TkDefaultFont", 8, "italic")).grid(row=row, column=0, columnspan=2, sticky="w", padx=(0, 0))
        row += 1
        
        # White border (electrical propagation corridor)
        self._add_slider(controls, row, "White border (% radius):", self.var_white_border, 0, 40, "%")
        ttk.Label(controls, text="  (for electrical propagation)", 
                 font=("TkDefaultFont", 8, "italic")).grid(row=row, column=0, columnspan=2, sticky="w", padx=(0, 0))
        row += 1
        
        # Inner coverage display
        self.inner_coverage_label = ttk.Label(controls, text="Inner pattern coverage: 0%", 
                                              font=("TkDefaultFont", 9, "italic"))
        self.inner_coverage_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 5))
        row += 1
        
        # Pattern-specific parameters frame
        self.params_frame = ttk.LabelFrame(controls, text="Pattern Parameters", padding=5)
        self.params_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1
        
        # Buttons
        btn_frame = ttk.Frame(controls)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        btn_preview = ttk.Button(btn_frame, text="Update Preview", command=self.on_preview)
        btn_preview.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        btn_generate = ttk.Button(btn_frame, text="Generate PDF", command=self.on_generate)
        btn_generate.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
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
        
        # Scrollbars
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal")
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical")
        
        # Canvas for preview
        self.preview_canvas = tk.Canvas(canvas_frame, bg="black", 
                                       xscrollcommand=h_scroll.set,
                                       yscrollcommand=v_scroll.set)
        
        h_scroll.config(command=self.preview_canvas.xview)
        v_scroll.config(command=self.preview_canvas.yview)
        
        # Grid layout
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        
        # Bind mouse wheel for zoom
        self.preview_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.preview_canvas.bind("<Button-4>", self.on_mouse_wheel)  # Linux scroll up
        self.preview_canvas.bind("<Button-5>", self.on_mouse_wheel)  # Linux scroll down
        
        # Trace variables to update inner coverage
        self.var_coverage.trace_add("write", self._update_inner_coverage)
        self.var_white_border.trace_add("write", self._update_inner_coverage)

    def zoom_in(self):
        """Zoom in one level"""
        if self.zoom_index < len(self.zoom_levels) - 1:
            self.zoom_index += 1
            self.zoom_level = self.zoom_levels[self.zoom_index]
            self._update_preview_zoom()
    
    def zoom_out(self):
        """Zoom out one level"""
        if self.zoom_index > 0:
            self.zoom_index -= 1
            self.zoom_level = self.zoom_levels[self.zoom_index]
            self._update_preview_zoom()
    
    def zoom_reset(self):
        """Reset zoom to 100%"""
        self.zoom_index = 2  # 1.0x
        self.zoom_level = 1.0
        self._update_preview_zoom()
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel zoom"""
        if not self.preview_image_full:
            return
        
        # Determine scroll direction
        if event.num == 4 or event.delta > 0:  # Scroll up
            self.zoom_in()
        elif event.num == 5 or event.delta < 0:  # Scroll down
            self.zoom_out()
    
    def _update_preview_zoom(self):
        """Update preview with current zoom level"""
        if not self.preview_image_full:
            return
        
        # Update zoom label
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        
        # Calculate new size
        new_size = int(self.preview_size * self.zoom_level)
        
        # Resize image
        img_resized = self.preview_image_full.resize((new_size, new_size), Image.LANCZOS)
        self.preview_image_tk = ImageTk.PhotoImage(img_resized)
        
        # Update canvas
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, anchor="nw", image=self.preview_image_tk)
        self.preview_canvas.config(scrollregion=(0, 0, new_size, new_size))

    def _on_pattern_change(self, event=None):
        """Update parameter controls based on selected pattern type"""
        # Clear existing parameter widgets
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        
        pattern_type = self.var_pattern_type.get()
        
        if pattern_type == "Interstitial":
            self._add_entry(self.params_frame, 0, "Spacing (µm):", self.var_stripe_width, "µm")
            ttk.Label(self.params_frame, text="(stripe width auto-calculated from coverage)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
            self._add_entry(self.params_frame, 2, "Stripe angle (deg):", self.var_stripe_angle, "°")
        
        elif pattern_type == "Diffuse":
            self._add_entry(self.params_frame, 0, "Spot size (µm):", self.var_spot_size, "µm")
            ttk.Label(self.params_frame, text="(spots placed randomly, coverage controlled)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        elif pattern_type == "Patchy":
            self._add_entry(self.params_frame, 0, "Patch size (µm):", self.var_patch_size, "µm")
            ttk.Label(self.params_frame, text="(creates mix of large and small patches)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
            self._add_slider(self.params_frame, 2, "Dispersion:", self.var_dispersion, 0.3, 3.0, "")
            ttk.Label(self.params_frame, text="(lower=clustered, higher=spread out)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        elif pattern_type == "Compact":
            self._add_slider(self.params_frame, 0, "Irregularity:", self.var_irregularity, 0.0, 0.5, "")
            ttk.Label(self.params_frame, text="(0=circle, higher=more irregular)", 
                     font=("TkDefaultFont", 8, "italic")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
            self._add_slider(self.params_frame, 2, "Offset X (mm):", self.var_offset_x, -3.0, 3.0, "mm")
            self._add_slider(self.params_frame, 3, "Offset Y (mm):", self.var_offset_y, -3.0, 3.0, "mm")
            self._add_entry(self.params_frame, 4, "Border width (µm):", self.var_border_width, "µm")
    
    def _add_entry(self, parent, row, label, var, unit):
        """Add a labeled entry field"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=2)
        entry = ttk.Entry(frame, textvariable=var, width=10)
        entry.pack(side="left")
        if unit:
            ttk.Label(frame, text=unit).pack(side="left", padx=(4, 0))
        parent.columnconfigure(1, weight=1)
    
    def _add_slider(self, parent, row, label, var, from_, to, unit):
        """Add a labeled slider"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=2)
        
        slider = ttk.Scale(frame, from_=from_, to=to, variable=var, orient="horizontal")
        slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        value_label = ttk.Label(frame, text=f"{var.get():.1f}{unit}", width=6)
        value_label.pack(side="left")
        
        def update_label(*args):
            value_label.config(text=f"{var.get():.1f}{unit}")
        var.trace_add("write", update_label)
        
        return frame

    def _current_params(self):
        """Get current pattern parameters"""
        pattern_type = self.var_pattern_type.get()
        diameter = MATTEK_SIZES[self.var_mattek_size.get()]
        coverage = self.var_coverage.get() / 100.0
        white_border = self.var_white_border.get() / 100.0
        
        params = {
            "pattern_type": pattern_type,
            "coverage": coverage,
            "circle_diameter_mm": diameter,
            "white_border_fraction": white_border,
        }
        
        if pattern_type == "Interstitial":
            params["stripe_width_mm"] = self.var_stripe_width.get() / 1000.0
            params["angle_deg"] = self.var_stripe_angle.get()
        elif pattern_type == "Diffuse":
            params["spot_size_mm"] = self.var_spot_size.get() / 1000.0
            params["spacing_mm"] = self.var_spot_spacing.get() / 1000.0
        elif pattern_type == "Patchy":
            params["patch_size_mm"] = self.var_patch_size.get() / 1000.0
            params["dispersion"] = self.var_dispersion.get()
        elif pattern_type == "Compact":
            params["border_width_mm"] = self.var_border_width.get() / 1000.0
            params["irregularity"] = self.var_irregularity.get()
            params["offset_x_mm"] = self.var_offset_x.get()
            params["offset_y_mm"] = self.var_offset_y.get()
        
        return params

    def _update_inner_coverage(self, *args):
        """Update the inner coverage label"""
        total_coverage = self.var_coverage.get() / 100.0
        white_border = self.var_white_border.get() / 100.0
        pattern_radius_fraction = 1.0 - white_border
        area_ratio = pattern_radius_fraction ** 2
        if area_ratio > 0:
            inner_coverage = min(99, (total_coverage / area_ratio) * 100)
        else:
            inner_coverage = 0
        self.inner_coverage_label.config(text=f"Inner pattern coverage: {inner_coverage:.1f}%")

    def on_preview(self):
        """Generate preview image"""
        self.last_seed = random.randint(0, 10**9)
        params = self._current_params()
        
        # Generate high-res image for zooming
        self.preview_image_full = render_pattern_image(size_px=800, seed=self.last_seed, **params)
        
        # Reset zoom
        self.zoom_reset()

    def on_generate(self):
        """Generate PDF file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save pattern as PDF"
        )
        if not filename:
            return
        
        try:
            params = self._current_params()
            if self.last_seed is None:
                self.last_seed = random.randint(0, 10**9)
            generate_pattern(filename=filename, seed=self.last_seed, **params)
            messagebox.showinfo("Success", f"Pattern saved to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate pattern:\n{str(e)}")

def main():
    root = tk.Tk()
    gui = FibrosisPatternGUI(root)
    # Initialize parameter controls
    gui._on_pattern_change()
    root.mainloop()

if __name__ == "__main__":
    main()

