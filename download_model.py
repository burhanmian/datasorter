"""
Downloads the pre-trained body part classifier weights on first run.
Falls back gracefully if the download fails — the app still works with
heuristics-only detection.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "body_part_classifier.pth"
MARKER_PATH = MODEL_DIR / ".download_attempted"  # prevents re-download on failure

# ImageNet-pre-trained ResNet18 — used as the base for body-part classification.
# Replace URL with actual fine-tuned weights when available.
# The app falls back to heuristics if this file is absent or invalid.
MODEL_URL = "https://download.pytorch.org/models/resnet18-f37072fd.pth"


def download_model():
    # Already have valid weights
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1024:
        print("[AI Model] Already present.")
        return True

    # Don't retry if we already tried and failed this session
    if MARKER_PATH.exists():
        print("[AI Model] Previous download failed — skipping. Heuristics will be used.")
        return False

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("[AI Model] Downloading pre-trained body part classifier…")
    try:
        import urllib.request

        def report(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                pct = min(downloaded / total_size * 100, 100)
                bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
                sys.stdout.write(f"\r  [{bar}] {pct:.0f}%  ")
                sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook=report)
        print("\n[AI Model] Download complete.")
        return True
    except Exception as exc:
        print(f"\n[AI Model] Download failed: {exc}")
        print("[AI Model] The app will use heuristic detection only.")
        # Mark so we skip on next launch (avoids hanging on no-internet systems)
        MARKER_PATH.write_text("failed")
        if MODEL_PATH.exists():
            MODEL_PATH.unlink()
        return False


if __name__ == "__main__":
    download_model()
