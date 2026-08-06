"""Central configuration: paths, supported formats, thresholds."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CACHE_DIR = PROJECT_ROOT / "cache"
DB_PATH = CACHE_DIR / "index.db"
THUMBS_DIR = CACHE_DIR / "thumbs"
WEB_DIR = PROJECT_ROOT / "web"

# All Pillow-native, so this stays a plain extension list. Multi-frame files use frame 0.
SUPPORTED_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
)

# --- Border crop -------------------------------------------------------------
# Per-channel difference still counted as "the same colour as the border".
# Compressed black bars contain values like 0/2/3, so an exact-match test finds
# no border at all; the tolerance is what makes the padded-screenshot case work.
BORDER_TOLERANCE = 12
# Only crop when it actually removes padding, not a couple of dark pixel rows.
BORDER_MIN_AREA_REDUCTION = 0.02

ROTATIONS = (0, 90, 180, 270)

# --- Hashing -----------------------------------------------------------------
# imagehash.phash(hash_size=8) -> 8x8 low-frequency DCT coefficients -> 64 bits.
HASH_SIZE = 8
HASH_BITS = HASH_SIZE * HASH_SIZE

# Fast mode ships this one value; there is no slider for it.
# Read off the PR curve in results/sweep_normalized.csv: the loosest threshold
# that still holds precision >= 0.999 on the 16,000-image benchmark. At 10 that
# is 5 false positives out of 127.8M non-duplicate pairs, for 0.771 recall.
# Only even values matter -- phash thresholds each of the 64 DCT coefficients
# against the median of all 64, so every hash has exactly 32 bits set and every
# Hamming distance between two of them is even. 11 behaves exactly like 10.
# Regenerate with: python -m eval.run_eval
FAST_HAMMING_THRESHOLD = 10

# Loose recall-oriented gate. Everything at or under this is written to `pairs`
# and becomes the candidate set the Phase 3 CNN re-ranks.
# 16 is 4 standard deviations below the mean distance between unrelated hashes
# (~Binomial(64, 0.5): mean 32, sd 4). Do not raise this to 24 without measuring:
# 24 lets ~2.3% of random pairs through and the cascade stops saving anything.
CANDIDATE_HAMMING_GATE = 16

# Peak bytes allowed for one chunk of the (queries x indexed x 4) xor buffer.
# Chunk size is derived from this so memory stays flat as the library grows.
DISTANCE_CHUNK_BYTES = 64_000_000

# --- Thumbnails --------------------------------------------------------------
THUMB_SIZE = 256
THUMB_QUALITY = 80

# --- UI ----------------------------------------------------------------------
# Smart-mode cosine slider bounds (Phase 3; the UI reads them now so the layout
# does not shift later).
COSINE_MIN = 0.85
COSINE_MAX = 1.00
COSINE_DEFAULT = 0.93
