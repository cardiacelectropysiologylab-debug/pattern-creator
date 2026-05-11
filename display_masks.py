"""
Display the Generated Masks
"""

import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np

# Load masks
tissue_mask = tifffile.imread(r"C:\Users\Lior\Desktop\New folder\result\optimal_tissue_mask.tif")
hole_mask = tifffile.imread(r"C:\Users\Lior\Desktop\New folder\result\optimal_hole_mask.tif")
boundary = tifffile.imread(r"C:\Users\Lior\Desktop\New folder\result\optimal_tissue_boundary.tif")

# Create figure
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.patch.set_facecolor("white")

# Tissue mask
axes[0].imshow(tissue_mask, cmap='gray')
axes[0].set_title("Final Tissue Mask\n(255=tissue, 0=holes)", fontsize=12, fontweight='bold')
axes[0].axis('off')

# Hole mask
axes[1].imshow(hole_mask, cmap='Reds')
axes[1].set_title("Detected Holes Only", fontsize=12, fontweight='bold')
axes[1].axis('off')

# Boundary
axes[2].imshow(boundary, cmap='Blues')
axes[2].set_title("Tissue Boundary", fontsize=12, fontweight='bold')
axes[2].axis('off')

plt.tight_layout()
plt.savefig(r"C:\Users\Lior\Desktop\New folder\display_masks.png", dpi=150, bbox_inches='tight')
plt.show()

print("✓ Displayed masks!")
print(f"Tissue mask shape: {tissue_mask.shape}")
print(f"Tissue area: {(tissue_mask > 0).sum()} pixels")
print(f"Holes area: {(hole_mask > 0).sum()} pixels")
