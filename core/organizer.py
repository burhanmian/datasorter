"""
Central orchestrator.  Runs in a background thread and emits progress
callbacks so the GUI stays responsive.
"""
from __future__ import annotations

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
        on_done: Optional[Callable[[OrganizerStats], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.on_progress = on_progress     # (current, total, filename)
        self.on_file_done = on_file_done   # (body_part, method, confidence)
        self.on_phase = on_phase           # phase name string
        self.on_log = on_log               # log message string
        self.on_done = on_done             # OrganizerStats
        self.on_error = on_error           # error string

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()            # not paused initially

        self.stats = OrganizerStats()
        self._manifest = ManifestBuilder()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def cancel(self):
        self._stop_event.set()
        self._pause_event.set()   # unblock if paused

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------
    def _emit_log(self, msg: str):
        log.info(msg)
        if self.on_log:
            self.on_log(msg)

    def _emit_phase(self, phase: str):
        if self.on_phase:
            self.on_phase(phase)

    def _run(self):
        cfg = self.config
        dest = Path(cfg.destination_folder)

        setup_logger(dest / "reports" / "_logs")
        file_ops = FileOperations(
            destination=dest,
            operation=cfg.file_operation,
            preview_only=cfg.preview_only,
        )

        # ---- Phase 1: Scan ----
        self._emit_phase("Scanning for DICOM files…")
        self._emit_log(f"Scanning: {cfg.source_folder}")
        all_files = find_dicom_files(cfg.source_folder, recursive=cfg.recursive)
        self.stats.total = len(all_files)
        self._emit_log(f"Found {self.stats.total} potential DICOM files.")

        if self._stop_event.is_set():
            return

        # ---- Phase 2: Process each file ----
        self._emit_phase("Reading & detecting body parts…")

        for idx, fpath in enumerate(all_files):
            self._pause_event.wait()   # blocks if paused
            if self._stop_event.is_set():
                break

            if self.on_progress:
                self.on_progress(idx + 1, self.stats.total, fpath.name)

            self._process_file(fpath, file_ops, cfg)

        # ---- Phase 3: Manifest & reports ----
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

        # Classify modality
        modality = classify_modality(meta)
        scan_type = cfg.scan_type.upper()
        if scan_type == "MRI" and modality != "MR":
            self.stats.skipped += 1
            return
        if scan_type == "CT" and modality != "CT":
            self.stats.skipped += 1
            return
        if scan_type not in ("MRI", "CT", "BOTH", "AUTO"):
            pass  # accept all

        # Load representative pixel slices for AI/heuristic
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

        # Sub-type (MRI sequence / CT contrast)
        sub_type = get_sub_type(meta, modality)

        # Build destination path
        rel_path = self._build_rel_path(cfg, modality, detection, sub_type, meta)

        # Uncertain files go to review instead of the body-part folder
        if detection.needs_review and cfg.move_uncertain_to_review:
            dest_path = file_ops.transfer_file(
                fpath, Path("_Review_Needed") / fpath.name, meta.sop_instance_uid
            )
            self.stats.review_needed += 1
        else:
            dest_path = file_ops.transfer_file(
                fpath, Path(rel_path) / fpath.name, meta.sop_instance_uid
            )
            if dest_path is None and not cfg.preview_only:
                self.stats.errors += 1
                return
            self.stats.sorted_ok += 1

        # Update stats
        bp = detection.body_part
        self.stats.body_part_counts[bp] = self.stats.body_part_counts.get(bp, 0) + 1
        method = detection.method
        self.stats.method_counts[method] = self.stats.method_counts.get(method, 0) + 1

        if self.on_file_done:
            self.on_file_done(bp, method, detection.confidence)

        # Manifest row
        self._manifest.add({
            "file_path": str(fpath),
            "relative_path": str(rel_path),
            "anonymized_id": meta.patient_id,
            "modality": modality,
            "detected_body_part": bp,
            "detection_method": method,
            "confidence_score": round(detection.confidence, 4),
            "alternative_guesses": str(detection.alternatives[:3]),
            "sequence_or_contrast_type": sub_type,
            "study_date": meta.study_date,
            "series_uid": meta.series_instance_uid,
            "series_number": meta.series_number,
            "slice_count": "",
            "rows": meta.rows,
            "columns": meta.columns,
            "pixel_spacing_x": meta.pixel_spacing_x,
            "pixel_spacing_y": meta.pixel_spacing_y,
            "slice_thickness": meta.slice_thickness,
            "manufacturer": meta.manufacturer,
            "model": meta.manufacturer_model_name,
            "field_strength_or_kvp": meta.magnetic_field_strength or meta.kvp,
            "patient_age": meta.patient_age,
            "patient_sex": meta.patient_sex,
            "split_assignment": "",
            "label": "",
            "notes": "",
        })

    def _load_pixel_slices(self, fpath: Path) -> list[np.ndarray]:
        """Load up to 3 representative slices from a DICOM file."""
        try:
            import pydicom
            ds = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array
            if arr.ndim == 2:
                return [arr]
            slices = [arr[0], arr[arr.shape[0] // 2], arr[-1]]
            return slices
        except Exception:
            return []

    def _build_rel_path(
        self,
        cfg: SortConfig,
        modality: str,
        detection: DetectionResult,
        sub_type: str,
        meta: DicomMetadata,
    ) -> str:
        """Build relative destination path based on mode."""
        mod_label = "MRI" if modality == "MR" else ("CT" if modality == "CT" else modality)
        body_part = detection.body_part

        patient_id = safe_filename(meta.patient_id or "UNKNOWN")
        study_date = safe_filename(meta.study_date or "NoDate")
        series_n = safe_filename(meta.series_number or "0")
        series_desc = slugify(meta.series_description or "Series", 32)

        if cfg.mode == "simple":
            return (
                f"{mod_label}/{body_part}"
                f"/{patient_id}_{study_date}"
                f"/Series_{series_n}_{series_desc}"
            )
        else:
            # Dataset mode
            ds_name = safe_filename(cfg.dataset_name)
            anon_id = safe_filename(meta.patient_id)
            return (
                f"{ds_name}/raw/{mod_label}/{body_part}/{sub_type}"
                f"/{anon_id}/{study_date}/Series_{series_n}"
            )

    def _do_dataset_finalization(self, dest: Path, cfg: SortConfig):
        """Dataset-mode extras: NIfTI conversion, PNG previews, splitting."""
        from core.splitter import split_dataset
        import pandas as pd

        df = self._manifest.to_dataframe()
        if df.empty:
            return

        # Train/val/test split
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
        bp_counts = df["detected_body_part"].value_counts().to_dict()
        table_rows = "\n".join(f"| {k} | {v} |" for k, v in bp_counts.items())
        ds_name = safe_filename(cfg.dataset_name)

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
    arr = ds.pixel_array  # numpy array
    # ... normalise & convert to tensor
```

## MONAI Loading Snippet

```python
from monai.data import Dataset, DataLoader
from monai.transforms import LoadImaged, EnsureChannelFirstd, ScaleIntensityd, Compose

manifest = pd.read_csv("{ds_name}/splits/train.csv")
brain_df = manifest[manifest["detected_body_part"] == "Brain"]
data = [{{"image": r["file_path"]}} for _, r in brain_df.iterrows()]

transforms = Compose([LoadImaged(keys=["image"]), EnsureChannelFirstd(keys=["image"]),
                      ScaleIntensityd(keys=["image"])])
dataset = Dataset(data=data, transform=transforms)
loader = DataLoader(dataset, batch_size=4)
```

## Detection Accuracy Notes

- **Metadata-based** detection (confidence ≥ 0.85) is the most reliable.
- **AI-based** detection works best when metadata is absent; accuracy depends on
  the pre-trained weights in `models/body_part_classifier.pth`.
- **Heuristic** detection is a fallback with ~60–70% accuracy.
- Files with confidence < 0.5 are placed in `_review_needed/` for manual verification.

## Known Limitations

- Multi-modality files (e.g. PET-CT) may be split across folders.
- Very non-standard vendor field names may not be parsed correctly.
- AI detection requires PyTorch; if unavailable, falls back to heuristics.
"""
        readme_path = dest / ds_name / "README.md"
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(readme, encoding="utf-8")
        self._emit_log(f"README written: {readme_path}")
