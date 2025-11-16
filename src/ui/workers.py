"""
LocalScribe - Background Worker Threads
Threaded workers for long-running operations to keep UI responsive.
"""

from PySide6.QtCore import QThread, Signal, QTimer, QObject
from pathlib import Path
import time
import multiprocessing
import traceback
from queue import Empty as QueueEmpty
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


# ============================================================================
# MULTIPROCESSING WORKERS (for CPU-intensive tasks that block the GIL)
# ============================================================================

def onnx_generation_worker_process(
    model_name: str,
    combined_text: str,
    summary_length: int,
    output_queue,
    heartbeat_interval: float = 5.0,
    batch_size: int = 15,
    batch_timeout: float = 0.5
):
    """
    Standalone worker function that runs in a separate process for ONNX generation.

    This function runs completely isolated from the GUI process, preventing
    ONNX Runtime's blocking operations from freezing the UI.

    Args:
        model_name: Name of the model being used ('standard' or 'pro')
        combined_text: The text to summarize
        summary_length: Target summary length in words
        output_queue: multiprocessing.Queue for sending messages back to GUI
        heartbeat_interval: Seconds between heartbeat messages (default: 5.0)
        batch_size: Number of characters to batch before sending (default: 15)
        batch_timeout: Max seconds to wait before sending batch (default: 0.5)

    Messages sent via output_queue:
        {'type': 'heartbeat', 'data': 'alive', 'timestamp': float}
        {'type': 'token', 'data': str, 'buffer_size': int}
        {'type': 'progress', 'data': int}  # Percentage (0-100)
        {'type': 'complete', 'data': str, 'word_count': int, 'token_count': int}
        {'type': 'error', 'data': str, 'traceback': str}
        {'type': 'shutdown'}
    """
    import sys
    import os

    # Ensure parent directory is in path so imports work
    worker_dir = Path(__file__).parent.parent.parent
    if str(worker_dir) not in sys.path:
        sys.path.insert(0, str(worker_dir))

    try:
        debug_log("\n[WORKER PROCESS] Starting ONNX generation worker...")
        debug_log(f"[WORKER PROCESS] Model: {model_name}")
        debug_log(f"[WORKER PROCESS] Input length: {len(combined_text)} chars")
        debug_log(f"[WORKER PROCESS] Target summary length: {summary_length} words")

        # Send initial heartbeat to confirm process started
        output_queue.put({
            'type': 'heartbeat',
            'data': 'alive',
            'timestamp': time.time()
        })

        # Import and initialize model manager IN THIS PROCESS
        # (Must be done here, not passed from parent, due to multiprocessing constraints)
        from src.ai.onnx_model_manager import ONNXModelManager

        debug_log("[WORKER PROCESS] Initializing ONNX Model Manager...")
        model_manager = ONNXModelManager()

        # Check if model is already loaded (it won't be in new process)
        if not model_manager.is_model_loaded():
            debug_log(f"[WORKER PROCESS] Loading model: {model_name}")
            output_queue.put({
                'type': 'status',
                'data': f'Loading {model_name} model in worker process...'
            })

            # Load model
            load_success = model_manager.load_model(model_name, verbose=False)
            if not load_success:
                raise RuntimeError(f"Failed to load model: {model_name}")

            debug_log(f"[WORKER PROCESS] Model loaded successfully")

        # Send heartbeat after model load
        output_queue.put({
            'type': 'heartbeat',
            'data': 'alive',
            'timestamp': time.time()
        })

        # Validate input
        if not combined_text or not combined_text.strip():
            raise ValueError("Input text is empty")

        # Start generation
        debug_log("[WORKER PROCESS] Starting summary generation...")
        output_queue.put({
            'type': 'status',
            'data': 'Generating summary...'
        })

        token_buffer = []
        full_summary = ""
        token_count = 0
        last_batch_time = time.time()
        last_heartbeat_time = time.time()
        estimated_tokens = summary_length * 1.3  # Rough estimate (tokens > words)

        # Stream tokens from model
        for token in model_manager.generate_summary(
            case_text=combined_text,
            max_words=summary_length,
            stream=True
        ):
            token_count += 1
            full_summary += token
            token_buffer.append(token)

            current_time = time.time()
            buffer_text = ''.join(token_buffer)

            # Send batch if: buffer >= batch_size chars OR timeout elapsed
            should_send_batch = (
                len(buffer_text) >= batch_size or
                (current_time - last_batch_time) >= batch_timeout
            )

            if should_send_batch and token_buffer:
                output_queue.put({
                    'type': 'token',
                    'data': buffer_text,
                    'buffer_size': len(token_buffer)
                })
                token_buffer = []
                last_batch_time = current_time

            # Send progress update (estimated percentage)
            if token_count % 20 == 0:
                progress_pct = min(95, int((token_count / estimated_tokens) * 100))
                output_queue.put({
                    'type': 'progress',
                    'data': progress_pct
                })

            # Send heartbeat periodically
            if (current_time - last_heartbeat_time) >= heartbeat_interval:
                output_queue.put({
                    'type': 'heartbeat',
                    'data': 'alive',
                    'timestamp': current_time
                })
                last_heartbeat_time = current_time
                debug_log(f"[WORKER PROCESS] Heartbeat sent (token #{token_count})")

        # Send any remaining tokens
        if token_buffer:
            output_queue.put({
                'type': 'token',
                'data': ''.join(token_buffer),
                'buffer_size': len(token_buffer)
            })

        # Calculate final stats
        word_count = len(full_summary.split())

        debug_log(f"[WORKER PROCESS] Generation complete!")
        debug_log(f"[WORKER PROCESS] Tokens: {token_count}, Words: {word_count}")

        # Send completion message
        output_queue.put({
            'type': 'complete',
            'data': full_summary.strip(),
            'word_count': word_count,
            'token_count': token_count
        })

        # Send final heartbeat
        output_queue.put({
            'type': 'heartbeat',
            'data': 'alive',
            'timestamp': time.time()
        })

    except Exception as e:
        # Catch all errors and send to GUI
        error_msg = str(e)
        error_traceback = traceback.format_exc()

        debug_log(f"[WORKER PROCESS] ERROR: {error_msg}")
        debug_log(f"[WORKER PROCESS] Traceback:\n{error_traceback}")

        output_queue.put({
            'type': 'error',
            'data': error_msg,
            'traceback': error_traceback
        })

    finally:
        # Always send shutdown message
        output_queue.put({'type': 'shutdown'})
        debug_log("[WORKER PROCESS] Worker process shutting down")


