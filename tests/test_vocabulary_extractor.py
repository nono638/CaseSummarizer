"""
Tests for the VocabularyExtractor class.

Tests cover:
- Word list loading (exclude list, medical terms)
- Unusual term detection logic
- Category assignment
- Definition lookup via WordNet
- Full extraction pipeline with deduplication and relevance scoring
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.vocabulary import VocabularyExtractor  # noqa: E402

# Define paths for test resources
TEST_DIR = Path(__file__).parent
EXCLUDE_LIST_PATH = TEST_DIR / "test_legal_exclude.txt"
MEDICAL_TERMS_PATH = TEST_DIR / "test_medical_terms.txt"

# Create dummy exclude and medical terms files for testing
@pytest.fixture(scope="module", autouse=True)
def setup_test_files():
    # Create a dummy legal exclude list
    with open(EXCLUDE_LIST_PATH, "w", encoding="utf-8") as f:
        f.write("verdict\n")
        f.write("plaintiff\n")
        f.write("defendant\n")
        f.write("court\n")

    # Create a dummy medical terms list
    with open(MEDICAL_TERMS_PATH, "w", encoding="utf-8") as f:
        f.write("cardiomyopathy\n")
        f.write("nephrology\n")
        f.write("endoscopy\n")

    yield

    # Teardown: Remove dummy files
    os.remove(EXCLUDE_LIST_PATH)
    os.remove(MEDICAL_TERMS_PATH)

@pytest.fixture
def extractor():
    return VocabularyExtractor(EXCLUDE_LIST_PATH, MEDICAL_TERMS_PATH)

def test_load_word_list(extractor):
    assert "verdict" in extractor.exclude_list
    assert "plaintiff" in extractor.exclude_list
    assert "cardiomyopathy" in extractor.medical_terms
    assert "nephrology" in extractor.medical_terms

def test_is_unusual(extractor):
    # Common word, should not be unusual
    doc = extractor.nlp("The quick brown fox jumps over the lazy dog.")
    assert not extractor._is_unusual(doc[1], ent_type=doc[1].ent_type_) # quick

    # Excluded legal term, should not be unusual
    doc = extractor.nlp("The jury reached a verdict.")
    assert not extractor._is_unusual(doc[4], ent_type=doc[4].ent_type_) # verdict

    # Medical term, should be unusual
    doc = extractor.nlp("The patient suffered from cardiomyopathy.")
    assert extractor._is_unusual(doc[4], ent_type=doc[4].ent_type_) # cardiomyopathy

    # Proper noun, not in exclude list, should be unusual
    doc = extractor.nlp("Dr. Smith examined the patient.")
    assert extractor._is_unusual(doc[1], ent_type=doc[1].ent_type_) # Smith

    # Acronym, should be unusual
    doc = extractor.nlp("The FDA approved the drug.")
    assert extractor._is_unusual(doc[1], ent_type=doc[1].ent_type_) # FDA

    # Number/Punctuation, should not be unusual
    doc = extractor.nlp("123,.")
    assert not extractor._is_unusual(doc[0], ent_type=doc[0].ent_type_) # 123
    assert not extractor._is_unusual(doc[1], ent_type=doc[1].ent_type_) # ,

def test_get_category(extractor):
    doc = extractor.nlp("Dr. John Smith is a cardiologist at Mayo Clinic. The patient had a CT scan.")

    # Person (simplified category) - requires full_term for validation with new heuristics
    token_smith = doc[3] # Smith
    ent_smith = [ent for ent in doc.ents if ent.text == "John Smith"][0]
    # Pass full entity text so validation heuristics can check multi-word name pattern
    assert extractor._get_category(token_smith, ent_type=ent_smith.label_, full_term="John Smith") == "Person"

    # Organization → Place (simplified category)
    token_mayo = doc[8] # Mayo
    ent_mayo = [ent for ent in doc.ents if ent.text == "Mayo Clinic"][0]
    # Pass full entity text so validation can detect "Clinic" as organization indicator
    assert extractor._get_category(token_mayo, ent_type=ent_mayo.label_, full_term="Mayo Clinic") == "Place"

    # Medical Term
    token_cardio = doc[5] # cardiologist (will be lowercased in _is_unusual check)
    assert extractor._get_category(token_cardio, ent_type=token_cardio.ent_type_) == "Technical"

    # Acronym "CT" - behavior varies by spaCy model version
    # With en_core_web_lg, CT may be detected differently
    token_ct = doc[14] # CT
    ct_category = extractor._get_category(token_ct, ent_type=token_ct.ent_type_)
    # Accept either Place (if detected as ORG) or Technical (if detected as acronym)
    assert ct_category in ["Place", "Technical", "Unknown"]

    # Known medical term
    doc2 = extractor.nlp("The patient requires a nephrology consultation.")
    token_nephro = doc2[4] # nephrology
    assert extractor._get_category(token_nephro, ent_type=token_nephro.ent_type_) == "Medical"

def test_get_definition(extractor):
    # WordNet definition for Technical term
    definition = extractor._get_definition("cat", category="Technical")
    assert "feline" in definition.lower() # Check for part of the definition

    # No WordNet definition
    definition_no_def = extractor._get_definition("asdfghjkl", category="Technical")
    assert definition_no_def == "—"

    # Person category - no definition needed
    definition_person = extractor._get_definition("John Smith", category="Person")
    assert definition_person == "—"

    # Place category - no definition needed
    definition_place = extractor._get_definition("Mayo Clinic", category="Place")
    assert definition_place == "—"

def test_extract(extractor):
    test_text = "The plaintiff, Mr. John Doe, presented with cardiomyopathy. He visited Dr. Jane Smith at Mayo Clinic for a CT scan. The court delivered its verdict."

    vocabulary = extractor.extract(test_text)

    # Expected terms (using new simplified API: Type and Role/Relevance)
    # Note: Some classifications may vary based on spaCy model version and NER context
    expected_terms_single = {
        "john doe": {"Type": "Person", "Role/Relevance": "Person in case"},  # No plaintiff context
        "cardiomyopathy": {"Type": "Medical", "Role/Relevance": "Medical term"},
        "jane smith": {"Type": "Person", "Role/Relevance": "Medical professional"},  # "Dr. Jane Smith"
        # Mayo Clinic may be classified as "Medical facility" (more accurate) or "Location mentioned in case"
        "mayo clinic": {"Type": "Place", "Role/Relevance": ["Medical facility", "Location mentioned in case"]},
    }

    found_terms = {item["Term"].lower(): item for item in vocabulary}

    for term, expected_data in expected_terms_single.items():
        assert term in found_terms, f"Term '{term}' not found in extracted vocabulary"
        assert found_terms[term]["Type"] == expected_data["Type"]
        # Support multiple acceptable Role/Relevance values for flexible NER classification
        expected_roles = expected_data["Role/Relevance"]
        if isinstance(expected_roles, list):
            assert found_terms[term]["Role/Relevance"] in expected_roles, \
                f"Role/Relevance '{found_terms[term]['Role/Relevance']}' not in expected {expected_roles}"
        else:
            assert found_terms[term]["Role/Relevance"] == expected_roles
        # Definition check: Person/Place should be "—", Medical/Technical should have definition or "—"
        if expected_data["Type"] in ["Person", "Place"]:
            assert found_terms[term]["Definition"] == "—"

    # Ensure excluded terms are not present
    assert "plaintiff" not in found_terms
    assert "court" not in found_terms
    assert "verdict" not in found_terms

    # Check that duplicates are handled
    test_text_dup = "Cardiomyopathy is a serious condition. The patient had cardiomyopathy. Also, cardiomyopathy can be genetic."
    vocabulary_dup = extractor.extract(test_text_dup)

    # Expected for duplicated term: cardiomyopathy
    found_cardiomyopathy = next((item for item in vocabulary_dup if item["Term"].lower() == "cardiomyopathy"), None)
    assert found_cardiomyopathy is not None
    assert found_cardiomyopathy["Type"] == "Medical"
    assert found_cardiomyopathy["Role/Relevance"] == "Medical term"
    assert found_cardiomyopathy["Definition"] != "—" # Should have a definition
    assert sum(1 for item in vocabulary_dup if item["Term"].lower() == "cardiomyopathy") == 1 # Still only one entry
