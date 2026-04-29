"""
Window 4 — Results & Summary screen.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import apply_theme, make_title, make_subtitle, make_card, make_primary_button, make_secondary_button, ACCENT, SUCCESS, WARNING, DANGER, MUTED
from utils.config import SortConfig


class ResultsWindow(ctk.CTk):
    def __init__(self, config: SortConfig, stats, on_sort_more=None):
        super().__init__()
        self.cfg = config
        self.stats = stats
        self.on_sort_more = on_sort_more

        apply_theme(config.theme)
        self.title("DICOM Organizer — Results")
        self.geometry("1000x720")
        self.minsize(800, 600)
        self.resizable(True, True)
        self._center()

        self._build_ui()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1000x720+{(sw-1000)//2}+{(sh-720)//2}")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=20)

        # Header
        make_title(scroll, "✅  Organisation Complete!", size=22).pack(anchor="w", pady=(0, 4))
        make_subtitle(scroll, "Your DICOM files have been sorted successfully.").pack(anchor="w")

        # Stats row
        stats_row = ctk.CTkFrame(scroll, fg_color="transparent")
        stats_row.pack(fill="x", pady=(20, 0))

        for value, label, color in [
            (str(self.stats.sorted_ok), "Files Sorted", SUCCESS),
            (str(self.stats.skipped), "Skipped", MUTED),
            (str(self.stats.errors), "Errors", DANGER),
            (str(self.stats.review_needed), "Need Review", WARNING),
            (str(len(self.stats.body_part_counts)), "Body Parts", ACCENT),
        ]:
            card = make_card(stats_row)
            card.pack(side="left", padx=6, pady=4)
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=28, weight="bold"),
                         text_color=color).pack(padx=20, pady=(16, 2))
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11),
                         text_color=MUTED).pack(padx=20, pady=(0, 14))

        # Review warning
        if self.stats.review_needed > 0:
            warn = make_card(scroll)
            warn.pack(fill="x", pady=(16, 0))
            warn_inner = ctk.CTkFrame(warn, fg_color="transparent")
            warn_inner.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(
                warn_inner,
                text=f"⚠️  {self.stats.review_needed} files need manual review — "
                     f"confidence was too low to sort automatically.",
                text_color=WARNING,
                font=ctk.CTkFont(size=13, weight="bold"),
                wraplength=620,
            ).pack(side="left", fill="x", expand=True)
            make_primary_button(
                warn_inner, "🔍 Open Review Tool",
                command=self._open_review_tool, width=180,
            ).pack(side="right", padx=(12, 0))

        # Charts row
        charts_row = ctk.CTkFrame(scroll, fg_color="transparent")
        charts_row.pack(fill="x", pady=(20, 0))
        charts_row.columnconfigure((0, 1), weight=1)

        # Pie chart — body part distribution
        if self.stats.body_part_counts:
            pie_card = make_card(charts_row)
            pie_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
            ctk.CTkLabel(pie_card, text="Body Part Distribution",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(10, 0))
            self._add_pie_chart(pie_card)

        # Bar chart — detection method breakdown
        if self.stats.method_counts:
            bar_card = make_card(charts_row)
            bar_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
            ctk.CTkLabel(bar_card, text="Detection Method Breakdown",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(10, 0))
            self._add_bar_chart(bar_card)

        # Action buttons
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(24, 0))

        make_primary_button(btn_row, "📂 Open Output Folder",
                            command=self._open_folder, width=200).pack(side="left", padx=(0, 10))
        make_primary_button(btn_row, "📄 View Report",
                            command=self._open_report, width=160).pack(side="left", padx=(0, 10))
        make_secondary_button(btn_row, "🔄 Sort More",
                              command=self._sort_more, width=130).pack(side="left", padx=(0, 10))
        make_secondary_button(btn_row, "💾 Save Preset",
                              command=self._save_preset, width=130).pack(side="left")

    def _add_pie_chart(self, parent):
        bp = self.stats.body_part_counts
        labels = list(bp.keys())
        values = list(bp.values())

        fig, ax = plt.subplots(figsize=(4, 3.5))
        fig.patch.set_facecolor("#2B3038")
        ax.set_facecolor("#2B3038")
        wedges, texts, autotexts = ax.pie(
            values, labels=None, autopct="%1.0f%%",
            colors=plt.cm.Set3(range(len(labels))), startangle=90,
        )
        for t in autotexts:
            t.set_color("white")
            t.set_fontsize(8)
        ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.22),
                  ncol=2, fontsize=7, framealpha=0, labelcolor="white")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(padx=8, pady=(4, 12))

    def _add_bar_chart(self, parent):
        mc = self.stats.method_counts
        labels = list(mc.keys())
        values = list(mc.values())

        fig, ax = plt.subplots(figsize=(3.8, 3.5))
        fig.patch.set_facecolor("#2B3038")
        ax.set_facecolor("#2B3038")
        colors = [{"metadata": "#4A90D9", "ai": "#27AE60", "heuristic": "#E67E22", "manual": "#9B59B6"}.get(l, "#7F8C8D") for l in labels]
        bars = ax.bar(labels, values, color=colors, edgecolor="none")
        ax.set_facecolor("#2B3038")
        ax.tick_params(colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, str(val),
                    ha="center", color="white", fontsize=9)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(padx=8, pady=(4, 12))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _open_folder(self):
        path = self.cfg.destination_folder
        if not path:
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _open_report(self):
        report = Path(self.cfg.destination_folder) / "reports" / "sorting_report.html"
        if report.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(report))
                else:
                    subprocess.Popen(["xdg-open", str(report)])
            except Exception:
                pass

    def _sort_more(self):
        self.destroy()
        if self.on_sort_more:
            self.on_sort_more()

    def _open_review_tool(self):
        from gui.review_window import ReviewWindow
        ReviewWindow(self, self.cfg.destination_folder, self.cfg)

    def _save_preset(self):
        from utils.config import save_preset
        win = ctk.CTkToplevel(self)
        win.title("Save Preset")
        win.geometry("380x180")
        win.grab_set()

        ctk.CTkLabel(win, text="Preset name:", font=ctk.CTkFont(size=13)).pack(pady=(20, 4))
        name_var = ctk.StringVar(value="my_preset")
        entry = ctk.CTkEntry(win, textvariable=name_var, width=260)
        entry.pack()

        def do_save():
            save_preset(name_var.get(), self.cfg)
            win.destroy()

        make_primary_button(win, "Save", command=do_save, width=120).pack(pady=16)
