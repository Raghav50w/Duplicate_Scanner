# Duplicate Image Scanner

A desktop application that finds and removes duplicate images using a 5-step pipeline:
exact hashing → image pre-processing → CNN feature extraction → FAISS vector search → ORB keypoint verification.

---

## Requirements

- Python 3.11 or 3.12 (recommended)
- 4 GB RAM minimum (8 GB recommended for large libraries)
- Internet connection for first run (downloads EfficientNet-B0 weights ~20 MB)

---

## Installation — Step by Step

### Step 1: Install Python

Download Python 3.11 or 3.12 from https://python.org
During installation on Windows: **check "Add Python to PATH"**

Verify in terminal:
```
python --version
```

### Step 2: Create a virtual environment

Open a terminal (Command Prompt / PowerShell on Windows, Terminal on Mac/Linux).
Navigate to where you downloaded this project folder, then:

```bash
cd duplicate_scanner
python -m venv venv
```

Activate it:

**Windows:**
```
venv\Scripts\activate
```

**Mac / Linux:**
```
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt.

### Step 3: Install PyTorch first

Go to https://pytorch.org/get-started/locally/ and select your OS.

**If you have NO GPU (most laptops):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

**If you have an NVIDIA GPU:**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Step 4: Install all other dependencies

```bash
pip install Pillow pillow-heif timm faiss-cpu opencv-python numpy PyQt6 send2trash
```

### Step 5: Run the app

```bash
python main.py
```

---

## How to Use

1. Click **Browse** and select a folder containing your images (scans subfolders automatically).
2. Adjust the **Similarity threshold** slider — 92% is a good default. Lower = finds more duplicates but more false positives. Higher = stricter.
3. Adjust **Hash threads** (default 8) and **CNN workers** (default 4) if needed.
4. Click **Scan**.
5. Review results in the grid. The first image in each group is marked **KEEP**. Click **Delete** on any image to send it to the OS trash (not permanent).

---

## What each step does

| Step | What it does | Tech |
|------|-------------|------|
| 1 | Groups files by size, then SHA-256 hash | stdlib hashlib |
| 2 | Crops solid-colour borders, removes screenshot chrome | Pillow + NumPy |
| 3 | Extracts CNN features at 4 rotations | EfficientNet-B0 via timm |
| 4 | Finds visually similar images by vector similarity | FAISS |
| 5 | Confirms geometry matches, rejects false positives | OpenCV ORB + RANSAC |

---

## Edge cases handled

- Rotated images (4-rotation vector search)
- Scaled / resolution-changed images (CNN is scale-invariant)
- Compressed images (CNN is compression-robust)
- Black, white, or coloured solid borders (auto-cropped before CNN)
- Screenshots with browser/app chrome (centre-crop removes top/bottom 10%)
- Watermarked images (centre-crop + ORB matching on content area)
- HEIC and AVIF (iPhone photos) via pillow-heif
- Two different TVs / flat screens flagged as duplicates (ORB + RANSAC geometric verification rejects these)

---

## File structure

```
duplicate_scanner/
├── backend/
│   ├── cache.py          SQLite cache: path, mtime, hash, vectors
│   ├── hasher.py         Step 1: size grouping + SHA-256
│   ├── preprocessor.py   Step 2: border crop, centre crop, resize
│   ├── extractor.py      Step 3: EfficientNet-B0 4-rotation vectors
│   ├── indexer.py        Step 4: FAISS max-score search
│   └── verifier.py       Step 5: ORB + Lowe ratio + RANSAC homography
│   └── pipeline.py       Orchestrates all 5 steps
├── frontend/
│   ├── main_window.py    PyQt6 main window + settings
│   ├── thumbnail_grid.py Scrollable duplicate group viewer
│   └── worker_thread.py  QThread wrapper (keeps UI responsive)
├── tests/
│   └── test_hasher.py
├── main.py               Entry point
├── requirements.txt
└── cache.db              Created on first run
```

---

## Troubleshooting

**"No module named PyQt6"** — make sure your venv is activated before running.

**App is slow on first scan** — the first scan downloads and runs EfficientNet-B0. Subsequent scans are fast because features are cached in `cache.db`.

**HEIC files not loading** — run `pip install pillow-heif` and restart the app.

**"RANSAC rejected" everything** — lower the similarity threshold. Try 85-88%.

**App freezes during scan** — this shouldn't happen. If it does, reduce CNN workers to 2.
