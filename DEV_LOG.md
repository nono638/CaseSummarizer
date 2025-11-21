### 2025-11-20 - Phase 3 Merge to Main

*   **Action:** Merged `phase3-enhancements` branch into `main`.
*   **Result:** All Phase 3 features, including Ollama backend integration, critical GUI bug fixes, and multiprocessing architecture, are now integrated into the `main` branch.
*   **Status:** `phase3-enhancements` branch deleted locally and remotely. `main` branch is now up-to-date with all latest features and fixes.

### 2025-11-20 - UI Enhancement: Keyboard Shortcut for Generate Summaries

*   **Action:** Added keyboard shortcut `Ctrl+G` for the "Generate Summaries" action.
*   **Module(s) Modified:** `src/ui/main_window.py`
*   **Benefit:** Improves user experience by providing a quick keyboard-driven way to initiate summary generation.

### 2025-11-20 - Feature: Vocabulary Extractor Module (Phase 1)

*   **Action:** Implemented core logic for vocabulary extraction from legal documents.
    *   Identifies unusual terms (medical, acronyms, proper nouns).
    *   Excludes common legal terminology using a configurable list (`config/legal_exclude.txt`).
    *   Categorizes terms (e.g., "Medical Term", "Proper Noun (Person)", "Acronym", "Technical Term").
    *   Provides definitions using NLTK WordNet (offline).
*   **Module(s) Added/Modified:**
    *   `src/vocabulary_extractor.py` (New module)
    *   `config/legal_exclude.txt` (New file)
    *   `config/medical_terms.txt` (New file)
    *   `requirements.txt` (Added `spacy`, `nltk`)
    *   `pytest.ini` (New file for test configuration)
    *   `tests/test_vocabulary_extractor.py` (New test file)
*   **Verification:** All 5 tests in `tests/test_vocabulary_extractor.py` passed successfully.
*   **Next:** Integration into UI and refining "Relevance to Case" logic.
