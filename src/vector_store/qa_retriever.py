"""
Q&A Retriever for LocalScribe.

Retrieves relevant document context for user questions using FAISS similarity search.
Formats context with source citations for RAG (Retrieval-Augmented Generation).

Architecture:
- Loads FAISS index from disk (file-based persistence)
- Performs similarity search to find relevant chunks
- Returns formatted context string with source attribution
- Supports relevance score filtering

Integration:
- Used by QAWorker in background thread
- Provides context to Ollama for answer generation
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import DEBUG_MODE, QA_RETRIEVAL_K, QA_SIMILARITY_THRESHOLD
from src.logging_config import debug_log

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings


@dataclass
class SourceInfo:
    """Source information for a retrieved chunk."""

    filename: str
    chunk_num: int
    section: str
    relevance_score: float
    word_count: int


@dataclass
class RetrievalResult:
    """Result of context retrieval."""

    context: str
    sources: list[SourceInfo]
    chunks_retrieved: int
    retrieval_time_ms: float


class QARetriever:
    """
    Retrieves relevant context for Q&A from FAISS vector store.

    Uses similarity search to find the most relevant document chunks
    for a given question. Formats results with source citations for
    accurate attribution in AI-generated answers.

    Example:
        retriever = QARetriever(persist_dir, embeddings)
        result = retriever.retrieve_context("Who are the plaintiffs?")
        print(f"Context: {result.context}")
        print(f"Sources: {[s.filename for s in result.sources]}")
    """

    def __init__(
        self,
        vector_store_path: Path,
        embeddings: "HuggingFaceEmbeddings"
    ):
        """
        Initialize retriever with existing vector store.

        Args:
            vector_store_path: Path to directory containing index.faiss/index.pkl
            embeddings: HuggingFaceEmbeddings model for query encoding

        Raises:
            FileNotFoundError: If vector store files don't exist
        """
        from langchain_community.vectorstores import FAISS

        self.vector_store_path = Path(vector_store_path)
        self.embeddings = embeddings

        # Verify files exist
        faiss_file = self.vector_store_path / "index.faiss"
        if not faiss_file.exists():
            raise FileNotFoundError(
                f"Vector store not found at {self.vector_store_path}. "
                "Ensure documents have been processed first."
            )

        # Load FAISS index from disk
        # allow_dangerous_deserialization=True is safe because we control the data
        self.vector_store = FAISS.load_local(
            folder_path=str(self.vector_store_path),
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )

        if DEBUG_MODE:
            debug_log(f"[QARetriever] Loaded vector store from: {self.vector_store_path}")

    def retrieve_context(
        self,
        question: str,
        k: int | None = None,
        min_score: float | None = None
    ) -> RetrievalResult:
        """
        Retrieve top-k relevant chunks for a question.

        Uses cosine similarity to find the most relevant document chunks.
        Filters by minimum relevance score if specified.

        Args:
            question: The user's question
            k: Number of chunks to retrieve (default: QA_RETRIEVAL_K from config)
            min_score: Minimum relevance score (0-1) to include (default: from config)

        Returns:
            RetrievalResult with formatted context and source information
        """
        import time
        start_time = time.perf_counter()

        # Use config defaults if not specified
        k = k or QA_RETRIEVAL_K
        min_score = min_score if min_score is not None else QA_SIMILARITY_THRESHOLD

        if DEBUG_MODE:
            debug_log(f"[QARetriever] Query: '{question[:50]}...' (k={k})")

        # Perform similarity search with scores
        # Returns list of (Document, score) tuples
        docs_and_scores = self.vector_store.similarity_search_with_relevance_scores(
            question, k=k
        )

        # Filter by minimum score and build results
        context_parts = []
        sources = []

        for doc, score in docs_and_scores:
            # Skip low-relevance chunks
            if score < min_score:
                if DEBUG_MODE:
                    debug_log(f"[QARetriever] Skipped chunk (score {score:.2f} < {min_score})")
                continue

            # Extract metadata
            metadata = doc.metadata
            filename = metadata.get('filename', 'unknown')
            chunk_num = metadata.get('chunk_num', 0)
            section = metadata.get('section_name', 'N/A')
            word_count = metadata.get('word_count', len(doc.page_content.split()))

            # Format source citation for context
            source_cite = f"[{filename}"
            if section and section != 'N/A':
                source_cite += f", {section}"
            source_cite += "]:"

            context_parts.append(f"{source_cite}\n{doc.page_content}")

            sources.append(SourceInfo(
                filename=filename,
                chunk_num=chunk_num,
                section=section,
                relevance_score=score,
                word_count=word_count
            ))

        # Combine context parts with separator
        context = "\n\n---\n\n".join(context_parts) if context_parts else ""

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if DEBUG_MODE:
            debug_log(f"[QARetriever] Retrieved {len(sources)} chunks in {elapsed_ms:.1f}ms")
            for src in sources:
                debug_log(f"  - {src.filename} (chunk {src.chunk_num}, score {src.relevance_score:.2f})")

        return RetrievalResult(
            context=context,
            sources=sources,
            chunks_retrieved=len(sources),
            retrieval_time_ms=elapsed_ms
        )

    def get_relevant_sources_summary(self, result: RetrievalResult) -> str:
        """
        Format source information for display.

        Creates a readable summary of sources used in the answer.

        Args:
            result: RetrievalResult from retrieve_context()

        Returns:
            Formatted string like "complaint.pdf (Section Parties), answer.pdf"
        """
        if not result.sources:
            return "No sources found"

        summaries = []
        seen_files = set()

        for source in result.sources:
            if source.filename not in seen_files:
                if source.section and source.section != 'N/A':
                    summaries.append(f"{source.filename} ({source.section})")
                else:
                    summaries.append(source.filename)
                seen_files.add(source.filename)

        return ", ".join(summaries)

    def get_chunk_count(self) -> int:
        """
        Get total number of chunks in the vector store.

        Returns:
            Number of indexed chunks
        """
        # FAISS stores document count in index.ntotal
        return self.vector_store.index.ntotal
