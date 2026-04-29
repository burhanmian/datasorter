"""
DICOM Organizer — Main entry point.

Double-click this file (or run_app.bat) to launch the application.
"""
from __future__ import annotations

import sys
import os

# Ensure the project root is on sys.path regardless of where Python is invoked
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# --- Dependency check / auto-install ---
def _ensure_deps():
    """Install requirements if any critical package is missing."""
    import importlib
    import subprocess

    req_file = os.path.join(ROOT, "requirements.txt")
    if not os.path.exists(req_file):
        return

    missing: list[str] = []
    pkg_map = {
        "customtkinter": "customtkinter",
        "pydicom": "pydicom",
        "pandas": "pandas",
        "numpy": "numpy",
        "PIL": "Pillow",
        "matplotlib": "matplotlib",
        "sklearn": "scikit-learn",
    }

    for import_name, pkg_name in pkg_map.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        print(f"[DICOM Organizer] Installing missing packages: {', '.join(missing)}")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", req_file,
                "--quiet", "--disable-pip-version-check",
            ])
            print("[DICOM Organizer] Installation complete — restarting…")
            # Restart the script after installing
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"[DICOM Organizer] Auto-install failed: {e}")
            print("Please run: pip install -r requirements.txt")
            sys.exit(1)


_ensure_deps()

# --- Launch GUI ---
import tkinter as tk
from utils.config import load_settings, save_settings, SortConfig
from utils.logger import setup_logger, get_logger

log = setup_logger()


def launch_wizard(mode: str, config: SortConfig):
    """Open the configuration wizard for the selected mode."""
    from gui.wizard_window import WizardWindow

    def on_start(cfg: SortConfig):
        save_settings(cfg)
        launch_processing(cfg)

    wiz = WizardWindow(config, on_start=on_start)
    wiz.mainloop()


def launch_processing(config: SortConfig):
    """Open the progress window and start the organizer."""
    from core.organizer import Organizer
    from gui.progress_window import ProgressWindow

    organizer = Organizer(config)

    prog = ProgressWindow(config, organizer)

    def on_done(stats):
        prog.after(1200, lambda: _open_results(prog, config, stats))

    prog.set_on_done(on_done)
    prog.mainloop()


def _open_results(parent_win, config: SortConfig, stats):
    parent_win.destroy()
    from gui.results_window import ResultsWindow

    def on_sort_more():
        launch_welcome()

    res = ResultsWindow(config, stats, on_sort_more=on_sort_more)

    # Add review button if needed
    if stats.review_needed > 0:
        from gui.review_window import ReviewWindow
        review_btn_frame = tk.Frame(res, bg="#2B3038")
        review_btn_frame.pack()

    res.mainloop()


def launch_welcome():
    """Show the welcome / mode selection screen."""
    from gui.welcome_window import WelcomeWindow

    config = load_settings()
    config.first_run = False
    save_settings(config)

    def on_mode(mode: str):
        config.mode = mode
        launch_wizard(mode, config)

    welcome = WelcomeWindow(config, on_mode_selected=on_mode)
    welcome.mainloop()


if __name__ == "__main__":
    launch_welcome()
