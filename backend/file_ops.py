"""
Soft-delete and file-info helpers.
"""

import os
import shutil
from PIL import Image

REVIEW_FOLDER_NAME = "_deleted_review"


def get_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def get_image_resolution(path: str):
    try:
        with Image.open(path) as img:
            return img.size  # (width, height)
    except Exception:
        return (0, 0)


def _unique_destination(dest_folder: str, filename: str) -> str:
    """Handle name collisions by appending a counter before the extension."""
    base, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(dest_folder, candidate)):
        candidate = f"{base}_{counter}{ext}"
        counter += 1
    return candidate


def move_to_review_folder(paths: list, source_folder: str) -> list:
    """
    Moves given files into a `_deleted_review` subfolder inside the scanned
    folder, preserving filenames (handling name collisions by renaming if needed).
    Returns the list of new paths.
    """
    review_dir = os.path.join(source_folder, REVIEW_FOLDER_NAME)
    os.makedirs(review_dir, exist_ok=True)

    new_paths = []
    for path in paths:
        if not os.path.exists(path):
            continue
        filename = os.path.basename(path)
        safe_name = _unique_destination(review_dir, filename)
        dest = os.path.join(review_dir, safe_name)
        try:
            shutil.move(path, dest)
            new_paths.append(dest)
        except OSError:
            # Skip files that can't be moved (permissions, in-use, etc.)
            continue
    return new_paths