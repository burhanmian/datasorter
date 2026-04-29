"""
DICOM file reader.  Extracts structured metadata from a DICOM file using
pydicom, with graceful handling of corrupt or partial files.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import pydicom
from pydicom.errors import InvalidDicomError

from utils.logger import get_logger

log = get_logger()


@dataclass
class DicomMetadata:
    file_path: Path
    is_valid: bool = False
    error_message: str = ""

    # Identity
    modality: str = "UNKNOWN"
    sop_instance_uid: str = ""
    study_instance_uid: str = ""
    series_instance_uid: str = ""
    series_number: str = ""
    instance_number: str = ""

    # Patient
    patient_id: str = "UNKNOWN"
    patient_name: str = "UNKNOWN"
    patient_age: str = ""
    patient_sex: str = ""

    # Study / Series descriptions
    study_date: str = ""
    study_description: str = ""
    series_description: str = ""
    protocol_name: str = ""
    body_part_examined: str = ""
    requested_procedure_description: str = ""
    performed_procedure_step_description: str = ""

    # Geometry
    rows: int = 0
    columns: int = 0
    slice_thickness: float = 0.0
    pixel_spacing_x: float = 0.0
    pixel_spacing_y: float = 0.0
    reconstruction_diameter: float = 0.0
    patient_position: str = ""
    image_orientation_patient: list[float] = field(default_factory=list)

    # MRI-specific
    magnetic_field_strength: float = 0.0
    sequence_name: str = ""
    scanning_sequence: str = ""
    repetition_time: float = 0.0
    echo_time: float = 0.0
    flip_angle: float = 0.0

    # CT-specific
    kvp: float = 0.0
    xray_tube_current: float = 0.0
    convolution_kernel: str = ""
    contrast_bolus_agent: str = ""

    # Manufacturer
    manufacturer: str = ""
    manufacturer_model_name: str = ""

    # Raw pixel array (lazy — loaded separately)
    pixel_array: Optional[Any] = field(default=None, repr=False)


def _safe_get(ds: pydicom.Dataset, tag: str, default: Any = "") -> Any:
    try:
        val = getattr(ds, tag, default)
        if val is None:
            return default
        if hasattr(val, "original_string"):
            return str(val).strip()
        return val
    except Exception:
        return default


def _safe_float(ds: pydicom.Dataset, tag: str) -> float:
    try:
        val = _safe_get(ds, tag, "")
        if val == "":
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        # might be DS (DecimalString) sequence
        if hasattr(val, "__iter__") and not isinstance(val, str):
            return float(list(val)[0])
        return float(str(val).split("\\")[0])
    except Exception:
        return 0.0


def read_dicom(path: Path, load_pixels: bool = False) -> DicomMetadata:
    """Read a DICOM file and return a populated DicomMetadata object."""
    meta = DicomMetadata(file_path=path)
    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=not load_pixels, force=True)
    except InvalidDicomError as exc:
        meta.error_message = f"Invalid DICOM: {exc}"
        return meta
    except Exception as exc:
        meta.error_message = f"Read error: {exc}"
        return meta

    try:
        meta.is_valid = True
        meta.modality = str(_safe_get(ds, "Modality", "UNKNOWN")).upper()
        meta.sop_instance_uid = str(_safe_get(ds, "SOPInstanceUID", ""))
        meta.study_instance_uid = str(_safe_get(ds, "StudyInstanceUID", ""))
        meta.series_instance_uid = str(_safe_get(ds, "SeriesInstanceUID", ""))
        meta.series_number = str(_safe_get(ds, "SeriesNumber", ""))
        meta.instance_number = str(_safe_get(ds, "InstanceNumber", ""))

        meta.patient_id = str(_safe_get(ds, "PatientID", "UNKNOWN")).strip() or "UNKNOWN"
        meta.patient_name = str(_safe_get(ds, "PatientName", "UNKNOWN")).strip() or "UNKNOWN"
        meta.patient_age = str(_safe_get(ds, "PatientAge", "")).strip()
        meta.patient_sex = str(_safe_get(ds, "PatientSex", "")).strip()

        meta.study_date = str(_safe_get(ds, "StudyDate", "")).strip()
        meta.study_description = str(_safe_get(ds, "StudyDescription", "")).strip()
        meta.series_description = str(_safe_get(ds, "SeriesDescription", "")).strip()
        meta.protocol_name = str(_safe_get(ds, "ProtocolName", "")).strip()
        meta.body_part_examined = str(_safe_get(ds, "BodyPartExamined", "")).strip()
        meta.requested_procedure_description = str(
            _safe_get(ds, "RequestedProcedureDescription", "")
        ).strip()
        meta.performed_procedure_step_description = str(
            _safe_get(ds, "PerformedProcedureStepDescription", "")
        ).strip()

        meta.rows = int(_safe_get(ds, "Rows", 0))
        meta.columns = int(_safe_get(ds, "Columns", 0))
        meta.slice_thickness = _safe_float(ds, "SliceThickness")
        meta.reconstruction_diameter = _safe_float(ds, "ReconstructionDiameter")
        meta.patient_position = str(_safe_get(ds, "PatientPosition", "")).strip()

        ps = _safe_get(ds, "PixelSpacing", [])
        if ps and hasattr(ps, "__iter__") and not isinstance(ps, str):
            ps_list = list(ps)
            meta.pixel_spacing_x = float(ps_list[0]) if ps_list else 0.0
            meta.pixel_spacing_y = float(ps_list[1]) if len(ps_list) > 1 else meta.pixel_spacing_x
        elif isinstance(ps, str) and "\\" in ps:
            parts = ps.split("\\")
            meta.pixel_spacing_x = float(parts[0]) if parts else 0.0
            meta.pixel_spacing_y = float(parts[1]) if len(parts) > 1 else meta.pixel_spacing_x

        iop = _safe_get(ds, "ImageOrientationPatient", [])
        if iop and hasattr(iop, "__iter__") and not isinstance(iop, str):
            meta.image_orientation_patient = [float(v) for v in iop]

        meta.magnetic_field_strength = _safe_float(ds, "MagneticFieldStrength")
        meta.sequence_name = str(_safe_get(ds, "SequenceName", "")).strip()
        meta.scanning_sequence = str(_safe_get(ds, "ScanningSequence", "")).strip()
        meta.repetition_time = _safe_float(ds, "RepetitionTime")
        meta.echo_time = _safe_float(ds, "EchoTime")
        meta.flip_angle = _safe_float(ds, "FlipAngle")

        meta.kvp = _safe_float(ds, "KVP")
        meta.xray_tube_current = _safe_float(ds, "XRayTubeCurrent")
        meta.convolution_kernel = str(_safe_get(ds, "ConvolutionKernel", "")).strip()
        meta.contrast_bolus_agent = str(_safe_get(ds, "ContrastBolusAgent", "")).strip()

        meta.manufacturer = str(_safe_get(ds, "Manufacturer", "")).strip()
        meta.manufacturer_model_name = str(_safe_get(ds, "ManufacturerModelName", "")).strip()

        if load_pixels:
            try:
                meta.pixel_array = ds.pixel_array
            except Exception:
                pass

    except Exception as exc:
        log.debug("Metadata parse warning for %s: %s", path.name, exc)

    return meta
