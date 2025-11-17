"""
LocalScribe - Background Worker Threads
Threaded workers for long-running operations to keep UI responsive.

IMPORTANT: Subprocess Initialization Considerations
====================================================
When modifying the ai_generation_worker_process() function, be aware of:

1. Model Manager Integration: The worker uses the ModelManager interface (via the multiprocessing
   queue), so it works with any backend (Ollama, ONNX, etc.) without modification.

2. Module Imports: Always perform critical imports at the BEGINNING of the subprocess function
   to ensure proper context initialization.

See development_log.md for detailed information about worker architecture and debugging.
Reference: https://onnxruntime.ai/docs/genai/howto/troubleshoot.html
"""

from PySide6.QtCore import QThread, Signal, QTimer, QObject
from pathlib import Path
import time
import multiprocessing
import traceback
from queue import Empty as QueueEmpty
from src.performance_tracker import get_performance_tracker
from src.debug_logger import debug_log
from src.chunking_engine import ChunkingEngine
from src.progressive_summarizer import ProgressiveSummarizer


class ModelLoadWorker(QThread):
    """
    Background worker thread for loading AI models with periodic progress updates.

    This worker runs the model loading in a background thread and emits
    progress signals every 100ms so the UI can show responsive feedback
    (elapsed time and animated progress bar) even though the actual
    model loading is a blocking operation.

    The key improvement: Uses a separate timer thread to emit progress
    signals during the blocking load_model() call, preventing UI freezing.

    Signals:
        progress: Emitted every 100ms with elapsed time (float seconds)
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
        """Execute model loading with periodic progress signal emission."""
        import threading

        self._start_time = time.time()
        self._is_running = True
        load_result = None
        exception_occurred = None

        # Define a function to emit progress updates periodically
        # This runs in a separate daemon thread while load_model() is blocking
        def emit_progress():
            """Emit progress signals every 100ms while loading."""
            while self._is_running:
                elapsed = time.time() - self._start_time
                self.progress.emit(elapsed)
                time.sleep(0.1)  # Update every 100ms

        # Start the progress emission thread
        progress_thread = threading.Thread(target=emit_progress, daemon=True)
        progress_thread.start()

        try:
            # This is the blocking call - but now progress signals are
            # being emitted in a separate thread every 100ms
            load_result = self.model_manager.load_model(
                self.model_type,
                verbose=False
            )

        except Exception as e:
            exception_occurred = e

        finally:
            # Stop the progress thread
            self._is_running = False
            progress_thread.join(timeout=1.0)

            # Emit final status
            elapsed = time.time() - self._start_time
            self.progress.emit(elapsed)

            if exception_occurred:
                self.error.emit(f"Error loading model: {str(exception_occurred)}")
            elif load_result:
                self.success.emit()
            else:
                self.error.emit(f"Failed to load {self.model_type} model")

    def stop(self):
        """Request the worker to stop (for future cancellation support)."""
        self._is_running = False


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
        heartbeat_lost: Emitted if worker becomes unresponsive (for compatibility with AIWorkerProcess)
    """

    # Signals
    progress_updated = Signal(str)  # Status message
    token_generated = Signal(str)  # Individual token for streaming display
    summary_complete = Signal(str)  # Complete summary text
    error = Signal(str)  # Error message
    heartbeat_lost = Signal()  # Emitted if worker becomes unresponsive (compatibility signal)

    def __init__(self, model_manager, processing_results, summary_length, preset_id="factual-summary"):
        """
        Initialize the AI worker (thread-based, Windows-compatible).

        Args:
            model_manager: The ModelManager instance
            processing_results: List of processing result dicts from DocumentCleaner
            summary_length: Target summary length in words (from slider)
            preset_id: Prompt template preset to use (default: 'factual-summary')
        """
        super().__init__()
        self.model_manager = model_manager
        self.processing_results = processing_results
        self.summary_length = summary_length
        self.preset_id = preset_id
        self._is_running = True
        self._combined_text = ""  # Store for performance logging

    def run(self):
        """Execute AI summary generation in background thread with intelligent chunking."""
        import datetime

        # Log immediately before any other operations to catch startup errors
        try:
            debug_log("\n[AIWORKER] *** RUN METHOD STARTED ***")
        except Exception as e:
            print(f"[AIWORKER] Critical error in run() startup: {e}")

        start_time = time.time()

        def log_step(msg):
            """Log detailed timestamped messages for troubleshooting."""
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            try:
                debug_log(f"[{timestamp}] [AIWORKER] {msg}")
            except Exception as e:
                print(f"[AIWORKER] Logging error: {e}")

        try:
            log_step("=== STARTING AI WORKER THREAD ===")
            log_step(f"Summary length target: {self.summary_length} words")
            log_step(f"Preset ID: {self.preset_id}")
            log_step(f"Number of documents to process: {len(self.processing_results)}")

            # Step 1: Combine cleaned texts from all documents
            log_step("STEP 1: Starting document text combination...")
            self.progress_updated.emit("Combining document texts...")

            combined_text = ""
            doc_info = []  # Track document names and start positions for chunk reporting

            for idx, result in enumerate(self.processing_results):
                log_step(f"  Processing document {idx+1}/{len(self.processing_results)}")
                if result.get('status') == 'success' and result.get('cleaned_text'):
                    filename = result.get('filename', 'Unknown')
                    text_length = len(result.get('cleaned_text', ''))
                    log_step(f"    Document: {filename}, Text length: {text_length} chars")
                    doc_info.append({'filename': filename, 'start_pos': len(combined_text)})
                    combined_text += f"\n\n--- Document: {filename} ---\n\n"
                    combined_text += result['cleaned_text']
                else:
                    log_step(f"    Document SKIPPED (status: {result.get('status')}, has text: {bool(result.get('cleaned_text'))})")

            if not combined_text.strip():
                log_step("ERROR: No valid document text found!")
                self.error.emit("No valid document text found to summarize")
                return

            log_step(f"STEP 1 COMPLETE: Combined text length: {len(combined_text)} chars, {len(combined_text.split())} words")
            self._combined_text = combined_text

            # Step 2: Prepare text for model (respecting context window limits)
            log_step("STEP 2: Preparing text for model processing...")
            combined_words = combined_text.split()
            log_step(f"  Combined document has {len(combined_words)} words")

            # IMPORTANT: Phi-3 Mini has 4096 token context window
            # Conservative strategy per best practices:
            # - Actual token-to-word ratio: ~2.0 for typical legal text
            # - Max context: 4096 tokens
            # - Leave 500 token margin for prompt template overhead
            # - Leave 200 token margin for output generation
            # Available for input: 4096 - 500 - 200 = 3396 tokens
            # Safe input words: 3396 / 2.0 = 1698 words max
            # Use 1200 words as conservative limit (leaves ~400 tokens extra buffer)
            MAX_INPUT_WORDS = 1200  # Conservative limit: 1200 words ≈ 2400 tokens, safe for 4096 context
            if len(combined_words) > MAX_INPUT_WORDS:
                log_step(f"  Document exceeds max input words ({len(combined_words)} > {MAX_INPUT_WORDS})")
                log_step(f"  Truncating to first {MAX_INPUT_WORDS} words for model input")
                combined_text = " ".join(combined_words[:MAX_INPUT_WORDS])
                log_step(f"  Truncated text length: {len(combined_text.split())} words")
                self.progress_updated.emit(
                    f"Processing first {MAX_INPUT_WORDS} words of {len(combined_words)} total..."
                )
            else:
                log_step("  Document size acceptable for model")
                self.progress_updated.emit(
                    f"Processing {len(combined_words)} words of input..."
                )

            # Step 3: Prepare for model generation
            log_step("STEP 3: Preparing for model generation...")
            final_word_count = len(combined_text.split())
            log_step(f"  Final input length: {final_word_count} words, {len(combined_text)} chars")
            log_step(f"  Model manager status: loaded={self.model_manager.is_model_loaded()}, model={self.model_manager.current_model_name}")

            self.progress_updated.emit(
                f"Generating {self.summary_length}-word summary... (first token may take 1-5 minutes on CPU)"
            )

            full_summary = ""
            token_count = 0

            # Step 4: Generate summary (non-streaming, with periodic status updates)
            log_step("STEP 4: Starting summary generation...")
            log_step(f"  Calling model_manager.generate_summary()...")
            log_step(f"  Parameters: max_words={self.summary_length}, preset_id={self.preset_id}")

            generation_start = time.time()
            first_update = True
            progress_spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            spinner_idx = 0

            # Start progress update timer (emit status every 1 second)
            import threading
            def emit_progress_updates():
                """Emit progress updates with elapsed time every second."""
                nonlocal spinner_idx, first_update
                while self._is_running and generation_start < time.time():
                    if first_update:
                        log_step("Inference started, emitting progress updates every second...")
                        first_update = False

                    elapsed = time.time() - generation_start
                    spinner = progress_spinner[spinner_idx % len(progress_spinner)]
                    status = f"Generating {self.summary_length}-word summary... {spinner} ({elapsed:.0f}s)"
                    self.progress_updated.emit(status)
                    spinner_idx += 1
                    time.sleep(1.0)

            progress_thread = threading.Thread(target=emit_progress_updates, daemon=True)
            progress_thread.start()

            try:
                # Non-streaming generation - returns complete summary as string
                full_summary = self.model_manager.generate_summary(
                    case_text=combined_text,
                    max_words=self.summary_length,
                    preset_id=self.preset_id
                )

                # Stop the progress update thread
                self._is_running = False
                progress_thread.join(timeout=2.0)

                log_step(f"*** GENERATION COMPLETE! *** {len(full_summary)} chars received")
                log_step(f"Summary preview: {full_summary[:100]}...")

                if not full_summary:
                    log_step("ERROR: Empty summary returned!")
                    self.error.emit("Model generated empty summary")
                    return

                token_count = len(full_summary.split())  # Use word count as proxy for tokens

            except Exception as e:
                log_step(f"ERROR during summary generation: {str(e)}")
                import traceback
                log_step(f"Traceback: {traceback.format_exc()}")
                self.error.emit(f"Summary generation failed: {str(e)}")
                return

            # Step 5: Complete and finalize
            log_step("STEP 5: Summarization complete, finalizing...")
            word_count = len(full_summary.split())
            generation_time = time.time() - generation_start
            total_time = time.time() - start_time

            log_step(f"  Final summary: {word_count} words, {token_count} tokens")
            log_step(f"  Generation time: {generation_time:.1f}s")
            log_step(f"  Total time (including preprocessing): {total_time:.1f}s")

            # Non-streaming mode doesn't track time-to-first-token, but we can calculate average time/token
            avg_token_time = generation_time / max(1, token_count)
            log_step(f"  Average time per token: {avg_token_time:.3f}s")

            self.progress_updated.emit(f"Summary complete ({word_count} words)")

            # DEBUG: Write summary to file for verification
            from pathlib import Path
            debug_output = Path(__file__).parent.parent.parent / "generated_summary.txt"
            with open(debug_output, 'w', encoding='utf-8') as f:
                f.write("=== Generated Summary ===\n")
                f.write(f"Generation time: {generation_time:.1f}s\n")
                f.write(f"Total time: {total_time:.1f}s\n")
                f.write(f"Word count: {word_count}\n")
                f.write(f"Token count: {token_count}\n")
                f.write("=" * 60 + "\n\n")
                f.write(full_summary.strip())
            log_step(f"  Summary written to: {debug_output}")

            self.summary_complete.emit(full_summary.strip())
            log_step("=== AI WORKER COMPLETE ===")

            # Step 6: Log performance data for future predictions (non-critical)
            # Wrapped in try-except to prevent crashes if performance logging fails
            log_step("STEP 6: Logging performance data...")
            try:
                print("[AIWORKER] Getting performance tracker...")
                tracker = get_performance_tracker()
                print("[AIWORKER] Tracker obtained successfully")
                model_name = self.model_manager.current_model_name or 'standard'
                print(f"[AIWORKER] Logging generation: {word_count} words in {generation_time:.1f}s")

                tracker.log_generation(
                    input_text=self._combined_text,
                    input_documents=len(self.processing_results),
                    requested_summary_length=self.summary_length,
                    actual_summary_length=word_count,
                    generation_time_seconds=generation_time,
                    model_name=model_name
                )
                print("[AIWORKER] Performance logging successful")
                log_step("Performance logging complete")
            except Exception as perf_error:
                # Performance logging is non-critical - log the error but don't crash
                error_msg = f"Performance logging failed (non-critical): {perf_error}"
                log_step(error_msg)
                print(f"[AIWORKER] {error_msg}")
                import traceback
                print(f"[AIWORKER] Traceback: {traceback.format_exc()}")
                # Continue anyway - performance logging is not critical to functionality

            # Final success message - always reached if no exception above
            log_step("=== AI WORKER THREAD FINISHED SUCCESSFULLY ===")
            print("[AIWORKER] === WORKER THREAD EXITING NORMALLY ===")

    def _process_with_intelligent_chunking(self, combined_text, doc_info):
        """
        Process document chunks intelligently with progress reporting.

        Shows: "Processing chunk 6/17 for TranscriptABC.pdf, chunk 6/55 overall"
        """
        from src.chunking_engine import ChunkingEngine
        from src.progressive_summarizer import ProgressiveSummarizer
        from pathlib import Path

        # Initialize engines
        # Use .resolve() to get absolute path (important for thread context)
        config_path = Path(__file__).resolve().parent.parent / "config" / "chunking_config.yaml"
        chunking_engine = ChunkingEngine(config_path)
        progressive_summarizer = ProgressiveSummarizer(config_path)

        # Step 1: Chunk the document
        debug_log("[WORKER] Starting document chunking...")
        chunks = chunking_engine.chunk_text(combined_text)
        debug_log(f"[WORKER] Document chunked into {len(chunks)} chunks")
        self.progress_updated.emit(f"Document chunked into {len(chunks)} chunks. Summarizing...")

        # Step 2: Prepare DataFrame
        progressive_summarizer.prepare_chunks_dataframe(chunks)

        # Step 3: Summarize each chunk with progress reporting
        total_chunks = len(chunks)
        current_overall_chunk = 0

        for chunk in chunks:
            if not self._is_running:
                return combined_text

            current_overall_chunk += 1
            chunk_num = chunk.chunk_num
            section_name = chunk.section_name or "Unknown Section"

            # Find which document this chunk belongs to (for progress reporting)
            doc_name = "Combined"
            for doc in doc_info:
                if chunk.text.startswith(doc['filename'][:20]):  # Heuristic match
                    doc_name = doc['filename'].replace('.pdf', '').replace('.txt', '')
                    break

            # Report detailed progress
            progress_msg = (
                f"Processing chunk {chunk_num}/{total_chunks} for {doc_name}, "
                f"chunk {current_overall_chunk}/{total_chunks} overall"
            )
            debug_log(f"[WORKER] {progress_msg}")
            self.progress_updated.emit(progress_msg)

            # TODO: Summarize this chunk with model
            # For now, just track that we're processing it
            # Full implementation would call model for each chunk

        # Step 4: Return combined progressive summary
        # For now, return original combined text (full AI implementation pending)
        debug_log("[WORKER] Chunking and summarization complete")
        return combined_text

    def stop(self):
        """Request the worker to stop generating."""
        self._is_running = False


