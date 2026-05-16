"""
Behavioral tests for src.worker_process._build_scorer_inputs.

This helper turns a vocabulary list into the input dict that
key_sentences.extract_key_passages expects. It also pulls rejected
terms from the feedback CSV and a Google frequency rank map.

Coverage focus:
- Required output keys.
- Term lowercasing.
- Quality score propagation.
- Person-term set membership rules (IS_PERSON == YES only).
- Empty-term skip.
- Resilience when feedback / frequency loaders raise.
"""

from unittest.mock import patch

# ---------------------------------------------------------------------------
# Output shape & basic mapping
# ---------------------------------------------------------------------------


class TestBuildScorerInputsShape:
    """_build_scorer_inputs returns a dict with the four documented keys."""

    def test_returns_all_four_keys(self):
        """Result must expose vocab_terms, person_terms, rejected_terms, frequency_rank_map."""
        from src.worker_process import _build_scorer_inputs

        out = _build_scorer_inputs([])
        assert set(out.keys()) == {
            "vocab_terms",
            "person_terms",
            "rejected_terms",
            "frequency_rank_map",
        }

    def test_empty_input_returns_empty_collections(self):
        """An empty vocab list produces empty mappings/sets."""
        from src.worker_process import _build_scorer_inputs

        out = _build_scorer_inputs([])
        assert out["vocab_terms"] == {}
        assert out["person_terms"] == set()
        # rejected_terms / frequency_rank_map come from external loaders;
        # they may be non-empty depending on the dev environment, but they
        # must still be the documented types.
        assert isinstance(out["rejected_terms"], set)
        assert isinstance(out["frequency_rank_map"], dict)


class TestVocabTermMapping:
    """Term/quality pairs are normalized into the vocab_terms dict."""

    def test_term_keys_are_lowercased(self):
        """Vocab terms are stored in lower-case for case-insensitive lookups."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "Negligence", "Quality Score": 5}]
        out = _build_scorer_inputs(vocab)
        assert "negligence" in out["vocab_terms"]
        assert "Negligence" not in out["vocab_terms"]

    def test_quality_score_value_preserved(self):
        """Quality score is the value mapped under the lowercased term."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "duty", "Quality Score": 7}]
        out = _build_scorer_inputs(vocab)
        assert out["vocab_terms"]["duty"] == 7

    def test_missing_quality_score_defaults_to_zero(self):
        """A vocab entry without Quality Score falls back to 0."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "breach"}]
        out = _build_scorer_inputs(vocab)
        assert out["vocab_terms"]["breach"] == 0

    def test_empty_term_skipped(self):
        """Entries with empty Term must be ignored entirely."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "", "Quality Score": 9}, {"Term": "real", "Quality Score": 3}]
        out = _build_scorer_inputs(vocab)
        assert "real" in out["vocab_terms"]
        # Empty string must NOT be a key.
        assert "" not in out["vocab_terms"]
        assert len(out["vocab_terms"]) == 1

    def test_missing_term_key_skipped(self):
        """Entries with no Term key at all are skipped (not crashed on)."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Quality Score": 4}, {"Term": "valid"}]
        out = _build_scorer_inputs(vocab)
        assert list(out["vocab_terms"].keys()) == ["valid"]

    def test_later_duplicate_overwrites_earlier(self):
        """If two entries share a term (case-insensitive), the later one wins."""
        from src.worker_process import _build_scorer_inputs

        vocab = [
            {"Term": "Damage", "Quality Score": 1},
            {"Term": "damage", "Quality Score": 9},
        ]
        out = _build_scorer_inputs(vocab)
        assert out["vocab_terms"]["damage"] == 9


# ---------------------------------------------------------------------------
# person_terms classification
# ---------------------------------------------------------------------------


class TestPersonTerms:
    """Only entries flagged IS_PERSON == 'Yes' land in person_terms."""

    def test_person_yes_added_lowercased(self):
        """Person-flagged term is added in lowercase form."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "Jane Doe", "Quality Score": 8, "Is Person": "Yes"}]
        out = _build_scorer_inputs(vocab)
        assert "jane doe" in out["person_terms"]

    def test_person_no_excluded(self):
        """A vocab term flagged 'No' must NOT appear in person_terms."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "negligence", "Quality Score": 5, "Is Person": "No"}]
        out = _build_scorer_inputs(vocab)
        assert "negligence" not in out["person_terms"]

    def test_person_flag_absent_excluded(self):
        """No Is Person key at all -> term is treated as non-person."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "spine", "Quality Score": 4}]
        out = _build_scorer_inputs(vocab)
        assert "spine" not in out["person_terms"]

    def test_person_flag_other_string_excluded(self):
        """Any value other than the literal 'Yes' is treated as non-person."""
        from src.worker_process import _build_scorer_inputs

        # Case mismatch and truthy-but-wrong values must not count as person.
        for flag in ("yes", "true", "1", "person"):
            out = _build_scorer_inputs([{"Term": "x", "Is Person": flag}])
            assert "x" not in out["person_terms"], f"Flag {flag!r} should not count"

    def test_person_also_appears_in_vocab_terms(self):
        """Person terms are STILL members of vocab_terms (not just person_terms)."""
        from src.worker_process import _build_scorer_inputs

        vocab = [{"Term": "John", "Quality Score": 6, "Is Person": "Yes"}]
        out = _build_scorer_inputs(vocab)
        assert "john" in out["vocab_terms"]
        assert "john" in out["person_terms"]


