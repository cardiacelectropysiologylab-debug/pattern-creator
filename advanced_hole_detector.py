"""
Advanced Hole Detection for Fibrosis Tissue
=============================================
Uses adaptive thresholding, morphological operations, and contour detection
to find holes in tissue images captured by macroscope.

Usage:
    python advanced_hole_detector.py
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


# ============================================================
# PARAMETERS
# ============================================================

INPUT_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
OUTPUT_DIR = r"C:\Users\Lior\Desktop\New folder\result"

# Adaptive thresholding block size
ADAPTIVE_BLOCK_SIZE = 31

# Morphological operations
MORPH_CLOSE_KERNEL = 5
MORPH_OPEN_KERNEL = 3

# Hole area filtering
MIN_HOLE_AREA = 10  # pixels - reduced for smaller holes
MAX_HOLE_AREA = 5000  # pixels


# ============================================================
# ADVANCED DETECTION
# ============================================================

def load_and_preprocess(path: str) -> np.ndarray:
    """Load TIFF and create reference from median projection."""
    print(f"[load] Loading: {path}")
    stack = tifffile.imread(path)
    print(f"[load] Shape: {stack.shape}")
    
    if stack.ndim == 3:
        ref = np.median(stack.astype(np.float32), axis=0)
    else:
        ref = stack.astype(np.float32)
    
    return ref


def detect_tissue_and_holes_adaptive(ref: np.ndarray) -> tuple:
    """
    Detect tissue and holes using adaptive thresholding.
    More robust to uneven illumination.
    """
    print("[detect] Using adaptive thresholding...")
    
    # Normalize to 0-255 for OpenCV
    ref_norm = ((ref - ref.min()) / (ref.max() - ref.min() + 1e-6) * 255).astype(np.uint8)
    
    # Adaptive thresholding
    tissue_binary = cv2.adaptiveThreshold(
        ref_norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, ADAPTIVE_BLOCK_SIZE, 2
    )
    tissue_mask = tissue_binary > 0
    
    # Morphological cleanup
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                             (MORPH_CLOSE_KERNEL * 2 + 1, 
                                              MORPH_CLOSE_KERNEL * 2 + 1))
    tissue_mask = cv2.morphologyEx(tissue_mask.astype(np.uint8), 
                                   cv2.MORPH_CLOSE, kernel_close) > 0
    
    # Fill small holes within tissue
    tissue_filled = ndimage.binary_fill_holes(tissue_mask)
    
    # Keep only largest component (outer tissue)
    labeled, n_comps = ndimage.label(tissue_filled)
    if n_comps > 0:
        sizes = ndimage.sum(tissue_filled, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        outer_tissue = (labeled == largest)
    else:
        outer_tissue = tissue_filled
    
    print(f"[detect] Tissue area: {outer_tissue.sum():.0f} px²")
    
    # Detect holes: regions inside tissue that are NOT tissue
    holes = outer_tissue & ~tissue_mask
    
    # Filter by area
    labeled_holes, n_holes_raw = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    
    for hole_id in range(1, n_holes_raw + 1):
        hole_mask = (labeled_holes == hole_id)
        area = hole_mask.sum()
        if MIN_HOLE_AREA <= area <= MAX_HOLE_AREA:
            holes_filtered |= hole_mask
    
    labeled_holes_filtered, n_holes = ndimage.label(holes_filtered)
    
    print(f"[detect] Found {n_holes} holes after filtering")
    
    return outer_tissue, holes_filtered, ref_norm


def detect_holes_by_intensity(ref: np.ndarray, tissue_mask: np.ndarray) -> np.ndarray:
    """
    Detect holes by finding regions with anomalously low intensity
    compared to surrounding tissue (intensity-based method).
    """
    print("[detect] Using intensity-based detection...")
    
    # Get background tissue statistics
    tissue_intensities = ref[tissue_mask]
    tissue_mean = np.mean(tissue_intensities)
    tissue_std = np.std(tissue_intensities)
    tissue_threshold = tissue_mean - 1.5 * tissue_std  # More sensitive
    
    print(f"[detect] Tissue mean: {tissue_mean:.0f}, std: {tissue_std:.0f}")
    print(f"[detect] Hole threshold: {tissue_threshold:.0f}")
    
    # Holes are regions with very low intensity
    potential_holes = ref < tissue_threshold
    potential_holes = potential_holes & tissue_mask
    
    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    holes = cv2.morphologyEx(potential_holes.astype(np.uint8), 
                             cv2.MORPH_OPEN, kernel) > 0
    
    # Filter by area
    labeled_holes, n_holes_raw = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    
    for hole_id in range(1, n_holes_raw + 1):
        hole_mask = (labeled_holes == hole_id)
        area = hole_mask.sum()
        if MIN_HOLE_AREA <= area <= MAX_HOLE_AREA:
            holes_filtered |= hole_mask
    
    labeled_holes_filtered, n_holes = ndimage.label(holes_filtered)
    
    print(f"[detect] Found {n_holes} holes")
    
    return holes_filtered


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  Advanced Fibrosis Hole Detector")
    print("=" * 60)
    
    # Load and preprocess
    ref = load_and_preprocess(INPUT_PATH)
    
    # Method 1: Adaptive thresholding
    print("\n--- Method 1: Adaptive Thresholding ---")
    tissue_adaptive, holes_adaptive, ref_norm = detect_tissue_and_holes_adaptive(ref)
    
    # Method 2: Intensity-based detection
    print("\n--- Method 2: Intensity-Based Detection ---")
    holes_intensity = detect_holes_by_intensity(ref, tissue_adaptive)
    
    # Combine methods (union)
    holes_combined = holes_adaptive | holes_intensity
    labeled_combined, n_combined = ndimage.label(holes_combined)
    
    print(f"\n[combined] Total holes from both methods: {n_combined}")
    
    # Calculate coverage
    coverage = 100 * holes_combined.sum() / (tissue_adaptive.sum() + 1e-6)
    print(f"[combined] Coverage: {coverage:.1f}%")
    
    # Save results
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    final_mask = (tissue_adaptive & ~holes_combined) * 255
    tifffile.imwrite(Path(OUTPUT_DIR) / "advanced_tissue_mask.tif", final_mask.astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "advanced_hole_mask.tif", (holes_combined * 255).astype(np.uint8))
    
    # Visualization
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.patch.set_facecolor("#1a1a2e")
    
    p2, p98 = np.percentile(ref, (2, 98))
    
    axes[0, 0].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 0].set_title("Reference Image", color='white')
    axes[0, 0].axis('off')
    
    axes[0, 1].imshow(ref_norm, cmap='gray')
    axes[0, 1].set_title("Normalized for Adaptive", color='white')
    axes[0, 1].axis('off')
    
    axes[0, 2].imshow(tissue_adaptive, cmap='Blues')
    axes[0, 2].set_title("Detected Tissue (Adaptive)", color='white')
    axes[0, 2].axis('off')
    
    axes[1, 0].imshow(holes_adaptive, cmap='Reds')
    labeled_a, n_a = ndimage.label(holes_adaptive)
    axes[1, 0].set_title(f"Holes (Adaptive): {n_a}", color='white')
    axes[1, 0].axis('off')
    
    axes[1, 1].imshow(holes_intensity, cmap='Oranges')
    labeled_i, n_i = ndimage.label(holes_intensity)
    axes[1, 1].set_title(f"Holes (Intensity): {n_i}", color='white')
    axes[1, 1].axis('off')
    
    axes[1, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    overlay[holes_combined] = [1, 0.2, 0.2, 0.6]
    axes[1, 2].imshow(overlay)
    axes[1, 2].set_title(f"Combined Holes Overlay: {n_combined}", color='white')
    axes[1, 2].axis('off')
    
    for ax in axes.flat:
        for spine in ax.spines.values():
            spine.set_visible(False)
    
    plt.suptitle(f"Advanced Hole Detection | Coverage: {coverage:.1f}% | Holes: {n_combined}",
                 color='white', fontsize=13, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(Path(OUTPUT_DIR) / "advanced_detection_result.png", 
                dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.show()
    
    print(f"\n[done] Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
