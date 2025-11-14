"""
LocalScribe - Custom UI Widgets
Phase 2: File Review Table and other custom widgets
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QCheckBox,
    QWidget, QHBoxLayout, QHeaderView, QVBoxLayout,
    QGroupBox, QRadioButton, QSlider, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
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
        self.standard_radio = QRadioButton("Standard (9B) - Fast, good quality")
        self.standard_radio.setChecked(True)
        self.standard_radio.toggled.connect(self._on_model_selection_changed)
        layout.addWidget(self.standard_radio)

        self.pro_radio = QRadioButton("Pro (27B) - Slower, best quality")
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
