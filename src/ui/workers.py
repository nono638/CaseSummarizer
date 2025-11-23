import threading
import multiprocessing
import time
import os
import traceback
from queue import Queue, Empty
from pathlib import Path

from src.cleaner import DocumentCleaner
from src.debug_logger import debug_log
from src.progressive_summarizer import ProgressiveSummarizer
from src.vocabulary_extractor import VocabularyExtractor
from src.ai.ollama_model_manager import OllamaModelManager # Import for context
from src.ui.ollama_worker import ollama_generation_worker_process


class ProcessingWorker(threading.Thread):
    """
    Background worker for processing documents (cleaning, chunking).
    Communicates with the main UI via a queue.
    """
    def __init__(self, file_paths, ui_queue, jurisdiction="ny"):
        super().__init__(daemon=True)
        self.file_paths = file_paths
        self.ui_queue = ui_queue
        self.jurisdiction = jurisdiction
        self.cleaner = DocumentCleaner(jurisdiction=self.jurisdiction)
        self.processed_results = [] # Store results for later AI processing
        self._stop_event = threading.Event() # Event for graceful stopping

    def stop(self):
        """Signals the worker to stop processing."""
        self._stop_event.set()

    def run(self):
        """Execute document cleaning and pre-processing in background thread."""
        try:
            total_files = len(self.file_paths)
            self.processed_results = []

            for idx, file_path in enumerate(self.file_paths):
                if self._stop_event.is_set():
                    debug_log("[PROCESSING WORKER] Stop signal received. Exiting.")
                    self.ui_queue.put(('error', "Document processing cancelled."))
                    return # Exit gracefully
                
                percentage = int((idx / total_files) * 100)
                filename = os.path.basename(file_path)
                
                self.ui_queue.put(('progress', (percentage, f"Processing and cleaning {filename}...")))

                def progress_callback(msg):
                    if self._stop_event.is_set():
                        # If stop requested during callback, don't update UI further
                        raise InterruptedError("Processing stopped by user.")
                    self.ui_queue.put(('progress', (percentage, msg)))

                try:
                    cleaned_result = self.cleaner.process_document(file_path, progress_callback=progress_callback)
                except InterruptedError:
                    debug_log("[PROCESSING WORKER] Document cleaning interrupted by user.")
                    self.ui_queue.put(('error', "Document processing cancelled."))
                    return # Exit gracefully
                
                # Store the cleaned result for subsequent AI processing
                self.processed_results.append(cleaned_result)
                self.ui_queue.put(('file_processed', cleaned_result))
            
            if not self._stop_event.is_set(): # Only send finished if not stopped
                self.ui_queue.put(('processing_finished', self.processed_results))
                self.ui_queue.put(('progress', (100, "Document processing complete")))

        except Exception as e:
            debug_log(f"ProcessingWorker encountered a critical error: {e}\n{traceback.format_exc()}")
            self.ui_queue.put(('error', f"Critical document processing error: {str(e)}"))

class OllamaAIWorkerManager:
    """
    Manages the multiprocessing worker for Ollama AI generation.
    Handles starting, stopping, and communication with the worker process.
    """
    def __init__(self, ui_queue: Queue):
        self.ui_queue = ui_queue
        self.input_queue = multiprocessing.Queue()
        self.output_queue = multiprocessing.Queue()
        self.process = None
        self.is_running = False

    @staticmethod
    def _clear_queue(queue):
        """Safely clear all messages from a queue."""
        while not queue.empty():
            try:
                queue.get_nowait()
            except Empty:
                break

    def start_worker(self):
        """Starts the Ollama AI worker process."""
        if self.is_running and self.process and self.process.is_alive():
            debug_log("[OLLAMA MANAGER] Worker already running.")
            return

        # Ensure queues are empty from previous runs
        self._clear_queue(self.input_queue)
        self._clear_queue(self.output_queue)

        debug_log("[OLLAMA MANAGER] Starting Ollama AI worker process.")
        self.process = multiprocessing.Process(
            target=ollama_generation_worker_process,
            args=(self.input_queue, self.output_queue),
            daemon=True # Daemon process allows main process to exit even if worker is alive
        )
        self.process.start()
        self.is_running = True
        debug_log(f"[OLLAMA MANAGER] Worker process started with PID: {self.process.pid}")

    def stop_worker(self):
        """Sends a termination signal and stops the Ollama AI worker process."""
        if self.is_running and self.process and self.process.is_alive():
            debug_log("[OLLAMA MANAGER] Sending TERMINATE signal to worker.")
            try:
                self.input_queue.put_nowait("TERMINATE") # Non-blocking put
                self.process.join(timeout=5) # Wait for worker to exit gracefully
            except Exception as e:
                debug_log(f"[OLLAMA MANAGER] Error sending terminate signal or joining: {e}")
            
            if self.process.is_alive():
                debug_log("[OLLAMA MANAGER] Worker did not terminate gracefully, forcing shutdown.")
                self.process.terminate()
            self.process = None
            self.is_running = False
            debug_log("[OLLAMA MANAGER] Ollama AI worker process stopped.")
        elif self.is_running:
            debug_log("[OLLAMA MANAGER] Worker process already stopped or not alive.")
            self.process = None
            self.is_running = False

    def send_task(self, task_type: str, payload: dict):
        """Sends a task to the worker process."""
        if not (self.is_running and self.process and self.process.is_alive()):
            self.start_worker() # Ensure worker is running before sending task
        
        debug_log(f"[OLLAMA MANAGER] Sending task '{task_type}' to worker.")
        self.input_queue.put((task_type, payload))

    def check_for_messages(self):
        """Checks the output queue for messages from the worker process."""
        messages = []
        while not self.output_queue.empty():
            try:
                messages.append(self.output_queue.get_nowait())
            except Empty:
                break
        return messages

    def is_worker_alive(self) -> bool:
        return self.process is not None and self.process.is_alive()


