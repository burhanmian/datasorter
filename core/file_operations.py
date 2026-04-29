"""
File copy / move operations with duplicate detection and checkpoint support.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional, Callable

from utils.logger import get_logger
from utils.helpers import ensure_unique_path, safe_filename

log = get_logger()

CHECKPOINT_FILE = ".checkpoint.json"


class FileOperations:
    def __init__(
        self,
        destination: Path,
        operation: str = "copy",
        preview_only: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.destination = Path(destination)
        self.operation = operation   # "copy" or "move"
        self.preview_only = preview_only
        self.progress_callback = progress_callback
        self._processed_uids: set[str] = set()
        self._checkpoint_path = self.destination / CHECKPOINT_FILE
        self._load_checkpoint()

    # ------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------
    def _load_checkpoint(self):
        if self._checkpoint_path.exists():
            try:
                data = json.loads(self._checkpoint_path.read_text())
                self._processed_uids = set(data.get("processed_uids", []))
                log.info("Resumed from checkpoint (%d already done)", len(self._processed_uids))
            except Exception:
                pass

    def _save_checkpoint(self):
        try:
            self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self._checkpoint_path.write_text(
                json.dumps({"processed_uids": list(self._processed_uids)})
            )
        except Exception as exc:
            log.debug("Checkpoint save failed: %s", exc)

    def clear_checkpoint(self):
        self._processed_uids.clear()
        if self._checkpoint_path.exists():
            self._checkpoint_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def is_duplicate(self, sop_uid: str) -> bool:
        return bool(sop_uid) and sop_uid in self._processed_uids

    def transfer_file(self, src: Path, rel_dest: Path, sop_uid: str = "") -> Optional[Path]:
        """
        Copy or move *src* to destination / *rel_dest*.
        Returns the final destination path, or None on failure.
        """
        if sop_uid and self.is_duplicate(sop_uid):
            log.debug("Skipping duplicate: %s", src.name)
            return None

        dest = self.destination / rel_dest
        dest = ensure_unique_path(dest)

        if self.preview_only:
            log.info("[PREVIEW] %s → %s", src, dest)
            return dest

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if self.operation == "move":
                shutil.move(str(src), str(dest))
            else:
                shutil.copy2(str(src), str(dest))

            if sop_uid:
                self._processed_uids.add(sop_uid)
                self._save_checkpoint()

            if self.progress_callback:
                self.progress_callback(str(dest))

            return dest
        except Exception as exc:
            log.error("File transfer failed (%s → %s): %s", src, dest, exc)
            return None

    def move_to_errors(self, src: Path, reason: str = "") -> Optional[Path]:
        errors_dir = self.destination / "_Errors"
        return self.transfer_file(src, Path("_Errors") / src.name)

    def move_to_review(self, src: Path) -> Optional[Path]:
        review_dir = self.destination / "_Review_Needed"
        return self.transfer_file(src, Path("_Review_Needed") / src.name)
