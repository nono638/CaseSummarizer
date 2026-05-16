"""
Behavioral tests for ExtractionResult and the file_readers._wrap_reader helper.

Coverage focus:
- ExtractionResult.success / .error factories
- dict-style access (__getitem__ / .get) backward compatibility
- _wrap_reader: success path, short-circuit ExtractionResult return,
  exception conversion to error result, confidence delegation.

All tests use real ExtractionResult instances (no mocks of the type itself).
File I/O is exercised through tmp_path.
"""

from unittest.mock import MagicMock

import pytest

from src.core.extraction.extraction_result import ExtractionResult
from src.core.extraction.file_readers import FileReaders

# ---------------------------------------------------------------------------
# ExtractionResult.success
# ---------------------------------------------------------------------------


class TestExtractionResultSuccess:
    """ExtractionResult.success constructs a populated success result."""

    def test_success_sets_text_method_status(self):
        """success() must populate text/method/status correctly."""
        r = ExtractionResult.success("hello", "direct_read", 92)
        assert r.text == "hello"
        assert r.method == "direct_read"
        assert r.status == "success"

    def test_success_casts_float_confidence_to_int(self):
        """Confidence is normalized to int regardless of float/int input."""
        r = ExtractionResult.success("x", "m", 87.6)
        assert isinstance(r.confidence, int)
        assert r.confidence == 87  # int() truncates, doesn't round

    def test_success_page_count_kwarg_threaded_through(self):
        """page_count keyword is stored on the result."""
        r = ExtractionResult.success("x", "m", 50, page_count=4)
        assert r.page_count == 4

    def test_success_default_page_count_is_none(self):
        """Omitting page_count leaves it as None (not zero)."""
        r = ExtractionResult.success("x", "m", 50)
        assert r.page_count is None

    def test_success_default_pages_is_none(self):
        """Omitting pages leaves it as None."""
        r = ExtractionResult.success("x", "m", 50)
        assert r.pages is None

    def test_success_pages_dict_threaded_through(self):
        """Per-page dict is preserved verbatim."""
        pages = {1: "page one", 2: "page two"}
        r = ExtractionResult.success("combined", "ocr", 70, pages=pages)
        assert r.pages == pages

    def test_success_error_message_is_none(self):
        """A success result must not carry an error_message."""
        r = ExtractionResult.success("x", "m", 50)
        assert r.error_message is None


# ---------------------------------------------------------------------------
# ExtractionResult.error
# ---------------------------------------------------------------------------


class TestExtractionResultError:
    """ExtractionResult.error constructs a populated failure result."""

    def test_error_default_status_is_error(self):
        """Default status string is the literal 'error'."""
        r = ExtractionResult.error("boom")
        assert r.status == "error"

    def test_error_stores_message(self):
        """The provided message is stored in error_message."""
        r = ExtractionResult.error("file missing")
        assert r.error_message == "file missing"

    def test_error_default_text_is_none(self):
        """Error results have no extracted text by default."""
        r = ExtractionResult.error("boom")
        assert r.text is None

    def test_error_default_confidence_zero(self):
        """Error results carry zero confidence by default."""
        r = ExtractionResult.error("boom")
        assert r.confidence == 0

    def test_error_accepts_custom_status(self):
        """A custom status (e.g. 'ocr_skipped') can be supplied."""
        r = ExtractionResult.error("skipped", status="ocr_skipped")
        assert r.status == "ocr_skipped"

    def test_error_accepts_page_count(self):
        """page_count can be set on an error (e.g. image OCR fail = 1 page)."""
        r = ExtractionResult.error("bad image", page_count=1)
        assert r.page_count == 1


# ---------------------------------------------------------------------------
# ExtractionResult dict-style access
# ---------------------------------------------------------------------------


