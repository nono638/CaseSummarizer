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

### 2025-11-20 - UI Integration: Vocabulary Extractor

*   **Action:** Integrated `VocabularyExtractor` module into the main application UI.
    *   Added a "Generate Vocabulary List (CSV)" checkbox to the main window.
    *   Modified `process_with_ai` to trigger vocabulary extraction and CSV export if the checkbox is selected.
    *   Added `_save_vocabulary_csv` method to handle CSV file saving.
*   **Module(s) Modified:**
    *   `src/ui/main_window.py`
    *   `src/config.py` (added paths for exclude and medical terms lists)
*   **Next:** Refine "Relevance to Case" logic and implement meta-summary options.

### 2025-11-20 - UI Integration: Summary Options

*   **Action:** Added UI controls for meta-summary and individual summary generation.
    *   Added checkboxes and length input spinboxes to `AIControlsWidget` for "Generate Overall Summary" and "Generate Per-Document Summaries".
    *   Refactored `process_with_ai` to retrieve these settings and delegate to new helper methods (`_generate_meta_summary`, `_generate_individual_summaries`).
    *   Implemented placeholder logic for `_generate_meta_summary` and `_generate_individual_summaries`.
*   **Module(s) Modified:**
    *   `src/ui/main_window.py`
    *   `src/ui/widgets.py`
*   **Next:** Refine "Relevance to Case" logic.
