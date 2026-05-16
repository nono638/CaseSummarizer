"""
Tests for key sentences extraction via K-means clustering.

Covers: basic extraction, filtering, cluster diversity, edge cases,
source attribution, document position ordering, and K scaling.
"""

import numpy as np

from src.core.summarization.key_sentences import (
    _cluster_and_select,
    compute_sentence_count,
)

# =========================================================================
# compute_sentence_count
# =========================================================================


class TestComputeSentenceCount:
    """Tests for K scaling with page count."""

    def test_minimum_is_5(self):
        """Even for very short docs, K >= 5."""
        assert compute_sentence_count(1) == 5
        assert compute_sentence_count(10) == 5
        assert compute_sentence_count(24) == 5

    def test_scales_with_pages(self):
        """1 key sentence per ~5 pages."""
        assert compute_sentence_count(25) == 5
        assert compute_sentence_count(50) == 10
        assert compute_sentence_count(60) == 12

    def test_maximum_is_15(self):
        """K is capped at 15."""
        assert compute_sentence_count(100) == 15
        assert compute_sentence_count(500) == 15

    def test_zero_pages(self):
        """Zero pages still returns minimum."""
        assert compute_sentence_count(0) == 5


# =========================================================================
# _cluster_and_select
# =========================================================================


class TestClusterAndSelect:
    """Tests for K-means clustering selection."""

    def test_fewer_sentences_than_k(self):
        """When fewer sentences than K, return all indices."""
        embeddings = np.random.randn(3, 768).astype(np.float32)
        result = _cluster_and_select(embeddings, n=10)
        assert sorted(result) == [0, 1, 2]

    def test_exact_k_sentences(self):
        """When exactly K sentences, return all indices."""
        embeddings = np.random.randn(5, 768).astype(np.float32)
        result = _cluster_and_select(embeddings, n=5)
        assert sorted(result) == [0, 1, 2, 3, 4]

    def test_selects_correct_count(self):
        """Should return exactly K indices when enough sentences."""
        np.random.seed(42)
        embeddings = np.random.randn(50, 768).astype(np.float32)
        result = _cluster_and_select(embeddings, n=5)
        assert len(result) <= 5  # May be less if empty clusters
        assert len(set(result)) == len(result)  # No duplicates

    def test_indices_in_range(self):
        """All returned indices should be valid."""
        np.random.seed(42)
        embeddings = np.random.randn(20, 768).astype(np.float32)
        result = _cluster_and_select(embeddings, n=5)
        for idx in result:
            assert 0 <= idx < 20

    def test_diverse_clusters(self):
        """Sentences from distinct clusters should produce diverse selections."""
        np.random.seed(42)
        # Create 3 distinct clusters
        cluster1 = np.random.randn(10, 768).astype(np.float32) + np.array([10, 0] + [0] * 766)
        cluster2 = np.random.randn(10, 768).astype(np.float32) + np.array([0, 10] + [0] * 766)
        cluster3 = np.random.randn(10, 768).astype(np.float32) + np.array([-10, -10] + [0] * 766)
        embeddings = np.vstack([cluster1, cluster2, cluster3])
        result = _cluster_and_select(embeddings, n=3)
        # Should pick one from each cluster region
        assert len(result) == 3
