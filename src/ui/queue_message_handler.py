"""
Queue Message Handler Module

Centralizes handling of inter-thread messages from worker threads.
Decouples message type handling from main window event loop.
"""

from tkinter import messagebox
from src.debug_logger import debug_log


class QueueMessageHandler:
    """
    Handles different message types from worker threads.

    This class encapsulates all queue message handling logic, making it easier
    to test, extend, and maintain message-handling behavior separately from
    the main window event loop.
    """

    def __init__(self, main_window):
        """
        Initialize the message handler.

        Args:
            main_window: Reference to MainWindow instance (for widget updates)
        """
        self.main_window = main_window

    def handle_progress(self, data):
        """
        Handle 'progress' message from worker thread.

        Args:
            data: Tuple of (percentage, message)
        """
        percentage, message = data
        self.main_window.progress_bar.set(percentage / 100.0)
        self.main_window.status_label.configure(text=message)

    def handle_file_processed(self, data):
        """
        Handle 'file_processed' message when a document is done.

        Args:
            data: Result dictionary with filename, status, confidence, etc.
        """
        self.main_window.processed_results.append(data)
        self.main_window.file_table.add_result(data)

        # If individual document summary is available, display it
        if data.get('summary'):
            self.main_window.summary_results.update_outputs(
                document_summaries={data['filename']: data['summary']}
            )

    def handle_meta_summary_generated(self, data):
        """
        Handle 'meta_summary_generated' message.

        Args:
            data: The meta-summary text
        """
        self.main_window.summary_results.update_outputs(meta_summary=data)

    def handle_vocab_csv_generated(self, data):
        """
        Handle 'vocab_csv_generated' message.

        Args:
            data: List of vocabulary CSV rows
        """
        self.main_window.summary_results.update_outputs(vocab_csv_data=data)

    def handle_processing_finished(self, data):
        """
        Handle 'processing_finished' message when document extraction is done.

        Args:
            data: List of extracted documents
        """
        extracted_documents = data

        # If AI generation was requested, start it now
        if self.main_window.pending_ai_generation:
            # Check if vocabulary extraction is needed
            output_options = {
                "individual_summaries": self.main_window.output_options.individual_summaries_check.get(),
                "meta_summary": self.main_window.output_options.meta_summary_check.get(),
                "vocab_csv": self.main_window.output_options.vocab_csv_check.get()
            }

            # Start vocabulary extraction in parallel (if checkbox enabled)
            if output_options.get('vocab_csv', False):
                combined_text = self.main_window._combine_documents(extracted_documents)
                self._start_vocab_extraction(combined_text)

            # Start AI generation (parallel processing)
            self.main_window._start_ai_generation(
                extracted_documents,
                self.main_window.pending_ai_generation
            )
        else:
            # No AI generation, just finish up
            self._reset_ui_after_processing()
            self.main_window.status_label.configure(text="Processing complete.")

    def _start_vocab_extraction(self, combined_text):
        """Start vocabulary extraction in background thread."""
        from src.ui.workers import VocabularyWorker

        worker = VocabularyWorker(
            combined_text=combined_text,
            ui_queue=self.main_window.ui_queue,
            exclude_list_path="config/legal_exclude.txt",
            medical_terms_path="config/medical_terms.txt"
        )
        worker.start()
        debug_log("[QUEUE HANDLER] Started vocabulary extraction worker thread.")

    def handle_summary_result(self, data):
        """
        Handle 'summary_result' message when AI summary is generated.

        Args:
            data: Dictionary with 'summary' key
        """
        debug_log(f"[QUEUE HANDLER] Summary result received: {data}")
        self.main_window.summary_results.update_outputs(meta_summary=data.get('summary', ''))
        self.main_window.progress_bar.set(1.0)
        self.main_window.status_label.configure(text="Summary generation complete!")
        self._reset_ui_after_processing()
        self.main_window.pending_ai_generation = None

    def handle_error(self, error_message):
        """
        Handle 'error' message when processing fails.

        Args:
            error_message: Description of the error
        """
        messagebox.showerror("Processing Error", error_message)
        self._reset_ui_after_processing()
        self.main_window.pending_ai_generation = None

    def _reset_ui_after_processing(self):
        """Reset UI buttons and progress bar to post-processing state."""
        self.main_window.select_files_btn.configure(state="normal")
        self.main_window.generate_outputs_btn.configure(state="normal")
        self.main_window.progress_bar.grid_remove()

    def process_message(self, message_type, data):
        """
        Route a message to the appropriate handler.

        Args:
            message_type: Type of message (str)
            data: Message payload

        Returns:
            True if message was handled, False otherwise
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

        return False
