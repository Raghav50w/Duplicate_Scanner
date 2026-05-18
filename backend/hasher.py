"""
hasher.py — Step 1: group files by size, then SHA-256 hash.
Returns exact duplicate groups and the list of files that need CNN processing.
"""

import hashlib
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif",
    ".webp", ".heic", ".heif", ".avif",
}


def scan_directory(folder: str) -> list[str]:
    """Recursively collect all supported image paths under folder."""
    paths = []
    for root, _, files in os.walk(folder):
        for fname in files:
            if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                paths.append(os.path.join(root, fname))
    return paths


def _sha256(path: str) -> tuple[str, str]:
    """Return (path, hex-digest). Reads file in 64 KB chunks."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return path, h.hexdigest()
    except (OSError, PermissionError):
        return path, ""


def find_exact_duplicates(
    paths: list[str],
    max_workers: int = 8,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[list[str]], list[str]]:
    """
    Step 1 of pipeline.

    Returns
    -------
    exact_groups : list of lists — each inner list is a group of byte-identical files.
    remaining    : files that are NOT exact duplicates; need CNN processing.
    """
    # --- Phase A: group by file size (free — no I/O beyond stat) ---
    size_groups: dict[int, list[str]] = defaultdict(list)
    for p in paths:
        try:
            size_groups[os.path.getsize(p)].append(p)
        except OSError:
            pass

    # Files with unique sizes cannot be duplicates
    candidates = [p for group in size_groups.values() if len(group) > 1 for p in group]
    unique_size = [p for group in size_groups.values() if len(group) == 1 for p in group]

    # --- Phase B: SHA-256 on size-matched candidates (parallel I/O) ---
    hash_map: dict[str, list[str]] = defaultdict(list)
    total = len(candidates)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_sha256, p): p for p in candidates}
        for fut in as_completed(futures):
            path, digest = fut.result()
            done += 1
            if progress_cb:
                progress_cb(done, total)
            if digest:
                hash_map[digest].append(path)

    exact_groups = [group for group in hash_map.values() if len(group) > 1]
    exact_paths = {p for group in exact_groups for p in group}

    # Keep only ONE representative from each exact group in remaining
    exact_representatives = [group[0] for group in exact_groups]
    remaining = unique_size + [p for p in candidates if p not in exact_paths] + exact_representatives

    return exact_groups, remaining
