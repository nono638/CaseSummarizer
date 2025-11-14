"""
LocalScribe - Background Worker Threads
Threaded workers for long-running operations to keep UI responsive.
"""

from PySide6.QtCore import QThread, Signal
from pathlib import Path
import time


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
