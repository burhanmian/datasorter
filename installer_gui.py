"""
DICOM Organizer — Professional Installer
=========================================
Builds into a single DICOM_Organizer_Setup.exe (Windows) or
DICOM_Organizer_Setup (Linux/macOS) via the build_installer script.

Pure stdlib only (tkinter) — safe to run before any packages are installed.
Cross-platform: Windows, Linux, macOS.

Usage:
  python installer_gui.py          # run directly (development)
  DICOM_Organizer_Setup.exe        # run built installer (distribution)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

# ── Hide console on Windows ───────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME    = "DICOM Organizer"
APP_VERSION = "1.0"
IS_WINDOWS  = sys.platform == "win32"
IS_MAC      = sys.platform == "darwin"

# Default install locations per platform
if IS_WINDOWS:
    _base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    DEFAULT_DIR = _base / "DICOMOrganizer"
elif IS_MAC:
    DEFAULT_DIR = Path.home() / "Applications" / "DICOMOrganizer"
else:
    DEFAULT_DIR = Path.home() / ".local" / "share" / "dicom-organizer"

# Packages
CORE_PACKAGES = [
    "customtkinter>=5.2",
    "pydicom>=2.4",
    "pandas>=2.0",
    "numpy>=1.24",
    "Pillow>=10.0",
    "matplotlib>=3.7",
    "scikit-learn>=1.3",
    "scipy>=1.11",
    "tqdm>=4.65",
    "requests>=2.31",
    "packaging>=23.0",
    "tkinterdnd2>=0.3",
]
AI_CPU_PKGS  = ["torch", "torchvision"]
AI_GPU_PKGS  = ["torch", "torchvision"]
CONV_PKGS    = ["SimpleITK==2.3.1", "dicom2nifti==2.4.8"]
TORCH_CPU_URL = "https://download.pytorch.org/whl/cpu"
TORCH_GPU_URL = "https://download.pytorch.org/whl/cu121"

# ── Colours ───────────────────────────────────────────────────────────────────
BG    = "#1C2333"
BG2   = "#242D3E"
BG3   = "#2D3748"
FG    = "#E8EAF0"
MUTED = "#8892A4"
ACCENT= "#4A90D9"
OK    = "#2ECC71"
WARN  = "#F39C12"
ERR   = "#E74C3C"
WHITE = "#FFFFFF"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bundle_dir() -> Path:
    """Source tree root — PyInstaller temp dir or project root."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _find_python() -> str | None:
    """
    Locate a real Python 3.9+ executable.
    When bundled by PyInstaller sys.executable is the .exe itself, so we
    must search for an installed Python separately.
    """
    candidates: list[str] = []

    # If running as normal Python (not bundled), current interpreter is fine
    if not hasattr(sys, "_MEIPASS"):
        candidates.append(sys.executable)

    # PATH search
    for name in ("python3", "python3.12", "python3.11", "python3.10", "python3.9", "python"):
        p = shutil.which(name)
        if p:
            candidates.append(p)

    # Windows-specific: check registry + common paths
    if IS_WINDOWS:
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for sub in (
                    r"SOFTWARE\Python\PythonCore",
                    r"SOFTWARE\WOW6432Node\Python\PythonCore",
                ):
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            i = 0
                            while True:
                                try:
                                    ver = winreg.EnumKey(k, i)
                                    with winreg.OpenKey(k, rf"{ver}\InstallPath") as ip:
                                        path = winreg.QueryValue(ip, None)
                                        candidates.append(
                                            str(Path(path) / "python.exe"))
                                    i += 1
                                except OSError:
                                    break
                    except OSError:
                        pass
        except ImportError:
            pass
        for drive in ("C", "D"):
            for ver in ("312", "311", "310", "39"):
                candidates.append(rf"{drive}:\Python{ver}\python.exe")

    # Linux/macOS common paths
    for p in ("/usr/bin/python3", "/usr/local/bin/python3",
              "/opt/homebrew/bin/python3", "/opt/local/bin/python3"):
        candidates.append(p)

    seen: set[str] = set()
    for c in candidates:
        c = str(c)
        if c in seen:
            continue
        seen.add(c)
        if not Path(c).exists():
            continue
        if IS_WINDOWS and "WindowsApps" in c:
            continue  # MS Store stub — unusable for venv
        try:
            r = subprocess.run(
                [c, "-c",
                 "import sys; v=sys.version_info; "
                 "exit(0 if v>=(3,9) else 1)"],
                capture_output=True, timeout=6,
            )
            if r.returncode == 0:
                return c
        except Exception:
            pass

    return None


