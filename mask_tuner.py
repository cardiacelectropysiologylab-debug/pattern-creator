"""
Interactive Fibrosis Mask Tuner
================================
Loads a TIFF video and lets you adjust segmentation parameters in real-time.
Displays the pattern comparison side-by-side.

Usage:
    python mask_tuner.py
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from pathlib import Path
from scipy import ndimage
from skimage import filters, morphology, measure, exposure
import cv2


# ============================================================
# PARAMETERS - Can be adjusted by sliders
# ============================================================

INPUT_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
PATTERN_PATH = r"C:\Users\Lior\Desktop\Shir\Fibrosis\Patterns\Pattern creator\9mm\9mm_Compact 2 circ_30.4% coverage_19% outer circle.pdf"

# Default parameters
THRESHOLD_PERCENTILE = 50  # For outer mask
RING_WIDTH = 10
K_MAD = 1.5
MIN_HOLE_SIZE = 50
MEDIAN_FILTER_RADIUS = 3
CLOSING_RADIUS = 20


# ============================================================
# FUNCTIONS
# ============================================================

def load_image(path: str) -> np.ndarray:
    """Load TIFF file."""
    print(f"[load] Loading: {path}")
    img = tifffile.imread(path)
    print(f"[load] Shape: {img.shape}, dtype: {img.dtype}")
    return img


def make_reference(stack: np.ndarray) -> np.ndarray:
    """Create reference image from stack."""
    if stack.ndim == 2:
        return stack.astype(np.float32)
    elif stack.ndim == 3:
        ref = np.median(stack.astype(np.float32), axis=0)
        return ref
    else:
        return stack[0].astype(np.float32)


def preprocess_image(ref: np.ndarray, median_radius: int) -> np.ndarray:
    """Preprocess reference image."""
    img = ref.copy()
    
    if median_radius > 0:
        img = ndimage.median_filter(img, size=median_radius * 2 + 1)
    
    # Normalize to [0, 1]
    img_min, img_max = img.min(), img.max()
    if img_max > img_min:
        img_norm = (img - img_min) / (img_max - img_min)
    else:
        img_norm = np.zeros_like(img, dtype=np.float32)
    
    return img_norm.astype(np.float32)


def make_outer_tissue_mask(img_norm: np.ndarray, closing_radius: int) -> np.ndarray:
    """Create outer tissue mask."""
    # Otsu thresholding
    threshold = filters.threshold_otsu(img_norm)
    binary = img_norm > threshold
    
    # Morphological closing
    if closing_radius > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                           (closing_radius * 2 + 1, closing_radius * 2 + 1))
        binary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0
    
    # Fill holes
    filled = ndimage.binary_fill_holes(binary)
    
    # Keep largest component
    labeled, n_comps = ndimage.label(filled)
    if n_comps > 0:
        sizes = ndimage.sum(filled, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        filled = (labeled == largest)
    
    return filled.astype(bool)


def get_centroid(mask: np.ndarray) -> tuple:
    """Get centroid of mask."""
    y, x = ndimage.center_of_mass(mask)
    return x, y


def compute_ring_stats(ref: np.ndarray, mask: np.ndarray, x0: float, y0: float, 
                       ring_width: int, k_mad: float) -> tuple:
    """Compute ring-based statistics for hole detection."""
    
    # Distance map
    yy, xx = np.ogrid[:ref.shape[0], :ref.shape[1]]
    dist_map = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)
    
    # Find ring boundaries
    max_dist = dist_map[mask].max() if mask.any() else 0
    n_rings = int(np.ceil(max_dist / ring_width))
    
    threshold_img = np.zeros_like(ref)
    
    for ring_idx in range(n_rings):
        r_lo = ring_idx * ring_width
        r_hi = (ring_idx + 1) * ring_width
        
        ring_mask = (dist_map >= r_lo) & (dist_map < r_hi) & mask
        
        if ring_mask.sum() < 5:
            continue
        
        ring_vals = ref[ring_mask]
        median_val = np.median(ring_vals)
        mad_val = np.median(np.abs(ring_vals - median_val))
        
        # Threshold
        threshold = median_val - k_mad * mad_val * 1.4826
        threshold_img[ring_mask] = threshold
    
    return threshold_img


def detect_holes(ref: np.ndarray, mask: np.ndarray, threshold_img: np.ndarray, 
                 min_size: int) -> np.ndarray:
    """Detect holes by comparing to threshold."""
    
    hole_mask = (ref < threshold_img) & mask
    
    # Remove small objects
    hole_mask = morphology.remove_small_objects(hole_mask, min_size=max(1, min_size - 1))
    
    return hole_mask


# ============================================================
# MAIN INTERACTIVE TUNER
# ============================================================

def main():
    # Load data
    print("Loading video...")
    stack = load_image(INPUT_PATH)
    ref = make_reference(stack)
    
    print(f"Reference shape: {ref.shape}, range: [{ref.min():.0f}, {ref.max():.0f}]")
    
    # Initial processing
    img_norm = preprocess_image(ref, MEDIAN_FILTER_RADIUS)
    outer_mask = make_outer_tissue_mask(img_norm, CLOSING_RADIUS)
    x0, y0 = get_centroid(outer_mask)
    
    print(f"Centroid: ({x0:.1f}, {y0:.1f})")
    print(f"Tissue area: {outer_mask.sum():.0f} px²")
    
    # Create figure with subplots and sliders
    fig = plt.figure(figsize=(16, 10))
    
    # Main comparison area
    ax_ref = plt.subplot(2, 3, 1)
    ax_mask = plt.subplot(2, 3, 2)
    ax_holes = plt.subplot(2, 3, 3)
    ax_overlay = plt.subplot(2, 3, 4)
    ax_ring = plt.subplot(2, 3, 5)
    ax_hist = plt.subplot(2, 3, 6)
    
    # Initialize images
    p2, p98 = np.percentile(ref, (2, 98))
    im_ref = ax_ref.imshow(ref, cmap="gray", vmin=p2, vmax=p98)
    ax_ref.set_title("Reference Image")
    ax_ref.plot(x0, y0, "r+", markersize=15, markeredgewidth=2)
    
    im_mask = ax_mask.imshow(outer_mask, cmap="Blues")
    ax_mask.set_title("Outer Tissue Mask")
    
    holes = detect_holes(ref, outer_mask, 
                        compute_ring_stats(ref, outer_mask, x0, y0, RING_WIDTH, K_MAD),
                        MIN_HOLE_SIZE)
    im_holes = ax_holes.imshow(holes, cmap="Reds")
    ax_holes.set_title(f"Holes Detected: {holes.sum():.0f} px")
    
    # Overlay
    ax_overlay.imshow(ref, cmap="gray", vmin=p2, vmax=p98)
    overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    overlay[holes] = [1, 0.2, 0.2, 0.6]
    ax_overlay.imshow(overlay)
    ax_overlay.set_title("Holes Overlaid")
    
    # Ring visualization
    yy, xx = np.ogrid[:ref.shape[0], :ref.shape[1]]
    dist_map = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)
    im_ring = ax_ring.imshow(dist_map * outer_mask, cmap="viridis")
    ax_ring.set_title("Distance Map (Rings)")
    
    # Histogram
    tissue_vals = ref[outer_mask]
    ax_hist.hist(tissue_vals, bins=50, color='gray', alpha=0.7)
    ax_hist.set_title("Tissue Intensity Distribution")
    ax_hist.set_xlabel("Intensity")
    ax_hist.set_ylabel("Count")
    
    plt.tight_layout(rect=[0, 0.3, 1, 0.95])
    
    # Add sliders
    ax_ring_w = plt.axes([0.2, 0.22, 0.6, 0.03])
    ax_k_mad = plt.axes([0.2, 0.18, 0.6, 0.03])
    ax_min_hole = plt.axes([0.2, 0.14, 0.6, 0.03])
    ax_close_r = plt.axes([0.2, 0.10, 0.6, 0.03])
    
    slider_ring_w = Slider(ax_ring_w, "Ring Width", 5, 30, valinit=RING_WIDTH, valstep=1)
    slider_k_mad = Slider(ax_k_mad, "K_MAD (sensitivity)", 0.5, 3.0, valinit=K_MAD, valstep=0.1)
    slider_min_hole = Slider(ax_min_hole, "Min Hole Size (px)", 10, 200, valinit=MIN_HOLE_SIZE, valstep=10)
    slider_close_r = Slider(ax_close_r, "Closing Radius", 0, 30, valinit=CLOSING_RADIUS, valstep=1)
    
    def update(val):
        ring_w = int(slider_ring_w.val)
        k_m = slider_k_mad.val
        min_h = int(slider_min_hole.val)
        close_r = int(slider_close_r.val)
        
        # Reprocess
        img_norm_new = preprocess_image(ref, MEDIAN_FILTER_RADIUS)
        outer_mask_new = make_outer_tissue_mask(img_norm_new, close_r)
        
        threshold_img = compute_ring_stats(ref, outer_mask_new, x0, y0, ring_w, k_m)
        holes_new = detect_holes(ref, outer_mask_new, threshold_img, min_h)
        
        # Update displays
        im_mask.set_array(outer_mask_new)
        im_holes.set_array(holes_new)
        ax_holes.set_title(f"Holes: {holes_new.sum():.0f} px ({100*holes_new.sum()/(outer_mask_new.sum() + 1e-6):.1f}%)")
        
        overlay_new = np.zeros((*ref.shape, 4), dtype=np.float32)
        overlay_new[holes_new] = [1, 0.2, 0.2, 0.6]
        ax_overlay.clear()
        ax_overlay.imshow(ref, cmap="gray", vmin=p2, vmax=p98)
        ax_overlay.imshow(overlay_new)
        ax_overlay.set_title("Holes Overlaid")
        ax_overlay.axis("off")
        
        fig.canvas.draw_idle()
    
    slider_ring_w.on_changed(update)
    slider_k_mad.on_changed(update)
    slider_min_hole.on_changed(update)
    slider_close_r.on_changed(update)
    
    # Title
    fig.suptitle("Fibrosis Pattern Tuner - Adjust sliders to optimize detection", 
                 fontsize=14, fontweight='bold')
    
    plt.show()


if __name__ == "__main__":
    main()
