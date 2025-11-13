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


class TestPageNumberRemoval:
    """Tests for page number removal."""

    @pytest.fixture
    def cleaner(self):
        return DocumentCleaner()

    def test_removes_page_X(self, cleaner):
        """Test removal of 'Page X' format."""
        text = "Some content here.\nPage 1\nMore content here."
        cleaned = cleaner._clean_text(text)
        assert "Page 1" not in cleaned
        assert "content" in cleaned

    def test_removes_page_X_of_Y(self, cleaner):
        """Test removal of 'Page X of Y' format."""
        text = "Content line 1.\nPage 1 of 10\nContent line 2."
        cleaned = cleaner._clean_text(text)
        assert "Page 1 of 10" not in cleaned

    def test_removes_dashed_page_numbers(self, cleaner):
        """Test removal of '- X -' format."""
        text = "First paragraph.\n- 5 -\nSecond paragraph."
        cleaned = cleaner._clean_text(text)
        assert "- 5 -" not in cleaned

    def test_removes_standalone_numbers(self, cleaner):
        """Test removal of standalone page numbers."""
        text = "Paragraph text here.\n42\nMore text here with substance."
        cleaned = cleaner._clean_text(text)
        # Should remove standalone "42" but keep text
        assert "text here with substance" in cleaned


class TestCaseNumberExtraction:
    """Tests for case number extraction."""

    @pytest.fixture
    def cleaner(self):
        return DocumentCleaner()

    def test_extract_federal_case_number(self, cleaner):
        """Test extraction of federal case numbers."""
        text = "This matter is Case No. 1:23-cv-12345 before the court."
        case_nums = cleaner._extract_case_numbers(text)
        assert len(case_nums) > 0
        assert any("1:23-cv-12345" in num for num in case_nums)

    def test_extract_ny_index_number(self, cleaner):
        """Test extraction of NY Index numbers."""
        text = "Index No. 123456/2024 in the Supreme Court."
        case_nums = cleaner._extract_case_numbers(text)
        assert len(case_nums) > 0
        assert any("123456/2024" in num for num in case_nums)

    def test_extract_multiple_case_numbers(self, cleaner):
        """Test extraction of multiple case numbers."""
        text = "Case No. 1:23-cv-12345 and Index No. 987654/2024"
        case_nums = cleaner._extract_case_numbers(text)
        assert len(case_nums) >= 2

    def test_case_numbers_in_result(self, cleaner, tmp_path):
        """Test that case numbers appear in processing result."""
        test_file = tmp_path / "test.txt"
        test_content = "SUPREME COURT\nIndex No. 654321/2024\nThe plaintiff brings this action."
        test_file.write_text(test_content)

        result = cleaner.process_document(str(test_file))

        assert result['status'] == 'success'
        assert 'case_numbers' in result
        assert len(result['case_numbers']) > 0


class TestProgressCallback:
    """Tests for progress callback functionality."""

    @pytest.fixture
    def cleaner(self):
        return DocumentCleaner()

    def test_progress_callback_called(self, cleaner, tmp_path):
        """Test that progress callback is invoked."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content for progress tracking.")

        progress_calls = []

        def capture_progress(message, percent):
            progress_calls.append((message, percent))

        result = cleaner.process_document(str(test_file), progress_callback=capture_progress)

        assert result['status'] == 'success'
        assert len(progress_calls) > 0
        # Should have start, extraction, cleaning, and completion
        assert any(p[1] == 0 for p in progress_calls)  # Start
        assert any(p[1] == 100 for p in progress_calls)  # Complete

    def test_progress_callback_exception_handling(self, cleaner, tmp_path):
        """Test that callback exceptions don't crash processing."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("This is test content for progress tracking that has enough substance to pass cleaning filters.")

        def failing_callback(message, percent):
            raise Exception("Callback failed!")

        # Should not raise exception despite callback failure
        result = cleaner.process_document(str(test_file), progress_callback=failing_callback)
        assert result['status'] == 'success'


class TestImprovedErrorMessages:
    """Tests for improved error message handling."""

    @pytest.fixture
    def cleaner(self):
        return DocumentCleaner()

    def test_unsupported_file_type_message(self, cleaner, tmp_path):
        """Test error message for unsupported file types."""
        test_file = tmp_path / "test.docx"
        test_file.write_text("test")

        result = cleaner.process_document(str(test_file))

        assert result['status'] == 'error'
        assert 'Supported formats' in result['error_message']
        assert 'PDF' in result['error_message']
        assert 'TXT' in result['error_message']
        assert 'RTF' in result['error_message']


class TestRTFProcessing:
    """Tests for RTF file processing."""

    @pytest.fixture
    def cleaner(self):
        return DocumentCleaner()

    def test_process_rtf_file(self, cleaner, tmp_path):
        """Test processing an RTF file with formatting codes."""
        # Create a test RTF file with typical RTF formatting
        test_file = tmp_path / "test.rtf"
        rtf_content = r"""{\rtf1\ansi\deff0
{\fonttbl{\f0 Times New Roman;}}
\f0\fs24
{\b SUPREME COURT}\par
\par
This is a test document with plaintiff and defendant.\par
The court finds in favor of the plaintiff.\par
}"""
        test_file.write_text(rtf_content)

        result = cleaner.process_document(str(test_file))

        assert result['status'] == 'success'
        assert result['method'] == 'rtf_extraction'
        assert result['confidence'] == 100
        assert len(result['cleaned_text']) > 0
        # Verify formatting codes are removed
        assert '\\rtf' not in result['cleaned_text']
        assert '\\par' not in result['cleaned_text']
        assert 'SUPREME COURT' in result['cleaned_text']
        assert 'plaintiff' in result['cleaned_text']

    def test_process_rtf_with_special_chars(self, cleaner, tmp_path):
        """Test RTF file with special characters and escaped quotes."""
        test_file = tmp_path / "test_special.rtf"
        rtf_content = r"""{\rtf1\ansi
The plaintiff\rquote s claim was denied.\par
The defendant said \ldblquote no comment\rdblquote in response.\par
}"""
        test_file.write_text(rtf_content)

        result = cleaner.process_document(str(test_file))

        assert result['status'] == 'success'
        assert result['method'] == 'rtf_extraction'
        # Verify text is extracted (striprtf should handle special chars)
        assert len(result['cleaned_text']) > 0
        assert 'claim' in result['cleaned_text']

    def test_process_sample_rtf_file(self, cleaner):
        """Test processing the sample RTF motion file."""
        sample_file = Path(__file__).parent / "sample_docs" / "test_motion.rtf"

        # Skip if sample file doesn't exist
        if not sample_file.exists():
            pytest.skip("Sample RTF file not found")

        result = cleaner.process_document(str(sample_file))

        assert result['status'] == 'success'
        assert result['method'] == 'rtf_extraction'
        assert result['confidence'] == 100
        assert len(result['cleaned_text']) > 0
        # Verify key legal terms are preserved
        assert 'SUPREME COURT' in result['cleaned_text']
        assert 'plaintiff' in result['cleaned_text'].lower()
        assert 'defendant' in result['cleaned_text'].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
