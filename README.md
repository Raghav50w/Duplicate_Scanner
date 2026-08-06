# GallerySweep — Duplicate Photo Detector

Finds duplicate and near-duplicate photos in a phone-backup folder, shows them
side by side, and moves the extras to the Recycle Bin.

It handles two cases that ordinary file comparison misses:

- **Rotated copies** — the same photo saved at 90/180/270°, or EXIF-rotated vs. baked in.
- **Padded screenshots** — the same screenshot with black, white or coloured bars added.

Python, FastAPI and SQLite on the server; plain HTML, CSS and JavaScript on the
page. No Node, no build step, no database server.

## Quick start

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python.exe -m app.main
```

The third command starts the server and opens your browser at
<http://127.0.0.1:8000>. Nothing else to configure — no environment variables, no
database to create. `Ctrl+C` stops it. Full notes in [Setup](#setup) below.

On Linux or macOS the paths differ only in the usual way: `.venv/bin/python`
instead of `.venv\Scripts\python.exe`.

---

## Results

Measured on a generated benchmark of **16,000 images** — 800 base photos from
DIV2K, each put through 19 transforms — giving **152,000 duplicate pairs** and
**127.8 million non-duplicate pairs**. Every number below is reproduced by
`python -m eval.run_eval`; the CSVs and plots are in [`results/`](results).

| | with normalization | without |
|---|---|---|
| Average precision | **0.829** | 0.499 |
| Precision at the shipped threshold | **0.99996** (5 false positives in 127.8M pairs) | |
| Recall at the shipped threshold | 0.771 | |
| F1 at the shipped threshold | 0.871 | |
| Best F1 | 0.884 (at distance 12) | |

**Accuracy is not reported.** 99.88% of all pairs are non-duplicates, so a
detector that answers "never a duplicate" scores 99.88% and finds nothing.

### Recall by transform

Only the transforms where something actually happens are listed. Distances are
Hamming, out of 64 bits, and the shipped threshold is 10.

| Transform | recall | without normalization | median dist. | p95 |
|---|---|---|---|---|
| **crop 20%** | **0.000** | 0.000 | 26 | 32 |
| **crop 10%** | **0.035** | 0.031 | 20 | 26 |
| **crop 5%** | **0.609** | 0.608 | 10 | 16 |
| white bars | 0.988 | **0.138** | 0 | 2 |
| coloured bars | 0.989 | **0.111** | 0 | 2 |
| black bars | 0.994 | **0.139** | 0 | 2 |
| brightness +20% / −20% | 0.996 / 0.999 | 0.999 / 1.000 | 2 / 0 | 4 / 2 |
| rotate 90° / 180° / 270° | 1.000 | **0.000** | 0 | 2 |

The eight transforms not shown — exact copies, JPEG at q90/q60/q30, WhatsApp
recompression, and resizes to 75/50/25% — all score between **0.997 and 1.000**
with or without normalization, since none of them changes the low-frequency
structure a DCT hash reads. Full numbers for all 19 are in
[`results/per_transform_recall.csv`](results/per_transform_recall.csv).

**Why some values are exactly 1.000 and 0.000.** These are not rounded — they are
structural, and anything else would mean a bug:

- A 90° rotation is a **lossless pixel permutation**. The rotated copy's hash is
  bit-identical to the rotation-90 hash already stored for the original, so the
  distance is 0, not merely small. Hence exactly 1.000.
- Without normalization the same rotation scores exactly 0.000, because rotating
  permutes the DCT basis and puts the copy ~32 bits away — **the same distance as
  a completely unrelated photo**. Not weak signal; no signal.
- A checksum scores 1.000 on exact copies and 0.000 on all 18 other transforms,
  because a single changed byte changes the hash completely. That is the whole
  argument for perceptual hashing: **byte comparison finds 1 of 19 duplicate types.**

Three things the table says:

- **Cropping is where the hash fails**, and it is the only place it fails. Recall
  collapses from 0.609 at a 5% crop to 0.000 at 20%, where the copy sits a median
  of 26 bits from its own original — indistinguishable from a stranger. The overall
  0.771 recall is almost entirely this.
- **Normalization is what catches rotations and padding**, and nothing else.
  Rotations go 0.000 → 1.000, padded screenshots ~0.13 → ~0.99. Everywhere else
  the ablation column is flat, which is the honest result: the stage earns its
  place on exactly two cases.
- **The median/p95 columns matter more than the recall column.** A transform at
  median 0 with p95 2 is comfortably inside the threshold; `crop_5%` at median 10
  with p95 16 is sitting on the boundary, which is why its recall is 0.609 rather
  than something stable.

### What these numbers do not show

The benchmark is built from **DIV2K**, a standard super-resolution dataset: 800
professionally shot, sharp, mutually distinct scenes. That makes the negatives
unusually easy — no two base photos resemble each other, so a false positive
requires a genuine hash collision. **A real phone gallery is the opposite**: burst
frames of the same subject, ten photos of one room, screenshots that differ only
in their text. Perceptual hashing struggles precisely there, so the 0.99996
precision figure should be read as an upper bound, not as what a real library
would give.

Each generated copy also has exactly one transform applied cleanly. Real
duplicates stack them — a forwarded screenshot of a crop, three re-saves deep.

Two smaller caveats. The base images are DIV2K at 4× downscale (~510×350), so the
WhatsApp transform's 1600px resize never triggers and that row really measures a
q80 re-encode. And a "duplicate pair" here is any two files from the same base
photo, including `crop_20` against `rotate_90`, which is harder than either
against the original.

### On a realistic folder

Because the benchmark's threshold was chosen on the benchmark itself,
[`eval/make_testset.py`](eval/make_testset.py) builds a second, differently-shaped
set: 1,000 images laid out like a phone backup — 800 photos of which **668 have no
duplicate at all**, and 132 that have one, two or three stray copies scattered
across `Camera`, `WhatsApp`, `Screenshots` and three other folders, each mangled
with randomised parameters rather than fixed ones.

| | |
|---|---|
| Stray copies found | **170 of 200** (0.85) |
| Pair precision | 0.9957 — **one** false positive |
| Groups surfaced | 121 |

Every one of the 30 misses was a crop, including some as light as 3%. The single
false positive is a real collision worth looking at: a portrait of a man with wild
dark hair on a dark background matched against an aerial shot of a white boat on
dark water — to a 32×32 DCT both are one bright shape on a dark field.

Reproduce with `python -m eval.make_testset` then `python -m eval.score_testset`.

---

## How it works

```
folder ──▶ normalize ──▶ pHash x4 rotations ──▶ Hamming search ──▶ connected components ──▶ review grid
             │
      EXIF orientation
      uniform-border crop
