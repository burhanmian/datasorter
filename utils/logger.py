"""
Logging utilities for DICOM Organizer.
Provides file + GUI-streamed logging.
"""
import logging
import queue
import threading
from pathlib import Path
from datetime import datetime


class QueueHandler(logging.Handler):
    """Sends log records to a thread-safe queue for GUI consumption."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord):
        self.log_queue.put(self.format(record))


_log_queue: queue.Queue = queue.Queue()
_logger_initialized = False


def get_log_queue() -> queue.Queue:
    return _log_queue


def setup_logger(log_dir: Path | None = None) -> logging.Logger:
    global _logger_initialized

    logger = logging.getLogger("dicom_organizer")
    if _logger_initialized:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    # Console handler (for development)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Queue handler (for GUI live log)
    qh = QueueHandler(_log_queue)
    qh.setLevel(logging.INFO)
    qh.setFormatter(fmt)
    logger.addHandler(qh)

    # File handler (always write to log file)
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(log_dir / f"dicom_organizer_{ts}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    _logger_initialized = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("dicom_organizer")
