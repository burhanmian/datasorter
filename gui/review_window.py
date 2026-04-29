"""
Window 5 — Manual Review Tool.
Shows low-confidence files with their middle-slice preview so the user
can confirm or reassign the body part classification.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional
import numpy as np
import customtkinter as ctk
from PIL import Image, ImageTk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import (
    apply_theme, make_title, make_subtitle, make_card,
    make_primary_button, make_secondary_button, ACCENT, MUTED, SUCCESS, WARNING,
)
from core.body_part_detector import BODY_PART_KEYWORDS
from utils.logger import get_logger

log = get_logger()

BODY_PARTS = sorted(BODY_PART_KEYWORDS.keys()) + ["Other_Unknown"]


class ReviewWindow(ctk.CTkToplevel):
    """
    Opens as a child window showing all files in the _Review_Needed/ folder.
    Lets the user reassign each file to the correct body part and move it.
    """

    def __init__(self, parent, destination_folder: str, config):
        super().__init__(parent)
        self.dest = Path(destination_folder)
        self.cfg = config

        apply_theme(config.theme)
        self.title("DICOM Organizer — Manual Review")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.grab_set()

        self._review_dir = self.dest / "_Review_Needed"
        self._files = list(self._review_dir.glob("*.dcm")) + list(self._review_dir.glob("*"))
        self._files = [f for f in self._files if f.is_file()]
        self._current_idx = 0
        self._assignments: dict[str, str] = {}   # file path → chosen body part

        self._build_ui()
        if self._files:
            self._show_file(0)
        else:
            self._show_empty()

    def _build_ui(self):
        # Left — file list
        left = ctk.CTkFrame(self, width=240, corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        make_title(left, "Review Files", size=14).pack(padx=12, pady=(14, 6))
        ctk.CTkLabel(left, text=f"{len(self._files)} files need review",
                     font=ctk.CTkFont(size=11), text_color=WARNING).pack(padx=12)

        self._file_list = ctk.CTkScrollableFrame(left)
        self._file_list.pack(fill="both", expand=True, padx=4, pady=8)

        self._file_btns: list[ctk.CTkButton] = []
        for i, f in enumerate(self._files):
            btn = ctk.CTkButton(
                self._file_list, text=f.name[:30],
                anchor="w", font=ctk.CTkFont(size=11),
                fg_color="transparent", hover_color=ACCENT,
                command=lambda idx=i: self._show_file(idx),
            )
            btn.pack(fill="x", pady=1)
            self._file_btns.append(btn)

        # Right — viewer
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=16, pady=16)

        self._title_lbl = make_title(right, "Select a file →", size=15)
        self._title_lbl.pack(anchor="w")

        self._info_lbl = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=11),
                                      text_color=MUTED, justify="left")
        self._info_lbl.pack(anchor="w", pady=(4, 8))

        # Image canvas
        img_card = make_card(right)
        img_card.pack(fill="x", pady=(0, 12))
        self._img_canvas_label = ctk.CTkLabel(img_card, text="No preview", width=400, height=300)
        self._img_canvas_label.pack(padx=12, pady=12)

        # Body part picker
        pick_row = ctk.CTkFrame(right, fg_color="transparent")
        pick_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(pick_row, text="Assign to:", font=ctk.CTkFont(size=13, weight="bold")).pack(
            side="left", padx=(0, 10)
        )
        self._bp_var = ctk.StringVar(value=BODY_PARTS[0])
        self._bp_menu = ctk.CTkOptionMenu(
            pick_row, values=BODY_PARTS, variable=self._bp_var, width=200,
        )
        self._bp_menu.pack(side="left")

        # Action buttons
        action_row = ctk.CTkFrame(right, fg_color="transparent")
        action_row.pack(fill="x")

        make_primary_button(action_row, "✓ Confirm & Move", command=self._confirm_and_move,
                            width=180).pack(side="left", padx=(0, 10))
        make_secondary_button(action_row, "⏭ Skip", command=self._skip, width=100).pack(side="left")

        # Progress at bottom
        self._progress_lbl = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=11), text_color=MUTED)
        self._progress_lbl.pack(anchor="w", pady=(12, 0))

    def _show_file(self, idx: int):
        if not self._files or idx >= len(self._files):
            return
        self._current_idx = idx
        fpath = self._files[idx]

        # Highlight in list
        for i, btn in enumerate(self._file_btns):
            btn.configure(fg_color=ACCENT if i == idx else "transparent")

        self._title_lbl.configure(text=fpath.name[:60])
        self._progress_lbl.configure(text=f"File {idx+1} of {len(self._files)}")

        # Read metadata for info
        try:
            from core.dicom_reader import read_dicom
            meta = read_dicom(fpath)
            info = (
                f"Modality: {meta.modality}   "
                f"Body part tag: {meta.body_part_examined or '—'}   "
                f"Series: {meta.series_description or '—'}"
            )
            self._info_lbl.configure(text=info)
        except Exception:
            self._info_lbl.configure(text="Could not read metadata.")

        # Generate preview
        self._show_preview(fpath)

    def _show_preview(self, fpath: Path):
        try:
            import pydicom
            ds = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array.astype(np.float32)
            if arr.ndim == 3:
                arr = arr[arr.shape[0] // 2]
            mn, mx = arr.min(), arr.max()
            if mx - mn > 0:
                arr = (arr - mn) / (mx - mn) * 255.0
            else:
                arr = np.zeros_like(arr)
            img = Image.fromarray(arr.astype(np.uint8)).convert("RGB").resize((384, 320))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(384, 320))
            self._img_canvas_label.configure(image=ctk_img, text="")
            self._img_canvas_label._image = ctk_img
        except Exception as exc:
            self._img_canvas_label.configure(text=f"Preview unavailable:\n{exc}", image=None)

    def _confirm_and_move(self):
        if not self._files:
            return
        fpath = self._files[self._current_idx]
        body_part = self._bp_var.get()

        # Determine target folder
        mod_label = "MRI"
        try:
            import pydicom
            ds = pydicom.dcmread(str(fpath), force=True)
            mod = str(getattr(ds, "Modality", "")).upper()
            mod_label = "MRI" if mod == "MR" else ("CT" if mod == "CT" else mod)
        except Exception:
            pass

        target_dir = self.dest / mod_label / body_part
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / fpath.name

        try:
            shutil.move(str(fpath), str(target))
            log.info("Manually moved %s → %s", fpath.name, target)
            self._assignments[str(fpath)] = body_part
            self._file_btns[self._current_idx].configure(text_color=SUCCESS)
            self._skip()
        except Exception as exc:
            log.error("Move failed: %s", exc)

    def _skip(self):
        if self._current_idx < len(self._files) - 1:
            self._show_file(self._current_idx + 1)
        else:
            self._title_lbl.configure(text="✅ All files reviewed!")
            self._info_lbl.configure(text=f"Manually assigned: {len(self._assignments)} files.")

    def _show_empty(self):
        ctk.CTkLabel(self, text="No files in _Review_Needed/ folder.",
                     font=ctk.CTkFont(size=14)).pack(expand=True)
