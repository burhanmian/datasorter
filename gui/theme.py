"""
Shared theme constants and CTk helper wrappers.
"""
import customtkinter as ctk

# Colours
ACCENT = "#4A90D9"
ACCENT_HOVER = "#357ABD"
SUCCESS = "#27AE60"
WARNING = "#E67E22"
DANGER = "#E74C3C"
MUTED = "#7F8C8D"
BG_DARK = "#1E2229"
BG_CARD = "#2B3038"


def apply_theme(theme: str = "dark"):
    ctk.set_appearance_mode(theme)
    ctk.set_default_color_theme("blue")


def make_title(parent, text: str, size: int = 24) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=size, weight="bold"))


def make_subtitle(parent, text: str, size: int = 14) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=size), text_color=MUTED)


def make_section_label(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=13, weight="bold"))


def make_card(parent, **kwargs) -> ctk.CTkFrame:
    defaults = {"corner_radius": 12, "border_width": 0}
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def make_primary_button(parent, text: str, command=None, width: int = 180) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        font=ctk.CTkFont(size=14, weight="bold"),
        fg_color=ACCENT, hover_color=ACCENT_HOVER,
        corner_radius=10, height=44,
    )


def make_secondary_button(parent, text: str, command=None, width: int = 140) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        font=ctk.CTkFont(size=13),
        fg_color="transparent", border_width=2,
        corner_radius=10, height=40,
    )


def add_tooltip(widget, text: str):
    """Simple tooltip using Toplevel."""
    tip: ctk.CTkToplevel | None = None

    def show(event):
        nonlocal tip
        if tip:
            return
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tip = ctk.CTkToplevel(widget)
        tip.wm_overrideredirect(True)
        tip.geometry(f"+{x}+{y}")
        lbl = ctk.CTkLabel(
            tip, text=text, wraplength=280,
            font=ctk.CTkFont(size=11),
            corner_radius=6, padx=8, pady=4,
        )
        lbl.pack()

    def hide(event):
        nonlocal tip
        if tip:
            tip.destroy()
            tip = None

    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)
