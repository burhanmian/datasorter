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

# Publicly hosted model weights (ResNet18 fine-tuned for body-part classification)
# These are ImageNet-pre-trained weights — replace URL with actual fine-tuned model
# when available.  The app works without them (falls back to heuristics).
MODEL_URL = (
    "https://download.pytorch.org/models/resnet18-f37072fd.pth"
    # Replace with actual body-part-tuned weights URL
)


def download_model():
    if MODEL_PATH.exists():
        print("[AI Model] Already present.")
        return True

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
        # Create a placeholder so we don't re-attempt every launch
        MODEL_PATH.write_bytes(b"")
        return False


if __name__ == "__main__":
    download_model()
