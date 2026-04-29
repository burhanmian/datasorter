"""
Layer 3 — Anatomical heuristics body-part detection.
Uses image geometry, pixel statistics, and DICOM geometry tags.
"""
from __future__ import annotations

from typing import Optional
import numpy as np

from core.dicom_reader import DicomMetadata
from utils.logger import get_logger

log = get_logger()


def heuristic_detect(meta: DicomMetadata, pixel_array: Optional[np.ndarray] = None
                     ) -> tuple[str, float]:
    """
    Return (body_part_label, confidence_score) using anatomical heuristics.
    confidence_score is in [0.0, 1.0].
    """
    scores: dict[str, float] = {}

    # --- Geometry-based rules ---
    rows = meta.rows
    cols = meta.columns
    fov = meta.reconstruction_diameter  # mm
    ps_x = meta.pixel_spacing_x
    ps_y = meta.pixel_spacing_y
    st = meta.slice_thickness

    # Small FOV → likely extremity/limb
    if 0 < fov < 150:
        scores["Upper_Limb"] = scores.get("Upper_Limb", 0) + 0.4
        scores["Lower_Limb"] = scores.get("Lower_Limb", 0) + 0.3
        scores["Face"] = scores.get("Face", 0) + 0.2

    # Medium FOV → brain or neck
    if 150 <= fov < 260:
        scores["Brain"] = scores.get("Brain", 0) + 0.45
        scores["Neck"] = scores.get("Neck", 0) + 0.2
        scores["Face"] = scores.get("Face", 0) + 0.15

    # Large FOV → torso
    if fov >= 350:
        scores["Chest"] = scores.get("Chest", 0) + 0.35
        scores["Abdomen"] = scores.get("Abdomen", 0) + 0.3
        scores["Pelvis"] = scores.get("Pelvis", 0) + 0.2

    # Very small pixel spacing → high-res scan of small area (extremity/brain)
    if 0 < ps_x < 0.5:
        scores["Brain"] = scores.get("Brain", 0) + 0.15
        scores["Upper_Limb"] = scores.get("Upper_Limb", 0) + 0.1

    # Large matrix → CT chest/abdomen
    if rows >= 512 and cols >= 512:
        scores["Chest"] = scores.get("Chest", 0) + 0.25
        scores["Abdomen"] = scores.get("Abdomen", 0) + 0.2

    # Thick slices → body / thorax CT
    if st >= 5.0:
        scores["Chest"] = scores.get("Chest", 0) + 0.2
        scores["Abdomen"] = scores.get("Abdomen", 0) + 0.15

    # Thin slices → brain MRI or spine
    if 0 < st <= 1.5:
        scores["Brain"] = scores.get("Brain", 0) + 0.2
        scores["Spine"] = scores.get("Spine", 0) + 0.1

    # Aspect ratio of image (very tall/thin → spine)
    if rows > 0 and cols > 0:
        aspect = rows / cols
        if aspect > 2.5 or aspect < 0.4:
            scores["Spine"] = scores.get("Spine", 0) + 0.3

    # --- Modality-specific bias ---
    mod = meta.modality.upper()
    if mod == "MR":
        scores["Brain"] = scores.get("Brain", 0) + 0.05
    elif mod == "CT":
        scores["Chest"] = scores.get("Chest", 0) + 0.05

    # --- Pixel statistics (if array provided) ---
    if pixel_array is not None:
        try:
            arr = pixel_array.astype(np.float32)
            mean_val = float(np.mean(arr))
            std_val = float(np.std(arr))
            # HU range for air is very negative; lots of air → chest
            if mod == "CT":
                air_fraction = float(np.mean(arr < -500))
                if air_fraction > 0.3:
                    scores["Chest"] = scores.get("Chest", 0) + 0.4
                # Bone-heavy (high HU) → limb/skull
                bone_fraction = float(np.mean(arr > 400))
                if bone_fraction > 0.15:
                    scores["Upper_Limb"] = scores.get("Upper_Limb", 0) + 0.25
                    scores["Lower_Limb"] = scores.get("Lower_Limb", 0) + 0.25
            else:
                # MRI: uniform, high-intensity centre → brain
                centre_slice = arr[arr.shape[0] // 2] if arr.ndim == 3 else arr
                if std_val > 0:
                    centre_mean = float(np.mean(centre_slice))
                    symmetry = abs(centre_mean - mean_val) / (std_val + 1e-6)
                    if symmetry < 0.3:
                        scores["Brain"] = scores.get("Brain", 0) + 0.2
        except Exception as exc:
            log.debug("Heuristic pixel analysis failed: %s", exc)

    if not scores:
        return "Other_Unknown", 0.1

    best = max(scores, key=lambda k: scores[k])
    raw_conf = scores[best]
    # Normalize to [0, 0.7] range so heuristics never exceed 70 % confidence
    conf = min(raw_conf, 0.7)
    log.debug("Heuristic result: %s (%.2f)", best, conf)
    return best, conf
