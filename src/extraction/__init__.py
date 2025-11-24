"""
Extraction Package

This package handles Step 1-2 of the document processing pipeline:
- Step 1: Extract raw text from files (PDF/TXT/RTF)
- Step 2: Apply basic normalization (de-hyphenation, page removal, etc.)
"""

from src.extraction.raw_text_extractor import RawTextExtractor

__all__ = ['RawTextExtractor']
