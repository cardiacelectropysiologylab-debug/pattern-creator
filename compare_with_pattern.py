"""
Compare Current Mask with Reference Pattern
==============================================
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from pathlib import Path
import fitz
from PIL import Image
import cv2


def extract_pdf_pattern(pdf_path: str) -> np.ndarray:
    """Extract pattern from PDF at high resolution."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # High zoom for detail
    mat = fitz.Matrix(10, 10)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    img_pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = np.array(img_pil)
    
    img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    doc.close()
    
    return img_gray


def load_current_mask(tif_path: str) -> np.ndarray:
    """Load current detected mask."""
    return tifffile.imread(tif_path)


# Paths
PATTERN_PDF = r"C:\Users\Lior\Desktop\Shir\Fibrosis\Patterns\Pattern creator\9mm\9mm_Compact 2 circ_30.4% coverage_19% outer circle.pdf"
CURRENT_MASK = r"C:\Users\Lior\Desktop\New folder\result\final_tissue_mask.tif"
CURRENT_HOLES = r"C:\Users\Lior\Desktop\New folder\result\radial_hole_mask.tif"

# Load
print("[extract] Extracting pattern from PDF...")
pattern = extract_pdf_pattern(PATTERN_PDF)

print("[load] Loading current mask...")
mask = load_current_mask(CURRENT_MASK)
holes = load_current_mask(CURRENT_HOLES)

print(f"Pattern shape: {pattern.shape}")
print(f"Current mask shape: {mask.shape}")

# Resize pattern to match mask for comparison
if pattern.shape != mask.shape:
    pattern_resized = cv2.resize(pattern, (mask.shape[1], mask.shape[0]))
else:
    pattern_resized = pattern

# Display
fig, axes = plt.subplots(2, 3, figsize=(16, 10))
fig.patch.set_facecolor("#1a1a2e")

# Pattern
axes[0, 0].imshow(pattern, cmap='gray')
axes[0, 0].set_title("Reference Pattern (PDF)", color='white', fontsize=12)
axes[0, 0].axis('off')

# Pattern thresholded (to see structure)
_, pattern_thresh = cv2.threshold(pattern, 127, 255, cv2.THRESH_BINARY)
axes[0, 1].imshow(pattern_thresh, cmap='gray')
axes[0, 1].set_title("Pattern Thresholded (Black=Holes)", color='white', fontsize=12)
axes[0, 1].axis('off')

# Pattern inverted
axes[0, 2].imshow(255 - pattern, cmap='gray')
axes[0, 2].set_title("Pattern Inverted", color='white', fontsize=12)
axes[0, 2].axis('off')

# Current mask
axes[1, 0].imshow(mask, cmap='gray')
axes[1, 0].set_title("Current Detected Mask", color='white', fontsize=12)
axes[1, 0].axis('off')

# Current holes
axes[1, 1].imshow(holes, cmap='gray')
axes[1, 1].set_title("Current Detected Holes", color='white', fontsize=12)
axes[1, 1].axis('off')

# Difference
diff = (mask.astype(float) - cv2.resize(pattern_resized, (mask.shape[1], mask.shape[0])).astype(float))
axes[1, 2].imshow(diff, cmap='RdBu', vmin=-128, vmax=128)
axes[1, 2].set_title("Difference (Red=Missing, Blue=Extra)", color='white', fontsize=12)
axes[1, 2].axis('off')

for ax in axes.flat:
    for spine in ax.spines.values():
        spine.set_visible(False)

plt.suptitle("Pattern Comparison: Reference vs Current Detection", 
             color='white', fontsize=14, fontweight='bold', y=0.98)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig(r"C:\Users\Lior\Desktop\New folder\pattern_comparison.png", 
            dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.show()

print("[done] Comparison saved to pattern_comparison.png")
