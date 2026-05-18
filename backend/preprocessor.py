"""
preprocessor.py — Step 2: image pre-processing before CNN.

1. Register HEIC/AVIF support via pillow-heif (if installed).
2. Detect and crop solid-colour borders of ANY colour (not just black).
3. Centre-crop to 80% of height to remove screenshot chrome / watermarks.
4. Resize to 224×224 and return as a float32 numpy array.
"""

import numpy as np
from PIL import Image

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    _HEIC_SUPPORTED = True
except ImportError:
    _HEIC_SUPPORTED = False

TARGET_SIZE = (224, 224)
BORDER_VARIANCE_THRESHOLD = 8.0   # pixel variance below this = solid-colour border
CENTRE_CROP_RATIO = 0.80           # keep central 80% vertically


def _crop_solid_borders(img: Image.Image) -> Image.Image:
    """
    Remove solid-colour borders from all four sides.
    Works for any border colour (black, white, grey, coloured).
    A row/column is considered a border if its per-channel variance is below threshold.
    """
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    h, w, _ = arr.shape

    def row_is_border(r):
        return float(arr[r].var()) < BORDER_VARIANCE_THRESHOLD

    def col_is_border(c):
        return float(arr[:, c, :].var()) < BORDER_VARIANCE_THRESHOLD

    top = 0
    while top < h - 1 and row_is_border(top):
        top += 1

    bottom = h - 1
    while bottom > top and row_is_border(bottom):
        bottom -= 1

    left = 0
    while left < w - 1 and col_is_border(left):
        left += 1

    right = w - 1
    while right > left and col_is_border(right):
        right -= 1

    if top >= bottom or left >= right:
        return img

    return img.crop((left, top, right + 1, bottom + 1))


def _centre_crop(img: Image.Image) -> Image.Image:
    """
    Crop the central 80% of the image height.
    Removes browser toolbars, notification banners, and bottom bars
    commonly added when screenshotting content.
    """
    w, h = img.size
    margin = int(h * (1 - CENTRE_CROP_RATIO) / 2)
    if margin < 1:
        return img
    return img.crop((0, margin, w, h - margin))


def load_and_preprocess(path: str) -> np.ndarray | None:
    """
    Load image at path, apply preprocessing pipeline, return (224,224,3) float32 array
    with pixel values in [0, 1]. Returns None on any read error.
    """
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None

    img = _crop_solid_borders(img)
    img = _centre_crop(img)
    img = img.resize(TARGET_SIZE, Image.LANCZOS)

    arr = np.array(img, dtype=np.float32) / 255.0
    return arr


def load_for_orb(path: str) -> np.ndarray | None:
    """
    Load image for ORB keypoint matching.
    Returns a grayscale uint8 numpy array after border-crop and centre-crop.
    Keeps native resolution (don't resize — ORB needs real pixel detail).
    """
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None

    img = _crop_solid_borders(img)
    img = _centre_crop(img)

    gray = np.array(img.convert("L"), dtype=np.uint8)
    return gray
