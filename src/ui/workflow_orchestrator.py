"""
Workflow Orchestrator Module

Manages the document processing workflow state machine, coordinating between:
- Document extraction (Step 1-2.5)
- Vocabulary extraction (Step 2.5b)
- AI summary generation (Step 3+)

This module separates workflow orchestration logic from UI updates,
improving testability and maintainability.

Workflow State Machine:
    IDLE -> EXTRACTING -> [VOCAB_EXTRACTION | AI_GENERATION] -> COMPLETE

The orchestrator decides WHAT to do next; the QueueMessageHandler decides
HOW to update the UI in response.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.logging_config import debug_log
from src.config import LEGAL_EXCLUDE_LIST_PATH, MEDICAL_TERMS_LIST_PATH
from src.utils.text_utils import combine_document_texts


@dataclass
class WorkflowState:
    """
    Represents the current state of a document processing workflow.

    Attributes:
        extracted_documents: List of documents that have been extracted
        pending_ai_params: AI generation parameters (model, length, options)
        output_options: Dictionary of requested output types
        is_complete: Whether the workflow has finished
    """
    extracted_documents: List[Dict] = None
    pending_ai_params: Optional[Dict] = None
    output_options: Optional[Dict] = None
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

    def get_output_options(self) -> Dict[str, bool]:
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
        extracted_documents: List[Dict],
        ai_params: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Handle completion of document extraction phase.

        This is the main orchestration method. It decides what workflow steps
        to execute next based on the current state and user options.

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

        actions_taken = {
            'vocab_extraction_started': False,
            'ai_generation_started': False,
            'workflow_complete': False,
            'combined_text': None
        }

        # If no AI generation requested, workflow is done
        if not ai_params:
            debug_log("[ORCHESTRATOR] No AI generation requested. Workflow complete.")
            self.state.is_complete = True
            actions_taken['workflow_complete'] = True
            return actions_taken

        # Start vocabulary extraction if requested (runs in parallel with AI)
        if self.state.output_options.get('vocab_csv', False):
            combined_text = self._get_combined_text(extracted_documents)
            actions_taken['combined_text'] = combined_text
            actions_taken['vocab_extraction_started'] = True
            self._start_vocab_extraction(combined_text)
            debug_log("[ORCHESTRATOR] Started vocabulary extraction (parallel).")

        # Start AI generation
        self._start_ai_generation(extracted_documents, ai_params)
        actions_taken['ai_generation_started'] = True
        debug_log("[ORCHESTRATOR] Started AI summary generation.")

        return actions_taken

    def _get_combined_text(self, extracted_documents: List[Dict]) -> str:
        """
        Get combined text from all documents for vocabulary extraction.

        Uses the shared utility function from src/utils/text_utils.

        Args:
            extracted_documents: List of document result dictionaries

        Returns:
            Combined text from all documents, separated by double newlines
        """
        combined = combine_document_texts(extracted_documents, include_headers=False)
        doc_count = sum(1 for d in extracted_documents if d.get('extracted_text'))
        debug_log(f"[ORCHESTRATOR] Combined {doc_count} documents "
                  f"({len(combined)} characters total).")
        return combined

    def _start_vocab_extraction(self, combined_text: str):
        """
        Start vocabulary extraction worker thread.

        Args:
            combined_text: Combined text from all documents
        """
        # Import here to avoid circular imports
        from src.ui.workers import VocabularyWorker

        worker = VocabularyWorker(
            combined_text=combined_text,
            ui_queue=self.main_window.ui_queue,
            exclude_list_path=str(LEGAL_EXCLUDE_LIST_PATH),
            medical_terms_path=str(MEDICAL_TERMS_LIST_PATH)
        )
        worker.start()
        debug_log("[ORCHESTRATOR] VocabularyWorker thread started.")

    def _start_ai_generation(self, extracted_documents: List[Dict], ai_params: Dict):
        """
        Start AI summary generation via main window.

        Delegates to main_window._start_ai_generation() which manages
        the AI worker process.

        Args:
            extracted_documents: List of extracted document dictionaries
            ai_params: AI generation parameters (model, length, options)
        """
        self.main_window._start_ai_generation(extracted_documents, ai_params)

    def on_summary_complete(self):
        """Handle completion of AI summary generation."""
        debug_log("[ORCHESTRATOR] AI summary generation complete.")
        # Note: Vocab extraction may still be running; that's fine (parallel)

    def on_vocab_complete(self):
        """Handle completion of vocabulary extraction."""
        debug_log("[ORCHESTRATOR] Vocabulary extraction complete.")

    def reset(self):
        """Reset the orchestrator state for a new workflow."""
        self.state = WorkflowState()
        debug_log("[ORCHESTRATOR] State reset for new workflow.")
