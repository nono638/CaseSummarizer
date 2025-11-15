"""
LocalScribe - Background Worker Threads
Threaded workers for long-running operations to keep UI responsive.
"""

from PySide6.QtCore import QThread, Signal
from pathlib import Path
import time
from src.performance_tracker import get_performance_tracker
from src.debug_logger import debug_log


class ModelLoadWorker(QThread):
    """
    Background worker thread for loading AI models.

    Since llama-cpp-python doesn't provide loading progress callbacks,
    this worker simply runs the load operation off the main thread
    and emits signals when complete.

    Signals:
        progress: Emitted periodically with elapsed time (for timer display)
        success: Emitted when model loads successfully
        error: Emitted with error message if loading fails
    """

    # Signals
    progress = Signal(float)  # Elapsed time in seconds
    success = Signal()
    error = Signal(str)

    def __init__(self, model_manager, model_type):
        """
        Initialize the worker.

        Args:
            model_manager: The ModelManager instance
            model_type: Either 'standard' or 'pro'
        """
        super().__init__()
        self.model_manager = model_manager
        self.model_type = model_type
        self._is_running = True

    def run(self):
        """Execute model loading in background thread."""
        start_time = time.time()

        try:
            # Start a timer to emit progress updates every 0.5 seconds
            # This allows the UI to display elapsed time
            last_update = start_time

            # We need to run load_model() while also emitting progress
            # Since load_model() is blocking, we'll run it in a way that
            # the progress signal gets emitted

            # Start the actual loading (this is the blocking operation)
            # Note: We can't emit progress during load_model itself,
            # but we'll emit final time when done

            load_result = self.model_manager.load_model(
                self.model_type,
                verbose=False
            )

            # Calculate total time
            elapsed = time.time() - start_time
            self.progress.emit(elapsed)

            if load_result:
                self.success.emit()
            else:
                self.error.emit(f"Failed to load {self.model_type} model")

        except Exception as e:
            elapsed = time.time() - start_time
            self.progress.emit(elapsed)
            self.error.emit(f"Error loading model: {str(e)}")

    def stop(self):
        """Request the worker to stop (for future cancellation support)."""
        self._is_running = False


class ModelLoadWorkerWithTimer(QThread):
    """
    Enhanced model loading worker that emits periodic progress updates.

    This version uses a separate timer to emit progress signals while
    the model is loading, allowing the UI to show elapsed time.

    Signals:
        progress: Emitted every 0.1 seconds with elapsed time
        success: Emitted when model loads successfully
        error: Emitted with error message if loading fails
    """

    # Signals
    progress = Signal(float)  # Elapsed time in seconds
    success = Signal()
    error = Signal(str)

    def __init__(self, model_manager, model_type):
        """
        Initialize the worker.

        Args:
            model_manager: The ModelManager instance
            model_type: Either 'standard' or 'pro'
        """
        super().__init__()
        self.model_manager = model_manager
        self.model_type = model_type
        self._is_running = True
        self._start_time = None

    def run(self):
        """Execute model loading with periodic progress updates."""
        self._start_time = time.time()
        self._is_running = True

        # We need to run load_model in a way that allows us to emit progress
        # Unfortunately, load_model is blocking, so we'll use a different approach:
        # Run it directly but use QTimer in the main thread for progress

        # Actually, since this is already in a QThread, we can't easily
        # emit progress during the blocking call. Instead, we'll just
        # load and emit final time.

        # Better approach: Emit progress from main thread using QTimer
        # This worker just does the loading

        try:
            load_result = self.model_manager.load_model(
                self.model_type,
                verbose=False
            )

            elapsed = time.time() - self._start_time
            self.progress.emit(elapsed)

            if load_result:
                self.success.emit()
            else:
                self.error.emit(f"Failed to load {self.model_type} model")

        except Exception as e:
            if self._start_time:
                elapsed = time.time() - self._start_time
                self.progress.emit(elapsed)
            self.error.emit(f"Error loading model: {str(e)}")


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
        from src.cleaner import DocumentCleaner
        import os

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


