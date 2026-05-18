"""
verifier.py — Step 5: geometric keypoint verification.

For each candidate group from FAISS:
1. Extract ORB keypoints on centre-cropped grayscale images.
2. BFMatcher + Lowe ratio test at 0.75.
3. RANSAC homography check — if valid transform found, confirmed duplicate.
4. Fallback: if image has < MIN_KEYPOINTS keypoints, use strict CNN threshold (handled
   in pipeline.py by passing the FAISS similarity score alongside).
"""

import cv2
import numpy as np
from backend.preprocessor import load_for_orb

MIN_KEYPOINTS = 20          # below this → too few features for ORB to be reliable
LOWE_RATIO = 0.75           # standard ratio test threshold
RANSAC_REPROJECTION = 5.0   # pixel tolerance for RANSAC inlier detection
MIN_RANSAC_INLIERS = 8      # minimum inliers to call it a valid homography

_orb = None


def _get_orb():
    global _orb
    if _orb is None:
        _orb = cv2.ORB_create(nfeatures=500)
    return _orb


def _features(gray: np.ndarray) -> tuple[list, np.ndarray | None]:
    """Return (keypoints, descriptors) for a grayscale image."""
    orb = _get_orb()
    kps, descs = orb.detectAndCompute(gray, None)
    return kps, descs


def _match_pair(gray_a: np.ndarray, gray_b: np.ndarray) -> tuple[bool, str]:
    """
    Returns (is_duplicate, reason_string).

    Verification logic:
    1. Extract ORB keypoints.
    2. BFMatcher + Lowe ratio test.
    3. If enough matches: RANSAC homography check.
    4. If too few keypoints on either image: return (True, "low-kp fallback")
       so pipeline.py can decide based on CNN score alone.
    """
    kps_a, descs_a = _features(gray_a)
    kps_b, descs_b = _features(gray_b)

    # Low keypoint fallback — image too small or too uniform for ORB
    if len(kps_a) < MIN_KEYPOINTS or len(kps_b) < MIN_KEYPOINTS:
        return True, "low-kp-fallback"

    if descs_a is None or descs_b is None:
        return False, "no-descriptors"

    # BFMatcher with Hamming distance (correct for ORB binary descriptors)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw_matches = matcher.knnMatch(descs_a, descs_b, k=2)

    # Lowe ratio test
    good = []
    for match_pair in raw_matches:
        if len(match_pair) == 2:
            m, n = match_pair
            if m.distance < LOWE_RATIO * n.distance:
                good.append(m)

    if len(good) < MIN_RANSAC_INLIERS:
        return False, f"too-few-matches:{len(good)}"

    # RANSAC homography — confirms consistent geometric transformation
    src_pts = np.float32([kps_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, RANSAC_REPROJECTION)

    if H is None or mask is None:
        return False, "ransac-failed"

    inliers = int(mask.sum())
    if inliers >= MIN_RANSAC_INLIERS:
        return True, f"ransac-ok:{inliers}-inliers"
    else:
        return False, f"ransac-rejected:{inliers}-inliers"


def verify_groups(
    candidate_groups: list[list[str]],
    faiss_scores: dict[tuple[str, str], float] | None = None,
    strict_cnn_threshold: float = 0.97,
) -> list[list[str]]:
    """
    Filter candidate groups through ORB + RANSAC verification.

    Parameters
    ----------
    candidate_groups    : from indexer.build_candidate_groups
    faiss_scores        : optional dict (path_a, path_b) → similarity score
                          used to confirm low-keypoint-fallback pairs
    strict_cnn_threshold: fallback threshold when keypoints are insufficient

    Returns verified duplicate groups (False positives removed).
    """
    verified_groups = []

    for group in candidate_groups:
        if len(group) < 2:
            continue

        # Build adjacency within the group using pairwise ORB verification
        confirmed_pairs: list[tuple[str, str]] = []

        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                path_a, path_b = group[i], group[j]

                gray_a = load_for_orb(path_a)
                gray_b = load_for_orb(path_b)

                if gray_a is None or gray_b is None:
                    continue

                is_dup, reason = _match_pair(gray_a, gray_b)

                # For low-keypoint fallback, require strict CNN score
                if reason == "low-kp-fallback" and faiss_scores is not None:
                    key = (min(path_a, path_b), max(path_a, path_b))
                    score = faiss_scores.get(key, 0.0)
                    is_dup = score >= strict_cnn_threshold

                if is_dup:
                    confirmed_pairs.append((path_a, path_b))

        if not confirmed_pairs:
            continue

        # Merge confirmed pairs into sub-groups via Union-Find
        paths_in_group = group
        parent = {p: p for p in paths_in_group}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for a, b in confirmed_pairs:
            union(a, b)

        clusters: dict[str, list[str]] = {}
        for p in paths_in_group:
            root = find(p)
            clusters.setdefault(root, []).append(p)

        for sub in clusters.values():
            if len(sub) >= 2:
                verified_groups.append(sub)

    return verified_groups
