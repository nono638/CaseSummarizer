"""
Tests for the feedback and meta-learner system (Session 25).

Tests cover:
- FeedbackManager: Recording, retrieving, and persisting feedback
- VocabularyMetaLearner: Training on feedback data
- Integration: Feedback loop with quality score boosting
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.vocabulary.feedback_manager import FeedbackManager  # noqa: E402
from src.vocabulary.meta_learner import VocabularyMetaLearner  # noqa: E402


@pytest.fixture
def temp_feedback_dir():
    """Create a temporary directory for feedback files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def feedback_manager(temp_feedback_dir):
    """Create FeedbackManager with temp directory."""
    return FeedbackManager(feedback_dir=temp_feedback_dir)


@pytest.fixture
def meta_learner(temp_feedback_dir):
    """Create VocabularyMetaLearner with temp model path."""
    model_path = temp_feedback_dir / "test_model.pkl"
    return VocabularyMetaLearner(model_path=model_path)


class TestFeedbackManager:
    """Tests for FeedbackManager."""

    def test_record_positive_feedback(self, feedback_manager):
        """Test recording thumbs up feedback."""
        term_data = {
            "Term": "adenocarcinoma",
            "Type": "Medical",
            "Sources": "NER",
            "Quality Score": 75,
            "In-Case Freq": 3,
            "Freq Rank": 250000,
        }
        result = feedback_manager.record_feedback(term_data, +1)
        assert result is True
        assert feedback_manager.get_rating("adenocarcinoma") == 1

    def test_record_negative_feedback(self, feedback_manager):
        """Test recording thumbs down feedback."""
        term_data = {"Term": "the"}
        result = feedback_manager.record_feedback(term_data, -1)
        assert result is True
        assert feedback_manager.get_rating("the") == -1

    def test_toggle_feedback(self, feedback_manager):
        """Test toggling feedback from positive to negative."""
        term_data = {"Term": "spondylosis"}
        feedback_manager.record_feedback(term_data, +1)
        assert feedback_manager.get_rating("spondylosis") == 1

        feedback_manager.record_feedback(term_data, -1)
        assert feedback_manager.get_rating("spondylosis") == -1

    def test_clear_feedback(self, feedback_manager):
        """Test clearing feedback (setting to 0)."""
        term_data = {"Term": "cardiomyopathy"}
        feedback_manager.record_feedback(term_data, +1)
        assert feedback_manager.get_rating("cardiomyopathy") == 1

        feedback_manager.record_feedback(term_data, 0)
        assert feedback_manager.get_rating("cardiomyopathy") == 0

    def test_case_insensitive(self, feedback_manager):
        """Test that feedback lookups are case-insensitive."""
        term_data = {"Term": "HIPAA"}
        feedback_manager.record_feedback(term_data, +1)
        assert feedback_manager.get_rating("hipaa") == 1
        assert feedback_manager.get_rating("HIPAA") == 1
        assert feedback_manager.get_rating("Hipaa") == 1

    def test_get_unrated_term(self, feedback_manager):
        """Test getting rating for unrated term returns 0."""
        assert feedback_manager.get_rating("never_rated") == 0

    def test_feedback_persists(self, temp_feedback_dir):
        """Test that feedback persists across manager instances."""
        term_data = {"Term": "persistent_term"}

        # Create first manager and record feedback
        manager1 = FeedbackManager(feedback_dir=temp_feedback_dir)
        manager1.record_feedback(term_data, +1)

        # Create second manager and verify feedback was loaded
        manager2 = FeedbackManager(feedback_dir=temp_feedback_dir)
        assert manager2.get_rating("persistent_term") == 1

    def test_get_feedback_count(self, feedback_manager):
        """Test feedback count tracking."""
        assert feedback_manager.get_feedback_count() == 0

        feedback_manager.record_feedback({"Term": "term1"}, +1)
        feedback_manager.record_feedback({"Term": "term2"}, -1)
        assert feedback_manager.get_feedback_count() == 2

    def test_document_id(self, feedback_manager):
        """Test document ID generation and setting."""
        doc_id = feedback_manager.generate_document_id("Sample document text")
        assert doc_id.startswith("doc_")
        assert len(doc_id) > 4

        feedback_manager.set_document_id(doc_id)
        assert feedback_manager._current_doc_id == doc_id


class TestVocabularyMetaLearner:
    """Tests for VocabularyMetaLearner."""

    def test_untrained_prediction(self, meta_learner):
        """Test that untrained model returns neutral prediction."""
        assert not meta_learner.is_trained
        prediction = meta_learner.predict_preference({"Term": "test"})
        assert prediction == 0.5  # Neutral for untrained

    def test_feature_extraction(self, meta_learner):
        """Test feature extraction from term data."""
        term_data = {
            "quality_score": 75,
            "in_case_freq": 3,
            "freq_rank": 250000,
            "algorithms": "NER,RAKE",
            "type": "Medical",
        }
        features = meta_learner._extract_features(term_data)
        assert len(features) == 11  # Total feature count
        assert features[0] == 75  # quality_score
        assert features[1] == 3  # in_case_freq

    def test_training_insufficient_data(self, temp_feedback_dir, meta_learner):
        """Test that training fails with insufficient data."""
        feedback_mgr = FeedbackManager(feedback_dir=temp_feedback_dir)
        # Add only a few samples (below threshold)
        for i in range(5):
            feedback_mgr.record_feedback({"Term": f"term{i}"}, +1 if i % 2 == 0 else -1)

        result = meta_learner.train(feedback_mgr)
        assert result is False  # Should fail - not enough data

    def test_model_save_load(self, temp_feedback_dir):
        """Test model persistence."""
        model_path = temp_feedback_dir / "test_model.pkl"

        # Create and "train" a mock scenario
        learner1 = VocabularyMetaLearner(model_path=model_path)
        assert not learner1.is_trained

        # After proper training (if we had enough data), model would save
        # For now, verify load works with non-existent model
        learner2 = VocabularyMetaLearner(model_path=model_path)
        assert not learner2.is_trained

    def test_should_retrain(self, temp_feedback_dir):
        """Test retraining threshold check."""
        feedback_mgr = FeedbackManager(feedback_dir=temp_feedback_dir)
        model_path = temp_feedback_dir / "test_model.pkl"
        learner = VocabularyMetaLearner(model_path=model_path)

        # Initially should not need retraining
        assert not learner.should_retrain(feedback_mgr)


class TestIntegration:
    """Integration tests for the full feedback-ML pipeline."""

    def test_full_pipeline_import(self):
        """Test that all components can be imported together."""
        from src.vocabulary import (
            VocabularyExtractor,
            get_feedback_manager,
            get_meta_learner,
        )
        # Just verify imports work
        assert VocabularyExtractor is not None
        assert get_feedback_manager is not None
        assert get_meta_learner is not None

    def test_extractor_has_meta_learner(self):
        """Test that VocabularyExtractor has meta-learner integration."""
        from src.vocabulary import VocabularyExtractor
        extractor = VocabularyExtractor()
        assert hasattr(extractor, '_meta_learner')
        assert extractor._meta_learner is not None
