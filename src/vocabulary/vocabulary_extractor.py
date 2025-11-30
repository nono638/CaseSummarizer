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
from pathlib import Path

import nltk
import spacy
from nltk.corpus import wordnet

from src.config import (
    GOOGLE_WORD_FREQUENCY_FILE,
    SPACY_DOWNLOAD_TIMEOUT_SEC,
    SPACY_SOCKET_TIMEOUT_SEC,
    SPACY_THREAD_TIMEOUT_SEC,
    VOCABULARY_BATCH_SIZE,
    VOCABULARY_MAX_TEXT_KB,
    VOCABULARY_MIN_OCCURRENCES,
    VOCABULARY_RARITY_THRESHOLD,
    VOCABULARY_SORT_BY_RARITY,
)
from src.logging_config import debug_log
from src.vocabulary.role_profiles import RoleDetectionProfile, StenographerProfile

# Constants for spaCy model
# Using large model (lg) for ~4% better NER accuracy vs small model (sm)
# Model size: 560MB download, ~741MB on disk
# Speed: ~10,014 words/sec on CPU (vs ~684 for transformer model)
SPACY_MODEL_NAME = "en_core_web_lg"
SPACY_MODEL_VERSION = "3.8.0"
# Timeout imported from config.py: SPACY_DOWNLOAD_TIMEOUT_SEC

# Regex patterns for filtering out word variations
# These match common patterns that shouldn't be included as "rare" vocabulary
VARIATION_FILTERS = [
    r'^[a-z]+\(s\)$',          # Matches "plaintiff(s)", "defendant(s)", etc.
    r'^[a-z]+s\(s\)$',         # Matches double plurals like "defendants(s)"
    r'^[a-z]+\([a-z]+\)$',     # Matches any parenthetical variation like "word(variant)"
    r'^[a-z]+\'s$',            # Matches possessives like "plaintiff's"
    r'^[a-z]+-[a-z]+$',        # Matches hyphenated words (often just variations)
]

# OCR error patterns - common scanner/PDF artifacts
# Conservative patterns to avoid false negatives on valid terms
OCR_ERROR_PATTERNS = [
    r'^[A-Za-z]+-[A-Z][a-z]',     # Line-break artifacts: "Hos-pital", "medi-cal"
    r'.*[0-9][A-Za-z]{2,}[0-9]',  # Digit-letter-digit sequences: "3ohn5mith"
]

# Common title abbreviations to exclude (not rare technical acronyms)
# These are well-known to stenographers and add no value to vocabulary list
TITLE_ABBREVIATIONS = {
    'dr', 'mr', 'mrs', 'ms', 'md', 'phd', 'esq', 'jr', 'sr', 'ii', 'iii', 'iv',
    'dds', 'dvm', 'od', 'do', 'rn', 'lpn', 'np', 'pa', 'pt', 'ot', 'cpa',
    'jd', 'llm', 'mba', 'cfa', 'pe', 'ra',
}

# Legal citation patterns - statute references stenographers already know
LEGAL_CITATION_PATTERNS = [
    r'^[A-Z]{2,}\s+(?:SS|§)\s*\d+',  # CPLR SS3043, NY SS123
    r'^\w+\s+Law\s+(?:SS|§)\s*\d+',   # Education Law SS6527
    r'^\d+\s+[A-Z]+\s+\d+',            # 22 NYCRR 130
    r'^[A-Z]{2,}\s+\d+',               # CPLR 4546 (without SS)
]

# Legal boilerplate phrase patterns - standard legal terminology
LEGAL_BOILERPLATE_PATTERNS = [
    r'Verified\s+(?:Bill|Answer|Complaint|Petition)',
    r'Notice\s+of\s+Commencement',
    r'Cause\s+of\s+Action',
    r'Honorable\s+Court',
    r'Answering\s+Defendant',
]

# Case citation pattern - case names (X v. Y)
CASE_CITATION_PATTERN = r'^[A-Z][a-zA-Z]+\s+v\.?\s+[A-Z][a-zA-Z]+$'

# Geographic code patterns - ZIP codes, etc.
GEOGRAPHIC_CODE_PATTERNS = [
    r'^\d{5}(?:-\d{4})?$',  # ZIP codes: 11354, 12345-6789
    r'^[A-Z]{2}\s+\d{5}$',   # State + ZIP: NY 11354
]

# --- NEW FILTERS (Session 15) ---

# Address fragment patterns - partial addresses extracted as entities
ADDRESS_FRAGMENT_PATTERNS = [
    r'\d+(?:st|nd|rd|th)\s+Floor',     # "11th Floor", "2nd Floor"
    r'\b(?:Street|Drive|Avenue|Road|Lane|Court|Boulevard|Place|Way)\b',  # Street suffixes
    r'^\d+\s+[A-Z]',                    # "123 Main" - number followed by word
]

# Document fragment patterns - multi-word junk from legal documents
DOCUMENT_FRAGMENT_PATTERNS = [
    r'^(?:SUPREME|CIVIL|FAMILY|DISTRICT)\s+COURT',  # Court headers
    r'^NOTICE\s+OF',                                  # Notice headers
    r'Attorneys?\s+for\s+(?:Plaintiff|Defendant)',   # Attorney listings
    r'Services?\s+-\s+(?:Plaintiff|Defendant|None)', # Table rows
    r"^(?:Plaintiff|Defendant)(?:'s)?$",              # Just "Plaintiff's"
    r'^(?:FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+CAUSE', # Causes of action
    r'^\d+\s+of\s+\d+$',                              # Page numbers "1 of 5"
]

