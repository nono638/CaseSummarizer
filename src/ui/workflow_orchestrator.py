"""
Workflow Orchestrator Module

Manages the document processing workflow state machine, coordinating between:
- Document extraction (Step 1-2.5)
- Vocabulary extraction (Step 2.5b)
- AI summary generation (Step 3+)

This module separates workflow orchestration logic from UI updates,
improving testability and maintainability.

Workflow State Machine (SEQUENTIAL - Session 14 fix):
    IDLE -> EXTRACTING -> VOCAB_EXTRACTION -> AI_GENERATION -> COMPLETE

Key Design Decision:
    Vocabulary extraction completes BEFORE AI generation starts.
    This ensures the user can view/download the vocab list while AI runs.

The orchestrator decides WHAT to do next; the QueueMessageHandler decides
HOW to update the UI in response.
"""

from dataclasses import dataclass
from typing import Any

from src.config import LEGAL_EXCLUDE_LIST_PATH, MEDICAL_TERMS_LIST_PATH, USER_VOCAB_EXCLUDE_PATH
from src.logging_config import debug_log
from src.utils.text_utils import combine_document_texts


@dataclass
class WorkflowState:
    """
    Represents the current state of a document processing workflow.

    Attributes:
        extracted_documents: List of documents that have been extracted
        pending_ai_params: AI generation parameters (model, length, options)
        output_options: Dictionary of requested output types
        vocab_complete: Whether vocabulary extraction has finished
        ai_complete: Whether AI generation has finished
        is_complete: Whether the entire workflow has finished
    """
    extracted_documents: list[dict] = None
    pending_ai_params: dict | None = None
    output_options: dict | None = None
    vocab_complete: bool = False
    ai_complete: bool = False
    is_complete: bool = False

    def __post_init__(self):
        if self.extracted_documents is None:
            self.extracted_documents = []


