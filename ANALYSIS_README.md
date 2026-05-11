# Fibrosis Mask Analysis - Optimized Parameters

## Summary
סקריפט זה מאתר חורים (fibrosis) בתוך רקמה שנתפסה בווידאו מ-macroscope.

## Current Optimal Parameters
```
K_MAD = 1.0              # Sensitivity (lower = more holes detected)
RING_WIDTH = 8           # Radial resolution in pixels
MIN_HOLE_SIZE = 10       # Minimum hole area in pixels
MEDIAN_FILTER_RADIUS = 3 # Pre-processing blur
CLOSING_RADIUS = 20      # Tissue boundary cleanup
```

## Detection Results
- **Holes Found**: 9 regions
- **Total Hole Area**: ~1197 pixels
- **Coverage**: ~19% of tissue area
- **Method**: Radial-distance thresholding with MAD (Median Absolute Deviation)

## How It Works

### 1. Preprocessing
- Load TIFF video stack (2701 frames)
- Create reference image via median projection
- Apply median filter to reduce noise

### 2. Outer Tissue Mask
- Use Otsu thresholding to find tissue boundary
- Morphological closing to connect broken edges
- Fill internal holes to get solid tissue mask

### 3. Centroid Detection
- Find geometric center of tissue
- Used as reference point for radial analysis

### 4. Radial Ring Analysis
- Divide tissue into concentric rings (width = 8 pixels)
- For each ring, compute statistics:
  - Median intensity
  - MAD (robust standard deviation)
  - Threshold = Median - K_MAD × MAD

### 5. Hole Detection
- Pixels below ring threshold are flagged as holes
- Filter by area (10-5000 pixels)
- Remove noise with morphological opening

## Output Files
- `final_tissue_mask.tif` - Binary mask of tissue (white) vs holes/background (black)
- `radial_hole_mask.tif` - Binary mask of detected holes
- `overlay_QC.png` - Quality control visualization with 8 subplots
- `reference_median.tif` - Median projection reference image

## Adjustment Tips

### To Find More/Larger Holes
- **Decrease K_MAD** (e.g., 0.8): Makes thresholding more sensitive
- **Decrease RING_WIDTH** (e.g., 5-6): Improves spatial resolution  
- **Decrease MIN_HOLE_SIZE** (e.g., 5): Keeps tiny holes

### To Find Fewer/Smaller Holes
- **Increase K_MAD** (e.g., 1.5-2.0): Makes thresholding stricter
- **Increase RING_WIDTH** (e.g., 12-15): Reduces false positives
- **Increase MIN_HOLE_SIZE** (e.g., 50-100): Filters noise

## Pattern Information
- **Pattern**: 9mm_Compact 2 circ
- **Expected Coverage**: 30.4% (from pattern name)
- **Target**: ~19% outer circle (from pattern name)
- **Current Detection**: ~19% ✓

## Using the Mask

### In Python
```python
import tifffile
mask = tifffile.imread("final_tissue_mask.tif")
tissue = mask > 0  # Boolean array
```

### In ImageJ/FIJI
- Open `final_tissue_mask.tif`
- Use as ROI for electrical signal analysis
- White = tissue (analyze signals here)
- Black = holes/background (ignore)

## References
- OpenCV: Adaptive thresholding and morphology
- scikit-image: Ring statistics and hole detection
- scipy: Connected component analysis
