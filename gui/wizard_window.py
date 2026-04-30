"""
Window 2 — Configuration wizard (7 steps).
Supports drag-and-drop on the source folder entry via tkinterdnd2.
"""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk

from gui.theme import (
    apply_theme, make_title, make_subtitle, make_section_label,
    make_primary_button, make_secondary_button, make_card,
    add_tooltip, ACCENT, MUTED, SUCCESS, WARNING,
)
from utils.helpers import find_dicom_files, format_bytes, get_free_space
from utils.config import SortConfig

# ── Optional drag-and-drop support ───────────────────────────────────────────
_HAS_DND = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD as _TkDnD
    _HAS_DND = True
except ImportError:
    pass


def _init_dnd(tk_root):
    """Activate tkinterdnd2 on an existing Tk/CTk root."""
    if not _HAS_DND:
        return False
    try:
        _TkDnD._require(tk_root)
        return True
    except Exception:
        return False


def _register_drop(widget, callback):
    """Register a CTkEntry (or plain Entry) for file/folder drop events."""
    if not _HAS_DND:
        return
    try:
        # CTkEntry wraps a tk.Entry accessible via ._entry
        inner = getattr(widget, "_entry", widget)
        inner.drop_target_register(DND_FILES)
        inner.dnd_bind("<<Drop>>", callback)
    except Exception:
        pass