```

**Normalization comes first, because perceptual hashing is not
rotation-invariant.** pHash reads low-frequency DCT coefficients, and a 90°
rotation permutes the DCT basis: an image and its own rotation land ~32 bits
apart out of 64 — statistically indistinguishable from two unrelated photos.

**All four rotations are indexed, rather than picking a canonical one.** Each
image's rotation-0 hash is compared against all four rotations of every other
image, so a photo matches its own 90° copy via `A.h0 == B.h90`. Choosing a
canonical rotation — say, the numeric minimum of the four — would be a discrete
choice that JPEG noise can flip, leaving two copies of one photo with different
canonical forms that silently never match.

This works even though pHash resizes to a square and ignores aspect ratio.
Resizing to a square and rotating by a multiple of 90° commute: rotating swaps
the axes and therefore swaps the two scale factors, so the 32×32 grid of a
rotated image is exactly the rotated 32×32 grid of the original. Only resampling
noise differs, worth a couple of bits.

**Border crop uses a tolerance, not `getbbox()`.** A compressed "black" bar is
full of 0/2/3 values, so an exact-match difference is non-zero everywhere and the
bounding box comes back as the whole image. The tolerance threshold is what makes
the padded-screenshot case work at all. The crop reads the four corner pixels, and
applies only if they agree and the crop removes more than 2% of the area — so dark
edges on a real photo are left alone.

**Distance** is Hamming over `uint64` hashes via `np.bitwise_count`, chunked over
query rows so peak memory stays flat as the library grows.

**Grouping is connected components** over the matched pairs
(`scipy.sparse.csgraph`). This chains: if A~B and B~C, all three group together
even when A and C look different. The scanner logs a warning when the largest
group is implausibly big, which is the signal that a threshold is too loose.

**The keeper** — the photo that starts unchecked — is the one with the most
pixels, then the largest file, then the oldest mtime. The original is assumed
biggest and earliest; forwarded copies are shrunken and made later.

Thresholds live in [`app/config.py`](app/config.py): matches are reported at a
Hamming distance of 10 or less, and pairs are stored out to 16. Ten is the
loosest value that holds precision above 0.999 on the benchmark.

**Only even thresholds mean anything.** pHash compares each of the 64
low-frequency DCT coefficients against the median of all 64, so every hash has
exactly 32 bits set. For two such hashes `|A xor B| = 64 - 2|A and B|`, which is
always even — a threshold of 11 accepts precisely the same pairs as 10. The
sweep in `results/sweep_normalized.csv` shows this directly: rows 8 and 9 are
identical, as are 10 and 11, and 12 and 13.

---

## Setup

Requires **Python 3.12 or newer**, and nothing else — no Node, no database
server, no Docker. Everything else comes from pip.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running it

```bash
.venv\Scripts\python.exe -m app.main
```

That starts the server on <http://127.0.0.1:8000> and opens a browser. `Ctrl+C`
stops it. There are no launcher scripts — this one command is the whole thing, on
every platform (`.venv/bin/python -m app.main` on Linux and macOS).

To choose a different port, or to run without the browser opening:

```bash
python -m uvicorn app.main:app --port 9000
```

The **Browse** button opens the native folder dialog through tkinter, which ships
with the python.org installers and with macOS Python. On Debian or Ubuntu it is a
separate package (`sudo apt install python3-tk`); without it the button returns an
error and you can paste a path into the text field instead.

## Using it

1. **Browse** to a folder, or paste a path. Scanning is **recursive** — point it
   at a parent folder and duplicates are found *across* subfolders, so the same
   photo in `Gallery` and in `WhatsApp/Media` lands in one group.
2. Wait for the scan. A second scan of the same folder is near-instant: hashes are
   cached against `(path, size, mtime)`, so unchanged files are never re-hashed.
3. Review the groups. **The best copy starts unchecked; every other copy starts
   checked.** Untick anything worth keeping.
4. **Delete** — everything ticked goes to the Recycle Bin.

The Recycle Bin is the undo; there is no quarantine folder and no undo log.
`send2trash` fails on network drives and on removable media that have no Recycle
Bin, and the app reports that rather than falling back to a permanent delete.

Files that cannot be decoded — truncated downloads, PNGs named `.jpg` — are
counted and skipped, and the count is shown above the results. One bad file
never stops a scan.

Nothing is ever written into the folder being cleaned. The cache
(`cache/index.db` and `cache/thumbs/`) lives inside the project and is gitignored.

**Supported formats:** `.jpg .jpeg .png .webp .bmp .tif .tiff .gif`. Multi-frame
files use frame 0.

---

## Layout

```
app/
  config.py      extensions, thresholds, cache paths
  normalize.py   exif_transpose, border_crop, rotations
  hashing.py     pHash over the 4 rotations
  matching.py    Hamming search, connected components, grouping, keeper pick
  db.py          the two tables, cache lookup by (path, size, mtime)
  scanner.py     recursive walk, background scan, one module-level progress state
  thumbs.py      256px webp cache
  actions.py     send2trash deletion
  main.py        FastAPI routes + static mount
