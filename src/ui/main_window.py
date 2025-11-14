"""
LocalScribe - Main Window
Phase 2: Desktop UI Shell

Main application window with file selection, processing, and results display.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog,
    QMessageBox, QStatusBar, QMenuBar
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction
import os
from pathlib import Path

from src.ui.widgets import FileReviewTable, AIControlsWidget
from src.cleaner import DocumentCleaner
from src.ai import ModelManager


class ProcessingWorker(QThread):
    """
    Background worker thread for processing documents.
    Prevents UI freezing during long-running operations.
    """
    # Signals for communicating with main thread
    progress_updated = Signal(int, str)  # (percentage, message)
    file_processed = Signal(dict)  # result dictionary
    finished = Signal(list)  # all results
    error = Signal(str)  # error message

    def __init__(self, file_paths, jurisdiction="ny"):
        super().__init__()
        self.file_paths = file_paths
        self.jurisdiction = jurisdiction
        self.cleaner = None

    def run(self):
        """Execute document processing in background thread."""
        try:
            # Initialize cleaner
            self.cleaner = DocumentCleaner(jurisdiction=self.jurisdiction)

            results = []
            total_files = len(self.file_paths)

            for idx, file_path in enumerate(self.file_paths):
                # Update progress
                percentage = int((idx / total_files) * 100)
                filename = os.path.basename(file_path)
                self.progress_updated.emit(percentage, f"Processing {filename}...")

                # Process document with progress callback
                def progress_callback(msg):
                    self.progress_updated.emit(percentage, msg)

                result = self.cleaner.process_document(
                    file_path,
                    progress_callback=progress_callback
                )

                results.append(result)
                self.file_processed.emit(result)

            # Complete
            self.progress_updated.emit(100, "Processing complete")
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """
    Main application window for LocalScribe.

    Phase 2 Features:
    - File selection (dialog and drag-and-drop in future)
    - Document preprocessing with progress tracking
    - File Review Table showing processing results
    - Basic menu structure for future phases
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalScribe - Legal Document Processor")
        self.setMinimumSize(1000, 700)

        # State
        self.selected_files = []
        self.processing_results = []
        self.worker = None

        # AI Model Manager (Phase 3)
        self.model_manager = ModelManager()

        # Initialize UI
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Apply styling
        self._apply_styles()

    def _create_menus(self):
        """Create menu bar with File and Help menus."""
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        select_files_action = QAction("&Select Files...", self)
        select_files_action.setShortcut("Ctrl+O")
        select_files_action.triggered.connect(self.select_files)
        file_menu.addAction(select_files_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings Menu (placeholder for Phase 6)
        settings_menu = menubar.addMenu("&Settings")
        settings_action = QAction("&Preferences...", self)
        settings_action.setEnabled(False)  # Disabled for now
        settings_menu.addAction(settings_action)

        # Help Menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About LocalScribe", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create toolbar with file selection and processing controls."""
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(10, 10, 10, 10)

        # File selection button
        self.select_files_btn = QPushButton("Select Files...")
        self.select_files_btn.clicked.connect(self.select_files)
        toolbar_layout.addWidget(self.select_files_btn)

        # Spacer
        toolbar_layout.addStretch()

        # Info label
        self.files_label = QLabel("No files selected")
        toolbar_layout.addWidget(self.files_label)

        toolbar_widget.setLayout(toolbar_layout)

        # Add toolbar as a widget (not using QToolBar for more layout control)
        self.toolbar_container = toolbar_widget

    def _create_central_widget(self):
        """Create central widget with file review table and controls."""
        central_widget = QWidget()
        main_layout = QHBoxLayout()  # Horizontal layout for sidebar

        # Left side: File review and controls
        left_widget = QWidget()
        layout = QVBoxLayout()

        # Add toolbar
        layout.addWidget(self.toolbar_container)

        # Warning banner (initially hidden)
        self.warning_banner = QLabel()
        self.warning_banner.setWordWrap(True)
        self.warning_banner.setStyleSheet("""
            background-color: #fff3cd;
            color: #856404;
            padding: 10px;
            border: 1px solid #ffeaa7;
            border-radius: 4px;
        """)
        self.warning_banner.hide()
        layout.addWidget(self.warning_banner)

        # File Review Table
        self.file_table = FileReviewTable()
        self.file_table.selection_changed.connect(self.on_selection_changed)
        layout.addWidget(self.file_table)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Progress message label
        self.progress_label = QLabel()
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        # Bottom controls
        controls_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.file_table.select_all)
        self.select_all_btn.setEnabled(False)
        controls_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.file_table.deselect_all)
        self.deselect_all_btn.setEnabled(False)
        controls_layout.addWidget(self.deselect_all_btn)

        controls_layout.addStretch()

        # Phase 3: Process button for AI processing
        self.process_btn = QPushButton("Generate Summaries")
        self.process_btn.setEnabled(False)
        self.process_btn.setToolTip("Select files and load a model to begin")
        self.process_btn.clicked.connect(self.process_with_ai)
        controls_layout.addWidget(self.process_btn)

        layout.addLayout(controls_layout)

        left_widget.setLayout(layout)
        main_layout.addWidget(left_widget, stretch=3)

        # Right side: AI Controls (Phase 3)
        self.ai_controls = AIControlsWidget(self.model_manager)
        self.ai_controls.load_model_requested.connect(self.load_ai_model)
        self.ai_controls.setMaximumWidth(300)
        main_layout.addWidget(self.ai_controls, stretch=1)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def _create_status_bar(self):
        """Create status bar for messages."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _apply_styles(self):
        """Apply application-wide styles."""
        # Basic styling - can be enhanced later
        self.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
            QPushButton:disabled {
                color: #999;
                background-color: #f8f9fa;
            }
        """)

    @Slot()
    def select_files(self):
        """Open file dialog to select documents for processing."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Documents (*.pdf *.txt *.rtf);;All Files (*)")
        file_dialog.setWindowTitle("Select Legal Documents")

        if file_dialog.exec():
            selected_paths = file_dialog.selectedFiles()
            if selected_paths:
                self.selected_files = selected_paths
                self.files_label.setText(f"{len(selected_paths)} file(s) selected")
                self.status_bar.showMessage(f"Processing {len(selected_paths)} file(s)...")

                # Start processing
                self.start_processing(selected_paths)

    def start_processing(self, file_paths):
        """
        Start background processing of selected documents.

        Args:
            file_paths: List of file paths to process
        """
        # Disable controls during processing
        self.select_files_btn.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(False)

        # Show progress indicators
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.progress_label.show()

        # Clear previous results
        self.file_table.clear()
        self.processing_results = []

        # Create and start worker thread
        self.worker = ProcessingWorker(file_paths, jurisdiction="ny")
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.file_processed.connect(self.on_file_processed)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.error.connect(self.on_processing_error)
        self.worker.start()

    @Slot(int, str)
    def on_progress_updated(self, percentage, message):
        """Handle progress updates from worker thread."""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)
        self.status_bar.showMessage(message)

    @Slot(dict)
    def on_file_processed(self, result):
        """Handle individual file processing completion."""
        self.processing_results.append(result)
        self.file_table.add_result(result)

    @Slot(list)
    def on_processing_finished(self, results):
        """Handle completion of all file processing."""
        # Re-enable controls
        self.select_files_btn.setEnabled(True)
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)

        # Hide progress indicators
        self.progress_bar.hide()
        self.progress_label.hide()

        # Check for low confidence files
        low_confidence_count = sum(
            1 for r in results
            if r.get('status') == 'success' and r.get('confidence', 100) < 70
        )

        failed_count = sum(1 for r in results if r.get('status') == 'error')

        # Show warnings if needed
        if low_confidence_count > 0:
            self.warning_banner.setText(
                f"⚠ {low_confidence_count} file(s) have confidence <70% and may produce unreliable results"
            )
            self.warning_banner.show()
        else:
            self.warning_banner.hide()

        # Update status
        success_count = len(results) - failed_count
        status_msg = f"Processed {len(results)} file(s): {success_count} successful"
        if failed_count > 0:
            status_msg += f", {failed_count} failed"

        self.status_bar.showMessage(status_msg)

        # Show failure dialog if any files failed
        if failed_count > 0:
            failed_files = [
                r.get('filename', 'Unknown')
                for r in results
                if r.get('status') == 'error'
            ]
            self.show_failed_files_dialog(failed_files)

    @Slot(str)
    def on_processing_error(self, error_message):
        """Handle processing errors."""
        self.select_files_btn.setEnabled(True)
        self.progress_bar.hide()
        self.progress_label.hide()

        QMessageBox.critical(
            self,
            "Processing Error",
            f"An error occurred during processing:\n\n{error_message}"
        )
        self.status_bar.showMessage("Processing failed")

    def show_failed_files_dialog(self, failed_files):
        """Show dialog listing files that failed processing."""
        files_list = "\n".join(f"• {f}" for f in failed_files)

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Processing Warnings")
        msg_box.setText("The following files could not be processed:")
        msg_box.setDetailedText(files_list)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()

    @Slot()
    def on_selection_changed(self):
        """Handle changes in file table selection."""
        selected_count = self.file_table.get_selected_count()

        # Update process button state based on model and selection
        can_process = selected_count > 0 and self.model_manager.is_model_loaded()
        self.process_btn.setEnabled(can_process)

        if can_process:
            self.process_btn.setToolTip(f"Generate summaries for {selected_count} selected file(s)")
            self.status_bar.showMessage(f"{selected_count} file(s) selected for processing")
        elif selected_count > 0:
            self.process_btn.setToolTip("Load a model first to generate summaries")
            self.status_bar.showMessage(f"{selected_count} file(s) selected - Load a model to continue")
        else:
            self.process_btn.setToolTip("Select files and load a model to begin")
            self.status_bar.showMessage("Ready")

    @Slot(str)
    def load_ai_model(self, model_type):
        """
        Load an AI model in a background thread.

        Args:
            model_type: Either 'standard' or 'pro'
        """
        self.status_bar.showMessage(f"Loading {model_type} model... This may take a few minutes.")
        self.ai_controls.load_model_btn.setEnabled(False)
        self.ai_controls.load_model_btn.setText("Loading...")

        # TODO: Create a ModelLoadWorker thread for background loading
        # For now, load in main thread (will freeze UI temporarily)
        success = self.model_manager.load_model(model_type)

        if success:
            self.status_bar.showMessage(f"{model_type.title()} model loaded successfully!")
            QMessageBox.information(
                self,
                "Model Loaded",
                f"The {model_type} model has been loaded and is ready to use."
            )
            self.ai_controls.refresh_status()
            self.on_selection_changed()  # Update process button state
        else:
            self.status_bar.showMessage(f"Failed to load {model_type} model")
            QMessageBox.critical(
                self,
                "Model Load Failed",
                f"Failed to load the {model_type} model. Please check that the model file exists "
                f"in the models directory and try again."
            )
            self.ai_controls.refresh_status()

    @Slot()
    def process_with_ai(self):
        """Process selected files with AI to generate summaries."""
        selected_results = self.file_table.get_selected_files()

        if not selected_results:
            QMessageBox.warning(self, "No Files Selected", "Please select files to process.")
            return

        if not self.model_manager.is_model_loaded():
            QMessageBox.warning(self, "No Model Loaded", "Please load a model first.")
            return

        # Get summary settings
        summary_length = self.ai_controls.get_summary_length()

        # TODO: Implement AI processing in Phase 3
        # For now, show a placeholder message
        QMessageBox.information(
            self,
            "AI Processing",
            f"Ready to process {len(selected_results)} file(s) with {summary_length}-word summaries.\n\n"
            f"AI processing with streaming will be implemented next."
        )

    @Slot()
    def show_about(self):
        """Show About dialog."""
        about_text = """
        <h2>LocalScribe v2.0</h2>
        <p><b>100% Offline Legal Document Processor</b></p>
        <p>LocalScribe processes legal documents entirely on your computer,
        ensuring complete privacy and PII/PHI protection.</p>
        <p><i>Powered by Google Gemma 2 models</i></p>
        <hr>
        <p><b>Current Phase:</b> Phase 3 - AI Integration (In Progress)</p>
        <p><b>Status:</b> Pre-processing engine active, AI model loading enabled</p>
        """

        QMessageBox.about(self, "About LocalScribe", about_text)

    def closeEvent(self, event):
        """Handle window close event."""
        # Stop worker thread if running
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Document processing is still running. Are you sure you want to quit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
