"""
LocalScribe - Main Application Entry Point
Phase 2: PySide6 Desktop UI

This module initializes the PySide6 application and launches the main window.
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow


def main():
    """
    Main entry point for LocalScribe desktop application.
    """
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
