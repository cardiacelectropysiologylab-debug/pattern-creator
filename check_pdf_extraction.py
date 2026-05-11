import fitz
from PIL import Image
import numpy as np
import cv2
import matplotlib.pyplot as plt

pdf_path = r"C:\Users\Lior\Desktop\Shir\Fibrosis\Patterns\Pattern creator\9mm\9mm_Compact 2 circ_30.4% coverage_19% outer circle.pdf"

doc = fitz.open(pdf_path)
page = doc[0]

# High zoom
mat = fitz.Matrix(6, 6)
pix = page.get_pixmap(matrix=mat, alpha=False)

img_pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
img = np.array(img_pil)

img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

print(f"Shape: {img_gray.shape}")
print(f"Min: {img_gray.min()}, Max: {img_gray.max()}, Mean: {img_gray.mean():.0f}")
print(f"Unique values: {len(np.unique(img_gray))}")

# Display
plt.figure(figsize=(12, 6))
plt.subplot(1, 2, 1)
plt.imshow(img)
plt.title("RGB from PDF")
plt.axis('off')

plt.subplot(1, 2, 2)
plt.imshow(img_gray, cmap='gray')
plt.title("Grayscale")
plt.axis('off')

plt.tight_layout()
plt.savefig(r"C:\Users\Lior\Desktop\New folder\pattern_extracted.png", dpi=150, bbox_inches='tight')
print("Saved to pattern_extracted.png")
plt.show()

doc.close()
