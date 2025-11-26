"""
Queue Message Handler Module

Routes inter-thread messages from worker threads to appropriate UI update handlers.
This module is responsible for UI updates ONLY - workflow orchestration logic
is delegated to WorkflowOrchestrator.

Design Principle: Single Responsibility
- QueueMessageHandler: Routes messages and updates UI widgets
- WorkflowOrchestrator: Decides what workflow steps to execute next

Message Types Handled:
- progress: Update progress bar and status label
- file_processed: Add/update file in results table
- meta_summary_generated: Display generated meta-summary
- vocab_csv_generated: Store vocabulary CSV data
- processing_finished: Delegate to orchestrator, then update UI
- summary_result: Display AI-generated summary
- error: Show error dialog and reset UI
"""

from tkinter import messagebox
from src.logging_config import debug_log


class QueueMessageHandler:
    """
    Routes queue messages to appropriate UI update handlers.

    This class encapsulates all UI update logic for worker thread messages,
    making it easier to test and maintain message-handling behavior.

    For workflow orchestration (deciding what to do next), see WorkflowOrchestrator.

    Attributes:
        main_window: Reference to MainWindow instance
        orchestrator: Reference to WorkflowOrchestrator instance
    """

    def __init__(self, main_window):
        """
        Initialize the message handler.

        Args:
            main_window: Reference to MainWindow instance (for widget updates)
        """
        self.main_window = main_window
        # Orchestrator is set by main_window after construction
        self.orchestrator = None

    def set_orchestrator(self, orchestrator):
        """
        Set the workflow orchestrator reference.

        Called by MainWindow after both handler and orchestrator are created.

        Args:
            orchestrator: WorkflowOrchestrator instance
        """
        self.orchestrator = orchestrator

    def handle_progress(self, data):
        """
        Handle 'progress' message - update progress bar and status.

        Args:
            data: Tuple of (percentage: int, message: str)
        """
        percentage, message = data
        self.main_window.progress_bar.set(percentage / 100.0)
        self.main_window.status_label.configure(text=message)

    def handle_file_processed(self, data):
        """
        Handle 'file_processed' message - update file table with result.

        Args:
            data: Result dictionary with filename, status, confidence, etc.
        """
        self.main_window.processed_results.append(data)
        self.main_window.file_table.add_result(data)

        # Display individual document summary if available
        if data.get('summary'):
            self.main_window.summary_results.update_outputs(
                document_summaries={data['filename']: data['summary']}
            )

    def handle_meta_summary_generated(self, data):
        """
        Handle 'meta_summary_generated' message - display meta-summary.

        Args:
            data: The meta-summary text string
        """
        self.main_window.summary_results.update_outputs(meta_summary=data)

    def handle_vocab_csv_generated(self, data):
        """
        Handle 'vocab_csv_generated' message - store vocabulary data.

        Args:
            data: List of vocabulary term dictionaries
        """
        self.main_window.summary_results.update_outputs(vocab_csv_data=data)
        if self.orchestrator:
            self.orchestrator.on_vocab_complete()

    def handle_processing_finished(self, data):
        """
        Handle 'processing_finished' message - document extraction complete.

        Delegates workflow decisions to the orchestrator, then updates UI
        based on what actions were taken.

        Args:
            data: List of extracted document result dictionaries
        """
        extracted_documents = data

        if self.orchestrator and self.main_window.pending_ai_generation:
            # Delegate to orchestrator for workflow decisions
            actions = self.orchestrator.on_extraction_complete(
                extracted_documents,
                self.main_window.pending_ai_generation
            )

            # If workflow completed without AI (shouldn't happen normally)
            if actions.get('workflow_complete'):
                self._reset_ui_after_processing()
                self.main_window.status_label.configure(text="Processing complete.")
        elif self.main_window.pending_ai_generation:
            # Fallback if orchestrator not set (backward compatibility)
            debug_log("[QUEUE HANDLER] WARNING: Orchestrator not set, using fallback.")
            self.main_window._start_ai_generation(
                extracted_documents,
                self.main_window.pending_ai_generation
            )
        else:
            # No AI generation requested
            self._reset_ui_after_processing()
            self.main_window.status_label.configure(text="Processing complete.")

    def handle_summary_result(self, data):
        """
        Handle 'summary_result' message - AI summary generated.

        Args:
            data: Dictionary with 'summary' key containing the generated text
        """
        debug_log(f"[QUEUE HANDLER] Summary result received.")
        self.main_window.summary_results.update_outputs(
            meta_summary=data.get('summary', '')
        )
        self.main_window.progress_bar.set(1.0)
        self.main_window.status_label.configure(text="Summary generation complete!")
        self._reset_ui_after_processing()
        self.main_window.pending_ai_generation = None

        if self.orchestrator:
            self.orchestrator.on_summary_complete()

    def handle_error(self, error_message):
        """
        Handle 'error' message - show error dialog and reset UI.

        Args:
            error_message: Description of the error to display
        """
        messagebox.showerror("Processing Error", error_message)
        self._reset_ui_after_processing()
        self.main_window.pending_ai_generation = None

    def _reset_ui_after_processing(self):
        """Reset UI buttons and progress bar to post-processing state."""
        self.main_window.select_files_btn.configure(state="normal")
        self.main_window.generate_outputs_btn.configure(state="normal")
        self.main_window.progress_bar.grid_remove()

    def process_message(self, message_type: str, data) -> bool:
        """
        Route a message to the appropriate handler.

        Args:
            message_type: Type of message (e.g., 'progress', 'error')
            data: Message payload (type varies by message_type)

        Returns:
            True if message was handled successfully, False otherwise
        """
        handlers = {
            'progress': self.handle_progress,
            'file_processed': self.handle_file_processed,
            'meta_summary_generated': self.handle_meta_summary_generated,
            'vocab_csv_generated': self.handle_vocab_csv_generated,
            'processing_finished': self.handle_processing_finished,
            'summary_result': self.handle_summary_result,
            'error': self.handle_error,
        }

        handler = handlers.get(message_type)
        if handler:
            try:
                handler(data)
                return True
            except Exception as e:
                debug_log(f"[QUEUE HANDLER] Error handling {message_type}: {e}")
                return False

        debug_log(f"[QUEUE HANDLER] Unknown message type: {message_type}")
        return False
