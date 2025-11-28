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
from src.config import (
    GOOGLE_WORD_FREQUENCY_FILE,
    VOCABULARY_RARITY_THRESHOLD,
    VOCABULARY_SORT_BY_RARITY
)
from src.vocabulary.role_profiles import RoleDetectionProfile, StenographerProfile


# Constants for spaCy model
SPACY_MODEL_NAME = "en_core_web_sm"
SPACY_MODEL_VERSION = "3.8.0"
SPACY_DOWNLOAD_TIMEOUT = 300  # 5 minutes

# Regex patterns for filtering out word variations
# These match common patterns that shouldn't be included as "rare" vocabulary
VARIATION_FILTERS = [
    r'^[a-z]+\(s\)$',          # Matches "plaintiff(s)", "defendant(s)", etc.
    r'^[a-z]+s\(s\)$',         # Matches double plurals like "defendants(s)"
    r'^[a-z]+\([a-z]+\)$',     # Matches any parenthetical variation like "word(variant)"
    r'^[a-z]+\'s$',            # Matches possessives like "plaintiff's"
    r'^[a-z]+-[a-z]+$',        # Matches hyphenated words (often just variations)
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
        exclude_list_path: Optional[str] = None,
        medical_terms_path: Optional[str] = None,
        user_exclude_path: Optional[str] = None,
        role_profile: Optional[RoleDetectionProfile] = None
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
        self.exclude_list: Set[str] = (
            self._load_word_list(exclude_list_path) if exclude_list_path else set()
        )
        self.user_exclude_list: Set[str] = (
            self._load_word_list(user_exclude_path) if user_exclude_path else set()
        )
        self.medical_terms: Set[str] = (
            self._load_word_list(medical_terms_path) if medical_terms_path else set()
        )

        # Load common medical/legal words blacklist (defense-in-depth filtering)
        # This catches common words that slip through frequency filtering
        common_blacklist_path = Path(__file__).parent.parent.parent / "config" / "common_medical_legal.txt"
        self.common_words_blacklist: Set[str] = self._load_word_list(common_blacklist_path)

        # Load Google word frequency dataset for rarity filtering
        self.frequency_dataset: Dict[str, int] = self._load_frequency_dataset()
        self.frequency_rank_map: Dict[str, int] = {}  # Cached word→rank mapping
        self.rarity_threshold = VOCABULARY_RARITY_THRESHOLD
        self.sort_by_rarity = VOCABULARY_SORT_BY_RARITY

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
    def _load_frequency_dataset(self) -> Dict[str, int]:
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
            with open(GOOGLE_WORD_FREQUENCY_FILE, 'r', encoding='utf-8') as f:
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

        # Named entities (Person, Org, Location) should bypass frequency check,
        # BUT add safety net for common words to filter spaCy false positives
        if ent_type in ["PERSON", "ORG", "GPE", "LOC"]:
            # Multi-word entities always accepted (e.g., "John Smith", "Memorial Hospital")
            if len(token.text.split()) > 1:
                return True

            # Single-word entities: still check frequency to filter "the", "and", etc.
            # This catches spaCy tagging errors like "the Medical Center" → extracting "the"
            if self.frequency_dataset:
                if not self._is_word_rare_enough(token.text):
                    return False  # Too common (even though tagged as entity) → reject

            return True  # Rare single-word entity → accept

        # Medical terms: filter common words, keep rare terms
        # Common: "hospital" (rank 1345), "doctor" (rank 2034), "medical" (rank 501)
        # Rare: "adenocarcinoma" (rank >150K), "bronchogenic" (rank >150K)
        if lower_text in self.medical_terms:
            # Use frequency threshold to separate common from rare
            if self.frequency_dataset:
                if not self._is_word_rare_enough(token.text):
                    return False  # Common medical word → reject

            return True  # Rare medical term → accept

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

    def _get_category(self, token, ent_type: str) -> Optional[str]:
        """
        Determine the simplified category for an unusual term.

        Categories:
        - Person: Named individuals
        - Place: Organizations, locations, facilities
        - Medical: Medical/anatomical terms
        - Technical: Other rare/unusual terms

        Args:
            token: spaCy Token object
            ent_type: Entity type string from spaCy NER

        Returns:
            Category string or None if term should be skipped
        """
        lower_text = token.text.lower()

        # Check medical terms first (highest priority)
        if lower_text in self.medical_terms:
            return "Medical"

        # Categorize by entity type
        if ent_type:
            # People
            if ent_type == "PERSON":
                return "Person"

            # Places/Organizations
            if ent_type in ["ORG", "GPE", "LOC"]:
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
            category: Term category (Person/Place/Medical/Technical)

        Returns:
            Definition string for Medical/Technical terms
            "—" for Person/Place (no definition needed)
            "—" if WordNet lookup fails
        """
        # Skip definitions for people and places
        if category in ["Person", "Place"]:
            return "—"

        # Look up definition for Medical/Technical terms
        synsets = wordnet.synsets(term)
        if synsets:
            return synsets[0].definition()

        return "—"


    def extract(self, text: str) -> List[Dict[str, str]]:
        """
        Extract unusual vocabulary from text with categorization, role detection, and definitions.

        Performs a three-step extraction:
        1. First pass: Extract named entities and unusual tokens, count frequencies
        2. Second pass: Deduplicate, categorize, detect roles/relevance, add definitions
        3. Third pass: Sort by rarity if enabled

        Args:
            text: The document text to analyze

        Returns:
            List of dictionaries, each containing:
            - Term: The extracted term
            - Type: One of "Person", "Place", "Medical", or "Technical"
            - Role/Relevance: Context-specific role (e.g., "Plaintiff", "Treating physician",
                             "Accident location", "Medical term", "Technical term")
            - Definition: WordNet definition for Medical/Technical terms, "—" for Person/Place
        """
        doc = self.nlp(text)

        # First pass: Extract terms and count frequencies
        extracted_terms, term_frequencies = self._first_pass_extraction(doc)

        # Deduplicate terms (remove variants and substrings)
        extracted_terms = self._deduplicate_terms(extracted_terms)

        # Second pass: Categorize, detect roles, and build final vocabulary
        vocabulary = self._second_pass_processing(extracted_terms, term_frequencies, text)

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

    def _sort_by_rarity(self, vocabulary: List[Dict[str, str]]) -> List[Dict[str, str]]:
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

    def _deduplicate_terms(self, extracted_terms: List[Dict]) -> List[Dict]:
        """
        Remove duplicate/variant entries from extracted terms.

        Handles:
        1. Prefix normalization: "the State of New York" → "State of New York"
        2. Party label removal: "Plaintiff XIANJUN LIANG" → "XIANJUN LIANG"
        3. Substring filtering: If "XIANJUN LIANG" exists, filter out "XIANJUN"

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

        # Second pass: Filter substring duplicates
        # If "XIANJUN LIANG" exists, filter out "XIANJUN"
        final_terms = []
        terms_list = list(normalized_map.values())

        for i, term_dict in enumerate(terms_list):
            term_text = term_dict["Term"]
            is_substring = False

            # Check if this term is a substring of any other term
            for j, other_dict in enumerate(terms_list):
                if i != j:
                    other_text = other_dict["Term"]
                    # Case-insensitive substring check, and this term must be shorter
                    if (term_text.lower() in other_text.lower() and
                        len(term_text) < len(other_text)):
                        is_substring = True
                        break

            if not is_substring:
                final_terms.append(term_dict)

        return final_terms

    def _second_pass_processing(
        self,
        extracted_terms: List[Dict],
        term_frequencies: Dict[str, int],
        full_text: str
    ) -> List[Dict[str, str]]:
        """
        Second pass: Deduplicate, categorize, detect roles, and build final vocabulary list.

        Args:
            extracted_terms: List of term dictionaries from first pass
            term_frequencies: Dictionary mapping lowercase terms to frequency counts
            full_text: Complete document text for role/relevance detection

        Returns:
            Final vocabulary list with Type, Role/Relevance, and Definition
            Format: [{"Term": str, "Type": str, "Role/Relevance": str, "Definition": str}, ...]
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

            # Determine category (simplified: Person/Place/Medical/Technical)
            category = self._get_category(self.nlp(term)[0], ent_type=ent_type)

            # Skip if category is None (e.g., DATE, TIME entities)
            if category is None:
                continue

            # Detect role/relevance using profession-specific profile
            if category == "Person":
                role_relevance = self.role_profile.detect_person_role(term, full_text)
            elif category == "Place":
                role_relevance = self.role_profile.detect_place_relevance(term, full_text)
            elif category == "Medical":
                role_relevance = "Medical term"
            else:  # Technical
                role_relevance = "Technical term"

            vocabulary.append({
                "Term": term,
                "Type": category,  # Simplified: Person/Place/Medical/Technical
                "Role/Relevance": role_relevance,  # Context-specific relevance
                "Definition": self._get_definition(term, category)  # Only for Medical/Technical
            })
            seen_terms.add(lower_term)

        return vocabulary
