"""
LocalScribe - Custom UI Widgets
Phase 2: File Review Table and other custom widgets
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QCheckBox,
    QWidget, QHBoxLayout, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import os


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
