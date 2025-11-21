"""
LocalScribe - Main Application Entry Point
Phase 2.1: CustomTkinter UI

This module initializes the CustomTkinter application and launches the main window.
"""

import sys
import multiprocessing
import customtkinter as ctk

# CRITICAL: Import src.ai BEFORE UI framework to avoid DirectML DLL conflicts on Windows
# This pre-loads onnxruntime_genai before UI framework initializes
import src.ai  # noqa: F401

from src.ui.main_window import MainWindow

def main():
    """
    Main entry point for LocalScribe desktop application.
    """
    # Enable multiprocessing support for Windows frozen executables
    multiprocessing.freeze_support()

    # Set appearance mode (light/dark/system)
    ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
    ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

    # Create and run the application
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
