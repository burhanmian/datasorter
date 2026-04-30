"""
DICOM Organizer — Application entry point.
Run via DICOM_Organizer.bat (recommended) or: python main.py
"""
from __future__ import annotations

import sys
import os

# Ensure project root is on sys.path when run from any working directory
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Dependency guard ──────────────────────────────────────────────────────────
# Show a friendly dialog instead of a raw ImportError if packages are missing.
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


def launch_wizard(mode: str, config: SortConfig):
    from gui.wizard_window import WizardWindow

    def _on_start(cfg: SortConfig):
        save_settings(cfg)
        launch_processing(cfg)

    WizardWindow(config, on_start=_on_start).mainloop()


def launch_processing(config: SortConfig):
    from core.organizer import Organizer
    from gui.progress_window import ProgressWindow

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

    config            = load_settings()
    is_first          = config.first_run
    config.first_run  = False
    save_settings(config)

    def _on_mode(mode: str):
        config.mode = mode
        launch_wizard(mode, config)

    WelcomeWindow(config, on_mode_selected=_on_mode,
                  show_tutorial=is_first).mainloop()


if __name__ == "__main__":
    launch_welcome()
