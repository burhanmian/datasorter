"""
Patient data anonymizer for dataset mode.
Replaces PHI with hashed anonymous IDs and strips private tags.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Optional

import pydicom
from pydicom.uid import generate_uid

from utils.logger import get_logger

log = get_logger()

TAGS_TO_BLANK = [
    "PatientName",
    "PatientBirthDate",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "ReferringPhysicianName",
    "InstitutionName",
    "InstitutionAddress",
    "OperatorsName",
    "PhysiciansOfRecord",
    "PerformingPhysicianName",
    "RequestingPhysician",
    "StudyID",
]

_mapping: dict[str, str] = {}   # original_id → anon_id


def get_anon_id(patient_id: str, salt: str = "dicom_organizer_anon") -> str:
    key = f"{salt}:{patient_id}"
    if key not in _mapping:
        h = hashlib.sha256(key.encode()).hexdigest()[:10].upper()
        _mapping[key] = f"ANON_{h}"
    return _mapping[key]


def anonymize_dataset(ds: pydicom.Dataset, patient_id: str) -> str:
    """
    Modify dataset in-place to remove/replace PHI.
    Returns the anonymous patient ID assigned.
    """
    anon_id = get_anon_id(patient_id)
    ds.PatientID = anon_id
    ds.PatientName = anon_id

    for tag_name in TAGS_TO_BLANK:
        if hasattr(ds, tag_name):
            try:
                setattr(ds, tag_name, "")
            except Exception:
                pass

    # Strip all private tags
    ds.remove_private_tags()

    return anon_id


def save_mapping(output_dir: Path):
    """Save the original→anon ID mapping to a secured CSV."""
    map_file = output_dir / "_anon_mapping.csv"
    with open(map_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["original_key", "anon_id"])
        for k, v in _mapping.items():
            writer.writerow([k, v])
    log.info("Anonymization mapping saved to %s", map_file)
