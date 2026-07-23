"""
Folder-level orchestration: walking, exact-match fast path, near-duplicate
grouping via hashing.py. This is the single entry point the frontend calls.
"""

import os
import hashlib
from PIL import Image, UnidentifiedImageError

from . import hashing

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def _collect_image_files(folder_path: str) -> list:
    files = []
    for root, _dirs, filenames in os.walk(folder_path):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append(os.path.join(root, name))
    return files


def _md5_of_file(path: str) -> str:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def scan_folder_hash(folder_path: str, hash_threshold: int = 5,
                      progress_callback=None) -> list:
    """
    1. Recursively walks folder_path, collecting all supported image files
    2. Computes MD5 of raw file bytes for every image (exact-duplicate fast path)
    3. Groups any images with identical MD5 immediately
    4. For all remaining images, computes rotation-hash sets via hashing.py
    5. Compares all pairs using hash_distance; groups anything <= hash_threshold
    6. Merges exact-duplicate groups and near-duplicate groups, removing overlaps
    7. Returns a list of groups (each a list of full file paths).
       Groups of size 1 are excluded.

    progress_callback(current, total), if provided, is called periodically
    so the frontend can update a progress label.
    """
    files = _collect_image_files(folder_path)
    total = len(files)

    # --- Step 2 & 3: exact-duplicate fast path via MD5 ---
    md5_map = {}
    for i, path in enumerate(files):
        digest = _md5_of_file(path)
        if digest:
            md5_map.setdefault(digest, []).append(path)
        if progress_callback:
            progress_callback(i + 1, total)

    exact_groups = [group for group in md5_map.values() if len(group) > 1]
    exact_matched_paths = {p for group in exact_groups for p in group}

    # --- Step 4: compute rotation hashes for everything not already exact-matched ---
    remaining = [p for p in files if p not in exact_matched_paths]

    hash_data = []  # list of (path, hashes)
    for i, path in enumerate(remaining):
        try:
            with Image.open(path) as img:
                hashes = hashing.compute_rotation_hashes(img)
            hash_data.append((path, hashes))
        except (UnidentifiedImageError, OSError):
            continue  # skip unsupported/corrupt files, no crash
        if progress_callback:
            progress_callback(len(exact_matched_paths) + i + 1, total)

    # --- Step 5: pairwise comparison ---
    n = len(hash_data)
    parent = list(range(n))  # union-find for grouping

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for i in range(n):
        for j in range(i + 1, n):
            dist = hashing.hash_distance(hash_data[i][1], hash_data[j][1])
            if dist <= hash_threshold:
                union(i, j)

    near_groups_map = {}
    for i in range(n):
        root = find(i)
        near_groups_map.setdefault(root, []).append(hash_data[i][0])

    near_groups = [group for group in near_groups_map.values() if len(group) > 1]

    # --- Step 6: merge, remove overlaps (exact groups take precedence) ---
    all_groups = exact_groups + near_groups

    return all_groups


def run_scan(folder_path: str, method: str = "hash", **settings) -> list:
    """
    Dispatcher the frontend actually calls. Currently only supports
    method="hash" and routes to scan_folder_hash. Future detection methods
    (e.g. "cnn") slot in here as new branches without touching frontend code.
    """
    if method == "hash":
        return scan_folder_hash(
            folder_path,
            hash_threshold=settings.get("hash_threshold", 5),
            progress_callback=settings.get("progress_callback"),
        )
    elif method == "cnn":
        raise NotImplementedError("CNN detection mode is not implemented yet.")
    else:
        raise ValueError(f"Unknown detection method: {method}")