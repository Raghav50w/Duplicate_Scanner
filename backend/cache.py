"""
cache.py — SQLite-backed cache for file hashes and CNN vectors.
Stores: path, file size, mtime, sha256, and 4 rotation vectors.
"""

import sqlite3
import pickle
import os
import threading
from pathlib import Path
from typing import Optional

import numpy as np

DB_PATH = Path(__file__).parent.parent / "cache.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_cache (
            path      TEXT PRIMARY KEY,
            file_size INTEGER,
            mtime     REAL,
            sha256    TEXT,
            vectors   BLOB
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sha256 ON file_cache(sha256)")
    conn.commit()


def get_entry(path: str) -> Optional[dict]:
    """
    Return cached entry for path if mtime still matches, else None.
    Entry dict keys: path, file_size, mtime, sha256, vectors (np.ndarray shape [4, D])
    """
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return None

    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM file_cache WHERE path = ?", (path,)
    ).fetchone()

    if row is None:
        return None

    if abs(row["mtime"] - stat.st_mtime) > 1e-3:
        return None

    vectors = pickle.loads(row["vectors"]) if row["vectors"] else None
    return {
        "path": row["path"],
        "file_size": row["file_size"],
        "mtime": row["mtime"],
        "sha256": row["sha256"],
        "vectors": vectors,
    }


def set_entry(path: str, file_size: int, mtime: float,
              sha256: str, vectors: Optional[np.ndarray]):
    """Upsert a cache entry."""
    blob = pickle.dumps(vectors) if vectors is not None else None
    conn = _get_conn()
    conn.execute("""
        INSERT INTO file_cache (path, file_size, mtime, sha256, vectors)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            file_size = excluded.file_size,
            mtime     = excluded.mtime,
            sha256    = excluded.sha256,
            vectors   = excluded.vectors
    """, (path, file_size, mtime, sha256, blob))
    conn.commit()


def delete_entry(path: str):
    """Remove a cache entry (called after user deletes an image)."""
    conn = _get_conn()
    conn.execute("DELETE FROM file_cache WHERE path = ?", (path,))
    conn.commit()


def clear_all():
    """Wipe the entire cache (for testing / reset)."""
    conn = _get_conn()
    conn.execute("DELETE FROM file_cache")
    conn.commit()
