"""
DICOM Organizer — Self-installing bootstrapper.
Uses ONLY Python standard library — safe to run before any packages are installed.
Double-click  DICOM_Organizer.bat  to start everything automatically.
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox

# ── Immediately hide the console window on Windows ────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes as _ct
        _ct.windll.user32.ShowWindow(_ct.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent.resolve()
MARKER_FILE = ROOT_DIR / ".deps_installed"
APP_NAME    = "DICOM Organizer"
APP_VERSION = "1.0"

# ── Colours ───────────────────────────────────────────────────────────────────
BG       = "#1C2333"
BG_CARD  = "#242D3E"
BG_LOG   = "#161E2D"
FG       = "#E8EAF0"
FG_MUT   = "#8892A4"
ACCENT   = "#4A90D9"
OK_C     = "#2ECC71"
WARN_C   = "#F39C12"
ERR_C    = "#E74C3C"
BORDER   = "#2E3A50"

WIN_W, WIN_H = 600, 680

# ── Package catalogue ─────────────────────────────────────────────────────────
REQUIRED = [
    ("customtkinter", "customtkinter==5.2.2",  "Modern GUI framework"),
    ("pydicom",       "pydicom==2.4.4",         "DICOM file reading"),
    ("pandas",        "pandas==2.1.4",          "Data processing"),
    ("numpy",         "numpy==1.26.2",          "Numerical computing"),
    ("PIL",           "Pillow==10.1.0",         "Image handling"),
    ("matplotlib",    "matplotlib==3.8.2",      "Charts and graphs"),
    ("sklearn",       "scikit-learn==1.3.2",    "ML split utilities"),
    ("scipy",         "scipy==1.11.4",          "Scientific computing"),
    ("tqdm",          "tqdm==4.66.1",           "Progress tracking"),
    ("requests",      "requests==2.31.0",       "File downloads"),
    ("packaging",     "packaging==23.2",        "Version management"),
    ("tkinterdnd2",   "tkinterdnd2",            "Drag-and-drop support"),
]

AI_CPU = [
    ("torch",       "torch",       "PyTorch CPU  (~220 MB)"),
    ("torchvision", "torchvision", "TorchVision  CPU"),
]
AI_GPU = [
    ("torch",       "torch",       "PyTorch CUDA GPU  (~2.5 GB)"),
    ("torchvision", "torchvision", "TorchVision  CUDA GPU"),
]
CONV = [
    ("SimpleITK",   "SimpleITK==2.3.1",   "NIfTI conversion engine"),
    ("dicom2nifti", "dicom2nifti==2.4.8", "DICOM-to-NIfTI converter"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _installed(import_name: str) -> bool:
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def _has_cuda() -> bool:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


# ── Main installer class ──────────────────────────────────────────────────────
class InstallerApp:
    def __init__(self):
        self.root = Tk()
        self.root.title(f"{APP_NAME}  —  Setup")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{WIN_W}x{WIN_H}+{(sw-WIN_W)//2}+{(sh-WIN_H)//2}")

        self._install_ai    = BooleanVar(value=False)
        self._use_gpu       = BooleanVar(value=False)
        self._install_nifti = BooleanVar(value=False)
        self._installing    = False
        self._cuda_avail    = False
        self._prog_val      = 0.0
        self._step_info: dict[str, tuple] = {}

        self._build()
        self.root.after(200, lambda: threading.Thread(
            target=self._startup_check, daemon=True).start())

    # ── UI construction ───────────────────────────────────────────────────────
    def _build(self):
        # Accent top-bar
        Frame(self.root, bg=ACCENT, height=4).pack(fill=X)

        # Header
        hdr = Frame(self.root, bg=BG, pady=18)
        hdr.pack(fill=X)
        Label(hdr, text="🏥", bg=BG, fg=FG,
              font=("Segoe UI Emoji", 36)).pack()
        Label(hdr, text=APP_NAME, bg=BG, fg=FG,
              font=("Segoe UI", 20, "bold")).pack(pady=(4, 1))
        Label(hdr, text=f"v{APP_VERSION}  ·  Smart Medical Image Sorting",
              bg=BG, fg=FG_MUT, font=("Segoe UI", 10)).pack()

        Frame(self.root, bg=BORDER, height=1).pack(fill=X)

        # ── Steps panel ───────────────────────────────────────────────────────
        sp = Frame(self.root, bg=BG_CARD, padx=18, pady=12)
        sp.pack(fill=X, padx=16, pady=(12, 0))
        Label(sp, text="Installation steps", bg=BG_CARD, fg=FG_MUT,
              font=("Segoe UI", 9, "bold")).pack(anchor=W, pady=(0, 6))

        for key, num, label in [
            ("check",   "1", "System check"),
            ("install", "2", "Install packages"),
            ("model",   "3", "AI model download"),
            ("launch",  "4", "Launch application"),
        ]:
            row = Frame(sp, bg=BG_CARD)
            row.pack(fill=X, pady=2)

            badge = Label(row, text=f" {num} ", bg=BG_CARD, fg=FG_MUT,
                          font=("Segoe UI", 9, "bold"),
                          relief="solid", bd=1, padx=4, pady=1)
            badge.pack(side=LEFT, padx=(0, 10))

            lbl = Label(row, text=label, bg=BG_CARD, fg=FG_MUT,
                        font=("Segoe UI", 10), anchor=W)
            lbl.pack(side=LEFT, fill=X, expand=True)

            status = Label(row, text="Waiting", bg=BG_CARD, fg=FG_MUT,
                           font=("Segoe UI", 9, "italic"), width=16, anchor=E)
            status.pack(side=RIGHT)

            self._step_info[key] = (badge, lbl, status)

        # ── Options panel ─────────────────────────────────────────────────────
        op = Frame(self.root, bg=BG_CARD, padx=18, pady=12)
        op.pack(fill=X, padx=16, pady=(8, 0))
        Label(op, text="Optional features  (select before installing)",
              bg=BG_CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 6))

        Checkbutton(
            op,
            text="  AI body part detection  —  PyTorch CPU  (~220 MB, recommended)",
            variable=self._install_ai, command=self._ai_toggled,
            bg=BG_CARD, fg=FG, selectcolor="#1a2235",
            activebackground=BG_CARD, activeforeground=FG,
            font=("Segoe UI", 10), cursor="hand2",
        ).pack(anchor=W)

        self._gpu_row = Frame(op, bg=BG_CARD)
        self._gpu_cb  = Checkbutton(
            self._gpu_row,
            text="     Use NVIDIA GPU / CUDA  (~2.5 GB — detected automatically)",
            variable=self._use_gpu,
            bg=BG_CARD, fg=FG_MUT, selectcolor="#1a2235",
            activebackground=BG_CARD, activeforeground=FG,
            font=("Segoe UI", 9), cursor="hand2", state=DISABLED,
        )
        self._gpu_cb.pack(anchor=W)

        Checkbutton(
            op,
            text="  NIfTI conversion  —  SimpleITK + dicom2nifti  (~150 MB, dataset mode)",
            variable=self._install_nifti,
            bg=BG_CARD, fg=FG, selectcolor="#1a2235",
            activebackground=BG_CARD, activeforeground=FG,
            font=("Segoe UI", 10), cursor="hand2",
        ).pack(anchor=W, pady=(4, 0))

        # ── Progress area ─────────────────────────────────────────────────────
        pg = Frame(self.root, bg=BG, padx=16, pady=(10, 0))
        pg.pack(fill=X)

        self._status_var = StringVar(value="Ready — choose options and click Install")
        Label(pg, textvariable=self._status_var, bg=BG, fg=FG,
              font=("Segoe UI", 10), anchor=W).pack(fill=X)

        self._pb_canvas = Canvas(pg, bg=BG_CARD, height=20,
                                  highlightthickness=0)
        self._pb_canvas.pack(fill=X, pady=(4, 0))
        self._pb_canvas.bind("<Configure>", lambda _e: self._draw_bar())

        # ── Log ───────────────────────────────────────────────────────────────
        lg = Frame(self.root, bg=BG, padx=16, pady=(8, 0))
        lg.pack(fill=BOTH, expand=True)
        Label(lg, text="Installation log", bg=BG, fg=FG_MUT,
              font=("Segoe UI", 9, "bold")).pack(anchor=W)

        box = Frame(lg, bg=BG_LOG, relief=SOLID, bd=1)
        box.pack(fill=BOTH, expand=True, pady=(4, 0))

        self._log = Text(box, bg=BG_LOG, fg=FG, font=("Consolas", 9),
                         state=DISABLED, bd=0, padx=8, pady=6, wrap=WORD)
        sb = Scrollbar(box, command=self._log.yview, bg=BG_CARD,
                       troughcolor=BG_LOG, relief=FLAT)
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        self._log.pack(side=LEFT, fill=BOTH, expand=True)

        self._log.tag_configure("ok",   foreground=OK_C)
        self._log.tag_configure("err",  foreground=ERR_C)
        self._log.tag_configure("warn", foreground=WARN_C)
        self._log.tag_configure("act",  foreground=ACCENT)
        self._log.tag_configure("dim",  foreground=FG_MUT)

        # ── Buttons ───────────────────────────────────────────────────────────
        ba = Frame(self.root, bg=BG, pady=14)
        ba.pack(fill=X)

        self._btn = Button(
            ba,
            text="   Install & Launch   ",
            bg=ACCENT, fg="white",
            activebackground="#357ABD", activeforeground="white",
            font=("Segoe UI", 12, "bold"),
            bd=0, relief=FLAT, cursor="hand2",
            padx=28, pady=10,
            command=self._btn_click,
        )
        self._btn.pack()

        self._skip = Label(ba,
            text="Already installed?  Click here to launch directly  →",
            bg=BG, fg=FG_MUT, font=("Segoe UI", 9), cursor="hand2")
        self._skip.pack(pady=(6, 0))
        self._skip.bind("<Button-1>", lambda _e: self._launch())
        self._skip.bind("<Enter>",    lambda _e: self._skip.configure(fg=ACCENT))
        self._skip.bind("<Leave>",    lambda _e: self._skip.configure(fg=FG_MUT))

    # ── Progress bar ─────────────────────────────────────────────────────────
    def _draw_bar(self):
        c  = self._pb_canvas
        w  = c.winfo_width()
        h  = c.winfo_height()
        if w < 2:
            return
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill=BG_CARD, outline="")
        fw = int(w * self._prog_val)
        if fw:
            # Segmented look
            for x in range(0, fw, 6):
                c.create_rectangle(x, 0, min(x+5, fw), h, fill=ACCENT, outline="")
        pct = f"{int(self._prog_val*100)} %"
        c.create_text(w//2, h//2, text=pct, fill=FG, font=("Segoe UI", 8, "bold"))

    def _set_prog(self, v: float):
        self._prog_val = max(0.0, min(1.0, v))
        self.root.after(0, self._draw_bar)

    # ── Step helpers ──────────────────────────────────────────────────────────
    def _step(self, key: str, text: str, color: str, done=False):
        def _do():
            badge, lbl, status = self._step_info[key]
            if done:
                badge.configure(text=" ✓ ", fg=OK_C, relief="flat", bd=0)
            else:
                num = {"check":"1","install":"2","model":"3","launch":"4"}[key]
                badge.configure(text=f" {num} ", fg=color, relief="solid", bd=1)
            lbl.configure(fg=FG if color != FG_MUT else FG_MUT)
            status.configure(text=text, fg=color)
        self.root.after(0, _do)

    # ── Log helpers ───────────────────────────────────────────────────────────
    def _emit(self, msg: str, tag: str = ""):
        def _do():
            self._log.configure(state=NORMAL)
            ts = time.strftime("%H:%M:%S")
            idx = self._log.index("end-1c")
            self._log.insert(END, f"[{ts}]  {msg}\n")
            if tag:
                self._log.tag_add(tag, idx, "end-1c")
            self._log.configure(state=DISABLED)
            self._log.see(END)
        self.root.after(0, _do)

    def _setstatus(self, s: str):
        self.root.after(0, lambda: self._status_var.set(s))

    # ── Startup check ─────────────────────────────────────────────────────────
    def _startup_check(self):
        self._step("check", "Checking…", ACCENT)
        self._emit(f"Python {sys.version.split()[0]}  ·  "
                   f"{platform.system()} {platform.machine()}", "dim")

        # CUDA probe
        self._cuda_avail = _has_cuda()
        if self._cuda_avail:
            self._emit("NVIDIA GPU detected — CUDA option enabled.", "ok")
            self.root.after(0, self._enable_gpu_option)

        # Dependency check
        missing = [pkg for imp, pkg, _ in REQUIRED if not _installed(imp)]

        if MARKER_FILE.exists() and not missing:
            self._emit("All required packages are already installed.", "ok")
            self._step("check",   "Complete", OK_C, done=True)
            self._step("install", "Complete", OK_C, done=True)
            self._set_prog(0.75)
            self.root.after(0, self._set_launch_ready)
        else:
            self._step("check", "Complete", OK_C, done=True)
            if missing:
                self._emit(f"{len(missing)} package(s) need installing:", "warn")
                for p in missing:
                    self._emit(f"   • {p}", "dim")
            else:
                self._emit("All packages present (no marker file — will verify).", "dim")

    def _enable_gpu_option(self):
        self._gpu_cb.configure(state=NORMAL, fg=FG)
        self._gpu_row.pack(anchor=W)

    def _ai_toggled(self):
        if self._install_ai.get() and self._cuda_avail:
            self._gpu_row.pack(anchor=W)
        elif not self._install_ai.get():
            self._gpu_row.pack_forget()

    def _set_launch_ready(self):
        self._btn.configure(
            text="   🚀  Launch DICOM Organizer   ",
            bg=OK_C, activebackground="#27AE60",
        )
        self._setstatus("Ready to launch!")

    # ── Button handler ────────────────────────────────────────────────────────
    def _btn_click(self):
        if MARKER_FILE.exists():
            self._launch()
        else:
            self._begin_install()

    # ── Installation ──────────────────────────────────────────────────────────
    def _begin_install(self):
        if self._installing:
            return
        self._installing = True
        self._btn.configure(state=DISABLED, text="  ⏳  Installing, please wait…  ")
        self._step("install", "Installing…", ACCENT)
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        pkgs = list(REQUIRED)
        if self._install_ai.get():
            pkgs += AI_GPU if (self._use_gpu.get() and self._cuda_avail) else AI_CPU
        if self._install_nifti.get():
            pkgs += CONV

        total  = len(pkgs)
        errors = []

        # Upgrade pip first
        self._setstatus("Upgrading pip…")
        self._emit("Upgrading pip…", "dim")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip",
             "--quiet", "--disable-pip-version-check"],
            capture_output=True,
        )

        for i, (imp, spec, desc) in enumerate(pkgs):
            base = spec.split("==")[0]
            if _installed(imp):
                self._emit(f"✓  {base:<22} already installed", "ok")
                self._set_prog((i + 1) / total * 0.92)
                continue

            self._setstatus(f"Installing {base}…  ({i+1}/{total})")
            self._emit(f"→  {spec:<30}  {desc}", "act")
            self._set_prog(i / total * 0.92)

            # PyTorch needs special index
            extra: list[str] = []
            if imp == "torch":
                if self._use_gpu.get() and self._cuda_avail:
                    extra = ["--index-url",
                             "https://download.pytorch.org/whl/cu121"]
                else:
                    extra = ["--index-url",
                             "https://download.pytorch.org/whl/cpu"]

            ok = self._pip(spec, extra)
            self._set_prog((i + 1) / total * 0.92)

            if ok:
                self._emit(f"✓  {base} installed", "ok")
            else:
                errors.append(spec)
                self._emit(f"✗  Failed: {spec}", "err")

        self._set_prog(0.95)

        # Write marker
        MARKER_FILE.write_text(json.dumps({
            "packages":    [p[1] for p in pkgs],
            "timestamp":   time.strftime("%Y-%m-%d %H:%M:%S"),
            "ai":          self._install_ai.get(),
            "nifti":       self._install_nifti.get(),
        }, indent=2))

        self.root.after(0, lambda: self._install_done(errors))

    def _pip(self, spec: str, extra: list[str] | None = None) -> bool:
        cmd = [sys.executable, "-m", "pip", "install", spec,
               "--quiet", "--disable-pip-version-check"]
        if extra:
            cmd += extra
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0 and r.stderr:
                self._emit(f"   {r.stderr.strip()[:140]}", "err")
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            self._emit(f"   Timed out installing {spec}", "err")
            return False
        except Exception as exc:
            self._emit(f"   Error: {exc}", "err")
            return False

    def _install_done(self, errors: list):
        self._installing = False
        self._set_prog(1.0)

        if errors:
            self._step("install", f"{len(errors)} error(s)", WARN_C)
            self._emit(f"⚠  {len(errors)} package(s) failed — app may still work.", "warn")
            self._btn.configure(
                state=NORMAL,
                text="   ▶  Continue & Launch   ",
                bg=WARN_C, activebackground="#D68910",
            )
            self._setstatus(f"Done with {len(errors)} error(s). Click to launch.")
        else:
            self._step("install", "Complete", OK_C, done=True)
            self._emit("✓  All packages installed successfully!", "ok")
            self._btn.configure(
                state=NORMAL,
                text="   🚀  Launch DICOM Organizer   ",
                bg=OK_C, activebackground="#27AE60",
            )
            self._setstatus("Installation complete — ready to launch!")

    # ── Launch ────────────────────────────────────────────────────────────────
    def _launch(self):
        self._step("launch", "Launching…", ACCENT)
        self._setstatus("Starting DICOM Organizer…")
        self._btn.configure(state=DISABLED)
        self.root.after(400, self._do_launch)

    def _do_launch(self):
        main_py = ROOT_DIR / "main.py"
        if not main_py.exists():
            messagebox.showerror(
                "File Not Found",
                f"Cannot find main.py in:\n{ROOT_DIR}\n\n"
                "Make sure all DICOM Organizer files are in the same folder."
            )
            self._btn.configure(state=NORMAL)
            return

        try:
            if sys.platform == "win32":
                pythonw = Path(sys.executable).parent / "pythonw.exe"
                exe     = str(pythonw) if pythonw.exists() else sys.executable
                subprocess.Popen(
                    [exe, str(main_py)],
                    cwd=str(ROOT_DIR),
                    creationflags=subprocess.DETACHED_PROCESS
                                | subprocess.CREATE_NO_WINDOW,
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(main_py)],
                    cwd=str(ROOT_DIR),
                )

            self._step("launch", "Launched ✓", OK_C, done=True)
            self._emit("✓  DICOM Organizer is starting…", "ok")
            self._setstatus("Launched! This window will close shortly.")
            self.root.after(1800, self.root.destroy)

        except Exception as exc:
            messagebox.showerror("Launch Error",
                                 f"Could not start the application:\n{exc}")
            self._btn.configure(state=NORMAL)

    # ── Close handler ─────────────────────────────────────────────────────────
    def _on_close(self):
        if self._installing:
            if messagebox.askyesno(
                "Installation in Progress",
                "Installation is still running.\nAre you sure you want to quit?",
            ):
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    InstallerApp().run()
