"""
main_window.py — PyQt6 main application window.

Layout:
  ┌─────────────────────────────────────────┐
  │  Top bar: folder picker + scan button   │
  │  Settings: threshold + thread sliders   │
  │  Progress bar + status label            │
  │  Scrollable thumbnail grid (main area)  │
  └─────────────────────────────────────────┘
"""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QSlider, QProgressBar, QSpinBox, QGroupBox,
    QSizePolicy, QFrame,
)

from frontend.thumbnail_grid import ThumbnailGrid
from frontend.worker_thread import ScanWorker

APP_TITLE  = "Duplicate Image Scanner"
MIN_WIDTH  = 900
MIN_HEIGHT = 650

DARK_BG      = "#0f0f1a"
PANEL_BG     = "#1a1a2e"
ACCENT       = "#6c63ff"
ACCENT_HOVER = "#7c74ff"
TEXT_PRIMARY = "#e2e8f0"
TEXT_MUTED   = "#94a3b8"
BORDER       = "#2d2d44"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker: ScanWorker | None = None
        self._setup_window()
        self._build_ui()
        self._apply_stylesheet()

    # ----------------------------------------------------------------- setup
    def _setup_window(self):
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.resize(1100, 750)

    # ----------------------------------------------------------------- UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_top_bar())
        root.addWidget(self._make_settings_bar())
        root.addWidget(self._make_progress_bar())
        root.addWidget(self._make_grid(), stretch=1)

    def _make_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        title = QLabel(APP_TITLE)
        title.setObjectName("appTitle")
        layout.addWidget(title)
        layout.addStretch()

        # Folder input
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("Select folder to scan...")
        self._folder_input.setMinimumWidth(350)
        self._folder_input.setObjectName("folderInput")
        layout.addWidget(self._folder_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.clicked.connect(self._browse_folder)
        layout.addWidget(browse_btn)

        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setObjectName("primaryBtn")
        self._scan_btn.clicked.connect(self._start_scan)
        layout.addWidget(self._scan_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("dangerBtn")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_scan)
        layout.addWidget(self._cancel_btn)

        return bar

    def _make_settings_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("settingsBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(30)

        # Similarity threshold
        layout.addWidget(QLabel("Similarity threshold:"))
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(80, 99)
        self._threshold_slider.setValue(92)
        self._threshold_slider.setFixedWidth(160)
        self._threshold_slider.valueChanged.connect(self._update_threshold_label)
        layout.addWidget(self._threshold_slider)

        self._threshold_label = QLabel("92%")
        self._threshold_label.setMinimumWidth(36)
        layout.addWidget(self._threshold_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Hash threads
        layout.addWidget(QLabel("Hash threads:"))
        self._hash_spin = QSpinBox()
        self._hash_spin.setRange(1, 32)
        self._hash_spin.setValue(8)
        self._hash_spin.setFixedWidth(60)
        layout.addWidget(self._hash_spin)

        # CNN workers
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        layout.addWidget(QLabel("CNN workers:"))
        self._cnn_spin = QSpinBox()
        self._cnn_spin.setRange(1, 16)
        self._cnn_spin.setValue(4)
        self._cnn_spin.setFixedWidth(60)
        layout.addWidget(self._cnn_spin)

        layout.addStretch()
        return bar

    def _make_progress_bar(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("progressWidget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(4)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready — select a folder and press Scan.")
        self._status_label.setObjectName("statusLabel")
        layout.addWidget(self._status_label)

        return widget

    def _make_grid(self) -> ThumbnailGrid:
        self._grid = ThumbnailGrid()
        return self._grid

    # ----------------------------------------------------------------- slots
    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select image folder")
        if path:
            self._folder_input.setText(path)

    def _update_threshold_label(self, value: int):
        self._threshold_label.setText(f"{value}%")

    def _start_scan(self):
        folder = self._folder_input.text().strip()
        if not folder or not os.path.isdir(folder):
            self._status_label.setText("Please select a valid folder first.")
            return

        threshold = self._threshold_slider.value() / 100.0

        self._scan_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(100)
        self._status_label.setText("Starting scan...")

        self._worker = ScanWorker(
            folder=folder,
            threshold=threshold,
            hash_workers=self._hash_spin.value(),
            cnn_workers=self._cnn_spin.value(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cancel_scan(self):
        if self._worker:
            self._worker.cancel()
            self._status_label.setText("Cancelling...")

    def _on_progress(self, stage: str, done: int, total: int, message: str):
        STAGE_WEIGHT = {
            "scan":    5,
            "hash":   20,
            "extract": 55,
            "index":  12,
            "verify":  8,
        }
        stage_offsets = {"scan": 0, "hash": 5, "extract": 25, "index": 80, "verify": 92}

        offset = stage_offsets.get(stage, 0)
        weight = STAGE_WEIGHT.get(stage, 10)
        pct = offset + (weight * done // max(total, 1))
        self._progress_bar.setValue(min(pct, 100))

        stage_labels = {
            "scan":    "Scanning files",
            "hash":    "Hashing files",
            "extract": "Extracting CNN features",
            "index":   "Building search index",
            "verify":  "Verifying with keypoints",
        }
        label = stage_labels.get(stage, stage)
        if message:
            self._status_label.setText(f"{label}: {message}")
        else:
            self._status_label.setText(f"{label}... {done}/{total}")

    def _on_finished(self, exact_groups: list, near_groups: list):
        self._progress_bar.setValue(100)
        total = len(exact_groups) + len(near_groups)
        self._status_label.setText(
            f"Scan complete — {total} duplicate group(s) found "
            f"({len(exact_groups)} exact, {len(near_groups)} near-duplicate)."
        )
        self._scan_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._grid.populate(exact_groups, near_groups)

    def _on_error(self, message: str):
        self._status_label.setText(f"Error: {message}")
        self._scan_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._progress_bar.setValue(0)

    # ----------------------------------------------------------------- style
    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {DARK_BG};
                color: {TEXT_PRIMARY};
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                font-size: 13px;
            }}
            #topBar {{
                background-color: {PANEL_BG};
                border-bottom: 1px solid {BORDER};
            }}
            #appTitle {{
                font-size: 16px;
                font-weight: 500;
                color: {TEXT_PRIMARY};
            }}
            #settingsBar {{
                background-color: {DARK_BG};
                border-bottom: 1px solid {BORDER};
            }}
            #progressWidget {{
                background-color: {DARK_BG};
                border-bottom: 1px solid {BORDER};
            }}
            #statusLabel {{
                color: {TEXT_MUTED};
                font-size: 12px;
            }}
            #folderInput {{
                background: #16162a;
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: {TEXT_PRIMARY};
                font-size: 13px;
            }}
            #folderInput:focus {{
                border-color: {ACCENT};
            }}
            #primaryBtn {{
                background: {ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 7px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            #primaryBtn:hover {{
                background: {ACCENT_HOVER};
            }}
            #primaryBtn:disabled {{
                background: #333355;
                color: #666;
            }}
            #secondaryBtn {{
                background: #2a2a44;
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 13px;
            }}
            #secondaryBtn:hover {{
                background: #33334d;
            }}
            #dangerBtn {{
                background: #4a1a1a;
                color: #f87171;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 13px;
            }}
            #dangerBtn:hover {{
                background: #5a2020;
            }}
            QProgressBar {{
                background: #2a2a44;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 3px;
            }}
            QSlider::groove:horizontal {{
                background: #2a2a44;
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 14px;
                height: 14px;
                border-radius: 7px;
                margin: -5px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT};
                border-radius: 2px;
            }}
            QSpinBox {{
                background: #16162a;
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px;
                color: {TEXT_PRIMARY};
            }}
            QLabel {{
                color: {TEXT_MUTED};
            }}
            #separator {{
                color: {BORDER};
            }}
            QScrollArea {{
                border: none;
            }}
            QScrollBar:vertical {{
                background: {DARK_BG};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #333355;
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QFrame[frameShape="4"] {{
                color: {BORDER};
            }}
        """)
