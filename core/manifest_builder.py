"""
Builds and maintains the manifest CSV / JSON that records every processed file.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.logger import get_logger

log = get_logger()

COLUMNS = [
    "file_path", "relative_path", "anonymized_id", "modality",
    "detected_body_part", "detection_method", "confidence_score", "alternative_guesses",
    "sequence_or_contrast_type", "study_date", "series_uid", "series_number",
    "slice_count", "rows", "columns", "pixel_spacing_x", "pixel_spacing_y",
    "slice_thickness", "manufacturer", "model", "field_strength_or_kvp",
    "patient_age", "patient_sex", "split_assignment", "label", "notes",
]


class ManifestBuilder:
    def __init__(self):
        self._rows: list[dict] = []

    def add(self, row: dict):
        """Add one row (dict keyed by COLUMNS)."""
        full = {col: row.get(col, "") for col in COLUMNS}
        self._rows.append(full)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self._rows, columns=COLUMNS)

    def save(self, output_dir: Path, dataset_name: str = "dataset"):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        df = self.to_dataframe()

        # CSV
        csv_path = output_dir / "manifest.csv"
        df.to_csv(csv_path, index=False)

        # JSON
        json_path = output_dir / "manifest.json"
        json_path.write_text(
            json.dumps(df.to_dict(orient="records"), indent=2, default=str),
            encoding="utf-8",
        )

        # Stats
        stats = {
            "dataset_name": dataset_name,
            "created": datetime.now().isoformat(),
            "total_files": len(df),
            "modality_counts": df["modality"].value_counts().to_dict(),
            "body_part_counts": df["detected_body_part"].value_counts().to_dict(),
            "detection_method_counts": df["detection_method"].value_counts().to_dict(),
        }
        stats_path = output_dir / "dataset_stats.json"
        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

        log.info("Manifest saved: %s (%d rows)", csv_path, len(df))
        return df

    def save_html_report(self, output_dir: Path):
        """Generate a human-readable HTML report."""
        df = self.to_dataframe()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        bp_counts = df["detected_body_part"].value_counts()
        mod_counts = df["modality"].value_counts()
        method_counts = df["detection_method"].value_counts()

        rows_html = ""
        for _, row in df.head(200).iterrows():
            rows_html += "<tr>" + "".join(
                f"<td>{row.get(c, '')}</td>" for c in COLUMNS[:10]
            ) + "</tr>\n"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DICOM Organizer Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; background:#f5f5f5; }}
  h1 {{ color: #2c3e50; }}
  .stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px; }}
  .card {{ background: white; border-radius: 8px; padding: 16px; min-width: 160px;
           box-shadow: 0 2px 6px rgba(0,0,0,.1); }}
  .card h3 {{ margin: 0 0 8px; color: #555; font-size: 13px; }}
  .card p {{ margin: 0; font-size: 28px; font-weight: bold; color: #2c3e50; }}
  table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 12px; }}
  th {{ background: #2c3e50; color: white; }}
</style>
</head>
<body>
<h1>DICOM Organizer — Sorting Report</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<div class="stats">
  <div class="card"><h3>Total Files</h3><p>{len(df)}</p></div>
  {"".join(f'<div class="card"><h3>{k}</h3><p>{v}</p></div>' for k, v in bp_counts.items())}
</div>
<h2>Detection Methods</h2>
<div class="stats">
  {"".join(f'<div class="card"><h3>{k}</h3><p>{v}</p></div>' for k, v in method_counts.items())}
</div>
<h2>First 200 Files</h2>
<table>
<thead><tr>{"".join(f"<th>{c}</th>" for c in COLUMNS[:10])}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</body>
</html>"""

        report_path = output_dir / "sorting_report.html"
        report_path.write_text(html, encoding="utf-8")
        log.info("HTML report saved: %s", report_path)
        return report_path
