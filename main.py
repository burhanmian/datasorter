"""
DICOM Organizer — Application entry point.
Run via DICOM_Organizer.bat (recommended) or: python main.py
"""
from __future__ import annotations

import sys
import os
import threading

# Ensure project root is on sys.path when run from any working directory
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Dependency guard ──────────────────────────────────────────────────────────
def _check_deps():
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        _r = _tk.Tk()
        _r.withdraw()
        _mb.showerror(
            "Missing Dependencies",
            "Required packages are not yet installed.\n\n"
            "Please double-click  DICOM_Organizer.bat  to install them "
            "automatically and launch the app.",
        )
        _r.destroy()
        sys.exit(1)

_check_deps()

# ── Normal startup ────────────────────────────────────────────────────────────
from utils.config import load_settings, save_settings, SortConfig
from utils.logger import setup_logger

setup_logger()


def _ensure_ai_model():
    """
    Download the AI model weights if missing, showing a GUI progress window.
    Safe to call even when AI is disabled — exits immediately in that case.
    Blocks until the download completes or fails, then returns.
    """
    from download_model import MODEL_PATH, MODEL_URL, MARKER_PATH, MODEL_DIR

    # Already downloaded or previously failed → nothing to do
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_024:
        return
    if MARKER_PATH.exists():
        return

    import customtkinter as ctk
    from gui.theme import ACCENT, MUTED, SUCCESS, WARNING

    win = ctk.CTk()
    win.title("DICOM Organizer — Downloading AI Model")
    win.geometry("500x230")
    win.resizable(False, False)
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"500x230+{(sw-500)//2}+{(sh-230)//2}")

    ctk.CTkLabel(
        win, text="Downloading AI Model Weights",
        font=ctk.CTkFont(size=15, weight="bold"),
    ).pack(pady=(28, 4))
    ctk.CTkLabel(
        win,
        text="One-time download (~44 MB). The app still works without it\n"
             "— it will fall back to heuristic detection if this fails.",
        font=ctk.CTkFont(size=11), text_color=MUTED, justify="center",
    ).pack()

    pbar = ctk.CTkProgressBar(win, width=440, height=16, corner_radius=8)
    pbar.set(0)
    pbar.pack(pady=(18, 4))

    status = ctk.CTkLabel(win, text="Connecting…",
                          font=ctk.CTkFont(size=11), text_color=MUTED)
    status.pack()

    def _download():
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import urllib.request

            def _report(block_num, block_size, total_size):
                if total_size > 0:
                    pct = min(block_num * block_size / total_size, 1.0)
                    mb  = block_num * block_size / 1_048_576
                    tot = total_size / 1_048_576
                    try:
                        win.after(0, lambda p=pct: pbar.set(p))
                        win.after(0, lambda m=mb, t=tot:
                                  status.configure(text=f"{m:.1f} MB / {t:.1f} MB"))
                    except Exception:
                        pass

            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook=_report)
            try:
                win.after(0, lambda: pbar.set(1.0))
                win.after(0, lambda: status.configure(
                    text="✅  Download complete!", text_color=SUCCESS))
                win.after(1200, win.destroy)
            except Exception:
                pass
        except Exception as exc:
            MARKER_PATH.write_text("failed")
            if MODEL_PATH.exists():
                MODEL_PATH.unlink(missing_ok=True)
            try:
                win.after(0, lambda: status.configure(
                    text=f"⚠️  Download failed — heuristics will be used",
                    text_color=WARNING))
                win.after(2500, win.destroy)
            except Exception:
                pass

    threading.Thread(target=_download, daemon=True).start()
    win.mainloop()


def launch_wizard(mode: str, config: SortConfig):
    from gui.wizard_window import WizardWindow

    def _on_start(cfg: SortConfig):
        save_settings(cfg)
        launch_processing(cfg)

    WizardWindow(config, on_start=_on_start).mainloop()


def launch_processing(config: SortConfig):
    from core.organizer import Organizer
    from gui.progress_window import ProgressWindow

    # Download AI model weights if needed (shows GUI progress)
    if config.enable_ai_detection:
        _ensure_ai_model()

    organizer = Organizer(config)
    prog      = ProgressWindow(config, organizer)
    prog.set_on_done(lambda stats: prog.after(1200,
                     lambda: _open_results(prog, config, stats)))
    prog.mainloop()


def _open_results(parent, config: SortConfig, stats):
    parent.destroy()
    from gui.results_window import ResultsWindow
    ResultsWindow(config, stats, on_sort_more=launch_welcome).mainloop()


def launch_welcome():
    from gui.welcome_window import WelcomeWindow

    config           = load_settings()
    is_first         = config.first_run
    config.first_run = False
    save_settings(config)

    def _on_mode(mode: str):
        config.mode = mode
        launch_wizard(mode, config)

    WelcomeWindow(config, on_mode_selected=_on_mode,
                  show_tutorial=is_first).mainloop()


if __name__ == "__main__":
    launch_welcome()
