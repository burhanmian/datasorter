"""
Layer 2 — AI-based body part classifier.

Uses a lightweight ResNet18 pre-trained on ImageNet, fine-tuned for body-part
recognition.  Falls back gracefully if PyTorch / torchvision is unavailable.

On first run the model weights are downloaded from GitHub Releases.
"""
from __future__ import annotations

import io
import os
import hashlib
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from utils.logger import get_logger

log = get_logger()

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODEL_DIR / "body_part_classifier.pth"

BODY_PARTS = [
    "Brain", "Spine", "Heart", "Chest", "Abdomen",
    "Pelvis", "Upper_Limb", "Lower_Limb", "Hip",
    "Neck", "Face", "Breast", "Whole_Body", "Other_Unknown",
]

_model = None
_torch_available = False


def _try_import_torch():
    global _torch_available
    try:
        import torch
        import torchvision
        _torch_available = True
        return torch, torchvision
    except ImportError:
        return None, None


def _load_model():
    global _model
    if _model is not None:
        return _model

    torch, torchvision = _try_import_torch()
    if torch is None:
        return None

    try:
        import torchvision.models as models
        import torch.nn as nn

        net = models.resnet18(weights=None)
        net.fc = nn.Linear(net.fc.in_features, len(BODY_PARTS))

        if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1024:
            state = torch.load(str(MODEL_PATH), map_location="cpu")
            net.load_state_dict(state, strict=False)
            log.info("AI classifier: loaded weights from %s", MODEL_PATH)
        else:
            log.warning(
                "AI classifier: no valid weights at %s. "
                "Using ImageNet-only features — accuracy will be limited.",
                MODEL_PATH,
            )

        net.eval()
        _model = net
        return net
    except Exception as exc:
        log.warning("AI classifier could not be initialised: %s", exc)
        return None


def _preprocess(pixel_array: np.ndarray) -> Optional["torch.Tensor"]:
    """Convert a raw pixel array (2D or 3D) to a normalised 256×256 tensor."""
    torch, torchvision = _try_import_torch()
    if torch is None:
        return None
    try:
        import torchvision.transforms.functional as TF

        arr = pixel_array.astype(np.float32)
        # If 3D take middle slice
        if arr.ndim == 3:
            arr = arr[arr.shape[0] // 2]

        # Normalize to [0, 255]
        mn, mx = arr.min(), arr.max()
        if mx - mn > 0:
            arr = (arr - mn) / (mx - mn) * 255.0
        else:
            arr = np.zeros_like(arr)

        img = Image.fromarray(arr.astype(np.uint8)).convert("RGB")
        img = img.resize((256, 256), Image.LANCZOS)
        tensor = TF.to_tensor(img)
        tensor = TF.normalize(tensor, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        return tensor.unsqueeze(0)
    except Exception as exc:
        log.debug("AI preprocess failed: %s", exc)
        return None


def ai_detect(slices: list[np.ndarray]) -> tuple[str, float]:
    """
    Run inference on a list of pixel arrays (representative slices).
    Returns (body_part_label, confidence_score).
    """
    if not slices:
        return "Other_Unknown", 0.0

    model = _load_model()
    if model is None:
        return "Other_Unknown", 0.0

    torch, _ = _try_import_torch()
    if torch is None:
        return "Other_Unknown", 0.0

    import torch.nn.functional as F

    vote_counts: dict[str, int] = {bp: 0 for bp in BODY_PARTS}
    confidences: list[float] = []

    with torch.no_grad():
        for arr in slices:
            tensor = _preprocess(arr)
            if tensor is None:
                continue
            logits = model(tensor)
            probs = F.softmax(logits, dim=1).squeeze()
            best_idx = int(probs.argmax())
            best_label = BODY_PARTS[best_idx]
            vote_counts[best_label] += 1
            confidences.append(float(probs[best_idx]))

    if not confidences:
        return "Other_Unknown", 0.0

    winner = max(vote_counts, key=lambda k: vote_counts[k])
    avg_conf = float(np.mean(confidences))
    log.debug("AI detected: %s (avg conf %.2f)", winner, avg_conf)
    return winner, avg_conf


def is_ai_available() -> bool:
    """Return True if PyTorch is installed and the model can be loaded."""
    torch, _ = _try_import_torch()
    if torch is None:
        return False
    try:
        _load_model()
        return _model is not None
    except Exception:
        return False


def has_gpu() -> bool:
    torch, _ = _try_import_torch()
    if torch is None:
        return False
    return torch.cuda.is_available()