class AIWorker(QThread):
    """
    Background worker thread for AI summary generation with streaming.

    This worker combines multiple cleaned document texts and generates
    a single case-level summary using the loaded AI model.

    Signals:
        progress_updated: Emitted with status messages
        token_generated: Emitted for each token during streaming (for real-time display)
        summary_complete: Emitted with full summary text when done
        error: Emitted with error message if generation fails
    """

    # Signals
    progress_updated = Signal(str)  # Status message
    token_generated = Signal(str)  # Individual token for streaming display
    summary_complete = Signal(str)  # Complete summary text
    error = Signal(str)  # Error message

    def __init__(self, model_manager, processing_results, summary_length):
        """
        Initialize the AI worker.

        Args:
            model_manager: The ModelManager instance
            processing_results: List of processing result dicts from DocumentCleaner
            summary_length: Target summary length in words (from slider)
        """
        super().__init__()
        self.model_manager = model_manager
        self.processing_results = processing_results
        self.summary_length = summary_length
        self._is_running = True
        self._combined_text = ""  # Store for performance logging

    def run(self):
        """Execute AI summary generation in background thread."""
        start_time = time.time()

        try:
            # Step 1: Combine cleaned texts from all documents
            self.progress_updated.emit("Combining document texts...")

            combined_text = ""
            for result in self.processing_results:
                if result.get('status') == 'success' and result.get('cleaned_text'):
                    # Add document separator with filename
                    filename = result.get('filename', 'Unknown')
                    combined_text += f"\n\n--- Document: {filename} ---\n\n"
                    combined_text += result['cleaned_text']

            if not combined_text.strip():
                self.error.emit("No valid document text found to summarize")
                return

            # Store combined text for performance logging
            self._combined_text = combined_text

            # Step 1.5: Truncate text to fit context window AND reasonable CPU processing time
            # Context window: 4096 tokens (Phi-3 Mini) or 8192 (Gemma 2)
            # Reserve: 500 tokens for prompt, 800 tokens for output
            # ONNX DirectML performance: Start conservative with 300 words for testing
            # Can increase after confirming stability
            max_input_words = 300
            combined_words = combined_text.split()

            if len(combined_words) > max_input_words:
                self.progress_updated.emit(
                    f"Text too long ({len(combined_words)} words), truncating to {max_input_words} words..."
                )
                # Truncate and add notice
                combined_text = ' '.join(combined_words[:max_input_words])
                combined_text += "\n\n[Note: Document text was truncated to fit context window]"
                self._combined_text = combined_text  # Update stored text

            # Step 2: Generate summary with streaming
            # Note: With Phi-3, first token takes 10-45 seconds; with Gemma 2 on CPU, 5-10 minutes
            final_word_count = len(combined_text.split())

            # DEBUG: Log what we're sending to the model
            debug_log("\n=== DEBUG: Text being sent to model ===")
            debug_log(f"Word count: {final_word_count}")
            debug_log(f"Character count: {len(combined_text)}")
            debug_log(f"First 500 chars:\n{combined_text[:500]}")
            debug_log(f"Last 200 chars:\n{combined_text[-200:]}")
            debug_log("=== END DEBUG ===\n")

            self.progress_updated.emit(
                f"Processing {final_word_count} words of input... (first words may take 15-60 seconds)"
            )

            full_summary = ""
            token_count = 0

            # Stream tokens from the model
            first_token = True
            debug_log("\n[WORKER] About to call generate_summary()...")
            debug_log(f"[WORKER] Parameters: max_words={self.summary_length}, stream=True")

            for token in self.model_manager.generate_summary(
                case_text=combined_text,
                max_words=self.summary_length,
                stream=True
            ):
                if not self._is_running:
                    debug_log("[WORKER] Generation cancelled by user")
                    self.error.emit("Summary generation cancelled")
                    return

                # First token received - update status to show streaming has started
                if first_token:
                    debug_log(f"[WORKER] *** FIRST TOKEN RECEIVED! *** Token: '{token}'")
                    self.progress_updated.emit(f"Generating {self.summary_length}-word summary...")
                    first_token = False

                # Emit token for real-time display
                if token_count < 10 or token_count % 20 == 0:
                    debug_log(f"[WORKER] Token #{token_count}: '{token}'")
                self.token_generated.emit(token)
                full_summary += token
                token_count += 1

                # Update progress periodically
                if token_count % 10 == 0:
                    word_count = len(full_summary.split())
                    debug_log(f"[WORKER] Progress update: {word_count} words, {token_count} tokens")
                    self.progress_updated.emit(
                        f"Generating summary... ({word_count} words so far)"
                    )

            # Step 3: Emit complete summary
            word_count = len(full_summary.split())
            generation_time = time.time() - start_time

            self.progress_updated.emit(f"Summary complete ({word_count} words)")

            # DEBUG: Write summary to file for verification
            from pathlib import Path
            debug_output = Path(__file__).parent.parent.parent / "generated_summary.txt"
            with open(debug_output, 'w', encoding='utf-8') as f:
                f.write("=== Generated Summary ===\n")
                f.write(f"Generation time: {generation_time:.1f}s\n")
                f.write(f"Word count: {word_count}\n")
                f.write(f"Token count: {token_count}\n")
                f.write("=" * 60 + "\n\n")
                f.write(full_summary.strip())
            debug_log(f"\n[WORKER] Summary written to: {debug_output}")

            self.summary_complete.emit(full_summary.strip())

            # Step 4: Log performance data for future predictions
            try:
                tracker = get_performance_tracker()
                model_name = self.model_manager.current_model_name or 'standard'

                tracker.log_generation(
                    input_text=self._combined_text,
                    input_documents=len(self.processing_results),
                    requested_summary_length=self.summary_length,
                    actual_summary_length=word_count,
                    generation_time_seconds=generation_time,
                    model_name=model_name
                )
            except Exception as e:
                # Don't fail the whole operation if logging fails
                print(f"Performance logging failed: {e}")

        except Exception as e:
            import traceback
            error_details = f"Error generating summary: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_details)

    def stop(self):
        """Request the worker to stop generating."""
        self._is_running = False
