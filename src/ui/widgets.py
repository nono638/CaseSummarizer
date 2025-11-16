"""
LocalScribe - Custom UI Widgets
Phase 2: File Review Table and other custom widgets
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QCheckBox,
    QWidget, QHBoxLayout, QHeaderView, QVBoxLayout,
    QGroupBox, QRadioButton, QSlider, QLabel, QPushButton,
    QTextEdit, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QTextCursor
import os

# Import prompt configuration
from ..prompt_config import get_prompt_config


class FileReviewTable(QTableWidget):
    """
    Custom table widget for displaying document processing results.

    Columns:
    - Checkbox (Include in processing)
    - Filename
    - Status (Ready/Warning/Failed)
    - Method (Digital/OCR)
    - Confidence (percentage)
    - Pages
    - Size
    """

    # Signal emitted when selection changes
    selection_changed = Signal()

    # Column indices
    COL_INCLUDE = 0
    COL_FILENAME = 1
    COL_STATUS = 2
    COL_METHOD = 3
    COL_CONFIDENCE = 4
    COL_PAGES = 5
    COL_SIZE = 6

    def __init__(self):
        super().__init__()

        # Configure table
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Include",
            "Filename",
            "Status",
            "Method",
            "OCR Confidence",
            "Pages",
            "Size"
        ])

        # Configure table behavior
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)  # Hide row numbers

        # Configure column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_INCLUDE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_FILENAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_METHOD, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_CONFIDENCE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_PAGES, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_SIZE, QHeaderView.ResizeToContents)

        # Enable sorting
        self.setSortingEnabled(True)

        # Store checkbox widgets for later access
        self.checkboxes = []

    def clear(self):
        """Clear all rows from the table."""
        self.setRowCount(0)
        self.checkboxes = []

    def add_result(self, result):
        """
        Add a processing result to the table.

        Args:
            result: Dictionary containing processing result with keys:
                - filename: str
                - status: 'success', 'warning', or 'error'
                - method: 'digital', 'ocr', or 'direct_read'
                - confidence: int (0-100)
                - page_count: int
                - file_size: int (bytes)
                - error: str (optional, for errors)
        """
        row = self.rowCount()
        self.insertRow(row)

        # Extract data with defaults
        filename = result.get('filename', 'Unknown')
        status = result.get('status', 'error')
        method = result.get('method', 'unknown')
        confidence = result.get('confidence', 0)
        page_count = result.get('page_count', 0)
        file_size = result.get('file_size', 0)
        error = result.get('error', '')

        # Column 0: Include checkbox
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setAlignment(Qt.AlignCenter)

        checkbox = QCheckBox()

        # Auto-check files with confidence >= 70% and success status
        if status == 'success' and confidence >= 70:
            checkbox.setChecked(True)
        else:
            checkbox.setChecked(False)

        # Disable checkbox for failed files
        if status == 'error':
            checkbox.setEnabled(False)

        checkbox.stateChanged.connect(self._on_checkbox_changed)
        checkbox_layout.addWidget(checkbox)
        checkbox_widget.setLayout(checkbox_layout)

        self.setCellWidget(row, self.COL_INCLUDE, checkbox_widget)
        self.checkboxes.append(checkbox)

        # Column 1: Filename
        filename_item = QTableWidgetItem(filename)
        filename_item.setToolTip(result.get('file_path', filename))
        self.setItem(row, self.COL_FILENAME, filename_item)

        # Column 2: Status with icon
        status_text, status_color = self._get_status_display(status, confidence)
        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(QColor(status_color))

        if error:
            status_item.setToolTip(error)

        self.setItem(row, self.COL_STATUS, status_item)

        # Column 3: Method
        method_display = self._get_method_display(method)
        method_item = QTableWidgetItem(method_display)
        self.setItem(row, self.COL_METHOD, method_item)

        # Column 4: Confidence
        if status == 'error':
            confidence_item = QTableWidgetItem("—")
        else:
            confidence_item = QTableWidgetItem(f"{confidence}%")

            # Color code by confidence level
            if confidence >= 90:
                confidence_item.setForeground(QColor("#28a745"))  # Green
            elif confidence >= 70:
                confidence_item.setForeground(QColor("#ffc107"))  # Yellow
            else:
                confidence_item.setForeground(QColor("#dc3545"))  # Red

        # Store numeric value for sorting
        confidence_item.setData(Qt.UserRole, confidence)
        self.setItem(row, self.COL_CONFIDENCE, confidence_item)

        # Column 5: Pages
        if status == 'error' or page_count == 0:
            pages_item = QTableWidgetItem("—")
            pages_item.setData(Qt.UserRole, 0)
        else:
            pages_item = QTableWidgetItem(str(page_count))
            pages_item.setData(Qt.UserRole, page_count)

        self.setItem(row, self.COL_PAGES, pages_item)

        # Column 6: Size
        if status == 'error':
            size_item = QTableWidgetItem("—")
            size_item.setData(Qt.UserRole, 0)
        else:
            size_display = self._format_file_size(file_size)
            size_item = QTableWidgetItem(size_display)
            size_item.setData(Qt.UserRole, file_size)

        self.setItem(row, self.COL_SIZE, size_item)

    def _get_status_display(self, status, confidence):
        """
        Get display text and color for status.

        Returns:
            tuple: (status_text, color)
        """
        if status == 'error':
            return ("✗ Failed", "#dc3545")  # Red
        elif status == 'success':
            if confidence >= 70:
                return ("✓ Ready", "#28a745")  # Green
            else:
                return ("⚠ Low Quality", "#ffc107")  # Yellow
        else:
            return ("⚠ Warning", "#ffc107")  # Yellow

    def _get_method_display(self, method):
        """Get display text for extraction method."""
        method_map = {
            'digital': 'Digital',
            'ocr': 'OCR',
            'direct_read': 'Text File',
            'unknown': 'Unknown'
        }
        return method_map.get(method, method.capitalize())

    def _format_file_size(self, size_bytes):
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            str: Formatted size (e.g., "2.3 MB", "856 KB")
        """
        if size_bytes == 0:
            return "0 B"

        units = ['B', 'KB', 'MB', 'GB']
        size = float(size_bytes)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        # Format with appropriate precision
        if size >= 100:
            return f"{size:.0f} {units[unit_index]}"
        elif size >= 10:
            return f"{size:.1f} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"

    def _on_checkbox_changed(self):
        """Handle checkbox state change."""
        self.selection_changed.emit()

    def select_all(self):
        """Check all enabled checkboxes."""
        for checkbox in self.checkboxes:
            if checkbox.isEnabled():
                checkbox.setChecked(True)

    def deselect_all(self):
        """Uncheck all checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)

    def get_selected_count(self):
        """
        Get count of selected files.

        Returns:
            int: Number of checked checkboxes
        """
        return sum(1 for cb in self.checkboxes if cb.isChecked())

    def get_selected_files(self):
        """
        Get list of selected file paths.

        Returns:
            list: File paths for checked rows
        """
        selected = []
        for row, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                # Get filename from table
                filename_item = self.item(row, self.COL_FILENAME)
                if filename_item:
                    # Get full path from tooltip
                    file_path = filename_item.toolTip()
                    selected.append(file_path)

        return selected


class StatusIndicator(QWidget):
    """
    Custom widget for displaying status with color indicator.

    Used for showing processing status (Ready, Warning, Failed).
    """

    def __init__(self, status, message):
        super().__init__()
        # TODO: Implement if needed for more complex status displays
        pass


class AIControlsWidget(QGroupBox):
    """
    AI Controls panel for model selection and summary settings.

    Phase 3 Features:
    - Model selection (Standard 9B vs Pro 27B)
    - Summary length slider (100-500 words)
    - Model status indicator
    - Load/unload model buttons
    """

    # Signals
    model_changed = Signal(str)  # Emits 'standard' or 'pro'
    summary_length_changed = Signal(int)  # Emits word count
    load_model_requested = Signal(str)  # Emits model type to load

    def __init__(self, model_manager=None):
        super().__init__("AI Settings")
        self.model_manager = model_manager
        self.prompt_config = get_prompt_config()
        self._init_ui()
        self._update_model_status()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()

        # Model Selection Section
        model_label = QLabel("<b>Model Selection:</b>")
        layout.addWidget(model_label)

        # Radio buttons for model selection
        self.standard_radio = QRadioButton("Standard (Phi-3 3.8B) - CPU-optimized")
        self.standard_radio.setChecked(True)
        self.standard_radio.setToolTip(
            "Phi-3 Mini 3.8B: Fast on CPU (30-90 sec), good quality\n"
            "Recommended for most users"
        )
        self.standard_radio.toggled.connect(self._on_model_selection_changed)
        layout.addWidget(self.standard_radio)

        self.pro_radio = QRadioButton("Pro (Gemma 2 9B) - GPU recommended")
        self.pro_radio.setToolTip(
            "Gemma 2 9B: Best quality but slow on CPU (5-10 min)\n"
            "Recommended only for GPU users"
        )
        self.pro_radio.toggled.connect(self._on_model_selection_changed)
        layout.addWidget(self.pro_radio)

        # Model status indicator
        self.model_status_label = QLabel()
        self.model_status_label.setWordWrap(True)
        layout.addWidget(self.model_status_label)

        # Load model button
        self.load_model_btn = QPushButton("Load Model")
        self.load_model_btn.clicked.connect(self._on_load_model_clicked)
        layout.addWidget(self.load_model_btn)

        # Separator
        layout.addSpacing(15)

        # Summary Length Section
        length_label = QLabel("<b>Summary Length (Approximate):</b>")
        layout.addWidget(length_label)

        # Get configuration values
        min_words = self.prompt_config.min_summary_words
        max_words = self.prompt_config.max_summary_words
        default_words = self.prompt_config.default_summary_words
        increment = self.prompt_config.slider_increment

        # Slider for summary length
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel(str(min_words)))

        self.length_slider = QSlider(Qt.Horizontal)
        self.length_slider.setMinimum(min_words)
        self.length_slider.setMaximum(max_words)
        self.length_slider.setValue(default_words)
        self.length_slider.setTickPosition(QSlider.TicksBelow)
        self.length_slider.setTickInterval(increment)
        self.length_slider.setSingleStep(increment)  # Arrow keys move by increment
        self.length_slider.setPageStep(increment)    # Page up/down move by increment
        self.length_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.length_slider)

        slider_layout.addWidget(QLabel(str(max_words)))
        layout.addLayout(slider_layout)

        # Current value label with range indication
        tolerance = self.prompt_config.word_count_tolerance
        min_range = default_words - tolerance
        max_range = default_words + tolerance
        self.length_value_label = QLabel(f"{default_words} words ({min_range}-{max_range})")
        self.length_value_label.setAlignment(Qt.AlignCenter)
        self.length_value_label.setToolTip(
            f"Target: {default_words} words. Model will generate between "
            f"{min_range} and {max_range} words."
        )
        layout.addWidget(self.length_value_label)

        # Add stretch to push everything to top
        layout.addStretch()

        self.setLayout(layout)

    def _on_model_selection_changed(self):
        """Handle model selection change."""
        model_type = 'standard' if self.standard_radio.isChecked() else 'pro'
        self.model_changed.emit(model_type)
        self._update_model_status()

    def _on_slider_changed(self, value):
        """Handle slider value change and snap to increment."""
        increment = self.prompt_config.slider_increment

        # Snap to nearest increment
        snapped_value = round(value / increment) * increment

        # Update slider if value was adjusted (prevents infinite loop by checking if different)
        if snapped_value != value:
            self.length_slider.blockSignals(True)
            self.length_slider.setValue(snapped_value)
            self.length_slider.blockSignals(False)
            value = snapped_value

        # Calculate and display range
        tolerance = self.prompt_config.word_count_tolerance
        min_range = value - tolerance
        max_range = value + tolerance

        self.length_value_label.setText(f"{value} words ({min_range}-{max_range})")
        self.length_value_label.setToolTip(
            f"Target: {value} words. Model will generate between "
            f"{min_range} and {max_range} words."
        )

        self.summary_length_changed.emit(value)

    def _on_load_model_clicked(self):
        """Handle load model button click."""
        model_type = 'standard' if self.standard_radio.isChecked() else 'pro'
        self.load_model_requested.emit(model_type)

    def _update_model_status(self):
        """Update the model status label based on current state."""
        if self.model_manager is None:
            self.model_status_label.setText("Status: No model manager")
            return

        # Get available models
        models = self.model_manager.get_available_models()
        current_model = 'standard' if self.standard_radio.isChecked() else 'pro'
        model_info = models[current_model]

        # Check if selected model is available
        if not model_info['available']:
            self.model_status_label.setText(
                f"<font color='#d9534f'>Status: Model not downloaded "
                f"({model_info['size_gb']} GB required)</font>"
            )
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setToolTip("Model file not found. Download required.")
        elif self.model_manager.is_model_loaded() and self.model_manager.current_model_name == current_model:
            self.model_status_label.setText(
                f"<font color='#5cb85c'>Status: {model_info['name']} loaded and ready</font>"
            )
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setText("Model Loaded")
        else:
            self.model_status_label.setText(
                f"<font color='#f0ad4e'>Status: {model_info['name']} available "
                f"({model_info['size_gb']} GB)</font>"
            )
            self.load_model_btn.setEnabled(True)
            self.load_model_btn.setText("Load Model")
            self.load_model_btn.setToolTip(f"Load the {model_info['name']} model into memory")

    def get_selected_model(self) -> str:
        """Get the currently selected model type."""
        return 'standard' if self.standard_radio.isChecked() else 'pro'

    def get_summary_length(self) -> int:
        """Get the current summary length setting."""
        return self.length_slider.value()

    def refresh_status(self):
        """Refresh the model status display."""
        self._update_model_status()


class SummaryResultsWidget(QGroupBox):
    """
    Widget to display AI-generated summary with streaming support.

    Features:
    - Real-time streaming text display
    - Word count and timing statistics
    - Save to file functionality
    - Copy to clipboard
    - Editable text area for post-generation refinement
    """

    # Signals
    save_requested = Signal(str)  # Summary text to save
    cancel_requested = Signal()  # User wants to cancel generation

    def __init__(self, parent=None):
        super().__init__("Case Summary", parent)
        self._generation_start_time = None
        self._timer = None
        self._setup_ui()

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Statistics bar
        stats_layout = QHBoxLayout()

        self.word_count_label = QLabel("Words: 0")
        self.word_count_label.setStyleSheet("color: #666; font-size: 11px;")

        self.last_updated_label = QLabel("")  # Hidden by default
        self.last_updated_label.setStyleSheet("color: #16a34a; font-size: 11px; font-style: italic;")
        self.last_updated_label.setVisible(False)

        self.gen_time_label = QLabel("Generation time: --")
        self.gen_time_label.setStyleSheet("color: #666; font-size: 11px;")

        stats_layout.addWidget(self.word_count_label)
        stats_layout.addWidget(self.last_updated_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.gen_time_label)

        layout.addLayout(stats_layout)

        # Progress section (hidden by default)
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(0, 5, 0, 5)

        # Top row: Status message and cancel button
        progress_top_layout = QHBoxLayout()

        # Status message with timer
        self.progress_status = QLabel("Generating 200-word summary...")
        self.progress_status.setStyleSheet("color: #2563eb; font-size: 12px; font-weight: bold;")

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMaximumWidth(80)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)

        progress_top_layout.addWidget(self.progress_status)
        progress_top_layout.addStretch()
        progress_top_layout.addWidget(self.cancel_btn)

        # Progress bar (indeterminate/pulsing)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setTextVisible(False)

        progress_layout.addLayout(progress_top_layout)
        progress_layout.addWidget(self.progress_bar)
        self.progress_widget.setLayout(progress_layout)
        self.progress_widget.hide()  # Hidden by default

        layout.addWidget(self.progress_widget)

        # Summary text area (editable)
        self.summary_text = QTextEdit()
        self.summary_text.setPlaceholderText(
            "Generated summary will appear here...\n\n"
            "Select files, load a model, and click 'Generate Summaries' to begin."
        )
        self.summary_text.setMinimumHeight(200)

        # Set a readable font
        from PySide6.QtGui import QFont
        font = QFont("Segoe UI", 10)
        self.summary_text.setFont(font)

        layout.addWidget(self.summary_text)

        # Action buttons
        button_layout = QHBoxLayout()

        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        self.copy_btn.setEnabled(False)

        self.save_btn = QPushButton("Save to File...")
        self.save_btn.clicked.connect(self._save_to_file)
        self.save_btn.setEnabled(False)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_summary)
        self.clear_btn.setEnabled(False)

        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def append_token(self, token: str):
        """
        Append a token to the summary (for streaming display).

        Args:
            token: Text token from the AI model (may be batched)
        """
        from src.debug_logger import debug_log
        from datetime import datetime

        # Debug: Log first few tokens to verify method is being called
        current_text = self.summary_text.toPlainText()
        if len(current_text) < 100:
            debug_log(f"[GUI append_token] Token batch received: '{token[:50]}...' (current length: {len(current_text)})")

        # Insert the token at the end
        # Note: We use insertPlainText instead of cursor manipulation
        # because it's more reliable in Qt for streaming text
        self.summary_text.moveCursor(QTextCursor.MoveOperation.End)
        self.summary_text.insertPlainText(token)

        # Update word count
        self._update_word_count()

        # Update "last updated" timestamp to prove updates are happening
        now = datetime.now()
        self.last_updated_label.setText(f"Updated: {now.strftime('%H:%M:%S')}")
        self.last_updated_label.setVisible(True)

        # Auto-scroll to show new content
        self.summary_text.ensureCursorVisible()

    def set_summary(self, summary: str):
        """
        Set the complete summary text (for non-streaming display).

        Args:
            summary: Complete summary text
        """
        self.summary_text.setPlainText(summary)
        self._update_word_count()
        self._enable_buttons()

    def clear_summary(self):
        """Clear the summary text area."""
        self.summary_text.clear()
        self.word_count_label.setText("Words: 0")
        self.gen_time_label.setText("Generation time: --")
        self.last_updated_label.setVisible(False)
        self._disable_buttons()
        self.hide_progress()

    def start_generation(self, target_words: int):
        """
        Start showing generation progress.

        Args:
            target_words: Target summary length in words
        """
        import time
        self._generation_start_time = time.time()

        # Hide last updated timestamp from previous generation
        self.last_updated_label.setVisible(False)

        # Update status message
        self.progress_status.setText(f"Generating {target_words}-word summary... (0:00)")

        # Show progress widget
        self.progress_widget.show()

        # Start timer to update elapsed time
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._update_progress_timer)

        self._timer.start(100)  # Update every 100ms

    def hide_progress(self):
        """Hide the progress indicator."""
        if self._timer:
            self._timer.stop()

        self.progress_widget.hide()
        self._generation_start_time = None

    def _update_progress_timer(self):
        """Update the elapsed time display in the progress status."""
        if self._generation_start_time is None:
            return

        import time
        elapsed = time.time() - self._generation_start_time

        # Format time as M:SS or H:MM:SS
        if elapsed < 60:
            time_str = f"0:{int(elapsed):02d}"
        elif elapsed < 3600:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            time_str = f"{minutes}:{seconds:02d}"
        else:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"{hours}:{minutes:02d}:{seconds:02d}"

        # Get current word count
        word_count = len(self.summary_text.toPlainText().split())

        # Update status with timer and word count
        # Extract target words from current status (if it exists)
        current_status = self.progress_status.text()
        if "Generating" in current_status and "-word" in current_status:
            # Extract target number
            import re
            match = re.search(r'(\d+)-word', current_status)
            if match:
                target = match.group(1)
                self.progress_status.setText(
                    f"Generating {target}-word summary... ({time_str} elapsed, {word_count} words so far)"
                )
        else:
            self.progress_status.setText(
                f"Generating summary... ({time_str} elapsed, {word_count} words so far)"
            )

    def set_generation_time(self, seconds: float):
        """
        Display the summary generation time.

        Args:
            seconds: Generation time in seconds
        """
        if seconds < 60:
            time_str = f"{seconds:.1f} seconds"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            time_str = f"{minutes}m {remaining_seconds:.0f}s"

        self.gen_time_label.setText(f"Generation time: {time_str}")

    def get_summary(self) -> str:
        """Get the current summary text."""
        return self.summary_text.toPlainText()

    def _update_word_count(self):
        """Update the word count display."""
        text = self.summary_text.toPlainText()
        word_count = len(text.split()) if text.strip() else 0
        self.word_count_label.setText(f"Words: {word_count}")

        # Enable buttons if there's content
        if word_count > 0:
            self._enable_buttons()

    def _enable_buttons(self):
        """Enable action buttons."""
        self.copy_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    def _disable_buttons(self):
        """Disable action buttons."""
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

    def _copy_to_clipboard(self):
        """Copy summary to system clipboard."""
        from PySide6.QtWidgets import QApplication

        summary = self.get_summary()
        if summary:
            clipboard = QApplication.clipboard()
            clipboard.setText(summary)

            # Show brief confirmation in status (parent should connect to this)
            # For now, just enable the button feedback
            original_text = self.copy_btn.text()
            self.copy_btn.setText("Copied!")
            self.copy_btn.setEnabled(False)

            # Reset button after 1 second
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, lambda: self._reset_copy_button(original_text))

    def _reset_copy_button(self, original_text: str):
        """Reset the copy button text."""
        self.copy_btn.setText(original_text)
        self.copy_btn.setEnabled(True)

    def _save_to_file(self):
        """Emit signal to save summary to file."""
        summary = self.get_summary()
        if summary:
            self.save_requested.emit(summary)

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        # Emit signal to parent to stop generation
        self.cancel_requested.emit()

        # Disable cancel button to prevent multiple clicks
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        self.progress_status.setText("Cancelling generation...")
