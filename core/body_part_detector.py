"""
3-Layer body part detection engine.

Layer 1: DICOM metadata keyword matching
Layer 2: AI image classifier
Layer 3: Anatomical heuristics

Returns a DetectionResult with body part, confidence, method, and alternatives.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from core.dicom_reader import DicomMetadata
from core.heuristics import heuristic_detect
from utils.logger import get_logger

log = get_logger()

# ---------------------------------------------------------------------------
# Comprehensive keyword mapping (Layer 1)
# ---------------------------------------------------------------------------
BODY_PART_KEYWORDS: dict[str, list[str]] = {
    "Brain": [
        "brain", "head", "skull", "cerebr", "cranial", "intracranial",
        "neuro", "cabeza", "tete", "gehirn", "cerveau", "encephal",
        "hemisphere", "cortex", "basal ganglia", "ventricle", "pituitary",
        "fossa", "cerebellum", "brainstem", "temporal lobe",
    ],
    "Spine": [
        "spine", "spinal", "vertebr", "cervical", "thoracic", "lumbar",
        "sacral", "c-spine", "l-spine", "t-spine", "back", "cord",
        "disc", "foramen", "spondyl", "myelogram", "columna",
    ],
    "Heart": [
        "heart", "cardiac", "cardio", "coronary", "myocard", "aortic",
        "ventric", "atri", "valv", "pericardium", "endocard",
        "mitral", "tricuspid", "aorta", "pulmonary artery",
    ],
    "Chest": [
        "chest", "thorax", "thorac", "lung", "pulmon", "pleura",
        "mediastin", "trachea", "bronch", "rib", "sternum",
        "thoracic cage", "pectoral",
    ],
    "Abdomen": [
        "abdomen", "abdominal", "liver", "hepatic", "kidney", "renal",
        "spleen", "splenic", "pancrea", "stomach", "gastric",
        "bowel", "intestin", "colon", "adrenal", "bile", "gallbladder",
        "portal", "mesentery", "retroperitoneal",
    ],
    "Pelvis": [
        "pelvis", "pelvic", "bladder", "prostate", "uterus", "ovary",
        "rectum", "sigmoid", "sacrum", "ilium", "ischium",
        "pudendal", "perineum",
    ],
    "Upper_Limb": [
        "arm", "shoulder", "elbow", "wrist", "hand", "finger",
        "humerus", "radius", "ulna", "carpal", "forearm",
        "upper extremity", "upper limb", "brachial", "clavicle",
        "scapula", "thumb", "metacarpal",
    ],
    "Lower_Limb": [
        "leg", "knee", "ankle", "foot", "toe", "femur",
        "tibia", "fibula", "patella", "thigh", "calf",
        "lower extremity", "lower limb", "metatarsal",
        "achilles", "plantar", "tarsal",
    ],
    "Hip": [
        "hip", "iliac", "femoral head", "acetabulum", "trochanter",
        "sacroiliac",
    ],
    "Neck": [
        "neck", "throat", "thyroid", "carotid", "larynx", "pharynx",
        "cervix", "hyoid", "jugular",
    ],
    "Face": [
        "face", "facial", "sinus", "orbit", "maxilla", "mandible",
        "jaw", "tmj", "nasal", "zygomatic", "palate", "parotid",
        "temporal bone", "mastoid", "ear", "nose",
    ],
    "Breast": [
        "breast", "mammo", "mammary", "mastectomy",
    ],
    "Whole_Body": [
        "whole body", "wholebody", "total body", "pet-ct",
        "skeletal survey", "bone survey", "whole-body",
    ],
}

SENSITIVITY_THRESHOLDS = {
    "conservative": 0.90,
    "balanced": 0.85,
    "aggressive": 0.70,
}

AI_THRESHOLDS = {
    "conservative": 0.85,
    "balanced": 0.75,
    "aggressive": 0.60,
}


@dataclass
class DetectionResult:
    body_part: str = "Other_Unknown"
    confidence: float = 0.0
    method: str = "none"                     # metadata | ai | heuristic | manual
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    needs_review: bool = False


# ---------------------------------------------------------------------------
# Layer 1 — Metadata keyword matching
# ---------------------------------------------------------------------------

def _score_text_against_keywords(text: str) -> dict[str, float]:
    """Return a score dict mapping body part → confidence based on keyword hits."""
    text_lower = text.lower()
    scores: dict[str, float] = {}
    for part, keywords in BODY_PART_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                # Longer keyword match → higher confidence bonus
                bonus = min(len(kw) / 20.0, 0.3) + 0.5
                scores[part] = max(scores.get(part, 0.0), bonus)
    return scores


def _metadata_detect(meta: DicomMetadata) -> dict[str, float]:
    """
    Check DICOM tags in priority order.
    Returns merged score dict.
    """
    tag_weights = [
        (meta.body_part_examined, 1.0),
        (meta.study_description, 0.85),
        (meta.series_description, 0.80),
        (meta.protocol_name, 0.75),
        (meta.requested_procedure_description, 0.70),
        (meta.performed_procedure_step_description, 0.65),
    ]

    combined: dict[str, float] = {}
    for text, weight in tag_weights:
        if not text or text.upper() in ("", "UNKNOWN", "N/A"):
            continue
        scores = _score_text_against_keywords(text)
        for part, sc in scores.items():
            combined[part] = max(combined.get(part, 0.0), sc * weight)

    return combined


# ---------------------------------------------------------------------------
# Public detection function
# ---------------------------------------------------------------------------

def detect_body_part(
    meta: DicomMetadata,
    enable_ai: bool = True,
    sensitivity: str = "balanced",
    pixel_slices: Optional[list[np.ndarray]] = None,
) -> DetectionResult:
    """
    Run the 3-layer detection pipeline.

    Parameters
    ----------
    meta:
        Parsed DICOM metadata.
    enable_ai:
        Whether to run Layer 2 (AI classifier).
    sensitivity:
        'conservative', 'balanced', or 'aggressive'.
    pixel_slices:
        Representative slices (numpy arrays) for AI/heuristic analysis.
    """
    l1_threshold = SENSITIVITY_THRESHOLDS.get(sensitivity, 0.85)
    l2_threshold = AI_THRESHOLDS.get(sensitivity, 0.75)

    # ------ Layer 1: Metadata ------
    l1_scores = _metadata_detect(meta)
    l1_top: list[tuple[str, float]] = sorted(l1_scores.items(), key=lambda x: -x[1])

    l1_best_part = l1_top[0][0] if l1_top else None
    l1_best_conf = l1_top[0][1] if l1_top else 0.0

    log.debug("L1 metadata result: %s=%.2f", l1_best_part, l1_best_conf)

    if l1_best_conf >= l1_threshold:
        alts = [(p, c) for p, c in l1_top[1:4]]
        return DetectionResult(
            body_part=l1_best_part,
            confidence=min(l1_best_conf, 0.99),
            method="metadata",
            alternatives=alts,
            needs_review=False,
        )

    # ------ Layer 2: AI ------
    l2_part: Optional[str] = None
    l2_conf = 0.0

    if enable_ai and pixel_slices:
        try:
            from core.ai_classifier import ai_detect
            l2_part, l2_conf = ai_detect(pixel_slices)
            log.debug("L2 AI result: %s=%.2f", l2_part, l2_conf)
        except Exception as exc:
            log.warning("AI classifier error (falling back): %s", exc)

    if l2_part and l2_conf >= l2_threshold:
        # Agreement between metadata and AI boosts confidence
        if l1_best_part and l1_best_part == l2_part:
            final_conf = min((l1_best_conf + l2_conf) / 2 + 0.1, 0.98)
        else:
            final_conf = l2_conf
        alts = [(p, c) for p, c in l1_top[:3] if p != l2_part]
        return DetectionResult(
            body_part=l2_part,
            confidence=final_conf,
            method="ai",
            alternatives=alts[:3],
            needs_review=False,
        )

    # ------ Layer 3: Heuristics ------
    pixel_arr = pixel_slices[len(pixel_slices) // 2] if pixel_slices else None
    h_part, h_conf = heuristic_detect(meta, pixel_arr)
    log.debug("L3 heuristic result: %s=%.2f", h_part, h_conf)

    # Merge all evidence
    all_candidates: list[tuple[str, float]] = []
    if l1_best_part:
        all_candidates.append((l1_best_part, l1_best_conf * 0.8))
    if l2_part:
        all_candidates.append((l2_part, l2_conf * 0.9))
    all_candidates.append((h_part, h_conf))

    # Majority voting / highest combined score
    part_scores: dict[str, float] = {}
    for part, conf in all_candidates:
        part_scores[part] = part_scores.get(part, 0.0) + conf

    best = max(part_scores, key=lambda k: part_scores[k])
    best_conf = min(part_scores[best] / len(all_candidates), 0.75)

    needs_review = best_conf < 0.5 or best == "Other_Unknown"
    final_label = f"Uncertain_{best}" if needs_review else best

    alts = sorted(
        [(p, c) for p, c in part_scores.items() if p != best],
        key=lambda x: -x[1],
    )[:3]

    return DetectionResult(
        body_part=final_label,
        confidence=best_conf,
        method="heuristic",
        alternatives=alts,
        needs_review=needs_review,
    )