web/             index.html, app.js, styles.css
eval/augment.py  transform suite: rotations, bars, JPEG quality, resize, crop,
                 brightness, WhatsApp-style recompress
tests/           normalize, hashing, matching
```

### Data model

Two SQLite tables.

- `images(id, path UNIQUE, size, mtime, width, height, h0, h90, h180, h270)`
  Hashes are stored as **16-char hex TEXT, not INTEGER** — SQLite's INTEGER is
  signed 64-bit, so the roughly half of all pHashes with the high bit set would
  overflow or raise *"Python int too large to convert to SQLite INTEGER."*
  `(path, size, mtime)` is the cache key.
- `pairs(image_a, image_b, hamming, cosine, rotation_a, rotation_b)`
  One row per pair, always `image_a < image_b`, never a self-pair — a
  near-symmetric photo would otherwise match its own 180° rotation.

Groups are **not** stored. They are derived from `pairs` at whatever threshold is
asked for, so changing the threshold re-groups instantly with no rescan. `pairs`
is rebuilt from scratch on every scan, since the expensive part — hashing — stays
cached and stale pairs would resurrect deleted photos in the review grid. Rows
whose file no longer exists are pruned at the start of each scan.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/config` | Thresholds the page needs to render its controls |
| `POST /api/pick-folder` | Opens the native OS folder dialog, returns the chosen path |
| `POST /api/scan` | `{folder, mode}` → starts the background scan |
| `GET /api/progress` | `{phase, done, total, errors}` — polled |
| `GET /api/groups?threshold=` | Groups at the given threshold, from cached `pairs` |
| `GET /api/thumb/{image_id}` | Serves the cached 256px webp |
| `POST /api/delete` | `{image_ids}` → `send2trash` each |

