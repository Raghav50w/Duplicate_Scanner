"""
thumbnail_grid.py — Scrollable grid showing grouped duplicate images.

Each group gets a titled card with thumbnail previews and a "Send to Trash" button
for every image in the group (except the first, which is kept as the original).
"""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSizePolicy,
    QGridLayout, QSpacerItem,
)

try:
    from send2trash import send2trash
    _HAS_SEND2TRASH = True
except ImportError:
    _HAS_SEND2TRASH = False

THUMB_SIZE = 140
GROUP_PADDING = 16
EXACT_COLOR  = "#2d4a3e"   # dark green tint for exact duplicate headers
NEAR_COLOR   = "#3a3060"   # dark purple tint for near-duplicate headers


class ThumbnailCard(QFrame):
    """
    A single image card: thumbnail + filename + file size + delete button.
    """
    deleted = pyqtSignal(str)   # emits path when image is trashed

    def __init__(self, path: str, is_original: bool = False, parent=None):
        super().__init__(parent)
        self.path = path
        self._build_ui(is_original)

    def _build_ui(self, is_original: bool):
        self.setFixedWidth(THUMB_SIZE + 20)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        thumb_label = QLabel()
        thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setStyleSheet("background: #1a1a2e; border-radius: 4px;")

        pix = QPixmap(self.path)
        if pix.isNull():
            thumb_label.setText("?")
            thumb_label.setStyleSheet(
                "background:#2a2a2a; border-radius:4px; color:#888; font-size:24px;")
        else:
            thumb_label.setPixmap(
                pix.scaled(THUMB_SIZE, THUMB_SIZE,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(thumb_label)

        # Filename (truncated)
        name = Path(self.path).name
        if len(name) > 18:
            name = name[:15] + "..."
        name_lbl = QLabel(name)
        name_lbl.setToolTip(self.path)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet("font-size:11px; color:#aaa;")
        layout.addWidget(name_lbl)

        # File size
        try:
            size_bytes = os.path.getsize(self.path)
            size_str = _fmt_size(size_bytes)
        except OSError:
            size_str = "?"
        size_lbl = QLabel(size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_lbl.setStyleSheet("font-size:10px; color:#666;")
        layout.addWidget(size_lbl)

        # Keep / Delete indicator
        if is_original:
            badge = QLabel("KEEP")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "background:#1a4a2a; color:#4ade80; font-size:10px; "
                "border-radius:3px; padding:2px 6px;"
            )
            layout.addWidget(badge)
        else:
            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet(
                "QPushButton { background:#4a1a1a; color:#f87171; border:none; "
                "border-radius:4px; padding:4px; font-size:11px; }"
                "QPushButton:hover { background:#6a2020; }"
            )
            del_btn.clicked.connect(self._delete)
            layout.addWidget(del_btn)

    def _delete(self):
        if _HAS_SEND2TRASH:
            try:
                send2trash(self.path)
            except Exception as e:
                print(f"[delete error] {self.path}: {e}")
                return
        else:
            try:
                os.remove(self.path)
            except Exception as e:
                print(f"[delete error] {self.path}: {e}")
                return

        from backend.cache import delete_entry
        delete_entry(self.path)
        self.deleted.emit(self.path)
        self.setVisible(False)


class GroupCard(QFrame):
    """
    A card for one duplicate group: header + row of ThumbnailCards.
    """
    def __init__(self, group: list[str], label: str,
                 is_exact: bool = False, parent=None):
        super().__init__(parent)
        self.group = list(group)
        self._build_ui(label, is_exact)

    def _build_ui(self, label: str, is_exact: bool):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        header_color = EXACT_COLOR if is_exact else NEAR_COLOR

        layout = QVBoxLayout(self)
        layout.setContentsMargins(GROUP_PADDING, GROUP_PADDING,
                                  GROUP_PADDING, GROUP_PADDING)
        layout.setSpacing(10)

        # Header row
        header = QLabel(label)
        header.setStyleSheet(
            f"background:{header_color}; color:#e2e8f0; font-size:13px; "
            f"font-weight:500; border-radius:6px; padding:6px 12px;"
        )
        layout.addWidget(header)

        # Thumbnails row
        row = QHBoxLayout()
        row.setSpacing(10)
        for i, path in enumerate(self.group):
            card = ThumbnailCard(path, is_original=(i == 0))
            card.deleted.connect(self._on_deleted)
            row.addWidget(card)
        row.addStretch()
        layout.addLayout(row)

    def _on_deleted(self, path: str):
        if path in self.group:
            self.group.remove(path)
        if len(self.group) <= 1:
            self.setVisible(False)


class ThumbnailGrid(QScrollArea):
    """
    The main scrollable area that holds all GroupCards.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._layout    = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(16)
        self._layout.setContentsMargins(16, 16, 16, 16)

        self.setWidget(self._container)
        self._show_empty_state()

    def _show_empty_state(self):
        lbl = QLabel("No duplicates found yet.\nSelect a folder and click Scan.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#555; font-size:14px; padding:60px;")
        self._empty_label = lbl
        self._layout.addWidget(lbl)

    def populate(self, exact_groups: list[list[str]],
                 near_groups: list[list[str]]):
        """Clear current content and render new results."""
        # Clear all widgets
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not exact_groups and not near_groups:
            self._show_empty_state()
            return

        total = len(exact_groups) + len(near_groups)
        summary = QLabel(
            f"Found {len(exact_groups)} exact duplicate groups and "
            f"{len(near_groups)} near-duplicate groups  ({total} total)"
        )
        summary.setStyleSheet(
            "color:#94a3b8; font-size:13px; padding:4px 0 12px 0;")
        self._layout.addWidget(summary)

        for i, group in enumerate(exact_groups):
            sizes = [_fmt_size(os.path.getsize(p)) for p in group
                     if os.path.exists(p)]
            label = (f"Exact duplicates — group {i+1} of {len(exact_groups)}  "
                     f"({len(group)} files, {sizes[0] if sizes else '?'} each)")
            card = GroupCard(group, label, is_exact=True)
            self._layout.addWidget(card)

        for i, group in enumerate(near_groups):
            label = (f"Near duplicates — group {i+1} of {len(near_groups)}  "
                     f"({len(group)} files)")
            card = GroupCard(group, label, is_exact=False)
            self._layout.addWidget(card)

        self._layout.addStretch()


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
