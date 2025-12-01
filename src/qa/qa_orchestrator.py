"""
Q&A Orchestrator for LocalScribe.

Coordinates the Q&A process: loading questions, performing vector search,
and generating answers. Manages the list of QAResult objects for display
and export.

Architecture:
- Loads default questions from qa_questions.yaml
- Uses QARetriever for FAISS similarity search
- Uses AnswerGenerator for answer generation (extraction or Ollama)
- Tracks include_in_export flag for selective export

Integration:
- Used by QAWorker for background processing
- Results displayed in QAPanel UI widget
- Exportable to TXT with checkbox-based selection
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from src.config import DEBUG_MODE
from src.logging_config import debug_log
from src.vector_store.qa_retriever import QARetriever, RetrievalResult

# Default questions YAML path (relative to this file: src/qa/ -> config/)
DEFAULT_QUESTIONS_PATH = Path(__file__).parent.parent.parent / "config" / "qa_questions.yaml"


@dataclass
class QAResult:
    """
    Single question-answer pair with metadata.

    Attributes:
        question: The question that was asked
        answer: The generated answer
        include_in_export: Whether to include this Q&A in export (default: True)
        source_summary: Human-readable source citation (e.g., "complaint.pdf, page 3")
        answer_mode: How the answer was generated ("extraction" or "ollama")
        confidence: Relevance score from vector search (0-1)
        retrieval_time_ms: Time taken for vector search
        is_followup: Whether this is a user-asked follow-up question
    """

    question: str
    answer: str
    include_in_export: bool = True
    source_summary: str = ""
    answer_mode: Literal["extraction", "ollama"] = "extraction"
    confidence: float = 0.0
    retrieval_time_ms: float = 0.0
    is_followup: bool = False


@dataclass
class QuestionDef:
    """Question definition from YAML config."""

    id: str
    text: str
    category: str
    question_type: str  # "classification" or "extraction"


class QAOrchestrator:
    """
    Coordinates Q&A process: vector search + answer generation.

    Manages the full Q&A workflow:
    1. Load questions from YAML config
    2. For each question, perform vector similarity search
    3. Generate answer from retrieved context
    4. Track results with export flags

    Example:
        orchestrator = QAOrchestrator(vector_store_path, embeddings)
        results = orchestrator.run_default_questions()

        # User can toggle include_in_export
        results[0].include_in_export = False

        # Ask follow-up question
        followup = orchestrator.ask_followup("What injuries were claimed?")
    """

    def __init__(
        self,
        vector_store_path: Path,
        embeddings,
        answer_mode: str = "extraction",
        questions_path: Path | None = None
    ):
        """
        Initialize Q&A orchestrator.

        Args:
            vector_store_path: Path to FAISS index directory
            embeddings: HuggingFaceEmbeddings model for query encoding
            answer_mode: "extraction" (fast, from context) or "ollama" (LLM-generated)
            questions_path: Path to questions YAML (default: config/qa_questions.yaml)
        """
        self.vector_store_path = Path(vector_store_path)
        self.embeddings = embeddings
        self.answer_mode = answer_mode
        self.questions_path = questions_path or DEFAULT_QUESTIONS_PATH

        # Initialize retriever
        self.retriever = QARetriever(self.vector_store_path, self.embeddings)

        # Initialize answer generator (lazy import to avoid circular deps)
        from src.qa.answer_generator import AnswerGenerator
        self.answer_generator = AnswerGenerator(mode=answer_mode)

        # Results storage
        self.results: list[QAResult] = []

        # Load questions
        self._questions: list[QuestionDef] = []
        self._load_questions()

        if DEBUG_MODE:
            debug_log(f"[QAOrchestrator] Initialized with {len(self._questions)} questions")
            debug_log(f"[QAOrchestrator] Answer mode: {answer_mode}")

    def _load_questions(self) -> None:
        """Load question definitions from YAML config."""
        if not self.questions_path.exists():
            debug_log(f"[QAOrchestrator] Questions file not found: {self.questions_path}")
            return

        try:
            with open(self.questions_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not config or "questions" not in config:
                debug_log("[QAOrchestrator] No questions found in YAML config")
                return

            for q in config["questions"]:
                self._questions.append(QuestionDef(
                    id=q.get("id", ""),
                    text=q.get("text", ""),
                    category=q.get("category", "General"),
                    question_type=q.get("type", "extraction")
                ))

            if DEBUG_MODE:
                debug_log(f"[QAOrchestrator] Loaded {len(self._questions)} questions")

        except Exception as e:
            debug_log(f"[QAOrchestrator] Error loading questions: {e}")

    def get_default_questions(self) -> list[str]:
        """
        Get list of default question texts.

        Returns:
            List of question strings to ask
        """
        return [q.text for q in self._questions]

    def run_default_questions(self, progress_callback=None) -> list[QAResult]:
        """
        Run all default questions against the document.

        Args:
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of QAResult objects (also stored in self.results)
        """
        self.results = []
        questions = self.get_default_questions()
        total = len(questions)

        for i, question in enumerate(questions):
            if progress_callback:
                progress_callback(i, total)

            result = self._ask_single_question(question, is_followup=False)
            self.results.append(result)

            if DEBUG_MODE:
                debug_log(f"[QAOrchestrator] Q{i + 1}/{total}: {question[:40]}... -> {len(result.answer)} chars")

        if progress_callback:
            progress_callback(total, total)

        return self.results

    def ask_followup(self, question: str) -> QAResult:
        """
        Ask a single follow-up question.

        Args:
            question: User's follow-up question

        Returns:
            QAResult (also appended to self.results)
        """
        result = self._ask_single_question(question, is_followup=True)
        self.results.append(result)
        return result

    def _ask_single_question(self, question: str, is_followup: bool = False) -> QAResult:
        """
        Ask a single question and generate answer.

        Args:
            question: The question to ask
            is_followup: Whether this is a user-initiated follow-up

        Returns:
            QAResult with answer and metadata
        """
        # Retrieve relevant context
        retrieval_result = self.retriever.retrieve_context(question)

        # Generate answer
        if retrieval_result.context:
            answer = self.answer_generator.generate(question, retrieval_result.context)
            source_summary = self.retriever.get_relevant_sources_summary(retrieval_result)
            confidence = self._calculate_confidence(retrieval_result)
        else:
            answer = "No relevant information found in the documents."
            source_summary = ""
            confidence = 0.0

        return QAResult(
            question=question,
            answer=answer,
            include_in_export=True,  # Default to included
            source_summary=source_summary,
            answer_mode=self.answer_mode,
            confidence=confidence,
            retrieval_time_ms=retrieval_result.retrieval_time_ms,
            is_followup=is_followup
        )

    def _calculate_confidence(self, retrieval_result: RetrievalResult) -> float:
        """
        Calculate overall confidence score from retrieval results.

        Uses average relevance score of retrieved chunks.

        Args:
            retrieval_result: Result from QARetriever

        Returns:
            Confidence score (0-1)
        """
        if not retrieval_result.sources:
            return 0.0

        avg_score = sum(s.relevance_score for s in retrieval_result.sources) / len(retrieval_result.sources)
        return round(avg_score, 2)

    def get_exportable_results(self) -> list[QAResult]:
        """
        Get results where include_in_export is True.

        Returns:
            Filtered list of QAResult objects
        """
        return [r for r in self.results if r.include_in_export]

    def toggle_export(self, index: int) -> bool:
        """
        Toggle include_in_export for a result by index.

        Args:
            index: Index of the result to toggle

        Returns:
            New value of include_in_export
        """
        if 0 <= index < len(self.results):
            self.results[index].include_in_export = not self.results[index].include_in_export
            return self.results[index].include_in_export
        return False

    def clear_results(self) -> None:
        """Clear all stored results."""
        self.results = []

    def export_to_text(self) -> str:
        """
        Format exportable results as plain text.

        Returns:
            Formatted text string suitable for TXT export
        """
        exportable = self.get_exportable_results()
        if not exportable:
            return ""

        lines = [
            "=" * 60,
            "DOCUMENT Q&A SUMMARY",
            "=" * 60,
            ""
        ]

        for i, result in enumerate(exportable, 1):
            lines.append(f"Q{i}: {result.question}")
            lines.append(f"A: {result.answer}")
            if result.source_summary:
                lines.append(f"   [Source: {result.source_summary}]")
            lines.append("")

        return "\n".join(lines)
