"""
Configuration management for DICOM Organizer.
Handles save/load of user presets and app settings.
"""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


APP_DATA_DIR = Path.home() / ".dicom_organizer"
PRESETS_FILE = APP_DATA_DIR / "presets.json"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"


@dataclass
class SortConfig:
    # Paths
    source_folder: str = ""
    destination_folder: str = ""
    recursive: bool = True

    # Mode
    mode: str = "simple"          # "simple" or "dataset"
    scan_type: str = "both"       # "mri", "ct", "both", "auto"

    # Body part detection
    enable_ai_detection: bool = True
    detection_sensitivity: str = "balanced"   # "conservative", "balanced", "aggressive"
    move_uncertain_to_review: bool = True

    # File operation
    file_operation: str = "copy"  # "copy" or "move"
    preview_only: bool = False

    # Dataset mode extras
    dataset_name: str = "my_dataset"
    dataset_purpose: str = "research"
    enable_nifti: bool = False
    enable_png_previews: bool = True
    enable_anonymization: bool = True
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    random_seed: int = 42

    # UI
    theme: str = "dark"
    first_run: bool = True


def load_settings() -> SortConfig:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            cfg = SortConfig()
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            return cfg
        except Exception:
            pass
    return SortConfig()


def save_settings(cfg: SortConfig):
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")


def list_presets() -> list[str]:
    if PRESETS_FILE.exists():
        try:
            data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
            return list(data.keys())
        except Exception:
            pass
    return []


def save_preset(name: str, cfg: SortConfig):
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    presets = {}
    if PRESETS_FILE.exists():
        try:
            presets = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    presets[name] = asdict(cfg)
    PRESETS_FILE.write_text(json.dumps(presets, indent=2), encoding="utf-8")


def load_preset(name: str) -> Optional[SortConfig]:
    if not PRESETS_FILE.exists():
        return None
    try:
        presets = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        data = presets.get(name)
        if data is None:
            return None
        cfg = SortConfig()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg
    except Exception:
        return None
