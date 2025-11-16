"""
LocalScribe - Main Application Entry Point
Phase 2: PySide6 Desktop UI

This module initializes the PySide6 application and launches the main window.
"""

import sys
import multiprocessing

# CRITICAL: Import src.ai BEFORE PySide6 to avoid DirectML DLL conflicts on Windows
# This pre-loads onnxruntime_genai before Qt/PySide6 initializes its DLLs
import src.ai  # noqa: F401

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow


def main():
    """
    Main entry point for LocalScribe desktop application.
    """
    # Enable multiprocessing support for Windows frozen executables
    multiprocessing.freeze_support()

    # Enable High DPI scaling for better display on modern monitors
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create the application
    app = QApplication(sys.argv)
    app.setApplicationName("LocalScribe")
    app.setOrganizationName("LocalScribe")
    app.setApplicationVersion("2.0")

    # Create and show the main window
    window = MainWindow()
    window.show()

    # Run the application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
