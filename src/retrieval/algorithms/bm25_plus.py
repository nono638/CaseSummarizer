"""
BM25+ Retrieval Algorithm for LocalScribe Q&A.

Implements lexical (keyword-based) retrieval using BM25+, an improved version
of the classic BM25 algorithm that addresses term frequency saturation issues.

BM25+ vs BM25:
- Standard BM25 has diminishing returns for term frequency (TF saturation)
- BM25+ adds a lower bound (delta) to the TF component, improving recall
- Better for legal documents where exact terminology matters

Why BM25+ for Legal Documents:
- Legal language is precise - exact terms matter ("plaintiff" vs "claimant")
- No neural model needed - faster, deterministic, no GPU required
- Works out-of-the-box without domain-specific training
- Handles rare legal terminology that embedding models may not understand

Reference:
    Lv, Y., & Zhai, C. (2011). "Lower-bounding term frequency normalization"
    CIKM '11: Proceedings of the 20th ACM international conference on Information
    and knowledge management.
"""

import re
import time
from typing import Any

from rank_bm25 import BM25Plus

from src.config import DEBUG_MODE
from src.logging_config import debug_log
from src.retrieval.algorithms import register_algorithm
from src.retrieval.base import (
    AlgorithmRetrievalResult,
    BaseRetrievalAlgorithm,
    DocumentChunk,
    RetrievedChunk,
)


def simple_tokenize(text: str) -> list[str]:
    """
    Simple tokenizer for BM25 indexing.

    Converts text to lowercase, removes punctuation, and splits on whitespace.
    For legal documents, we preserve hyphenated terms and numbers.

    Args:
        text: Input text to tokenize

    Returns:
        List of tokens (words)
    """
    # Lowercase
    text = text.lower()

    # Keep alphanumeric, hyphens (for compound terms), and spaces
    # Remove other punctuation
    text = re.sub(r"[^\w\s\-]", " ", text)

    # Split on whitespace and filter empty tokens
    tokens = [token.strip() for token in text.split() if token.strip()]

    return tokens


@register_algorithm
class BM25PlusRetriever(BaseRetrievalAlgorithm):
    """
    BM25+ retrieval algorithm for lexical/keyword search.

    Uses the BM25Plus algorithm from rank_bm25 library for term-based retrieval.
    Scores are normalized to 0-1 range for compatibility with other algorithms.

    Attributes:
        name: Algorithm identifier ("BM25+")
        weight: Default weight for merging (1.0 - primary algorithm)
        enabled: Whether this algorithm is active

    Example:
        retriever = BM25PlusRetriever()
        retriever.index_documents(chunks)
        results = retriever.retrieve("Who are the plaintiffs?", k=5)
    """

    name: str = "BM25+"
    weight: float = 1.0
    enabled: bool = True

    def __init__(self):
        """Initialize BM25+ retriever."""
        self._index: BM25Plus | None = None
        self._chunks: list[DocumentChunk] = []
        self._tokenized_corpus: list[list[str]] = []

    def index_documents(self, chunks: list[DocumentChunk]) -> None:
        """
        Build BM25+ index from document chunks.

        Tokenizes each chunk and creates the BM25+ index for retrieval.

        Args:
            chunks: List of DocumentChunk objects to index

        Raises:
            ValueError: If chunks is empty
        """
        start_time = time.perf_counter()

        if not chunks:
            raise ValueError("Cannot index empty chunk list")

        self._chunks = chunks

        # Tokenize all chunks
        self._tokenized_corpus = [simple_tokenize(chunk.text) for chunk in chunks]

        # Build BM25+ index
        # BM25Plus parameters: k1=1.5, b=0.75, delta=1 (defaults)
        # delta=1 is the BM25+ improvement over standard BM25
        self._index = BM25Plus(self._tokenized_corpus)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if DEBUG_MODE:
            debug_log(f"[BM25+] Indexed {len(chunks)} chunks in {elapsed_ms:.1f}ms")
            avg_tokens = sum(len(t) for t in self._tokenized_corpus) / len(chunks)
            debug_log(f"[BM25+] Average tokens per chunk: {avg_tokens:.1f}")

    def retrieve(self, query: str, k: int = 5) -> AlgorithmRetrievalResult:
        """
        Retrieve top-k relevant chunks using BM25+ scoring.

        Args:
            query: The search query string
            k: Maximum number of chunks to retrieve

        Returns:
            AlgorithmRetrievalResult with ranked chunks

        Raises:
            RuntimeError: If index_documents() hasn't been called
        """
        start_time = time.perf_counter()

        if not self.is_indexed:
            raise RuntimeError("Index not built. Call index_documents() first.")

        # Tokenize query
        query_tokens = simple_tokenize(query)

        if DEBUG_MODE:
            debug_log(f"[BM25+] Query: '{query[:50]}...' -> {len(query_tokens)} tokens")

        # Get BM25+ scores for all documents
        raw_scores = self._index.get_scores(query_tokens)

        # Get top-k indices (sorted by score descending)
        # Use negative scores for argsort to get descending order
        import numpy as np

        top_k_indices = np.argsort(raw_scores)[::-1][:k]

        # Normalize scores to 0-1 range
        # BM25 scores are unbounded positive values
        max_score = max(raw_scores) if max(raw_scores) > 0 else 1.0

        # Build result chunks
        retrieved_chunks = []
        for idx in top_k_indices:
            raw_score = raw_scores[idx]

            # Skip zero-score chunks (no query terms found)
            if raw_score <= 0:
                continue

            chunk = self._chunks[idx]

            # Normalize score to 0-1 range
            # Using sigmoid-like normalization to handle score distribution
            normalized_score = raw_score / (raw_score + max_score) if max_score > 0 else 0

            retrieved_chunks.append(RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                relevance_score=normalized_score,
                raw_score=raw_score,
                source_algorithm=self.name,
                filename=chunk.filename,
                chunk_num=chunk.chunk_num,
                section_name=chunk.section_name,
                metadata={
                    "query_tokens": query_tokens,
                    "chunk_tokens": len(self._tokenized_corpus[idx]),
                }
            ))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if DEBUG_MODE:
            debug_log(f"[BM25+] Retrieved {len(retrieved_chunks)} chunks in {elapsed_ms:.1f}ms")
            for i, chunk in enumerate(retrieved_chunks[:3]):
                debug_log(f"  [{i + 1}] score={chunk.raw_score:.2f} -> {chunk.relevance_score:.3f} | {chunk.filename}")

        return AlgorithmRetrievalResult(
            chunks=retrieved_chunks,
            processing_time_ms=elapsed_ms,
            query=query,
            metadata={
                "algorithm": self.name,
                "index_size": len(self._chunks),
                "max_raw_score": max_score,
                "query_token_count": len(query_tokens),
            }
        )

    @property
    def is_indexed(self) -> bool:
        """Check if the BM25+ index is built."""
        return self._index is not None and len(self._chunks) > 0

    def get_config(self) -> dict[str, Any]:
        """Return BM25+ configuration."""
        config = super().get_config()
        config.update({
            "index_size": len(self._chunks) if self._chunks else 0,
            "algorithm_variant": "BM25Plus",
            "parameters": {
                "k1": 1.5,  # BM25+ default
                "b": 0.75,  # BM25+ default
                "delta": 1.0,  # BM25+ improvement factor
            }
        })
        return config
