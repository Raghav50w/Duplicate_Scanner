"""
Main window layout: folder picker, mode dropdown, threshold slider,
keeper toggle, scan trigger, progress label.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from backend import scanner
from . import styles
from .results_view import ResultsView


class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Duplicate Scanner")
        self.geometry("1100x750")
        self.configure(bg=styles.COLOR_BG)
        self.minsize(800, 500)

        self.selected_folder = tk.StringVar(value="No folder selected")
        self.detection_mode = tk.StringVar(value="Hash")
        self.threshold_value = tk.IntVar(value=5)
        self.keeper_preference = tk.StringVar(value="largest")

        self._setup_style()
        self._build_layout()

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=styles.COLOR_BG)
        style.configure("Panel.TFrame", background=styles.COLOR_BG_PANEL)
        style.configure(
            "TLabel", background=styles.COLOR_BG,
            foreground=styles.COLOR_TEXT, font=styles.FONT_NORMAL,
        )
        style.configure(
            "Heading.TLabel", background=styles.COLOR_BG,
            foreground=styles.COLOR_TEXT, font=styles.FONT_HEADING,
        )
        style.configure(
            "Muted.TLabel", background=styles.COLOR_BG,
            foreground=styles.COLOR_TEXT_MUTED, font=styles.FONT_SMALL,
        )
        style.configure(
            "Accent.TButton", font=styles.FONT_BUTTON,
            background=styles.COLOR_ACCENT, foreground="white",
            padding=(12, 8), borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", styles.COLOR_ACCENT_HOVER)],
        )
        style.configure(
            "TCombobox", fieldbackground=styles.COLOR_BG_CARD,
            background=styles.COLOR_BG_CARD, foreground=styles.COLOR_TEXT,
        )
        style.configure(
            "Horizontal.TScale", background=styles.COLOR_BG,
        )

    def _build_layout(self):
        control_panel = ttk.Frame(self, style="Panel.TFrame", padding=styles.PAD_LARGE)
        control_panel.pack(side="top", fill="x")

        # Folder picker row
        folder_row = ttk.Frame(control_panel, style="Panel.TFrame")
        folder_row.pack(fill="x", pady=(0, styles.PAD_MEDIUM))

        choose_btn = ttk.Button(
            folder_row, text="Choose Folder", style="Accent.TButton",
            command=self._choose_folder,
        )
        choose_btn.pack(side="left")

        folder_label = ttk.Label(
            folder_row, textvariable=self.selected_folder, style="Muted.TLabel",
        )
        folder_label.pack(side="left", padx=styles.PAD_MEDIUM)

        # Settings row
        settings_row = ttk.Frame(control_panel, style="Panel.TFrame")
        settings_row.pack(fill="x", pady=(0, styles.PAD_MEDIUM))

        ttk.Label(settings_row, text="Mode:", style="TLabel").pack(side="left")
        mode_dropdown = ttk.Combobox(
            settings_row, textvariable=self.detection_mode,
            values=["Hash"], state="readonly", width=10,
        )
        mode_dropdown.pack(side="left", padx=(styles.PAD_SMALL, styles.PAD_LARGE))

        ttk.Label(settings_row, text="Similarity threshold:", style="TLabel").pack(side="left")
        threshold_slider = ttk.Scale(
            settings_row, from_=0, to=20, orient="horizontal",
            variable=self.threshold_value, length=160,
            command=lambda v: self._sync_threshold_label(),
        )
        threshold_slider.pack(side="left", padx=(styles.PAD_SMALL, styles.PAD_SMALL))

        self.threshold_label = ttk.Label(settings_row, text="5", style="TLabel")
        self.threshold_label.pack(side="left", padx=(0, styles.PAD_LARGE))

        ttk.Label(settings_row, text="Keep:", style="TLabel").pack(side="left")
        keeper_dropdown = ttk.Combobox(
            settings_row, textvariable=self.keeper_preference,
            values=["largest", "smallest"], state="readonly", width=10,
        )
        keeper_dropdown.pack(side="left", padx=(styles.PAD_SMALL, styles.PAD_LARGE))

        self.scan_btn = ttk.Button(
            settings_row, text="Scan", style="Accent.TButton",
            command=self._start_scan,
        )
        self.scan_btn.pack(side="left")

        # Progress row
        self.progress_label = ttk.Label(control_panel, text="", style="Muted.TLabel")
        self.progress_label.pack(fill="x")

        # Results area
        self.results_view = ResultsView(self, keeper_preference=self.keeper_preference)
        self.results_view.pack(side="top", fill="both", expand=True)

    def _sync_threshold_label(self):
        self.threshold_label.config(text=str(self.threshold_value.get()))

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder.set(folder)

    def _start_scan(self):
        folder = self.selected_folder.get()
        if not folder or folder == "No folder selected":
            messagebox.showwarning("No folder", "Please choose a folder first.")
            return

        self.scan_btn.config(state="disabled")
        self.progress_label.config(text="Scanning... 0/0")
        self.results_view.clear()

        thread = threading.Thread(
            target=self._run_scan_thread, args=(folder,), daemon=True,
        )
        thread.start()

    def _run_scan_thread(self, folder: str):
        def progress_callback(current, total):
            self.after(0, lambda: self.progress_label.config(
                text=f"Scanning... {current}/{total}"
            ))

        try:
            groups = scanner.run_scan(
                folder,
                method="hash",
                hash_threshold=self.threshold_value.get(),
                progress_callback=progress_callback,
            )
        except Exception as e:
            self.after(0, lambda: self._on_scan_error(str(e)))
            return

        self.after(0, lambda: self._on_scan_complete(folder, groups))

    def _on_scan_complete(self, folder: str, groups: list):
        self.scan_btn.config(state="normal")
        self.progress_label.config(
            text=f"Done. Found {len(groups)} duplicate group(s)."
        )
        self.results_view.display_groups(groups, source_folder=folder)

    def _on_scan_error(self, message: str):
        self.scan_btn.config(state="normal")
        self.progress_label.config(text="Scan failed.")
        messagebox.showerror("Scan error", message)


def main():
    app = AppWindow()
    app.mainloop()