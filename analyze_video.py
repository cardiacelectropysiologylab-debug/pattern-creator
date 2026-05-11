"""
Analyze Video Content
=======================
Check what's actually in the video data
"""

import numpy as np
import tifffile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt


INPUT_PATH = r"C:\Users\Lior\Desktop\New folder\02-1hz pacing_short.tif"

print("[load] Loading video...")
stack = tifffile.imread(INPUT_PATH)
print(f"Shape: {stack.shape}, dtype: {stack.dtype}")

# Create reference
ref = np.median(stack.astype(np.float32), axis=0)

print(f"Reference: min={ref.min():.0f}, max={ref.max():.0f}, mean={ref.mean():.0f}, std={ref.std():.0f}")

# Normalize
ref_norm = (ref - ref.min()) / (ref.max() - ref.min())

# Histogram analysis
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# Image with colorbar
ax = axes[0, 0]
im = ax.imshow(ref, cmap='jet')
ax.set_title("Reference Image (Raw)")
plt.colorbar(im, ax=ax)

# Normalized
ax = axes[0, 1]
im = ax.imshow(ref_norm, cmap='jet')
ax.set_title("Normalized [0, 1]")
plt.colorbar(im, ax=ax)

# Histogram
ax = axes[1, 0]
ax.hist(ref.flatten(), bins=100, color='blue', alpha=0.7)
ax.set_title("Intensity Histogram")
ax.set_xlabel("Intensity")
ax.set_ylabel("Count")

# Percentiles
ax = axes[1, 1]
percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
values = [np.percentile(ref, p) for p in percentiles]
ax.bar(range(len(percentiles)), values, color='orange', alpha=0.7)
ax.set_xticks(range(len(percentiles)))
ax.set_xticklabels([f'{p}%' for p in percentiles], rotation=45)
ax.set_title("Intensity Percentiles")
ax.set_ylabel("Value")

plt.tight_layout()
plt.savefig(r"C:\Users\Lior\Desktop\New folder\video_analysis.png", dpi=150, bbox_inches='tight')
plt.show()

print("[saved] Visualization saved")

# Check for very dark regions
dark_threshold = np.percentile(ref, 10)
dark_pixels = (ref < dark_threshold).sum()
print(f"\nPixels below 10th percentile ({dark_threshold:.0f}): {dark_pixels} ({100*dark_pixels/ref.size:.1f}%)")

dark_threshold_5 = np.percentile(ref, 5)
dark_pixels_5 = (ref < dark_threshold_5).sum()
print(f"Pixels below 5th percentile ({dark_threshold_5:.0f}): {dark_pixels_5} ({100*dark_pixels_5/ref.size:.1f}%)")
