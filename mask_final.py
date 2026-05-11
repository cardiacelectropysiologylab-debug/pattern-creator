"""
Optimal Fibrosis Hole Detector
===============================
Combined approach using Otsu + Local Intensity Detection
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import ndimage
from skimage import filters, morphology, measure
import cv2


def main():
    print("=" * 60)
    print("  Optimal Fibrosis Hole Detector")
    print("=" * 60)
    
    INPUT_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
    OUTPUT_DIR = r"C:\Users\Lior\Desktop\New folder\result"
    
    # ======== STEP 1: LOAD AND PREPROCESS ========
    print("\n[step1] Loading and preprocessing...")
    stack = tifffile.imread(INPUT_PATH)
    print(f"Shape: {stack.shape}, dtype: {stack.dtype}")
    
    if stack.ndim == 3:
        ref = np.median(stack.astype(np.float32), axis=0)
    else:
        ref = stack.astype(np.float32)
    
    print(f"Reference: min={ref.min():.0f}, max={ref.max():.0f}, mean={ref.mean():.0f}, std={ref.std():.0f}")
    
    # Apply gentle median filter to reduce noise
    ref_smooth = ndimage.median_filter(ref, size=3)
    
    # ======== STEP 2: FIND TISSUE BOUNDARY (Otsu) ========
    print("\n[step2] Finding tissue boundary...")
    otsu_thresh = filters.threshold_otsu(ref_smooth)
    print(f"Otsu threshold: {otsu_thresh:.0f}")
    
    tissue_raw = ref_smooth > otsu_thresh
    
    # Morphological cleanup
    kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    tissue = cv2.morphologyEx(tissue_raw.astype(np.uint8), cv2.MORPH_CLOSE, kernel_large) > 0
    tissue = cv2.morphologyEx(tissue.astype(np.uint8), cv2.MORPH_OPEN, kernel_large) > 0
    tissue = ndimage.binary_fill_holes(tissue)
    
    # Keep only largest component
    labeled, n_comps = ndimage.label(tissue)
    if n_comps > 0:
        sizes = ndimage.sum(tissue, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        tissue = (labeled == largest)
    
    print(f"Tissue area: {tissue.sum():.0f} px²")
    
    # ======== STEP 3: DETECT HOLES WITHIN TISSUE ========
    print("\n[step3] Detecting holes...")
    
    # Strategy 1: Pixels inside tissue that are much darker than tissue mean
    tissue_intensities = ref[tissue]
    tissue_mean = np.mean(tissue_intensities)
    tissue_std = np.std(tissue_intensities)
    tissue_percentile_90 = np.percentile(tissue_intensities, 90)  # Bright part of tissue
    
    print(f"Tissue stats: mean={tissue_mean:.0f}, std={tissue_std:.0f}, p90={tissue_percentile_90:.0f}")
    
    # Holes are pixels SIGNIFICANTLY darker than bright tissue
    hole_threshold = tissue_percentile_90 - 2.0 * tissue_std
    print(f"Hole threshold: {hole_threshold:.0f}")
    
    # Find dark pixels inside tissue
    holes_dark = (ref < hole_threshold) & tissue
    
    # Strategy 2: Use local contrast
    # Create local mean (tissue baseline in this region)
    local_mean = cv2.blur(ref.astype(np.float32), (13, 13))
    
    # Holes are much darker than their local neighborhood
    holes_local = (ref < (local_mean - 1.5 * tissue_std)) & tissue & (ref < otsu_thresh)
    
    # Combine strategies
    holes_combined = holes_dark | holes_local
    
    # Morphological cleanup
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    holes = cv2.morphologyEx(holes_combined.astype(np.uint8), cv2.MORPH_OPEN, kernel_small) > 0
    
    # Filter by size
    labeled_holes, n_holes_raw = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    
    hole_areas = []
    for hole_id in range(1, n_holes_raw + 1):
        hole_mask = (labeled_holes == hole_id)
        area = hole_mask.sum()
        if 10 <= area <= 5000:  # Size range
            holes_filtered |= hole_mask
            hole_areas.append(area)
    
    labeled_final, n_holes = ndimage.label(holes_filtered)
    
    coverage = 100 * holes_filtered.sum() / (tissue.sum() + 1e-6)
    
    print(f"Holes found: {n_holes}")
    print(f"Coverage: {coverage:.1f}%")
    if len(hole_areas) > 0:
        print(f"Hole sizes: min={min(hole_areas)}, max={max(hole_areas)}, mean={np.mean(hole_areas):.0f}")
    
    # ======== STEP 4: CREATE FINAL MASK ========
    final_mask = (tissue & ~holes_filtered) * 255
    
    # ======== STEP 5: SAVE ========
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    tifffile.imwrite(Path(OUTPUT_DIR) / "optimal_tissue_mask.tif", final_mask.astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "optimal_hole_mask.tif", (holes_filtered * 255).astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "optimal_tissue_boundary.tif", (tissue * 255).astype(np.uint8))
    
    # ======== STEP 6: VISUALIZE ========
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.patch.set_facecolor("#1a1a2e")
    
    p2, p98 = np.percentile(ref, (2, 98))
    
    axes[0, 0].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 0].set_title("Reference Image", color='white', fontsize=11)
    axes[0, 0].axis('off')
    
    axes[0, 1].imshow(tissue, cmap='Blues')
    axes[0, 1].set_title("Detected Tissue", color='white', fontsize=11)
    axes[0, 1].axis('off')
    
    axes[0, 2].imshow(holes_dark, cmap='Reds', alpha=0.7)
    axes[0, 2].set_title("Holes (Dark Strategy)", color='white', fontsize=11)
    axes[0, 2].axis('off')
    
    axes[1, 0].imshow(holes_local, cmap='Oranges', alpha=0.7)
    axes[1, 0].set_title("Holes (Local Contrast)", color='white', fontsize=11)
    axes[1, 0].axis('off')
    
    axes[1, 1].imshow(holes_filtered, cmap='Reds')
    axes[1, 1].set_title(f"Final Holes ({n_holes})", color='white', fontsize=11)
    axes[1, 1].axis('off')
    
    axes[1, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    overlay[holes_filtered] = [1, 0.2, 0.2, 0.7]
    axes[1, 2].imshow(overlay)
    axes[1, 2].set_title(f"Overlay ({coverage:.1f}%)", color='white', fontsize=11)
    axes[1, 2].axis('off')
    
    for ax in axes.flat:
        for spine in ax.spines.values():
            spine.set_visible(False)
    
    plt.suptitle("Optimal Fibrosis Detection", color='white', fontsize=13, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(Path(OUTPUT_DIR) / "optimal_detection.png", 
                dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    
    # Don't show - just save
    plt.close()
    
    print(f"\n[done] Saved to: {OUTPUT_DIR}")
    print("  - optimal_tissue_mask.tif")
    print("  - optimal_hole_mask.tif")
    print("  - optimal_tissue_boundary.tif")
    print("  - optimal_detection.png")


if __name__ == "__main__":
    main()
