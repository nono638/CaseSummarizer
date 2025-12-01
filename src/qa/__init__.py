"""
Q&A Package for LocalScribe.

Provides question-answering functionality using FAISS vector search and
optional Ollama LLM answer generation.

Components:
- QAOrchestrator: Coordinates Q&A process (vector search + answer generation)
- AnswerGenerator: Generates answers via extraction or Ollama
- QAResult: Data model for question-answer pairs

Usage:
    from src.qa import QAOrchestrator, QAResult, AnswerMode

    orchestrator = QAOrchestrator(vector_store_path, embeddings)
    results = orchestrator.run_default_questions()
    for result in results:
        print(f"Q: {result.question}")
        print(f"A: {result.answer}")
"""

from src.qa.answer_generator import AnswerGenerator, AnswerMode
from src.qa.qa_orchestrator import QAOrchestrator, QAResult

__all__ = [
    "QAOrchestrator",
    "QAResult",
    "AnswerGenerator",
    "AnswerMode",
]
