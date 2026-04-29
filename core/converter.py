"""
Converts DICOM series to NIfTI (.nii.gz) and PNG preview images.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import numpy as np

from utils.logger import get_logger

log = get_logger()


def convert_series_to_nifti(series_dir: Path, output_path: Path) -> bool:
    """
    Convert a directory of DICOM files to a NIfTI file.
    Returns True on success.
    """
    try:
        import dicom2nifti
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dicom2nifti.convert_directory(str(series_dir), str(output_path.parent), reorient=True)
        log.info("NIfTI conversion complete: %s", output_path.parent)
        return True
    except ImportError:
        log.warning("dicom2nifti not available; trying SimpleITK…")
    except Exception as exc:
        log.warning("dicom2nifti failed for %s: %s", series_dir, exc)

    # Fallback: SimpleITK
    try:
        import SimpleITK as sitk
        reader = sitk.ImageSeriesReader()
        dcm_series = reader.GetGDCMSeriesFileNames(str(series_dir))
        if not dcm_series:
            return False
        reader.SetFileNames(dcm_series)
        image = reader.Execute()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(image, str(output_path))
        log.info("NIfTI (SimpleITK) saved: %s", output_path)
        return True
    except Exception as exc:
        log.error("NIfTI conversion failed: %s", exc)
        return False


def save_png_preview(pixel_array: np.ndarray, output_path: Path) -> bool:
    """
    Save a normalised middle-slice PNG preview of the pixel array.
    """
    try:
        from PIL import Image
        arr = pixel_array.astype(np.float32)
        if arr.ndim == 3:
            mid = arr[arr.shape[0] // 2]
        else:
            mid = arr

        mn, mx = mid.min(), mid.max()
        if mx - mn > 0:
            mid = (mid - mn) / (mx - mn) * 255.0
        else:
            mid = np.zeros_like(mid)

        img = Image.fromarray(mid.astype(np.uint8)).convert("L").resize((512, 512))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))
        return True
    except Exception as exc:
        log.warning("PNG preview failed: %s", exc)
        return False
