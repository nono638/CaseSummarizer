"""
Vocabulary Extraction Package

This package provides functionality for extracting unusual and domain-specific
vocabulary from legal documents. It identifies proper nouns (people, organizations,
locations), medical terms, acronyms, and technical terminology.

Main Components:
- VocabularyExtractor: Core class for extracting and categorizing vocabulary

Usage:
    from src.vocabulary import VocabularyExtractor

    extractor = VocabularyExtractor(
        exclude_list_path="config/legal_exclude.txt",
        medical_terms_path="config/medical_terms.txt"
    )
    vocabulary = extractor.extract(document_text)
"""

from .vocabulary_extractor import VocabularyExtractor

__all__ = ['VocabularyExtractor']
