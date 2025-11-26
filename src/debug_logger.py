"""
Debug Logger Module (Backward Compatibility Wrapper)

This module provides backward compatibility for code importing from debug_logger.
All functionality has been consolidated into src/logging_config.py.

New code should import directly from logging_config:
    from src.logging_config import debug_log, info, warning, error, Timer

Existing imports will continue to work:
    from src.debug_logger import debug_log  # Still works

See src/logging_config.py for full documentation on the unified logging system.
"""

# Re-export all logging functions from the unified module
from src.logging_config import (
    debug_log,
    debug,
    info,
    warning,
    error,
    critical,
    close_debug_log,
    Timer,
)

__all__ = [
    'debug_log',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
    'close_debug_log',
    'Timer',
]
