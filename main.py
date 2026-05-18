"""
main.py — Entry point. Run with: python main.py
"""

import sys
import multiprocessing

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


def main():
    # Required for ProcessPoolExecutor on Windows (freeze support)
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setApplicationName("Duplicate Image Scanner")

    from frontend.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