class WorkflowOrchestrator:
    """
    Orchestrates the document processing workflow.

    This class is responsible for:
    1. Deciding what workflow steps to execute next
    2. Managing workflow state transitions
    3. Coordinating parallel execution of vocabulary extraction and AI generation

    It does NOT directly update the UI - that's the QueueMessageHandler's job.

    Example:
        orchestrator = WorkflowOrchestrator(main_window)
        orchestrator.on_extraction_complete(documents, ai_params)
    """

    def __init__(self, main_window):
        """
        Initialize the workflow orchestrator.

        Args:
            main_window: Reference to MainWindow instance (for spawning workers
                        and accessing state). The orchestrator reads from but
                        doesn't directly modify UI widgets.
        """
        self.main_window = main_window
        self.state = WorkflowState()
        self.vocab_worker = None  # Track vocabulary worker for cancellation

    def get_output_options(self) -> dict[str, bool]:
        """
        Read current output options from UI checkboxes.

        Returns:
            Dictionary with keys: individual_summaries, meta_summary, vocab_csv
        """
        return {
            "individual_summaries": self.main_window.output_options.individual_summaries_check.get(),
            "meta_summary": self.main_window.output_options.meta_summary_check.get(),
            "vocab_csv": self.main_window.output_options.vocab_csv_check.get()
        }

    def on_extraction_complete(
        self,
        extracted_documents: list[dict],
        ai_params: dict | None
    ) -> dict[str, Any]:
        """
        Handle completion of document extraction phase.

        This is the main orchestration method. It decides what workflow steps
        to execute next based on the current state and user options.

        SEQUENTIAL WORKFLOW (Session 14):
        1. If vocab requested → start vocab extraction, wait for completion
        2. When vocab completes → start AI generation
        3. This ensures user can view/export vocab while AI runs

        Args:
            extracted_documents: List of extracted document result dictionaries
            ai_params: AI generation parameters, or None if AI not requested

        Returns:
            Dictionary describing actions taken:
            {
                'vocab_extraction_started': bool,
                'ai_generation_started': bool,
                'workflow_complete': bool,
                'combined_text': str (if vocab extraction started)
            }
        """
        debug_log(f"[ORCHESTRATOR] Extraction complete. {len(extracted_documents)} documents.")

        # Update state
        self.state.extracted_documents = extracted_documents
        self.state.pending_ai_params = ai_params
        self.state.output_options = self.get_output_options()
        self.state.vocab_complete = False
        self.state.ai_complete = False

        actions_taken = {
            'vocab_extraction_started': False,
            'ai_generation_started': False,
            'workflow_complete': False,
            'combined_text': None
        }

        # If no AI generation requested and no vocab requested, workflow is done
        if not ai_params and not self.state.output_options.get('vocab_csv', False):
            debug_log("[ORCHESTRATOR] No outputs requested. Workflow complete.")
            self.state.is_complete = True
            actions_taken['workflow_complete'] = True
            return actions_taken

        # SEQUENTIAL: Start vocabulary extraction FIRST if requested
        # AI generation will start AFTER vocab completes (in on_vocab_complete)
        if self.state.output_options.get('vocab_csv', False):
            combined_text, doc_count = self._get_combined_text(extracted_documents)
            actions_taken['combined_text'] = combined_text
            actions_taken['vocab_extraction_started'] = True
            self._start_vocab_extraction(combined_text, doc_count)
            debug_log("[ORCHESTRATOR] Started vocabulary extraction (AI will start after).")
            # Do NOT start AI here - wait for vocab to complete
            return actions_taken

        # If no vocab requested but AI is, start AI directly
        if ai_params:
            self._start_ai_generation(extracted_documents, ai_params)
            actions_taken['ai_generation_started'] = True
            debug_log("[ORCHESTRATOR] Started AI summary generation (no vocab requested).")

        return actions_taken

    def _get_combined_text(self, extracted_documents: list[dict]) -> tuple:
        """
        Get combined text from all documents for vocabulary extraction.

        Uses the shared utility function from src/utils/text_utils.
        Preprocessing is disabled for vocabulary extraction to preserve
        original terms (line numbers, Q/A markers, etc. don't affect NER).

        Args:
            extracted_documents: List of document result dictionaries

        Returns:
            Tuple of (combined_text, doc_count)
        """
        # Disable preprocessing for vocabulary - we want raw text for NER
        combined = combine_document_texts(extracted_documents, include_headers=False, preprocess=False)
        doc_count = sum(1 for d in extracted_documents if d.get('extracted_text'))
        debug_log(f"[ORCHESTRATOR] Combined {doc_count} documents "
                  f"({len(combined)} characters total).")
        return combined, doc_count

    def _start_vocab_extraction(self, combined_text: str, doc_count: int = 1):
        """
        Start vocabulary extraction worker thread.

        Args:
            combined_text: Combined text from all documents
            doc_count: Number of documents being processed (for frequency filtering)
        """
        # Import here to avoid circular imports
        from src.ui.workers import VocabularyWorker

        self.vocab_worker = VocabularyWorker(
            combined_text=combined_text,
            ui_queue=self.main_window.ui_queue,
            exclude_list_path=str(LEGAL_EXCLUDE_LIST_PATH),
            medical_terms_path=str(MEDICAL_TERMS_LIST_PATH),
            user_exclude_path=str(USER_VOCAB_EXCLUDE_PATH),
            doc_count=doc_count
        )
        self.vocab_worker.start()
        debug_log(f"[ORCHESTRATOR] VocabularyWorker thread started (doc_count={doc_count}).")

    def _start_ai_generation(self, extracted_documents: list[dict], ai_params: dict):
        """
        Start AI summary generation - routes to single or multi-doc mode.

        Single document: Uses existing Ollama worker for direct summarization.
        Multiple documents: Uses MultiDocSummaryWorker for hierarchical
        map-reduce summarization (each doc chunked, then meta-summarized).

        Args:
            extracted_documents: List of extracted document dictionaries
            ai_params: AI generation parameters (model, length, options)
        """
        # Count documents with actual text
        valid_docs = [d for d in extracted_documents if d.get('extracted_text')]
        doc_count = len(valid_docs)

        debug_log(f"[ORCHESTRATOR] Starting AI generation for {doc_count} document(s)")

        if doc_count <= 1:
            # Single document: Use existing fast path via main window
            debug_log("[ORCHESTRATOR] Single document mode - using direct Ollama summarization")
            self.main_window._start_ai_generation(extracted_documents, ai_params)
        else:
            # Multiple documents: Use hierarchical map-reduce via MultiDocSummaryWorker
            debug_log("[ORCHESTRATOR] Multi-document mode - using hierarchical summarization")
            self._start_multi_doc_generation(valid_docs, ai_params)

    def _start_multi_doc_generation(self, documents: list[dict], ai_params: dict):
        """
        Start multi-document hierarchical summarization.

        Uses MultiDocSummaryWorker which:
        1. Summarizes each document in parallel via progressive chunking
        2. Combines individual summaries into a coherent meta-summary

        Args:
            documents: List of documents with 'filename' and 'extracted_text'
            ai_params: AI parameters (model_name, summary_length, etc.)
        """
        from src.ui.workers import MultiDocSummaryWorker

        # Track worker for cancellation
        self.multi_doc_worker = MultiDocSummaryWorker(
            documents=documents,
            ui_queue=self.main_window.ui_queue,
            ai_params=ai_params
        )
        self.multi_doc_worker.start()
        debug_log(f"[ORCHESTRATOR] MultiDocSummaryWorker started for {len(documents)} documents")

    def on_summary_complete(self):
        """Handle completion of AI summary generation."""
        debug_log("[ORCHESTRATOR] AI summary generation complete.")
        self.state.ai_complete = True
        self._check_workflow_complete()

    def on_vocab_complete(self):
        """
        Handle completion of vocabulary extraction.

        SEQUENTIAL WORKFLOW: Now that vocab is done and visible to user,
        start AI generation if it was requested.
        """
        debug_log("[ORCHESTRATOR] Vocabulary extraction complete.")
        self.state.vocab_complete = True

        # Now start AI generation if it was requested
        if self.state.pending_ai_params and self.state.output_options.get('meta_summary', False):
            debug_log("[ORCHESTRATOR] Vocab complete, now starting AI generation...")
            self._start_ai_generation(
                self.state.extracted_documents,
                self.state.pending_ai_params
            )
        else:
            # No AI requested, workflow is complete
            debug_log("[ORCHESTRATOR] No AI generation requested. Workflow complete.")
            self._check_workflow_complete()

    def _check_workflow_complete(self):
        """Check if all requested workflow steps are complete."""
        vocab_needed = self.state.output_options.get('vocab_csv', False) if self.state.output_options else False
        ai_needed = self.state.output_options.get('meta_summary', False) if self.state.output_options else False

        vocab_done = self.state.vocab_complete or not vocab_needed
        ai_done = self.state.ai_complete or not ai_needed

        if vocab_done and ai_done:
            self.state.is_complete = True
            debug_log("[ORCHESTRATOR] All workflow steps complete.")

    def reset(self):
        """Reset the orchestrator state for a new workflow."""
        self.state = WorkflowState()
        debug_log("[ORCHESTRATOR] State reset for new workflow.")
