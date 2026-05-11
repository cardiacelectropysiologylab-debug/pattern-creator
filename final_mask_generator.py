"""
FINAL Fibrosis Mask Generator
=============================
Generates tissue and hole masks optimized for fibrosis analysis.
Detects black holes (low intensity) within white tissue (high intensity).

Usage:
    python final_mask_generator.py

OUTPUT FILES:
  - final_tissue_mask.tif      : Main mask (255=tissue, 0=holes/background)
  - final_hole_mask.tif        : Binary hole locations
  - final_visualization.png    : Quality control visualization
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import ndimage
from skimage import filters
import cv2


# ========================================================================
# ADJUSTABLE PARAMETERS
# ========================================================================

# Input/Output
INPUT_VIDEO = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
OUTPUT_DIR = r"C:\Users\Lior\Desktop\New folder\result"

# Preprocessing
MEDIAN_FILTER_RADIUS = 3        # Smooth noise (3-5 pixels)

# Tissue boundary detection (Otsu)
# Otsu_ADJUSTMENT: multiply Otsu threshold by this factor
# 1.0 = standard Otsu
# >1.0 = more conservative (excludes dim edges)
# <1.0 = more aggressive (includes more regions)
OTSU_ADJUSTMENT = 1.0

# Morphological cleanup for tissue boundary
MORPH_KERNEL_SIZE = 7           # (7-9 pixels for smooth boundary)

# Hole detection
HOLE_SENSITIVITY = 0.8          # Multiplier for std deviation (LOWER = more holes)
                                # 0.8 = very sensitive (many holes)
                                # 1.0 = standard
                                # 1.5 = conservative (few holes)

# Hole size filtering
MIN_HOLE_PIXELS = 15            # Smallest hole to keep
MAX_HOLE_PIXELS = 800           # Largest hole to keep (avoid huge false regions)

# ========================================================================
# MAIN ALGORITHM
# ========================================================================

def main():
    print("=" * 70)
    print("  FINAL Fibrosis Mask Generator")
    print("=" * 70)
    
    # ---- 1. LOAD VIDEO ----
    print("\n[1/6] Loading video...")
    stack = tifffile.imread(INPUT_VIDEO)
    
    if stack.ndim == 3:
        print(f"  Stack shape: {stack.shape}")
        ref = np.median(stack.astype(np.float32), axis=0)
        print(f"  Created median projection")
    else:
        ref = stack.astype(np.float32)
    
    print(f"  Reference: shape={ref.shape}, "
          f"min={ref.min():.0f}, max={ref.max():.0f}, "
          f"mean={ref.mean():.0f}, std={ref.std():.0f}")
    
    # ---- 2. PREPROCESS ----
    print("\n[2/6] Preprocessing...")
    if MEDIAN_FILTER_RADIUS > 0:
        ref = ndimage.median_filter(ref, size=MEDIAN_FILTER_RADIUS * 2 + 1)
        print(f"  Applied median filter (radius={MEDIAN_FILTER_RADIUS})")
    
    # ---- 3. FIND TISSUE BOUNDARY ----
    print("\n[3/6] Detecting tissue boundary...")
    otsu_thresh = filters.threshold_otsu(ref)
    otsu_thresh_adjusted = otsu_thresh * OTSU_ADJUSTMENT
    print(f"  Otsu threshold: {otsu_thresh:.0f} (adjusted: {otsu_thresh_adjusted:.0f})")
    
    tissue_raw = ref > otsu_thresh_adjusted
    
    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                       (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE))
    tissue = cv2.morphologyEx(tissue_raw.astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0
    tissue = cv2.morphologyEx(tissue.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0
    tissue = ndimage.binary_fill_holes(tissue)
    
    # Keep largest connected component
    labeled, n_comps = ndimage.label(tissue)
    if n_comps > 0:
        sizes = ndimage.sum(tissue, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        tissue = (labeled == largest)
    
    tissue_area = tissue.sum()
    print(f"  Tissue area: {tissue_area:.0f} pixels")
    
    # ---- 4. DETECT HOLES IN TISSUE ----
    print("\n[4/6] Detecting holes...")
    
    # Get tissue intensity statistics
    tissue_vals = ref[tissue]
    tissue_mean = np.mean(tissue_vals)
    tissue_std = np.std(tissue_vals)
    tissue_p90 = np.percentile(tissue_vals, 90)  # Bright part of tissue
    
    print(f"  Tissue intensity: mean={tissue_mean:.0f}, std={tissue_std:.0f}, p90={tissue_p90:.0f}")
    
    # Holes are DARK pixels (much darker than bright tissue)
    hole_threshold = tissue_p90 - HOLE_SENSITIVITY * tissue_std
    print(f"  Hole threshold: {hole_threshold:.0f} "
          f"(p90 - {HOLE_SENSITIVITY}×std)")
    
    # Strategy 1: Absolute darkness
    holes_dark = (ref < hole_threshold) & tissue
    
    # Strategy 2: Local contrast (compare to local neighborhood)
    local_mean = cv2.blur(ref.astype(np.float32), (13, 13))
    holes_local = (ref < (local_mean - HOLE_SENSITIVITY * tissue_std)) & tissue
    
    # Combine strategies
    holes = holes_dark | holes_local
    
    # Morphological cleanup
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    holes = cv2.morphologyEx(holes.astype(np.uint8), cv2.MORPH_OPEN, kernel_small) > 0
    
    # Filter by size
    labeled_holes, n_holes_raw = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    hole_sizes = []
    
    for hole_id in range(1, n_holes_raw + 1):
        hole_mask = (labeled_holes == hole_id)
        area = hole_mask.sum()
        if MIN_HOLE_PIXELS <= area <= MAX_HOLE_PIXELS:
            holes_filtered |= hole_mask
            hole_sizes.append(area)
    
    labeled_final, n_holes = ndimage.label(holes_filtered)
    holes_area = holes_filtered.sum()
    coverage = 100 * holes_area / (tissue_area + 1e-6)
    
    print(f"  Holes found: {n_holes}")
    print(f"  Holes area: {holes_area:.0f} pixels ({coverage:.1f}% of tissue)")
    if len(hole_sizes) > 0:
        print(f"  Hole sizes: min={min(hole_sizes)}, max={max(hole_sizes)}, "
              f"mean={np.mean(hole_sizes):.0f}, median={np.median(hole_sizes):.0f}")
    
    # ---- 5. CREATE FINAL MASK ----
    print("\n[5/6] Creating final mask...")
    final_mask = (tissue & ~holes_filtered) * 255
    
    # ---- 6. SAVE & VISUALIZE ----
    print("\n[6/6] Saving results...")
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    tifffile.imwrite(Path(OUTPUT_DIR) / "final_tissue_mask.tif", 
                     final_mask.astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "final_hole_mask.tif", 
                     (holes_filtered * 255).astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "final_tissue_boundary.tif",
                     (tissue * 255).astype(np.uint8))
    
    # Visualization
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.patch.set_facecolor("#1a1a2e")
    
    p2, p98 = np.percentile(ref, (2, 98))
    
    # Reference
    axes[0, 0].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 0].set_title("Reference Image", color='white', fontsize=11, fontweight='bold')
    axes[0, 0].axis('off')
    
    # Tissue boundary
    axes[0, 1].imshow(tissue, cmap='Blues')
    axes[0, 1].set_title(f"Tissue Boundary\n({tissue_area:.0f} px)", 
                         color='white', fontsize=11, fontweight='bold')
    axes[0, 1].axis('off')
    
    # Holes alone
    axes[0, 2].imshow(holes_filtered, cmap='Reds')
    axes[0, 2].set_title(f"Detected Holes\n({n_holes} regions, {holes_area:.0f} px)", 
                         color='white', fontsize=11, fontweight='bold')
    axes[0, 2].axis('off')
    
    # Final mask
    axes[1, 0].imshow(final_mask, cmap='gray')
    axes[1, 0].set_title("Final Tissue Mask\n(255=tissue, 0=holes)", 
                         color='white', fontsize=11, fontweight='bold')
    axes[1, 0].axis('off')
    
    # Overlay on reference
    axes[1, 1].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    tissue_overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    tissue_overlay[tissue] = [0.2, 0.8, 0.2, 0.3]  # Green overlay
    axes[1, 1].imshow(tissue_overlay)
    axes[1, 1].set_title("Tissue Overlay (Green)", 
                         color='white', fontsize=11, fontweight='bold')
    axes[1, 1].axis('off')
    
    # Overlay holes
    axes[1, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    hole_overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    hole_overlay[holes_filtered] = [1.0, 0.2, 0.2, 0.7]  # Red overlay
    axes[1, 2].imshow(hole_overlay)
    axes[1, 2].set_title(f"Holes Overlay (Red)\nCoverage: {coverage:.1f}%", 
                         color='white', fontsize=11, fontweight='bold')
    axes[1, 2].axis('off')
    
    # Styling
    for ax in axes.flat:
        for spine in ax.spines.values():
            spine.set_visible(False)
    
    plt.suptitle("FINAL Fibrosis Mask Analysis", 
                 color='white', fontsize=14, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(Path(OUTPUT_DIR) / "final_visualization.png", 
                dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    
    # Summary
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Input:      {INPUT_VIDEO}")
    print(f"  Output:     {OUTPUT_DIR}")
    print(f"  Tissue:     {tissue_area:.0f} pixels")
    print(f"  Holes:      {n_holes} regions, {holes_area:.0f} pixels ({coverage:.1f}%)")
    print(f"\n  Files saved:")
    print(f"    ✓ final_tissue_mask.tif       (Main result: tissue mask)")
    print(f"    ✓ final_hole_mask.tif         (Hole locations)")
    print(f"    ✓ final_tissue_boundary.tif   (Tissue boundary)")
    print(f"    ✓ final_visualization.png     (Quality control figure)")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
