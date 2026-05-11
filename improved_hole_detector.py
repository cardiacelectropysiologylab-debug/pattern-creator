"""
Improved Hole Detection - Avoid False Positives at Edges
=========================================================
Uses multiple strategies to:
1. Correctly identify tissue boundaries (ignore edges)
2. Detect ALL holes (black regions) within tissue
3. Avoid false positives from intensity gradients
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import ndimage
from skimage import filters, morphology
import cv2


def load_and_preprocess(path: str) -> np.ndarray:
    """Load TIFF and create reference."""
    print(f"[load] Loading: {path}")
    stack = tifffile.imread(path)
    
    if stack.ndim == 3:
        ref = np.median(stack.astype(np.float32), axis=0)
    else:
        ref = stack.astype(np.float32)
    
    return ref


def find_tissue_boundary_conservative(ref: np.ndarray) -> np.ndarray:
    """
    Find tissue using VERY conservative thresholding to avoid false edges.
    """
    print("[boundary] Finding tissue boundary (conservative)...")
    
    # Normalize
    ref_norm = ref.copy()
    ref_min, ref_max = ref_norm.min(), ref_norm.max()
    if ref_max > ref_min:
        ref_norm = (ref_norm - ref_min) / (ref_max - ref_min)
    
    # Use higher percentile to avoid dim edges
    threshold = np.percentile(ref_norm, 40)  # More conservative than Otsu
    print(f"[boundary] Threshold: {threshold:.3f}")
    
    tissue = ref_norm > threshold
    
    # Aggressive morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    tissue = cv2.morphologyEx(tissue.astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0
    tissue = cv2.morphologyEx(tissue.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0
    
    # Keep only largest component
    labeled, n_comps = ndimage.label(tissue)
    if n_comps > 0:
        sizes = ndimage.sum(tissue, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        tissue = (labeled == largest)
    
    print(f"[boundary] Tissue area: {tissue.sum():.0f} px²")
    
    return tissue


def detect_holes_adaptive_local(ref: np.ndarray, tissue_mask: np.ndarray) -> np.ndarray:
    """
    Detect holes using local adaptive intensity thresholding.
    This avoids false positives from global intensity gradients.
    """
    print("[detect] Using adaptive local thresholding...")
    
    # For each pixel, compare to local neighborhood
    kernel_size = 13
    
    # Create local mean image
    ref_uint8 = ((ref - ref.min()) / (ref.max() - ref.min() + 1e-6) * 255).astype(np.uint8)
    
    local_mean = cv2.blur(ref_uint8, (kernel_size, kernel_size))
    local_std = cv2.blur(ref_uint8.astype(float)**2, (kernel_size, kernel_size))
    local_std = np.sqrt(np.maximum(local_std - local_mean.astype(float)**2, 0)).astype(np.uint8)
    
    # Holes are pixels significantly DARKER than local mean
    # Use 1.5 std below local mean
    threshold_map = local_mean - 1.5 * local_std
    
    holes = (ref_uint8 < threshold_map) & tissue_mask
    
    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    holes = cv2.morphologyEx(holes.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0
    
    # Filter by size
    labeled, n_holes = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    
    for hole_id in range(1, n_holes + 1):
        hole_mask = (labeled == hole_id)
        area = hole_mask.sum()
        if 10 <= area <= 5000:  # Size filter
            holes_filtered |= hole_mask
    
    labeled_filtered, n_holes_filtered = ndimage.label(holes_filtered)
    print(f"[detect] Found {n_holes_filtered} holes")
    
    return holes_filtered


def detect_holes_by_absolute_darkness(ref: np.ndarray, tissue_mask: np.ndarray) -> np.ndarray:
    """
    Detect holes that are ABSOLUTELY dark (true black, not just darker than neighbors).
    """
    print("[detect] Using absolute darkness detection...")
    
    # Get intensity statistics for TRUE tissue (inner regions)
    # Erode tissue mask to get only solid middle regions
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    inner_tissue = cv2.morphologyEx(tissue_mask.astype(np.uint8), cv2.MORPH_ERODE, kernel) > 0
    
    if inner_tissue.sum() < 50:
        print("[detect] Not enough inner tissue for analysis")
        return np.zeros_like(tissue_mask, dtype=bool)
    
    # Get statistics from inner tissue only
    inner_intensities = ref[inner_tissue]
    inner_mean = np.mean(inner_intensities)
    inner_std = np.std(inner_intensities)
    
    print(f"[detect] Inner tissue: mean={inner_mean:.0f}, std={inner_std:.0f}")
    
    # Holes are MUCH darker than inner tissue mean
    hole_threshold = inner_mean - 2.5 * inner_std
    print(f"[detect] Hole threshold: {hole_threshold:.0f}")
    
    holes = (ref < hole_threshold) & tissue_mask
    
    # Morphological cleanup  
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    holes = cv2.morphologyEx(holes.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0
    
    # Filter by size
    labeled, n_holes = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    
    for hole_id in range(1, n_holes + 1):
        hole_mask = (labeled == hole_id)
        area = hole_mask.sum()
        if 10 <= area <= 5000:
            holes_filtered |= hole_mask
    
    labeled_filtered, n_holes_filtered = ndimage.label(holes_filtered)
    print(f"[detect] Found {n_holes_filtered} holes")
    
    return holes_filtered


def main():
    print("=" * 60)
    print("  Improved Hole Detector (Edge-Safe)")
    print("=" * 60)
    
    INPUT_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
    OUTPUT_DIR = r"C:\Users\Lior\Desktop\New folder\result"
    
    # Load
    ref = load_and_preprocess(INPUT_PATH)
    
    # Find conservative tissue boundary
    tissue = find_tissue_boundary_conservative(ref)
    
    # Method 1: Local adaptive
    print("\n--- Method 1: Local Adaptive ---")
    holes_adaptive = detect_holes_adaptive_local(ref, tissue)
    
    # Method 2: Absolute darkness
    print("\n--- Method 2: Absolute Darkness ---")
    holes_dark = detect_holes_by_absolute_darkness(ref, tissue)
    
    # Combine (intersection for precision, union for sensitivity)
    holes_combined = holes_adaptive | holes_dark
    
    labeled_combined, n_combined = ndimage.label(holes_combined)
    coverage = 100 * holes_combined.sum() / (tissue.sum() + 1e-6)
    
    print(f"\n[result] Total holes: {n_combined}")
    print(f"[result] Coverage: {coverage:.1f}%")
    
    # Save
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    final_mask = (tissue & ~holes_combined) * 255
    tifffile.imwrite(Path(OUTPUT_DIR) / "improved_tissue_mask.tif", final_mask.astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "improved_hole_mask.tif", (holes_combined * 255).astype(np.uint8))
    
    # Visualize
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.patch.set_facecolor("#1a1a2e")
    
    p2, p98 = np.percentile(ref, (2, 98))
    
    axes[0, 0].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 0].set_title("Reference Image", color='white')
    axes[0, 0].axis('off')
    
    axes[0, 1].imshow(tissue, cmap='Blues', alpha=0.8)
    axes[0, 1].set_title("Tissue Boundary (Conservative)", color='white')
    axes[0, 1].axis('off')
    
    axes[0, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 2].imshow(tissue.astype(float), cmap='Blues', alpha=0.3)
    axes[0, 2].set_title("Tissue Overlay", color='white')
    axes[0, 2].axis('off')
    
    axes[1, 0].imshow(holes_adaptive, cmap='Reds')
    labeled_a, n_a = ndimage.label(holes_adaptive)
    axes[1, 0].set_title(f"Holes (Adaptive): {n_a}", color='white')
    axes[1, 0].axis('off')
    
    axes[1, 1].imshow(holes_dark, cmap='Oranges')
    labeled_d, n_d = ndimage.label(holes_dark)
    axes[1, 1].set_title(f"Holes (Dark): {n_d}", color='white')
    axes[1, 1].axis('off')
    
    axes[1, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    overlay[holes_combined] = [1, 0.2, 0.2, 0.7]
    axes[1, 2].imshow(overlay)
    axes[1, 2].set_title(f"Combined ({n_combined} holes, {coverage:.1f}%)", color='white')
    axes[1, 2].axis('off')
    
    for ax in axes.flat:
        for spine in ax.spines.values():
            spine.set_visible(False)
    
    plt.suptitle("Improved Hole Detection (Conservative Boundary)",
                 color='white', fontsize=13, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(Path(OUTPUT_DIR) / "improved_detection.png", 
                dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.show()
    
    print(f"\n[done] Saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