`/api/groups` returns a normalized `similarity` (0–1, higher = more similar)
rather than a raw distance.

The folder dialog runs in a subprocess: tkinter misbehaves when driven from a
server worker thread, and a subprocess stuck on a modal dialog cannot take the
app down with it.

---

## Tests

```bash
.venv\Scripts\python.exe -m pytest
```

26 tests, generated from synthetic photos so the suite needs no committed image
files. From one base image the suite builds an exact copy, all three rotations,
black/white/coloured bars, a JPEG re-encode and a half-size resize, and asserts
they all land in one group while an unrelated photo stays out.

Three of them exist to catch specific silent failures: `border_crop` on a
JPEG-compressed bar (which a `getbbox()`-only implementation passes on clean PNGs
and fails on every real photo), `border_crop` on a photo with dark but textured
edges (over-cropping real content is that function's failure mode), and a pHash
with the high bit set round-tripping through `uint64`.

## Reproducing the benchmark

Every number in this README comes from one command. The extra packages are kept
out of `requirements.txt`, since running the app does not need them.

```bash
.venv\Scripts\python.exe -m pip install -r requirements-eval.txt
```

```bash
.venv\Scripts\python.exe -m eval.make_dataset
```

```bash
.venv\Scripts\python.exe -m eval.run_eval
```

`make_dataset.py` downloads DIV2K (247 MB), then writes 19 transformed copies of
each of the 800 base photos — about 1.2 GB under `data/`, which is gitignored.
Nothing is labelled by hand: two files generated from the same base photo are
duplicates and two from different bases are not, so the labels are a by-product
of generating the images and the whole benchmark is reproducible from a seed.
DIV2K is published for academic and research use; no images from it are committed.

`run_eval.py` hashes all 16,000 images twice — once through the normalization
stage, once raw — and sweeps every Hamming threshold from 0 to 64. Hashes are
cached in `data/hashes.csv`, so re-running the sweep does not re-hash; pass
`--rehash` to force it. It writes to [`results/`](results):

| File | Contents |
|---|---|
| `summary.csv` | headline metrics |
| `sweep_normalized.csv` | precision/recall/F1 at all 65 thresholds |
| `sweep_no_normalization.csv` | the same, ablated |
| `per_transform_recall.csv` | recall per transform, plus the checksum baseline |
| `pr_curve.png` | both PR curves |
| `distance_distribution.png` | same-photo vs different-photo distances |

Precision and recall are computed from 65-bucket distance histograms rather than
a per-pair score vector: at 127.8 million negative pairs, no per-sample metric
function will take the input, but a PR curve needs nothing more than the buckets.
That is also why scikit-learn is not a dependency.
