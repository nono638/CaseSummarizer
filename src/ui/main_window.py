"""
LocalScribe - Main Window (CustomTkinter)
Session 29: Two-Panel Q&A-First Layout

Main application window with:
- Header: Corpus dropdown + Settings button
- No-corpus warning banner
- Two-panel layout: Left (Session Documents + Tasks), Right (Results)
- Status bar with processing timer
"""

import os
import sys
import time
from pathlib import Path
from queue import Queue, Empty
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.config import DEBUG_MODE, PROMPTS_DIR
from src.logging_config import debug_log
from src.ai import OllamaModelManager
from src.prompt_template_manager import PromptTemplateManager
from src.user_preferences import get_user_preferences
from src.ui.widgets import FileReviewTable, ModelSelectionWidget, OutputOptionsWidget
from src.ui.dynamic_output import DynamicOutputWidget
from src.ui.workers import ProcessingWorker, VocabularyWorker, QAWorker
from src.vocabulary import get_corpus_registry
from src.vector_store import VectorStoreBuilder


class MainWindow(ctk.CTk):
    """
    Main application window for LocalScribe.

    Session 29: Q&A-first two-panel layout with corpus management.

    Layout:
    - Header row: App title, corpus dropdown, settings button
    - Warning banner: Shown when no corpus configured
    - Left panel: Session documents + task checkboxes + "Perform N Tasks" button
    - Right panel: Results display with output type selector
    - Status bar: Status text + corpus info + processing timer
    """

    def __init__(self):
        super().__init__()

        self.title("LocalScribe")
        self.geometry("1200x750")
        self.minsize(900, 600)

        # State
        self.selected_files: list[str] = []
        self.processing_results: list[dict] = []
        self._processing_start_time: float | None = None
        self._timer_after_id: str | None = None

        # Managers
        self.model_manager = OllamaModelManager()
        self.prompt_template_manager = PromptTemplateManager(PROMPTS_DIR)
        self.corpus_registry = get_corpus_registry()

        # Workers and queue
        self._processing_worker: ProcessingWorker | None = None
        self._vocabulary_worker: VocabularyWorker | None = None
        self._qa_worker: QAWorker | None = None
        self._ui_queue: Queue | None = None
        self._queue_poll_id: str | None = None

        # Q&A infrastructure
        self._embeddings = None  # Lazy-loaded HuggingFaceEmbeddings
        self._vector_store_path = None  # Path to current session's vector store
        self._qa_results: list = []  # Store QAResult objects

        # Build UI
        self._create_header()
        self._create_warning_banner()
        self._create_main_panels()
        self._create_status_bar()

        # Initialize state
        self._refresh_corpus_dropdown()
        self._update_corpus_banner()
        self._update_generate_button_state()

        # Startup checks
        self._check_ollama_service()

        if DEBUG_MODE:
            debug_log("[MainWindow] Initialized with two-panel layout")

    # =========================================================================
    # UI Creation Methods
    # =========================================================================

    def _create_header(self):
        """Create header row with corpus dropdown and settings button."""
        self.header_frame = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.header_frame.pack(fill="x", padx=0, pady=0)
        self.header_frame.pack_propagate(False)

        # App title (left)
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="LocalScribe",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(side="left", padx=15, pady=10)

        # Settings button (right)
        self.settings_btn = ctk.CTkButton(
            self.header_frame,
            text="⚙ Settings",
            width=100,
            command=self._open_settings
        )
        self.settings_btn.pack(side="right", padx=15, pady=10)

        # Corpus dropdown (right of title)
        self.corpus_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.corpus_frame.pack(side="right", padx=10, pady=10)

        corpus_label = ctk.CTkLabel(
            self.corpus_frame,
            text="Corpus:",
            font=ctk.CTkFont(size=12)
        )
        corpus_label.pack(side="left", padx=(0, 5))

        self.corpus_dropdown = ctk.CTkComboBox(
            self.corpus_frame,
            values=["Loading..."],
            width=150,
            command=self._on_corpus_changed
        )
        self.corpus_dropdown.pack(side="left")

        # Manage button
        self.manage_corpus_btn = ctk.CTkButton(
            self.corpus_frame,
            text="Manage",
            width=70,
            fg_color=("gray70", "gray30"),
            command=self._open_corpus_dialog
        )
        self.manage_corpus_btn.pack(side="left", padx=(5, 0))

    def _create_warning_banner(self):
        """Create the no-corpus warning banner."""
        self.banner_frame = ctk.CTkFrame(
            self,
            fg_color=("#fff3cd", "#4a4528"),
            corner_radius=0,
            height=45
        )
        # Initially hidden, shown by _update_corpus_banner if needed
        self.banner_frame.pack_propagate(False)

        warning_text = (
            "⚠️ No corpus configured. Set up a corpus to improve vocabulary detection. "
            "Your corpus stays 100% local and offline."
        )
        self.banner_label = ctk.CTkLabel(
            self.banner_frame,
            text=warning_text,
            font=ctk.CTkFont(size=12),
            text_color=("#856404", "#d4b833")
        )
        self.banner_label.pack(side="left", padx=15, pady=10)

        self.setup_corpus_btn = ctk.CTkButton(
            self.banner_frame,
            text="Set Up Now",
            width=100,
            command=self._open_corpus_dialog
        )
        self.setup_corpus_btn.pack(side="right", padx=15, pady=8)

    def _create_main_panels(self):
        """Create the two-panel main content area."""
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Configure grid for two panels
        self.main_frame.grid_columnconfigure(0, weight=2)  # Left panel
        self.main_frame.grid_columnconfigure(1, weight=3)  # Right panel (larger)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Left panel: Session Documents + Tasks
        self._create_left_panel()

        # Right panel: Results
        self._create_right_panel()

    def _create_left_panel(self):
        """Create the left panel with session documents and task options."""
        self.left_panel = ctk.CTkFrame(self.main_frame)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)

        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)  # File table expands

        # Section header
        docs_header = ctk.CTkLabel(
            self.left_panel,
            text="📁 SESSION DOCUMENTS",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        docs_header.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        # File Review Table
        self.file_table = FileReviewTable(self.left_panel)
        self.file_table.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # File buttons
        file_btn_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        file_btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.add_files_btn = ctk.CTkButton(
            file_btn_frame,
            text="+ Add Files",
            width=100,
            command=self._select_files
        )
        self.add_files_btn.pack(side="left", padx=(0, 5))

        self.clear_files_btn = ctk.CTkButton(
            file_btn_frame,
            text="Clear All",
            width=80,
            fg_color=("gray70", "gray30"),
            command=self._clear_files
        )
        self.clear_files_btn.pack(side="left")

        # Task checkboxes section
        task_header = ctk.CTkLabel(
            self.left_panel,
            text="TASKS",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        task_header.grid(row=3, column=0, sticky="w", padx=10, pady=(15, 5))

        task_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        task_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=0)

        # Q&A checkbox (default ON)
        self.qa_check = ctk.CTkCheckBox(
            task_frame,
            text="Questions & Answers",
            command=self._update_generate_button_state
        )
        self.qa_check.pack(anchor="w", pady=2)
        self.qa_check.select()  # ON by default

        # Vocabulary checkbox (default ON)
        self.vocab_check = ctk.CTkCheckBox(
            task_frame,
            text="Vocabulary",
            command=self._update_generate_button_state
        )
        self.vocab_check.pack(anchor="w", pady=2)
        self.vocab_check.select()  # ON by default

        # Summary checkbox (default OFF, with warning)
        self.summary_check = ctk.CTkCheckBox(
            task_frame,
            text="Summary (slow)",
            command=self._on_summary_checked
        )
        self.summary_check.pack(anchor="w", pady=2)
        # OFF by default - no select()

        # "Perform N Tasks" button
        self.generate_btn = ctk.CTkButton(
            self.left_panel,
            text="Perform 2 Tasks",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self._perform_tasks
        )
        self.generate_btn.grid(row=5, column=0, sticky="ew", padx=10, pady=(15, 10))

    def _create_right_panel(self):
        """Create the right panel with results display."""
        self.right_panel = ctk.CTkFrame(self.main_frame)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)

        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)  # Results area expands

        # Header with results dropdown
        results_header = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        results_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        results_label = ctk.CTkLabel(
            results_header,
            text="📋 RESULTS",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        results_label.pack(side="left")

        # Dynamic Output Widget (contains the results selector and display)
        self.output_display = DynamicOutputWidget(self.right_panel)
        self.output_display.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # Follow-up question input (for Q&A mode)
        followup_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        followup_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        followup_frame.grid_columnconfigure(0, weight=1)

        self.followup_entry = ctk.CTkEntry(
            followup_frame,
            placeholder_text="Ask a follow-up question...",
            height=35
        )
        self.followup_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.followup_entry.bind("<Return>", lambda e: self._ask_followup())

        self.followup_btn = ctk.CTkButton(
            followup_frame,
            text="Ask",
            width=60,
            command=self._ask_followup,
            state="disabled"  # Enabled after Q&A results exist
        )
        self.followup_btn.grid(row=0, column=1)

    def _create_status_bar(self):
        """Create status bar at bottom of window."""
        self.status_frame = ctk.CTkFrame(self, height=30, corner_radius=0)
        self.status_frame.pack(fill="x", side="bottom")
        self.status_frame.pack_propagate(False)

        # Status text
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Ready",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.pack(side="left", padx=10, pady=5)

        # Timer (right side)
        self.timer_label = ctk.CTkLabel(
            self.status_frame,
            text="⏱ 0:00",
            font=ctk.CTkFont(size=11)
        )
        self.timer_label.pack(side="right", padx=10, pady=5)

        # Corpus info (middle)
        self.corpus_info_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.corpus_info_label.pack(side="right", padx=20, pady=5)

    # =========================================================================
    # Corpus Management
    # =========================================================================

    def _refresh_corpus_dropdown(self):
        """Refresh the corpus dropdown with available corpora."""
        try:
            corpora = self.corpus_registry.list_corpora()
            names = [c.name for c in corpora]

            if names:
                self.corpus_dropdown.configure(values=names)
                active = self.corpus_registry.get_active_corpus()
                self.corpus_dropdown.set(active)

                # Update status bar with corpus info
                active_info = next((c for c in corpora if c.name == active), None)
                if active_info:
                    self.corpus_info_label.configure(
                        text=f"Corpus: {active} ({active_info.doc_count} docs)"
                    )
            else:
                self.corpus_dropdown.configure(values=["No corpora"])
                self.corpus_dropdown.set("No corpora")
                self.corpus_info_label.configure(text="")

        except Exception as e:
            debug_log(f"[MainWindow] Error refreshing corpus dropdown: {e}")
            self.corpus_dropdown.configure(values=["Error"])
            self.corpus_dropdown.set("Error")

    def _update_corpus_banner(self):
        """Show or hide the no-corpus warning banner."""
        try:
            corpora = self.corpus_registry.list_corpora()
            total_docs = sum(c.doc_count for c in corpora)

            if total_docs == 0:
                # Show banner
                self.banner_frame.pack(fill="x", after=self.header_frame)
            else:
                # Hide banner
                self.banner_frame.pack_forget()

        except Exception:
            # On error, hide banner
            self.banner_frame.pack_forget()

    def _on_corpus_changed(self, corpus_name: str):
        """Handle corpus selection change."""
        try:
            self.corpus_registry.set_active_corpus(corpus_name)
            self._refresh_corpus_dropdown()
            self.set_status(f"Active corpus: {corpus_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to switch corpus: {e}")

    def _open_corpus_dialog(self):
        """Open the corpus management dialog."""
        from src.ui.corpus_dialog import CorpusDialog

        dialog = CorpusDialog(self)
        self.wait_window(dialog)

        # Refresh after dialog closes
        if dialog.corpus_changed:
            self._refresh_corpus_dropdown()
            self._update_corpus_banner()
            self.set_status("Corpus updated")

    # =========================================================================
    # File Management
    # =========================================================================

    def _select_files(self):
        """Open file dialog to select documents for this session."""
        files = filedialog.askopenfilenames(
            title="Select Documents for This Session",
            filetypes=[
                ("Documents", "*.pdf *.txt *.rtf"),
                ("PDF files", "*.pdf"),
                ("Text files", "*.txt"),
                ("RTF files", "*.rtf"),
                ("All files", "*.*")
            ]
        )

        if not files:
            return

        self.selected_files = list(files)
        self.set_status(f"Processing {len(files)} file(s)...")
        self._start_preprocessing()

    def _clear_files(self):
        """Clear all files from the session."""
        self.selected_files.clear()
        self.processing_results.clear()
        self.file_table.clear()
        self._update_generate_button_state()
        self.set_status("Files cleared")

    def _start_preprocessing(self):
        """Start preprocessing selected files."""
        if not self.selected_files:
            return

        # Disable controls during preprocessing
        self.add_files_btn.configure(state="disabled")
        self.generate_btn.configure(state="disabled")

        # Clear previous results
        self.file_table.clear()
        self.processing_results.clear()

        # Start timer
        self._start_timer()

        # Create queue for worker communication
        self._ui_queue = Queue()

        # Create and start worker
        self._processing_worker = ProcessingWorker(
            file_paths=self.selected_files,
            ui_queue=self._ui_queue
        )
        self._processing_worker.start()

        # Start polling the queue
        self._poll_queue()

    def _poll_queue(self):
        """Poll the UI queue for worker messages."""
        try:
            while True:
                msg_type, data = self._ui_queue.get_nowait()
                self._handle_queue_message(msg_type, data)
        except Empty:
            pass

        # Continue polling if worker is running
        if self._processing_worker and self._processing_worker.is_alive():
            self._queue_poll_id = self.after(50, self._poll_queue)
        else:
            # Final poll to catch any remaining messages
            try:
                while True:
                    msg_type, data = self._ui_queue.get_nowait()
                    self._handle_queue_message(msg_type, data)
            except Empty:
                pass

    def _handle_queue_message(self, msg_type: str, data):
        """Handle a message from the worker queue."""
        if msg_type == "progress":
            percentage, message = data
            self.set_status(message)

        elif msg_type == "file_processed":
            self.processing_results.append(data)
            self.file_table.add_result(data)

        elif msg_type == "processing_finished":
            self._on_preprocessing_complete(data)

        elif msg_type == "error":
            self.set_status(f"Error: {data}")
            messagebox.showerror("Processing Error", str(data))
            self._on_preprocessing_complete([])

    def _on_preprocessing_complete(self, results: list[dict]):
        """Handle preprocessing completion."""
        # Stop timer
        self._stop_timer()

        # Stop queue polling
        if self._queue_poll_id:
            self.after_cancel(self._queue_poll_id)
            self._queue_poll_id = None

        # Re-enable controls
        self.add_files_btn.configure(state="normal")
        self._update_generate_button_state()

        # Count results
        success_count = sum(1 for r in results if r.get('status') == 'success')
        failed_count = len(results) - success_count

        status = f"Processed {len(results)} file(s): {success_count} ready"
        if failed_count > 0:
            status += f", {failed_count} failed"

        self.set_status(status)

    # =========================================================================
    # Task Execution
    # =========================================================================

    def _get_task_count(self) -> int:
        """Get the number of selected tasks."""
        count = 0
        if self.qa_check.get():
            count += 1
        if self.vocab_check.get():
            count += 1
        if self.summary_check.get():
            count += 1
        return count

    def _update_generate_button_state(self):
        """Update the generate button text and state."""
        task_count = self._get_task_count()
        has_files = len(self.processing_results) > 0

        if task_count == 0:
            self.generate_btn.configure(text="Select Tasks", state="disabled")
        elif not has_files:
            self.generate_btn.configure(text=f"Add Files ({task_count} tasks)", state="disabled")
        elif task_count == 1:
            self.generate_btn.configure(text="Perform 1 Task", state="normal")
        else:
            self.generate_btn.configure(text=f"Perform {task_count} Tasks", state="normal")

    def _on_summary_checked(self):
        """Handle summary checkbox toggle - show warning if enabling."""
        if self.summary_check.get():
            # Show warning dialog
            result = messagebox.askyesno(
                "Summary Warning",
                "Summary generation typically takes 30+ minutes and results depend "
                "heavily on your hardware.\n\n"
                "For quick case familiarization, Q&A is recommended instead.\n\n"
                "Continue with summary?",
                icon="warning"
            )
            if not result:
                self.summary_check.deselect()

        self._update_generate_button_state()

    def _perform_tasks(self):
        """Execute the selected tasks."""
        if not self.processing_results:
            messagebox.showwarning("No Files", "Please add files first.")
            return

        task_count = self._get_task_count()
        if task_count == 0:
            messagebox.showwarning("No Tasks", "Please select at least one task.")
            return

        # Disable controls during processing
        self.generate_btn.configure(state="disabled", text=f"Processing {task_count} tasks...")
        self.add_files_btn.configure(state="disabled")

        # Start timer
        self._start_timer()

        # Get selected options
        do_qa = self.qa_check.get()
        do_vocab = self.vocab_check.get()
        do_summary = self.summary_check.get()

        # Track pending tasks
        self._pending_tasks = {
            'vocab': do_vocab,
            'qa': do_qa,
            'summary': do_summary
        }
        self._completed_tasks = set()

        # Start vocabulary extraction first (if requested)
        if do_vocab:
            self._start_vocabulary_extraction()
        elif do_qa:
            self._start_qa_task()
        elif do_summary:
            self._start_summary_task()
        else:
            self._on_tasks_complete(True, "No tasks selected")

    def _start_vocabulary_extraction(self):
        """Start vocabulary extraction task."""
        from src.utils.text_utils import combine_document_texts
        from src.config import LEGAL_EXCLUDE_LIST_PATH, MEDICAL_TERMS_LIST_PATH, USER_VOCAB_EXCLUDE_PATH

        self.set_status("Extracting vocabulary...")

        # Debug: Log what's in processing_results
        debug_log(f"[MainWindow] Vocabulary: {len(self.processing_results)} documents in processing_results")
        for i, doc in enumerate(self.processing_results):
            text_len = len(doc.get('extracted_text', '') or '')
            debug_log(f"[MainWindow] Doc {i}: {doc.get('filename', 'unknown')} - {text_len} chars, status={doc.get('status')}")

        # Combine text from all processed documents
        combined_text = combine_document_texts(self.processing_results)

        debug_log(f"[MainWindow] Combined text length: {len(combined_text)} chars")

        if not combined_text.strip():
            self.set_status("No text to analyze for vocabulary")
            debug_log("[MainWindow] WARNING: No text after combining documents!")
            self._on_vocab_complete([])
            return

        # Create queue for vocab worker
        self._vocab_queue = Queue()

        # Start vocabulary worker
        self._vocabulary_worker = VocabularyWorker(
            combined_text=combined_text,
            ui_queue=self._vocab_queue,
            exclude_list_path=str(LEGAL_EXCLUDE_LIST_PATH),
            medical_terms_path=str(MEDICAL_TERMS_LIST_PATH),
            user_exclude_path=str(USER_VOCAB_EXCLUDE_PATH),
            doc_count=len(self.processing_results)
        )
        self._vocabulary_worker.start()

        # Start polling vocab queue
        self._poll_vocab_queue()

    def _poll_vocab_queue(self):
        """Poll the vocabulary worker queue."""
        try:
            while True:
                msg_type, data = self._vocab_queue.get_nowait()
                if msg_type == "progress":
                    self.set_status(data[1] if isinstance(data, tuple) else str(data))
                elif msg_type == "vocab_csv_generated":
                    self._on_vocab_complete(data)
                    return
                elif msg_type == "error":
                    self.set_status(f"Vocabulary error: {data}")
                    self._on_vocab_complete([])
                    return
        except Empty:
            pass

        # Continue polling if worker is alive
        if self._vocabulary_worker and self._vocabulary_worker.is_alive():
            self.after(50, self._poll_vocab_queue)
        else:
            # Worker finished - do final poll
            try:
                while True:
                    msg_type, data = self._vocab_queue.get_nowait()
                    if msg_type == "vocab_csv_generated":
                        self._on_vocab_complete(data)
                        return
            except Empty:
                pass
            # If we get here, worker finished without sending results
            self._on_vocab_complete([])

    def _on_vocab_complete(self, vocab_data: list):
        """Handle vocabulary extraction completion."""
        self._completed_tasks.add('vocab')

        # Display results using update_outputs
        if vocab_data:
            self.output_display.update_outputs(vocab_csv_data=vocab_data)
            self.set_status(f"Vocabulary: {len(vocab_data)} terms found")
        else:
            self.set_status("Vocabulary extraction complete (no terms)")

        # Continue to next task
        if self._pending_tasks.get('qa'):
            self._start_qa_task()
        elif self._pending_tasks.get('summary'):
            self._start_summary_task()
        else:
            self._finalize_tasks()

    def _start_qa_task(self):
        """Start Q&A task - build vector store then run questions."""
        import threading

        self.set_status("Q&A: Loading embeddings model (this may take a moment)...")

        # Run the heavy initialization in a background thread
        def initialize_qa():
            """Background thread for embeddings + vector store setup."""
            try:
                # Lazy-load embeddings model (slow first time, reused after)
                if self._embeddings is None:
                    debug_log("[MainWindow] Loading HuggingFaceEmbeddings model...")
                    from langchain_huggingface import HuggingFaceEmbeddings
                    self._embeddings = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'}
                    )
                    debug_log("[MainWindow] Embeddings model loaded")

                # Build vector store from documents
                debug_log("[MainWindow] Building vector store...")
                builder = VectorStoreBuilder()
                result = builder.create_from_documents(
                    documents=self.processing_results,
                    embeddings=self._embeddings
                )
                self._vector_store_path = result.persist_dir
                debug_log(f"[MainWindow] Vector store created: {result.chunk_count} chunks at {result.persist_dir}")

                # Signal main thread that initialization is complete
                self.after(0, lambda: self._qa_init_complete(True, None))

            except Exception as e:
                debug_log(f"[MainWindow] Q&A initialization error: {e}")
                self.after(0, lambda: self._qa_init_complete(False, str(e)))

        # Start background thread
        init_thread = threading.Thread(target=initialize_qa, daemon=True)
        init_thread.start()

    def _qa_init_complete(self, success: bool, error: str | None):
        """Called when Q&A initialization (embeddings + vector store) completes."""
        if not success:
            self.set_status(f"Q&A error: {error[:50] if error else 'Unknown'}...")
            self._completed_tasks.add('qa')
            if self._pending_tasks.get('summary'):
                self._start_summary_task()
            else:
                self._finalize_tasks()
            return

        self.set_status("Q&A: Building vector store...")

        # Create Q&A queue and worker
        self._qa_queue = Queue()
        self._qa_worker = QAWorker(
            vector_store_path=self._vector_store_path,
            embeddings=self._embeddings,
            ui_queue=self._qa_queue,
            answer_mode="extraction"  # Fast extraction mode
        )
        self._qa_worker.start()

        # Start polling Q&A queue
        self.set_status("Q&A: Processing questions...")
        self._poll_qa_queue()

    def _poll_qa_queue(self):
        """Poll the Q&A worker queue for results."""
        try:
            while True:
                msg_type, data = self._qa_queue.get_nowait()
                if msg_type == "qa_progress":
                    current, total, question = data
                    self.set_status(f"Q&A: Processing question {current + 1}/{total}...")
                elif msg_type == "qa_result":
                    # Individual result - could update incrementally
                    pass
                elif msg_type == "qa_complete":
                    self._on_qa_complete(data)
                    return
                elif msg_type == "error":
                    self.set_status(f"Q&A error: {data}")
                    self._on_qa_complete([])
                    return
        except Empty:
            pass

        # Continue polling if worker is alive
        if self._qa_worker and self._qa_worker.is_alive():
            self.after(50, self._poll_qa_queue)
        else:
            # Worker finished - do final poll
            try:
                while True:
                    msg_type, data = self._qa_queue.get_nowait()
                    if msg_type == "qa_complete":
                        self._on_qa_complete(data)
                        return
            except Empty:
                pass
            # Worker finished without sending results
            self._on_qa_complete([])

    def _on_qa_complete(self, qa_results: list):
        """Handle Q&A completion."""
        self._completed_tasks.add('qa')
        self._qa_results = qa_results

        # Display results using update_outputs
        if qa_results:
            self.output_display.update_outputs(qa_results=qa_results)
            self.set_status(f"Q&A: {len(qa_results)} questions answered")
            # Enable follow-up button
            self.followup_btn.configure(state="normal")
        else:
            self.set_status("Q&A complete (no results)")

        # Continue to next task
        if self._pending_tasks.get('summary'):
            self._start_summary_task()
        else:
            self._finalize_tasks()

    def _start_summary_task(self):
        """Start summary generation task."""
        self.set_status("Summary: This feature takes 30+ minutes...")

        # Summary is complex - show placeholder for now
        self._completed_tasks.add('summary')

        self.output_display.update_outputs(
            meta_summary="Summary generation is a long-running task (30+ minutes). "
            "For quick case familiarization, use Q&A instead."
        )

        self._finalize_tasks()

    def _finalize_tasks(self):
        """Finalize all tasks and update UI."""
        completed = len(self._completed_tasks)
        self._on_tasks_complete(True, f"Completed {completed} task(s)")

    def _on_tasks_complete(self, success: bool, message: str):
        """Handle task completion."""
        self._stop_timer()

        # Re-enable controls
        self.add_files_btn.configure(state="normal")
        self._update_generate_button_state()

        # Enable follow-up if Q&A was run
        if self.qa_check.get() and success:
            self.followup_btn.configure(state="normal")

        self.set_status(message)

    def _ask_followup(self):
        """Ask a follow-up question using the Q&A system."""
        question = self.followup_entry.get().strip()
        if not question:
            return

        # Check prerequisites
        if not self._vector_store_path or not self._embeddings:
            messagebox.showwarning("Not Ready", "Please run Q&A first to enable follow-up questions.")
            return

        # Clear entry
        self.followup_entry.delete(0, "end")

        self.set_status(f"Asking: {question[:40]}...")

        try:
            # Import and use QAOrchestrator for follow-up
            from src.qa import QAOrchestrator

            orchestrator = QAOrchestrator(
                vector_store_path=self._vector_store_path,
                embeddings=self._embeddings,
                answer_mode="extraction"
            )

            # Ask the follow-up question
            result = orchestrator.ask_followup(question)

            # Add to existing results and refresh display
            self._qa_results.append(result)
            self.output_display.update_outputs(qa_results=self._qa_results)
            self.set_status(f"Follow-up answered: {len(result.answer)} chars")

        except Exception as e:
            debug_log(f"[MainWindow] Follow-up error: {e}")
            messagebox.showerror("Error", f"Failed to process follow-up: {str(e)}")

    # =========================================================================
    # Settings
    # =========================================================================

    def _open_settings(self):
        """Open the settings dialog."""
        from src.ui.settings.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self, self.model_manager, self.prompt_template_manager)
        dialog.wait_window()

        # Refresh UI after settings change
        self._refresh_corpus_dropdown()
        self._update_corpus_banner()

    # =========================================================================
    # Timer
    # =========================================================================

    def _start_timer(self):
        """Start the processing timer."""
        self._processing_start_time = time.time()
        self._update_timer()

    def _stop_timer(self):
        """Stop the processing timer."""
        if self._timer_after_id:
            self.after_cancel(self._timer_after_id)
            self._timer_after_id = None

        # Keep final time displayed
        if self._processing_start_time:
            elapsed = time.time() - self._processing_start_time
            self._format_timer(elapsed)

    def _update_timer(self):
        """Update the timer display."""
        if self._processing_start_time:
            elapsed = time.time() - self._processing_start_time
            self._format_timer(elapsed)
            self._timer_after_id = self.after(1000, self._update_timer)

    def _format_timer(self, seconds: float):
        """Format and display the timer."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        self.timer_label.configure(text=f"⏱ {minutes}:{secs:02d}")

    # =========================================================================
    # Status Bar
    # =========================================================================

    def set_status(self, message: str):
        """Update the status bar message."""
        self.status_label.configure(text=message)
        if DEBUG_MODE:
            debug_log(f"[MainWindow] Status: {message}")

    # =========================================================================
    # Startup Checks
    # =========================================================================

    def _check_ollama_service(self):
        """Check if Ollama service is running on startup."""
        try:
            self.model_manager.health_check()
            debug_log("[MainWindow] Ollama service is accessible")
        except Exception as e:
            debug_log(f"[MainWindow] Ollama service not accessible: {e}")

            # Show warning
            messagebox.showwarning(
                "Ollama Not Found",
                "Ollama service is not running.\n\n"
                "LocalScribe requires Ollama for Q&A and summaries.\n\n"
                "To install: Visit https://ollama.ai\n"
                "To start: Run 'ollama serve' in a terminal\n\n"
                "Vocabulary extraction will still work without Ollama."
            )

    # =========================================================================
    # Cleanup
    # =========================================================================

    def destroy(self):
        """Clean up resources before destroying window."""
        # Stop queue polling
        if self._queue_poll_id:
            self.after_cancel(self._queue_poll_id)
            self._queue_poll_id = None

        # Stop any running workers
        if self._processing_worker and self._processing_worker.is_alive():
            # Worker is a daemon thread, will stop when main thread exits
            pass
        if self._vocabulary_worker and hasattr(self._vocabulary_worker, 'is_alive') and self._vocabulary_worker.is_alive():
            pass

        # Stop timer
        self._stop_timer()

        super().destroy()
