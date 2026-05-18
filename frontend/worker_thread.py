"""
worker_thread.py — QThread that runs the pipeline without blocking the UI.

Emits Qt signals for progress updates and completion.
The UI connects to these signals; it never calls pipeline functions directly.
"""

from PyQt6.QtCore import QThread, pyqtSignal


class ScanWorker(QThread):
    # Signals — connected by MainWindow
    progress   = pyqtSignal(str, int, int, str)   # stage, done, total, message
    finished   = pyqtSignal(list, list)            # exact_groups, near_groups
    error      = pyqtSignal(str)                   # error message

    def __init__(self, folder: str, threshold: float,
                 hash_workers: int, cnn_workers: int):
        super().__init__()
        self.folder       = folder
        self.threshold    = threshold
        self.hash_workers = hash_workers
        self.cnn_workers  = cnn_workers
        self._cancelled   = [False]

    def cancel(self):
        self._cancelled[0] = True

    def run(self):
        try:
            from backend.pipeline import run_pipeline

            exact_groups, near_groups = run_pipeline(
                folder=self.folder,
                threshold=self.threshold,
                max_hash_workers=self.hash_workers,
                max_cnn_workers=self.cnn_workers,
                progress_cb=self._on_progress,
                cancelled_flag=self._cancelled,
            )
            if not self._cancelled[0]:
                self.finished.emit(exact_groups, near_groups)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, stage: str, done: int, total: int, message: str):
        self.progress.emit(stage, done, total, message)
