"""
Train / Val / Test splitter for dataset mode.
Splits at patient level and stratifies by body_part + modality.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import pandas as pd
from sklearn.model_selection import train_test_split

from utils.logger import get_logger

log = get_logger()


def split_dataset(
    manifest: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    output_dir: Optional[Path] = None,
) -> dict[str, pd.DataFrame]:
    """
    Split manifest into train / val / test at patient level.

    Returns a dict with keys 'train', 'val', 'test'.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        "Ratios must sum to 1.0"

    random.seed(seed)

    # Get unique patients; stratify by dominant body_part
    patient_col = "anonymized_id" if "anonymized_id" in manifest.columns else "patient_id"
    if patient_col not in manifest.columns:
        # Last-resort fallback: treat every row as its own patient
        manifest = manifest.copy()
        manifest[patient_col] = range(len(manifest))

    def _dominant(x: pd.Series) -> str:
        m = x.mode()
        return m.iloc[0] if len(m) > 0 else "Other"

    patients = manifest.groupby(patient_col)["detected_body_part"].agg(
        _dominant
    ).reset_index()
    patients.columns = [patient_col, "stratum"]

    # Guard: if too few samples for stratified split, fall back to random
    try:
        train_ps, temp_ps = train_test_split(
            patients, test_size=(1 - train_ratio), stratify=patients["stratum"],
            random_state=seed,
        )
        rel_val = val_ratio / (val_ratio + test_ratio)
        val_ps, test_ps = train_test_split(
            temp_ps, test_size=(1 - rel_val),
            stratify=temp_ps["stratum"] if len(temp_ps) >= 4 else None,
            random_state=seed,
        )
    except ValueError:
        log.warning("Stratified split failed; using random split.")
        train_ps, temp_ps = train_test_split(patients, test_size=(1 - train_ratio), random_state=seed)
        rel_val = val_ratio / (val_ratio + test_ratio)
        val_ps, test_ps = train_test_split(temp_ps, test_size=(1 - rel_val), random_state=seed)

    def assign(df: pd.DataFrame, patient_set: pd.DataFrame, split_name: str) -> pd.DataFrame:
        ids = set(patient_set[patient_col])
        subset = df[df[patient_col].isin(ids)].copy()
        subset["split_assignment"] = split_name
        return subset

    train_df = assign(manifest, train_ps, "train")
    val_df = assign(manifest, val_ps, "val")
    test_df = assign(manifest, test_ps, "test")

    log.info("Split sizes — train:%d  val:%d  test:%d",
             len(train_df), len(val_df), len(test_df))

    if output_dir:
        splits_dir = Path(output_dir) / "splits"
        splits_dir.mkdir(parents=True, exist_ok=True)
        train_df.to_csv(splits_dir / "train.csv", index=False)
        val_df.to_csv(splits_dir / "val.csv", index=False)
        test_df.to_csv(splits_dir / "test.csv", index=False)

    return {"train": train_df, "val": val_df, "test": test_df}
