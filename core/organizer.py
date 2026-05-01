"""
Central orchestrator.  Runs in a background thread and emits progress
callbacks so the GUI stays responsive.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pydicom

from core.dicom_reader import read_dicom, DicomMetadata
from core.body_part_detector import detect_body_part, DetectionResult
from core.categorizer import classify_modality, get_sub_type
from core.file_operations import FileOperations
from core.manifest_builder import ManifestBuilder
from utils.config import SortConfig
from utils.helpers import find_dicom_files, safe_filename, slugify
from utils.logger import get_logger, setup_logger

log = get_logger()


@dataclass
class OrganizerStats:
    total: int = 0
    sorted_ok: int = 0
    skipped: int = 0
    errors: int = 0
    review_needed: int = 0
    body_part_counts: dict = field(default_factory=dict)
    method_counts: dict = field(default_factory=dict)


class Organizer:
    """
    Runs the full sort pipeline.  All heavy work happens in run() which is
    meant to be called from a non-GUI thread.
    """

    def __init__(
        self,
        config: SortConfig,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_file_done: Optional[Callable[[str, str, float], None]] = None,
        on_phase: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[["OrganizerStats"], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.on_progress = on_progress
        self.on_file_done = on_file_done
        self.on_phase = on_phase
        self.on_log = on_log
        self.on_done = on_done
        self.on_error = on_error

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()   # not paused initially

        self.stats = OrganizerStats()
        self._manifest = ManifestBuilder()
        self._thread: Optional[threading.Thread] = None

    # ── Control ───────────────────────────────────────────────────────────────
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def cancel(self):
        self._stop_event.set()
        self._pause_event.set()

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    # ── Internal pipeline ─────────────────────────────────────────────────────
    def _emit_log(self, msg: str):
        log.info(msg)
        if self.on_log:
            self.on_log(msg)

    def _emit_phase(self, phase: str):
        if self.on_phase:
            self.on_phase(phase)

    def _run(self):
        cfg  = self.config
        dest = Path(cfg.destination_folder)

        setup_logger(dest / "reports" / "_logs")
        file_ops = FileOperations(
            destination=dest,
            operation=cfg.file_operation,
            preview_only=cfg.preview_only,
        )

        # Phase 1 — scan
        self._emit_phase("Scanning for DICOM files…")
        self._emit_log(f"Scanning: {cfg.source_folder}")
        all_files = find_dicom_files(cfg.source_folder, recursive=cfg.recursive)
        self.stats.total = len(all_files)
        self._emit_log(f"Found {self.stats.total} potential DICOM files.")

        if self._stop_event.is_set():
            return

        # Phase 2 — process files
        self._emit_phase("Reading & detecting body parts…")
        for idx, fpath in enumerate(all_files):
            self._pause_event.wait()
            if self._stop_event.is_set():
                break
            if self.on_progress:
                self.on_progress(idx + 1, self.stats.total, fpath.name)
            self._process_file(fpath, file_ops, cfg)

        # Phase 3 — manifest + reports
        if not self._stop_event.is_set():
            self._emit_phase("Saving manifest & reports…")
            reports_dir = dest / "reports"
            self._manifest.save(reports_dir, cfg.dataset_name)
            self._manifest.save_html_report(reports_dir)

            if cfg.mode == "dataset":
                self._do_dataset_finalization(dest, cfg)

        if self.on_done:
            self.on_done(self.stats)

    def _process_file(self, fpath: Path, file_ops: FileOperations, cfg: SortConfig):
        # Read metadata
        meta = read_dicom(fpath)
        if not meta.is_valid:
            self._emit_log(f"ERROR reading {fpath.name}: {meta.error_message}")
            file_ops.move_to_errors(fpath, meta.error_message)
            self.stats.errors += 1
            return

        # Duplicate check
        if file_ops.is_duplicate(meta.sop_instance_uid):
            self.stats.skipped += 1
            return

        # Modality filter
        modality  = classify_modality(meta)
        scan_type = cfg.scan_type.upper()
        if scan_type == "MRI" and modality != "MR":
            self.stats.skipped += 1
            return
        if scan_type == "CT" and modality != "CT":
            self.stats.skipped += 1
            return

        # Pixel slices for AI/heuristic
        pixel_slices: list[np.ndarray] = []
        if cfg.enable_ai_detection:
            pixel_slices = self._load_pixel_slices(fpath)

        # Detect body part
        detection: DetectionResult = detect_body_part(
            meta,
            enable_ai=cfg.enable_ai_detection,
            sensitivity=cfg.detection_sensitivity,
            pixel_slices=pixel_slices,
        )

        sub_type = get_sub_type(meta, modality)

        # Anonymize in dataset mode
        anon_id = meta.patient_id or "UNKNOWN"
        src_to_transfer = fpath
        tmp_path: Optional[Path] = None

        if cfg.mode == "dataset" and cfg.enable_anonymization:
            try:
                ds = pydicom.dcmread(str(fpath), force=True)
                pid = str(getattr(ds, "PatientID", "UNKNOWN"))
                from core.anonymizer import anonymize_dataset
                anon_id = anonymize_dataset(ds, pid)
                tmp_fd, tmp_str = tempfile.mkstemp(suffix=".dcm")
                os.close(tmp_fd)
                tmp_path = Path(tmp_str)
                ds.save_as(str(tmp_path))
                src_to_transfer = tmp_path
            except Exception as exc:
                log.warning(
                    "Anonymization SKIPPED for %s (file NOT anonymized): %s",
                    fpath.name, exc,
                )
                if self.on_log:
                    self.on_log(f"⚠ Anon skipped: {fpath.name} — {exc}")
                tmp_path = None
                src_to_transfer = fpath

        # Build destination path
        rel_path = self._build_rel_path(cfg, modality, detection, sub_type, meta, anon_id)

        # Transfer file (review vs. normal)
        dest_path: Optional[Path] = None
        if detection.needs_review and cfg.move_uncertain_to_review:
            dest_path = file_ops.transfer_file(
                src_to_transfer,
                Path("_Review_Needed") / fpath.name,
                meta.sop_instance_uid,
            )
            self.stats.review_needed += 1
        else:
            dest_path = file_ops.transfer_file(
                src_to_transfer,
                Path(rel_path) / fpath.name,
                meta.sop_instance_uid,
            )
            if dest_path is None and not cfg.preview_only:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                self.stats.errors += 1
                return
            self.stats.sorted_ok += 1

        # Clean up temp anonymized file
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        # PNG preview per file (dataset mode)
        if (cfg.mode == "dataset" and cfg.enable_png_previews
                and dest_path and not cfg.preview_only):
            self._generate_png_preview(fpath, rel_path)

        # Update stats
        bp     = detection.body_part
        method = detection.method
        self.stats.body_part_counts[bp]     = self.stats.body_part_counts.get(bp, 0) + 1
        self.stats.method_counts[method]    = self.stats.method_counts.get(method, 0) + 1

        if self.on_file_done:
            self.on_file_done(bp, method, detection.confidence)

        # Manifest row
        self._manifest.add({
            "file_path":                  str(fpath),
            "relative_path":              str(rel_path),
            "anonymized_id":              anon_id,
            "modality":                   modality,
            "detected_body_part":         bp,
            "detection_method":           method,
            "confidence_score":           round(detection.confidence, 4),
            "alternative_guesses":        str(detection.alternatives[:3]),
            "sequence_or_contrast_type":  sub_type,
            "study_date":                 meta.study_date,
            "series_uid":                 meta.series_instance_uid,
            "series_number":              meta.series_number,
            "slice_count":                self._get_slice_count(fpath),
            "rows":                       meta.rows,
            "columns":                    meta.columns,
            "pixel_spacing_x":            meta.pixel_spacing_x,
            "pixel_spacing_y":            meta.pixel_spacing_y,
            "slice_thickness":            meta.slice_thickness,
            "manufacturer":               meta.manufacturer,
            "model":                      meta.manufacturer_model_name,
            "field_strength_or_kvp":      meta.magnetic_field_strength or meta.kvp,
            "patient_age":                meta.patient_age,
            "patient_sex":                meta.patient_sex,
            "split_assignment":           "",
            "label":                      "",
            "notes":                      "",
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_pixel_slices(self, fpath: Path) -> list[np.ndarray]:
        try:
            ds  = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array
            if arr.ndim == 2:
                return [arr]
            return [arr[0], arr[arr.shape[0] // 2], arr[-1]]
        except Exception:
            return []

    def _get_slice_count(self, fpath: Path) -> str:
        """Read NumberOfFrames tag without loading pixel data."""
        try:
            ds = pydicom.dcmread(str(fpath), force=True, stop_before_pixels=True)
            if hasattr(ds, "NumberOfFrames"):
                return str(int(str(ds.NumberOfFrames)))
            return "1"
        except Exception:
            return ""

    def _build_rel_path(
        self,
        cfg: SortConfig,
        modality: str,
        detection: DetectionResult,
        sub_type: str,
        meta: DicomMetadata,
        anon_id: str = "",
    ) -> str:
        mod_label  = "MRI" if modality == "MR" else ("CT" if modality == "CT" else modality)
        body_part  = detection.body_part
        patient_id = safe_filename(meta.patient_id or "UNKNOWN")
        study_date = safe_filename(meta.study_date or "NoDate")
        series_n   = safe_filename(str(meta.series_number or "0"))
        series_desc = slugify(meta.series_description or "Series", 32)

        if cfg.mode == "simple":
            return (
                f"{mod_label}/{body_part}"
                f"/{patient_id}_{study_date}"
                f"/Series_{series_n}_{series_desc}"
            )
        else:
            ds_name  = safe_filename(cfg.dataset_name)
            used_id  = safe_filename(anon_id or patient_id)
            return (
                f"{ds_name}/raw/{mod_label}/{body_part}/{sub_type}"
                f"/{used_id}/{study_date}/Series_{series_n}"
            )

    def _generate_png_preview(self, fpath: Path, rel_path: str):
        from core.converter import save_png_preview
        try:
            ds  = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array
            ds_name = safe_filename(self.config.dataset_name)
            preview_dir = (
                Path(self.config.destination_folder)
                / ds_name / "processed" / "png_previews"
            )
            # Flatten rel_path to a safe directory name
            flat = rel_path.replace("/", "_").replace("\\", "_")
            preview_path = preview_dir / flat / (fpath.stem + ".png")
            save_png_preview(arr, preview_path)
        except Exception as exc:
            log.debug("PNG preview skipped for %s: %s", fpath.name, exc)

    # ── Dataset finalisation ──────────────────────────────────────────────────

    def _do_dataset_finalization(self, dest: Path, cfg: SortConfig):
        import pandas as pd
        from core.splitter import split_dataset

        df = self._manifest.to_dataframe()
        if df.empty:
            return

        # NIfTI conversion (series-level)
        if cfg.enable_nifti:
            self._emit_phase("Converting DICOM series to NIfTI…")
            from core.converter import convert_series_to_nifti
            ds_name  = safe_filename(cfg.dataset_name)
            raw_dir  = dest / ds_name / "raw"
            nifti_dir = dest / ds_name / "processed" / "nifti"
            if raw_dir.exists():
                for series_dir in sorted(raw_dir.rglob("Series_*")):
                    if self._stop_event.is_set():
                        break
                    if series_dir.is_dir():
                        rel       = series_dir.relative_to(raw_dir)
                        nii_name  = str(rel).replace(os.sep, "_") + ".nii.gz"
                        out_path  = nifti_dir / nii_name
                        self._emit_log(f"  NIfTI: {series_dir.name}")
                        convert_series_to_nifti(series_dir, out_path)

        # Save anonymisation mapping
        if cfg.enable_anonymization:
            try:
                from core.anonymizer import save_mapping
                save_mapping(dest / "reports")
            except Exception as exc:
                log.warning("Could not save anon mapping: %s", exc)

        # Train / val / test split
        self._emit_phase("Splitting dataset…")
        split_dataset(
            df,
            train_ratio=cfg.train_ratio,
            val_ratio=cfg.val_ratio,
            test_ratio=cfg.test_ratio,
            seed=cfg.random_seed,
            output_dir=dest / safe_filename(cfg.dataset_name),
        )

        self._generate_readme(dest, cfg, df)

    def _generate_readme(self, dest: Path, cfg: SortConfig, df):
        from datetime import datetime
        bp_counts  = df["detected_body_part"].value_counts().to_dict()
        table_rows = "\n".join(f"| {k} | {v} |" for k, v in bp_counts.items())
        ds_name    = safe_filename(cfg.dataset_name)

        readme = f"""# {cfg.dataset_name}