# ---------------------------------------------------------------------------
# Loader failure resilience
# ---------------------------------------------------------------------------


class TestLoaderFailureResilience:
    """Loader exceptions become empty defaults instead of propagating."""

    def test_feedback_manager_exception_yields_empty_rejected(self):
        """FeedbackManager raising must NOT crash _build_scorer_inputs."""
        from src.worker_process import _build_scorer_inputs

        with patch(
            "src.core.vocabulary.feedback_manager.FeedbackManager",
            side_effect=RuntimeError("csv missing"),
        ):
            out = _build_scorer_inputs([{"Term": "x", "Quality Score": 1}])
        assert out["rejected_terms"] == set()
        # vocab_terms still computed normally.
        assert out["vocab_terms"] == {"x": 1}

    def test_frequency_loader_exception_yields_empty_map(self):
        """A failing load_raw_frequency_data must not crash the call."""
        from src.worker_process import _build_scorer_inputs

        with patch(
            "src.core.vocabulary.frequency_data.load_raw_frequency_data",
            side_effect=OSError("frequency file missing"),
        ):
            out = _build_scorer_inputs([{"Term": "y", "Quality Score": 3}])
        assert out["frequency_rank_map"] == {}
        assert out["vocab_terms"] == {"y": 3}

    def test_frequency_loader_returns_none_yields_empty_map(self):
        """If the loader returns None (no data), the map stays empty without erroring."""
        from src.worker_process import _build_scorer_inputs

        with patch(
            "src.core.vocabulary.frequency_data.load_raw_frequency_data",
            return_value=None,
        ):
            out = _build_scorer_inputs([])
        assert out["frequency_rank_map"] == {}


# ---------------------------------------------------------------------------
# Frequency rank map ordering
# ---------------------------------------------------------------------------


class TestFrequencyRankOrdering:
    """frequency_rank_map ranks words from most-frequent (rank 0) downward."""

    def test_highest_frequency_word_gets_rank_zero(self):
        """The word with the largest frequency gets rank 0 (most common)."""
        from src.worker_process import _build_scorer_inputs

        fake_freq = {"the": 10_000, "negligence": 30, "obscure": 1}
        with patch(
            "src.core.vocabulary.frequency_data.load_raw_frequency_data",
            return_value=fake_freq,
        ):
            out = _build_scorer_inputs([])
        ranks = out["frequency_rank_map"]
        assert ranks["the"] == 0
        assert ranks["negligence"] == 1
        assert ranks["obscure"] == 2
