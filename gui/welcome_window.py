"""
Window 1 — Welcome / mode selection screen  +  first-run tutorial overlay.
"""
from __future__ import annotations

import customtkinter as ctk
from gui.theme import (
    apply_theme, make_title, make_subtitle, make_primary_button,
    make_secondary_button, make_card, ACCENT, MUTED, SUCCESS,
)


# ── Tutorial data ─────────────────────────────────────────────────────────────
_TUTORIAL_SLIDES = [
    (
        "👋  Welcome to DICOM Organizer!",
        (
            "This app automatically sorts your MRI and CT DICOM files\n"
            "into neat, labelled folders — no command line needed.\n\n"
            "It works even when DICOM metadata is missing, wrong,\n"
            "or inconsistent."
        ),
    ),
    (
        "🎯  3-Layer Body Part Detection",
        (
            "Layer 1 — Metadata:  reads DICOM tags (instant, most reliable)\n\n"
            "Layer 2 — AI Vision:  analyses the actual image pixels\n"
            "using a neural network when tags are missing\n\n"
            "Layer 3 — Heuristics:  uses geometry, pixel statistics,\n"
            "and modality rules as a final fallback\n\n"
            "Every file gets a confidence score  (0–100 %)."
        ),
    ),
    (
        "📁  Two Sorting Modes",
        (
            "Just Sort My Files\n"
            "Organises files into  MRI/Brain/ ,  CT/Chest/  etc.\n"
            "Simple and fast.\n\n"
            "Build ML Dataset\n"
            "Sorts + anonymises + converts to NIfTI + generates\n"
            "train / val / test splits and a full manifest CSV.\n"
            "For researchers and AI developers."
        ),
    ),
    (
        "✅  Ready to Start!",
        (
            "Tips for best results:\n\n"
            "• Keep 'AI detection' ON for the best accuracy\n"
            "• Use Copy (not Move) to keep your originals safe\n"
            "• Files with low confidence go to  _Review_Needed/\n"
            "  — open the Review Tool to fix them manually\n\n"
            "Click  Finish  to choose your sorting mode."
        ),
    ),
]


class _TutorialOverlay(ctk.CTkToplevel):
    """Modal carousel tutorial shown on first run."""

    def __init__(self, parent: ctk.CTk):
        super().__init__(parent)
        self.title("Welcome — Quick Start Guide")
        self.geometry("540x400")
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()

        self._idx = 0
        self._build()
        self._show_slide(0)

        # Center over parent
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - 540) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.geometry(f"540x400+{px}+{py}")

    def _build(self):
        # Dot indicators at top
        dot_row = ctk.CTkFrame(self, fg_color="transparent")
        dot_row.pack(pady=(16, 0))
        self._dots: list[ctk.CTkLabel] = []
        for _ in range(len(_TUTORIAL_SLIDES)):
            d = ctk.CTkLabel(dot_row, text="●", font=ctk.CTkFont(size=10),
                             text_color=MUTED)
            d.pack(side="left", padx=4)
            self._dots.append(d)

        # Title
        self._title_lbl = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=17, weight="bold"),
            wraplength=480,
        )
        self._title_lbl.pack(pady=(18, 8), padx=30)

        # Body text
        self._body_lbl = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=13),
            text_color=MUTED, justify="left", wraplength=480,
        )
        self._body_lbl.pack(fill="both", expand=True, padx=30)

        # Navigation
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=30, pady=(0, 20))

        self._back_btn = make_secondary_button(nav, "← Back",
                                               command=self._prev, width=100)
        self._back_btn.pack(side="left")

        self._next_btn = make_primary_button(nav, "Next →",
                                             command=self._next, width=130)
        self._next_btn.pack(side="right")

        # Slide counter
        self._counter = ctk.CTkLabel(nav, text="", text_color=MUTED,
                                     font=ctk.CTkFont(size=11))
        self._counter.pack(side="left", padx=(12, 0))

    def _show_slide(self, idx: int):
        self._idx = idx
        title, body = _TUTORIAL_SLIDES[idx]
        self._title_lbl.configure(text=title)
        self._body_lbl.configure(text=body)
        self._counter.configure(text=f"{idx+1} / {len(_TUTORIAL_SLIDES)}")
        self._back_btn.configure(state="normal" if idx > 0 else "disabled")

        for i, dot in enumerate(self._dots):
            dot.configure(text_color=ACCENT if i == idx else MUTED)

        if idx == len(_TUTORIAL_SLIDES) - 1:
            self._next_btn.configure(text="Finish ✓", fg_color=SUCCESS)
        else:
            self._next_btn.configure(text="Next →", fg_color=ACCENT)

    def _next(self):
        if self._idx < len(_TUTORIAL_SLIDES) - 1:
            self._show_slide(self._idx + 1)
        else:
            self.destroy()

    def _prev(self):
        if self._idx > 0:
            self._show_slide(self._idx - 1)


# ── Welcome window ────────────────────────────────────────────────────────────

