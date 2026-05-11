"""
Fibrosis Pattern Analyzer & Mask Optimizer
============================================
Extracts pattern from PDF, analyzes hole characteristics, and optimizes
video segmentation parameters to match the known pattern.

Usage:
    python analyze_pattern_and_optimize.py
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import ndimage
from skimage import filters, morphology, measure, exposure
import cv2
import fitz  # PyMuPDF
import warnings
warnings.filterwarnings('ignore')


# ============================================================
# PATHS
# ============================================================

VIDEO_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"
PATTERN_PDF = r"C:\Users\Lior\Desktop\Shir\Fibrosis\Patterns\Pattern creator\9mm\9mm_Compact 2 circ_30.4% coverage_19% outer circle.pdf"
OUTPUT_DIR = r"C:\Users\Lior\Desktop\New folder\result"


# ============================================================
# EXTRACT AND ANALYZE PATTERN FROM PDF
# ============================================================

def extract_pattern_from_pdf(pdf_path: str) -> np.ndarray:
    """Extract first page image from PDF using PyMuPDF."""
    print(f"[pattern] Extracting from: {pdf_path}")
    
    # Open PDF
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # Render page to image with higher zoom
    mat = fitz.Matrix(6, 6)  # 6x zoom for better resolution
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    # Convert to image in PIL then to numpy
    from PIL import Image
    
    img_pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = np.array(img_pil)
    
    # Convert to grayscale
    img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    doc.close()
    
    print(f"[pattern] Extracted shape: {img_gray.shape}")
    return img_gray


def analyze_pattern_holes(pattern_img: np.ndarray) -> dict:
    """Analyze hole characteristics from pattern image."""
    print("[pattern] Analyzing hole distribution...")
    
    # Threshold using Otsu to separate black (holes) from white (tissue)
    threshold = cv2.threshold(pattern_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]
    print(f"[pattern] Otsu threshold: {threshold}")
    
    binary = pattern_img > threshold
    holes = ~binary  # Holes are black, so invert
    
    # Get outer circle (tissue region) - find largest connected component
    labeled, n_comps = ndimage.label(~holes)
    if n_comps > 0:
        sizes = ndimage.sum(~holes, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        tissue_mask = (labeled == largest)
    else:
        tissue_mask = ~holes
    
    holes_in_tissue = holes & tissue_mask
    
    # Analyze holes
    labeled_holes, n_holes = ndimage.label(holes_in_tissue)
    
    hole_sizes = []
    hole_positions = []
    
    for hole_id in range(1, n_holes + 1):
        hole_mask = (labeled_holes == hole_id)
        size = hole_mask.sum()
        if size > 5:  # Filter very small noise
            hole_sizes.append(size)
            y, x = ndimage.center_of_mass(hole_mask)
            hole_positions.append((x, y))
    
    hole_sizes = np.array(hole_sizes)
    hole_coverage = 100 * holes_in_tissue.sum() / (tissue_mask.sum() + 1e-6)
    
    stats = {
        'n_holes': len(hole_sizes),
        'hole_sizes_mean': np.mean(hole_sizes) if len(hole_sizes) > 0 else 0,
        'hole_sizes_std': np.std(hole_sizes) if len(hole_sizes) > 0 else 0,
        'hole_sizes_min': np.min(hole_sizes) if len(hole_sizes) > 0 else 0,
        'hole_sizes_max': np.max(hole_sizes) if len(hole_sizes) > 0 else 0,
        'coverage_percent': hole_coverage,
        'tissue_mask': tissue_mask,
        'holes_mask': holes_in_tissue,
        'hole_positions': hole_positions,
        'binary': binary
    }
    
    return stats


# ============================================================
# VIDEO PROCESSING
# ============================================================

def load_video(path: str) -> np.ndarray:
    """Load TIFF video."""
    print(f"[video] Loading: {path}")
    img = tifffile.imread(path)
    print(f"[video] Shape: {img.shape}, dtype: {img.dtype}")
    return img


def make_reference(stack: np.ndarray) -> np.ndarray:
    """Create reference from stack."""
    if stack.ndim == 3:
        ref = np.median(stack.astype(np.float32), axis=0)
    else:
        ref = stack.astype(np.float32)
    return ref


def process_video_for_mask(ref: np.ndarray, 
                           ring_width: int, 
                           k_mad: float,
                           min_hole_size: int,
                           median_filter_radius: int,
                           closing_radius: int) -> tuple:
    """Full pipeline for video mask extraction."""
    
    # Preprocess
    img = ref.copy()
    if median_filter_radius > 0:
        img = ndimage.median_filter(img, size=median_filter_radius * 2 + 1)
    
    img_min, img_max = img.min(), img.max()
    if img_max > img_min:
        img_norm = (img - img_min) / (img_max - img_min)
    else:
        img_norm = np.zeros_like(img, dtype=np.float32)
    
    # Outer mask
    threshold = filters.threshold_otsu(img_norm)
    binary = img_norm > threshold
    
    if closing_radius > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                           (closing_radius * 2 + 1, closing_radius * 2 + 1))
        binary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0
    
    outer_mask = ndimage.binary_fill_holes(binary)
    
    labeled, n_comps = ndimage.label(outer_mask)
    if n_comps > 0:
        sizes = ndimage.sum(outer_mask, labeled, range(n_comps + 1))
        largest = np.argmax(sizes)
        outer_mask = (labeled == largest)
    
    # Centroid
    y, x = ndimage.center_of_mass(outer_mask)
    x0, y0 = float(x), float(y)
    
    # Distance map
    yy, xx = np.ogrid[:ref.shape[0], :ref.shape[1]]
    dist_map = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)
    
    # Ring-based thresholding
    max_dist = dist_map[outer_mask].max()
    n_rings = int(np.ceil(max_dist / ring_width))
    
    threshold_img = np.zeros_like(ref)
    
    for ring_idx in range(n_rings):
        r_lo = ring_idx * ring_width
        r_hi = (ring_idx + 1) * ring_width
        
        ring_mask = (dist_map >= r_lo) & (dist_map < r_hi) & outer_mask
        
        if ring_mask.sum() < 5:
            continue
        
        ring_vals = ref[ring_mask]
        median_val = np.median(ring_vals)
        mad_val = np.median(np.abs(ring_vals - median_val))
        
        threshold = median_val - k_mad * mad_val * 1.4826
        threshold_img[ring_mask] = threshold
    
    # Detect holes
    hole_mask = (ref < threshold_img) & outer_mask
    hole_mask = morphology.remove_small_objects(hole_mask, min_size=max(1, min_hole_size - 1))
    
    return outer_mask, hole_mask, (x0, y0)


def compute_score(detected_holes: np.ndarray, 
                  outer_mask: np.ndarray,
                  target_coverage: float,
                  target_n_holes: int) -> float:
    """Score how well detected holes match the target pattern."""
    
    detected_coverage = 100 * detected_holes.sum() / (outer_mask.sum() + 1e-6)
    
    # Connectivity analysis
    labeled_holes, n_detected_holes = ndimage.label(detected_holes)
    
    # Score: minimize difference from target
    coverage_error = abs(detected_coverage - target_coverage)
    hole_count_error = abs(n_detected_holes - target_n_holes)
    
    # Weighted score (lower is better)
    score = coverage_error + 0.1 * hole_count_error
    
    return score, {
        'coverage': detected_coverage,
        'n_holes': n_detected_holes,
        'coverage_error': coverage_error,
        'hole_count_error': hole_count_error,
        'total_score': score
    }


# ============================================================
# OPTIMIZATION
# ============================================================

def optimize_parameters(ref: np.ndarray, pattern_stats: dict) -> dict:
    """Find optimal parameters by testing different combinations."""
    
    print("\n[optimize] Starting parameter optimization...")
    print(f"[optimize] Target: {pattern_stats['coverage_percent']:.1f}% coverage, "
          f"{pattern_stats['n_holes']} holes")
    
    best_params = None
    best_score = float('inf')
    results = []
    
    # Parameter ranges to test
    ring_widths = [5, 8, 10, 12, 15]
    k_mads = [0.8, 1.0, 1.2, 1.5, 1.8, 2.0]
    min_sizes = [20, 50, 100, 150]
    
    total_tests = len(ring_widths) * len(k_mads) * len(min_sizes)
    test_count = 0
    
    for rw in ring_widths:
        for km in k_mads:
            for ms in min_sizes:
                test_count += 1
                if test_count % 10 == 0:
                    print(f"  Testing: {test_count}/{total_tests}...")
                
                outer_mask, hole_mask, _ = process_video_for_mask(
                    ref, rw, km, ms, 3, 20
                )
                
                score, score_dict = compute_score(
                    hole_mask, outer_mask,
                    pattern_stats['coverage_percent'],
                    pattern_stats['n_holes']
                )
                
                results.append({
                    'params': {'ring_width': rw, 'k_mad': km, 'min_hole_size': ms},
                    'score': score,
                    'details': score_dict
                })
                
                if score < best_score:
                    best_score = score
                    best_params = {'ring_width': rw, 'k_mad': km, 'min_hole_size': ms}
    
    # Sort by score
    results = sorted(results, key=lambda x: x['score'])
    
    print(f"\n[optimize] Best parameters found (score: {best_score:.2f}):")
    print(f"  Ring Width: {best_params['ring_width']}")
    print(f"  K_MAD: {best_params['k_mad']}")
    print(f"  Min Hole Size: {best_params['min_hole_size']}")
    
    print(f"\n[optimize] Top 5 results:")
    for i, res in enumerate(results[:5]):
        print(f"  {i+1}. Score: {res['score']:.2f} | "
              f"RW={res['params']['ring_width']}, "
              f"K={res['params']['k_mad']}, "
              f"MS={res['params']['min_hole_size']} | "
              f"Coverage: {res['details']['coverage']:.1f}%, "
              f"Holes: {res['details']['n_holes']}")
    
    return best_params, results


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  Fibrosis Pattern Analyzer & Optimizer")
    print("=" * 60)
    
    # Step 1: Extract and analyze pattern
    pattern_img = extract_pattern_from_pdf(PATTERN_PDF)
    pattern_stats = analyze_pattern_holes(pattern_img)
    
    print(f"[pattern] Statistics:")
    print(f"  Number of holes: {pattern_stats['n_holes']}")
    print(f"  Hole size (mean ± std): {pattern_stats['hole_sizes_mean']:.0f} ± {pattern_stats['hole_sizes_std']:.0f} px")
    print(f"  Coverage: {pattern_stats['coverage_percent']:.1f}%")
    
    # Step 2: Load video
    stack = load_video(VIDEO_PATH)
    ref = make_reference(stack)
    
    # Step 3: Optimize parameters
    best_params, results = optimize_parameters(ref, pattern_stats)
    
    # Step 4: Generate final result with best parameters
    print(f"\n[final] Generating final mask...")
    outer_mask, hole_mask, (x0, y0) = process_video_for_mask(
        ref,
        best_params['ring_width'],
        best_params['k_mad'],
        best_params['min_hole_size'],
        3, 20
    )
    
    # Save results
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    final_mask = (outer_mask & ~hole_mask) * 255
    tifffile.imwrite(Path(OUTPUT_DIR) / "optimized_tissue_mask.tif", final_mask.astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "optimized_hole_mask.tif", (hole_mask * 255).astype(np.uint8))
    tifffile.imwrite(Path(OUTPUT_DIR) / "optimized_reference.tif", ref.astype(np.float32))
    
    # Visualization
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.patch.set_facecolor("#1a1a2e")
    
    p2, p98 = np.percentile(ref, (2, 98))
    
    # Original pattern
    axes[0, 0].imshow(pattern_img, cmap='gray')
    axes[0, 0].set_title("Target Pattern (PDF)", color='white', fontsize=11)
    axes[0, 0].axis('off')
    
    # Pattern holes
    axes[0, 1].imshow(pattern_stats['holes_mask'], cmap='Reds')
    axes[0, 1].set_title(f"Pattern Holes ({pattern_stats['n_holes']} @ {pattern_stats['coverage_percent']:.1f}%)", 
                         color='white', fontsize=11)
    axes[0, 1].axis('off')
    
    # Reference image
    axes[0, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    axes[0, 2].plot(x0, y0, 'r+', markersize=15, markeredgewidth=2)
    axes[0, 2].set_title("Video Reference", color='white', fontsize=11)
    axes[0, 2].axis('off')
    
    # Outer mask
    axes[1, 0].imshow(outer_mask, cmap='Blues')
    axes[1, 0].set_title("Detected Tissue", color='white', fontsize=11)
    axes[1, 0].axis('off')
    
    # Detected holes
    labeled_holes, n_holes = ndimage.label(hole_mask)
    axes[1, 1].imshow(hole_mask, cmap='Reds')
    hole_cov = 100 * hole_mask.sum() / (outer_mask.sum() + 1e-6)
    axes[1, 1].set_title(f"Detected Holes ({n_holes} @ {hole_cov:.1f}%)", 
                         color='white', fontsize=11)
    axes[1, 1].axis('off')
    
    # Overlay
    axes[1, 2].imshow(ref, cmap='gray', vmin=p2, vmax=p98)
    overlay = np.zeros((*ref.shape, 4), dtype=np.float32)
    overlay[hole_mask] = [1, 0.2, 0.2, 0.6]
    axes[1, 2].imshow(overlay)
    axes[1, 2].set_title("Holes Overlaid", color='white', fontsize=11)
    axes[1, 2].axis('off')
    
    for ax in axes.flat:
        for spine in ax.spines.values():
            spine.set_visible(False)
    
    plt.suptitle(f"Pattern-Optimized Segmentation\n"
                 f"RW={best_params['ring_width']}, K_MAD={best_params['k_mad']}, "
                 f"MinSize={best_params['min_hole_size']}",
                 color='white', fontsize=13, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(Path(OUTPUT_DIR) / "pattern_optimized_result.png", 
                dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.show()
    
    print(f"\n[done] Results saved to: {OUTPUT_DIR}")
    print(f"  - optimized_tissue_mask.tif")
    print(f"  - optimized_hole_mask.tif")
    print(f"  - pattern_optimized_result.png")


if __name__ == "__main__":
    main()
