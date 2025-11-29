"""
LocalScribe - Main Window

Main application window for LocalScribe, built with CustomTkinter.

This module serves as the central coordinator for the application:
- Manages application state (selected files, processing results)
- Creates and wires up UI components
- Handles user interactions (file selection, generation start)
- Coordinates between workers, message handlers, and orchestrator

Architecture:
- UI Layout: Delegated to quadrant_builder.py
- Message Routing: Delegated to QueueMessageHandler
- Workflow Logic: Delegated to WorkflowOrchestrator
- Background Work: Delegated to workers.py

Performance Optimizations (Session 14):
- Explicit garbage collection after processing completes
- Worker reference cleanup to prevent memory leaks
- Improved queue processing to prevent duplicate AI message handling
"""
import gc
import os
from queue import Empty, Queue
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.ai import ModelManager
from src.config import PROMPTS_DIR, USER_PROMPTS_DIR
from src.logging_config import debug_log
from src.prompt_template_manager import PromptTemplateManager
from src.ui.settings import SettingsDialog
from src.ui.menu_handler import create_menus
from src.ui.quadrant_builder import create_central_widget_layout
from src.ui.queue_message_handler import QueueMessageHandler
from src.ui.processing_timer import ProcessingTimer
from src.ui.system_monitor import SystemMonitor
from src.ui.workers import OllamaAIWorkerManager, ProcessingWorker
from src.ui.workflow_orchestrator import WorkflowOrchestrator
from src.user_preferences import get_user_preferences
from src.utils.text_utils import combine_document_texts