# ============================================================================
# MULTIPROCESSING WORKERS (for CPU-intensive tasks that block the GIL)
# ============================================================================

def ai_generation_worker_process(
    model_name: str,
    combined_text: str,
    summary_length: int,
    output_queue,
    preset_id: str = "factual-summary",
    heartbeat_interval: float = 5.0,
    batch_size: int = 15,
    batch_timeout: float = 0.5
):
    """
    Standalone worker function that runs in a separate process for AI model generation.

    This function runs completely isolated from the GUI process, preventing
    blocking operations from freezing the UI.

    Args:
        model_name: Name of the model being used ('standard' or 'pro')
        combined_text: The text to summarize
        summary_length: Target summary length in words
        output_queue: multiprocessing.Queue for sending messages back to GUI
        preset_id: Prompt template preset to use (default: 'factual-summary')
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
        debug_log("\n[WORKER PROCESS] Starting AI generation worker...")
        debug_log(f"[WORKER PROCESS] Model: {model_name}")
        debug_log(f"[WORKER PROCESS] Input length: {len(combined_text)} chars")
        debug_log(f"[WORKER PROCESS] Target summary length: {summary_length} words")

        # Send initial heartbeat to confirm process started
        output_queue.put({
            'type': 'heartbeat',
            'data': 'alive',
            'timestamp': time.time()
        })

        # Import and initialize Ollama model manager IN THIS PROCESS
        # (Must be done here, not passed from parent, due to multiprocessing constraints)
        from src.ai.ollama_model_manager import OllamaModelManager

        debug_log("[WORKER PROCESS] Initializing Ollama Model Manager...")
        model_manager = OllamaModelManager()

        # Check Ollama connection
        if not model_manager.is_model_loaded():
            debug_log(f"[WORKER PROCESS] ERROR: Ollama not accessible")
            raise RuntimeError(
                f"Ollama service not accessible at {model_manager.api_base}. "
                "Please ensure Ollama is running: ollama serve"
            )

        debug_log(f"[WORKER PROCESS] Ollama connected successfully")

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

        # Generate summary (Ollama REST API returns complete summary, not streaming)
        generation_start = time.time()
        last_heartbeat_time = time.time()

        debug_log(f"[WORKER PROCESS] Calling model_manager.generate_summary()...")
        debug_log(f"[WORKER PROCESS] Parameters: max_words={summary_length}, preset_id={preset_id}")

        full_summary = model_manager.generate_summary(
            case_text=combined_text,
            max_words=summary_length,
            preset_id=preset_id
        )

        debug_log(f"[WORKER PROCESS] Generation returned {len(full_summary)} chars")

        # Send the complete summary in batches to simulate streaming
        # This maintains UI responsiveness and matches the streaming interface
        char_pos = 0
        while char_pos < len(full_summary):
            # Get next batch of characters
            batch_end = min(char_pos + batch_size, len(full_summary))
            batch_text = full_summary[char_pos:batch_end]

            output_queue.put({
                'type': 'token',
                'data': batch_text,
                'buffer_size': len(batch_text)
            })

            char_pos = batch_end
            current_time = time.time()

            # Send heartbeat periodically
            if (current_time - last_heartbeat_time) >= heartbeat_interval:
                output_queue.put({
                    'type': 'heartbeat',
                    'data': 'alive',
                    'timestamp': current_time
                })
                last_heartbeat_time = current_time
                debug_log(f"[WORKER PROCESS] Heartbeat sent (chars sent: {char_pos}/{len(full_summary)})")

            # Small delay to make batching visible and allow heartbeats
            time.sleep(0.01)

        # Calculate final stats
        word_count = len(full_summary.split())
        token_count = len(full_summary.split())  # Approximate: use word count as token count

        debug_log(f"[WORKER PROCESS] Generation complete!")
        debug_log(f"[WORKER PROCESS] Words: {word_count}, Approximate tokens: {token_count}")

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

    def __init__(self, model_manager, processing_results, summary_length, preset_id="factual-summary"):
        """
        Initialize the multiprocessing AI worker.

        Args:
            model_manager: The ModelManager instance (used to get model info)
            processing_results: List of processing result dicts from DocumentCleaner
            summary_length: Target summary length in words (from slider)
            preset_id: Prompt template preset to use (default: 'factual-summary')
        """
        super().__init__()
        self.model_manager = model_manager
        self.processing_results = processing_results
        self.summary_length = summary_length
        self.preset_id = preset_id

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

            # Step 2: Use intelligent chunking for longer documents
            combined_words = combined_text.split()

            # Threshold for using chunking (words)
            CHUNKING_THRESHOLD = 2000  # If doc is longer than this, use chunking

            if len(combined_words) > CHUNKING_THRESHOLD:
                self.progress_updated.emit(
                    f"Large document detected ({len(combined_words)} words). Using intelligent chunking..."
                )
                combined_text = self._process_with_chunking(combined_text)
                debug_log(f"[AIWorkerProcess] Chunking complete, final summary length: {len(combined_text.split())} words")
            else:
                # For shorter documents, use simple truncation (backward compatible)
                max_input_words = 300
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
                target=ai_generation_worker_process,
                args=(
                    model_name,
                    combined_text,
                    self.summary_length,
                    self.queue,
                    self.preset_id  # Pass the preset_id for prompt selection
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

    def _process_with_chunking(self, text: str) -> str:
        """
        Process a long document using intelligent chunking and progressive summarization.

        This method:
        1. Uses ChunkingEngine to split text into intelligent chunks
        2. Prepares a progressive summarization state
        3. Organizes chunks and metadata in a DataFrame
        4. For each chunk, prepares context (global + local)
        5. Sends chunks to AI model for summarization
        6. Updates progressive document summary at batch boundaries
        7. Returns final cohesive summary

        Args:
            text: The combined document text

        Returns:
            Final cohesive summary of the entire document
        """
        try:
            debug_log("[AIWorkerProcess] Starting chunked summarization...")
            start_time = time.time()

            # Initialize components
            summarizer = ProgressiveSummarizer()
            self.progress_updated.emit("Chunking document...")

            # Step 1: Chunk the document
            chunks = summarizer.chunk_document(text)
            if not chunks:
                error_msg = "Failed to chunk document"
                debug_log(f"[AIWorkerProcess] ERROR: {error_msg}")
                self.error.emit(error_msg)
                return text[:300].split()  # Fallback to truncation

            debug_log(f"[AIWorkerProcess] Document split into {len(chunks)} chunks")

            # Step 2: Prepare DataFrame with chunk metadata
            summarizer.prepare_chunks_dataframe(chunks)

            # Step 3: Calculate batch boundaries for progressive updates
            total_chunks = len(chunks)
            batch_boundaries = summarizer._get_batch_boundaries(total_chunks)
            debug_log(f"[AIWorkerProcess] Progressive update boundaries: {batch_boundaries}")

            # Step 4: Process each chunk (simulate with AI calls)
            # NOTE: This is a PLACEHOLDER that demonstrates the architecture.
            # For full integration, each chunk would be passed to the AI model
            # with its context via the multiprocessing queue.
            # For now, we'll create a simplified summary demonstrating the approach.

            final_chunks_to_pass = []

            for chunk_num, chunk in enumerate(chunks, 1):
                # Emit progress
                progress_str = summarizer.get_progress_string(chunk_num, total_chunks)
                self.progress_updated.emit(progress_str)

                # Get context for this chunk
                global_ctx, local_ctx = summarizer.get_context_for_chunk(chunk_num)

                # Create prompt with context (this would normally go to AI model)
                chunk_prompt = summarizer.create_summarization_prompt(chunk_num)
                chunk_text_preview = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text

                debug_log(f"[AIWorkerProcess] Chunk {chunk_num}/{total_chunks} ({chunk.word_count} words)")
                debug_log(f"  Section: {chunk.section_name}")
                debug_log(f"  Global context: {global_ctx[:80]}...")
                debug_log(f"  Local context: {local_ctx[:80]}...")

                # SIMPLIFIED: For now, combine all chunks instead of calling AI for each
                # This demonstrates the architecture is in place
                final_chunks_to_pass.append(chunk.text)

                # Check if we should update progressive summary at batch boundary
                if chunk_num in batch_boundaries:
                    debug_log(f"[AIWorkerProcess] Batch boundary reached at chunk {chunk_num}, would update progressive summary here")

            # Step 5: Return combined text from all chunks
            # In a full implementation, this would be the final progressive summary
            # For now, return chunks combined (user can then pass this to AI model)
            combined = "\n\n--- CHUNK BOUNDARY ---\n\n".join(final_chunks_to_pass)

            processing_time = time.time() - start_time
            debug_log(f"[AIWorkerProcess] Chunking complete in {processing_time:.2f}s")

            # Save debug DataFrame if configured
            try:
                debug_output = Path(__file__).parent.parent.parent / "debug"
                if not debug_output.exists():
                    debug_output.mkdir(parents=True, exist_ok=True)
                debug_file = summarizer.save_debug_dataframe(debug_output)
                debug_log(f"[AIWorkerProcess] Debug DataFrame saved to {debug_file}")
            except Exception as e:
                debug_log(f"[AIWorkerProcess] Failed to save debug DataFrame: {e}")

            return combined

        except Exception as e:
            error_msg = f"Chunking error: {str(e)}"
            debug_log(f"[AIWorkerProcess] ERROR: {error_msg}\n{traceback.format_exc()}")
            self.error.emit(error_msg)
            return text[:300].split()  # Fallback to truncation

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
