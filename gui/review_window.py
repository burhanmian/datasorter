"""
Window 5 — Manual Review Tool.
Shows low-confidence files with middle-slice preview so the user
can confirm or reassign body-part classifications.

Keyboard shortcuts:
  ←  /  →   previous / next file
  Enter      confirm & move current file
  Delete     skip current file
"""
from __future__ import annotations

import shutil
from pathlib import Path
import numpy as np
import customtkinter as ctk
from PIL import Image

from gui.theme import (
    make_title, make_card,
    make_primary_button, make_secondary_button,
    ACCENT, MUTED, SUCCESS, WARNING,
)
from core.body_part_detector import BODY_PART_KEYWORDS
from utils.logger import get_logger

log = get_logger()

BODY_PARTS = sorted(BODY_PART_KEYWORDS.keys()) + ["Other_Unknown"]

# Confidence thresholds → badge colours
_BADGE_COLOURS = [
    (85, "#2ECC71"),   # green  — metadata
    (70, "#F39C12"),   # amber  — AI
    (50, "#E74C3C"),   # red    — heuristic
    (0,  "#7F8C8D"),   # grey   — unknown
]


def _conf_colour(score: float | None) -> str:
    if score is None:
        return _BADGE_COLOURS[-1][1]
    for threshold, colour in _BADGE_COLOURS:
        if score >= threshold:
            return colour
    return _BADGE_COLOURS[-1][1]