class TestExtractionResultDictAccess:
    """ExtractionResult supports dict-style indexing for back-compat."""

    def test_indexing_returns_attribute(self):
        """result['text'] returns the text attribute."""
        r = ExtractionResult.success("hello", "m", 50)
        assert r["text"] == "hello"
        assert r["method"] == "m"
        assert r["status"] == "success"

    def test_get_returns_default_for_missing(self):
        """get() returns the default for unknown keys."""
        r = ExtractionResult.success("x", "m", 50)
        assert r.get("nonexistent_key", "fallback") == "fallback"

    def test_get_returns_value_for_known_key(self):
        """get() returns the actual value for known attributes."""
        r = ExtractionResult.success("x", "m", 50, page_count=3)
        assert r.get("page_count") == 3

    def test_indexing_unknown_key_raises(self):
        """Indexing an unknown key raises AttributeError (consistent with getattr)."""
        r = ExtractionResult.success("x", "m", 50)
        with pytest.raises(AttributeError):
            _ = r["does_not_exist"]


# ---------------------------------------------------------------------------
# FileReaders._wrap_reader
# ---------------------------------------------------------------------------


def _make_readers(confidence: float = 80.0) -> FileReaders:
    """Helper: build a FileReaders with a stub dictionary validator."""
    dictionary = MagicMock()
    dictionary.calculate_confidence.return_value = confidence
    return FileReaders(dictionary=dictionary)


class TestWrapReaderSuccess:
    """_wrap_reader converts a (text, page_count) tuple into a success result."""

    def test_success_returns_success_status(self, tmp_path):
        """A returning callback produces ExtractionResult.success."""
        readers = _make_readers(confidence=88.0)
        result = readers._wrap_reader(
            tmp_path / "doc.txt",
            "text",
            "direct_read",
            "text file",
            lambda: ("hi", 1),
        )
        assert result.status == "success"
        assert result.text == "hi"
        assert result.method == "direct_read"

    def test_success_threads_page_count_through(self, tmp_path):
        """The page_count from the callback ends up on the result."""
        readers = _make_readers()
        result = readers._wrap_reader(
            tmp_path / "doc.txt", "text", "m", "text file", lambda: ("body", 5)
        )
        assert result.page_count == 5

    def test_success_uses_dictionary_confidence(self, tmp_path):
        """Confidence is sourced from dictionary.calculate_confidence(text)."""
        dictionary = MagicMock()
        dictionary.calculate_confidence.return_value = 73.2
        readers = FileReaders(dictionary=dictionary)
        readers._wrap_reader(tmp_path / "x.txt", "text", "m", "text file", lambda: ("payload", 1))
        dictionary.calculate_confidence.assert_called_once_with("payload")


class TestWrapReaderShortCircuit:
    """_wrap_reader returns a pre-built ExtractionResult unchanged."""

    def test_pre_built_error_passes_through(self, tmp_path):
        """If the callback returns an ExtractionResult, _wrap_reader returns it as-is."""
        readers = _make_readers()
        prebuilt = ExtractionResult.error("no readable text", page_count=0)
        result = readers._wrap_reader(
            tmp_path / "x.docx",
            "Word document",
            "docx_extraction",
            "Word document",
            lambda: prebuilt,
        )
        assert result is prebuilt
        assert result.status == "error"
        assert result.error_message == "no readable text"

    def test_pre_built_does_not_call_dictionary(self, tmp_path):
        """Short-circuit path must not invoke the dictionary validator."""
        dictionary = MagicMock()
        readers = FileReaders(dictionary=dictionary)
        readers._wrap_reader(
            tmp_path / "x.docx",
            "Word document",
            "m",
            "Word document",
            lambda: ExtractionResult.error("empty", page_count=0),
        )
        dictionary.calculate_confidence.assert_not_called()


