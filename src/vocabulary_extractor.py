import spacy
import nltk
from nltk.corpus import wordnet
import csv
from collections import defaultdict
import re
import os
from src.debug_logger import debug_log

class VocabularyExtractor:
    def __init__(self, exclude_list_path=None, medical_terms_path=None):
        """
        Initialize the vocabulary extractor.

        Args:
            exclude_list_path: Path to legal exclude words list (optional)
            medical_terms_path: Path to medical terms list (optional)

        If paths are None or files don't exist, uses empty lists (increases false positives).
        """
        self.nlp = spacy.load("en_core_web_sm")
        self.exclude_list = self._load_word_list(exclude_list_path) if exclude_list_path else set()
        self.medical_terms = self._load_word_list(medical_terms_path) if medical_terms_path else set()

        # Download NLTK data if not already present
        try:
            nltk.data.find('corpora/wordnet')
        except LookupError:
            nltk.download('wordnet')
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')

    def _load_word_list(self, file_path):
        """Loads a list of words from a line-separated text file."""
        if file_path is None:
            debug_log(f"[VOCAB] Word list not specified. Using empty list (increases false positives).")
            return set()
        if not os.path.exists(file_path):
            debug_log(f"[VOCAB] Word list file not found at {file_path}. Using empty list (increases false positives).")
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            word_list = {line.strip().lower() for line in f if line.strip()}
            debug_log(f"[VOCAB] Loaded {len(word_list)} words from {file_path}")
            return word_list

    def _is_unusual(self, token, ent_type=None):
        if not token.is_alpha or token.is_space or token.is_punct or token.is_digit:
            return False
        
        lower_text = token.text.lower()
        if lower_text in self.exclude_list:
            return False
        
        # If it's a known named entity (Person, Org, Loc), it's unusual
        if ent_type in ["PERSON", "ORG", "GPE", "LOC"]:
            return True

        # Medical terms and acronyms are always considered unusual
        if lower_text in self.medical_terms:
            return True
        if re.fullmatch(r'[A-Z]{2,}', token.text): # Check for acronyms
            return True

        # If it's found in WordNet, it's a common English word, so not unusual in general sense
        if wordnet.synsets(lower_text):
            return False 

        return True # Otherwise, consider it unusual (e.g., very rare words not caught by other rules)

    def _get_category(self, token, ent_type): # Changed ent to ent_type
        # Check for acronyms (all caps, 2+ characters)
        if re.fullmatch(r'[A-Z]{2,}', token.text):
            return "Acronym"

        lower_text = token.text.lower()
        if lower_text in self.medical_terms:
            return "Medical Term"

        if ent_type: # ent_type is now always a string
            if ent_type in ["PERSON"]:
                return "Proper Noun (Person)"
            elif ent_type in ["ORG"]:
                return "Proper Noun (Organization)"
            elif ent_type in ["GPE", "LOC"]:
                return "Proper Noun (Location)"
            elif ent_type in ["DATE", "TIME", "MONEY", "PERCENT"]: # Exclude common entities
                return None
        
        return "Technical Term" # Default for other unusual words

    def _get_definition(self, term):
        """Gets the definition of a term using WordNet."""
        synsets = wordnet.synsets(term)
        if synsets:
            # Return the definition of the first synset
            return synsets[0].definition()
        return "N/A" # Definition not found offline

    def extract(self, text):
        """
        Extracts unusual vocabulary, categorizes, and provides definitions.
        """
        doc = self.nlp(text)
        
        extracted_terms_prelim = [] # To store (term_text, category, frequency_key, ent_type_for_category)
        term_frequencies = defaultdict(int)

        # First pass: Extract all potential terms and count their frequencies
        # Extract named entities first
        for ent in doc.ents:
            # Prioritize multi-word entities if they are proper nouns
            if ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]:
                term_text = ent.text
                if term_text.lower() not in self.exclude_list:
                    term_frequencies[term_text.lower()] += 1
                    extracted_terms_prelim.append({
                        "Term": term_text,
                        "ent_type": ent.label_, # Use ent.label_ for category in second pass
                        "frequency_key": term_text.lower() # Key for frequency counting
                    })
        
        # Extract unusual single tokens not already covered by multi-word entities
        for token in doc:
            if self._is_unusual(token, ent_type=token.ent_type_):
                term_text = token.text
                
                # Check if this token is already part of a multi-word entity extracted
                is_part_of_entity = False
                for ent in doc.ents:
                    if ent.start <= token.i < ent.end and ent.text.lower() in term_frequencies:
                        is_part_of_entity = True
                        break
                
                if not is_part_of_entity and term_text.lower() not in self.exclude_list:
                    term_frequencies[term_text.lower()] += 1
                    extracted_terms_prelim.append({
                        "Term": term_text,
                        "ent_type": token.ent_type_, # Use token.ent_type_ for category in second pass
                        "frequency_key": term_text.lower()
                    })

        vocabulary = []
        seen_terms_final = set()

        # Second pass: Process unique terms, assign relevance, and definitions
        for item in extracted_terms_prelim:
            term = item["Term"]
            lower_term = term.lower()
            ent_type_for_category = item["ent_type"]
            
            if lower_term in seen_terms_final:
                continue # Skip duplicates that might arise from different extraction paths

            # Determine category based on new _get_category which now expects ent_type as string
            category = self._get_category(self.nlp(term)[0], ent_type=ent_type_for_category) 
            
            # Skip if category is None (e.g., DATE, TIME entities)
            if category is None:
                continue

            frequency = term_frequencies[lower_term]
            relevance = "Low" # Default

            if category in ["Proper Noun (Person)", "Proper Noun (Organization)", "Proper Noun (Location)"]:
                relevance = "High"
                if frequency > 1: # Boost proper nouns if they appear multiple times
                    relevance = "Very High"
            elif category == "Medical Term":
                relevance = "Medium"
                if frequency >= 2: # Appears more than once
                    relevance = "High"
            elif category == "Acronym":
                relevance = "Medium"
                if frequency >= 2: # Appears more than once
                    relevance = "High"
            elif category == "Technical Term":
                relevance = "Low"
                if frequency >= 3: # Appears multiple times
                    relevance = "Medium"

            vocabulary.append({
                "Term": term,
                "Category": category,
                "Relevance to Case": relevance,
                "Definition": self._get_definition(term)
            })
            seen_terms_final.add(lower_term)
        
        return vocabulary
