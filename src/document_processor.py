"""
Async Document Processor for LocalScribe

Handles intelligent parallel document processing with user-controlled CPU allocation.
Uses ThreadPoolExecutor for I/O-bound Ollama API calls.
"""

import os
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from pathlib import Path

from src.debug_logger import debug_log
from src.utils.logger import debug


@dataclass
class DocumentJob:
    """Represents a document to be processed."""
    file_path: str
    document_id: str  # Unique identifier for tracking
    case_text: str  # Already-extracted and normalized text from RawTextExtractor
    max_words: int = 200
    preset_id: str = "factual-summary"


class AsyncDocumentProcessor:
    """
    Manages parallel document processing with intelligent resource allocation.

    Formula for concurrent jobs:
    max_concurrent = min(
        ceil(cpu_count * user_fraction),     # Respect user's CPU choice
        available_ram_gb // 1,               # 1GB per concurrent request
        cpu_count - 2                        # Hard cap: reserve 2 cores for OS
    )
    """

    def __init__(self, cpu_fraction: float = 0.5):
        """
        Initialize the document processor.

        Args:
            cpu_fraction: User's CPU allocation choice (0.25, 0.5, or 0.75)
        """
        self.cpu_fraction = cpu_fraction
        self.executor = None
        self.max_concurrent = self._calculate_max_concurrent()

        debug(f"[PROCESSOR] Initialized with CPU fraction {cpu_fraction}")
        debug(f"[PROCESSOR] Max concurrent jobs: {self.max_concurrent}")
        debug_log(f"[PROCESSOR] Initialized with CPU fraction {cpu_fraction}, max concurrent: {self.max_concurrent}")

    def _calculate_max_concurrent(self) -> int:
        """
        Calculate maximum concurrent jobs based on CPU, RAM, and core count.

        Returns:
            int: Maximum number of concurrent document jobs
        """
        cpu_count = os.cpu_count() or 1
        available_memory_gb = psutil.virtual_memory().available / (1024 ** 3)

        # Calculate from CPU fraction
        from math import ceil
        max_from_cpu = ceil(cpu_count * self.cpu_fraction)

        # Calculate from available RAM (1GB per request)
        max_from_memory = int(available_memory_gb // 1)

        # Hard cap: reserve 2 cores for OS
        hard_cap = max(1, cpu_count - 2)

        # Take the minimum
        max_concurrent = min(max_from_cpu, max_from_memory, hard_cap)

        debug(f"[PROCESSOR] CPU calculation: {cpu_count} cores × {self.cpu_fraction} = {max_from_cpu}")
        debug(f"[PROCESSOR] Memory calculation: {available_memory_gb:.1f} GB available / 1 GB per request = {max_from_memory}")
        debug(f"[PROCESSOR] Hard cap: {cpu_count} cores - 2 = {hard_cap}")
        debug(f"[PROCESSOR] Final max_concurrent = min({max_from_cpu}, {max_from_memory}, {hard_cap}) = {max_concurrent}")

        return max(1, max_concurrent)

    def process_documents(
        self,
        documents: List[DocumentJob],
        generate_summary_fn: Callable,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, str]:
        """
        Process multiple documents in parallel.

        Args:
            documents: List of DocumentJob objects to process
            generate_summary_fn: Function to generate summary for a single document.
                                 Signature: generate_summary_fn(case_text, max_words, preset_id) -> str
            progress_callback: Optional callback for progress updates.
                              Signature: progress_callback(completed, total, concurrent_count, job_id)

        Returns:
            dict: Mapping of document_id -> generated_summary
        """
        if not documents:
            return {}

        results = {}
        total_docs = len(documents)

        debug(f"[PROCESSOR] Starting batch processing: {total_docs} documents")
        debug_log(f"[PROCESSOR] Processing {total_docs} documents with max {self.max_concurrent} concurrent")

        # Create thread pool
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            self.executor = executor

            # Submit all jobs and track them
            future_to_doc = {
                executor.submit(
                    self._process_single_document,
                    doc,
                    generate_summary_fn
                ): doc for doc in documents
            }

            completed = 0
            active_jobs = len(future_to_doc)

            # Process completions as they finish
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                completed += 1
                active_jobs = len([f for f in future_to_doc if not f.done()])

                try:
                    summary = future.result()
                    results[doc.document_id] = summary
                    debug(f"[PROCESSOR] Completed: {doc.document_id} ({completed}/{total_docs})")

                    # Call progress callback
                    if progress_callback:
                        progress_callback(
                            completed=completed,
                            total=total_docs,
                            concurrent_count=self.max_concurrent,
                            job_id=doc.document_id
                        )

                except Exception as e:
                    debug(f"[PROCESSOR] Error processing {doc.document_id}: {str(e)}")
                    debug_log(f"[PROCESSOR] Error: {str(e)}")
                    results[doc.document_id] = f"Error: {str(e)}"

                    # Still call callback to update progress
                    if progress_callback:
                        progress_callback(
                            completed=completed,
                            total=total_docs,
                            concurrent_count=self.max_concurrent,
                            job_id=doc.document_id
                        )

        debug(f"[PROCESSOR] Batch processing complete: {len(results)} documents processed")
        debug_log(f"[PROCESSOR] Completed batch: {len(results)}/{total_docs} documents")

        self.executor = None
        return results

    def _process_single_document(
        self,
        doc: DocumentJob,
        generate_summary_fn: Callable
    ) -> str:
        """
        Process a single document (runs in executor thread).

        Args:
            doc: DocumentJob to process
            generate_summary_fn: Summary generation function

        Returns:
            str: Generated summary
        """
        debug(f"[PROCESSOR WORKER] Starting: {doc.document_id}")
        try:
            summary = generate_summary_fn(
                case_text=doc.case_text,
                max_words=doc.max_words,
                preset_id=doc.preset_id
            )
            return summary
        except Exception as e:
            debug(f"[PROCESSOR WORKER] Failed: {doc.document_id} - {str(e)}")
            raise

    def cancel(self):
        """Cancel all pending operations."""
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
            debug("[PROCESSOR] Cancelled all pending operations")
