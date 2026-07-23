"""
All hash-mode logic: border-crop, rotation, perceptual hashing, comparison.
Pure functions — no GUI code, no file-system side effects beyond reading images.
"""

from PIL import Image
import imagehash
import numpy as np

# Fraction of image dimension a border can occupy before we stop trusting it
MAX_BORDER_FRACTION = 0.15
# How "flat" (low variance) a row/column must be to count as a border strip
FLATNESS_STD_THRESHOLD = 8.0
# How close to pure black/white the flat strip must be
DARK_THRESHOLD = 30
LIGHT_THRESHOLD = 225


def _row_is_border(row: np.ndarray) -> bool:
    """A row counts as a border strip if it's low-variance AND close to black or white."""
    mean = row.mean()
    std = row.std()
    if std > FLATNESS_STD_THRESHOLD:
        return False
    return mean <= DARK_THRESHOLD or mean >= LIGHT_THRESHOLD


def detect_and_crop_border(image: Image.Image) -> Image.Image:
    """
    Detects flat, near-black/white, sharp-edged borders that make up a small
    fraction of the image (screenshot artifacts) and crops them off.
    Leaves normal photos untouched — only triggers on genuine screenshot-style
    borders, not natural flat regions like sky or walls.
    """
    gray = np.array(image.convert("L"))
    h, w = gray.shape

    max_border_h = int(h * MAX_BORDER_FRACTION)
    max_border_w = int(w * MAX_BORDER_FRACTION)

    top = 0
    while top < max_border_h and _row_is_border(gray[top, :]):
        top += 1

    bottom = 0
    while bottom < max_border_h and _row_is_border(gray[h - 1 - bottom, :]):
        bottom += 1

    left = 0
    while left < max_border_w and _row_is_border(gray[:, left]):
        left += 1

    right = 0
    while right < max_border_w and _row_is_border(gray[:, w - 1 - right]):
        right += 1

    # If nothing detected, return original image untouched
    if top == 0 and bottom == 0 and left == 0 and right == 0:
        return image

    # Sanity check: don't crop away almost the whole image
    new_w = w - left - right
    new_h = h - top - bottom
    if new_w < w * 0.5 or new_h < h * 0.5:
        return image

    return image.crop((left, top, w - right, h - bottom))


def compute_rotation_hashes(image: Image.Image) -> list:
    """
    Applies detect_and_crop_border, then rotates the cleaned image at
    0°, 90°, 180°, 270°, computing one perceptual hash (phash) per rotation.
    Returns all 4 hashes for that image.
    """
    cleaned = detect_and_crop_border(image.convert("RGB"))
    hashes = []
    for angle in (0, 90, 180, 270):
        rotated = cleaned.rotate(angle, expand=True)
        hashes.append(imagehash.phash(rotated))
    return hashes


def hash_distance(hashes_a: list, hashes_b: list) -> int:
    """
    Compares two images' 4-hash sets pairwise (4x4 combinations) and returns
    the minimum Hamming distance found — this is what makes matching
    rotation-tolerant.
    """
    best = None
    for ha in hashes_a:
        for hb in hashes_b:
            d = ha - hb  # imagehash supports subtraction as Hamming distance
            if best is None or d < best:
                best = d
    return best if best is not None else 999