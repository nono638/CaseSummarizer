"""
LocalScribe - Custom Dialogs
Progress dialogs and other modal windows.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
import time


class ModelLoadProgressDialog(QDialog):
    """
    Progress dialog for model loading with elapsed time display.

    Since model loading doesn't provide progress callbacks, we show
    an indeterminate progress bar and a timer so users can see
    that something is happening and track typical load times.

    Signals:
        cancelled: Emitted if user clicks cancel (future enhancement)
    """

    cancelled = Signal()

    def __init__(self, model_name, parent=None):
        """
        Initialize the dialog.

        Args:
            model_name: Name of the model being loaded (e.g., "Standard (9B)")
            parent: Parent widget
        """
        super().__init__(parent)
        self.model_name = model_name
        self.start_time = time.time()

        # Make dialog modal and disable close button
        self.setModal(True)
        self.setWindowTitle("Loading Model")
        self.setMinimumWidth(400)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowTitleHint |
            Qt.CustomizeWindowHint  # Remove close button
        )

        self._init_ui()
        self._start_timer()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title label
        title_label = QLabel(f"Loading {self.model_name} Model")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Info label
        info_label = QLabel(
            "This may take 30-60 seconds depending on your hardware."
        )
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        # Indeterminate progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Timer label
        self.timer_label = QLabel("Elapsed time: 0.0 seconds")
        self.timer_label.setAlignment(Qt.AlignCenter)
        timer_font = QFont()
        timer_font.setPointSize(10)
        self.timer_label.setFont(timer_font)
        layout.addWidget(self.timer_label)

        # Status label (for optional updates)
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        # Future: Add cancel button
        # For now, model loading can't be safely cancelled mid-operation
        # button_layout = QHBoxLayout()
        # cancel_btn = QPushButton("Cancel")
        # cancel_btn.clicked.connect(self._on_cancel)
        # button_layout.addStretch()
        # button_layout.addWidget(cancel_btn)
        # layout.addLayout(button_layout)

        layout.addStretch()
        self.setLayout(layout)

    def _start_timer(self):
        """Start the elapsed time timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)
        self.timer.start(100)  # Update every 100ms

    def _update_timer(self):
        """Update the elapsed time display."""
        elapsed = time.time() - self.start_time
        self.timer_label.setText(f"Elapsed time: {elapsed:.1f} seconds")

    def set_status(self, status_text):
        """
        Update the status message.

        Args:
            status_text: New status text to display
        """
        self.status_label.setText(status_text)

    def update_elapsed_time(self, elapsed_seconds):
        """
        Update the elapsed time display.

        This is called by the worker thread's progress signal
        to keep the UI updated during model loading.

        Args:
            elapsed_seconds: Elapsed time as a float in seconds
        """
        self.timer_label.setText(f"Elapsed time: {elapsed_seconds:.1f} seconds")

    def _on_cancel(self):
        """Handle cancel button click (future enhancement)."""
        self.cancelled.emit()
        # Note: Actual cancellation of model loading requires
        # modifications to llama-cpp-python or loading process

    def closeEvent(self, event):
        """Prevent closing the dialog with X button."""
        # Only allow closing after completion (will be handled by accept/reject)
        event.ignore()

    def finish_success(self):
        """Mark loading as complete and close dialog."""
        self.timer.stop()
        elapsed = time.time() - self.start_time
        self.timer_label.setText(f"Completed in {elapsed:.1f} seconds")
        self.status_label.setText("Model loaded successfully!")
        self.status_label.setStyleSheet("color: #28a745;")  # Green
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)

        # Auto-close after a brief delay to show success
        QTimer.singleShot(500, self.accept)

    def finish_error(self, error_msg):
        """
        Mark loading as failed and close dialog.

        Args:
            error_msg: Error message to display
        """
        self.timer.stop()
        elapsed = time.time() - self.start_time
        self.timer_label.setText(f"Failed after {elapsed:.1f} seconds")
        self.status_label.setText(f"Error: {error_msg}")
        self.status_label.setStyleSheet("color: #dc3545;")  # Red
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # Auto-close after a delay to show error
        QTimer.singleShot(2000, self.reject)


class SimpleProgressDialog(QDialog):
    """
    Simple progress dialog with percentage bar and message.

    Used for operations that provide progress updates (like document processing).
    """

    def __init__(self, title, parent=None):
        """
        Initialize the dialog.

        Args:
            title: Dialog window title
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Message label
        self.message_label = QLabel("Starting...")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def update_progress(self, percentage, message):
        """
        Update progress display.

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        self.progress_bar.setValue(percentage)
        self.message_label.setText(message)
