"""
Window 2 — Configuration wizard (7 steps).
"""
from __future__ import annotations

import threading
import tkinter as tk
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
        self.cfg = config
        self.on_start = on_start

        apply_theme(config.theme)
        self.title("DICOM Organizer — Setup")
        self.geometry("900x640")
        self.minsize(780, 560)
        self.resizable(True, True)
        self._center()

        self._step = 0
        self._dicom_count = 0
        self._scan_thread: threading.Thread | None = None
        self._build_ui()
        self._show_step(0)

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"900x640+{(sw-900)//2}+{(sh-640)//2}")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Sidebar step list
        self._sidebar = ctk.CTkFrame(self, width=190, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        make_title(self._sidebar, "Setup", size=16).pack(padx=16, pady=(20, 12))

        self._step_labels: list[ctk.CTkLabel] = []
        for i, name in enumerate(self.STEPS):
            lbl = ctk.CTkLabel(
                self._sidebar,
                text=f"  {i+1}. {name}",
                anchor="w",
                font=ctk.CTkFont(size=12),
                corner_radius=6,
            )
            lbl.pack(fill="x", padx=8, pady=2)
            self._step_labels.append(lbl)

        # Main area
        self._main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._main.pack(side="left", fill="both", expand=True)

        # Content area
        self._content = ctk.CTkScrollableFrame(self._main, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=30, pady=20)

        # Nav buttons
        nav = ctk.CTkFrame(self._main, fg_color="transparent", height=60)
        nav.pack(fill="x", padx=30, pady=(0, 16))
        nav.pack_propagate(False)

        self._back_btn = make_secondary_button(nav, "← Back", command=self._go_back, width=120)
        self._back_btn.pack(side="left")
        self._next_btn = make_primary_button(nav, "Next →", command=self._go_next, width=140)
        self._next_btn.pack(side="right")

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------
    # Step navigation
    # ------------------------------------------------------------------
    def _show_step(self, step: int):
        self._step = step
        self._clear_content()

        # Highlight current sidebar label
        for i, lbl in enumerate(self._step_labels):
            if i == step:
                lbl.configure(fg_color=ACCENT, text_color="white")
            elif i < step:
                lbl.configure(fg_color="transparent", text_color=SUCCESS)
            else:
                lbl.configure(fg_color="transparent", text_color=MUTED)

        self._back_btn.configure(state="normal" if step > 0 else "disabled")

        # Skip Dataset Options if mode=simple
        skip_step4 = (step == 4 and self.cfg.mode == "simple")

        builders = [
            self._build_step_source,
            self._build_step_destination,
            self._build_step_scantype,
            self._build_step_detection,
            self._build_step_dataset,
            self._build_step_operation,
            self._build_step_confirm,
        ]

        if skip_step4:
            self._step = 5
            self._show_step(5)
            return

        builders[step]()

        if step == len(self.STEPS) - 1:
            self._next_btn.configure(text="🚀 Start Organising", fg_color=SUCCESS)
        else:
            self._next_btn.configure(text="Next →", fg_color=ACCENT)

    def _go_next(self):
        if self._step < len(self.STEPS) - 1:
            # Validate current step
            if not self._validate_step(self._step):
                return
            next_step = self._step + 1
            # Skip dataset step if simple mode
            if next_step == 4 and self.cfg.mode == "simple":
                next_step = 5
            self._show_step(next_step)
        else:
            # Final step — start
            if self._validate_step(self._step):
                self.destroy()
                self.on_start(self.cfg)

    def _go_back(self):
        if self._step > 0:
            prev = self._step - 1
            if prev == 4 and self.cfg.mode == "simple":
                prev = 3
            self._show_step(prev)

    def _validate_step(self, step: int) -> bool:
        if step == 0 and not self.cfg.source_folder:
            self._show_error("Please select a source folder.")
            return False
        if step == 1 and not self.cfg.destination_folder:
            self._show_error("Please select a destination folder.")
            return False
        return True

    def _show_error(self, msg: str):
        win = ctk.CTkToplevel(self)
        win.title("Validation Error")
        win.geometry("380x160")
        win.grab_set()
        ctk.CTkLabel(win, text=f"⚠️  {msg}", wraplength=340, font=ctk.CTkFont(size=13)).pack(
            pady=30, padx=20
        )
        make_primary_button(win, "OK", command=win.destroy, width=100).pack()

    # ------------------------------------------------------------------
    # Step builders
    # ------------------------------------------------------------------
    def _build_step_source(self):
        make_title(self._content, "📁  Step 1 — Source Folder", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(self._content, "Where are your DICOM files stored?").pack(anchor="w")

        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        row = ctk.CTkFrame(self._content, fg_color="transparent")
        row.pack(fill="x", pady=4)

        self._src_var = ctk.StringVar(value=self.cfg.source_folder)
        entry = ctk.CTkEntry(row, textvariable=self._src_var, placeholder_text="Choose a folder…", width=460)
        entry.pack(side="left", padx=(0, 10))
        entry.drop_target_register = lambda *a: None  # drag-drop placeholder

        def browse():
            d = filedialog.askdirectory(title="Select source folder")
            if d:
                self._src_var.set(d)
                self.cfg.source_folder = d
                self._start_dicom_scan(d)

        make_secondary_button(row, "Browse…", command=browse, width=100).pack(side="left")

        # Recursive checkbox
        self._recursive_var = ctk.BooleanVar(value=self.cfg.recursive)
        rec_cb = ctk.CTkCheckBox(
            self._content, text="Include sub-folders (recursive)",
            variable=self._recursive_var,
            command=lambda: setattr(self.cfg, "recursive", self._recursive_var.get()),
        )
        rec_cb.pack(anchor="w", pady=(12, 4))
        add_tooltip(rec_cb, "Scan all nested sub-folders for DICOM files")

        # Scan result label
        self._scan_lbl = ctk.CTkLabel(
            self._content, text="", text_color=SUCCESS,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._scan_lbl.pack(anchor="w", pady=(8, 0))

        if self.cfg.source_folder:
            self._start_dicom_scan(self.cfg.source_folder)

    def _start_dicom_scan(self, path: str):
        self._scan_lbl.configure(text="🔍 Scanning…", text_color=WARNING)
        self.cfg.source_folder = path

        def do_scan():
            files = find_dicom_files(path, recursive=self.cfg.recursive)
            count = len(files)
            self._dicom_count = count
            if self._scan_lbl.winfo_exists():
                self._scan_lbl.after(
                    0,
                    lambda: self._scan_lbl.configure(
                        text=f"✓ Found {count} potential DICOM files.",
                        text_color=SUCCESS,
                    ),
                )

        t = threading.Thread(target=do_scan, daemon=True)
        t.start()

    def _build_step_destination(self):
        make_title(self._content, "💾  Step 2 — Destination Folder", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(self._content, "Where should the sorted files be placed?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        row = ctk.CTkFrame(self._content, fg_color="transparent")
        row.pack(fill="x", pady=4)

        self._dest_var = ctk.StringVar(value=self.cfg.destination_folder)
        entry = ctk.CTkEntry(row, textvariable=self._dest_var, placeholder_text="Choose a folder…", width=460)
        entry.pack(side="left", padx=(0, 10))

        self._space_lbl = ctk.CTkLabel(self._content, text="", text_color=MUTED, font=ctk.CTkFont(size=12))
        self._space_lbl.pack(anchor="w", pady=(8, 0))

        def browse():
            d = filedialog.askdirectory(title="Select destination folder")
            if d:
                self._dest_var.set(d)
                self.cfg.destination_folder = d
                free = get_free_space(d)
                self._space_lbl.configure(text=f"Free space: {format_bytes(free)}")

        make_secondary_button(row, "Browse…", command=browse, width=100).pack(side="left")

        if self.cfg.destination_folder:
            free = get_free_space(self.cfg.destination_folder)
            self._space_lbl.configure(text=f"Free space: {format_bytes(free)}")

    def _build_step_scantype(self):
        make_title(self._content, "🔬  Step 3 — Scan Type", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(self._content, "Which type of medical images are you sorting?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        self._scan_type_var = ctk.StringVar(value=self.cfg.scan_type)
        options = [
            ("🧠  MRI only", "mri"),
            ("🫁  CT only", "ct"),
            ("🔄  Both MRI & CT", "both"),
            ("🤖  Auto-detect (accept all)", "auto"),
        ]
        for label, value in options:
            rb = ctk.CTkRadioButton(
                self._content, text=label, variable=self._scan_type_var, value=value,
                command=lambda v=value: setattr(self.cfg, "scan_type", v),
                font=ctk.CTkFont(size=13),
            )
            rb.pack(anchor="w", pady=6)

    def _build_step_detection(self):
        make_title(self._content, "🎯  Step 4 — Body Part Detection", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(
            self._content,
            "Configure how the app identifies which body part each scan shows.",
        ).pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        # AI toggle
        ai_var = ctk.BooleanVar(value=self.cfg.enable_ai_detection)
        ai_sw = ctk.CTkSwitch(
            self._content, text="Enable AI body part detection (slower but more accurate)",
            variable=ai_var,
            command=lambda: setattr(self.cfg, "enable_ai_detection", ai_var.get()),
            font=ctk.CTkFont(size=13),
        )
        ai_sw.pack(anchor="w", pady=(0, 4))
        add_tooltip(
            ai_sw,
            "Uses a neural network to analyse images when metadata is missing or unclear. "
            "Requires PyTorch. Automatically disabled if GPU unavailable.",
        )

        # Sensitivity slider
        make_section_label(self._content, "Detection Sensitivity").pack(anchor="w", pady=(16, 4))
        sens_map = {"conservative": 0, "balanced": 1, "aggressive": 2}
        sens_rev = {0: "conservative", 1: "balanced", 2: "aggressive"}
        sens_var = ctk.IntVar(value=sens_map.get(self.cfg.detection_sensitivity, 1))

        def sens_change(v):
            label = sens_rev[int(float(v))]
            self.cfg.detection_sensitivity = label
            sens_lbl.configure(text=label.capitalize())

        slider = ctk.CTkSlider(
            self._content, from_=0, to=2, number_of_steps=2, variable=sens_var,
            command=sens_change, width=300,
        )
        slider.pack(anchor="w")
        row = ctk.CTkFrame(self._content, fg_color="transparent")
        row.pack(anchor="w", fill="x")
        ctk.CTkLabel(row, text="Conservative", font=ctk.CTkFont(size=10), text_color=MUTED).pack(side="left")
        ctk.CTkLabel(row, text="Aggressive", font=ctk.CTkFont(size=10), text_color=MUTED).pack(side="right")
        sens_lbl = ctk.CTkLabel(self._content, text=self.cfg.detection_sensitivity.capitalize(),
                                font=ctk.CTkFont(size=12, weight="bold"), text_color=ACCENT)
        sens_lbl.pack(anchor="w", pady=(4, 0))
        add_tooltip(slider,
                    "Conservative: only classify when very confident.\n"
                    "Aggressive: classify even with less evidence.")

        # Review checkbox
        review_var = ctk.BooleanVar(value=self.cfg.move_uncertain_to_review)
        review_cb = ctk.CTkCheckBox(
            self._content,
            text="Move uncertain files to _Review_Needed/ for manual check",
            variable=review_var,
            command=lambda: setattr(self.cfg, "move_uncertain_to_review", review_var.get()),
            font=ctk.CTkFont(size=13),
        )
        review_cb.pack(anchor="w", pady=(18, 4))
        add_tooltip(review_cb,
                    "Files where the app isn't confident about the body part will be "
                    "placed in a special folder so you can check them manually.")

        # Info card
        info = make_card(self._content)
        info.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(
            info,
            text=(
                "ℹ️  How detection works:\n\n"
                "Layer 1 — Reads DICOM metadata tags (instant, most reliable)\n"
                "Layer 2 — AI image analysis (accurate when metadata is missing)\n"
                "Layer 3 — Anatomical rules (geometry, pixel stats, modality)\n\n"
                "A confidence score (0–100%) is recorded for every file."
            ),
            justify="left",
            font=ctk.CTkFont(size=12),
            wraplength=600,
        ).pack(padx=16, pady=16, anchor="w")

    def _build_step_dataset(self):
        make_title(self._content, "📊  Step 5 — Dataset Options", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(self._content, "Configure ML dataset building options.").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        # Dataset name
        make_section_label(self._content, "Dataset Name").pack(anchor="w", pady=(0, 4))
        name_var = ctk.StringVar(value=self.cfg.dataset_name)
        name_entry = ctk.CTkEntry(self._content, textvariable=name_var, width=300,
                                  placeholder_text="my_dataset")
        name_entry.pack(anchor="w")
        name_var.trace_add("write", lambda *_: setattr(self.cfg, "dataset_name", name_var.get()))

        # Purpose dropdown
        make_section_label(self._content, "Purpose").pack(anchor="w", pady=(16, 4))
        purpose_var = ctk.StringVar(value=self.cfg.dataset_purpose)
        purpose_menu = ctk.CTkOptionMenu(
            self._content,
            values=["research", "clinical_training", "algorithm_testing", "education", "other"],
            variable=purpose_var,
            command=lambda v: setattr(self.cfg, "dataset_purpose", v),
            width=200,
        )
        purpose_menu.pack(anchor="w")

        # Feature toggles
        for attr, label, tip in [
            ("enable_anonymization", "Anonymize patient data (HIPAA-safe)", "Replaces patient names/IDs with hashed anonymous codes and strips private tags."),
            ("enable_nifti", "Convert to NIfTI (.nii.gz)", "Converts DICOM series to NIfTI format for use with FSL, ANTs, ITK-SNAP, MONAI."),
            ("enable_png_previews", "Generate PNG preview images", "Saves a middle-slice PNG for quick visual inspection of each series."),
        ]:
            var = ctk.BooleanVar(value=getattr(self.cfg, attr))
            cb = ctk.CTkCheckBox(
                self._content, text=label, variable=var, font=ctk.CTkFont(size=13),
                command=lambda a=attr, v=var: setattr(self.cfg, a, v.get()),
            )
            cb.pack(anchor="w", pady=(12, 0))
            add_tooltip(cb, tip)

        # Split ratios
        make_section_label(self._content, "Train / Val / Test Split").pack(anchor="w", pady=(20, 4))
        split_row = ctk.CTkFrame(self._content, fg_color="transparent")
        split_row.pack(anchor="w")

        for label, attr, default in [
            ("Train %", "train_ratio", self.cfg.train_ratio),
            ("Val %", "val_ratio", self.cfg.val_ratio),
            ("Test %", "test_ratio", self.cfg.test_ratio),
        ]:
            col = ctk.CTkFrame(split_row, fg_color="transparent")
            col.pack(side="left", padx=10)
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont(size=11, weight="bold")).pack()
            var = ctk.StringVar(value=str(int(default * 100)))
            entry = ctk.CTkEntry(col, textvariable=var, width=70)
            entry.pack()
            var.trace_add("write", lambda *_, a=attr, v=var: self._update_ratio(a, v))

    def _update_ratio(self, attr: str, var: ctk.StringVar):
        try:
            val = float(var.get()) / 100.0
            setattr(self.cfg, attr, val)
        except ValueError:
            pass

    def _build_step_operation(self):
        make_title(self._content, "⚙️  Step 6 — File Operation", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(self._content, "How should files be moved to the destination?").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        op_var = ctk.StringVar(value=self.cfg.file_operation)
        for label, value, tip in [
            ("📋  Copy (keep originals — recommended)", "copy",
             "Original files are untouched. Use this unless you need to free up space."),
            ("✂️  Move (delete originals after sorting)", "move",
             "Original files are deleted after being moved. Cannot be undone easily!"),
        ]:
            rb = ctk.CTkRadioButton(
                self._content, text=label, variable=op_var, value=value,
                command=lambda v=value: setattr(self.cfg, "file_operation", v),
                font=ctk.CTkFont(size=13),
            )
            rb.pack(anchor="w", pady=8)
            add_tooltip(rb, tip)

        # Preview mode
        preview_var = ctk.BooleanVar(value=self.cfg.preview_only)
        preview_cb = ctk.CTkCheckBox(
            self._content,
            text="🔍 Preview only (don't actually copy/move files)",
            variable=preview_var,
            command=lambda: setattr(self.cfg, "preview_only", preview_var.get()),
            font=ctk.CTkFont(size=13),
        )
        preview_cb.pack(anchor="w", pady=(20, 4))
        add_tooltip(preview_cb,
                    "Dry-run mode: shows what would happen without touching any files. "
                    "Use to verify before committing.")

    def _build_step_confirm(self):
        make_title(self._content, "✅  Step 7 — Review & Confirm", size=18).pack(anchor="w", pady=(0, 6))
        make_subtitle(self._content, "Double-check your settings before starting.").pack(anchor="w")
        ctk.CTkFrame(self._content, height=1, fg_color=MUTED).pack(fill="x", pady=14)

        cfg = self.cfg
        items = [
            ("Mode", "Simple Sort" if cfg.mode == "simple" else "Build ML Dataset"),
            ("Source", cfg.source_folder or "—"),
            ("Destination", cfg.destination_folder or "—"),
            ("DICOM files found", str(self._dicom_count)),
            ("Scan type", cfg.scan_type.upper()),
            ("AI detection", "Enabled" if cfg.enable_ai_detection else "Disabled"),
            ("Sensitivity", cfg.detection_sensitivity.capitalize()),
            ("File operation", cfg.file_operation.capitalize() +
             (" [PREVIEW ONLY]" if cfg.preview_only else "")),
        ]
        if cfg.mode == "dataset":
            items += [
                ("Dataset name", cfg.dataset_name),
                ("Anonymize", "Yes" if cfg.enable_anonymization else "No"),
                ("NIfTI conversion", "Yes" if cfg.enable_nifti else "No"),
                ("Split", f"Train {int(cfg.train_ratio*100)}% / Val {int(cfg.val_ratio*100)}% / Test {int(cfg.test_ratio*100)}%"),
            ]

        card = make_card(self._content)
        card.pack(fill="x", pady=8)

        for label, value in items:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(row, text=label + ":", width=160, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w",
                         font=ctk.CTkFont(size=12), text_color=MUTED).pack(side="left")

        if cfg.preview_only:
            ctk.CTkLabel(
                self._content,
                text="⚠️  PREVIEW MODE — No files will be copied or moved.",
                text_color=WARNING,
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(pady=(12, 0))
