"""
Window 4 — Results & Summary.
Includes: stats cards, charts, sorted-file browser with right-click reassign,
and direct link to the manual review tool.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import ttk
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import (
    apply_theme, make_title, make_subtitle, make_card,
    make_primary_button, make_secondary_button,
    ACCENT, SUCCESS, WARNING, DANGER, MUTED,
)
from utils.config import SortConfig

# Body parts available for reassignment
from core.body_part_detector import BODY_PART_KEYWORDS
_ALL_BODY_PARTS = sorted(BODY_PART_KEYWORDS.keys()) + ["Other_Unknown"]


class ResultsWindow(ctk.CTk):
    def __init__(self, config: SortConfig, stats, on_sort_more=None):
        super().__init__()
        self.cfg          = config
        self.stats        = stats
        self.on_sort_more = on_sort_more

        apply_theme(config.theme)
        self.title("DICOM Organizer — Results")
        self.geometry("1060x740")
        self.minsize(860, 620)
        self.resizable(True, True)
        self._center()
        self._build_ui()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1060x740+{(sw-1060)//2}+{(sh-740)//2}")

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Left panel — stats + charts
        left = ctk.CTkScrollableFrame(self, fg_color="transparent", width=500)
        left.pack(side="left", fill="both", expand=True, padx=(20, 8), pady=20)
        self._build_left(left)

        # Right panel — file browser
        right = ctk.CTkFrame(self, width=360, corner_radius=12)
        right.pack(side="right", fill="y", padx=(0, 20), pady=20)
        right.pack_propagate(False)
        self._build_right(right)

    # ── Left panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent):
        make_title(parent, "✅  Organisation Complete!", size=22).pack(anchor="w", pady=(0, 4))
        make_subtitle(parent, "Your DICOM files have been sorted successfully.").pack(anchor="w")

        # Stat cards
        stat_row = ctk.CTkFrame(parent, fg_color="transparent")
        stat_row.pack(fill="x", pady=(18, 0))
        for value, label, color in [
            (str(self.stats.sorted_ok),                  "Files Sorted", SUCCESS),
            (str(self.stats.skipped),                    "Skipped",      MUTED),
            (str(self.stats.errors),                     "Errors",       DANGER),
            (str(self.stats.review_needed),              "Need Review",  WARNING),
            (str(len(self.stats.body_part_counts or {})), "Body Parts",   ACCENT),
        ]:
            card = make_card(stat_row)
            card.pack(side="left", padx=5, pady=4)
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=26, weight="bold"),
                         text_color=color).pack(padx=18, pady=(14, 2))
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=10),
                         text_color=MUTED).pack(padx=18, pady=(0, 12))

        # Review warning
        if self.stats.review_needed > 0:
            warn = make_card(parent)
            warn.pack(fill="x", pady=(14, 0))
            wi = ctk.CTkFrame(warn, fg_color="transparent")
            wi.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(
                wi,
                text=(f"⚠️  {self.stats.review_needed} files have low confidence "
                      f"and need manual review."),
                text_color=WARNING, font=ctk.CTkFont(size=13, weight="bold"),
                wraplength=400,
            ).pack(side="left", fill="x", expand=True)
            make_primary_button(wi, "🔍 Review Tool",
                                command=self._open_review, width=140).pack(side="right")

        # Charts
        charts_row = ctk.CTkFrame(parent, fg_color="transparent")
        charts_row.pack(fill="x", pady=(18, 0))
        charts_row.columnconfigure((0, 1), weight=1)
        charts_row.rowconfigure(0, weight=1)

        if self.stats.body_part_counts:
            pc = make_card(charts_row)
            pc.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
            ctk.CTkLabel(pc, text="Body Part Distribution",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(10, 0))
            self._pie_chart(pc)

        if self.stats.method_counts:
            bc = make_card(charts_row)
            bc.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
            ctk.CTkLabel(bc, text="Detection Method",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(10, 0))
            self._bar_chart(bc)

        # Action buttons
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(22, 0))
        make_primary_button(btn_row, "📂 Open Output Folder",
                            command=self._open_folder, width=200).pack(side="left", padx=(0, 8))
        make_primary_button(btn_row, "📄 View Report",
                            command=self._open_report, width=150).pack(side="left", padx=(0, 8))
        make_secondary_button(btn_row, "🔄 Sort More",
                              command=self._sort_more, width=120).pack(side="left", padx=(0, 8))
        make_secondary_button(btn_row, "💾 Save Preset",
                              command=self._save_preset, width=120).pack(side="left")

    # ── Charts ────────────────────────────────────────────────────────────────
    def _pie_chart(self, parent):
        bp     = self.stats.body_part_counts
        labels = list(bp.keys())
        values = list(bp.values())
        fig, ax = plt.subplots(figsize=(3.8, 3.2))
        fig.patch.set_facecolor("#2B3038")
        ax.set_facecolor("#2B3038")
        wedges, _, auto = ax.pie(
            values, labels=None, autopct="%1.0f%%",
            colors=plt.cm.Set3(range(len(labels))), startangle=90,
        )
        for t in auto:
            t.set_color("white")
            t.set_fontsize(8)
        ax.legend(wedges, labels, loc="lower center",
                  bbox_to_anchor=(0.5, -0.25), ncol=2,
                  fontsize=7, framealpha=0, labelcolor="white")
        fig.tight_layout()
        FigureCanvasTkAgg(fig, master=parent).get_tk_widget().pack(padx=6, pady=(4, 10))

    def _bar_chart(self, parent):
        mc     = self.stats.method_counts
        labels = list(mc.keys())
        values = list(mc.values())
        color_map = {
            "metadata":  "#4A90D9",
            "ai":        "#27AE60",
            "heuristic": "#E67E22",
            "manual":    "#9B59B6",
        }
        colors = [color_map.get(l, "#7F8C8D") for l in labels]
        fig, ax = plt.subplots(figsize=(3.8, 3.2))
        fig.patch.set_facecolor("#2B3038")
        ax.set_facecolor("#2B3038")
        bars = ax.bar(labels, values, color=colors, edgecolor="none")
        ax.tick_params(colors="white", labelsize=8)
        for sp in ax.spines.values():
            sp.set_visible(False)
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.3,
                    str(v), ha="center", color="white", fontsize=9)
        fig.tight_layout()
        FigureCanvasTkAgg(fig, master=parent).get_tk_widget().pack(padx=6, pady=(4, 10))

    # ── Right panel — file browser ─────────────────────────────────────────────
    def _build_right(self, parent):
        ctk.CTkLabel(parent, text="Sorted Files",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(padx=12, pady=(12, 4))
        ctk.CTkLabel(parent, text="Right-click a file to reassign its body part",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(padx=12)

        # ttk.Treeview (native widget, works inside CTkFrame)
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(8, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Results.Treeview",
                        background="#242D3E", foreground="#E8EAF0",
                        rowheight=24, fieldbackground="#242D3E",
                        borderwidth=0)
        style.configure("Results.Treeview.Heading",
                        background="#1C2333", foreground="#8892A4",
                        relief="flat")
        style.map("Results.Treeview",
                  background=[("selected", "#4A90D9")],
                  foreground=[("selected", "white")])

        cols = ("body_part", "confidence", "method")
        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings",
            style="Results.Treeview", selectmode="browse",
        )
        self._tree.heading("body_part",  text="Body Part")
        self._tree.heading("confidence", text="Conf.")
        self._tree.heading("method",     text="Method")
        self._tree.column("body_part",  width=120, minwidth=80)
        self._tree.column("confidence", width=55,  minwidth=40)
        self._tree.column("method",     width=80,  minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        # Populate from manifest or stats
        self._populate_tree()

        # Right-click context menu
        self._ctx_menu = tk.Menu(self._tree, tearoff=0)
        self._tree.bind("<Button-3>",  self._on_right_click)
        self._tree.bind("<Button-2>",  self._on_right_click)  # macOS

        # Refresh button
        make_secondary_button(
            parent, "🔄 Refresh", command=self._populate_tree, width=120
        ).pack(pady=(0, 10))

    def _populate_tree(self):
        """Fill the treeview from manifest CSV or fallback to stats dict."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        manifest = Path(self.cfg.destination_folder) / "reports" / "manifest.csv"
        if manifest.exists():
            try:
                import pandas as pd
                df = pd.read_csv(manifest)
                for _, row in df.iterrows():
                    bp   = str(row.get("detected_body_part", ""))
                    conf = row.get("confidence_score", 0)
                    meth = str(row.get("detection_method", ""))
                    fp   = str(row.get("file_path", ""))
                    self._tree.insert(
                        "", "end",
                        iid=fp,
                        values=(bp, f"{float(conf):.0%}", meth),
                        tags=("low",) if float(conf) < 0.5 else (),
                    )
                self._tree.tag_configure("low", foreground=WARNING)
                return
            except Exception:
                pass

        # Fallback: show summary from stats
        for bp, count in (self.stats.body_part_counts or {}).items():
            self._tree.insert("", "end", values=(bp, f"{count} files", "—"))

    def _on_right_click(self, event):
        row = self._tree.identify_row(event.y)
        if not row:
            return
        self._tree.selection_set(row)
        self._ctx_file = row   # file path (used as iid) or summary label

        self._ctx_menu.delete(0, "end")
        self._ctx_menu.add_command(
            label="🔁  Reassign Body Part…",
            command=self._reassign_dialog,
        )
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(
            label="📂  Reveal in Folder",
            command=lambda: self._reveal_file(self._ctx_file),
        )
        self._ctx_menu.post(event.x_root, event.y_root)

    def _reassign_dialog(self):
        file_path = self._ctx_file
        if not Path(file_path).exists():
            ctk.CTkToplevel(self).destroy()
            return

        win = ctk.CTkToplevel(self)
        win.title("Reassign Body Part")
        win.geometry("420x260")
        win.grab_set()
        win.focus_set()

        ctk.CTkLabel(win, text="Reassign this file to a different body part:",
                     font=ctk.CTkFont(size=13)).pack(pady=(20, 8), padx=20)
        ctk.CTkLabel(win, text=Path(file_path).name,
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack()

        bp_var = ctk.StringVar(value=_ALL_BODY_PARTS[0])
        ctk.CTkOptionMenu(win, values=_ALL_BODY_PARTS, variable=bp_var,
                          width=260).pack(pady=(12, 0))

        def _do():
            self._move_file_to_body_part(file_path, bp_var.get())
            win.destroy()
            self._populate_tree()

        make_primary_button(win, "✓  Confirm & Move", command=_do, width=180).pack(pady=16)

    def _move_file_to_body_part(self, file_path: str, new_body_part: str):
        """Move file to the correct body-part subfolder and update manifest."""
        fp = Path(file_path)
        if not fp.exists():
            return
        try:
            import pydicom
            ds  = pydicom.dcmread(str(fp), force=True)
            mod = str(getattr(ds, "Modality", "")).upper()
        except Exception:
            mod = "Other"

        mod_label  = "MRI" if mod == "MR" else ("CT" if mod == "CT" else mod)
        target_dir = Path(self.cfg.destination_folder) / mod_label / new_body_part
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / fp.name
        try:
            shutil.move(str(fp), str(dest))
            self._update_manifest(str(fp), str(dest), new_body_part)
        except Exception as exc:
            from utils.logger import get_logger
            get_logger().error("Reassign move failed: %s", exc)

    def _update_manifest(self, old_path: str, new_path: str, new_bp: str):
        manifest = Path(self.cfg.destination_folder) / "reports" / "manifest.csv"
        if not manifest.exists():
            return
        try:
            import pandas as pd
            df = pd.read_csv(manifest)
            mask = df["file_path"] == old_path
            df.loc[mask, "file_path"]         = new_path
            df.loc[mask, "detected_body_part"] = new_bp
            df.loc[mask, "detection_method"]   = "manual"
            df.to_csv(manifest, index=False)
        except Exception:
            pass

    def _reveal_file(self, file_path: str):
        fp = Path(file_path)
        if not fp.exists():
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(fp)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(fp)])
            else:
                subprocess.Popen(["xdg-open", str(fp.parent)])
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────
    def _open_review(self):
        from gui.review_window import ReviewWindow
        ReviewWindow(self, self.cfg.destination_folder, self.cfg)

    def _open_review_tool(self):
        self._open_review()

    def _open_folder(self):
        p = self.cfg.destination_folder
        if not p:
            return
        try:
            if sys.platform == "win32":
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", p])
            else:
                subprocess.Popen(["xdg-open", p])
        except Exception:
            pass

    def _open_report(self):
        r = Path(self.cfg.destination_folder) / "reports" / "sorting_report.html"
        if r.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(r))
                else:
                    subprocess.Popen(["xdg-open", str(r)])
            except Exception:
                pass

    def _sort_more(self):
        self.destroy()
        if self.on_sort_more:
            self.on_sort_more()

    def _save_preset(self):
        from utils.config import save_preset
        win = ctk.CTkToplevel(self)
        win.title("Save Preset")
        win.geometry("380x180")
        win.grab_set()
        ctk.CTkLabel(win, text="Preset name:",
                     font=ctk.CTkFont(size=13)).pack(pady=(20, 4))
        nv = ctk.StringVar(value="my_preset")
        ctk.CTkEntry(win, textvariable=nv, width=260).pack()
        make_primary_button(win, "Save",
                            command=lambda: (save_preset(nv.get(), self.cfg),
                                            win.destroy()),
                            width=120).pack(pady=16)
