"""
Vocabulary Extractor Module

Extracts unusual and domain-specific vocabulary from legal documents using
NLP techniques (spaCy for NER, NLTK WordNet for definitions).

This module identifies:
- Proper nouns (people, organizations, locations)
- Medical terminology
- Acronyms (all-caps words like "HIPAA", "ADA")
- Technical/rare terms not found in standard dictionaries

The extracted vocabulary is categorized and assigned relevance scores based on
frequency and category, making it useful for creating case-specific glossaries.
"""

import os
import re
import subprocess
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Set

import spacy
import nltk
from nltk.corpus import wordnet

from src.debug_logger import debug_log


# Constants for spaCy model
SPACY_MODEL_NAME = "en_core_web_sm"
SPACY_MODEL_VERSION = "3.8.0"
SPACY_DOWNLOAD_TIMEOUT = 300  # 5 minutes


class VocabularyExtractor:
    """
    Extracts unusual vocabulary from text and provides categorization and definitions.

    Uses spaCy for Named Entity Recognition (NER) and NLTK WordNet for definitions.
    Automatically downloads required models/data if not present.

    Attributes:
        nlp: Loaded spaCy language model
        exclude_list: Set of words to exclude from extraction (common legal terms)
        medical_terms: Set of known medical terms for categorization

    Example:
        >>> extractor = VocabularyExtractor(
        ...     exclude_list_path="config/legal_exclude.txt",
        ...     medical_terms_path="config/medical_terms.txt"
        ... )
        >>> vocab = extractor.extract("The plaintiff John Smith filed a HIPAA complaint.")
        >>> for term in vocab:
        ...     print(f"{term['Term']}: {term['Category']}")
        John Smith: Proper Noun (Person)
        HIPAA: Acronym
    """

    def __init__(
        self,
        exclude_list_path: Optional[str] = None,
        medical_terms_path: Optional[str] = None
    ):
        """
        Initialize the vocabulary extractor.

        Args:
            exclude_list_path: Path to file containing words to exclude (one per line).
                              These are typically common legal terms that aren't unusual.
            medical_terms_path: Path to file containing known medical terms (one per line).
                               These get categorized as "Medical Term" with higher relevance.

        Note:
            If paths are None or files don't exist, empty sets are used.
            This increases false positives but allows the extractor to function.
        """
        # Load or download spaCy model
        self.nlp = self._load_spacy_model()

        # Load word lists
        self.exclude_list: Set[str] = (
            self._load_word_list(exclude_list_path) if exclude_list_path else set()
        )
        self.medical_terms: Set[str] = (
            self._load_word_list(medical_terms_path) if medical_terms_path else set()
        )

        # Ensure NLTK data is available
        self._ensure_nltk_data()

    def _load_spacy_model(self):
        """
        Load spaCy model, attempting to download if not present.

        Returns:
            Loaded spaCy language model

        Raises:
            OSError: If model cannot be loaded or downloaded
            subprocess.TimeoutExpired: If download takes too long
        """
        try:
            debug_log(f"[VOCAB] Loading spaCy model '{SPACY_MODEL_NAME}'...")
            return spacy.load(SPACY_MODEL_NAME)
        except OSError:
            debug_log(
                f"[VOCAB] spaCy model '{SPACY_MODEL_NAME}' not found. "
                "Attempting to download..."
            )
            return self._download_spacy_model()

    def _download_spacy_model(self):
        """
        Download spaCy model using pip in the current virtual environment.

        Uses sys.executable to ensure the model installs to the correct
        Python environment (important when running in a virtualenv).

        Returns:
            Loaded spaCy language model after successful download

        Raises:
            subprocess.TimeoutExpired: If download exceeds timeout
            Exception: If download or installation fails
        """
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', f'{SPACY_MODEL_NAME}=={SPACY_MODEL_VERSION}'],
                check=True,
                capture_output=True,
                timeout=SPACY_DOWNLOAD_TIMEOUT
            )
            debug_log(f"[VOCAB] Successfully downloaded spaCy model '{SPACY_MODEL_NAME}'")
            return spacy.load(SPACY_MODEL_NAME)
        except subprocess.TimeoutExpired:
            debug_log("[VOCAB] Download timeout: spaCy model download took too long.")
            raise
        except Exception as e:
            debug_log(
                f"[VOCAB] Failed to download spaCy model: {e}. "
                "Vocabulary extraction may have reduced functionality."
            )
            raise

    def _ensure_nltk_data(self):
        """Download NLTK data packages if not already present."""
        nltk_packages = [
            ('corpora/wordnet', 'wordnet'),
            ('tokenizers/punkt', 'punkt')
        ]

        for data_path, package_name in nltk_packages:
            try:
                nltk.data.find(data_path)
            except LookupError:
                debug_log(f"[VOCAB] Downloading NLTK {package_name} data...")
                nltk.download(package_name, quiet=True)

    def _load_word_list(self, file_path: str) -> Set[str]:
        """
        Load a list of words from a line-separated text file.

        Args:
            file_path: Path to the word list file

        Returns:
            Set of lowercase words from the file, or empty set if file not found
        """
        if file_path is None:
            debug_log("[VOCAB] Word list not specified. Using empty list.")
            return set()

        if not os.path.exists(file_path):
            debug_log(
                f"[VOCAB] Word list file not found at {file_path}. "
                "Using empty list (may increase false positives)."
            )
            return set()

        with open(file_path, 'r', encoding='utf-8') as f:
            word_list = {line.strip().lower() for line in f if line.strip()}
            debug_log(f"[VOCAB] Loaded {len(word_list)} words from {file_path}")
            return word_list

    def _is_unusual(self, token, ent_type: Optional[str] = None) -> bool:
        """
        Determine if a token represents an unusual/noteworthy term.

        Args:
            token: spaCy Token object
            ent_type: Entity type string (e.g., "PERSON", "ORG") or None

        Returns:
            True if the term should be extracted, False otherwise
        """
        # Skip non-alphabetic, whitespace, punctuation, and digits
        if not token.is_alpha or token.is_space or token.is_punct or token.is_digit:
            return False

        lower_text = token.text.lower()

        # Skip excluded words (common legal terms)
        if lower_text in self.exclude_list:
            return False

        # Named entities (Person, Org, Location) are always unusual
        if ent_type in ["PERSON", "ORG", "GPE", "LOC"]:
            return True

        # Medical terms are always unusual
        if lower_text in self.medical_terms:
            return True

        # Acronyms (all caps, 2+ chars) are unusual
        if re.fullmatch(r'[A-Z]{2,}', token.text):
            return True

        # If found in WordNet, it's a common English word
        if wordnet.synsets(lower_text):
            return False

        # Otherwise, consider it unusual (rare/technical term)
        return True

    def _get_category(self, token, ent_type: str) -> Optional[str]:
        """
        Determine the category for an unusual term.

        Args:
            token: spaCy Token object
            ent_type: Entity type string from spaCy NER

        Returns:
            Category string or None if term should be skipped
        """
        # Check for acronyms first (all caps, 2+ characters)
        if re.fullmatch(r'[A-Z]{2,}', token.text):
            return "Acronym"

        lower_text = token.text.lower()

        # Check medical terms
        if lower_text in self.medical_terms:
            return "Medical Term"

        # Categorize by entity type
        if ent_type:
            entity_categories = {
                "PERSON": "Proper Noun (Person)",
                "ORG": "Proper Noun (Organization)",
                "GPE": "Proper Noun (Location)",
                "LOC": "Proper Noun (Location)",
            }
            if ent_type in entity_categories:
                return entity_categories[ent_type]

            # Skip common entity types that aren't useful for vocabulary
            if ent_type in ["DATE", "TIME", "MONEY", "PERCENT"]:
                return None

        # Default category for other unusual words
        return "Technical Term"

    def _get_definition(self, term: str) -> str:
        """
        Get the definition of a term using WordNet.

        Args:
            term: The term to look up

        Returns:
            Definition string, or "N/A" if not found
        """
        synsets = wordnet.synsets(term)
        if synsets:
            return synsets[0].definition()
        return "N/A"

    def _calculate_relevance(self, category: str, frequency: int) -> str:
        """
        Calculate relevance score based on category and frequency.

        Args:
            category: Term category (e.g., "Proper Noun (Person)")
            frequency: Number of times the term appears in the document

        Returns:
            Relevance string: "Low", "Medium", "High", or "Very High"
        """
        # Proper nouns are inherently important
        if category in [
            "Proper Noun (Person)",
            "Proper Noun (Organization)",
            "Proper Noun (Location)"
        ]:
            return "Very High" if frequency > 1 else "High"

        # Medical terms and acronyms are moderately important
        if category in ["Medical Term", "Acronym"]:
            return "High" if frequency >= 2 else "Medium"

        # Technical terms need multiple occurrences to be relevant
        if category == "Technical Term":
            return "Medium" if frequency >= 3 else "Low"

        return "Low"

    def extract(self, text: str) -> List[Dict[str, str]]:
        """
        Extract unusual vocabulary from text with categorization and definitions.

        Performs a two-pass extraction:
        1. First pass: Extract named entities and unusual tokens, count frequencies
        2. Second pass: Deduplicate, categorize, and assign relevance scores

        Args:
            text: The document text to analyze

        Returns:
            List of dictionaries, each containing:
            - Term: The extracted term
            - Category: One of "Proper Noun (Person/Organization/Location)",
                       "Medical Term", "Acronym", or "Technical Term"
            - Relevance to Case: "Low", "Medium", "High", or "Very High"
            - Definition: WordNet definition or "N/A"
        """
        doc = self.nlp(text)

        # First pass: Extract terms and count frequencies
        extracted_terms, term_frequencies = self._first_pass_extraction(doc)

        # Second pass: Deduplicate and build final vocabulary
        vocabulary = self._second_pass_processing(extracted_terms, term_frequencies)

        return vocabulary

    def _first_pass_extraction(self, doc) -> tuple:
        """
        First pass: Extract all potential terms and count frequencies.

        Args:
            doc: spaCy Doc object

        Returns:
            Tuple of (extracted_terms list, term_frequencies dict)
        """
        extracted_terms = []
        term_frequencies = defaultdict(int)

        # Extract named entities first (prioritize multi-word entities)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]:
                term_text = ent.text
                if term_text.lower() not in self.exclude_list:
                    term_frequencies[term_text.lower()] += 1
                    extracted_terms.append({
                        "Term": term_text,
                        "ent_type": ent.label_,
                        "frequency_key": term_text.lower()
                    })

        # Extract unusual single tokens not already part of multi-word entities
        for token in doc:
            if self._is_unusual(token, ent_type=token.ent_type_):
                term_text = token.text

                # Check if token is part of an already-extracted entity
                is_part_of_entity = any(
                    ent.start <= token.i < ent.end and ent.text.lower() in term_frequencies
                    for ent in doc.ents
                )

                if not is_part_of_entity and term_text.lower() not in self.exclude_list:
                    term_frequencies[term_text.lower()] += 1
                    extracted_terms.append({
                        "Term": term_text,
                        "ent_type": token.ent_type_,
                        "frequency_key": term_text.lower()
                    })

        return extracted_terms, term_frequencies

    def _second_pass_processing(
        self,
        extracted_terms: List[Dict],
        term_frequencies: Dict[str, int]
    ) -> List[Dict[str, str]]:
        """
        Second pass: Deduplicate, categorize, and build final vocabulary list.

        Args:
            extracted_terms: List of term dictionaries from first pass
            term_frequencies: Dictionary mapping lowercase terms to frequency counts

        Returns:
            Final vocabulary list with categories, relevance, and definitions
        """
        vocabulary = []
        seen_terms = set()

        for item in extracted_terms:
            term = item["Term"]
            lower_term = term.lower()
            ent_type = item["ent_type"]

            # Skip duplicates
            if lower_term in seen_terms:
                continue

            # Determine category
            category = self._get_category(self.nlp(term)[0], ent_type=ent_type)

            # Skip if category is None (e.g., DATE, TIME entities)
            if category is None:
                continue

            # Calculate relevance based on category and frequency
            frequency = term_frequencies[lower_term]
            relevance = self._calculate_relevance(category, frequency)

            vocabulary.append({
                "Term": term,
                "Category": category,
                "Relevance to Case": relevance,
                "Definition": self._get_definition(term)
            })
            seen_terms.add(lower_term)

        return vocabulary