def _check_cuda() -> bool:
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _create_shortcut_windows(target: str, args: str, working_dir: str,
                              shortcut_path: str, description: str = "") -> bool:
    ps = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{shortcut_path}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.Arguments = '{args}'; "
        f"$s.WorkingDirectory = '{working_dir}'; "
        f"$s.Description = '{description}'; "
        f"$s.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-Command", ps],
            capture_output=True, timeout=15,
        )
        return True
    except Exception:
        return False


def _create_shortcut_linux(exec_cmd: str, name: str,
                            desktop_path: str, icon: str = "") -> bool:
    content = (
        "[Desktop Entry]\n"
        f"Name={name}\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon}\n"
        "Type=Application\n"
        "Categories=Science;MedicalSoftware;\n"
        "Terminal=false\n"
    )
    try:
        Path(desktop_path).write_text(content, encoding="utf-8")
        Path(desktop_path).chmod(0o755)
        return True
    except Exception:
        return False


# ── Main installer class ──────────────────────────────────────────────────────

class InstallerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} {APP_VERSION} — Setup")
        self.root.geometry("720x540")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"720x540+{(sw-720)//2}+{(sh-540)//2}")

        # State vars
        self._install_dir      = tk.StringVar(value=str(DEFAULT_DIR))
        self._include_ai       = tk.BooleanVar(value=True)
        self._use_gpu          = tk.BooleanVar(value=False)
        self._include_conv     = tk.BooleanVar(value=True)
        self._desktop_shortcut = tk.BooleanVar(value=True)
        self._menu_shortcut    = tk.BooleanVar(value=True)
        self._accept_var       = tk.BooleanVar(value=False)
        self._launch_now       = tk.BooleanVar(value=True)

        self._page    = 0
        self._pages: list[tk.Frame] = []
        self._python_exe: str | None = None
        self._cuda_avail = False

        # Install results
        self._installed_venv_python: str = ""
        self._installed_main_py: str     = ""
        self._installed_dir: Path        = DEFAULT_DIR

        self._build_header()
        self._build_content()
        self._build_nav()
        self._show_page(0)

        # Background checks
        threading.Thread(target=self._bg_checks, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _lbl(self, parent, text, size=11, weight="normal", color=None, **kw):
        return tk.Label(parent, text=text, bg=BG,
                        fg=color or FG,
                        font=("Segoe UI" if IS_WINDOWS else "Sans", size, weight),
                        **kw)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=ACCENT, height=68)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self._lbl(hdr, f"🏥  {APP_NAME}  —  Setup",
                  size=17, weight="bold", color=WHITE).pack(
            side="left", padx=24, pady=16)
        self._lbl(hdr, f"v{APP_VERSION}",
                  size=10, color="#D0E8FF").pack(side="right", padx=20)

    def _build_content(self):
        self._container = tk.Frame(self.root, bg=BG)
        self._container.pack(fill="both", expand=True)

        self._pages = [
            self._page_welcome(),
            self._page_license(),
            self._page_directory(),
            self._page_components(),
            self._page_install(),
            self._page_finish(),
        ]

    def _build_nav(self):
        sep = tk.Frame(self.root, bg=BG3, height=1)
        sep.pack(fill="x")

        nav = tk.Frame(self.root, bg=BG2, height=56)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)

        self._cancel_btn = tk.Button(
            nav, text="Cancel", command=self._on_close,
            bg=BG2, fg=MUTED, relief="flat",
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
            padx=14, pady=6, cursor="hand2",
        )
        self._cancel_btn.pack(side="left", padx=16, pady=12)

        self._step_lbl = tk.Label(nav, text="", bg=BG2, fg=MUTED,
                                  font=("Segoe UI" if IS_WINDOWS else "Sans", 9))
        self._step_lbl.pack(side="left", padx=4)

        self._next_btn = tk.Button(
            nav, text="Next  →", command=self._next,
            bg=ACCENT, fg=WHITE, relief="flat",
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10, "bold"),
            padx=22, pady=6, cursor="hand2",
        )
        self._next_btn.pack(side="right", padx=16, pady=12)

        self._back_btn = tk.Button(
            nav, text="←  Back", command=self._back,
            bg=BG2, fg=MUTED, relief="flat",
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
            padx=14, pady=6, cursor="hand2", state="disabled",
        )
        self._back_btn.pack(side="right", padx=4, pady=12)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _page_welcome(self) -> tk.Frame:
        f = tk.Frame(self._container, bg=BG)

        tk.Frame(f, bg=BG, height=30).pack()
        self._lbl(f, "Welcome to DICOM Organizer Setup",
                  size=16, weight="bold").pack(pady=(0, 12))

        body = (
            "This wizard will install DICOM Organizer on your computer.\n\n"
            "DICOM Organizer automatically sorts MRI and CT medical image\n"
            "files into neat, labelled folders using a 3-layer detection\n"
            "engine: DICOM metadata → AI vision → anatomical heuristics.\n\n"
            "Please close all other applications before continuing."
        )
        self._lbl(f, body, color=MUTED, justify="center").pack(pady=4)

        self._python_status = tk.Label(
            f, text="  Checking Python…  ",
            bg=BG2, fg=MUTED,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 9),
        )
        self._python_status.pack(pady=(24, 0))

        self._lbl(f, "Click  Next →  to continue.",
                  color=ACCENT, size=10).pack(pady=(16, 0))
        return f

    def _page_license(self) -> tk.Frame:
        f = tk.Frame(self._container, bg=BG)
        self._lbl(f, "License Agreement", size=14, weight="bold").pack(
            pady=(24, 10), anchor="w", padx=36)

        box_frame = tk.Frame(f, bg=BG2, bd=0, relief="flat")
        box_frame.pack(fill="both", expand=True, padx=36, pady=(0, 8))

        sb = tk.Scrollbar(box_frame)
        sb.pack(side="right", fill="y")
        box = tk.Text(
            box_frame, bg=BG2, fg=MUTED,
            font=("Courier" if IS_WINDOWS else "Monospace", 9),
            relief="flat", wrap="word",
            yscrollcommand=sb.set, padx=10, pady=8,
        )
        sb.config(command=box.yview)
        box.pack(fill="both", expand=True)
        box.insert("end",
            "DICOM Organizer — Free for Research and Educational Use\n\n"
            "Copyright © 2025  DICOM Organizer Contributors\n\n"
            "Permission is hereby granted, free of charge, to any person "
            "obtaining a copy of this software and associated documentation "
            "files (the \"Software\"), to deal in the Software without "
            "restriction, including without limitation the rights to use, "
            "copy, modify, merge, publish, distribute, sublicense, and/or "
            "sell copies of the Software, and to permit persons to whom the "
            "Software is furnished to do so, subject to the following "
            "conditions:\n\n"
            "The above copyright notice and this permission notice shall be "
            "included in all copies or substantial portions of the Software.\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY "
            "KIND, EXPRESS OR IMPLIED. IN NO EVENT SHALL THE AUTHORS BE "
            "LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM "
            "THE USE OF THIS SOFTWARE.\n\n"
            "Third-party components (PyTorch, pydicom, customtkinter, pandas, "
            "matplotlib, scikit-learn, etc.) are subject to their own "
            "respective open-source licenses."
        )
        box.configure(state="disabled")

        cb_row = tk.Frame(f, bg=BG)
        cb_row.pack(anchor="w", padx=36, pady=(4, 0))
        tk.Checkbutton(
            cb_row, text="I accept the terms of the license agreement",
            variable=self._accept_var,
            bg=BG, fg=FG, selectcolor=BG2,
            activebackground=BG, activeforeground=FG,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
            command=self._update_next_state,
        ).pack(side="left")
        return f

    def _page_directory(self) -> tk.Frame:
        f = tk.Frame(self._container, bg=BG)
        self._lbl(f, "Installation Directory", size=14, weight="bold").pack(
            pady=(24, 8), anchor="w", padx=36)
        self._lbl(f, "Choose where DICOM Organizer will be installed:",
                  color=MUTED).pack(anchor="w", padx=36, pady=(0, 10))

        row = tk.Frame(f, bg=BG)
        row.pack(fill="x", padx=36)
        entry = tk.Entry(
            row, textvariable=self._install_dir,
            bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
        )
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        tk.Button(
            row, text="Browse…", command=self._browse_dir,
            bg=BG3, fg=FG, relief="flat",
            padx=10, pady=5, cursor="hand2",
        ).pack(side="left")

        self._lbl(
            f,
            "Estimated space: ~600 MB (core)  ·  +220 MB (AI/CPU)  ·  +2.5 GB (AI/GPU)",
            color=MUTED, size=9,
        ).pack(anchor="w", padx=36, pady=(18, 0))

        # Shortcut options
        tk.Frame(f, bg=BG3, height=1).pack(fill="x", padx=36, pady=(18, 12))
        self._lbl(f, "Shortcuts:", weight="bold").pack(anchor="w", padx=36)
        for var, text in [
            (self._desktop_shortcut, "Create Desktop shortcut"),
            (self._menu_shortcut,
             "Add to Start Menu" if IS_WINDOWS else "Add to application menu"),
        ]:
            tk.Checkbutton(
                f, text=text, variable=var,
                bg=BG, fg=FG, selectcolor=BG2,
                activebackground=BG, activeforeground=FG,
                font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
            ).pack(anchor="w", padx=48, pady=2)
        return f

    def _page_components(self) -> tk.Frame:
        f = tk.Frame(self._container, bg=BG)
        self._lbl(f, "Choose Components", size=14, weight="bold").pack(
            pady=(24, 8), anchor="w", padx=36)

        def _row(label, desc, var, fixed=False):
            card = tk.Frame(f, bg=BG2, relief="flat")
            card.pack(fill="x", padx=36, pady=4)
            left = tk.Frame(card, bg=BG2)
            left.pack(side="left", padx=(10, 0), pady=10)
            state = "disabled" if fixed else "normal"
            cb = tk.Checkbutton(
                left, variable=var, bg=BG2, fg=FG,
                selectcolor=BG3, activebackground=BG2,
                state=state,
            )
            cb.pack()
            body = tk.Frame(card, bg=BG2)
            body.pack(side="left", fill="x", expand=True, padx=8, pady=8)
            tk.Label(body, text=label, bg=BG2, fg=FG,
                     font=("Segoe UI" if IS_WINDOWS else "Sans", 11, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(body, text=desc, bg=BG2, fg=MUTED,
                     font=("Segoe UI" if IS_WINDOWS else "Sans", 9),
                     anchor="w", justify="left").pack(fill="x")

        core_var = tk.BooleanVar(value=True)
        _row("Core Application  (required)",
             "GUI, DICOM reader, sorting engine, detection, heuristics",
             core_var, fixed=True)

        _row("AI Body-Part Detection  (~220 MB CPU / ~2.5 GB GPU)",
             "PyTorch neural network for pixel-level image analysis",
             self._include_ai)

        # GPU sub-option
        gpu_row = tk.Frame(f, bg=BG)
        gpu_row.pack(fill="x", padx=72, pady=(0, 2))
        self._gpu_cb = tk.Checkbutton(
            gpu_row,
            text="Use NVIDIA GPU acceleration (CUDA 12.1)  ",
            variable=self._use_gpu,
            bg=BG, fg=MUTED, selectcolor=BG2,
            activebackground=BG,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 9),
        )
        self._gpu_cb.pack(side="left")
        self._cuda_badge = tk.Label(
            gpu_row, text="  Checking GPU…  ",
            bg=BG3, fg=MUTED,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 8),
        )
        self._cuda_badge.pack(side="left", padx=4)

        _row("NIfTI Conversion  (~30 MB)",
             "Convert DICOM series to NIfTI format for ML dataset mode",
             self._include_conv)
        return f

    def _page_install(self) -> tk.Frame:
        f = tk.Frame(self._container, bg=BG)
        self._lbl(f, "Installing…", size=14, weight="bold").pack(
            pady=(24, 4), anchor="w", padx=36)

        self._step_msg = tk.Label(
            f, text="Preparing…", bg=BG, fg=ACCENT,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
        )
        self._step_msg.pack(anchor="w", padx=36)

        # Progress bar (ttk for actual fill)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Inst.Horizontal.TProgressbar",
                        troughcolor=BG2, background=ACCENT,
                        lightcolor=ACCENT, darkcolor=ACCENT,
                        bordercolor=BG2, thickness=18)
        self._pbar = ttk.Progressbar(
            f, style="Inst.Horizontal.TProgressbar",
            length=640, mode="determinate",
        )
        self._pbar.pack(padx=36, pady=(8, 2))
        self._pct_lbl = tk.Label(f, text="0 %", bg=BG, fg=MUTED,
                                  font=("Segoe UI" if IS_WINDOWS else "Sans", 9))
        self._pct_lbl.pack(anchor="e", padx=36)

        # Log box
        log_frame = tk.Frame(f, bg=BG2)
        log_frame.pack(fill="both", expand=True, padx=36, pady=(6, 16))
        sb = tk.Scrollbar(log_frame, bg=BG2)
        sb.pack(side="right", fill="y")
        self._log_box = tk.Text(
            log_frame, bg=BG2, fg=MUTED,
            font=("Courier" if IS_WINDOWS else "Monospace", 8),
            relief="flat", wrap="word",
            yscrollcommand=sb.set, padx=8, pady=6,
        )
        sb.config(command=self._log_box.yview)
        self._log_box.pack(fill="both", expand=True)
        return f

    def _page_finish(self) -> tk.Frame:
        f = tk.Frame(self._container, bg=BG)
        tk.Frame(f, bg=BG, height=24).pack()
        self._finish_icon = tk.Label(f, text="✅", bg=BG, fg=OK,
                                     font=("Segoe UI Emoji", 52))
        self._finish_icon.pack(pady=(0, 8))
        self._finish_title = tk.Label(
            f, text="Installation Complete!",
            bg=BG, fg=FG,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 16, "bold"),
        )
        self._finish_title.pack()
        self._finish_sub = tk.Label(
            f, text="DICOM Organizer has been installed successfully.",
            bg=BG, fg=MUTED,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
        )
        self._finish_sub.pack(pady=(8, 24))
        tk.Checkbutton(
            f, text="Launch DICOM Organizer now",
            variable=self._launch_now,
            bg=BG, fg=FG, selectcolor=BG2,
            activebackground=BG, activeforeground=FG,
            font=("Segoe UI" if IS_WINDOWS else "Sans", 10),
        ).pack()
        return f

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show_page(self, idx: int):
        for p in self._pages:
            p.pack_forget()
        self._pages[idx].pack(fill="both", expand=True)
        self._page = idx

        total = len(self._pages)
        self._step_lbl.configure(text=f"Step {idx+1} of {total}")
        self._back_btn.configure(
            state="normal" if idx > 0 and idx != total - 2 else "disabled")
        self._update_next_state()

        if idx == total - 1:          # Finish page
            self._next_btn.configure(text="Finish  ✓", bg=OK)
        elif idx == total - 2:        # Install page
            self._next_btn.configure(text="Install", bg=OK)
        else:
            self._next_btn.configure(text="Next  →", bg=ACCENT)

    def _update_next_state(self, *_):
        if self._page == 1:
            state = "normal" if self._accept_var.get() else "disabled"
        else:
            state = "normal"
        self._next_btn.configure(state=state)

    def _next(self):
        total = len(self._pages)
        if self._page == total - 2:       # About to install
            if not self._python_exe:
                messagebox.showerror(
                    "Python Not Found",
                    "Python 3.9 or newer is required but could not be found.\n\n"
                    "Please install Python from https://python.org/downloads/\n"
                    "(tick 'Add Python to PATH' during install), then re-run setup.",
                    parent=self.root,
                )
                return
            self._show_page(self._page + 1)
            self._next_btn.configure(state="disabled")
            self._back_btn.configure(state="disabled")
            threading.Thread(target=self._run_install, daemon=True).start()
        elif self._page == total - 1:     # Finish
            self._finish_and_close()
        else:
            self._show_page(self._page + 1)

    def _back(self):
        if self._page > 0:
            self._show_page(self._page - 1)

    def _on_close(self):
        if self._page == len(self._pages) - 2:  # installing
            return  # don't allow close during install
        if messagebox.askyesno("Cancel Setup",
                                "Cancel the installation?",
                                parent=self.root):
            self.root.destroy()

    def _browse_dir(self):
        d = filedialog.askdirectory(parent=self.root,
                                     title="Choose installation folder")
        if d:
            self._install_dir.set(d)

    # ── Background checks ─────────────────────────────────────────────────────

    def _bg_checks(self):
        py = _find_python()
        self._python_exe = py
        cuda = _check_cuda()
        self._cuda_avail = cuda
        self.root.after(0, self._update_check_ui, py, cuda)

    def _update_check_ui(self, py: str | None, cuda: bool):
        if py:
            ver_out = subprocess.run(
                [py, "--version"], capture_output=True, text=True, timeout=5
            ).stdout.strip() or "Python found"
            self._python_status.configure(
                text=f"  ✓  {ver_out} found  ",
                bg=OK, fg=WHITE,
            )
        else:
            self._python_status.configure(
                text="  ✗  Python 3.9+ not found — install from python.org  ",
                bg=ERR, fg=WHITE,
            )
        if cuda:
            self._cuda_badge.configure(
                text="  ✓  NVIDIA GPU detected — GPU recommended  ",
                bg=OK, fg=WHITE,
            )
            self._use_gpu.set(True)
        else:
            self._cuda_badge.configure(
                text="  ✗  No NVIDIA GPU — will use CPU  ",
                bg=BG3, fg=MUTED,
            )
            self._gpu_cb.configure(state="disabled")

    # ── Install worker ────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.update_idletasks()

    def _set_progress(self, pct: int, msg: str = ""):
        self._pbar["value"] = pct
        self._pct_lbl.configure(text=f"{pct} %")
        if msg:
            self._step_msg.configure(text=msg)
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def _run_install(self):
        try:
            self._do_install()
        except Exception as exc:
            self._log(f"\n❌  Installation failed: {exc}")
            self._step_msg.configure(text=f"❌  Error: {exc}")
            self._next_btn.configure(state="normal", text="Retry", bg=WARN)
            self._back_btn.configure(state="disabled")

    def _pip_install(self, pip: str, pkg: str,
                     extra_args: list[str] | None = None) -> bool:
        cmd = [pip, "install", "--quiet", pkg] + (extra_args or [])
        self._log(f"    pip install {pkg}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and r.stderr:
            self._log(f"    ⚠  {r.stderr.strip()[:160]}")
        return r.returncode == 0

    def _do_install(self):
        python   = self._python_exe
        inst_dir = Path(self._install_dir.get())
        venv_dir = inst_dir / "venv"
        app_dir  = inst_dir / "app"

        # ── 1. Create install directory ──────────────────────────────────────
        self._set_progress(2, "Creating installation directory…")
        inst_dir.mkdir(parents=True, exist_ok=True)
        self._log(f"Install directory: {inst_dir}")
        self._installed_dir = inst_dir

        # ── 2. Copy application source ───────────────────────────────────────
        self._set_progress(6, "Copying application files…")
        src = _bundle_dir()
        app_dir.mkdir(parents=True, exist_ok=True)
        for item in ("gui", "core", "utils", "models"):
            s = src / item
            t = app_dir / item
            if s.exists():
                if t.exists():
                    shutil.rmtree(str(t))
                shutil.copytree(str(s), str(t))
                self._log(f"  Copied {item}/")
        for fname in ("main.py", "download_model.py"):
            s = src / fname
            if s.exists():
                shutil.copy2(str(s), str(app_dir / fname))
                self._log(f"  Copied {fname}")
        (inst_dir / "version.txt").write_text(APP_VERSION, encoding="utf-8")

        # ── 3. Create virtual environment ─────────────────────────────────────
        self._set_progress(12, "Creating virtual environment…")
        self._log("Creating virtual environment…")
        r = subprocess.run(
            [python, "-m", "venv", str(venv_dir)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"venv creation failed:\n{r.stderr[:300]}")
        self._log("  Virtual environment created.")

        # Resolve pip / python executables inside venv
        if IS_WINDOWS:
            pip_exe     = str(venv_dir / "Scripts" / "pip.exe")
            pythonw_exe = str(venv_dir / "Scripts" / "pythonw.exe")
            python_exe  = str(venv_dir / "Scripts" / "python.exe")
        else:
            pip_exe     = str(venv_dir / "bin" / "pip")
            pythonw_exe = str(venv_dir / "bin" / "python")
            python_exe  = str(venv_dir / "bin" / "python")

        # ── 4. Upgrade pip ────────────────────────────────────────────────────
        self._set_progress(15, "Upgrading pip…")
        subprocess.run([pip_exe, "install", "--quiet", "--upgrade", "pip"],
                       capture_output=True)

        # ── 5. Install core packages ──────────────────────────────────────────
        n_pkgs = (len(CORE_PACKAGES)
                  + (len(AI_CPU_PKGS) if self._include_ai.get() else 0)
                  + (len(CONV_PKGS)   if self._include_conv.get() else 0))
        start, end = 18, 85
        per = (end - start) / max(n_pkgs, 1)
        current = float(start)

        self._log("\n── Core packages ──")
        for pkg in CORE_PACKAGES:
            self._set_progress(int(current), f"Installing {pkg.split('>=')[0]}…")
            self._pip_install(pip_exe, pkg)
            current += per

        # ── 6. AI packages ────────────────────────────────────────────────────
        if self._include_ai.get():
            use_gpu = self._use_gpu.get() and self._cuda_avail
            index   = TORCH_GPU_URL if use_gpu else TORCH_CPU_URL
            label   = "GPU" if use_gpu else "CPU"
            self._log(f"\n── AI packages ({label}) ──")
            for pkg in AI_CPU_PKGS:
                self._set_progress(int(current),
                                   f"Installing PyTorch ({label}) — this may take a few minutes…")
                self._pip_install(pip_exe, pkg, ["--index-url", index])
                current += per

        # ── 7. NIfTI conversion ───────────────────────────────────────────────
        if self._include_conv.get():
            self._log("\n── NIfTI conversion packages ──")
            for pkg in CONV_PKGS:
                self._set_progress(int(current), f"Installing {pkg}…")
                self._pip_install(pip_exe, pkg)
                current += per

        # ── 8. Write launcher ─────────────────────────────────────────────────
        self._set_progress(88, "Creating launcher…")
        main_py = str(app_dir / "main.py")
        self._installed_venv_python = pythonw_exe
        self._installed_main_py     = main_py

        if IS_WINDOWS:
            launcher = inst_dir / "DICOM_Organizer.bat"
            launcher.write_text(
                f'@echo off\n'
                f'start "" "{pythonw_exe}" "{main_py}"\n',
                encoding="utf-8",
            )
            self._log(f"  Launcher: {launcher}")
        else:
            launcher = inst_dir / "DICOM_Organizer.sh"
            launcher.write_text(
                "#!/bin/bash\n"
                f'"{python_exe}" "{main_py}" &\n',
                encoding="utf-8",
            )
            launcher.chmod(0o755)
            self._log(f"  Launcher: {launcher}")

        # ── 9. Desktop shortcut ───────────────────────────────────────────────
        if self._desktop_shortcut.get():
            self._set_progress(91, "Creating desktop shortcut…")
            if IS_WINDOWS:
                desktop = Path.home() / "Desktop"
                lnk = str(desktop / "DICOM Organizer.lnk")
                ok = _create_shortcut_windows(
                    target=pythonw_exe, args=f'"{main_py}"',
                    working_dir=str(app_dir),
                    shortcut_path=lnk,
                    description="DICOM Organizer — Smart medical image sorter",
                )
                self._log(f"  Desktop shortcut: {'created' if ok else 'failed'}")
            else:
                desktop = Path.home() / "Desktop"
                desktop.mkdir(exist_ok=True)
                ok = _create_shortcut_linux(
                    exec_cmd=f'"{python_exe}" "{main_py}"',
                    name="DICOM Organizer",
                    desktop_path=str(desktop / "DICOM_Organizer.desktop"),
                )
                self._log(f"  Desktop shortcut: {'created' if ok else 'failed'}")

        # ── 10. Start Menu / app menu ─────────────────────────────────────────
        if self._menu_shortcut.get():
            self._set_progress(94, "Adding to app menu…")
            if IS_WINDOWS:
                sm = (Path(os.environ.get("APPDATA", ""))
                      / "Microsoft" / "Windows" / "Start Menu" / "Programs")
                lnk = str(sm / "DICOM Organizer.lnk")
                _create_shortcut_windows(
                    target=pythonw_exe, args=f'"{main_py}"',
                    working_dir=str(app_dir),
                    shortcut_path=lnk,
                    description="DICOM Organizer",
                )
                self._log("  Start Menu entry created.")
            else:
                apps_dir = Path.home() / ".local" / "share" / "applications"
                apps_dir.mkdir(parents=True, exist_ok=True)
                _create_shortcut_linux(
                    exec_cmd=f'"{python_exe}" "{main_py}"',
                    name="DICOM Organizer",
                    desktop_path=str(apps_dir / "dicom-organizer.desktop"),
                )
                self._log("  Application menu entry created.")

        # ── 11. Uninstaller ───────────────────────────────────────────────────
        self._set_progress(97, "Writing uninstaller…")
        if IS_WINDOWS:
            uninst = inst_dir / "Uninstall.bat"
            uninst.write_text(
                "@echo off\n"
                "echo Uninstalling DICOM Organizer...\n"
                f'rmdir /s /q "{inst_dir}"\n'
                f'del /f "%USERPROFILE%\\Desktop\\DICOM Organizer.lnk" 2>nul\n'
                "echo Uninstall complete.\n"
                "pause\n",
                encoding="utf-8",
            )
        else:
            uninst = inst_dir / "uninstall.sh"
            uninst.write_text(
                "#!/bin/bash\n"
                "echo 'Uninstalling DICOM Organizer...'\n"
                f'rm -rf "{inst_dir}"\n'
                f'rm -f "$HOME/Desktop/DICOM_Organizer.desktop"\n'
                f'rm -f "$HOME/.local/share/applications/dicom-organizer.desktop"\n'
                "echo 'Done.'\n",
                encoding="utf-8",
            )
            uninst.chmod(0o755)
        self._log(f"  Uninstaller: {uninst}")

        # ── Done ─────────────────────────────────────────────────────────────
        self._set_progress(100, "✅  Installation complete!")
        self._log(f"\n✅  DICOM Organizer installed successfully!")
        self._log(f"   Location: {inst_dir}")
        self.root.after(600, lambda: self._show_page(len(self._pages) - 1))
        self._next_btn.configure(state="normal")

    # ── Finish ────────────────────────────────────────────────────────────────

    def _finish_and_close(self):
        if self._launch_now.get() and self._installed_venv_python:
            try:
                kwargs = {}
                if IS_WINDOWS:
                    kwargs["creationflags"] = (
                        subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                    )
                subprocess.Popen(
                    [self._installed_venv_python, self._installed_main_py],
                    cwd=str(self._installed_dir / "app"),
                    **kwargs,
                )
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    InstallerApp().run()
