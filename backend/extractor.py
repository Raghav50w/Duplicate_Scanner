"""
extractor.py — Step 3: CNN feature extraction with EfficientNet-B0.

For each image:
  - Run at 0°, 90°, 180°, 270°
  - Store all 4 vectors separately (do NOT average — averaging loses info)
  - L2-normalise each vector so cosine similarity == dot product

Uses timm library. Falls back to torchvision if timm is not available.
Runs in a ProcessPoolExecutor (CPU/GPU bound).
"""

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Optional

import numpy as np

from backend.preprocessor import load_and_preprocess
from backend.cache import get_entry, set_entry

_model = None
_transform = None


def _init_model():
    """Lazy-load the model once per process."""
    global _model, _transform
    if _model is not None:
        return

    import torch

    try:
        import timm
        _model = timm.create_model("efficientnet_b0", pretrained=True, num_classes=0)
        _model.eval()
        # timm's data_config gives the right mean/std for the model
        data_cfg = timm.data.resolve_model_data_config(_model)
        _transform = timm.data.create_transform(**data_cfg, is_training=False)
    except ImportError:
        # Fallback: torchvision EfficientNet-B0
        from torchvision import models, transforms
        weights = models.EfficientNet_B0_Weights.DEFAULT
        _model = models.efficientnet_b0(weights=weights)
        _model.classifier = torch.nn.Identity()
        _model.eval()
        _transform = weights.transforms()


def _extract_single(arr: np.ndarray) -> np.ndarray:
    """
    Extract a single L2-normalised feature vector from a (224,224,3) float32 array.
    """
    import torch
    from PIL import Image

    _init_model()

    # Convert numpy array [0,1] → PIL → transform → tensor
    pil = Image.fromarray((arr * 255).astype(np.uint8))
    tensor = _transform(pil).unsqueeze(0)  # (1, C, H, W)

    with torch.no_grad():
        vec = _model(tensor).squeeze().numpy()

    norm = np.linalg.norm(vec)
    if norm > 1e-8:
        vec = vec / norm
    return vec.astype(np.float32)


def extract_vectors_for_path(path: str) -> tuple[str, Optional[np.ndarray]]:
    """
    Worker function — extract 4-rotation vectors for one image path.
    Returns (path, vectors) where vectors.shape == (4, D) or (path, None) on error.
    Checks cache first; writes to cache after extraction.
    """
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return path, None

    cached = get_entry(path)
    if cached and cached["vectors"] is not None:
        return path, cached["vectors"]

    arr = load_and_preprocess(path)
    if arr is None:
        return path, None

    try:
        rotations = [arr, np.rot90(arr, 1), np.rot90(arr, 2), np.rot90(arr, 3)]
        vectors = np.stack([_extract_single(r) for r in rotations])  # (4, D)
    except Exception:
        return path, None

    import hashlib
    try:
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        digest = ""

    set_entry(path, int(stat.st_size), stat.st_mtime, digest, vectors)
    return path, vectors


def extract_all(
    paths: list[str],
    max_workers: int = 4,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> dict[str, np.ndarray]:
    """
    Extract vectors for all paths using a ProcessPoolExecutor.
    Returns dict mapping path → (4, D) float32 array.
    """
    results: dict[str, np.ndarray] = {}
    total = len(paths)
    done = 0

    # ProcessPoolExecutor for CPU-bound CNN work
    # max_workers=4 is safe on most laptops; UI thread stays free
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(extract_vectors_for_path, p): p for p in paths}
        for fut in as_completed(futures):
            path, vectors = fut.result()
            done += 1
            if progress_cb:
                progress_cb(done, total)
            if vectors is not None:
                results[path] = vectors

    return results
