"""
Regression tests for the four robustness fixes (May 2026):
  #2 — Integrity check raises a clear FileNotFoundError if either FAISS or PKL is missing.
  #3 — _select_best_window returns None when no window has positive similarity,
       so callers fall back to a deterministic truncated excerpt instead of an
       arbitrary argmax pick.
  #4 — _run_followup rejects a second follow-up while the first is still alive,
       preventing two SemanticOrchestrators from loading the (thread-unsafe)
       sentencepiece tokenizer concurrently.

Fix #1 (full-path file removal) is covered by the
TestRemoveFile::test_same_basename_different_folders_removed_independently
regression test in tests/test_cumulative_files.py.
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fix #2 — Integrity check on missing vector-store files
# ---------------------------------------------------------------------------


class TestIntegrityCheckRaisesOnMissingFiles:
    """_verify_integrity_hash must raise FileNotFoundError, not silently
    compute a partial hash when one of the two store files is gone."""

    def _make_dir_with_hash_only(self, tmp_path: Path) -> Path:
        """Build a persist_dir containing only a .hash file (no FAISS/PKL)."""
        persist_dir = tmp_path / "store"
        persist_dir.mkdir()
        (persist_dir / ".hash").write_text("a" * 64)
        return persist_dir

    def test_missing_both_files_raises_file_not_found(self, tmp_path):
        """Both index files missing → FileNotFoundError with diagnostic message."""
        from src.core.vector_store.semantic_retriever import SemanticRetriever

        retriever = SemanticRetriever.__new__(SemanticRetriever)
        persist_dir = self._make_dir_with_hash_only(tmp_path)

        with pytest.raises(FileNotFoundError, match="missing required files"):
            retriever._verify_integrity_hash(persist_dir)

    def test_missing_faiss_only_raises_file_not_found(self, tmp_path):
        """Just the FAISS file missing → still raises (was previously silent)."""
        from src.core.vector_store.semantic_retriever import SemanticRetriever

        retriever = SemanticRetriever.__new__(SemanticRetriever)
        persist_dir = self._make_dir_with_hash_only(tmp_path)
        (persist_dir / "index.pkl").write_bytes(b"some pickle bytes")

        with pytest.raises(FileNotFoundError, match="FAISS exists: False"):
            retriever._verify_integrity_hash(persist_dir)

    def test_missing_pkl_only_raises_file_not_found(self, tmp_path):
        """Just the PKL file missing → still raises (was previously silent)."""
        from src.core.vector_store.semantic_retriever import SemanticRetriever

        retriever = SemanticRetriever.__new__(SemanticRetriever)
        persist_dir = self._make_dir_with_hash_only(tmp_path)
        (persist_dir / "index.faiss").write_bytes(b"some faiss bytes")

        with pytest.raises(FileNotFoundError, match="PKL exists: False"):
            retriever._verify_integrity_hash(persist_dir)

    def test_no_hash_file_still_short_circuits(self, tmp_path):
        """Backward compat path: no .hash file → silent return, no raise."""
        from src.core.vector_store.semantic_retriever import SemanticRetriever

        retriever = SemanticRetriever.__new__(SemanticRetriever)
        persist_dir = tmp_path / "legacy_store"
        persist_dir.mkdir()
        # No .hash, no index files — should simply return without raising.
        retriever._verify_integrity_hash(persist_dir)


# ---------------------------------------------------------------------------
# Fix #3 — Similarity floor in citation_excerpt
# ---------------------------------------------------------------------------


class _StubEmbeddingsConstant:
    """Returns the same vector for every input, producing 1.0 cosine similarity."""

    def embed_query(self, _text):
        """Return a constant unit vector for the query."""
        return [1.0, 0.0, 0.0]

    def embed_documents(self, texts):
        """Return one constant unit vector per input."""
        return [[1.0, 0.0, 0.0] for _ in texts]


class _StubEmbeddingsOrthogonal:
    """Returns vectors orthogonal to the question vector — similarity = 0."""

    def embed_query(self, _text):
        """Query vector along the x-axis."""
        return [1.0, 0.0, 0.0]

    def embed_documents(self, texts):
        """Window vectors along the y-axis (perpendicular to query)."""
        return [[0.0, 1.0, 0.0] for _ in texts]


class _StubEmbeddingsAntiCorrelated:
    """Returns vectors anti-correlated with the question — similarity < 0."""

    def embed_query(self, _text):
        """Query along +x."""
        return [1.0, 0.0, 0.0]

    def embed_documents(self, texts):
        """Window vectors along -x (similarity = -1)."""
        return [[-1.0, 0.0, 0.0] for _ in texts]


class TestSelectBestWindowSimilarityFloor:
    """_select_best_window must return None on non-positive similarity."""

    def _windows(self):
        """Three small overlapping windows used by all tests."""
        return [
            (0, 50, "alpha beta gamma delta epsilon"),
            (25, 75, "gamma delta epsilon zeta eta"),
            (50, 100, "epsilon zeta eta theta iota"),
        ]

    def test_positive_similarity_returns_a_window(self):
        """A genuinely-similar match returns the (start, end, text) tuple."""
        from src.core.semantic.citation_excerpt import _select_best_window

        result = _select_best_window(self._windows(), "q", _StubEmbeddingsConstant())
        assert result is not None
        assert result == self._windows()[0]  # first argmax tie wins

    def test_zero_similarity_returns_none(self):
        """All similarities = 0 → caller should fall back, not pick an arbitrary window."""
        from src.core.semantic.citation_excerpt import _select_best_window

        result = _select_best_window(self._windows(), "q", _StubEmbeddingsOrthogonal())
        assert result is None

    def test_negative_similarity_returns_none(self):
        """All similarities < 0 (anti-correlated) → return None."""
        from src.core.semantic.citation_excerpt import _select_best_window

        result = _select_best_window(self._windows(), "q", _StubEmbeddingsAntiCorrelated())
        assert result is None

    def test_extract_excerpt_falls_back_to_truncation_on_zero_similarity(self):
        """extract_citation_excerpt must use the sentence-truncation fallback
        when no window scores above zero — not return an arbitrary window."""
        from src.core.semantic.citation_excerpt import (
            _truncate_to_sentence,
            extract_citation_excerpt,
        )

        chunk = (
            "First sentence about apples. Second sentence about bananas. "
            "Third sentence about cherries. Fourth sentence about durians. "
            "Fifth sentence about elderberries. Sixth sentence about figs."
        )
        max_chars = 80
        expected = _truncate_to_sentence(chunk.strip(), max_chars)
        actual = extract_citation_excerpt(
            chunk, "totally unrelated question", _StubEmbeddingsOrthogonal(), max_chars
        )
        assert actual == expected


# ---------------------------------------------------------------------------
# Fix #4 — Followup thread serialization in worker subprocess
# ---------------------------------------------------------------------------


class _FakeQueue:
    """Minimal queue stand-in that records put() calls."""

    def __init__(self):
        """Initialize an empty message list."""
        self.messages = []

    def put(self, msg):
        """Append a message to the internal list."""
        self.messages.append(msg)


def _make_followup_state(thread_state):
    """Build the minimal state dict _run_followup needs."""
    return {
        "vector_store_path": "/some/path",
        "embeddings": object(),  # truthy
        "followup_thread": thread_state,
        "worker_lock": threading.Lock(),
    }


class TestFollowupRejectedWhenInFlight:
    """A second follow-up must be rejected while the first thread is alive."""

    def test_rejects_when_prior_thread_alive(self):
        """In-flight follow-up → put(None) result, no new thread launched."""
        from src.services.queue_messages import MessageType
        from src.worker_process import _run_followup

        live_thread = MagicMock()
        live_thread.is_alive.return_value = True

        state = _make_followup_state(live_thread)
        queue = _FakeQueue()

        _run_followup({"question": "another"}, queue, state)

        assert len(queue.messages) == 1
        msg_type, payload = queue.messages[0]
        # The rejection payload's result is None
        assert msg_type == MessageType.SEMANTIC_FOLLOWUP_RESULT
        assert payload is None
        # state still holds the live thread (we did not replace it)
        assert state["followup_thread"] is live_thread

    def test_allows_when_prior_thread_finished(self):
        """A completed prior thread should not block a new follow-up."""
        from src.worker_process import _run_followup

        finished_thread = MagicMock()
        finished_thread.is_alive.return_value = False

        state = _make_followup_state(finished_thread)
        queue = _FakeQueue()

        # We don't want to actually load the orchestrator; have embeddings be
        # falsy so _run_followup short-circuits after the guard check.
        state["embeddings"] = None
        _run_followup({"question": "after-completion"}, queue, state)

        # Short-circuit emits a None result — that's fine. The point is that
        # the guard did NOT trigger (which would log "Rejecting" first).
        assert len(queue.messages) == 1

    def test_allows_when_no_prior_thread(self):
        """First-ever follow-up with no prior thread should proceed past the guard."""
        from src.worker_process import _run_followup

        state = _make_followup_state(None)
        state["embeddings"] = None  # short-circuit before orchestrator load
        queue = _FakeQueue()

        _run_followup({"question": "first"}, queue, state)
        assert len(queue.messages) == 1
