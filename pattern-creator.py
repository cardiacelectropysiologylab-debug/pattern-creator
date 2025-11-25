import math
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from PIL import Image, ImageDraw, ImageTk

def draw_circle_background(c, diameter_mm):
    radius_pt = (diameter_mm / 2.0) * mm
    page_size = diameter_mm * mm + 4 * mm
    cx = cy = page_size / 2.0
    c.setFillColor(colors.black)
    c.rect(0, 0, page_size, page_size, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.circle(cx, cy, radius_pt, stroke=0, fill=1)
    return page_size, cx, cy, radius_pt

def clip_to_circle(c, cx, cy, radius_pt):
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, radius_pt)
    c.clipPath(p, stroke=0, fill=0)

def end_clip(c):
    c.restoreState()

def add_interstitial(c, cx, cy, radius_pt, coverage, stripe_width_um, angle_deg=0):
    if coverage <= 0:
        return
    stripe_width_mm = stripe_width_um / 1000.0
    stripe_width_pt = stripe_width_mm * mm
    if coverage >= 1:
        gap_pt = 0
    else:
        gap_pt = stripe_width_pt * (1.0 - coverage) / max(coverage, 1e-6)
    diag = radius_pt * 2 * math.sqrt(2)
    total_width = diag + 4 * (stripe_width_pt + gap_pt)
    x0 = cx - total_width / 2.0
    c.saveState()
    c.translate(cx, cy)
    c.rotate(angle_deg)
    c.translate(-cx, -cy)
    c.setFillColor(colors.black)
    x = x0
    while x < x0 + total_width:
        c.rect(x, cy - diag / 2.0, stripe_width_pt, diag, stroke=0, fill=1)
        x += stripe_width_pt + gap_pt
    c.restoreState()

def add_interstitial_preview(draw, cx, cy, radius_px, coverage, stripe_width_um, angle_deg, diameter_um):
    # draw stripes everywhere, mask later
    temp = Image.new("L", draw.im.size, 255)
    dtemp = ImageDraw.Draw(temp)
    stripe_width_px = (stripe_width_um / diameter_um) * (2 * radius_px)
    stripe_width_px = max(1.0, stripe_width_px)
    if coverage > 0:
        gap_px = stripe_width_px * (1.0 - coverage) / max(coverage, 1e-6)
    else:
        gap_px = 0
    diag = radius_px * 2 * math.sqrt(2)
    total_width = diag + 4 * (stripe_width_px + gap_px)
    x0 = -total_width / 2.0
    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x = x0
    while x < x0 + total_width:
        xr0 = x
        xr1 = x + stripe_width_px
        y_low = -diag / 2.0
        y_high = diag / 2.0
        corners_r = [(xr0, y_low), (xr1, y_low), (xr1, y_high), (xr0, y_high)]
        pts = []
        for xr, yr in corners_r:
            X = cx + xr * cos_a - yr * sin_a
            Y = cy + xr * sin_a + yr * cos_a
            pts.append((X, Y))
        dtemp.polygon(pts, fill=0)
        x += stripe_width_px + gap_px
    # mask with inner circle
    mask = Image.new("L", draw.im.size, 0)
    dmask = ImageDraw.Draw(mask)
    dmask.ellipse((cx-radius_px, cy-radius_px, cx+radius_px, cy+radius_px), fill=255)
    temp.paste(255, mask=Image.eval(mask, lambda v: 255-v))
    draw.bitmap((0, 0), temp)

def render_pattern_image(
    size_px,
    coverage=0.2,
    circle_diameter_mm=10.0,
    stripe_width_um=20.0,
    stripe_angle_deg=0.0,
    scar_margin_fraction=0.15,
    seed=None,
):
    if seed is not None:
        random.seed(seed)
    base = Image.new("L", (size_px, size_px), 0)
    draw_base = ImageDraw.Draw(base)
    cx = cy = size_px / 2.0
    radius_px = size_px * 0.45
    draw_base.ellipse((cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px), fill=255)
    tissue = Image.new("L", (size_px, size_px), 255)
    draw_t = ImageDraw.Draw(tissue)
    scar_radius = radius_px * (1.0 - max(0.0, min(0.9, scar_margin_fraction)))
    diameter_um = circle_diameter_mm * 1000.0
    add_interstitial_preview(draw_t, cx, cy, scar_radius, coverage, stripe_width_um, stripe_angle_deg, diameter_um)
    mask = Image.new("L", (size_px, size_px), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.ellipse((cx - scar_radius, cy - scar_radius, cx + scar_radius, cy + scar_radius), fill=255)
    base.paste(tissue, (0, 0), mask)
    return base.convert("RGB")

def generate_pattern(
    filename,
    coverage=0.2,
    circle_diameter_mm=10.0,
    stripe_width_um=20.0,
    stripe_angle_deg=0.0,
    scar_margin_fraction=0.15,
    seed=None,
):
    if seed is not None:
        random.seed(seed)
    dummy_size = circle_diameter_mm * mm + 4 * mm
    c = canvas.Canvas(filename, pagesize=(dummy_size, dummy_size))
    page_size, cx, cy, radius_pt = draw_circle_background(c, circle_diameter_mm)
    clip_to_circle(c, cx, cy, radius_pt)
    scar_radius = radius_pt * (1.0 - max(0.0, min(0.9, scar_margin_fraction)))
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, scar_radius)
    c.clipPath(p, stroke=0, fill=0)
    add_interstitial(c, cx, cy, scar_radius, coverage, stripe_width_um, stripe_angle_deg)
    c.restoreState()
    end_clip(c)
    c.showPage()
    c.save()

class InterstitialGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PRIMO Interstitial Pattern Generator")
        self.preview_size = 400
        self.preview_image_tk = None
        self.last_seed = None
        self._build_widgets()
    def _build_widgets(self):
        self.var_coverage = tk.DoubleVar(value=20.0)
        self.var_diameter = tk.DoubleVar(value=10.0)
        self.var_border = tk.DoubleVar(value=15.0)
        self.var_stripe_width = tk.DoubleVar(value=20.0)
        self.var_stripe_angle = tk.DoubleVar(value=0.0)
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        controls = ttk.Frame(main)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        preview_frame = ttk.Frame(main)
        preview_frame.grid(row=0, column=1, sticky="nsew")
        row = 0
        self._add_number_entry(controls, row, "Coverage (% area scar):", self.var_coverage, 0, 60, 1, "%"); row += 1
        self._add_number_entry(controls, row, "Circle diameter (mm):", self.var_diameter, 4, 25, 0.1, "mm"); row += 1
        self._add_number_entry(controls, row, "White border (% radius):", self.var_border, 0, 40, 1, "%"); row += 1
        self._add_number_entry(controls, row, "Stripe width (µm):", self.var_stripe_width, 2, 80, 1, "µm"); row += 1
        self._add_number_entry(controls, row, "Stripe angle (deg):", self.var_stripe_angle, -90, 90, 1, "°"); row += 1
        btn_frame = ttk.Frame(controls)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        btn_preview = ttk.Button(btn_frame, text="Update preview", command=self.on_preview)
        btn_preview.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        btn_generate = ttk.Button(btn_frame, text="Generate PDF", command=self.on_generate)
        btn_generate.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        for col in range(2):
            controls.columnconfigure(col, weight=1)
        self.preview_label = ttk.Label(preview_frame, text="Preview:")
        self.preview_label.pack(anchor="w")
        self.preview_canvas = tk.Label(preview_frame, bg="black")
        self.preview_canvas.pack(fill="both", expand=True)
    def _add_number_entry(self, parent, row, label, var, frm, to, step, unit):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=2)
        spin = tk.Spinbox(
            frame, textvariable=var, from_=frm, to=to,
            increment=step, width=7, justify="right"
        )
        spin.pack(side="left")
        if unit:
            ttk.Label(frame, text=unit).pack(side="left", padx=(4, 0))
        return frame
    def _current_params(self):
        return dict(
            coverage=max(0.0, min(1.0, self.var_coverage.get() / 100.0)),
            circle_diameter_mm=self.var_diameter.get(),
            stripe_width_um=self.var_stripe_width.get(),
            stripe_angle_deg=self.var_stripe_angle.get(),
            scar_margin_fraction=max(0.0, min(0.9, self.var_border.get() / 100.0)),
        )
    def on_preview(self):
        self.last_seed = random.randint(0, 10**9)
        params = self._current_params()
        img = render_pattern_image(
            size_px=self.preview_size,
            seed=self.last_seed,
            **params
        )
        self.preview_image_tk = ImageTk.PhotoImage(img)
        self.preview_canvas.configure(image=self.preview_image_tk)
    def on_generate(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save PRIMO pattern as PDF",
        )
        if not filename:
            return
        try:
            params = self._current_params()
            if self.last_seed is None:
                self.last_seed = random.randint(0, 10**9)
            generate_pattern(
                filename=filename,
                seed=self.last_seed,
                **params
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate pattern:\n{e}")
            return
        messagebox.showinfo("Done", f"Pattern saved to:\n{filename}")

def main():
    root = tk.Tk()
    InterstitialGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
