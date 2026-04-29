"""
Categorizes DICOM series by modality, body part, and sub-type
(MRI sequence type or CT contrast type).
"""
from __future__ import annotations

import re
from core.dicom_reader import DicomMetadata
from utils.logger import get_logger

log = get_logger()

# MRI sequence classification keywords
MRI_SEQUENCE_PATTERNS: list[tuple[str, list[str]]] = [
    ("T1", ["t1", "t1w", "mp-rage", "mprage", "se t1", "flash", "spgr", "vibe"]),
    ("T1c", ["t1c", "t1+c", "t1 gad", "t1gad", "post gad", "postgad", "ce-t1",
             "contrast t1", "enhanced", "gd", "gadolinium"]),
    ("T2", ["t2", "t2w", "tse", "turbo spin echo", "haste"]),
    ("FLAIR", ["flair", "fluid attenuat"]),
    ("DWI", ["dwi", "diffusion", "dti", "adc", "b0", "b1000", "epi dw"]),
    ("ADC", ["adc", "apparent diffusion"]),
    ("SWI", ["swi", "suscept", "gradient echo", "gre", "star", "*2"]),
    ("PD", ["pd", "proton density"]),
    ("MRA", ["mra", "angio", "tof", "time of flight", "mrv"]),
    ("Perfusion", ["perfusion", "asl", "dsc", "dce"]),
]

# CT contrast classification keywords
CT_CONTRAST_PATTERNS: list[tuple[str, list[str]]] = [
    ("Arterial", ["arterial", "artery", "art phase"]),
    ("Venous", ["venous", "portal", "porto", "pv phase"]),
    ("Delayed", ["delayed", "equilibrium", "late"]),
    ("Contrast", ["contrast", "iv contrast", "+c", "ce", "enhanced", "cect"]),
    ("NonContrast", ["non contrast", "noncontrast", "non-contrast", "without",
                     "w/o", "wo contrast", "plain", "unenhanced", "nect"]),
]

VALID_MODALITIES = {"MR", "CT", "PT", "NM", "US", "XA", "DX", "CR", "MG"}


def classify_modality(meta: DicomMetadata) -> str:
    """Return cleaned modality string, defaulting to 'Other'."""
    mod = meta.modality.upper().strip()
    if mod in VALID_MODALITIES:
        return mod
    # Heuristic: high field strength → MR; KVP → CT
    if meta.magnetic_field_strength > 0:
        return "MR"
    if meta.kvp > 0:
        return "CT"
    return "Other"


def classify_mri_sequence(meta: DicomMetadata) -> str:
    """Return MRI sequence type label (T1, T2, FLAIR, etc.)."""
    text = " ".join([
        meta.series_description,
        meta.sequence_name,
        meta.scanning_sequence,
        meta.protocol_name,
        meta.study_description,
    ]).lower()

    for label, patterns in MRI_SEQUENCE_PATTERNS:
        for pat in patterns:
            if pat in text:
                return label
    return "Other"


def classify_ct_contrast(meta: DicomMetadata) -> str:
    """Return CT contrast phase label."""
    text = " ".join([
        meta.contrast_bolus_agent,
        meta.series_description,
        meta.protocol_name,
        meta.study_description,
    ]).lower()

    for label, patterns in CT_CONTRAST_PATTERNS:
        for pat in patterns:
            if pat in text:
                return label
    return "NonContrast"


def get_sub_type(meta: DicomMetadata, modality: str) -> str:
    """Return the sub-type string appropriate for the modality."""
    if modality == "MR":
        return classify_mri_sequence(meta)
    elif modality == "CT":
        return classify_ct_contrast(meta)
    return "Other"
