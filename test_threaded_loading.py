"""
Test threaded model loading with progress dialog.

This script demonstrates that the UI remains responsive during model loading.
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt
from src.ai import ModelManager
from src.ui.workers import ModelLoadWorker
from src.ui.dialogs import ModelLoadProgressDialog


class TestWindow(QWidget):
    """Simple test window to verify threaded loading."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Threaded Model Loading Test")
        self.setMinimumWidth(400)

        self.model_manager = ModelManager()
        self.worker = None
        self.dialog = None

        layout = QVBoxLayout()

        # Info label
        info = QLabel(
            "This test demonstrates threaded model loading.\n\n"
            "Click 'Load Model' and observe:\n"
            "• Progress dialog with timer appears\n"
            "• Main window stays responsive (you can move it)\n"
            "• Timer updates every 100ms\n"
            "• Success message appears when done"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Status label
        self.status_label = QLabel("Status: No model loaded")
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        # Load button
        self.load_btn = QPushButton("Load Model")
        self.load_btn.clicked.connect(self.load_model)
        layout.addWidget(self.load_btn)

        # Test responsiveness button
        self.test_btn = QPushButton("Click Me During Loading")
        self.test_btn.clicked.connect(self.test_responsiveness)
        layout.addWidget(self.test_btn)

        self.response_label = QLabel("")
        self.response_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.response_label)

        self.setLayout(layout)

    def load_model(self):
        """Start model loading in background thread."""
        self.load_btn.setEnabled(False)
        self.status_label.setText("Status: Loading model...")
        self.response_label.setText("")

        # Create progress dialog
        self.dialog = ModelLoadProgressDialog("Standard (9B)", self)

        # Create worker
        self.worker = ModelLoadWorker(self.model_manager, 'standard')
        self.worker.success.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)

        # Start
        self.worker.start()
        self.dialog.show()

    def test_responsiveness(self):
        """Test that UI is responsive during loading."""
        self.response_label.setText("✓ UI is responsive! Button clicked.")
        self.response_label.setStyleSheet("color: #28a745; font-weight: bold;")

    def on_success(self):
        """Handle successful loading."""
        if self.dialog:
            self.dialog.finish_success()
        self.status_label.setText("Status: Model loaded successfully!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")

    def on_error(self, error_msg):
        """Handle loading error."""
        if self.dialog:
            self.dialog.finish_error(error_msg)
        self.status_label.setText(f"Status: Error - {error_msg}")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")

    def on_finished(self):
        """Clean up after loading."""
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Load Again")
        if self.worker:
            self.worker.deleteLater()
            self.worker = None


def main():
    print("=" * 70)
    print("Threaded Model Loading Test")
    print("=" * 70)
    print("\nThis test will:")
    print("1. Open a test window")
    print("2. Click 'Load Model' to start loading")
    print("3. Progress dialog will appear with timer")
    print("4. Try clicking 'Click Me During Loading' - it should work!")
    print("5. Try moving the window - it should be responsive")
    print("\nIf the window freezes, threading is NOT working.")
    print("If you can click buttons and move the window, threading IS working!")
    print("=" * 70)
    print()

    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
