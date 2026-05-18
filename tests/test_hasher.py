"""
tests/test_hasher.py — Basic tests for the hasher module.
Run with: python -m pytest tests/
"""

import os
import tempfile
import pytest
from backend.hasher import scan_directory, find_exact_duplicates


def _write(path, content):
    with open(path, "wb") as f:
        f.write(content)


def test_scan_finds_images(tmp_path):
    _write(tmp_path / "a.jpg", b"fake")
    _write(tmp_path / "b.png", b"fake2")
    _write(tmp_path / "c.txt", b"not an image")
    found = scan_directory(str(tmp_path))
    assert len(found) == 2
    assert all(f.endswith((".jpg", ".png")) for f in found)


def test_exact_duplicates_detected(tmp_path):
    content = b"\x89PNG\r\n\x1a\n" + b"x" * 200
    _write(tmp_path / "a.png", content)
    _write(tmp_path / "b.png", content)
    _write(tmp_path / "c.png", b"different content here 123")
    paths = [str(tmp_path / f) for f in ("a.png", "b.png", "c.png")]
    exact_groups, remaining = find_exact_duplicates(paths)
    assert len(exact_groups) == 1
    assert len(exact_groups[0]) == 2


def test_unique_files_not_grouped(tmp_path):
    for i in range(5):
        _write(tmp_path / f"img{i}.jpg", bytes([i] * 100))
    paths = scan_directory(str(tmp_path))
    exact_groups, remaining = find_exact_duplicates(paths)
    assert len(exact_groups) == 0