class WizardWindow(ctk.CTk):
    STEPS = [
        "Source Folder",
        "Destination",
        "Scan Type",
        "Detection Settings",
        "Dataset Options",
        "File Operation",
        "Review & Confirm",
    ]

    def __init__(self, config: SortConfig, on_start):
        super().__init__()
        self.cfg      = config
        self.on_start = on_start

        apply_theme(config.theme)
        self.title("DICOM Organizer — Setup")
        self.geometry("900x660")
        self.minsize(780, 560)
        self.resizable(True, True)
        self._center()

        # Activate drag-and-drop on this Tk root
        self._dnd_active = _init_dnd(self)

        self._step         = 0
        self._dicom_count  = 0
        self._build_ui()
        self._show_step(0)

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"900x660+{(sw-900)//2}+{(sh-660)//2}")

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=190, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        make_title(self._sidebar, "Setup", size=16).pack(padx=16, pady=(20, 12))

        self._step_lbls: list[ctk.CTkLabel] = []
        for i, name in enumerate(self.STEPS):
            lbl = ctk.CTkLabel(
                self._sidebar, text=f"  {i+1}. {name}",
                anchor="w", font=ctk.CTkFont(size=12), corner_radius=6,
            )
            lbl.pack(fill="x", padx=8, pady=2)
            self._step_lbls.append(lbl)

        # Main area
        self._main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._main.pack(side="left", fill="both", expand=True)

        self._content = ctk.CTkScrollableFrame(self._main, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=30, pady=20)

        # Nav bar
        nav = ctk.CTkFrame(self._main, fg_color="transparent", height=60)
        nav.pack(fill="x", padx=30, pady=(0, 16))
        nav.pack_propagate(False)

        self._back_btn = make_secondary_button(nav, "← Back",
                                               command=self._go_back, width=120)
        self._back_btn.pack(side="left")

        self._next_btn = make_primary_button(nav, "Next →",
                                             command=self._go_next, width=140)
        self._next_btn.pack(side="right")

        self._build_preset_loader(nav)

    def _build_preset_loader(self, parent):
        from utils.config import list_presets, load_preset
        import dataclasses
        presets = list_presets()
        if not presets:
            return
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(pf, text="Preset:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        pv = ctk.StringVar(value=presets[0])
        ctk.CTkOptionMenu(pf, values=presets, variable=pv, width=130).pack(side="left")

        def _apply():
            loaded = load_preset(pv.get())
            if loaded:
                for f in dataclasses.fields(loaded):
                    setattr(self.cfg, f.name, getattr(loaded, f.name))
                self._show_step(self._step)

        ctk.CTkButton(pf, text="Apply", width=58, height=28,
                      command=_apply, font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))

    def _clear(self):
        for w in self._content.winfo_children():
            w.destroy()

    # ── Navigation ────────────────────────────────────────────────────────────
    def _show_step(self, step: int):
        self._step = step
        self._clear()

        for i, lbl in enumerate(self._step_lbls):
            if i == step:
                lbl.configure(fg_color=ACCENT, text_color="white")
            elif i < step:
                lbl.configure(fg_color="transparent", text_color=SUCCESS)
            else:
                lbl.configure(fg_color="transparent", text_color=MUTED)

        self._back_btn.configure(state="normal" if step > 0 else "disabled")

        # Skip dataset step in simple mode
        if step == 4 and self.cfg.mode == "simple":
            self._step = 5
            self._show_step(5)
            return

        builders = [
            self._step_source,
            self._step_destination,
            self._step_scantype,
            self._step_detection,
            self._step_dataset,
            self._step_operation,
            self._step_confirm,
        ]
        builders[step]()

        if step == len(self.STEPS) - 1:
            self._next_btn.configure(text="🚀  Start Organising",
                                     fg_color=SUCCESS, hover_color="#229954")
        else:
            self._next_btn.configure(text="Next →", fg_color=ACCENT,
                                     hover_color="#357ABD")

    def _go_next(self):
        if not self._validate(self._step):
            return
        nxt = self._step + 1
        if nxt == 4 and self.cfg.mode == "simple":
            nxt = 5
        if nxt < len(self.STEPS):
            self._show_step(nxt)
        else:
            self.destroy()
            self.on_start(self.cfg)

    def _go_back(self):
        prev = self._step - 1
        if prev == 4 and self.cfg.mode == "simple":
            prev = 3
        if prev >= 0:
            self._show_step(prev)

    def _validate(self, step: int) -> bool:
        if step == 0 and not self.cfg.source_folder:
            self._error("Please select a source folder.")
            return False
        if step == 1 and not self.cfg.destination_folder:
            self._error("Please select a destination folder.")
            return False
        return True

    def _error(self, msg: str):
        w = ctk.CTkToplevel(self)
        w.title("Required Field")
        w.geometry("380x160")
        w.grab_set()
        ctk.CTkLabel(w, text=f"⚠️  {msg}", wraplength=340,
                     font=ctk.CTkFont(size=13)).pack(pady=30, padx=20)
        make_primary_button(w, "OK", command=w.destroy, width=100).pack()

    # ── Step 1 — Source folder ────────────────────────────────────────────────
    def _step_source(self):
        make_title(self._content, "📁  Step 1 — Source Folder", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content, "Where are your DICOM files stored?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        # Drop-zone hint
        if self._dnd_active:
            hint = ctk.CTkLabel(
                self._content,
                text="  📂  Drag a folder here, or click Browse  ",
                font=ctk.CTkFont(size=12), text_color=MUTED,
                fg_color=("gray90", "#2B3040"), corner_radius=8,
            )
            hint.pack(fill="x", pady=(0, 8), ipady=8)

        row = ctk.CTkFrame(self._content, fg_color="transparent")
        row.pack(fill="x", pady=4)

        self._src_var = ctk.StringVar(value=self.cfg.source_folder)
        self._src_entry = ctk.CTkEntry(row, textvariable=self._src_var,
                                       placeholder_text="Select or drop a folder…",
                                       width=460)
        self._src_entry.pack(side="left", padx=(0, 10))

        # Activate DnD on the entry
        _register_drop(self._src_entry, self._on_folder_drop)

        def _browse():
            d = filedialog.askdirectory(title="Select source folder")
            if d:
                self._set_source(d)

        make_secondary_button(row, "Browse…", command=_browse, width=100).pack(side="left")

        # Recursive checkbox
        rec_var = ctk.BooleanVar(value=self.cfg.recursive)
        rec_cb  = ctk.CTkCheckBox(
            self._content, text="Include sub-folders (recursive)",
            variable=rec_var,
            command=lambda: setattr(self.cfg, "recursive", rec_var.get()),
        )
        rec_cb.pack(anchor="w", pady=(12, 4))
        add_tooltip(rec_cb, "Scan all nested sub-folders for DICOM files.")

        # Scan result
        self._scan_lbl = ctk.CTkLabel(self._content, text="",
                                      text_color=SUCCESS,
                                      font=ctk.CTkFont(size=13, weight="bold"))
        self._scan_lbl.pack(anchor="w", pady=(8, 0))

        if self.cfg.source_folder:
            self._start_scan(self.cfg.source_folder)

    def _on_folder_drop(self, event):
        """Handle drag-and-drop event on source folder entry."""
        raw  = event.data.strip()
        # tkinterdnd2 wraps paths with spaces in {braces} on Windows
        path = raw.strip("{}").strip('"').strip("'")
        if path:
            self._set_source(path)

    def _set_source(self, path: str):
        self.cfg.source_folder = path
        self._src_var.set(path)
        self._start_scan(path)

    def _start_scan(self, path: str):
        self._scan_lbl.configure(text="🔍  Scanning…", text_color=WARNING)

        def _scan():
            files = find_dicom_files(path, recursive=self.cfg.recursive)
            self._dicom_count = len(files)
            if self._scan_lbl.winfo_exists():
                self._scan_lbl.after(
                    0,
                    lambda: self._scan_lbl.configure(
                        text=f"✓  Found {self._dicom_count} potential DICOM files.",
                        text_color=SUCCESS,
                    ),
                )

        threading.Thread(target=_scan, daemon=True).start()

    # ── Step 2 — Destination ──────────────────────────────────────────────────
    def _step_destination(self):
        make_title(self._content, "💾  Step 2 — Destination Folder", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content, "Where should the sorted files go?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        row = ctk.CTkFrame(self._content, fg_color="transparent")
        row.pack(fill="x", pady=4)

        self._dest_var = ctk.StringVar(value=self.cfg.destination_folder)
        dest_entry = ctk.CTkEntry(row, textvariable=self._dest_var,
                                  placeholder_text="Choose destination…", width=460)
        dest_entry.pack(side="left", padx=(0, 10))
        _register_drop(dest_entry, lambda e: self._set_dest(e.data.strip("{}").strip()))

        self._space_lbl = ctk.CTkLabel(self._content, text="", text_color=MUTED,
                                       font=ctk.CTkFont(size=12))
        self._space_lbl.pack(anchor="w", pady=(8, 0))

        def _browse():
            d = filedialog.askdirectory(title="Select destination folder")
            if d:
                self._set_dest(d)

        make_secondary_button(row, "Browse…", command=_browse, width=100).pack(side="left")

        if self.cfg.destination_folder:
            self._update_space(self.cfg.destination_folder)

    def _set_dest(self, path: str):
        self.cfg.destination_folder = path
        self._dest_var.set(path)
        self._update_space(path)

    def _update_space(self, path: str):
        free = get_free_space(path)
        self._space_lbl.configure(text=f"Free space: {format_bytes(free)}")

    # ── Step 3 — Scan type ────────────────────────────────────────────────────
    def _step_scantype(self):
        make_title(self._content, "🔬  Step 3 — Scan Type", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content, "Which types of scans are you sorting?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        st_var = ctk.StringVar(value=self.cfg.scan_type)
        for label, value in [
            ("🧠  MRI only",                "mri"),
            ("🫁  CT only",                 "ct"),
            ("🔄  Both MRI & CT",           "both"),
            ("🤖  Auto-detect (accept all)", "auto"),
        ]:
            ctk.CTkRadioButton(
                self._content, text=label, variable=st_var, value=value,
                command=lambda v=value: setattr(self.cfg, "scan_type", v),
                font=ctk.CTkFont(size=13),
            ).pack(anchor="w", pady=7)

    # ── Step 4 — Detection settings ───────────────────────────────────────────
    def _step_detection(self):
        make_title(self._content, "🎯  Step 4 — Body Part Detection", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content,
                      "Configure how the app identifies which body part each scan shows.").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        # AI toggle
        ai_var = ctk.BooleanVar(value=self.cfg.enable_ai_detection)
        ai_sw  = ctk.CTkSwitch(
            self._content,
            text="Enable AI body part detection  (slower but more accurate)",
            variable=ai_var,
            command=lambda: setattr(self.cfg, "enable_ai_detection", ai_var.get()),
            font=ctk.CTkFont(size=13),
        )
        ai_sw.pack(anchor="w", pady=(0, 4))
        add_tooltip(ai_sw,
                    "Uses a neural network to analyse images when metadata is missing.\n"
                    "Requires PyTorch (installed via the installer checkbox).")

        # Sensitivity
        make_section_label(self._content, "Detection Sensitivity").pack(anchor="w", pady=(16, 4))
        sens_map = {"conservative": 0, "balanced": 1, "aggressive": 2}
        sens_rev = {0: "conservative", 1: "balanced", 2: "aggressive"}
        sv       = ctk.IntVar(value=sens_map.get(self.cfg.detection_sensitivity, 1))
        sens_lbl = ctk.CTkLabel(self._content,
                                text=self.cfg.detection_sensitivity.capitalize(),
                                font=ctk.CTkFont(size=12, weight="bold"),
                                text_color=ACCENT)

        def _sens(v):
            lbl = sens_rev[int(float(v))]
            self.cfg.detection_sensitivity = lbl
            sens_lbl.configure(text=lbl.capitalize())

        sl = ctk.CTkSlider(self._content, from_=0, to=2, number_of_steps=2,
                           variable=sv, command=_sens, width=300)
        sl.pack(anchor="w")
        axis = ctk.CTkFrame(self._content, fg_color="transparent")
        axis.pack(anchor="w", fill="x")
        ctk.CTkLabel(axis, text="Conservative", font=ctk.CTkFont(size=10),
                     text_color=MUTED).pack(side="left")
        ctk.CTkLabel(axis, text="Aggressive", font=ctk.CTkFont(size=10),
                     text_color=MUTED).pack(side="right")
        sens_lbl.pack(anchor="w", pady=(4, 0))
        add_tooltip(sl,
                    "Conservative: only classify when very confident.\n"
                    "Aggressive: classify even with weaker evidence.")

        # Review checkbox
        rev_var = ctk.BooleanVar(value=self.cfg.move_uncertain_to_review)
        rev_cb  = ctk.CTkCheckBox(
            self._content,
            text="Move uncertain files to  _Review_Needed/  for manual check",
            variable=rev_var,
            command=lambda: setattr(self.cfg, "move_uncertain_to_review", rev_var.get()),
            font=ctk.CTkFont(size=13),
        )
        rev_cb.pack(anchor="w", pady=(18, 4))
        add_tooltip(rev_cb,
                    "Files with confidence < 50 % go into a separate review folder "
                    "so you can manually verify and reassign them.")

        # Info card
        info = make_card(self._content)
        info.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(
            info,
            text=(
                "ℹ️  How 3-layer detection works\n\n"
                "Layer 1  —  Reads DICOM metadata tags  (instant, 95 %+ accurate)\n"
                "Layer 2  —  AI image analysis           (when tags are missing)\n"
                "Layer 3  —  Anatomical heuristics       (FOV, geometry, pixel stats)\n\n"
                "A confidence score (0–100 %) is saved for every file in the manifest."
            ),
            justify="left", font=ctk.CTkFont(size=12), wraplength=580,
        ).pack(padx=16, pady=14, anchor="w")

    # ── Step 5 — Dataset options ──────────────────────────────────────────────
    def _step_dataset(self):
        make_title(self._content, "📊  Step 5 — Dataset Options", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content, "Configure ML dataset building.").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        make_section_label(self._content, "Dataset Name").pack(anchor="w", pady=(0, 4))
        nv = ctk.StringVar(value=self.cfg.dataset_name)
        ctk.CTkEntry(self._content, textvariable=nv, width=300,
                     placeholder_text="my_dataset").pack(anchor="w")
        nv.trace_add("write", lambda *_: setattr(self.cfg, "dataset_name", nv.get()))

        make_section_label(self._content, "Purpose").pack(anchor="w", pady=(14, 4))
        pv = ctk.StringVar(value=self.cfg.dataset_purpose)
        ctk.CTkOptionMenu(
            self._content,
            values=["research", "clinical_training", "algorithm_testing", "education", "other"],
            variable=pv, width=200,
            command=lambda v: setattr(self.cfg, "dataset_purpose", v),
        ).pack(anchor="w")

        for attr, label, tip in [
            ("enable_anonymization", "Anonymize patient data  (HIPAA-safe)",
             "Replaces names/IDs with hashed anonymous codes and strips private tags."),
            ("enable_nifti",         "Convert to NIfTI  (.nii.gz)",
             "Needs SimpleITK / dicom2nifti installed (optional installer checkbox)."),
            ("enable_png_previews",  "Generate PNG preview images",
             "Saves a middle-slice PNG per series for quick visual inspection."),
        ]:
            var = ctk.BooleanVar(value=getattr(self.cfg, attr))
            cb  = ctk.CTkCheckBox(
                self._content, text=label, variable=var,
                font=ctk.CTkFont(size=13),
                command=lambda a=attr, v=var: setattr(self.cfg, a, v.get()),
            )
            cb.pack(anchor="w", pady=(12, 0))
            add_tooltip(cb, tip)

        make_section_label(self._content, "Train / Val / Test Split").pack(anchor="w", pady=(18, 4))
        sr = ctk.CTkFrame(self._content, fg_color="transparent")
        sr.pack(anchor="w")
        for label, attr, default in [
            ("Train %", "train_ratio", self.cfg.train_ratio),
            ("Val %",   "val_ratio",   self.cfg.val_ratio),
            ("Test %",  "test_ratio",  self.cfg.test_ratio),
        ]:
            col = ctk.CTkFrame(sr, fg_color="transparent")
            col.pack(side="left", padx=10)
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont(size=11, weight="bold")).pack()
            sv = ctk.StringVar(value=str(int(default * 100)))
            ctk.CTkEntry(col, textvariable=sv, width=70).pack()
            sv.trace_add("write", lambda *_, a=attr, v=sv: self._update_ratio(a, v))

    def _update_ratio(self, attr, sv):
        try:
            setattr(self.cfg, attr, float(sv.get()) / 100.0)
        except ValueError:
            pass

    # ── Step 6 — File operation ───────────────────────────────────────────────
    def _step_operation(self):
        make_title(self._content, "⚙️  Step 6 — File Operation", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content, "How should files reach the destination?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        op_var = ctk.StringVar(value=self.cfg.file_operation)
        for label, value, tip in [
            ("📋  Copy  (keep originals — recommended)", "copy",
             "Your original files are untouched. Safest option."),
            ("✂️   Move  (delete originals after sorting)", "move",
             "Originals are deleted after being moved. Cannot be undone easily!"),
        ]:
            rb = ctk.CTkRadioButton(
                self._content, text=label, variable=op_var, value=value,
                command=lambda v=value: setattr(self.cfg, "file_operation", v),
                font=ctk.CTkFont(size=13),
            )
            rb.pack(anchor="w", pady=8)
            add_tooltip(rb, tip)

        pv = ctk.BooleanVar(value=self.cfg.preview_only)
        pc = ctk.CTkCheckBox(
            self._content,
            text="🔍  Preview only  (dry-run — don't actually copy or move any files)",
            variable=pv,
            command=lambda: setattr(self.cfg, "preview_only", pv.get()),
            font=ctk.CTkFont(size=13),
        )
        pc.pack(anchor="w", pady=(20, 4))
        add_tooltip(pc, "Shows what would happen without touching any files. "
                        "Useful for testing your settings first.")

    # ── Step 7 — Review & Confirm ─────────────────────────────────────────────
    def _step_confirm(self):
        make_title(self._content, "✅  Step 7 — Review & Confirm", size=18).pack(anchor="w", pady=(0, 4))
        make_subtitle(self._content, "Check your settings before starting.").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=12)

        cfg = self.cfg
        rows = [
            ("Mode",           "Simple Sort" if cfg.mode == "simple" else "Build ML Dataset"),
            ("Source",         cfg.source_folder or "—"),
            ("Destination",    cfg.destination_folder or "—"),
            ("DICOM files",    str(self._dicom_count) + " found"),
            ("Scan type",      cfg.scan_type.upper()),
            ("AI detection",   "Enabled" if cfg.enable_ai_detection else "Disabled"),
            ("Sensitivity",    cfg.detection_sensitivity.capitalize()),
            ("File operation", cfg.file_operation.capitalize()
             + ("  [PREVIEW ONLY]" if cfg.preview_only else "")),
        ]
        if cfg.mode == "dataset":
            rows += [
                ("Dataset name", cfg.dataset_name),
                ("Anonymize",    "Yes" if cfg.enable_anonymization else "No"),
                ("NIfTI",        "Yes" if cfg.enable_nifti else "No"),
                ("Split",        f"Train {int(cfg.train_ratio*100)}% / "
                                 f"Val {int(cfg.val_ratio*100)}% / "
                                 f"Test {int(cfg.test_ratio*100)}%"),
            ]

        card = make_card(self._content)
        card.pack(fill="x", pady=6)
        for label, value in rows:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(r, text=label + ":", width=160, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            ctk.CTkLabel(r, text=value, anchor="w",
                         font=ctk.CTkFont(size=12),
                         text_color=MUTED).pack(side="left")

        if cfg.preview_only:
            ctk.CTkLabel(
                self._content,
                text="⚠️  PREVIEW MODE — No files will be copied or moved.",
                text_color=WARNING, font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(pady=(14, 0))