class ReviewWindow(ctk.CTkToplevel):
    """
    Child window listing all files in _Review_Needed/.
    Lets the user reassign each file to the correct body part.
    """

    def __init__(self, parent, destination_folder: str, config):
        super().__init__(parent)
        self.dest = Path(destination_folder)
        self.cfg  = config

        self.title("DICOM Organizer — Manual Review")
        self.geometry("1160x740")
        self.minsize(900, 600)
        self.grab_set()

        self._review_dir = self.dest / "_Review_Needed"
        self._files: list[Path] = [
            f for f in sorted(self._review_dir.iterdir())
            if f.is_file()
        ] if self._review_dir.exists() else []

        self._current_idx = 0
        self._done: set[int] = set()          # indices already confirmed
        self._confidence_cache: dict[str, float | None] = {}

        self._build_ui()
        self._bind_keys()

        if self._files:
            self._show_file(0)
        else:
            self._show_empty()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Left panel: scrollable file list ──────────────────────────────────
        left = ctk.CTkFrame(self, width=260, corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        make_title(left, "Review Files", size=14).pack(padx=12, pady=(14, 4))

        count_lbl = ctk.CTkLabel(
            left,
            text=f"{len(self._files)} file{'s' if len(self._files) != 1 else ''} need review",
            font=ctk.CTkFont(size=11), text_color=WARNING,
        )
        count_lbl.pack(padx=12, pady=(0, 6))

        # Keyboard hint
        ctk.CTkLabel(
            left,
            text="← → navigate  ·  Enter confirm  ·  Del skip",
            font=ctk.CTkFont(size=10), text_color=MUTED,
        ).pack(padx=12, pady=(0, 8))

        self._file_list = ctk.CTkScrollableFrame(left)
        self._file_list.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        self._file_btns: list[ctk.CTkButton] = []
        for i, f in enumerate(self._files):
            btn = ctk.CTkButton(
                self._file_list,
                text=f.name[:32],
                anchor="w",
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                hover_color=ACCENT,
                command=lambda idx=i: self._show_file(idx),
            )
            btn.pack(fill="x", pady=1)
            self._file_btns.append(btn)

        # Batch-confirm at bottom of left panel
        make_primary_button(
            left, "✓ Confirm All Remaining",
            command=self._batch_confirm, width=220,
        ).pack(padx=16, pady=(0, 12))

        # ── Right panel: viewer ───────────────────────────────────────────────
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=16, pady=16)

        # Title + confidence badge on same row
        title_row = ctk.CTkFrame(right, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 4))

        self._title_lbl = make_title(title_row, "Select a file →", size=15)
        self._title_lbl.pack(side="left")

        self._conf_badge = ctk.CTkLabel(
            title_row, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=MUTED, corner_radius=8, text_color="white",
            width=90,
        )
        self._conf_badge.pack(side="left", padx=(14, 0))

        # Metadata info line
        self._info_lbl = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=11), text_color=MUTED, justify="left",
        )
        self._info_lbl.pack(anchor="w", pady=(0, 10))

        # Image preview card
        img_card = make_card(right)
        img_card.pack(fill="x", pady=(0, 12))
        self._img_lbl = ctk.CTkLabel(
            img_card, text="No preview", width=400, height=300,
        )
        self._img_lbl.pack(padx=12, pady=12)

        # Body-part picker
        pick_row = ctk.CTkFrame(right, fg_color="transparent")
        pick_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            pick_row, text="Assign to:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(0, 10))

        self._bp_var = ctk.StringVar(value=BODY_PARTS[0])
        self._bp_menu = ctk.CTkOptionMenu(
            pick_row, values=BODY_PARTS, variable=self._bp_var, width=200,
        )
        self._bp_menu.pack(side="left")

        # Action buttons
        action_row = ctk.CTkFrame(right, fg_color="transparent")
        action_row.pack(fill="x")

        make_primary_button(
            action_row, "✓  Confirm & Move",
            command=self._confirm_and_move, width=180,
        ).pack(side="left", padx=(0, 10))

        make_secondary_button(
            action_row, "⏭  Skip",
            command=self._skip, width=100,
        ).pack(side="left", padx=(0, 10))

        # Prev / Next navigation buttons
        nav_row = ctk.CTkFrame(right, fg_color="transparent")
        nav_row.pack(fill="x", pady=(10, 0))

        make_secondary_button(nav_row, "←  Prev", command=self._prev, width=110).pack(side="left", padx=(0, 8))
        make_secondary_button(nav_row, "Next  →", command=self._next, width=110).pack(side="left")

        # Progress label
        self._progress_lbl = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=11), text_color=MUTED,
        )
        self._progress_lbl.pack(anchor="w", pady=(12, 0))

    # ── Keyboard bindings ─────────────────────────────────────────────────────

    def _bind_keys(self):
        self.bind("<Left>",   lambda e: self._prev())
        self.bind("<Right>",  lambda e: self._next())
        self.bind("<Return>", lambda e: self._confirm_and_move())
        self.bind("<Delete>", lambda e: self._skip())

    # ── File display ──────────────────────────────────────────────────────────

    def _show_file(self, idx: int):
        if not self._files or not (0 <= idx < len(self._files)):
            return
        self._current_idx = idx
        fpath = self._files[idx]

        # Highlight list button
        for i, btn in enumerate(self._file_btns):
            if i in self._done:
                btn.configure(fg_color="transparent", text_color=SUCCESS)
            else:
                btn.configure(
                    fg_color=ACCENT if i == idx else "transparent",
                    text_color="white",
                )

        self._title_lbl.configure(text=fpath.name[:60])
        self._progress_lbl.configure(
            text=f"File {idx + 1} of {len(self._files)}   "
                 f"({len(self._done)} confirmed, {len(self._files) - len(self._done)} remaining)"
        )

        # Read metadata
        conf: float | None = None
        try:
            from core.dicom_reader import read_dicom
            meta = read_dicom(fpath)
            conf = getattr(meta, "confidence", None)
            self._confidence_cache[str(fpath)] = conf
            info_parts = [
                f"Modality: {meta.modality or '—'}",
                f"Body part tag: {meta.body_part_examined or '—'}",
                f"Series: {meta.series_description or '—'}",
            ]
            self._info_lbl.configure(text="   ".join(info_parts))
            # Pre-select body part from metadata if available
            if meta.body_part_examined:
                bp = meta.body_part_examined.title().replace(" ", "_")
                if bp in BODY_PARTS:
                    self._bp_var.set(bp)
        except Exception:
            self._info_lbl.configure(text="Could not read metadata.")

        # Confidence badge
        colour = _conf_colour(conf)
        score_text = f"  {conf:.0f} %  " if conf is not None else "  ? %  "
        self._conf_badge.configure(text=score_text, fg_color=colour)

        self._show_preview(fpath)

    def _show_preview(self, fpath: Path):
        try:
            import pydicom
            ds  = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array.astype(np.float32)
            if arr.ndim == 3:
                arr = arr[arr.shape[0] // 2]
            mn, mx = arr.min(), arr.max()
            arr = (arr - mn) / (mx - mn) * 255.0 if mx > mn else np.zeros_like(arr)
            img    = Image.fromarray(arr.astype(np.uint8)).convert("RGB").resize((400, 320))
            ck_img = ctk.CTkImage(light_image=img, dark_image=img, size=(400, 320))
            self._img_lbl.configure(image=ck_img, text="")
            self._img_lbl._image = ck_img          # keep reference
        except Exception as exc:
            self._img_lbl.configure(text=f"Preview unavailable:\n{exc}", image=None)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _confirm_and_move(self):
        if not self._files or self._current_idx in self._done:
            return
        fpath     = self._files[self._current_idx]
        body_part = self._bp_var.get()
        self._move_file(fpath, body_part)
        self._done.add(self._current_idx)
        if self._file_btns:
            self._file_btns[self._current_idx].configure(text_color=SUCCESS, fg_color="transparent")
        self._next()

    def _move_file(self, fpath: Path, body_part: str):
        mod_label = "Other"
        try:
            import pydicom
            ds  = pydicom.dcmread(str(fpath), force=True)
            mod = str(getattr(ds, "Modality", "")).upper()
            mod_label = "MRI" if mod == "MR" else ("CT" if mod == "CT" else (mod or "Other"))
        except Exception:
            pass

        target_dir = self.dest / mod_label / body_part
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / fpath.name
        try:
            shutil.move(str(fpath), str(target))
            log.info("Manual review: moved %s → %s/%s", fpath.name, mod_label, body_part)
        except Exception as exc:
            log.error("Move failed for %s: %s", fpath.name, exc)

    def _batch_confirm(self):
        """Move all not-yet-confirmed files using the currently selected body part."""
        bp = self._bp_var.get()
        confirmed = 0
        for i, fpath in enumerate(self._files):
            if i in self._done:
                continue
            self._move_file(fpath, bp)
            self._done.add(i)
            if i < len(self._file_btns):
                self._file_btns[i].configure(text_color=SUCCESS, fg_color="transparent")
            confirmed += 1

        self._title_lbl.configure(text="✅  Batch confirm complete")
        self._info_lbl.configure(
            text=f"Moved {confirmed} file{'s' if confirmed != 1 else ''} to {bp}."
        )
        self._conf_badge.configure(text="", fg_color=MUTED)
        self._progress_lbl.configure(
            text=f"All {len(self._files)} files confirmed."
        )

    def _skip(self):
        self._next()

    def _next(self):
        nxt = self._current_idx + 1
        if nxt < len(self._files):
            self._show_file(nxt)
        else:
            self._title_lbl.configure(text="✅  All files reviewed!")
            self._info_lbl.configure(
                text=f"Confirmed: {len(self._done)} / {len(self._files)} files."
            )

    def _prev(self):
        prv = self._current_idx - 1
        if prv >= 0:
            self._show_file(prv)

    def _show_empty(self):
        ctk.CTkLabel(
            self,
            text="✅  No files in _Review_Needed/ — nothing to review.",
            font=ctk.CTkFont(size=14),
        ).pack(expand=True)
