"""
Scrollable thumbnail groups, selection handling, deletion.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from backend import file_ops
from . import styles


class ResultsView(ttk.Frame):
    def __init__(self, parent, keeper_preference: tk.StringVar):
        super().__init__(parent, style="TFrame")
        self.keeper_preference = keeper_preference
        self.source_folder = None
        self.groups = []          # list[list[str]]
        self.selected_paths = set()
        self.thumbnail_refs = []  # keep PhotoImage references alive
        self.group_frames = []    # frames per group, for removal on delete

        self._build_scroll_area()
        self._build_footer()

    def _build_scroll_area(self):
        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True, padx=styles.PAD_LARGE, pady=styles.PAD_MEDIUM)

        self.canvas = tk.Canvas(container, bg=styles.COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.inner_frame = ttk.Frame(self.canvas, style="TFrame")

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _build_footer(self):
        footer = ttk.Frame(self, style="Panel.TFrame", padding=styles.PAD_MEDIUM)
        footer.pack(side="bottom", fill="x")

        self.summary_label = ttk.Label(footer, text="", style="Muted.TLabel")
        self.summary_label.pack(side="left")

        delete_btn = ttk.Button(
            footer, text="Delete Selected", style="Accent.TButton",
            command=self._delete_selected,
        )
        delete_btn.pack(side="right")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def clear(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
        self.groups = []
        self.selected_paths = set()
        self.thumbnail_refs = []
        self.group_frames = []
        self.summary_label.config(text="")

    def display_groups(self, groups: list, source_folder: str):
        self.clear()
        self.groups = groups
        self.source_folder = source_folder

        if not groups:
            ttk.Label(
                self.inner_frame, text="No duplicates found.", style="Muted.TLabel"
            ).pack(pady=styles.PAD_LARGE)
            return

        for group_index, group in enumerate(groups):
            self._render_group(group_index, group)

        self._update_summary()

    def _suggested_keeper(self, group: list) -> str:
        pref = self.keeper_preference.get()
        sizes = [(p, file_ops.get_file_size(p)) for p in group]
        if pref == "largest":
            return max(sizes, key=lambda x: x[1])[0]
        return min(sizes, key=lambda x: x[1])[0]

    def _render_group(self, group_index: int, group: list):
        keeper = self._suggested_keeper(group)

        group_frame = ttk.Frame(self.inner_frame, style="Panel.TFrame", padding=styles.PAD_MEDIUM)
        group_frame.pack(fill="x", pady=styles.PAD_SMALL, padx=styles.PAD_SMALL)
        self.group_frames.append((group_frame, group_index))

        header = ttk.Label(
            group_frame, text=f"Group {group_index + 1} — {len(group)} images",
            style="Heading.TLabel",
        )
        header.pack(anchor="w", pady=(0, styles.PAD_SMALL))

        thumbs_row = ttk.Frame(group_frame, style="Panel.TFrame")
        thumbs_row.pack(fill="x")

        for path in group:
            self._render_thumbnail(thumbs_row, path, is_keeper=(path == keeper),
                                    group_index=group_index)

        select_all_btn = ttk.Button(
            group_frame, text="Select all except keeper",
            command=lambda g=group, k=keeper: self._select_all_except_keeper(g, k),
        )
        select_all_btn.pack(anchor="w", pady=(styles.PAD_SMALL, 0))

    def _render_thumbnail(self, parent, path: str, is_keeper: bool, group_index: int):
        card = tk.Frame(parent, bg=styles.COLOR_BG_CARD, bd=2, relief="flat")
        card.pack(side="left", padx=styles.PAD_SMALL, pady=styles.PAD_SMALL)

        try:
            with Image.open(path) as img:
                img = img.copy()
                img.thumbnail(styles.THUMBNAIL_SIZE)
                photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None

        self.thumbnail_refs.append(photo)

        img_label = tk.Label(card, image=photo, bg=styles.COLOR_BG_CARD)
        img_label.pack()

        if is_keeper:
            badge = tk.Label(
                card, text="KEEPER", bg=styles.COLOR_KEEPER_BADGE,
                fg="white", font=styles.FONT_SMALL,
            )
            badge.pack(fill="x")

        filename = os.path.basename(path)
        w, h = file_ops.get_image_resolution(path)
        size_kb = file_ops.get_file_size(path) / 1024

        info_text = f"{filename}\n{w}x{h}  {size_kb:.0f} KB"
        info_label = tk.Label(
            card, text=info_text, bg=styles.COLOR_BG_CARD,
            fg=styles.COLOR_TEXT_MUTED, font=styles.FONT_SMALL,
            justify="left",
        )
        info_label.pack(anchor="w", padx=styles.PAD_SMALL)

        def toggle(event=None):
            self._toggle_selection(path, card)

        card.bind("<Button-1>", toggle)
        img_label.bind("<Button-1>", toggle)

        if path in self.selected_paths:
            card.config(bd=2, relief="solid", highlightbackground=styles.COLOR_SELECTED_BORDER)

    def _toggle_selection(self, path: str, card_widget: tk.Frame):
        if path in self.selected_paths:
            self.selected_paths.discard(path)
            card_widget.config(bg=styles.COLOR_BG_CARD, highlightthickness=0)
        else:
            self.selected_paths.add(path)
            card_widget.config(
                highlightbackground=styles.COLOR_SELECTED_BORDER,
                highlightthickness=2,
            )
        self._update_summary()

    def _select_all_except_keeper(self, group: list, keeper: str):
        for path in group:
            if path != keeper:
                self.selected_paths.add(path)
        # Re-render to reflect selection visually
        self.display_groups(self.groups, self.source_folder)

    def _update_summary(self):
        total_size = sum(file_ops.get_file_size(p) for p in self.selected_paths)
        mb = total_size / (1024 * 1024)
        self.summary_label.config(
            text=f"{len(self.selected_paths)} selected — {mb:.1f} MB would be freed"
        )

    def _delete_selected(self):
        if not self.selected_paths:
            messagebox.showinfo("Nothing selected", "Select images to delete first.")
            return

        confirm = messagebox.askyesno(
            "Confirm delete",
            f"Move {len(self.selected_paths)} image(s) to _deleted_review?",
        )
        if not confirm:
            return

        to_delete = list(self.selected_paths)
        moved = file_ops.move_to_review_folder(to_delete, self.source_folder)

        # Remove deleted paths from groups; drop groups that fall to size 1
        new_groups = []
        for group in self.groups:
            remaining = [p for p in group if p not in to_delete]
            if len(remaining) > 1:
                new_groups.append(remaining)

        freed_bytes = sum(file_ops.get_file_size(p) for p in moved)
        freed_mb = freed_bytes / (1024 * 1024)

        self.selected_paths = set()
        self.display_groups(new_groups, self.source_folder)
        self.summary_label.config(
            text=f"Moved {len(moved)} image(s) to _deleted_review — {freed_mb:.1f} MB"
        )