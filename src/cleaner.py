"""
Document Pre-processing Module (The "Cleaner")
Extracts and cleans text from legal documents (PDF, TXT, RTF).

This is the core Phase 1 module that can run standalone via command line.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import argparse

# PDF processing
import pdfplumber

# OCR
from pdf2image import convert_from_path
import pytesseract

# NLP
import nltk
from nltk.corpus import words

# Local imports
from src.config import (
    DEBUG_MODE,
    MAX_FILE_SIZE_MB,
    LARGE_FILE_WARNING_MB,
    MIN_LINE_LENGTH,
    MIN_DICTIONARY_CONFIDENCE,
    OCR_DPI,
    OCR_CONFIDENCE_THRESHOLD,
    LEGAL_KEYWORDS_NY,
    DEBUG_DEFAULT_FILE
)
from src.utils import debug, info, warning, error, Timer


class DocumentCleaner:
    """
    Processes legal documents to extract clean, usable text.

    Handles PDF (digital and scanned), TXT, and RTF files.
    Returns cleaned text with confidence scores and processing metadata.
    """

    def __init__(self, jurisdiction: str = "ny"):
        """
        Initialize the DocumentCleaner.

        Args:
            jurisdiction: Legal jurisdiction for keyword loading (ny, ca, federal)
        """
        self.jurisdiction = jurisdiction
        self.legal_keywords: Set[str] = set()
        self.english_words: Set[str] = set()

        with Timer("DocumentCleaner initialization"):
            self._load_keywords()
            self._load_dictionary()

    def _load_keywords(self):
        """Load legal keywords for the jurisdiction."""
        debug(f"Loading legal keywords for jurisdiction: {self.jurisdiction}")

        # For now, use a default set since keyword files don't exist yet
        # TODO: Download from Dropbox and cache locally
        self.legal_keywords = {
            "COURT", "PLAINTIFF", "DEFENDANT", "APPEARANCES", "SUPREME",
            "MOTION", "AFFIDAVIT", "EXHIBIT", "DEPOSITION", "TESTIMONY",
            "COMPLAINT", "ANSWER", "SUMMONS", "NOTICE", "ORDER",
            "JUDGE", "ATTORNEY", "COUNSEL", "PARTY", "ACTION"
        }

        debug(f"Loaded {len(self.legal_keywords)} legal keywords")

    def _load_dictionary(self):
        """Load NLTK English words corpus."""
        debug("Loading NLTK English words corpus")

        try:
            # Try to load the words corpus
            self.english_words = set(word.lower() for word in words.words())
            debug(f"Loaded {len(self.english_words)} English words")
        except LookupError:
            # Download if not available
            warning("NLTK words corpus not found. Downloading...")
            nltk.download('words', quiet=not DEBUG_MODE)
            self.english_words = set(word.lower() for word in words.words())
            debug(f"Downloaded and loaded {len(self.english_words)} English words")

    def process_document(self, file_path: str) -> Dict:
        """
        Process a single document.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary with keys:
                - filename: Name of the file
                - file_path: Full path to file
                - status: 'success', 'warning', or 'error'
                - method: 'direct_read', 'digital_text', 'ocr'
                - confidence: OCR confidence score (0-100)
                - cleaned_text: Cleaned text content
                - pages: Number of pages (for PDFs)
                - size_mb: File size in MB
                - error_message: Error description (if status is 'error')
        """
        file_path = Path(file_path)
        filename = file_path.name

        info(f"Processing document: {filename}")

        result = {
            'filename': filename,
            'file_path': str(file_path),
            'status': 'success',
            'method': None,
            'confidence': 0,
            'cleaned_text': '',
            'pages': None,
            'size_mb': 0,
            'error_message': None
        }

        try:
            with Timer(f"Processing {filename}"):
                # Check file exists
                if not file_path.exists():
                    result['status'] = 'error'
                    result['error_message'] = f"File not found: {file_path}"
                    error(result['error_message'])
                    return result

                # Get file size
                result['size_mb'] = file_path.stat().st_size / (1024 * 1024)

                # Check file size limits
                if result['size_mb'] > MAX_FILE_SIZE_MB:
                    result['status'] = 'error'
                    result['error_message'] = f"File exceeds maximum size ({MAX_FILE_SIZE_MB}MB). File size: {result['size_mb']:.1f}MB"
                    error(result['error_message'])
                    return result

                if result['size_mb'] > LARGE_FILE_WARNING_MB:
                    warning(f"Large file detected ({result['size_mb']:.1f}MB). Processing may take longer.")

                # Determine file type and process
                file_extension = file_path.suffix.lower()

                if file_extension in ['.txt', '.rtf']:
                    result.update(self._process_text_file(file_path))
                elif file_extension == '.pdf':
                    result.update(self._process_pdf(file_path))
                else:
                    result['status'] = 'error'
                    result['error_message'] = f"Unsupported file type: {file_extension}"
                    error(result['error_message'])
                    return result

                # Apply text cleaning
                if result['status'] != 'error' and result['cleaned_text']:
                    with Timer("Text cleaning"):
                        result['cleaned_text'] = self._clean_text(result['cleaned_text'])

                    # Check if cleaning resulted in empty text
                    if len(result['cleaned_text'].strip()) == 0:
                        result['status'] = 'error'
                        result['error_message'] = "Unable to extract readable text. File may be corrupted or contain only images."
                        error(result['error_message'])

                # Set status based on confidence
                if result['status'] == 'success':
                    if result['confidence'] < OCR_CONFIDENCE_THRESHOLD:
                        result['status'] = 'warning'

        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = f"Unexpected error: {str(e)}"
            error(f"Error processing {filename}: {str(e)}", exc_info=True)

        return result

    def _process_text_file(self, file_path: Path) -> Dict:
        """Process TXT or RTF file."""
        debug(f"Processing as text file: {file_path.name}")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()

            return {
                'method': 'direct_read',
                'confidence': 100,
                'cleaned_text': text,
                'status': 'success'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error_message': f"Failed to read text file: {str(e)}"
            }

    def _process_pdf(self, file_path: Path) -> Dict:
        """Process PDF file (digital or scanned)."""
        debug(f"Processing as PDF: {file_path.name}")

        # Step 1: Try digital text extraction
        with Timer("PDF text extraction (pdfplumber)"):
            text, page_count = self._extract_pdf_text(file_path)

        if text is None:
            # Error occurred
            return {
                'status': 'error',
                'error_message': 'Failed to open PDF. File may be password-protected or corrupted.',
                'pages': page_count
            }

        # Step 2: Heuristic check (digital vs scanned)
        with Timer("Dictionary confidence check"):
            dictionary_confidence = self._calculate_dictionary_confidence(text)

        debug(f"Dictionary confidence: {dictionary_confidence:.1f}%")

        # Decision: Use digital text or perform OCR?
        if dictionary_confidence > MIN_DICTIONARY_CONFIDENCE and len(text) > 1000:
            # Good digital text
            debug("Using digital text extraction")
            return {
                'method': 'digital_text',
                'confidence': 100,
                'cleaned_text': text,
                'pages': page_count,
                'status': 'success'
            }
        else:
            # Needs OCR
            debug("Digital text quality insufficient. Performing OCR...")
            return self._perform_ocr(file_path, page_count)

    def _extract_pdf_text(self, file_path: Path) -> Tuple[Optional[str], int]:
        """
        Extract text from PDF using pdfplumber.

        Returns:
            (text, page_count) or (None, 0) on error
        """
        try:
            text = ""
            page_count = 0

            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                debug(f"PDF has {page_count} pages")

                for i, page in enumerate(pdf.pages, 1):
                    if DEBUG_MODE and i % 10 == 0:
                        debug(f"Extracting page {i}/{page_count}")

                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            return text, page_count

        except Exception as e:
            error_msg = str(e).lower()
            if "password" in error_msg or "encrypted" in error_msg:
                error("PDF is password-protected")
            else:
                error(f"Failed to extract PDF text: {str(e)}", exc_info=True)

            return None, 0

    def _calculate_dictionary_confidence(self, text: str) -> float:
        """
        Calculate what percentage of words are valid English words.

        Args:
            text: Text to analyze

        Returns:
            Confidence percentage (0-100)
        """
        if not text:
            return 0.0

        # Tokenize (simple split on whitespace and punctuation)
        tokens = re.findall(r'\b[a-zA-Z]+\b', text.lower())

        if len(tokens) == 0:
            return 0.0

        # Count valid English words
        valid_words = sum(1 for token in tokens if token in self.english_words)

        confidence = (valid_words / len(tokens)) * 100
        return confidence

    def _perform_ocr(self, file_path: Path, page_count: int) -> Dict:
        """
        Perform OCR on PDF using Tesseract.

        Args:
            file_path: Path to PDF
            page_count: Number of pages (from pdfplumber)

        Returns:
            Result dictionary
        """
        debug(f"Starting OCR on {file_path.name}")

        try:
            # Convert PDF to images
            with Timer("PDF to images conversion"):
                images = convert_from_path(str(file_path), dpi=OCR_DPI)

            # OCR each page
            ocr_text = ""
            for i, image in enumerate(images, 1):
                if DEBUG_MODE:
                    debug(f"OCR processing page {i}/{len(images)}")

                with Timer(f"OCR page {i}", auto_log=DEBUG_MODE):
                    page_text = pytesseract.image_to_string(image)
                    ocr_text += page_text + "\n"

            # Calculate confidence
            confidence = self._calculate_dictionary_confidence(ocr_text)
            debug(f"OCR confidence: {confidence:.1f}%")

            return {
                'method': 'ocr',
                'confidence': int(confidence),
                'cleaned_text': ocr_text,
                'pages': page_count or len(images),
                'status': 'success'
            }

        except Exception as e:
            return {
                'status': 'error',
                'error_message': f"OCR processing failed: {str(e)}",
                'pages': page_count
            }

    def _clean_text(self, raw_text: str) -> str:
        """
        Apply cleaning rules to raw text.

        Rules:
        1. Line filtering (remove short lines, require lowercase or legal headers)
        2. De-hyphenation (rejoin words split across lines)
        3. Whitespace normalization

        Args:
            raw_text: Raw extracted text

        Returns:
            Cleaned text
        """
        debug("Applying text cleaning rules")

        # Rule 1: Line Filtering
        cleaned_lines = []
        for line in raw_text.split('\n'):
            # Minimum length check
            if len(line) <= MIN_LINE_LENGTH:
                continue

            # Check if line has lowercase letters
            has_lowercase = any(c.islower() for c in line)

            # Check if it's a legal header (all caps + contains legal keyword)
            is_legal_header = (
                line.isupper() and
                len(line) < 50 and
                any(keyword in line for keyword in self.legal_keywords)
            )

            # Count character types
            alpha_count = sum(c.isalpha() for c in line)
            other_count = sum(not c.isalpha() and not c.isspace() for c in line)

            # Keep line if it passes all tests
            if (has_lowercase or is_legal_header) and alpha_count > other_count:
                cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # Rule 2: De-hyphenation
        # Remove hyphen + newline when it's clearly a word break
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

        # Rule 3: Whitespace Normalization
        # Remove excess blank lines (max 1 between paragraphs)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = text.strip()

        debug(f"Cleaning reduced text from {len(raw_text)} to {len(text)} characters")

        return text


def main():
    """Command-line interface for the cleaner."""
    parser = argparse.ArgumentParser(
        description="LocalScribe Document Cleaner - Extract and clean text from legal documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single file
  python cleaner.py --input complaint.pdf

  # Process multiple files
  python cleaner.py --input file1.pdf file2.pdf file3.pdf

  # Specify output directory and jurisdiction
  python cleaner.py --input *.pdf --output-dir ./cleaned --jurisdiction ny

  # Debug mode (verbose logging)
  DEBUG=true python cleaner.py --input test.pdf
        """
    )

    parser.add_argument(
        '--input',
        nargs='+',
        required=True,
        help='Input file(s) to process (PDF, TXT, RTF)'
    )

    parser.add_argument(
        '--output-dir',
        default='./cleaned',
        help='Output directory for cleaned text files (default: ./cleaned)'
    )

    parser.add_argument(
        '--jurisdiction',
        default='ny',
        choices=['ny', 'ca', 'federal'],
        help='Legal jurisdiction for keyword filtering (default: ny)'
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize cleaner
    info(f"Initializing LocalScribe Document Cleaner (jurisdiction: {args.jurisdiction})")
    cleaner = DocumentCleaner(jurisdiction=args.jurisdiction)

    # Process files
    results = []
    for file_path in args.input:
        result = cleaner.process_document(file_path)
        results.append(result)

        # Save cleaned text if successful
        if result['status'] in ['success', 'warning'] and result['cleaned_text']:
            # Create output filename
            output_filename = f"{Path(result['filename']).stem}_cleaned.txt"
            output_path = output_dir / output_filename

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result['cleaned_text'])

            info(f"Saved cleaned text to: {output_path}")

    # Print summary report
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)

    for result in results:
        status_symbol = {
            'success': '[OK]',
            'warning': '[WARN]',
            'error': '[ERROR]'
        }.get(result['status'], '[?]')

        print(f"\n{status_symbol} {result['filename']}")
        print(f"  Status: {result['status'].upper()}")
        print(f"  Method: {result['method'] or 'N/A'}")
        print(f"  Confidence: {result['confidence']}%")
        print(f"  Size: {result['size_mb']:.2f} MB")

        if result.get('pages'):
            print(f"  Pages: {result['pages']}")

        if result['error_message']:
            print(f"  Error: {result['error_message']}")

    # Summary statistics
    total = len(results)
    success = sum(1 for r in results if r['status'] == 'success')
    warnings = sum(1 for r in results if r['status'] == 'warning')
    errors = sum(1 for r in results if r['status'] == 'error')

    print("\n" + "=" * 60)
    print(f"Total: {total} | Success: {success} | Warnings: {warnings} | Errors: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    # Use debug default file if in debug mode and no args provided
    if DEBUG_MODE and len(os.sys.argv) == 1 and DEBUG_DEFAULT_FILE.exists():
        info("DEBUG MODE: Using default test file")
        os.sys.argv.extend(['--input', str(DEBUG_DEFAULT_FILE)])

    main()
