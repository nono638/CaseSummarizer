"""
LocalScribe - Background Workers (CustomTkinter Refactor)
"""
import threading
import multiprocessing
import time
import os
import traceback
from queue import Queue, Empty
from pathlib import Path

from src.cleaner import DocumentCleaner
from src.debug_logger import debug_log

class ProcessingWorker(threading.Thread):
    """
    Background worker for processing documents.
    Communicates with the main UI via a queue.
    """
    def __init__(self, file_paths, ui_queue, jurisdiction="ny"):
        super().__init__(daemon=True)
        self.file_paths = file_paths
        self.jurisdiction = jurisdiction
        self.ui_queue = ui_queue
        self.cleaner = None

    def run(self):
        """Execute document processing in background thread."""
        try:
            self.cleaner = DocumentCleaner(jurisdiction=self.jurisdiction)
            total_files = len(self.file_paths)

            for idx, file_path in enumerate(self.file_paths):
                percentage = int((idx / total_files) * 100)
                filename = os.path.basename(file_path)
                
                self.ui_queue.put(('progress', (percentage, f"Processing {filename}...")))

                def progress_callback(msg):
                    self.ui_queue.put(('progress', (percentage, msg)))

                result = self.cleaner.process_document(file_path, progress_callback=progress_callback)
                self.ui_queue.put(('file_processed', result))

            self.ui_queue.put(('progress', (100, "Processing complete")))
            self.ui_queue.put(('finished', None))

        except Exception as e:
            self.ui_queue.put(('error', str(e)))

# NOTE: The AI-related workers (AIWorker, AIWorkerProcess, etc.) are highly complex
# and their refactoring would involve significant architectural changes to the
# model manager interaction. For this phase of getting the UI functional,
# we will stub out their functionality. A full refactor would be a separate,
# major task.

class AIWorker(threading.Thread):
    """
    Stubbed-out AI worker for CustomTkinter.
    """
    def __init__(self, ui_queue, **kwargs):
        super().__init__(daemon=True)
        self.ui_queue = ui_queue

    def run(self):
        self.ui_queue.put(('progress_ai', "Starting AI generation..."))
        time.sleep(2)
        self.ui_queue.put(('token', "This is a stubbed summary. "))
        time.sleep(1)
        self.ui_queue.put(('token', "The full AI worker needs to be refactored "))
        time.sleep(1)
        self.ui_queue.put(('token', "to work with CustomTkinter's threading model."))
        time.sleep(1)
        self.ui_queue.put(('summary_complete', "This is a stubbed summary. The full AI worker needs to be refactored to work with CustomTkinter's threading model."))
