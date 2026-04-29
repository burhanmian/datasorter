"""
General helper utilities for DICOM Organizer.
"""
import re
import hashlib
import os
import shutil
from pathlib import Path
from typing import Optional
import unicodedata


def slugify(text: str, max_length: int = 64) -> str:
    """Convert arbitrary text to a safe filesystem name."""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s\-]", "_", text)
    text = re.sub(r"[\s_]+", "_", text).strip("_")
    return text[:max_length] or "unnamed"


def hash_patient_id(patient_id: str, salt: str = "dicom_organizer") -> str:
    """Return a short anonymous ID for a patient."""
    raw = f"{salt}:{patient_id}"
    return "ANON_" + hashlib.sha256(raw.encode()).hexdigest()[:10].upper()


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def get_free_space(path: str) -> int:
    """Return free disk space in bytes for the drive containing *path*."""
    try:
        stat = shutil.disk_usage(path)
        return stat.free
    except Exception:
        return 0


def safe_filename(name: str) -> str:
    """Strip characters that are illegal on Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', "_", str(name)).strip()


def ensure_unique_path(path: Path) -> Path:
    """If *path* exists, append _1, _2 … until unique."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def find_dicom_files(root: str, recursive: bool = True) -> list[Path]:
    """Walk *root* and return paths that are likely DICOM files."""
    root_path = Path(root)
    candidates: list[Path] = []
    pattern = "**/*" if recursive else "*"
    for p in root_path.glob(pattern):
        if p.is_file():
            # Accept .dcm extension or no extension (many DICOM files have none)
            if p.suffix.lower() in (".dcm", ".dicom", "") or _is_likely_dicom(p):
                candidates.append(p)
    return candidates


def _is_likely_dicom(path: Path) -> bool:
    """Check DICOM magic bytes (DICM at offset 128)."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except Exception:
        return False


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