class MainWindow(ctk.CTk):
    """
    Main application window for LocalScribe.

    This class manages:
    - Application state (selected_files, processed_results, pending_ai_generation)
    - UI component lifecycle (toolbar, central widget, status bar)
    - Event loop integration (queue polling, Ollama health checks)

    Separation of Concerns:
    - QueueMessageHandler: Routes messages and updates UI widgets
    - WorkflowOrchestrator: Decides workflow steps (vocab extraction, AI generation)
    - Workers: Execute background tasks (extraction, vocabulary, AI)

    Attributes:
        selected_files: List of file paths selected by user
        processed_results: List of extraction results from ProcessingWorker
        pending_ai_generation: Dict of AI params when generation is pending
        model_manager: OllamaModelManager for AI model operations
        ui_queue: Queue for inter-thread communication
        message_handler: QueueMessageHandler instance
        workflow_orchestrator: WorkflowOrchestrator instance
    """

    def __init__(self):
        super().__init__()
        self.title("LocalScribe v2.1 - 100% Offline Legal Document Processor")
        self.geometry("1200x800")

        # Application State
        self.selected_files = []
        self.processed_results = []
        self.worker = None
        self.pending_ai_generation = None

        # AI Model Manager
        self.model_manager = ModelManager()

        # Prompt Template Manager (for prompt style selection)
        self.prompt_template_manager = PromptTemplateManager(PROMPTS_DIR, USER_PROMPTS_DIR)

        # Threading Queue for worker communication
        self.ui_queue = Queue()

        # AI Worker Manager for Ollama summaries
        self.ai_worker_manager = OllamaAIWorkerManager(self.ui_queue)

        # Message Handler and Workflow Orchestrator (separation of concerns)
        self.message_handler = QueueMessageHandler(self)
        self.workflow_orchestrator = WorkflowOrchestrator(self)
        self.message_handler.set_orchestrator(self.workflow_orchestrator)

        # Initialize UI Components
        self._create_main_layout()
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Start queue polling for worker messages
        self.after(100, self._process_queue)

        # Check Ollama service availability on startup
        self._check_ollama_service()
        self.model_selection.refresh_status()

    def _create_main_layout(self):
        """Creates the main grid layout."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _create_menus(self):
        """Create menubar with File and Help menus using menu_handler module."""
        create_menus(self, self.select_files, self.show_settings, self.quit)

    def show_settings(self):
        """Open the Settings dialog."""
        def on_save():
            """Callback when user saves settings."""
            self.status_label.configure(text="Settings saved.", text_color="green")

        dialog = SettingsDialog(parent=self, on_save_callback=on_save)
        self.wait_window(dialog)  # Wait for dialog to close

    def _create_toolbar(self):
        """Create toolbar with file selection controls."""
        self.toolbar_frame = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.toolbar_frame.grid_columnconfigure(1, weight=1)

        self.select_files_btn = ctk.CTkButton(self.toolbar_frame, text="Select Files...", command=self.select_files)
        self.select_files_btn.grid(row=0, column=0, padx=10, pady=10)

        self.files_label = ctk.CTkLabel(self.toolbar_frame, text="No files selected", text_color="gray")
        self.files_label.grid(row=0, column=2, padx=10, pady=10)

    def _create_central_widget(self):
        """
        Create the four-quadrant central widget using the quadrant builder.

        This method delegates all layout construction to the builder module,
        keeping main_window.py focused on state management and event handling.
        """
        (
            self.main_content_frame,
            self.file_table,
            self.model_selection,
            self.summary_results,
            self.output_options,
            self.generate_outputs_btn,
            self.cancel_btn
        ) = create_central_widget_layout(self, self.model_manager, self.prompt_template_manager)

        # Bind the generate button command
        self.generate_outputs_btn.configure(command=self._start_generation)

        # Bind the cancel button command
        self.cancel_btn.configure(command=self._cancel_processing)

        # Initialize prompt selector with available templates
        self.model_selection.refresh_prompts()

    def _create_status_bar(self):
        """Create status bar for messages, timer, and system monitoring."""
        self.status_bar_frame = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.status_bar_frame.grid(row=2, column=0, sticky="ew")
        self.status_bar_frame.grid_columnconfigure(0, weight=1)  # Status label expands
        self.status_bar_frame.grid_columnconfigure(1, weight=0)  # Timer fixed
        self.status_bar_frame.grid_columnconfigure(2, weight=0)  # Progress bar fixed
        self.status_bar_frame.grid_columnconfigure(3, weight=0)  # Monitor fixed

        # Status label - much larger for high visibility
        # Using white/light cyan text on dark background for contrast
        self.status_label = ctk.CTkLabel(
            self.status_bar_frame,
            text="Ready",
            anchor="w",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#00E5FF"  # Bright cyan - high contrast on dark bg
        )
        self.status_label.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        # Processing timer - shows elapsed time during processing
        self.processing_timer = ProcessingTimer(
            self.status_bar_frame,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFD700"  # Gold color for timer visibility
        )
        self.processing_timer.grid(row=0, column=1, sticky="e", padx=(5, 10))

        self.progress_bar = ctk.CTkProgressBar(self.status_bar_frame, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=2, sticky="e", padx=(5, 5))

        # Add system monitor (CPU/RAM display with hover tooltip)
        self.system_monitor = SystemMonitor(self.status_bar_frame)
        self.system_monitor.grid(row=0, column=3, sticky="e", padx=(0, 5))

    def select_files(self):
        """Open file dialog and update selected files."""
        filepaths = filedialog.askopenfilenames(
            title="Select Legal Documents",
            filetypes=(("Documents", "*.pdf *.txt *.rtf"), ("All files", "*.*"))
        )
        if filepaths:
            self.selected_files = filepaths
            self.files_label.configure(text=f"{len(filepaths)} file(s) selected")
            self.generate_outputs_btn.configure(state="normal")

            # Update output options with document count for dynamic button text
            self.output_options.set_document_count(len(filepaths))

            # Populate file table with initial pending status
            self.file_table.clear() # Clear existing entries
            for filepath in filepaths:
                filename = os.path.basename(filepath)
                file_size = os.path.getsize(filepath) # Get actual file size
                self.file_table.add_result({
                    'filename': filename,
                    'status': 'pending',
                    'method': 'N/A',
                    'confidence': 0,
                    'page_count': 0, # Page count requires processing, keep as 0 for now
                    'file_size': file_size
                })

        else:
            self.selected_files = []
            self.files_label.configure(text="No files selected")
            self.generate_outputs_btn.configure(state="disabled")
            self.output_options.set_document_count(0)  # Reset document count
            self.file_table.clear()

    def _start_generation(self):
        """Initiate the processing and generation of outputs."""
        if not self.selected_files:
            messagebox.showwarning("No Files Selected", "Please select documents to process first.")
            return

        # Get selected model and summary length
        selected_model = self.model_selection.model_selector.get()
        if selected_model == "Loading..." or selected_model == "Ollama not found":
            messagebox.showwarning("Model Not Selected", "Please select a valid AI model.")
            return

        summary_length = int(self.output_options.length_slider.get())

        # Get output options
        output_options = {
            "individual_summaries": self.output_options.individual_summaries_check.get(),
            "meta_summary": self.output_options.meta_summary_check.get(),
            "vocab_csv": self.output_options.vocab_csv_check.get()
        }

        # Check if at least one output option is selected
        if not any(output_options.values()):
            messagebox.showwarning("No Output Selected", "Please select at least one output type (Individual Summaries, Meta-Summary, or Rare Word List).")
            return

        self.start_processing(self.selected_files, selected_model, summary_length, output_options)

    def start_processing(self, file_paths, selected_model, summary_length, output_options):
        """Start background processing of selected documents."""
        # Disable UI elements to prevent mid-flight changes
        self.select_files_btn.configure(state="disabled")
        self.generate_outputs_btn.configure(state="disabled")
        self.output_options.lock_controls()  # Lock slider and checkboxes

        # Update button text to show "Generating..."
        self.output_options.set_generating_state(True)

        # Enable cancel button (make it red and clickable)
        self.cancel_btn.configure(
            state="normal",
            fg_color="#dc3545",  # Red when active
            hover_color="#b02a37"
        )

        self.progress_bar.grid()  # Make progress bar visible (already gridded at column 1)
        # DO NOT clear the file table - users need to see which files are being processed
        # The table entries will be updated with status as files are processed
        self.processed_results = []
        self.summary_results.update_outputs(meta_summary="", vocab_csv_data=[], document_summaries={}) # Clear previous results

        # Get selected prompt preset
        selected_preset_id = self.model_selection.get_selected_preset_id()

        # Build list of outputs being requested for metrics logging
        outputs_requested = []
        if output_options.get("individual_summaries"):
            outputs_requested.append("individual_summaries")
        if output_options.get("meta_summary"):
            outputs_requested.append("meta_summary")
        if output_options.get("vocab_csv"):
            outputs_requested.append("vocab_csv")

        # Gather document metadata for the timer/metrics
        documents_metadata = []
        for filepath in file_paths:
            documents_metadata.append({
                'filename': os.path.basename(filepath),
                'file_size': os.path.getsize(filepath),
                'page_count': 0  # Will be updated after extraction
            })

        # Start the processing timer with job metadata for CSV logging
        self.processing_timer.start({
            'documents': documents_metadata,
            'model_name': selected_model,
            'outputs_requested': outputs_requested
        })

        # Store AI generation parameters for after document extraction completes
        self.pending_ai_generation = {
            "selected_model": selected_model,
            "summary_length": summary_length,
            "output_options": output_options,
            "preset_id": selected_preset_id
        }

        self.worker = ProcessingWorker(
            file_paths,
            self.ui_queue
        )
        self.worker.start()

    def _cancel_processing(self):
        """Cancel all running background workers and restore UI state."""
        debug_log("[MAIN WINDOW] User requested cancellation.")

        # Stop ProcessingWorker if running
        if self.worker and self.worker.is_alive():
            debug_log("[MAIN WINDOW] Stopping ProcessingWorker...")
            self.worker.stop()

        # Stop VocabularyWorker if running (via orchestrator)
        if self.workflow_orchestrator.vocab_worker and self.workflow_orchestrator.vocab_worker.is_alive():
            debug_log("[MAIN WINDOW] Stopping VocabularyWorker...")
            self.workflow_orchestrator.vocab_worker.stop()

        # Stop AI worker if running
        if self.ai_worker_manager.is_running:
            debug_log("[MAIN WINDOW] Stopping AI worker...")
            self.ai_worker_manager.stop_worker()

        # Stop timer without logging (cancelled jobs shouldn't be in metrics)
        self.processing_timer.reset()

        # Reset UI state
        self.status_label.configure(text="Processing cancelled by user.")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        # Re-enable UI controls
        self.select_files_btn.configure(state="normal")
        self.generate_outputs_btn.configure(state="normal")
        self.output_options.unlock_controls()

        # Reset button text from "Generating..." back to normal
        self.output_options.set_generating_state(False)

        # Disable cancel button (grey it out instead of hiding)
        self.cancel_btn.configure(
            state="disabled",
            fg_color="#6c757d",  # Grey when disabled
            hover_color="#5a6268"
        )

        # Clear pending AI generation and processed results
        self.pending_ai_generation = None
        self.processed_results = []

        # Clear worker references to allow garbage collection
        self.worker = None
        self.workflow_orchestrator.vocab_worker = None

        # Run garbage collection in background thread (non-blocking)
        import threading
        threading.Thread(target=gc.collect, daemon=True).start()

        debug_log("[MAIN WINDOW] Cancellation complete. UI restored, background GC started.")

    def _start_ai_generation(self, extracted_documents, ai_params):
        """
        Start AI summary generation after document extraction is complete.

        Args:
            extracted_documents: List of extracted document dictionaries
            ai_params: Dict with 'selected_model', 'summary_length', 'output_options', 'preset_id'
        """
        try:
            selected_model = ai_params["selected_model"]
            summary_length = ai_params["summary_length"]
            preset_id = ai_params.get("preset_id", "factual-summary")  # Default to factual-summary

            # Combine documents with filename headers for AI context
            combined_text = combine_document_texts(
                extracted_documents,
                include_headers=True
            )

            self.status_label.configure(text="Generating AI summary...")
            self.progress_bar.set(0.5)

            # Send task to AI worker - using the correct format expected by ollama_worker
            task_payload = {
                "case_text": combined_text,
                "max_words": summary_length,
                "preset_id": preset_id  # Use the selected prompt template
            }

            self.ai_worker_manager.send_task("GENERATE_SUMMARY", task_payload)
            debug_log(f"[MAIN WINDOW] Started AI generation with model: {selected_model}, preset: {preset_id}, length: {summary_length} words")

        except Exception as e:
            debug_log(f"[MAIN WINDOW] Error starting AI generation: {e}")
            messagebox.showerror("AI Generation Error", f"Failed to start AI summary generation: {str(e)}")
            self.select_files_btn.configure(state="normal")
            self.generate_outputs_btn.configure(state="normal")
            self.progress_bar.grid_remove()

    def _process_queue(self):
        """
        Process messages from the worker thread queue and AI worker manager.

        Uses the QueueMessageHandler for decoupled, testable message routing.
        Processes messages in batches to keep GUI responsive during heavy loads.

        AI messages are processed directly (not re-queued) to prevent duplicates.
        """
        # Process up to 10 messages per cycle to keep GUI responsive
        # For 260-page PDFs, this prevents blocking the main thread
        MAX_MESSAGES_PER_CYCLE = 10
        messages_processed = 0

        try:
            while messages_processed < MAX_MESSAGES_PER_CYCLE:
                message_type, data = self.ui_queue.get_nowait()
                # Delegate to message handler for routing and processing
                self.message_handler.process_message(message_type, data)
                messages_processed += 1

        except Empty:
            pass  # No messages in queue

        # Process AI worker messages directly (not re-queued to prevent duplicates)
        if hasattr(self, 'ai_worker_manager'):
            ai_messages = self.ai_worker_manager.check_for_messages()
            for msg_type, msg_data in ai_messages:
                # Process AI messages directly through message handler
                self.message_handler.process_message(msg_type, msg_data)
                messages_processed += 1

        # Force UI update to keep responsive during heavy processing
        if messages_processed > 0:
            self.update_idletasks()

        self.after(100, self._process_queue)  # Poll again after 100ms

    def _check_ollama_service(self):
        """Check if Ollama service is running on startup."""
        try:
            self.model_manager.health_check()
            debug_log("[MAIN WINDOW] [OK] Ollama service is accessible on startup")
            self.status_label.configure(text="Ollama service connected.", text_color="green")
        except Exception as e:
            debug_log(f"[MAIN WINDOW] [ERROR] Ollama service not accessible: {str(e)}")
            self.status_label.configure(text="Ollama service not found!", text_color="red")
            messagebox.showwarning(
                "Ollama Service Not Found",
                "Ollama service is not accessible. Please ensure Ollama is running to generate summaries."
            )
