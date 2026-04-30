"""
Logging utilities for DICOM Organizer.
Provides file + GUI-streamed logging with duplicate-handler protection.
"""
from __future__ import annotations

import logging
import queue
from pathlib import Path
from datetime import datetime
from typing import Optional


class QueueHandler(logging.Handler):
    """Sends log records to a thread-safe queue for GUI consumption."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord):
        self.log_queue.put(self.format(record))


_log_queue: queue.Queue = queue.Queue()
_file_handler_added = False


def get_log_queue() -> queue.Queue:
    return _log_queue


def setup_logger(log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Configure the application logger.  Safe to call multiple times:
    - Console + queue handlers are added only once.
    - A file handler is added only once per session (first call with log_dir wins).
    """
    global _file_handler_added

    logger = logging.getLogger("dicom_organizer")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    # Determine which handler types are already attached
    existing_types = {type(h) for h in logger.handlers}

    # Console handler — added once
    if logging.StreamHandler not in existing_types:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # Queue handler — added once
    if QueueHandler not in existing_types:
        qh = QueueHandler(_log_queue)
        qh.setLevel(logging.INFO)
        qh.setFormatter(fmt)
        logger.addHandler(qh)

    # File handler — added once per session when a directory is provided
    if log_dir and not _file_handler_added:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(
            log_dir / f"dicom_organizer_{ts}.log", encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        _file_handler_added = True

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("dicom_organizer")
