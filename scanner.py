"""
scanner.py

Hash-based duplicate/near-duplicate image scanner.

Design note (for future Phase 2 extensibility):
This module exposes scan_folder_hash() as the hash-based implementation.
A future scan_folder_cnn(folder_path, similarity_threshold=0.9) can be added
alongside it with the same return shape (list of duplicate groups), so
main.py's run_scan() dispatcher can call either one without any changes
to the rest of the app (GUI, thumbnail rendering, delete logic).

# Future -- not implemented in this MVP:
# def scan_folder_cnn(folder_path: str, similarity_threshold: float = 0.9) -> list:
#     '''CNN-based scan. Same return shape as scan_folder_hash.'''
"""

import os
import hashlib

from PIL import Image
import imagehash

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def _find_image_files(folder_path):
    """Recursively collect paths to supported image files under folder_path."""
    image_files = []
    for root, _dirs, files in os.walk(folder_path):
        # Don't rescan anything already moved into the review/delete folder.
        if os.path.basename(root) == "_deleted_review":
            continue
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                image_files.append(os.path.join(root, name))
    return image_files


def _compute_md5(path):
    """MD5 of raw file bytes -- used to detect exact duplicates."""
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _compute_phash(path):
    """Perceptual hash of image content -- used to detect near-duplicates."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        return imagehash.phash(img)


class _UnionFind:
    """Simple disjoint-set structure for grouping files into duplicate clusters."""

    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def scan_folder_hash(folder_path: str, hash_threshold: int = 5, progress_callback=None) -> list:
    """
    Recursively scans folder_path for images, grouping exact duplicates
    (identical MD5) and near-duplicates (perceptual hash Hamming distance
    <= hash_threshold) into the same duplicate groups.

    Args:
        folder_path: root folder to scan recursively.
        hash_threshold: max phash Hamming distance to treat as "near-duplicate".
        progress_callback: optional callable(current, total) invoked as each
            file is processed, so a GUI can show scan progress.

    Returns:
        list[list[str]]: list of duplicate groups. Each group is a list of
        full file paths considered duplicates of each other. Groups with
        only one image (no duplicates found) are excluded.
    """
    image_paths = _find_image_files(folder_path)
    total = len(image_paths)

    md5_map = {}
    phash_map = {}
    valid_paths = []

    for i, path in enumerate(image_paths, start=1):
        try:
            md5_map[path] = _compute_md5(path)
            phash_map[path] = _compute_phash(path)
            valid_paths.append(path)
        except Exception as e:
            print(f"Warning: skipping unreadable file '{path}': {e}")
        finally:
            if progress_callback:
                progress_callback(i, total)

    uf = _UnionFind(valid_paths)

    # Exact duplicates: identical MD5 -> union immediately.
    md5_buckets = {}
    for path in valid_paths:
        md5_buckets.setdefault(md5_map[path], []).append(path)
    for bucket in md5_buckets.values():
        for other in bucket[1:]:
            uf.union(bucket[0], other)

    # Near-duplicates: phash Hamming distance <= threshold -> union.
    n = len(valid_paths)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = valid_paths[i], valid_paths[j]
            if uf.find(a) == uf.find(b):
                continue  # already grouped, skip the (cheap) hash comparison
            if (phash_map[a] - phash_map[b]) <= hash_threshold:
                uf.union(a, b)

    groups_by_root = {}
    for path in valid_paths:
        root = uf.find(path)
        groups_by_root.setdefault(root, []).append(path)

    return [group for group in groups_by_root.values() if len(group) > 1]


# Backward-compatible alias matching the original spec's function name/signature.
def scan_folder(folder_path: str, hash_threshold: int = 5) -> list:
    return scan_folder_hash(folder_path, hash_threshold=hash_threshold)
