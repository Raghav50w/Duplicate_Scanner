"""
indexer.py — Step 4: FAISS vector indexing and candidate grouping.

Key design decision vs original spec:
  - We store all 4 rotation vectors per image.
  - During search we take the MAXIMUM cosine similarity across all 4×4 = 16
    rotation-pair combinations.
  - This is more accurate than averaging the vectors.
"""

from typing import Callable, Optional
import numpy as np


def build_candidate_groups(
    vector_map: dict[str, np.ndarray],
    threshold: float = 0.92,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[list[str]]:
    """
    Build candidate duplicate groups using FAISS IndexFlatIP.

    Parameters
    ----------
    vector_map : path → (4, D) float32 array (already L2-normalised)
    threshold  : cosine similarity cutoff (0.92 = 92% similar)

    Returns
    -------
    List of groups, each group is a list of paths. Groups have ≥ 2 members.
    """
    import faiss

    paths = list(vector_map.keys())
    if len(paths) < 2:
        return []

    D = vector_map[paths[0]].shape[1]  # embedding dimension

    # Build one flat index with all 4 rotation vectors per image.
    # We tag each vector with its source image index so we can look it up later.
    all_vecs = []
    vec_to_img: list[int] = []   # index in all_vecs → image index

    for img_idx, path in enumerate(paths):
        vecs = vector_map[path]  # (4, D)
        for v in vecs:
            all_vecs.append(v)
            vec_to_img.append(img_idx)

    matrix = np.vstack(all_vecs).astype(np.float32)  # (N*4, D)

    index = faiss.IndexFlatIP(D)  # inner product == cosine for L2-normalised vecs
    index.add(matrix)

    # For each image, query using all 4 of its rotation vectors.
    # Collect the best (max) similarity score found against each other image.
    total = len(paths)
    adjacency: dict[tuple[int, int], float] = {}   # (i, j) → max similarity

    for img_idx, path in enumerate(paths):
        if progress_cb:
            progress_cb(img_idx + 1, total)

        vecs = vector_map[path].astype(np.float32)  # (4, D)
        k = min(50, matrix.shape[0])                # query top-50 neighbours
        sims, indices = index.search(vecs, k)        # (4, k) each

        for rot_idx in range(4):
            for rank in range(k):
                neighbour_vec_idx = indices[rot_idx][rank]
                score = float(sims[rot_idx][rank])
                neighbour_img_idx = vec_to_img[neighbour_vec_idx]

                if neighbour_img_idx == img_idx:
                    continue  # skip self
                if score < threshold:
                    continue

                pair = (min(img_idx, neighbour_img_idx),
                        max(img_idx, neighbour_img_idx))
                adjacency[pair] = max(adjacency.get(pair, 0.0), score)

    # Union-Find to form connected groups from pairs
    parent = list(range(len(paths)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (i, j) in adjacency:
        union(i, j)

    clusters: dict[int, list[str]] = {}
    for img_idx, path in enumerate(paths):
        root = find(img_idx)
        clusters.setdefault(root, []).append(path)

    return [g for g in clusters.values() if len(g) >= 2]
