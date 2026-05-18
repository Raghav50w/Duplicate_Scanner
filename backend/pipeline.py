"""
pipeline.py — Orchestrates the full 5-step duplicate detection pipeline.

Designed to run inside a QThread (or any thread).
Progress is reported via callbacks so the UI never blocks.

Usage:
    from backend.pipeline import run_pipeline

    def on_progress(stage, done, total, message):
        ...  # update UI

    exact_groups, near_groups = run_pipeline(
        folder="/path/to/photos",
        threshold=0.92,
        max_hash_workers=8,
        max_cnn_workers=4,
        progress_cb=on_progress,
    )
"""

from typing import Callable, Optional
from backend import cache, hasher, extractor, indexer, verifier

# Type alias for progress callback
# Args: stage (str), done (int), total (int), message (str)
ProgressCB = Callable[[str, int, int, str], None]


def run_pipeline(
    folder: str,
    threshold: float = 0.92,
    max_hash_workers: int = 8,
    max_cnn_workers: int = 4,
    progress_cb: Optional[ProgressCB] = None,
    cancelled_flag: Optional[list] = None,  # pass a [False] list; set [0]=True to cancel
) -> tuple[list[list[str]], list[list[str]]]:
    """
    Run the full pipeline.

    Returns
    -------
    exact_groups : groups of byte-identical files
    near_groups  : groups of visually similar (but not identical) files
    """
    def _prog(stage, done, total, msg=""):
        if progress_cb:
            progress_cb(stage, done, total, msg)

    def _cancelled():
        return cancelled_flag is not None and cancelled_flag[0]

    # Initialise the SQLite cache
    cache.init_db()

    # ------------------------------------------------------------------ Step 1
    _prog("scan", 0, 1, "Scanning directory for images...")
    all_paths = hasher.scan_directory(folder)
    total_files = len(all_paths)
    _prog("scan", 1, 1, f"Found {total_files} images")

    if _cancelled():
        return [], []

    _prog("hash", 0, total_files, "Computing file hashes...")

    def hash_progress(done, total):
        _prog("hash", done, total, f"Hashing {done}/{total}")

    exact_groups, remaining = hasher.find_exact_duplicates(
        all_paths,
        max_workers=max_hash_workers,
        progress_cb=hash_progress,
    )
    _prog("hash", total_files, total_files,
          f"Found {len(exact_groups)} exact duplicate groups")

    if _cancelled():
        return exact_groups, []

    # ------------------------------------------------------------------ Step 3
    _prog("extract", 0, len(remaining), "Extracting CNN features...")

    def extract_progress(done, total):
        _prog("extract", done, total, f"Extracting features {done}/{total}")

    vector_map = extractor.extract_all(
        remaining,
        max_workers=max_cnn_workers,
        progress_cb=extract_progress,
    )
    _prog("extract", len(remaining), len(remaining),
          f"Extracted features for {len(vector_map)} images")

    if _cancelled():
        return exact_groups, []

    # ------------------------------------------------------------------ Step 4
    _prog("index", 0, len(vector_map), "Building FAISS index and searching...")

    def index_progress(done, total):
        _prog("index", done, total, f"Indexing {done}/{total}")

    candidate_groups = indexer.build_candidate_groups(
        vector_map,
        threshold=threshold,
        progress_cb=index_progress,
    )
    _prog("index", len(vector_map), len(vector_map),
          f"Found {len(candidate_groups)} candidate groups")

    if _cancelled():
        return exact_groups, []

    # ------------------------------------------------------------------ Step 5
    _prog("verify", 0, len(candidate_groups), "Verifying with geometric matching...")

    near_groups = verifier.verify_groups(candidate_groups)

    _prog("verify", len(candidate_groups), len(candidate_groups),
          f"Confirmed {len(near_groups)} near-duplicate groups")

    return exact_groups, near_groups
