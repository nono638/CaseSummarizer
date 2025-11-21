"""
LocalScribe - Main Window
Phase 2: Desktop UI Shell

Main application window with file selection, processing, and results display.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog,
    QMessageBox, QStatusBar, QMenuBar, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction
import os
import sys
import platform
import csv # New: For CSV writing
from datetime import datetime # Already imported, but noting its relevance
from pathlib import Path

from src.ui.widgets import FileReviewTable, AIControlsWidget, SummaryResultsWidget
from src.ui.workers import ProcessingWorker, ModelLoadWorker, AIWorker, AIWorkerProcess
from src.ui.dialogs import ModelLoadProgressDialog
from src.cleaner import DocumentCleaner
from src.ai import ModelManager
from src.debug_logger import debug_log
from src.vocabulary_extractor import VocabularyExtractor # New: For vocabulary extraction
from src.config import LEGAL_EXCLUDE_LIST_PATH, MEDICAL_TERMS_LIST_PATH # New: For vocabulary extractor config


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
        self.model_load_worker = None
        self.model_load_dialog = None
        self.ai_worker = None # Single AI worker for meta-summary or initial phase
        self.individual_ai_workers = [] # List for individual document summaries

        # AI Model Manager (Phase 3)
        self.model_manager = ModelManager()

        # Initialize UI
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Apply styling
        self._apply_styles()

        # Check Ollama service on startup
        self._check_ollama_service()

    def _create_ai_worker(self, model_manager, processing_results, summary_length, preset_id):
        """
        Create the appropriate AI worker for the current platform.

        On Windows, ONNX Runtime has known issues with multiprocessing DLL reinitialization.
        This method detects the platform and uses the thread-based worker on Windows,
        or the multiprocessing-based worker on other platforms.

        Args:
            model_manager: The ModelManager instance
            processing_results: List of processing result dicts
            summary_length: Target summary length in words
            preset_id: Prompt template preset to use

        Returns:
            Either AIWorker (thread-based) or AIWorkerProcess (multiprocessing-based)
        """
        is_windows = sys.platform == 'win32' or platform.system() == 'Windows'

        if is_windows:
            # On Windows, use thread-based worker to avoid ONNX Runtime multiprocessing DLL issues
            # (WinError 1114: DLL initialization routine failed)
            # See: https://github.com/microsoft/onnxruntime-genai/issues/...
            from src.debug_logger import debug_log
            debug_log("\n[MAIN WINDOW] Windows detected - using thread-based AI worker to avoid DLL issues")
            return AIWorker(
                model_manager=model_manager,
                processing_results=processing_results,
                summary_length=summary_length,
                preset_id=preset_id
            )
        else:
            # On non-Windows platforms (Linux, macOS), use multiprocessing for better performance
            # since ONNX Runtime DLL issues don't apply
            from src.debug_logger import debug_log
            debug_log("\n[MAIN WINDOW] Non-Windows platform detected - using multiprocessing AI worker")
            return AIWorkerProcess(
                model_manager=model_manager,
                processing_results=processing_results,
                summary_length=summary_length,
                preset_id=preset_id
            )

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

        generate_summaries_action = QAction("&Generate Summaries", self)
        generate_summaries_action.setShortcut("Ctrl+G")
        generate_summaries_action.triggered.connect(self.process_with_ai)
        file_menu.addAction(generate_summaries_action)

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
        layout.addWidget(self.file_table, stretch=2)

        # Summary Results Widget (Phase 3)
        self.summary_results = SummaryResultsWidget()
        self.summary_results.save_requested.connect(self.save_summary)
        self.summary_results.cancel_requested.connect(self.cancel_ai_generation)
        layout.addWidget(self.summary_results, stretch=1)

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

        # New: Generate Vocabulary Checkbox
        self.generate_vocab_checkbox = QCheckBox("Generate Vocabulary List (CSV)")
        self.generate_vocab_checkbox.setToolTip("Extract unusual terms, proper nouns, medical terms, and acronyms into a CSV file.")
        controls_layout.addWidget(self.generate_vocab_checkbox)

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

        # Right side: AI Controls (Phase 3 - Ollama integration)
        self.ai_controls = AIControlsWidget(self.model_manager)
        # Connect Ollama-specific signals
        self.ai_controls.pull_model_requested.connect(self.pull_ai_model)
        self.ai_controls.model_changed.connect(self.on_model_changed)
        self.ai_controls.set_default_requested.connect(self.save_default_prompt)
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

        # IMPORTANT: Emit selection change signal to update button state
        # This ensures the "Generate Summary" button is enabled immediately
        # for any files that were auto-checked during processing
        self.file_table.selection_changed.emit()

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
    def pull_ai_model(self, model_name: str):
        """
        Pull/download a new Ollama model.

        Args:
            model_name: Ollama model name (e.g., 'qwen2.5:7b-instruct')
        """
        self.status_bar.showMessage(f"Pulling model: {model_name}... (this may take several minutes)")

        try:
            # Call Ollama API to pull model
            # Note: This is a blocking call, but Ollama runs as a separate service
            self.model_manager.load_model(model_name)

            self.status_bar.showMessage(f"Model {model_name} pulled successfully!", 5000)

            # Update UI
            self.ai_controls.pull_model_complete()
            self.ai_controls.refresh_status()

        except Exception as e:
            self.status_bar.showMessage(f"Failed to pull model: {str(e)}")
            QMessageBox.critical(
                self,
                "Model Pull Failed",
                f"Could not pull model '{model_name}':\n\n{str(e)}\n\n"
                f"Make sure Ollama service is running and the model name is correct."
            )
            self.ai_controls.pull_model_complete()

    def on_model_changed(self, model_name: str):
        """
        Handle model selection change from dropdown.

        Args:
            model_name: Selected Ollama model name
        """
        self.status_bar.showMessage(f"Selected model: {model_name}")
        # Model is already available (from get_available_models), just refresh status
        self.ai_controls.refresh_status()

    def load_ai_model(self, model_type):
        """
        Load an AI model in a background thread with progress dialog.

        Args:
            model_type: Either 'standard' or 'pro'
        """
        # Get model info for display name
        models = self.model_manager.get_available_models()
        model_info = models.get(model_type, {})
        model_display_name = model_info.get('name', model_type.title())

        # Disable the load button
        self.ai_controls.load_model_btn.setEnabled(False)
        self.ai_controls.load_model_btn.setText("Loading...")

        # Create progress dialog
        self.model_load_dialog = ModelLoadProgressDialog(model_display_name, self)

        # Create worker thread
        self.model_load_worker = ModelLoadWorker(self.model_manager, model_type)

        # Connect signals
        self.model_load_worker.progress.connect(self.model_load_dialog.update_elapsed_time)
        self.model_load_worker.success.connect(self._on_model_load_success)
        self.model_load_worker.error.connect(self._on_model_load_error)
        self.model_load_worker.finished.connect(self._on_model_load_finished)

        # Start loading
        self.status_bar.showMessage(f"Loading {model_display_name}...")
        self.model_load_worker.start()

        # FIXED: Use exec() to enter the dialog's event loop
        # This allows the dialog's timer to fire and worker signals to be processed
        # The dialog will be closed by finish_success() or finish_error()
        self.model_load_dialog.exec()

    def _on_model_load_success(self):
        """Handle successful model loading."""
        if self.model_load_dialog:
            self.model_load_dialog.finish_success()

        model_name = self.model_manager.current_model_name
        self.status_bar.showMessage(f"{model_name.title()} model loaded successfully!", 5000)

        # Update UI - green status indicator shows model is ready
        self.ai_controls.refresh_status()
        self.on_selection_changed()  # Update process button state

        # Populate prompt dropdown with available presets
        self._populate_prompt_dropdown()

    def _on_model_load_error(self, error_msg):
        """Handle model loading error."""
        if self.model_load_dialog:
            self.model_load_dialog.finish_error(error_msg)

        self.status_bar.showMessage(f"Failed to load model")

        # Show error message
        QMessageBox.critical(
            self,
            "Model Load Failed",
            f"Failed to load the model:\n\n{error_msg}\n\n"
            f"Please check that the model file exists in the models directory and try again."
        )

        # Update UI
        self.ai_controls.refresh_status()

    def _on_model_load_finished(self):
        """Clean up after model loading completes (success or failure)."""
        # Clean up worker
        if self.model_load_worker:
            self.model_load_worker.deleteLater()
            self.model_load_worker = None

        # Dialog will close itself via finish_success/finish_error

    def _populate_prompt_dropdown(self):
        """Populate the prompt dropdown with available presets for the loaded model."""
        from src.prompt_template_manager import PromptTemplateManager
        from src.user_preferences import get_user_preferences
        from src.config import PROMPTS_DIR

        # Get the model identifier (hardcoded for now, will be made dynamic)
        model_id = "phi-3-mini"

        # Initialize managers
        template_manager = PromptTemplateManager(PROMPTS_DIR)
        prefs_manager = get_user_preferences()

        # Get user's preferred default prompt for this model
        user_preference = prefs_manager.get_default_prompt(model_id)

        # Get best default preset (considering user preference)
        default_preset_id = template_manager.get_best_default_preset(model_id, user_preference)

        # Get available presets
        presets = template_manager.get_available_presets(model_id)

        # Populate the dropdown
        self.ai_controls.populate_prompts(model_id, presets, default_preset_id)

    def save_default_prompt(self, model_name: str, preset_id: str):
        """
        Save the user's preferred default prompt for a model.

        Args:
            model_name: Name of the model (e.g., 'phi-3-mini')
            preset_id: Preset identifier (e.g., 'factual-summary')
        """
        from src.user_preferences import get_user_preferences

        prefs_manager = get_user_preferences()
        prefs_manager.set_default_prompt(model_name, preset_id)

        # Show confirmation in status bar
        self.status_bar.showMessage(f"Saved '{preset_id}' as default prompt for {model_name}", 3000)

    @Slot()
    def process_with_ai(self):
        """Process selected files with AI to generate summaries."""
        import time

        # Get selected file paths
        selected_paths = self.file_table.get_selected_files()

        if not selected_paths:
            QMessageBox.warning(self, "No Files Selected", "Please select files to process.")
            return

        if not self.model_manager.is_model_loaded():
            QMessageBox.warning(self, "No Model Loaded", "Please load a model first.")
            return

        # Get summary and vocabulary generation options
        generate_vocab = self.generate_vocab_checkbox.isChecked()
        generate_meta_summary = self.ai_controls.get_generate_meta_summary()
        meta_summary_length = self.ai_controls.get_meta_summary_length()
        generate_individual_summaries = self.ai_controls.get_generate_individual_summaries()
        individual_summary_length = self.ai_controls.get_individual_summary_length()
        preset_id = self.ai_controls.get_selected_preset_id()

        if not (generate_vocab or generate_meta_summary or generate_individual_summaries):
            QMessageBox.information(
                self,
                "No Actions Selected",
                "Please select at least one action: 'Generate Vocabulary List', 'Generate Overall Summary', or 'Generate Per-Document Summaries'."
            )
            return

        # Filter processing_results to only include selected files
        # Match by file path
        selected_results = []
        for result in self.processing_results:
            if result.get('file_path') in selected_paths:
                selected_results.append(result)

        if not selected_results:
            QMessageBox.warning(
                self,
                "No Processed Files",
                "The selected files have not been processed yet."
            )
            return

        # --- Vocabulary Extraction Logic ---
        if generate_vocab:
            self.status_bar.showMessage("Extracting vocabulary terms...", 0)
            try:
                # Combine all cleaned text from selected documents
                all_cleaned_text = "\n\n".join([
                    res['cleaned_text'] for res in selected_results if res.get('cleaned_text')
                ])
                
                # Instantiate VocabularyExtractor
                vocab_extractor = VocabularyExtractor(
                    exclude_list_path=LEGAL_EXCLUDE_LIST_PATH,
                    medical_terms_path=MEDICAL_TERMS_LIST_PATH
                )
                
                # Extract vocabulary
                extracted_vocabulary = vocab_extractor.extract(all_cleaned_text)
                
                # Save to CSV
                self._save_vocabulary_csv(extracted_vocabulary)
                
                self.status_bar.showMessage(f"Vocabulary extracted and saved to CSV. Proceeding with summary generation...", 5000)
                
            except Exception as e:
                self.status_bar.showMessage(f"Vocabulary extraction failed: {str(e)}", 5000)
                QMessageBox.critical(
                    self,
                    "Vocabulary Extraction Error",
                    f"An error occurred during vocabulary extraction:\n\n{str(e)}"
                )
                # Continue with summary generation even if vocab extraction fails
                generate_vocab = False # Prevent further attempts in this run

        # --- Summary Generation Logic ---
        if generate_meta_summary:
            self.status_bar.showMessage(f"Generating overall summary ({meta_summary_length} words)...", 0)
            self._generate_meta_summary(selected_results, meta_summary_length, preset_id)
        
        if generate_individual_summaries:
            self.status_bar.showMessage(f"Generating individual summaries ({individual_summary_length} words)...", 0)
            self._generate_individual_summaries(selected_results, individual_summary_length, preset_id)

    def _generate_meta_summary(self, selected_results: list, summary_length: int, preset_id: str):
        """
        Generate a single meta-summary for all selected documents.
        """
        # Clear previous summary
        self.summary_results.clear_summary()
        self.summary_results.start_generation(summary_length)
        self.process_btn.setEnabled(False) # Disable button while processing

        # Combine all cleaned text from selected documents
        all_cleaned_text = "\n\n".join([
            res['cleaned_text'] for res in selected_results if res.get('cleaned_text')
        ])
        
        # Here you would typically feed the all_cleaned_text to a summarizer
        # For now, let's mock it or adapt the existing AIWorker process
        
        # The existing AIWorkerProcess is designed for a list of processing results,
        # where each result has a 'cleaned_text'. For a meta-summary, we effectively
        # want to treat the combined text as a single document.
        
        # Create a dummy processing result for the combined text
        meta_result = {
            'file_path': 'meta_summary_combined_docs',
            'cleaned_text': all_cleaned_text,
            'status': 'success',
            'filename': 'Combined Documents'
        }

        self.ai_worker = self._create_ai_worker(
            model_manager=self.model_manager,
            processing_results=[meta_result], # Pass as a list of one result
            summary_length=summary_length,
            preset_id=preset_id
        )

        self._ai_start_time = time.time() # Need to import time again or move up

        # Connect signals
        self.ai_worker.progress_updated.connect(self._on_ai_progress)
        self.ai_worker.token_generated.connect(self._on_token_generated)
        self.ai_worker.summary_complete.connect(self._on_summary_complete)
        self.ai_worker.error.connect(self._on_ai_error)
        self.ai_worker.heartbeat_lost.connect(self._on_heartbeat_lost)
        self.ai_worker.finished.connect(self._on_ai_finished) # Make sure to re-enable button on finish

        self.ai_worker.start()

    def _generate_individual_summaries(self, selected_results: list, summary_length: int, preset_id: str):
        """
        Generate individual summaries for each selected document.
        """
        if not selected_results:
            return

        self.status_bar.showMessage(f"Starting individual summary generation for {len(selected_results)} documents...", 0)
        self.process_btn.setEnabled(False) # Disable button while processing

        self.individual_ai_workers = [] # Clear previous workers
        for i, result in enumerate(selected_results):
            # Create a separate worker for each document
            worker = self._create_ai_worker(
                model_manager=self.model_manager,
                processing_results=[result], # Pass single result
                summary_length=summary_length,
                preset_id=preset_id
            )
            worker.summary_complete.connect(
                lambda summary, filename=result['filename']: self._on_individual_summary_complete(summary, filename)
            )
            worker.error.connect(
                lambda error_msg, filename=result['filename']: self._on_individual_summary_error(error_msg, filename)
            )
            worker.finished.connect(self._on_individual_summary_finished)
            
            self.individual_ai_workers.append(worker)
            worker.start()
            self.status_bar.showMessage(f"Generating summary for {result['filename']}...", 0)

        # Re-enable button when all workers are done (handled by _on_individual_summary_finished)

    def _on_individual_summary_complete(self, summary: str, filename: str):
        """Handle completed individual summary from AI worker."""
        # For now, save individual summaries to separate files
        self.status_bar.showMessage(f"Summary for {filename} completed. Saving...", 3000)
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"individual_summary_{Path(filename).stem}_{timestamp}.txt"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save Summary for {filename}",
                default_filename,
                "Text Files (*.txt);;All Files (*.*)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                QMessageBox.information(
                    self,
                    "Summary Saved",
                    f"Individual summary for '{filename}' successfully saved to:\n{file_path}"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save individual summary for '{filename}':\n{str(e)}"
            )

    def _on_individual_summary_error(self, error_message: str, filename: str):
        """Handle errors for individual summary generation."""
        QMessageBox.critical(
            self,
            "Individual Summary Generation Error",
            f"An error occurred while generating summary for '{filename}':\n\n{error_message}"
        )
        self.status_bar.showMessage(f"Individual summary generation failed for {filename}")

    def _on_individual_summary_finished(self):
        """Handle cleanup when an individual AI worker finishes."""
        # Check if all individual workers have finished
        all_finished = True
        for worker in self.individual_ai_workers:
            if worker.isRunning():
                all_finished = False
                break
        
        if all_finished:
            self.status_bar.showMessage("All individual summaries generated.", 5000)
            self.process_btn.setEnabled(True) # Re-enable the main process button
            self.individual_ai_workers = [] # Clear the list of workers

    def _save_vocabulary_csv(self, vocabulary_data):
        """
        Saves the extracted vocabulary data to a CSV file.
        """
        if not vocabulary_data:
            self.status_bar.showMessage("No vocabulary data to save.", 3000)
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"extracted_vocabulary_{timestamp}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Vocabulary List",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ["Term", "Category", "Relevance to Case", "Definition"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for row in vocabulary_data:
                        writer.writerow(row)
                
                self.status_bar.showMessage(f"Vocabulary list saved to {os.path.basename(file_path)}", 5000)
                QMessageBox.information(
                    self,
                    "Vocabulary Saved",
                    f"Vocabulary list successfully saved to:\n{file_path}"
                )
            except Exception as e:
                self.status_bar.showMessage(f"Failed to save vocabulary list: {str(e)}", 5000)
                QMessageBox.critical(
                    self,
                    "Save Error",
                    f"Failed to save vocabulary list:\n{str(e)}"
                )

    @Slot(str)
    def _on_ai_progress(self, message: str):
        """Handle progress updates from AI worker."""
        self.status_bar.showMessage(message)

    @Slot(str)
    def _on_token_generated(self, token: str):
        """Handle streaming tokens from AI worker."""
        self.summary_results.append_token(token)

    @Slot(str)
    def _on_summary_complete(self, summary: str):
        """Handle completed summary from AI worker."""
        import time
        import traceback

        try:
            # CRITICAL: Display the summary text in the results widget
            print("[MAIN WINDOW] Attempting to display summary...")
            self.summary_results.set_summary(summary)
            print(f"[MAIN WINDOW] Summary displayed successfully ({len(summary)} chars)")

            # Hide progress indicator
            print("[MAIN WINDOW] Hiding progress indicator...")
            self.summary_results.hide_progress()
            print("[MAIN WINDOW] Progress indicator hidden")

            # Calculate generation time
            if hasattr(self, '_ai_start_time'):
                elapsed = time.time() - self._ai_start_time
                print(f"[MAIN WINDOW] Setting generation time: {elapsed:.1f}s")
                self.summary_results.set_generation_time(elapsed)
                print("[MAIN WINDOW] Generation time set")

            # Update status
            word_count = len(summary.split())
            print(f"[MAIN WINDOW] Updating status bar with {word_count} words...")
            self.status_bar.showMessage(
                f"Summary complete! Generated {word_count} words.", 5000
            )
            print("[MAIN WINDOW] Status bar updated")

            debug_log(f"[MAIN WINDOW] Summary displayed to user: {word_count} words")

            # Re-enable process button and cleanup
            print("[MAIN WINDOW] Re-enabling process button...")
            self.process_btn.setEnabled(True)
            if self.ai_worker:
                self.ai_worker.deleteLater()
                self.ai_worker = None
            print("[MAIN WINDOW] Summary complete handler finished successfully")

        except Exception as e:
            error_details = f"Exception in _on_summary_complete: {str(e)}\n{traceback.format_exc()}"
            print(f"[MAIN WINDOW] {error_details}")
            debug_log(f"[MAIN WINDOW] ERROR IN SUMMARY COMPLETE HANDLER: {error_details}")
            # Show error to user
            self.status_bar.showMessage(f"Error displaying summary: {str(e)}", 5000)

    @Slot(str)
    def _on_ai_error(self, error_message: str):
        """Handle errors from AI worker."""
        # Hide progress indicator
        self.summary_results.hide_progress()

        QMessageBox.critical(
            self,
            "Summary Generation Error",
            f"An error occurred while generating the summary:\n\n{error_message}"
        )
        self.status_bar.showMessage("Summary generation failed")

        # Re-enable process button and cleanup
        self.process_btn.setEnabled(True)
        if self.ai_worker:
            self.ai_worker.deleteLater()
            self.ai_worker = None

    @Slot()
    def _on_heartbeat_lost(self):
        """Handle lost heartbeat from AI worker (process may have crashed)."""
        self.status_bar.showMessage("Warning: Worker process not responding...", 10000)
        # Note: Don't stop the worker yet - it might recover.
        # User will be notified, but generation continues

    @Slot()
    def _on_ai_finished(self):
        """Clean up after AI worker finishes."""
        # Re-enable process button
        self.process_btn.setEnabled(True)

        # Clean up worker
        if self.ai_worker:
            self.ai_worker.deleteLater()
            self.ai_worker = None

    @Slot()
    def cancel_ai_generation(self):
        """Cancel the current AI generation."""
        if self.ai_worker and self.ai_worker.isRunning():
            # Stop the worker
            self.ai_worker.stop()

            # Update UI
            self.status_bar.showMessage("Summary generation cancelled by user", 3000)

            # Note: The worker will emit finished signal when it stops,
            # which will trigger _on_ai_finished() to clean up

    @Slot(str)
    def save_summary(self, summary_text: str):
        """
        Save summary to a text file.

        Args:
            summary_text: The summary text to save
        """
        from datetime import datetime

        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"case_summary_{timestamp}.txt"

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Summary",
            default_filename,
            "Text Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                # Write summary to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(summary_text)

                self.status_bar.showMessage(f"Summary saved to {os.path.basename(file_path)}", 3000)

                QMessageBox.information(
                    self,
                    "Summary Saved",
                    f"Summary successfully saved to:\n{file_path}"
                )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Save Error",
                    f"Failed to save summary:\n{str(e)}"
                )

    @Slot()
    def show_about(self):
        """Show About dialog."""
        about_text = """
        <h2>LocalScribe v2.0</h2>
        <p><b>100% Offline Legal Document Processor</b></p>
        <p>LocalScribe processes legal documents entirely on your computer,
        ensuring complete privacy and PII/PHI protection.</p>
        <p><i>Powered by Ollama (qwen2.5:7b-instruct)</i></p>
        <hr>
        <p><b>Current Phase:</b> Phase 3 - AI Integration (Ollama)</p>
        <p><b>Status:</b> Pre-processing engine active, Ollama integration enabled</p>
        """

        QMessageBox.about(self, "About LocalScribe", about_text)

    def _check_ollama_service(self):
        """
        Check if Ollama service is running on startup.

        Shows a helpful warning dialog if service is not accessible,
        with instructions for starting it.
        """
        try:
            self.model_manager.health_check()
            debug_log("[MAIN WINDOW] [OK] Ollama service is accessible on startup")
        except Exception as e:
            debug_log(f"[MAIN WINDOW] [ERROR] Ollama service not accessible: {str(e)}")

            # Build platform-specific instructions
            start_command = "ollama serve"  # Default command
            if sys.platform == 'win32' or platform.system() == 'Windows':
                instructions = (
                    "1. Install Ollama from https://ollama.ai\n"
                    "2. Open Command Prompt or PowerShell\n"
                    f"3. Run: {start_command}\n"
                    "4. Wait for the service to start, then restart this application"
                )
            elif sys.platform == 'darwin':  # macOS
                instructions = (
                    "1. Install Ollama from https://ollama.ai\n"
                    "2. The Ollama service typically starts automatically\n"
                    "3. If not running, you may need to start it via the menu bar or:\n"
                    f"   {start_command}\n"
                    "4. Restart this application"
                )
            else:  # Linux
                instructions = (
                    "1. Install Ollama: curl https://ollama.ai/install.sh | sh\n"
                    "2. Start the service:\n"
                    f"   {start_command}\n"
                    "3. Restart this application"
                )

            warning_text = (
                "Ollama service is not accessible.\n\n"
                "LocalScribe requires Ollama to be running in the background.\n\n"
                f"{instructions}\n\n"
                "You can continue using LocalScribe to prepare documents, "
                "but you won't be able to generate summaries until Ollama is running."
            )

            QMessageBox.warning(
                self,
                "Ollama Service Not Found",
                warning_text
            )

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
