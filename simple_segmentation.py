"""
Simple Binary Segmentation
===========================
Basic approach: White = Tissue, Black = Holes
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import ndimage
import cv2


def main():
    print("=" * 60)
    print("  Simple Binary Segmentation")
    print("=" * 60)
    
    INPUT_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
    OUTPUT_DIR = r"C:\Users\Lior\Desktop\New folder\result"
    
    # Load
    print("[load] Loading video...")
    stack = tifffile.imread(INPUT_PATH)
    
    if stack.ndim == 3:
        ref = np.median(stack.astype(np.float32), axis=0)
    else:
        ref = stack.astype(np.float32)
    
    print(f"Reference: shape={ref.shape}, min={ref.min():.0f}, max={ref.max():.0f}, mean={ref.mean():.0f}")
    
    # Simple binary thresholding using multiple methods
    fig, axes = plt.subplots(3, 4, figsize=(16, 12))
    fig.patch.set_facecolor("#1a1a2e")
    
    p2, p98 = np.percentile(ref, (2, 98))
    
    # Show original
    axes[0, 0].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 0].set_title("Original", color='white')
    axes[0, 0].axis('off')
    
    # Method 1: Otsu threshold
    from skimage import filters
    otsu_thresh = filters.threshold_otsu(ref)
    otsu_mask = ref > otsu_thresh
    axes[0, 1].imshow(otsu_mask, cmap='gray')
    axes[0, 1].set_title(f"Otsu (thresh={otsu_thresh:.0f})", color='white')
    axes[0, 1].axis('off')
    
    # Method 2: Percentile-based (middle 40%)
    p_low = np.percentile(ref, 30)
    p_high = np.percentile(ref, 70)
    percentile_mask = (ref > p_low) & (ref < p_high)
    axes[0, 2].imshow(percentile_mask, cmap='gray')
    axes[0, 2].set_title(f"Percentile [30-70%]", color='white')
    axes[0, 2].axis('off')
    
    # Method 3: Simple mean threshold
    mean_thresh = ref.mean()
    simple_mask = ref > mean_thresh
    axes[0, 3].imshow(simple_mask, cmap='gray')
    axes[0, 3].set_title(f"Mean (thresh={mean_thresh:.0f})", color='white')
    axes[0, 3].axis('off')
    
    # Method 4: Darker version of Otsu
    dark_otsu = otsu_thresh * 0.7  # 70% of Otsu
    dark_mask = ref > dark_otsu
    axes[1, 0].imshow(dark_mask, cmap='gray')
    axes[1, 0].set_title(f"70% Otsu (thresh={dark_otsu:.0f})", color='white')
    axes[1, 0].axis('off')
    
    # Method 5: Bimodal - find gap in histogram
    hist, bins = np.histogram(ref, bins=100)
    # Find biggest valley (gap)
    diff = np.diff(hist)
    valley_idx = np.argmax(diff)  # Biggest drop
    bimodal_thresh = bins[valley_idx]
    bimodal_mask = ref > bimodal_thresh
    axes[1, 1].imshow(bimodal_mask, cmap='gray')
    axes[1, 1].set_title(f"Bimodal (thresh={bimodal_thresh:.0f})", color='white')
    axes[1, 1].axis('off')
    
    # Method 6: Triangle threshold
    triangle_thresh = filters.threshold_triangle(ref)
    triangle_mask = ref > triangle_thresh
    axes[1, 2].imshow(triangle_mask, cmap='gray')
    axes[1, 2].set_title(f"Triangle (thresh={triangle_thresh:.0f})", color='white')
    axes[1, 2].axis('off')
    
    # Method 7: Yen threshold
    yen_thresh = filters.threshold_yen(ref)
    yen_mask = ref > yen_thresh
    axes[1, 3].imshow(yen_mask, cmap='gray')
    axes[1, 3].set_title(f"Yen (thresh={yen_thresh:.0f})", color='white')
    axes[1, 3].axis('off')
    
    # Method 8: Li threshold
    li_thresh = filters.threshold_li(ref)
    li_mask = ref > li_thresh
    axes[2, 0].imshow(li_mask, cmap='gray')
    axes[2, 0].set_title(f"Li (thresh={li_thresh:.0f})", color='white')
    axes[2, 0].axis('off')
    
    # Best candidate: use Otsu as tissue
    tissue = otsu_mask
    tissue = ndimage.binary_fill_holes(tissue)
    
    # Find holes: regions inside tissue that are NOT tissue
    holes = tissue & ~otsu_mask
    
    # Filter holes by size
    labeled, n_holes = ndimage.label(holes)
    holes_filtered = np.zeros_like(holes)
    for hole_id in range(1, n_holes + 1):
        hole_mask = (labeled == hole_id)
        area = hole_mask.sum()
        if 5 <= area <= 5000:
            holes_filtered |= hole_mask
    
    axes[2, 1].imshow(holes_filtered, cmap='Reds')
    axes[2, 1].set_title(f"Holes Found: {ndimage.label(holes_filtered)[1]}", color='white')
    axes[2, 1].axis('off')
    
    # Overlay
    axes[2, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    overlay[holes_filtered] = [1, 0.2, 0.2, 0.7]
    axes[2, 2].imshow(overlay)
    coverage = 100 * holes_filtered.sum() / (tissue.sum() + 1e-6)
    axes[2, 2].set_title(f"Holes Overlay ({coverage:.1f}%)", color='white')
    axes[2, 2].axis('off')
    
    # Final mask
    final_mask = (tissue & ~holes_filtered) * 255
    axes[2, 3].imshow(final_mask, cmap='gray')
    axes[2, 3].set_title("Final Tissue Mask", color='white')
    axes[2, 3].axis('off')
    
    for ax in axes.flat:
        for spine in ax.spines.values():
            spine.set_visible(False)
    
    plt.suptitle("Comparing Segmentation Methods", color='white', fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    plt.savefig(Path(OUTPUT_DIR) / "segmentation_methods_comparison.png", 
                dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.show()
    
    # Save best result
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(Path(OUTPUT_DIR) / "simple_tissue_mask.tif", final_mask.astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "simple_hole_mask.tif", (holes_filtered * 255).astype(np.uint8))
    
    labeled_final, n_final = ndimage.label(holes_filtered)
    print(f"\n[result] Holes found: {n_final}")
    print(f"[result] Coverage: {coverage:.1f}%")
    print(f"[result] Saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
