"""
Debug Logger for LocalScribe
Writes debug output to both console and a log file for troubleshooting.
"""

import sys
from datetime import datetime
from pathlib import Path

class DebugLogger:
    """Singleton logger that writes to both console and file."""

    _instance = None
    _log_file = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Create log file in project root
            log_path = Path(__file__).parent.parent / "debug_flow.txt"
            cls._log_file = open(log_path, 'w', encoding='utf-8')
            cls._log_file.write(f"=== LocalScribe Debug Log ===\n")
            cls._log_file.write(f"Started: {datetime.now().isoformat()}\n")
            cls._log_file.write("=" * 60 + "\n\n")
            cls._log_file.flush()
        return cls._instance

    def log(self, message):
        """Write message to both console and file."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{timestamp}] {message}"

        # Write to console
        print(formatted)
        sys.stdout.flush()

        # Write to file
        if self._log_file:
            self._log_file.write(formatted + "\n")
            self._log_file.flush()

    def close(self):
        """Close the log file."""
        if self._log_file:
            self._log_file.write(f"\n{'=' * 60}\n")
            self._log_file.write(f"Ended: {datetime.now().isoformat()}\n")
            self._log_file.close()
            self._log_file = None

# Global instance
_logger = DebugLogger()

def debug_log(message):
    """Convenience function for debug logging."""
    _logger.log(message)

def close_debug_log():
    """Close the debug log file."""
    _logger.close()