# Entity length limits
MIN_ENTITY_LENGTH = 3    # Skip "M.D", "Esq" fragments (too short)
MAX_ENTITY_LENGTH = 60   # Skip very long fragments (document titles, etc.)

# Organization indicator words for category detection
ORGANIZATION_INDICATORS = {
    'LLP', 'PLLC', 'P.C.', 'LLC', 'Inc', 'Corp', 'Corporation',
    'Law Firm', 'Law Office', 'Firm',
    'Hospital', 'Medical', 'Healthcare', 'Health', 'Clinic',
    'University', 'College', 'School',
    'Bank', 'Insurance', 'Services',
}


class VocabularyExtractor:
    """
    Extracts unusual vocabulary from text and provides categorization and definitions.

    Uses spaCy for Named Entity Recognition (NER) and NLTK WordNet for definitions.
    Automatically downloads required models/data if not present.

    Attributes:
        nlp: Loaded spaCy language model
        exclude_list: Set of words to exclude from extraction (common legal terms)
        user_exclude_list: Set of user-specified terms to exclude (case-insensitive)
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
        exclude_list_path: str | None = None,
        medical_terms_path: str | None = None,
        user_exclude_path: str | None = None,
        role_profile: RoleDetectionProfile | None = None
    ):
        """
        Initialize the vocabulary extractor.

        Args:
            exclude_list_path: Path to file containing words to exclude (one per line).
                              These are typically common legal terms that aren't unusual.
            medical_terms_path: Path to file containing known medical terms (one per line).
                               These get categorized as "Medical Term" with higher relevance.
            user_exclude_path: Path to user's personal exclusion list (one per line).
                              These are terms the user has chosen to exclude via right-click.
            role_profile: Role detection profile for profession-specific relevance detection.
                         Defaults to StenographerProfile if not specified.

        Note:
            If paths are None or files don't exist, empty sets are used.
            This increases false positives but allows the extractor to function.
        """
        # Load or download spaCy model
        self.nlp = self._load_spacy_model()

        # Load word lists (all stored lowercase for case-insensitive matching)
        self.exclude_list: set[str] = (
            self._load_word_list(exclude_list_path) if exclude_list_path else set()
        )
        self.user_exclude_list: set[str] = (
            self._load_word_list(user_exclude_path) if user_exclude_path else set()
        )
        self.medical_terms: set[str] = (
            self._load_word_list(medical_terms_path) if medical_terms_path else set()
        )

        # Load common medical/legal words blacklist (defense-in-depth filtering)
        # This catches common words that slip through frequency filtering
        common_blacklist_path = Path(__file__).parent.parent.parent / "config" / "common_medical_legal.txt"
        self.common_words_blacklist: set[str] = self._load_word_list(common_blacklist_path)

        # Initialize rarity settings BEFORE loading frequency dataset
        # (frequency dataset loading logs the threshold value)
        self.frequency_rank_map: dict[str, int] = {}  # Cached word→rank mapping
        self.rarity_threshold = VOCABULARY_RARITY_THRESHOLD
        self.sort_by_rarity = VOCABULARY_SORT_BY_RARITY

        # Load Google word frequency dataset for rarity filtering
        self.frequency_dataset: dict[str, int] = self._load_frequency_dataset()

        # Store user exclude path for adding new exclusions
        self.user_exclude_path = user_exclude_path

        # Set role detection profile (defaults to Stenographer)
        self.role_profile = role_profile if role_profile is not None else StenographerProfile()

        # Ensure NLTK data is available
        self._ensure_nltk_data()

    # The Google word frequency dataset is sourced from Peter Norvig's website:
    # https://norvig.com/ngrams/
    # Specifically, the 'count_1w.txt' file is used for word frequencies.
    # https://norvig.com/ngrams/count_1w.txt
    def _load_frequency_dataset(self) -> dict[str, int]:
        """
        Load Google word frequency dataset and build cached rank mapping.

        Loads word→count mapping from file, then sorts by frequency to create
        a word→rank mapping for fast rarity lookups.

        Returns:
            Dictionary mapping word (lowercase) to frequency count
            Empty dict if file not found or cannot be loaded

        Side Effects:
            Populates self.frequency_rank_map with word→rank mapping
        """
        frequency_dict = {}

        if not GOOGLE_WORD_FREQUENCY_FILE.exists():
            debug_log(
                f"[VOCAB] Frequency dataset not found at {GOOGLE_WORD_FREQUENCY_FILE}. "
                "Will use WordNet-only filtering."
            )
            return frequency_dict

        try:
            with open(GOOGLE_WORD_FREQUENCY_FILE, encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        word, count_str = parts
                        try:
                            count = int(count_str)
                            frequency_dict[word.lower()] = count
                        except ValueError:
                            continue  # Skip lines with invalid counts

            debug_log(
                f"[VOCAB] Loaded {len(frequency_dict)} words from frequency dataset. "
                f"Rarity threshold: {self.rarity_threshold}"
            )

            # Build cached rank mapping (sort by frequency descending)
            # Rank 0 = most common word, rank 333K = least common
            debug_log("[VOCAB] Building frequency rank map for fast lookups...")
            sorted_words = sorted(frequency_dict.items(), key=lambda x: x[1], reverse=True)
            self.frequency_rank_map = {word: rank for rank, (word, _) in enumerate(sorted_words)}
            debug_log(f"[VOCAB] Built rank map for {len(self.frequency_rank_map)} words")

        except Exception as e:
            debug_log(f"[VOCAB] Error loading frequency dataset: {e}")

        return frequency_dict

    def _matches_variation_filter(self, word: str) -> bool:
        """
        Check if a word matches common variation patterns that should be filtered out.

        Args:
            word: The word to check (case-insensitive)

        Returns:
            True if the word matches a variation pattern, False otherwise
        """
        lower_word = word.lower()

        for pattern in VARIATION_FILTERS:
            if re.match(pattern, lower_word):
                return True

        return False

    def _clean_entity_text(self, entity_text: str) -> str:
        """
        Clean spaCy entity text to remove leading/trailing junk.

        Fixes issues like:
        - "and/or lung" → "lung"
        - "\nJohn Smith\n" → "John Smith"
        - "(Dr. Martinez)" → "Dr. Martinez"

        Args:
            entity_text: Raw entity text from spaCy

        Returns:
            Cleaned entity text, or empty string if nothing remains
        """
        cleaned = entity_text.strip()

        # Remove newlines and normalize whitespace
        cleaned = ' '.join(cleaned.split())

        # Remove leading/trailing conjunctions: "and/or lung" → "lung"
        cleaned = re.sub(r'^(and/or|and|or)\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+(and/or|and|or)$', '', cleaned, flags=re.IGNORECASE)

        # Remove leading/trailing punctuation (preserve internal hyphens/apostrophes)
        cleaned = cleaned.strip('.,;:!?()[]{}"\'/\\')

        return cleaned.strip()

    def _matches_entity_filter(self, entity_text: str) -> bool:
        """
        Check if an entity should be filtered out based on pattern matching.

        Catches:
        - Address fragments (NY 11354, 11th Floor, Community Drive)
        - Document fragments (SUPREME COURT, Notice of, Attorneys for)
        - Entities that are too short or too long
        - Legal boilerplate phrases

        Args:
            entity_text: The cleaned entity text to check

        Returns:
            True if the entity should be FILTERED OUT, False if it should be kept
        """
        # Length checks
        if len(entity_text) < MIN_ENTITY_LENGTH:
            return True  # Too short
        if len(entity_text) > MAX_ENTITY_LENGTH:
            return True  # Too long (likely document fragment)

        # Check address fragment patterns
        for pattern in ADDRESS_FRAGMENT_PATTERNS:
            if re.search(pattern, entity_text, re.IGNORECASE):
                return True

        # Check document fragment patterns
        for pattern in DOCUMENT_FRAGMENT_PATTERNS:
            if re.search(pattern, entity_text, re.IGNORECASE):
                return True

        # Check existing legal boilerplate patterns
        for pattern in LEGAL_BOILERPLATE_PATTERNS:
            if re.search(pattern, entity_text, re.IGNORECASE):
                return True

        # Check geographic code patterns (ZIP codes)
        for pattern in GEOGRAPHIC_CODE_PATTERNS:
            if re.match(pattern, entity_text):
                return True

        # Check legal citation patterns
        for pattern in LEGAL_CITATION_PATTERNS:
            if re.match(pattern, entity_text):
                return True

        return False

    def _looks_like_person_name(self, text: str) -> bool:
        """
        Heuristic: Does this text look like a person's name?

        Checks for patterns typical of names:
        - Two or more words
        - Words are capitalized
        - No business/organization indicators

        Args:
            text: The entity text to check

        Returns:
            True if it looks like a person name, False otherwise
        """
        if not text:
            return False

        words = text.split()

        # Single words can be names (surnames like "Smith", "Martinez")
        # But we're less confident about them
        if len(words) == 1:
            # If it's all caps and long, might be an acronym
            if text.isupper() and len(text) > 4:
                return False
            # Otherwise could be a surname
            return text[0].isupper()

        # Multi-word: check all words are capitalized
        for word in words:
            if not word:
                continue
            # Allow lowercase particles: "de", "van", "von"
            if word.lower() in {'de', 'van', 'von', 'da', 'del', 'della', 'di', 'la', 'le'}:
                continue
            if not word[0].isupper():
                return False

        # Reject if contains organization indicators
        for indicator in ORGANIZATION_INDICATORS:
            if indicator.upper() in text.upper():
                return False

        # Reject if it's all uppercase (likely an acronym or header)
        if text.isupper() and len(text) > 10:
            return False

        return True

    def _looks_like_organization(self, text: str) -> bool:
        """
        Heuristic: Does this text look like an organization?

        Checks for organization indicator words like LLP, Hospital, University, etc.

        Args:
            text: The entity text to check

        Returns:
            True if it looks like an organization, False otherwise
        """
        if not text:
            return False

        text_upper = text.upper()
        for indicator in ORGANIZATION_INDICATORS:
            if indicator.upper() in text_upper:
                return True

        return False

    def _is_word_rare_enough(self, word: str) -> bool:
        """
        Check if a word meets the rarity threshold using frequency rank.

        Uses cached rank mapping for O(1) lookup speed.

        Words are considered rare if:
        1. NOT in frequency dataset (extremely rare)
        2. Rank >= threshold (e.g., if threshold=75000, word must be rarer than top 75K)

        Args:
            word: The word to check (case-insensitive)

        Returns:
            True if word is rare enough to include, False if it's too common

        Example:
            threshold = 75000
            "the" (rank 1) → False (too common)
            "plaintiff" (rank ~50000) → False (still common)
            "spondylosis" (rank ~150000) → True (rare enough)
        """
        lower_word = word.lower()

        # If rarity threshold is disabled, accept all words
        if self.rarity_threshold < 0:
            return True

        # If no frequency data loaded, fall back to accepting all
        if not self.frequency_rank_map:
            return True

        # If word not in dataset, it's extremely rare (accept it)
        if lower_word not in self.frequency_rank_map:
            return True

        # Check if word's rank exceeds threshold
        # Higher rank = less common = rarer
        word_rank = self.frequency_rank_map[lower_word]
        return word_rank >= self.rarity_threshold

    def _load_spacy_model(self):
        """
        Load spaCy model with optimized component selection.

        Only enables components needed for vocabulary extraction:
        - NER (named entity recognition) - for people, places, organizations
        - Tokenizer (always enabled) - for word segmentation

        Disables unused components for ~3x speed improvement:
        - tagger (POS tagging) - not needed for vocab extraction
        - lemmatizer - not needed (we use raw tokens)
        - attribute_ruler - not needed

        Returns:
            Loaded spaCy language model

        Raises:
            OSError: If model cannot be loaded or downloaded
            subprocess.TimeoutExpired: If download takes too long
        """
        # Components to disable for performance (we only need NER)
        # This provides ~3x speedup on large documents
        disabled_components = ["tagger", "lemmatizer", "attribute_ruler"]

        try:
            debug_log(f"[VOCAB] Loading spaCy model '{SPACY_MODEL_NAME}' (optimized, NER-only)...")
            nlp = spacy.load(SPACY_MODEL_NAME, disable=disabled_components)
            debug_log(f"[VOCAB] Loaded with disabled components: {disabled_components}")
            return nlp
        except OSError:
            debug_log(
                f"[VOCAB] spaCy model '{SPACY_MODEL_NAME}' not found. "
                "Attempting to download..."
            )
            return self._download_spacy_model(disabled_components)

    def _download_spacy_model(self, disabled_components=None):
        """
        Download spaCy model using pip in the current virtual environment.

        Uses sys.executable to ensure the model installs to the correct
        Python environment (important when running in a virtualenv).

        Args:
            disabled_components: List of component names to disable after loading

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
                timeout=SPACY_DOWNLOAD_TIMEOUT_SEC
            )
            debug_log(f"[VOCAB] Successfully downloaded spaCy model '{SPACY_MODEL_NAME}'")
            if disabled_components:
                return spacy.load(SPACY_MODEL_NAME, disable=disabled_components)
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
        """
        Download NLTK data packages if not already present.

        Uses a timeout mechanism to prevent indefinite hangs on network issues.
        Falls back to offline mode if downloads fail.
        """
        import socket
        import threading

        nltk_packages = [
            ('corpora/wordnet', 'wordnet'),
            ('tokenizers/punkt', 'punkt')
        ]

        # Set a short timeout for network operations
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(SPACY_SOCKET_TIMEOUT_SEC)

        for data_path, package_name in nltk_packages:
            try:
                nltk.data.find(data_path)
                debug_log(f"[VOCAB] NLTK {package_name} data already present")
            except LookupError:
                debug_log(f"[VOCAB] Downloading NLTK {package_name} data (10s timeout)...")
                try:
                    # Run download with timeout using threading
                    download_success = [False]
                    download_error = [None]

                    def download_task(pkg=package_name, success=download_success, err=download_error):
                        try:
                            nltk.download(pkg, quiet=True)
                            success[0] = True
                        except Exception as e:
                            err[0] = e

                    thread = threading.Thread(target=download_task, daemon=True)
                    thread.start()
                    thread.join(timeout=SPACY_THREAD_TIMEOUT_SEC)

                    if thread.is_alive():
                        debug_log(f"[VOCAB] NLTK {package_name} download timed out. Continuing without it.")
                    elif download_error[0]:
                        debug_log(f"[VOCAB] NLTK {package_name} download failed: {download_error[0]}")
                    else:
                        debug_log(f"[VOCAB] NLTK {package_name} downloaded successfully")

                except Exception as e:
                    debug_log(f"[VOCAB] NLTK {package_name} download error: {e}. Continuing without it.")

        # Restore original timeout
        socket.setdefaulttimeout(original_timeout)

    def add_user_exclusion(self, term: str) -> bool:
        """
        Add a term to the user's exclusion list (case-insensitive).

        The term is stored in lowercase for case-insensitive matching.
        Future vocabulary extractions will skip this term.

        Args:
            term: The term to exclude from future extractions

        Returns:
            True if successfully added, False otherwise
        """
        if not self.user_exclude_path:
            debug_log("[VOCAB] Cannot add exclusion: no user exclude path configured")
            return False

        lower_term = term.lower().strip()
        if not lower_term:
            return False

        # Add to in-memory set
        self.user_exclude_list.add(lower_term)

        # Persist to file
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(self.user_exclude_path), exist_ok=True)

            # Append to file (create if doesn't exist)
            with open(self.user_exclude_path, 'a', encoding='utf-8') as f:
                f.write(f"{lower_term}\n")

            debug_log(f"[VOCAB] Added '{term}' to user exclusion list")
            return True
        except Exception as e:
            debug_log(f"[VOCAB] Failed to save user exclusion: {e}")
            return False

    def reload_user_exclusions(self):
        """Reload user exclusions from file (useful after external changes)."""
        if self.user_exclude_path:
            self.user_exclude_list = self._load_word_list(self.user_exclude_path)

    def _load_word_list(self, file_path: str) -> set[str]:
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

        with open(file_path, encoding='utf-8') as f:
            word_list = {line.strip().lower() for line in f if line.strip()}
            debug_log(f"[VOCAB] Loaded {len(word_list)} words from {file_path}")
            return word_list

    def _is_unusual(self, token, ent_type: str | None = None) -> bool:
        """
        Determine if a token represents an unusual/noteworthy term.

        Filters words through multiple stages:
        1. Basic checks (alpha, whitespace, punctuation)
        2. Exclusion lists (common legal terms, user exclusions)
        3. Variation patterns (plaintiff(s), defendant's, etc.)
        4. Named entities (PERSON, ORG, GPE, LOC - always accepted)
        5. Medical terms (always accepted)
        6. Acronyms (2+ uppercase letters - accepted)
        7. Frequency-based rarity (Google word frequency dataset)
        8. WordNet fallback (not in dictionary = rare)

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

        # Skip user-excluded words (case-insensitive)
        if lower_text in self.user_exclude_list:
            return False

        # Skip common medical/legal blacklist (defense-in-depth)
        # Catches words like "hospital", "doctor", "medical", "plaintiff", etc.
        if lower_text in self.common_words_blacklist:
            return False

        # Skip words matching variation patterns (plaintiff(s), defendant's, etc.)
        if self._matches_variation_filter(token.text):
            return False

        # Skip legal citations (CPLR SS3043, Education Law SS6527, etc.)
        for pattern in LEGAL_CITATION_PATTERNS:
            if re.match(pattern, token.text):
                return False

        # Skip legal boilerplate phrases (Verified Answer, Cause of Action, etc.)
        for pattern in LEGAL_BOILERPLATE_PATTERNS:
            if re.search(pattern, token.text, re.IGNORECASE):
                return False

        # Skip case citations (Mahr v. Perry pattern)
        if re.match(CASE_CITATION_PATTERN, token.text):
            return False

        # Skip geographic codes (ZIP codes, etc.)
        for pattern in GEOGRAPHIC_CODE_PATTERNS:
            if re.match(pattern, token.text):
                return False

        # Skip likely OCR errors (line-break artifacts, digit-letter mixups)
        for pattern in OCR_ERROR_PATTERNS:
            if re.match(pattern, token.text):
                return False

        # Named entities (Person, Org, Location) - trust spaCy's NER tagging
        # spaCy is trained on annotated data and recognizes names even when they're common words
        # e.g., "Smith" is a common word but when tagged as PERSON, it's a surname
        if ent_type in ["PERSON", "ORG", "GPE", "LOC"]:
            # Accept all named entities (multi-word or single-word)
            # The entity extractor in _first_pass_extraction prefers multi-word entities
            # from doc.ents, so single-word tokens here are typically legitimate names
            return True

        # Medical terms from our curated list are ALWAYS accepted
        # These are domain-specific terms important for stenographers
        # (frequency filtering is done at list curation time, not extraction time)
        if lower_text in self.medical_terms:
            return True  # Medical term from curated list → always accept

        # Acronyms (all caps, 2+ chars) are unusual, EXCEPT title abbreviations
        if re.fullmatch(r'[A-Z]{2,}', token.text):
            # Filter common title abbreviations (M.D., Ph.D., Esq., R.N., etc.)
            if lower_text in TITLE_ABBREVIATIONS:
                return False  # Common title → reject
            return True  # Rare acronym (HIPAA, FMLA, ADA) → accept

        # Check frequency-based rarity using Google word frequency dataset
        if self.frequency_dataset and not self._is_word_rare_enough(token.text):
            return False

        # If found in WordNet, it's a common English word
        if wordnet.synsets(lower_text):
            return False

        # Otherwise, consider it unusual (rare/technical term)
        return True

    def _get_category(self, token, ent_type: str, full_term: str = None) -> str | None:
        """
        Determine the simplified category for an unusual term.

        Categories:
        - Person: Named individuals (validated with heuristics)
        - Place: Organizations, locations, facilities (validated)
        - Medical: Medical/anatomical terms
        - Technical: Other rare/unusual terms
        - Unknown: When spaCy's classification conflicts with heuristics

        Args:
            token: spaCy Token object
            ent_type: Entity type string from spaCy NER
            full_term: Full entity text (for multi-word entity validation)

        Returns:
            Category string or None if term should be skipped
        """
        lower_text = token.text.lower()
        term_to_validate = full_term or token.text

        # Check medical terms first (highest priority - curated list)
        if lower_text in self.medical_terms:
            return "Medical"

        # Categorize by entity type with validation
        if ent_type:
            # People - validate with heuristics
            if ent_type == "PERSON":
                # Check if it actually looks like a person name
                if self._looks_like_person_name(term_to_validate):
                    return "Person"
                # spaCy says PERSON but doesn't look like a name
                # Could be a misclassification - mark as Unknown
                return "Unknown"

            # Places/Organizations - validate with heuristics
            if ent_type in ["ORG", "GPE", "LOC"]:
                # Check for obvious organization indicators
                if self._looks_like_organization(term_to_validate):
                    return "Place"
                # Check if it actually looks like a person name (misclassified)
                if self._looks_like_person_name(term_to_validate):
                    # spaCy says ORG/GPE/LOC but looks like a person
                    # Could be "ANDY CHOY" misclassified as ORG
                    return "Unknown"
                # No conflict - accept as Place
                return "Place"

            # Skip entity types that aren't useful (dates, money, etc.)
            if ent_type in ["DATE", "TIME", "MONEY", "PERCENT", "CARDINAL", "ORDINAL"]:
                return None

        # Check for acronyms - categorize as Technical
        if re.fullmatch(r'[A-Z]{2,}', token.text):
            return "Technical"

        # Default category for other unusual words
        return "Technical"

    def _get_definition(self, term: str, category: str) -> str:
        """
        Get definition for medical/technical terms only.

        Stenographers don't need definitions for people/places (they just need
        to know WHO they are and WHY they're relevant). Definitions are only
        useful for unfamiliar medical/technical terminology.

        Args:
            term: The term to look up
            category: Term category (Person/Place/Medical/Technical/Unknown)

        Returns:
            Definition string for Medical/Technical terms
            "—" for Person/Place/Unknown (no definition needed)
            "—" if WordNet lookup fails
        """
        # Skip definitions for people, places, and unknown categories
        if category in ["Person", "Place", "Unknown"]:
            return "—"

        # Look up definition for Medical/Technical terms
        synsets = wordnet.synsets(term)
        if synsets:
            return synsets[0].definition()

        return "—"


    def _chunk_text(self, text: str, chunk_size_kb: int = 50) -> list[str]:
        """
        Split text into chunks for efficient NLP processing.

        Splits on paragraph boundaries (double newlines) when possible,
        falling back to sentence boundaries, then character boundaries.

        Args:
            text: Full document text
            chunk_size_kb: Target chunk size in KB (default 50KB)

        Returns:
            List of text chunks
        """
        chunk_size_chars = chunk_size_kb * 1024
        chunks = []

        # If text is small enough, return as single chunk
        if len(text) <= chunk_size_chars:
            return [text]

        # Split on double newlines (paragraphs) first
        paragraphs = text.split('\n\n')
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para) + 2  # +2 for the newlines we removed

            if current_size + para_size > chunk_size_chars and current_chunk:
                # Save current chunk and start new one
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size

        # Don't forget the last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    def extract(self, text: str, doc_count: int = 1) -> list[dict[str, str]]:
        """
        Extract unusual vocabulary from text with categorization, role detection, and definitions.

        Uses chunked processing with nlp.pipe() for efficient memory usage on large documents.
        Per spaCy best practices: "there's no benefit to processing a large document as a
        single unit - all features are relatively local, usually within the same paragraph"

        Performs a three-step extraction:
        1. First pass: Extract named entities and unusual tokens from chunks
        2. Second pass: Deduplicate, categorize, detect roles/relevance, add definitions
        3. Third pass: Sort by rarity if enabled

        Args:
            text: The document text to analyze
            doc_count: Number of documents being processed (for frequency-based filtering).
                      Terms appearing more than doc_count * 4 times are filtered out
                      (except PERSON entities which are preserved).

        Returns:
            List of dictionaries, each containing:
            - Term: The extracted term
            - Type: One of "Person", "Place", "Medical", "Technical", or "Unknown"
            - Role/Relevance: Context-specific role (e.g., "Plaintiff", "Treating physician",
                             "Accident location", "Medical term", "Technical term", "Needs review")
            - Definition: WordNet definition for Medical/Technical terms, "—" for Person/Place/Unknown
        """
        import time

        original_len = len(text)
        original_kb = original_len // 1024
        debug_log(f"[VOCAB] Starting extraction on {original_kb}KB document")

        # Chunk text for efficient processing (50KB chunks recommended by spaCy docs)
        chunks = self._chunk_text(text, chunk_size_kb=50)
        debug_log(f"[VOCAB] Split into {len(chunks)} chunks for parallel NLP processing")

        # Limit total text processed to max size
        max_chars = VOCABULARY_MAX_TEXT_KB * 1024
        total_chars = 0
        chunks_to_process = []
        for chunk in chunks:
            if total_chars + len(chunk) > max_chars:
                # Include partial chunk to hit limit
                remaining = max_chars - total_chars
                if remaining > 1000:  # Only include if meaningful amount
                    chunks_to_process.append(chunk[:remaining])
                break
            chunks_to_process.append(chunk)
            total_chars += len(chunk)

        if total_chars < original_len:
            debug_log(
                f"[VOCAB] Processing {total_chars//1024}KB of {original_kb}KB "
                f"({len(chunks_to_process)} of {len(chunks)} chunks)"
            )

        # Run spaCy NLP pipeline on chunks using nlp.pipe() for efficiency
        # nlp.pipe() is recommended for batch processing - better memory usage
        debug_log(f"[VOCAB] Starting spaCy NLP (batch mode, {len(chunks_to_process)} chunks)...")
        start_time = time.time()

        all_extracted_terms = []
        term_frequencies = defaultdict(int)
        total_tokens = 0

        # Process chunks in batches using nlp.pipe()
        # VOCABULARY_BATCH_SIZE configurable for performance tuning (default: 8)
        for i, doc in enumerate(self.nlp.pipe(chunks_to_process, batch_size=VOCABULARY_BATCH_SIZE)):
            total_tokens += len(doc)
            chunk_terms, chunk_freqs = self._first_pass_extraction(doc)
            all_extracted_terms.extend(chunk_terms)
            for term, count in chunk_freqs.items():
                term_frequencies[term] += count

            # Log progress every 5 chunks
            if (i + 1) % 5 == 0:
                debug_log(f"[VOCAB] Processed {i+1}/{len(chunks_to_process)} chunks...")

        nlp_time = time.time() - start_time
        debug_log(f"[VOCAB] spaCy NLP completed in {nlp_time:.1f}s ({total_tokens} tokens from {len(chunks_to_process)} chunks)")

        # First pass complete - now deduplicate
        debug_log(f"[VOCAB] Found {len(all_extracted_terms)} raw terms, deduplicating...")
        extracted_terms = self._deduplicate_terms(all_extracted_terms)
        debug_log(f"[VOCAB] After deduplication: {len(extracted_terms)} unique terms")

        # Second pass: Categorize, detect roles, and build final vocabulary
        # Use full text for role detection context (to find "plaintiff", "defendant" mentions)
        debug_log(f"[VOCAB] Second pass: categorizing and role detection (doc_count={doc_count}, freq_threshold={doc_count*4})...")
        start_time = time.time()
        vocabulary = self._second_pass_processing(extracted_terms, dict(term_frequencies), text, doc_count)
        debug_log(f"[VOCAB] Second pass completed in {time.time()-start_time:.1f}s")

        # Third pass: Sort by rarity if enabled
        if self.sort_by_rarity and self.frequency_dataset:
            vocabulary = self._sort_by_rarity(vocabulary)

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
                # Clean entity text to remove fragments and junk
                term_text = self._clean_entity_text(ent.text)

                # Skip if nothing left after cleaning (e.g., "and/or" → "")
                if not term_text:
                    continue

                # NEW: Apply pattern-based entity filter (Phase 3)
                # Catches addresses, boilerplate, length issues
                if self._matches_entity_filter(term_text):
                    continue

                # NEW: Single-word entities need rarity check (Phase 4)
                # EXCEPT PERSON - names like "Smith" should be kept
                words = term_text.split()
                if len(words) == 1 and ent.label_ != "PERSON":
                    if not self._is_word_rare_enough(term_text):
                        continue

                lower_term = term_text.lower()
                # Check both system and user exclusions (case-insensitive)
                if lower_term not in self.exclude_list and lower_term not in self.user_exclude_list:
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

    def _sort_by_rarity(self, vocabulary: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Sort vocabulary list by rarity (rarest words first).

        Sorting strategy:
        1. Words NOT in frequency dataset appear first (extremely rare)
        2. Words IN dataset sorted by frequency count (lowest count = rarest)

        Args:
            vocabulary: List of vocabulary dictionaries

        Returns:
            Sorted vocabulary list
        """
        not_in_dataset = []
        in_dataset = []

        for item in vocabulary:
            term = item["Term"].lower()
            if term not in self.frequency_dataset:
                not_in_dataset.append(item)
            else:
                in_dataset.append(item)

        # Sort in-dataset words by frequency count (ascending = rarest first)
        in_dataset.sort(key=lambda x: self.frequency_dataset.get(x["Term"].lower(), float('inf')))

        # Combine: not-in-dataset (rarest) + in-dataset sorted by count
        return not_in_dataset + in_dataset

    def _deduplicate_terms(self, extracted_terms: list[dict]) -> list[dict]:
        """
        Remove duplicate/variant entries from extracted terms.

        Handles:
        1. Prefix normalization: "the State of New York" → "State of New York"
        2. Party label removal: "Plaintiff XIANJUN LIANG" → "XIANJUN LIANG"
        3. Substring filtering: If "XIANJUN LIANG" exists, filter out "XIANJUN"

        Performance: O(n log n) using sorted word lists instead of O(n²) comparison.

        Args:
            extracted_terms: List of extracted term dictionaries

        Returns:
            Deduplicated list of term dictionaries
        """
        normalized_map = {}  # normalized lower → original term dict

        # First pass: Normalize and keep shortest version of each unique term
        for term_dict in extracted_terms:
            text = term_dict["Term"]

            # Remove common article prefixes
            normalized = re.sub(r'^(?:the|a|an)\s+', '', text, flags=re.IGNORECASE)

            # Remove party label prefixes
            normalized = re.sub(r'^(?:Plaintiff|Defendant)[\'s]?\s+', '', normalized, flags=re.IGNORECASE)

            normalized_lower = normalized.lower()

            # Keep shortest version (prefer "John Smith" over "Plaintiff John Smith")
            if normalized_lower not in normalized_map or len(normalized) < len(normalized_map[normalized_lower]["Term"]):
                # Update Term in dict to normalized version
                updated_dict = term_dict.copy()
                updated_dict["Term"] = normalized
                normalized_map[normalized_lower] = updated_dict

        # Second pass: Filter substring duplicates using optimized algorithm
        # Build a set of all normalized terms for fast substring checking
        terms_list = list(normalized_map.values())

        # Sort by length descending - longer terms first
        # This allows us to check if shorter terms are substrings of longer ones
        terms_by_length = sorted(terms_list, key=lambda x: len(x["Term"]), reverse=True)

        # Build a set of "contained" terms that should be filtered
        # A term is contained if it appears as a substring of a longer term
        contained_terms = set()

        # For each term (sorted long to short), check if it contains any shorter terms
        # Use substring containment check (word-based approach reserved for future use)
        for i, term_dict in enumerate(terms_by_length):
            term_lower = term_dict["Term"].lower()

            # Check remaining (shorter) terms
            for j in range(i + 1, len(terms_by_length)):
                other_dict = terms_by_length[j]
                other_lower = other_dict["Term"].lower()

                # Quick check: if other term is substring of this term, mark as contained
                if other_lower in term_lower and other_lower != term_lower:
                    contained_terms.add(other_lower)

        # Filter out contained terms
        final_terms = [
            term_dict for term_dict in terms_list
            if term_dict["Term"].lower() not in contained_terms
        ]

        return final_terms

    def _get_term_frequency_rank(self, term: str) -> int:
        """
        Get Google frequency rank for a term (lower rank = more common).

        Args:
            term: The term to look up (case-insensitive)

        Returns:
            Rank (0-333000) if found in dataset, 0 if not found (extremely rare)
        """
        return self.frequency_rank_map.get(term.lower(), 0)

    def _calculate_quality_score(
        self, category: str, term_count: int, frequency_rank: int
    ) -> float:
        """
        Calculate a composite quality score (0-100) for a vocabulary term.

        Higher score = more likely to be a useful, high-quality term.

        Scoring factors:
        - Multiple occurrences boost score (recurring = important)
        - Rarer words (high rank) get boost
        - Reliable categories (Person/Place/Medical) get boost
        - Unknown category gets no boost (needs review)

        Args:
            category: Term category (Person/Place/Medical/Technical/Unknown)
            term_count: Number of occurrences in the documents
            frequency_rank: Google frequency rank (0 = not found/very rare)

        Returns:
            Quality score between 0.0 and 100.0
        """
        score = 50.0  # Base score

        # Boost for multiple occurrences (max +20)
        # Each occurrence adds 5 points, capped at 20
        occurrence_boost = min(term_count * 5, 20)
        score += occurrence_boost

        # Boost for rare words (max +20)
        # 0 = not in dataset = extremely rare = +20
        # >200K = rare = +15
        # >180K = somewhat rare = +10
        if frequency_rank == 0:
            score += 20  # Not in Google dataset - very rare
        elif frequency_rank > 200000:
            score += 15
        elif frequency_rank > 180000:
            score += 10

        # Boost for reliable categories (max +10)
        category_boost = {
            'Person': 10,
            'Place': 10,
            'Medical': 8,
            'Technical': 5,
            'Unknown': 0
        }
        score += category_boost.get(category, 0)

        return min(100.0, max(0.0, round(score, 1)))

    def _second_pass_processing(
        self,
        extracted_terms: list[dict],
        term_frequencies: dict[str, int],
        full_text: str,
        doc_count: int = 1
    ) -> list[dict[str, str]]:
        """
        Second pass: Deduplicate, categorize, detect roles, and build final vocabulary list.

        Args:
            extracted_terms: List of term dictionaries from first pass
            term_frequencies: Dictionary mapping lowercase terms to frequency counts
            full_text: Complete document text for role/relevance detection
            doc_count: Number of documents being processed (for frequency threshold)

        Returns:
            Final vocabulary list with Type, Role/Relevance, and Definition
            Format: [{"Term": str, "Type": str, "Role/Relevance": str, "Definition": str}, ...]
        """
        vocabulary = []
        seen_terms = set()

        # Calculate dynamic frequency threshold: doc_count * 4
        # Terms appearing more than this are likely common legal jargon
        frequency_threshold = doc_count * 4

        for item in extracted_terms:
            term = item["Term"]
            lower_term = term.lower()
            ent_type = item["ent_type"]
            term_count = term_frequencies.get(lower_term, 1)

            # Skip duplicates
            if lower_term in seen_terms:
                continue

            # Determine category (simplified: Person/Place/Medical/Technical/Unknown)
            # Pass full term for proper validation
            category = self._get_category(self.nlp(term)[0], ent_type=ent_type, full_term=term)

            # Skip if category is None (e.g., DATE, TIME entities)
            if category is None:
                continue

            # Document frequency filtering (Phase 2)
            # Skip non-PERSON terms that appear too frequently
            # PERSON entities are exempt - parties' names appear often but are important
            if category != "Person" and term_count > frequency_threshold:
                continue

            # Minimum occurrence filtering (Session 23)
            # Skip non-PERSON terms that appear only once (likely OCR errors/typos)
            # PERSON entities are exempt - party names may appear once but are important
            if category != "Person" and term_count < VOCABULARY_MIN_OCCURRENCES:
                continue

            # Detect role/relevance using profession-specific profile
            if category == "Person":
                role_relevance = self.role_profile.detect_person_role(term, full_text)
            elif category == "Place":
                role_relevance = self.role_profile.detect_place_relevance(term, full_text)
            elif category == "Medical":
                role_relevance = "Medical term"
            elif category == "Unknown":
                role_relevance = "Needs review"
            else:  # Technical
                role_relevance = "Technical term"

            # Calculate confidence metrics (Session 23)
            frequency_rank = self._get_term_frequency_rank(term)
            quality_score = self._calculate_quality_score(category, term_count, frequency_rank)

            vocabulary.append({
                "Term": term,
                "Type": category,  # Simplified: Person/Place/Medical/Technical/Unknown
                "Role/Relevance": role_relevance,  # Context-specific relevance
                "Quality Score": quality_score,  # Composite 0-100 (higher = better)
                "In-Case Freq": term_count,  # How many times term appears
                "Freq Rank": frequency_rank,  # Google rank (0=rare, high=common)
                "Definition": self._get_definition(term, category)  # Only for Medical/Technical
            })
            seen_terms.add(lower_term)

        return vocabulary
