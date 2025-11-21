import spacy
import nltk
from nltk.corpus import wordnet
import csv
from collections import defaultdict
import re
import os

class VocabularyExtractor:
    def __init__(self, exclude_list_path, medical_terms_path):
        self.nlp = spacy.load("en_core_web_sm")
        self.exclude_list = self._load_word_list(exclude_list_path)
        self.medical_terms = self._load_word_list(medical_terms_path)

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
        if not os.path.exists(file_path):
            print(f"Warning: Word list file not found at {file_path}. Continuing without it.")
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            return {line.strip().lower() for line in f if line.strip()}

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
        vocabulary = []
        seen_terms = set()

        # Extract named entities first
        for ent in doc.ents:
            # Prioritize multi-word entities if they are proper nouns
            if ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]:
                term_text = ent.text
                if term_text.lower() not in self.exclude_list and term_text.lower() not in seen_terms:
                    # Pass ent.label_ to _is_unusual for proper noun check
                    if self._is_unusual(ent.root, ent_type=ent.label_): # ent.root is a token
                        category = self._get_category(ent.root, ent_type=ent.label_) # Pass ent_type to _get_category
                        if category:
                            vocabulary.append({
                                "Term": term_text,
                                "Category": category,
                                "Relevance to Case": "High", # Placeholder, will be refined
                                "Definition": self._get_definition(term_text)
                            })
                            seen_terms.add(term_text.lower())
        
        # Extract unusual single tokens not already covered by multi-word entities
        for token in doc:
            # Pass token.ent_type_ to _is_unusual for proper noun check
            if self._is_unusual(token, ent_type=token.ent_type_) and token.text.lower() not in seen_terms:
                category = self._get_category(token, ent_type=token.ent_type_) # Pass ent_type_ here too for consistency
                if category:
                    vocabulary.append({
                        "Term": token.text,
                        "Category": category,
                        "Relevance to Case": "Medium", # Placeholder, will be refined
                        "Definition": self._get_definition(token.text)
                    })
                    seen_terms.add(token.text.lower())
        
        return vocabulary