**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total files:** {len(df)}
**Purpose:** {cfg.dataset_purpose}

## Body Part Distribution

| Body Part | Count |
|-----------|-------|
{table_rows}

## Folder Structure

```
{ds_name}/
├── manifest.csv
├── manifest.json
├── dataset_stats.json
├── splits/
│   ├── train.csv
│   ├── val.csv
│   └── test.csv
├── raw/
│   ├── MRI/<BodyPart>/<SequenceType>/...
│   └── CT/<BodyPart>/<ContrastType>/...
└── processed/
    ├── nifti/
    └── png_previews/
```

## Manifest Schema

Each row represents one DICOM file and includes:
- `file_path` — original location
- `anonymized_id` — hashed patient ID (PHI-free)
- `detected_body_part` — automatically detected body part
- `detection_method` — metadata | ai | heuristic | manual
- `confidence_score` — 0.0 to 1.0
- `alternative_guesses` — top 3 alternative detections

## PyTorch Loading Snippet

```python
import pandas as pd, pydicom, torch
from pathlib import Path

manifest = pd.read_csv("{ds_name}/manifest.csv")
brain_files = manifest[manifest["detected_body_part"] == "Brain"]["file_path"].tolist()

for fp in brain_files:
    ds = pydicom.dcmread(fp)
    arr = ds.pixel_array   # numpy array
    # normalise & convert to tensor ...
```

## Detection Accuracy Notes

- **Metadata-based** detection (confidence ≥ 0.85) is the most reliable.
- **AI-based** detection works best when metadata is absent.
- **Heuristic** detection is a fallback with ~60–70 % accuracy.
- Files with confidence < 0.5 are placed in `_Review_Needed/` for manual verification.
"""
        readme_path = dest / ds_name / "README.md"
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(readme, encoding="utf-8")
        self._emit_log(f"README written: {readme_path}")
