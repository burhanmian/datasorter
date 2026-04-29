"""
Window 1 — Welcome / mode selection screen.
"""
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
from gui.theme import (
    apply_theme, make_title, make_subtitle, make_primary_button,
    make_secondary_button, make_card, ACCENT, MUTED, SUCCESS,
)


class WelcomeWindow(ctk.CTk):
    def __init__(self, config, on_mode_selected):
        super().__init__()
        self.config_obj = config
        self.on_mode_selected = on_mode_selected

        apply_theme(config.theme)
        self.title("DICOM Organizer")
        self.geometry("820x580")
        self.minsize(700, 500)
        self.resizable(True, True)

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 820) // 2
        y = (sh - 580) // 2
        self.geometry(f"820x580+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(40, 20))

        make_title(header, "🏥 DICOM Organizer").pack(anchor="center")
        make_subtitle(header, "Smart medical image sorting with automatic body part detection").pack(
            anchor="center", pady=(6, 0)
        )

        # Mode cards
        cards_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=40, pady=10)
        cards_frame.columnconfigure((0, 1), weight=1, uniform="col")

        # Simple mode card
        simple_card = make_card(cards_frame)
        simple_card.grid(row=0, column=0, padx=(0, 12), pady=10, sticky="nsew")
        self._build_mode_card(
            simple_card,
            icon="📁",
            title="Just Sort My Files",
            description=(
                "Automatically organise your DICOM files into\n"
                "neat folders by modality and body part.\n\n"
                "Perfect for quick, everyday sorting."
            ),
            badge_text="Simple Mode",
            badge_color=ACCENT,
            command=lambda: self._select("simple"),
        )

        # Dataset mode card
        dataset_card = make_card(cards_frame)
        dataset_card.grid(row=0, column=1, padx=(12, 0), pady=10, sticky="nsew")
        self._build_mode_card(
            dataset_card,
            icon="🤖",
            title="Build ML Dataset",
            description=(
                "Sort + anonymise + convert to NIfTI +\n"
                "generate train/val/test splits and manifests.\n\n"
                "For researchers and AI developers."
            ),
            badge_text="Advanced Mode",
            badge_color=SUCCESS,
            command=lambda: self._select("dataset"),
        )

        # Bottom bar
        bottom = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        bottom.pack(fill="x", padx=40, pady=(0, 24))

        # Theme toggle
        theme_var = ctk.StringVar(value=self.config_obj.theme)
        theme_switch = ctk.CTkSwitch(
            bottom, text="Dark mode",
            variable=theme_var, onvalue="dark", offvalue="light",
            command=self._toggle_theme,
        )
        theme_switch.pack(side="left")

        # Help / About
        make_secondary_button(bottom, "❓ Help", command=self._show_help, width=100).pack(
            side="right", padx=(8, 0)
        )
        make_secondary_button(bottom, "ℹ️ About", command=self._show_about, width=100).pack(
            side="right"
        )

    def _build_mode_card(self, card, icon, title, description, badge_text, badge_color, command):
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=48)).pack(pady=(0, 8))

        badge = ctk.CTkLabel(
            inner, text=f"  {badge_text}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=badge_color, corner_radius=8, text_color="white",
        )
        badge.pack(pady=(0, 10))

        ctk.CTkLabel(
            inner, text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            inner, text=description,
            font=ctk.CTkFont(size=12),
            text_color=MUTED, justify="center",
        ).pack(pady=(0, 20))

        make_primary_button(inner, f"Choose {title.split()[0]} →", command=command, width=200).pack()

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

    def _show_help(self):
        win = ctk.CTkToplevel(self)
        win.title("Help")
        win.geometry("500x400")
        win.grab_set()
        ctk.CTkLabel(
            win,
            text=(
                "DICOM Organizer — Help\n\n"
                "This application sorts DICOM medical images (MRI & CT scans)\n"
                "into organised folders automatically.\n\n"
                "HOW IT WORKS:\n"
                "1. Choose a folder containing your DICOM files.\n"
                "2. Choose where you want them sorted.\n"
                "3. The app detects body parts using 3 layers:\n"
                "   • Layer 1: Reads DICOM tag metadata\n"
                "   • Layer 2: AI image analysis\n"
                "   • Layer 3: Anatomical rules\n\n"
                "Files needing manual review go into _Review_Needed/\n\n"
                "No technical knowledge required!"
            ),
            justify="left",
            wraplength=460,
        ).pack(padx=20, pady=20)

    def _show_about(self):
        win = ctk.CTkToplevel(self)
        win.title("About")
        win.geometry("400x260")
        win.grab_set()
        ctk.CTkLabel(
            win,
            text=(
                "DICOM Organizer v1.0\n\n"
                "Smart medical image sorting with\n"
                "3-layer automatic body part detection.\n\n"
                "Built with Python, customtkinter, pydicom,\n"
                "PyTorch, and matplotlib.\n\n"
                "For research and educational use."
            ),
            justify="center",
        ).pack(padx=20, pady=20)
