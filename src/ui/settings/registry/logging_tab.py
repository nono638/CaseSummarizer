"""
Logging tab settings (level, customize, open folder, clear, retention).
"""

import logging
import os

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)

logger = logging.getLogger(__name__)


def _open_logging_dialog() -> None:
    """Open the custom log categories dialog."""
    from src.ui.logging_dialog import LoggingDialog

    LoggingDialog(parent=None)


def _open_log_folder(logs_dir) -> None:
    """Open the logs folder in the system file explorer."""
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Windows
        os.startfile(str(logs_dir))
    except AttributeError:
        # macOS/Linux fallback
        import subprocess
        import sys

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(logs_dir)])
            else:
                subprocess.run(["xdg-open", str(logs_dir)])
        except Exception as e:
            logger.warning("Could not open log folder: %s", e)


def _clear_log_file() -> None:
    """Clear the log file with confirmation."""
    from tkinter import messagebox

    from src.logging_config import clear_log_file, get_log_file_size_mb

    size_mb = get_log_file_size_mb()
    result = messagebox.askyesno(
        "Clear Log File",
        f"Clear the log file?\n\n"
        f"Current size: {size_mb:.2f} MB\n\n"
        "This will erase all logged information. "
        "A new session header will be written.",
        icon="question",
    )

    if result:
        if clear_log_file():
            messagebox.showinfo(
                "Log Cleared",
                "Log file has been cleared and reinitialized.",
            )
        else:
            messagebox.showerror(
                "Clear Failed",
                "Failed to clear the log file. The file may be in use.",
            )


def register(prefs) -> None:
    """Register the Logging tab settings."""
    from src.config import LOGS_DIR

    SettingsRegistry.register(
        SettingDefinition(
            key="logging_level",
            label="Log detail level",
            category="Logging",
            setting_type=SettingType.DROPDOWN,
            tooltip=(
                "Controls how much detail is written to the log file.\n\n"
                "• Off: No logging (saves disk space)\n"
                "• Brief: Key milestones only - document processing, results, "
                "errors. Recommended for normal use.\n"
                "• Comprehensive: Everything - timing details, algorithm internals, "
                "chunk details. Use for debugging issues.\n\n"
                "Errors and warnings are always logged regardless of this setting."
            ),
            default="brief",
            options=[
                ("Off (no logging)", "off"),
                ("Brief (recommended)", "brief"),
                ("Comprehensive (debugging)", "comprehensive"),
                ("Custom (pick categories)", "custom"),
            ],
            getter=lambda: prefs.get_logging_level(),
            setter=lambda v: prefs.set_logging_level(v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="customize_logging",
            label="Customize Categories...",
            category="Logging",
            setting_type=SettingType.BUTTON,
            tooltip=("Choose which log categories are included when using Custom logging mode."),
            default=None,
            action=_open_logging_dialog,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="open_log_folder",
            label="Open Log Folder",
            category="Logging",
            setting_type=SettingType.BUTTON,
            tooltip=(
                "Open the folder containing log files in your system file explorer.\n\n"
                "Log files:\n"
                "• caseprepd.log - Application log\n\n"
                f"Location: {LOGS_DIR}"
            ),
            default=None,
            action=lambda: _open_log_folder(LOGS_DIR),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="clear_log_file",
            label="Clear Log File",
            category="Logging",
            setting_type=SettingType.BUTTON,
            tooltip=(
                "Clear the caseprepd.log file to free disk space.\n\n"
                "The file will be emptied. Use this if the log file "
                "has grown too large.\n\n"
                "Note: This cannot be undone."
            ),
            default=None,
            action=_clear_log_file,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="log_retention_days",
            label="Auto-delete old logs",
            category="Logging",
            setting_type=SettingType.DROPDOWN,
            tooltip=(
                "Automatically delete old main_log_*.txt debug files "
                "when the application starts.\n\n"
                "These files capture stdout/stderr output for crash "
                "debugging. They accumulate over time in:\n"
                "  %APPDATA%/CasePrepd/logs/\n\n"
                "This does NOT affect the structured caseprepd.log file."
            ),
            default="90",
            options=[
                ("Keep forever", "0"),
                ("7 days", "7"),
                ("30 days", "30"),
                ("90 days (Recommended)", "90"),
            ],
            getter=lambda: str(prefs.get("log_retention_days", "90")),
            setter=lambda v: prefs.set("log_retention_days", v),
        )
    )
