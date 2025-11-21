import pytest
import os
from pathlib import Path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from src.vocabulary_extractor import VocabularyExtractor

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
    
    # Person
    token_smith = doc[3] # Smith
    ent_smith = [ent for ent in doc.ents if ent.text == "John Smith"][0]
    assert extractor._get_category(token_smith, ent_type=ent_smith.label_) == "Proper Noun (Person)"

    # Organization
    token_mayo = doc[8] # Mayo
    ent_mayo = [ent for ent in doc.ents if ent.text == "Mayo Clinic"][0]
    assert extractor._get_category(token_mayo, ent_type=ent_mayo.label_) == "Proper Noun (Organization)"

    # Medical Term
    token_cardio = doc[5] # cardiologist (will be lowercased in _is_unusual check)
    assert extractor._get_category(token_cardio, ent_type=token_cardio.ent_type_) == "Technical Term" # 'cardiologist' not in dummy medical_terms.txt
    
    # Acronym
    token_ct = doc[14] # CT
    assert extractor._get_category(token_ct, ent_type=token_ct.ent_type_) == "Acronym"

    # Known medical term
    doc2 = extractor.nlp("The patient requires a nephrology consultation.")
    token_nephro = doc2[4] # nephrology
    assert extractor._get_category(token_nephro, ent_type=token_nephro.ent_type_) == "Medical Term"

def test_get_definition(extractor):
    # WordNet definition
    definition = extractor._get_definition("cat")
    assert "feline" in definition.lower() # Check for part of the definition

    # No WordNet definition
    definition_no_def = extractor._get_definition("asdfghjkl")
    assert definition_no_def == "N/A"

def test_extract(extractor):
    test_text = "The plaintiff, Mr. John Doe, presented with cardiomyopathy. He visited Dr. Jane Smith at Mayo Clinic for a CT scan. The court delivered its verdict."
    
    vocabulary = extractor.extract(test_text)
    
    # Expected terms (case-insensitive for comparison) for single occurrence
    expected_terms_single = {
        "john doe": {"Category": "Proper Noun (Person)", "Relevance to Case": "High"},
        "cardiomyopathy": {"Category": "Medical Term", "Relevance to Case": "Medium"},
        "jane smith": {"Category": "Proper Noun (Person)", "Relevance to Case": "High"},
        "mayo clinic": {"Category": "Proper Noun (Organization)", "Relevance to Case": "High"},
        "ct": {"Category": "Acronym", "Relevance to Case": "Medium"},
    }

    found_terms = {item["Term"].lower(): item for item in vocabulary}

    for term, expected_data in expected_terms_single.items():
        assert term in found_terms, f"Term '{term}' not found in extracted vocabulary"
        assert found_terms[term]["Category"] == expected_data["Category"]
        assert found_terms[term]["Relevance to Case"] == expected_data["Relevance to Case"]
        # Definition should not be N/A for known words
        if found_terms[term]["Definition"] == "N/A" and term not in ["ct", "john doe", "jane smith", "mayo clinic"]: # Proper nouns and acronyms might not have WordNet definitions
            pytest.fail(f"Definition for '{term}' should not be N/A")

    # Ensure excluded terms are not present
    assert "plaintiff" not in found_terms
    assert "court" not in found_terms
    assert "verdict" not in found_terms

    # Check that duplicates are handled and relevance is boosted
    test_text_dup = "Cardiomyopathy is a serious condition. The patient had cardiomyopathy. Also, cardiomyopathy can be genetic."
    vocabulary_dup = extractor.extract(test_text_dup)
    
    # Expected for duplicated term: cardiomyopathy
    found_cardiomyopathy = next((item for item in vocabulary_dup if item["Term"].lower() == "cardiomyopathy"), None)
    assert found_cardiomyopathy is not None
    assert found_cardiomyopathy["Category"] == "Medical Term"
    assert found_cardiomyopathy["Relevance to Case"] == "High" # Appears 3 times
    assert found_cardiomyopathy["Definition"] != "N/A" # Should have a definition
    assert sum(1 for item in vocabulary_dup if item["Term"].lower() == "cardiomyopathy") == 1 # Still only one entry
