"""FastAPI app: six endpoints and the static page."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import actions, db, scanner, thumbs
from app.config import (
    COSINE_DEFAULT,
    COSINE_MAX,
    COSINE_MIN,
    CANDIDATE_HAMMING_GATE,
    FAST_HAMMING_THRESHOLD,
    HASH_BITS,
    WEB_DIR,
)
from app.matching import assemble_groups, hamming_to_similarity

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s"
)
log = logging.getLogger(__name__)

app = FastAPI(title="GallerySweep")

# Run in a subprocess: tkinter misbehaves when driven from a server worker
# thread, and a subprocess that hangs on a modal dialog cannot take the app
# down with it.
_FOLDER_DIALOG = """
import tkinter
from tkinter import filedialog

root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
chosen = filedialog.askdirectory(title="Choose a photo folder")
root.destroy()
print(chosen or "")
"""


class ScanRequest(BaseModel):
    folder: str
    mode: str = "fast"


class DeleteRequest(BaseModel):
    image_ids: list[int]


@app.get("/api/config")
def get_config() -> dict:
    """What the page needs to render its controls without hardcoding numbers."""
    return {
        "fast_hamming_threshold": FAST_HAMMING_THRESHOLD,
        "candidate_gate": CANDIDATE_HAMMING_GATE,
        "fast_similarity": round(hamming_to_similarity(FAST_HAMMING_THRESHOLD), 4),
        "min_similarity": round(hamming_to_similarity(CANDIDATE_HAMMING_GATE), 4),
        "cosine_min": COSINE_MIN,
        "cosine_max": COSINE_MAX,
        "cosine_default": COSINE_DEFAULT,
        "smart_available": False,  # Phase 3 flips this
    }


@app.post("/api/pick-folder")
def pick_folder() -> dict:
    try:
        result = subprocess.run(
            [sys.executable, "-c", _FOLDER_DIALOG],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="the folder dialog timed out")
    if result.returncode != 0:
        raise HTTPException(
            status_code=500, detail=result.stderr.strip() or "the folder dialog failed"
        )
    return {"folder": result.stdout.strip()}


@app.post("/api/scan")
def start_scan(request: ScanRequest) -> dict:
    if request.mode == "smart":
        raise HTTPException(status_code=400, detail="Smart mode arrives in Phase 3")
    if request.mode != "fast":
        raise HTTPException(status_code=400, detail=f"unknown mode {request.mode!r}")

    folder = Path(request.folder.strip('" ')).expanduser()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"not a folder: {folder}")

    try:
        scanner.start_scan(folder.resolve(), request.mode)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return scanner.STATE.as_dict()


@app.get("/api/progress")
def progress() -> dict:
    return scanner.STATE.as_dict()


@app.get("/api/groups")
def groups(threshold: float | None = Query(default=None, ge=0.0, le=1.0)) -> dict:
    """Groups at the given normalized similarity, rebuilt from cached pairs.

    `similarity` is 0-1 and engine-independent, so turning on the CNN in Phase 3
    needs no frontend change.
    """
    if threshold is None:
        max_hamming = FAST_HAMMING_THRESHOLD
    else:
        # The pairs table only holds what passed the candidate gate, so asking
        # for anything looser than the gate cannot return more.
        max_hamming = min(int((1.0 - threshold) * HASH_BITS), CANDIDATE_HAMMING_GATE)

    conn = db.connect()
    try:
        db.init_db(conn)
        rows = db.load_pairs(conn, max_hamming)
        image_ids = sorted({r["image_a"] for r in rows} | {r["image_b"] for r in rows})
        records = db.images_by_id(conn, image_ids)
    finally:
        conn.close()

    images = {
        image_id: {
            "path": row["path"],
            "name": Path(row["path"]).name,
            "width": row["width"],
            "height": row["height"],
            "size": row["size"],
            "mtime": row["mtime"],
        }
        for image_id, row in records.items()
    }
    scored = [
        (r["image_a"], r["image_b"], hamming_to_similarity(r["hamming"])) for r in rows
    ]
    found = assemble_groups(scored, images)

    return {
        "threshold": round(hamming_to_similarity(max_hamming), 4),
        "max_hamming": max_hamming,
        "groups": found,
        "group_count": len(found),
        "file_count": sum(len(g["files"]) for g in found),
        "selected_count": sum(
            1 for g in found for f in g["files"] if not f["keep"]
        ),
        "reclaimable": sum(g["reclaimable"] for g in found),
    }


@app.get("/api/thumb/{image_id}")
def thumb(image_id: int) -> FileResponse:
    conn = db.connect()
    try:
        db.init_db(conn)
        path = db.image_path(conn, image_id)
    finally:
        conn.close()
    if path is None:
        raise HTTPException(status_code=404, detail="unknown image")
    try:
        return FileResponse(thumbs.ensure_thumb(image_id, path), media_type="image/webp")
    except Exception as exc:  # noqa: BLE001 - a broken file is a 404, not a 500
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/delete")
def delete(request: DeleteRequest) -> dict:
    if not request.image_ids:
        return {"deleted": 0, "freed_bytes": 0, "failed": []}
    conn = db.connect()
    try:
        db.init_db(conn)
        return actions.delete_images(conn, request.image_ids)
    finally:
        conn.close()


# Mounted last: a mount at "/" would otherwise swallow every route above it.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    import uvicorn

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
