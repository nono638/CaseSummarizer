"""
Summarization Package for LocalScribe

This package provides multi-document summarization with hierarchical
map-reduce architecture:

1. Map Phase: Each document is processed through ProgressiveSummarizer
   (chunking → chunk summaries → progressive document summary)

2. Reduce Phase: Individual document summaries are combined into
   a meta-summary that synthesizes the overall case narrative.

Components:
    DocumentSummaryResult - Result from single document summarization
    MultiDocumentSummaryResult - Result from multi-document summarization
    ProgressiveDocumentSummarizer - Wraps ProgressiveSummarizer for single docs
    MultiDocumentOrchestrator - Coordinates parallel multi-doc processing
    MetaSummaryGenerator - Combines individual summaries into meta-summary

Usage:
    from src.summarization import (
        ProgressiveDocumentSummarizer,
        MultiDocumentOrchestrator,
        MultiDocumentSummaryResult,
    )

    # Create components
    doc_summarizer = ProgressiveDocumentSummarizer(model_manager)
    orchestrator = MultiDocumentOrchestrator(doc_summarizer, model_manager)

    # Process multiple documents
    result = orchestrator.summarize_documents(documents)
    print(result.meta_summary)
"""

from .result_types import (
    DocumentSummaryResult,
    MultiDocumentSummaryResult,
)
from .document_summarizer import (
    DocumentSummarizer,
    ProgressiveDocumentSummarizer,
)
from .multi_document_orchestrator import MultiDocumentOrchestrator

__all__ = [
    # Result types
    'DocumentSummaryResult',
    'MultiDocumentSummaryResult',
    # Document summarizer
    'DocumentSummarizer',
    'ProgressiveDocumentSummarizer',
    # Multi-document orchestration
    'MultiDocumentOrchestrator',
]