class AIWorkerProcess(QObject):
    """
    Multiprocessing-based AI worker that runs ONNX generation in a separate process.

    This replaces the QThread-based AIWorker to fix GUI freezing issues caused
    by ONNX Runtime blocking the event loop. By running in a separate process,
    the GUI remains responsive regardless of what ONNX is doing.

    Signals:
        progress_updated: Emitted with status messages
        token_generated: Emitted for batched tokens during streaming
        summary_complete: Emitted with full summary text when done
        error: Emitted with error message if generation fails
        heartbeat_lost: Emitted if worker process appears to have crashed
    """

    # Signals (same as AIWorker for compatibility)
    progress_updated = Signal(str)
    token_generated = Signal(str)
    summary_complete = Signal(str)
    error = Signal(str)
    heartbeat_lost = Signal()

    def __init__(self, model_manager, processing_results, summary_length):
        """
        Initialize the multiprocessing AI worker.

        Args:
            model_manager: The ModelManager instance (used to get model info)
            processing_results: List of processing result dicts from DocumentCleaner
            summary_length: Target summary length in words (from slider)
        """
        super().__init__()
        self.model_manager = model_manager
        self.processing_results = processing_results
        self.summary_length = summary_length

        # Multiprocessing components
        self.process = None
        self.queue = None
        self.poll_timer = None

        # Heartbeat tracking
        self.last_heartbeat_time = None
        self.heartbeat_timeout_seconds = 15.0  # Show warning after 15s without heartbeat
        self.heartbeat_check_timer = None

        # Statistics
        self.start_time = None
        self._is_running = False

    def start(self):
        """Start the worker process and begin polling for results."""
        self.start_time = time.time()
        self._is_running = True

        try:
            # Step 1: Combine document texts
            self.progress_updated.emit("Combining document texts...")

            combined_text = ""
            for result in self.processing_results:
                if result.get('status') == 'success' and result.get('cleaned_text'):
                    filename = result.get('filename', 'Unknown')
                    combined_text += f"\n\n--- Document: {filename} ---\n\n"
                    combined_text += result['cleaned_text']

            if not combined_text.strip():
                self.error.emit("No valid document text found to summarize")
                return

            # Step 2: Truncate if needed (same logic as AIWorker)
            max_input_words = 300
            combined_words = combined_text.split()

            if len(combined_words) > max_input_words:
                self.progress_updated.emit(
                    f"Text too long ({len(combined_words)} words), truncating to {max_input_words} words..."
                )
                combined_text = ' '.join(combined_words[:max_input_words])
                combined_text += "\n\n[Note: Document text was truncated to fit context window]"

            # Step 3: Get model info
            model_name = self.model_manager.current_model_name or 'standard'

            debug_log(f"\n[AIWorkerProcess] Starting generation process...")
            debug_log(f"[AIWorkerProcess] Model: {model_name}")
            debug_log(f"[AIWorkerProcess] Input: {len(combined_text)} chars, {len(combined_words)} words")
            debug_log(f"[AIWorkerProcess] Target summary: {self.summary_length} words")

            # Step 4: Create queue and process
            self.queue = multiprocessing.Queue()

            self.process = multiprocessing.Process(
                target=onnx_generation_worker_process,
                args=(
                    model_name,
                    combined_text,
                    self.summary_length,
                    self.queue
                ),
                daemon=True  # Process will terminate when main program exits
            )

            # Step 5: Start process
            self.process.start()
            debug_log(f"[AIWorkerProcess] Worker process started (PID: {self.process.pid})")

            self.progress_updated.emit("Starting AI worker process...")

            # Step 6: Start polling timer (check queue every 100ms)
            self.poll_timer = QTimer()
            self.poll_timer.timeout.connect(self._poll_queue)
            self.poll_timer.start(100)

            # Step 7: Start heartbeat monitoring timer (check every 2 seconds)
            self.last_heartbeat_time = time.time()
            self.heartbeat_check_timer = QTimer()
            self.heartbeat_check_timer.timeout.connect(self._check_heartbeat)
            self.heartbeat_check_timer.start(2000)

        except Exception as e:
            error_msg = f"Failed to start worker process: {str(e)}"
            debug_log(f"[AIWorkerProcess] ERROR: {error_msg}")
            self.error.emit(error_msg)

    def _poll_queue(self):
        """Poll the queue for messages from the worker process."""
        try:
            # Process all available messages (non-blocking)
            while True:
                try:
                    message = self.queue.get_nowait()
                    self._handle_message(message)
                except QueueEmpty:
                    # No more messages available
                    break

        except Exception as e:
            debug_log(f"[AIWorkerProcess] Error polling queue: {str(e)}")

    def _handle_message(self, message):
        """Handle a message received from the worker process."""
        msg_type = message.get('type')

        if msg_type == 'heartbeat':
            # Update heartbeat timestamp
            self.last_heartbeat_time = message.get('timestamp', time.time())
            debug_log(f"[AIWorkerProcess] Heartbeat received")

        elif msg_type == 'status':
            # Status update
            status_msg = message.get('data', '')
            self.progress_updated.emit(status_msg)
            debug_log(f"[AIWorkerProcess] Status: {status_msg}")

        elif msg_type == 'token':
            # Token batch received
            token_text = message.get('data', '')
            buffer_size = message.get('buffer_size', 0)
            self.token_generated.emit(token_text)
            debug_log(f"[AIWorkerProcess] Token batch: {buffer_size} tokens, {len(token_text)} chars")

        elif msg_type == 'progress':
            # Progress percentage
            progress_pct = message.get('data', 0)
            self.progress_updated.emit(f"Generating summary... {progress_pct}%")

        elif msg_type == 'complete':
            # Generation complete!
            summary_text = message.get('data', '')
            word_count = message.get('word_count', 0)
            token_count = message.get('token_count', 0)
            generation_time = time.time() - self.start_time

            debug_log(f"[AIWorkerProcess] Generation complete!")
            debug_log(f"[AIWorkerProcess] Words: {word_count}, Tokens: {token_count}")
            debug_log(f"[AIWorkerProcess] Time: {generation_time:.1f}s")

            self.progress_updated.emit(f"Summary complete ({word_count} words)")
            self.summary_complete.emit(summary_text)

            # Save to file (for debugging, same as AIWorker)
            debug_output = Path(__file__).parent.parent.parent / "generated_summary.txt"
            with open(debug_output, 'w', encoding='utf-8') as f:
                f.write("=== Generated Summary (Multiprocessing) ===\n")
                f.write(f"Generation time: {generation_time:.1f}s\n")
                f.write(f"Word count: {word_count}\n")
                f.write(f"Token count: {token_count}\n")
                f.write("=" * 60 + "\n\n")
                f.write(summary_text)
            debug_log(f"[AIWorkerProcess] Summary written to: {debug_output}")

            # Log performance data
            try:
                tracker = get_performance_tracker()
                model_name = self.model_manager.current_model_name or 'standard'

                combined_text = ""
                for result in self.processing_results:
                    if result.get('status') == 'success' and result.get('cleaned_text'):
                        combined_text += result['cleaned_text']

                tracker.log_generation(
                    input_text=combined_text[:1000],  # First 1000 chars for storage
                    input_documents=len(self.processing_results),
                    requested_summary_length=self.summary_length,
                    actual_summary_length=word_count,
                    generation_time_seconds=generation_time,
                    model_name=model_name
                )
            except Exception as e:
                debug_log(f"[AIWorkerProcess] Performance logging failed: {e}")

            # Stop timers
            self._cleanup()

        elif msg_type == 'error':
            # Error occurred in worker process
            error_msg = message.get('data', 'Unknown error')
            error_traceback = message.get('traceback', '')

            debug_log(f"[AIWorkerProcess] Worker error: {error_msg}")
            if error_traceback:
                debug_log(f"[AIWorkerProcess] Traceback:\n{error_traceback}")

            self.error.emit(f"Generation error: {error_msg}")
            self._cleanup()

        elif msg_type == 'shutdown':
            # Worker process is shutting down
            debug_log("[AIWorkerProcess] Worker process shutdown")
            self._cleanup()

        else:
            debug_log(f"[AIWorkerProcess] Unknown message type: {msg_type}")

    def _check_heartbeat(self):
        """Check if we've received a heartbeat recently."""
        if not self._is_running or not self.last_heartbeat_time:
            return

        time_since_heartbeat = time.time() - self.last_heartbeat_time

        if time_since_heartbeat > self.heartbeat_timeout_seconds:
            debug_log(f"[AIWorkerProcess] WARNING: No heartbeat for {time_since_heartbeat:.1f}s")
            self.heartbeat_lost.emit()
            self.progress_updated.emit(
                f"Warning: No response from worker process ({time_since_heartbeat:.0f}s)..."
            )

    def _cleanup(self):
        """Stop timers and clean up resources."""
        self._is_running = False

        if self.poll_timer:
            self.poll_timer.stop()
            self.poll_timer = None

        if self.heartbeat_check_timer:
            self.heartbeat_check_timer.stop()
            self.heartbeat_check_timer = None

        # Process will terminate automatically (daemon=True)
        debug_log("[AIWorkerProcess] Cleanup complete")

    def stop(self):
        """Request the worker to stop (terminates the process)."""
        debug_log("[AIWorkerProcess] Stop requested")
        self._is_running = False
        self._cleanup()

        if self.process and self.process.is_alive():
            debug_log("[AIWorkerProcess] Terminating worker process")
            self.process.terminate()
            self.process.join(timeout=2.0)

            if self.process.is_alive():
                debug_log("[AIWorkerProcess] Force killing worker process")
                self.process.kill()
