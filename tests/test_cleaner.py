"""
Unit tests for the DocumentCleaner module.
"""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cleaner import DocumentCleaner


class TestDocumentCleaner:
    """Tests for DocumentCleaner class."""

    @pytest.fixture
    def cleaner(self):
        """Create a DocumentCleaner instance."""
        return DocumentCleaner(jurisdiction="ny")

    def test_initialization(self, cleaner):
        """Test that cleaner initializes with keywords and dictionary."""
        assert len(cleaner.legal_keywords) > 0
        assert len(cleaner.english_words) > 0

    def test_dictionary_confidence_good_text(self, cleaner):
        """Test confidence calculation with good English text."""
        text = "The plaintiff filed a complaint against the defendant."
        confidence = cleaner._calculate_dictionary_confidence(text)
        assert confidence > 80  # Should be high for good English

    def test_dictionary_confidence_gibberish(self, cleaner):
        """Test confidence calculation with gibberish."""
        text = "asdfg qwerty zxcvb hjkl"
        confidence = cleaner._calculate_dictionary_confidence(text)
        assert confidence < 20  # Should be low for gibberish

    def test_clean_text_removes_short_lines(self, cleaner):
        """Test that short lines are removed."""
        text = "This is a good line with enough content.\nShort\nAnother good line here."
        cleaned = cleaner._clean_text(text)
        assert "Short" not in cleaned
        assert "good line" in cleaned

    def test_clean_text_preserves_legal_headers(self, cleaner):
        """Test that legal headers in all caps are preserved."""
        text = "SUPREME COURT\nThis is the body text of the document."
        cleaned = cleaner._clean_text(text)
        assert "SUPREME COURT" in cleaned

    def test_clean_text_dehyphenation(self, cleaner):
        """Test that hyphenated words across lines are rejoined."""
        text = "The defen-\ndant appeared in court."
        cleaned = cleaner._clean_text(text)
        assert "defendant" in cleaned
        assert "defen-" not in cleaned

    def test_clean_text_whitespace_normalization(self, cleaner):
        """Test that excess whitespace is removed."""
        text = "Line 1\n\n\n\n\nLine 2"
        cleaned = cleaner._clean_text(text)
        assert "\n\n\n" not in cleaned  # Should have max 2 newlines

    def test_process_nonexistent_file(self, cleaner):
        """Test processing a file that doesn't exist."""
        result = cleaner.process_document("nonexistent_file.pdf")
        assert result['status'] == 'error'
        assert 'not found' in result['error_message'].lower()

    def test_unsupported_file_type(self, cleaner, tmp_path):
        """Test processing an unsupported file type."""
        # Create a dummy file with unsupported extension
        test_file = tmp_path / "test.docx"
        test_file.write_text("test content")

        result = cleaner.process_document(str(test_file))
        assert result['status'] == 'error'
        assert 'unsupported' in result['error_message'].lower()


class TestTextFileProcesing:
    """Tests for TXT file processing."""

    @pytest.fixture
    def cleaner(self):
        return DocumentCleaner()

    def test_process_txt_file(self, cleaner, tmp_path):
        """Test processing a simple text file."""
        # Create a test TXT file
        test_file = tmp_path / "test.txt"
        test_content = "This is a test complaint.\nThe plaintiff alleges negligence.\nThe defendant denies all allegations."
        test_file.write_text(test_content)

        result = cleaner.process_document(str(test_file))

        assert result['status'] == 'success'
        assert result['method'] == 'direct_read'
        assert result['confidence'] == 100
        assert len(result['cleaned_text']) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
