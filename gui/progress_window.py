"""
Window 3 — Processing / progress screen.
"""
from __future__ import annotations

import queue
import time
import tkinter as tk
from datetime import datetime
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import apply_theme, make_title, make_subtitle, make_card, ACCENT, MUTED, SUCCESS, WARNING, DANGER
from utils.config import SortConfig
from utils.logger import get_log_queue


class ProgressWindow(ctk.CTk):
    def __init__(self, config: SortConfig, organizer):
        super().__init__()
        self.cfg = config
        self.organizer = organizer

        apply_theme(config.theme)
        self.title("DICOM Organizer — Processing")
        self.geometry("1000x700")
        self.minsize(820, 580)
        self.resizable(True, True)
        self._center()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._start_time = time.time()
        self._total = 0
        self._current = 0
        self._paused = False
        self._bp_counts: dict[str, int] = {}
        self._method_counts: dict[str, int] = {}
        self._log_queue = get_log_queue()
        self._on_done_callback = None

        self._build_ui()
        self._start_organizer()
        self._poll()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1000x700+{(sw-1000)//2}+{(sh-700)//2}")

    def set_on_done(self, callback):
        self._on_done_callback = callback

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Left panel — progress & log
        left = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)

        make_title(left, "⚙️  Processing…", size=18).pack(anchor="w")
        self._phase_lbl = ctk.CTkLabel(left, text="Initialising…", text_color=ACCENT,
                                       font=ctk.CTkFont(size=12))
        self._phase_lbl.pack(anchor="w", pady=(2, 8))

        # Overall progress
        self._progress_bar = ctk.CTkProgressBar(left, height=18, corner_radius=9)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", pady=(0, 4))

        prog_row = ctk.CTkFrame(left, fg_color="transparent")
        prog_row.pack(fill="x")
        self._prog_lbl = ctk.CTkLabel(prog_row, text="0 / 0 files", font=ctk.CTkFont(size=12))
        self._prog_lbl.pack(side="left")
        self._eta_lbl = ctk.CTkLabel(prog_row, text="ETA: —", font=ctk.CTkFont(size=12), text_color=MUTED)
        self._eta_lbl.pack(side="right")

        self._current_file_lbl = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11),
                                               text_color=MUTED, wraplength=500)
        self._current_file_lbl.pack(anchor="w", pady=(4, 0))

        # Counters
        counters = make_card(left)
        counters.pack(fill="x", pady=(14, 0))
        counters.columnconfigure((0, 1, 2, 3, 4), weight=1)

        self._counter_labels: dict[str, ctk.CTkLabel] = {}
        for col, (key, label, color) in enumerate([
            ("sorted", "Sorted", SUCCESS),
            ("skipped", "Skipped", MUTED),
            ("errors", "Errors", DANGER),
            ("review", "Review", WARNING),
            ("detected", "Detected", ACCENT),
        ]):
            col_frame = ctk.CTkFrame(counters, fg_color="transparent")
            col_frame.grid(row=0, column=col, padx=8, pady=10)
            val_lbl = ctk.CTkLabel(col_frame, text="0", font=ctk.CTkFont(size=22, weight="bold"),
                                   text_color=color)
            val_lbl.pack()
            ctk.CTkLabel(col_frame, text=label, font=ctk.CTkFont(size=10), text_color=MUTED).pack()
            self._counter_labels[key] = val_lbl

        # Control buttons
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", pady=12)

        self._pause_btn = ctk.CTkButton(
            btn_row, text="⏸ Pause", width=110, command=self._toggle_pause,
            fg_color=WARNING, hover_color="#D35400", corner_radius=8,
        )
        self._pause_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="✖ Cancel", width=110, command=self._cancel,
            fg_color=DANGER, hover_color="#C0392B", corner_radius=8,
        ).pack(side="left")

        # Live log
        ctk.CTkLabel(left, text="Live Log", font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", pady=(8, 2)
        )
        self._log_box = ctk.CTkTextbox(left, height=180, font=ctk.CTkFont(family="Courier", size=10))
        self._log_box.pack(fill="both", expand=True)
        self._log_box.configure(state="disabled")

        # Right panel — live chart
        right = ctk.CTkFrame(self, width=300, corner_radius=12)
        right.pack(side="right", fill="y", padx=(0, 20), pady=20)
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="Body Parts Detected", font=ctk.CTkFont(size=13, weight="bold")).pack(
            padx=12, pady=(12, 4)
        )
        self._fig, self._ax = plt.subplots(figsize=(3.2, 5))
        self._fig.patch.set_facecolor("#2B3038")
        self._ax.set_facecolor("#2B3038")
        self._canvas = FigureCanvasTkAgg(self._fig, master=right)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        self._draw_chart()

    # ------------------------------------------------------------------
    # Organizer callbacks
    # ------------------------------------------------------------------
    def _start_organizer(self):
        self.organizer.on_progress = self._on_progress
        self.organizer.on_file_done = self._on_file_done
        self.organizer.on_phase = self._on_phase
        self.organizer.on_log = self._on_log_msg
        self.organizer.on_done = self._on_done
        self.organizer.on_error = self._on_error
        self.organizer.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self._current = current
        self._total = total
        # Schedule GUI update on main thread
        self.after(0, lambda: self._update_progress(current, total, filename))

    def _update_progress(self, current: int, total: int, filename: str):
        if total > 0:
            self._progress_bar.set(current / total)
        self._prog_lbl.configure(text=f"{current} / {total} files")
        self._current_file_lbl.configure(text=f"Processing: {filename}")

        # ETA
        elapsed = time.time() - self._start_time
        if current > 0:
            rate = current / elapsed
            remaining = (total - current) / rate if rate > 0 else 0
            mins, secs = divmod(int(remaining), 60)
            self._eta_lbl.configure(text=f"ETA: {mins}m {secs}s")

    def _on_file_done(self, body_part: str, method: str, confidence: float):
        self._bp_counts[body_part] = self._bp_counts.get(body_part, 0) + 1
        self._method_counts[method] = self._method_counts.get(method, 0) + 1
        self.after(0, self._update_counters)

    def _on_phase(self, phase: str):
        self.after(0, lambda: self._phase_lbl.configure(text=phase))

    def _on_log_msg(self, msg: str):
        self.after(0, lambda: self._append_log(msg))

    def _on_done(self, stats):
        self.after(0, lambda: self._handle_done(stats))

    def _on_error(self, msg: str):
        self.after(0, lambda: self._append_log(f"ERROR: {msg}"))

    def _handle_done(self, stats):
        self._phase_lbl.configure(text="✅ Complete!", text_color=SUCCESS)
        self._progress_bar.set(1.0)
        self._pause_btn.configure(state="disabled")
        if self._on_done_callback:
            self._on_done_callback(stats)

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _update_counters(self):
        from core.organizer import OrganizerStats
        stats = self.organizer.stats
        self._counter_labels["sorted"].configure(text=str(stats.sorted_ok))
        self._counter_labels["skipped"].configure(text=str(stats.skipped))
        self._counter_labels["errors"].configure(text=str(stats.errors))
        self._counter_labels["review"].configure(text=str(stats.review_needed))
        self._counter_labels["detected"].configure(text=str(sum(self._bp_counts.values())))
        self._draw_chart()

    def _append_log(self, msg: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _draw_chart(self):
        self._ax.clear()
        if not self._bp_counts:
            self._ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                          color="white", fontsize=10, transform=self._ax.transAxes)
        else:
            parts = list(self._bp_counts.keys())
            counts = list(self._bp_counts.values())
            colors = plt.cm.Set3(range(len(parts)))
            bars = self._ax.barh(parts, counts, color=colors)
            self._ax.set_facecolor("#2B3038")
            self._ax.tick_params(colors="white", labelsize=8)
            for spine in self._ax.spines.values():
                spine.set_visible(False)
            for bar, count in zip(bars, counts):
                self._ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                              str(count), va="center", color="white", fontsize=8)
        self._fig.tight_layout()
        self._canvas.draw()

    def _poll(self):
        """Drain the log queue and update UI periodically."""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.after(200, self._poll)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _toggle_pause(self):
        if self._paused:
            self.organizer.resume()
            self._pause_btn.configure(text="⏸ Pause")
            self._paused = False
        else:
            self.organizer.pause()
            self._pause_btn.configure(text="▶ Resume")
            self._paused = True

    def _cancel(self):
        self.organizer.cancel()
        self._phase_lbl.configure(text="Cancelling…", text_color=DANGER)

    def _on_close(self):
        self.organizer.cancel()
        self.destroy()