class WelcomeWindow(ctk.CTk):
    def __init__(self, config, on_mode_selected, show_tutorial: bool = False):
        super().__init__()
        self.config_obj       = config
        self.on_mode_selected = on_mode_selected
        self._show_tutorial   = show_tutorial

        apply_theme(config.theme)
        self.title("DICOM Organizer")
        self.geometry("820x580")
        self.minsize(700, 500)
        self.resizable(True, True)

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"820x580+{(sw-820)//2}+{(sh-580)//2}")

        self._build_ui()

        if show_tutorial:
            self.after(400, self._open_tutorial)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(40, 20))
        make_title(header, "🏥  DICOM Organizer").pack(anchor="center")
        make_subtitle(
            header, "Smart medical image sorting with automatic body part detection"
        ).pack(anchor="center", pady=(6, 0))

        # Mode cards
        cards = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        cards.pack(fill="both", expand=True, padx=40, pady=10)
        cards.columnconfigure((0, 1), weight=1, uniform="col")

        simple_card = make_card(cards)
        simple_card.grid(row=0, column=0, padx=(0, 12), pady=10, sticky="nsew")
        self._mode_card(
            simple_card, "📁", "Just Sort My Files",
            "Automatically organise your DICOM files into\n"
            "neat folders by modality and body part.\n\n"
            "Perfect for quick, everyday sorting.",
            "Simple Mode", ACCENT, lambda: self._select("simple"),
        )

        dataset_card = make_card(cards)
        dataset_card.grid(row=0, column=1, padx=(12, 0), pady=10, sticky="nsew")
        self._mode_card(
            dataset_card, "🤖", "Build ML Dataset",
            "Sort + anonymise + convert to NIfTI +\n"
            "generate train/val/test splits and manifests.\n\n"
            "For researchers and AI developers.",
            "Advanced Mode", SUCCESS, lambda: self._select("dataset"),
        )

        # Bottom bar
        bottom = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        bottom.pack(fill="x", padx=40, pady=(0, 24))

        theme_var = ctk.StringVar(value=self.config_obj.theme)
        ctk.CTkSwitch(
            bottom, text="Dark mode",
            variable=theme_var, onvalue="dark", offvalue="light",
            command=self._toggle_theme,
        ).pack(side="left")

        make_secondary_button(
            bottom, "📖  Tutorial", command=self._open_tutorial, width=110
        ).pack(side="right", padx=(8, 0))
        make_secondary_button(
            bottom, "❓  Help", command=self._show_help, width=90
        ).pack(side="right", padx=(8, 0))
        make_secondary_button(
            bottom, "ℹ️  About", command=self._show_about, width=90
        ).pack(side="right")

    def _mode_card(self, card, icon, title, desc, badge, badge_color, cmd):
        card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=48)).pack(pady=(0, 8))
        ctk.CTkLabel(
            inner, text=f"  {badge}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=badge_color, corner_radius=8, text_color="white",
        ).pack(pady=(0, 10))
        ctk.CTkLabel(inner, text=title,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=desc, font=ctk.CTkFont(size=12),
                     text_color=MUTED, justify="center").pack(pady=(0, 20))
        make_primary_button(
            inner, f"Choose {title.split()[0]} →", command=cmd, width=200
        ).pack()

    # ── Actions ───────────────────────────────────────────────────────────────
    def _select(self, mode: str):
        self.config_obj.mode = mode
        self.destroy()
        self.on_mode_selected(mode)

    def _toggle_theme(self):
        from utils.config import save_settings
        new = "light" if self.config_obj.theme == "dark" else "dark"
        self.config_obj.theme = new
        apply_theme(new)
        save_settings(self.config_obj)

    def _open_tutorial(self):
        _TutorialOverlay(self)

    def _show_help(self):
        w = ctk.CTkToplevel(self)
        w.title("Help")
        w.geometry("500x420")
        w.grab_set()
        ctk.CTkLabel(
            w,
            text=(
                "DICOM Organizer — Help\n\n"
                "HOW IT WORKS\n"
                "1. Choose a source folder with your DICOM files\n"
                "2. Choose a destination folder for sorted output\n"
                "3. The app detects body parts using 3 layers:\n"
                "   • Layer 1: DICOM metadata tags  (fastest)\n"
                "   • Layer 2: AI image analysis    (when tags missing)\n"
                "   • Layer 3: Anatomical heuristics (fallback)\n\n"
                "CONFIDENCE SCORES\n"
                "  85–100 %  →  detected from reliable metadata\n"
                "  70–84 %   →  confirmed by AI analysis\n"
                "  50–69 %   →  heuristic guess\n"
                "  < 50 %    →  file moved to _Review_Needed/\n\n"
                "REVIEW TOOL\n"
                "After sorting, open the Review Tool from the Results\n"
                "screen to manually verify low-confidence files."
            ),
            justify="left", wraplength=460,
        ).pack(padx=20, pady=20)

    def _show_about(self):
        w = ctk.CTkToplevel(self)
        w.title("About")
        w.geometry("400x280")
        w.grab_set()
        ctk.CTkLabel(
            w,
            text=(
                "DICOM Organizer  v1.0\n\n"
                "Smart medical image sorting with\n"
                "3-layer automatic body part detection.\n\n"
                "Built with Python · customtkinter · pydicom\n"
                "PyTorch · matplotlib · scikit-learn\n\n"
                "For research and educational use."
            ),
            justify="center",
        ).pack(padx=20, pady=20)