class TestWrapReaderException:
    """_wrap_reader converts callback exceptions to error results."""

    def test_exception_becomes_error_result(self, tmp_path):
        """An exception in the callback returns an ExtractionResult.error."""
        readers = _make_readers()

        def _read():
            """Always blow up, exercising the except branch."""
            raise ValueError("disk gone")

        result = readers._wrap_reader(tmp_path / "x.txt", "text", "direct_read", "text file", _read)
        assert result.status == "error"
        assert "disk gone" in result.error_message

    def test_error_subject_appears_in_message(self, tmp_path):
        """The error_subject parameter prefixes the failure message."""
        readers = _make_readers()

        def _read():
            """Raise to drive the error path."""
            raise OSError("permission denied")

        result = readers._wrap_reader(
            tmp_path / "x.rtf", "RTF", "rtf_extraction", "RTF file", _read
        )
        assert "Failed to read RTF file" in result.error_message
        assert "permission denied" in result.error_message

    def test_exception_result_has_page_count_zero(self, tmp_path):
        """Exception path sets page_count to 0 explicitly."""
        readers = _make_readers()

        def _read():
            """Raise so we exercise the exception branch."""
            raise RuntimeError("nope")

        result = readers._wrap_reader(tmp_path / "x.txt", "text", "m", "text file", _read)
        assert result.page_count == 0


# ---------------------------------------------------------------------------
# FileReaders.read_image_file — covers OCR-absent and OCR-success paths
# ---------------------------------------------------------------------------


class TestReadImageFile:
    """read_image_file handles missing OCR processor and delegates otherwise."""

    def test_missing_ocr_processor_returns_error(self, tmp_path):
        """No OCR processor configured -> error result with page_count=1."""
        dictionary = MagicMock()
        readers = FileReaders(dictionary=dictionary, ocr_processor=None)
        # Image file existence is irrelevant when OCR is disabled.
        result = readers.read_image_file(tmp_path / "scan.png")
        assert result.status == "error"
        assert "OCR processor not available" in result.error_message
        assert result.page_count == 1

    def test_nonexistent_image_returns_error(self, tmp_path):
        """Missing image file produces an error result, not an exception."""
        dictionary = MagicMock()
        ocr_processor = MagicMock()
        readers = FileReaders(dictionary=dictionary, ocr_processor=ocr_processor)
        result = readers.read_image_file(tmp_path / "does_not_exist.png")
        assert result.status == "error"
        # OCR processor must NOT be called when PIL can't open the file
        ocr_processor.process_image.assert_not_called()

    def test_successful_ocr_sets_page_count_one(self, tmp_path):
        """When OCR succeeds, page_count is forced to 1 (single image)."""
        from PIL import Image

        # Create a real 1x1 PNG so PIL.Image.open succeeds.
        img_path = tmp_path / "tiny.png"
        Image.new("RGB", (1, 1), color="white").save(img_path)

        dictionary = MagicMock()
        ocr_processor = MagicMock()
        ocr_processor.process_image.return_value = ExtractionResult.success(
            "scanned", "image_ocr", 65
        )
        readers = FileReaders(dictionary=dictionary, ocr_processor=ocr_processor)

        result = readers.read_image_file(img_path)
        assert result.status == "success"
        assert result.text == "scanned"
        assert result.page_count == 1  # forced by read_image_file


# ---------------------------------------------------------------------------
# FileReaders.read_docx_file — empty doc short-circuit
# ---------------------------------------------------------------------------


class TestReadDocxEmptyShortCircuit:
    """An empty .docx returns the canonical 'no readable text' error."""

    def test_empty_docx_returns_specific_message(self, tmp_path):
        """Empty Word document must return the documented error message."""
        try:
            from docx import Document
        except ImportError:
            pytest.skip("python-docx not installed")

        empty_path = tmp_path / "empty.docx"
        Document().save(empty_path)

        dictionary = MagicMock()
        dictionary.calculate_confidence.return_value = 90.0
        readers = FileReaders(dictionary=dictionary)

        result = readers.read_docx_file(empty_path)
        assert result.status == "error"
        assert "no readable text" in result.error_message
        assert result.page_count == 0
        # Empty-doc short-circuit must NOT exercise the dictionary
        dictionary.calculate_confidence.assert_not_called()
