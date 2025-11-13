"""
Logging utility with debug mode support.
Implements verbose logging with timestamps and performance timing as per CLAUDE.md requirements.
"""

import logging
import time
from datetime import datetime
from typing import Optional
from ..config import DEBUG_MODE, LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() if DEBUG_MODE else logging.NullHandler()
    ]
)

logger = logging.getLogger('LocalScribe')


class Timer:
    """
    Context manager for timing code blocks.
    Automatically logs execution time when debug mode is enabled.

    Usage:
        with Timer("FileParsing"):
            # code to time
            pass

    Output: [DEBUG 14:32:01] FileParsing took 842 ms
    """

    def __init__(self, operation_name: str, auto_log: bool = True):
        self.operation_name = operation_name
        self.auto_log = auto_log and DEBUG_MODE
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None

    def __enter__(self):
        if DEBUG_MODE:
            debug(f"Starting {self.operation_name}...")
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

        if self.auto_log:
            # Format duration in human-readable units
            if self.duration_ms < 1000:
                duration_str = f"{self.duration_ms:.0f} ms"
            else:
                duration_str = f"{self.duration_ms / 1000:.1f} seconds"

            debug(f"{self.operation_name} took {duration_str}")

        return False  # Don't suppress exceptions

    def get_duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.duration_ms is None:
            raise ValueError("Timer has not been completed yet")
        return self.duration_ms


def debug(message: str):
    """Log debug message (only appears in debug mode)."""
    if DEBUG_MODE:
        logger.debug(message)


def info(message: str):
    """Log info message (always appears)."""
    logger.info(message)


def warning(message: str):
    """Log warning message (always appears)."""
    logger.warning(message)


def error(message: str, exc_info: bool = False):
    """
    Log error message with optional exception info.

    Args:
        message: Error message to log
        exc_info: If True, include exception traceback (only in debug mode)
    """
    logger.error(message, exc_info=exc_info and DEBUG_MODE)


def critical(message: str, exc_info: bool = True):
    """Log critical error with exception info."""
    logger.critical(message, exc_info=exc_info and DEBUG_MODE)
