# LocalScribe - Human Summary

## Project Status
**Phase 2.1 - UI Refactor Complete** ✅ Application UI successfully migrated to CustomTkinter with all visual and interaction improvements finalized, application stable and production-ready.

**Roadmap Established** ✅ (2025-11-23) 5-phase development roadmap created and documented in scratchpad, aligned with official project specification. Covers document prioritization, parallel processing, system monitoring, model compatibility, and license integration.

**Code Patterns Refined** ✅ (2025-11-25) Session 5 refined code patterns: Reverted Session 4's descriptive variable naming to more Pythonic variable reuse pattern with comprehensive logging. All transformation stages now use single `text` variable with 4-category logging (execution tracking, performance timing, text metrics, error details). Simpler code, better observability, trusts Python's GC. Updated PROJECT_OVERVIEW.md Section 12. All 50 core tests passing.

**UI Bugs Fixed & Vocabulary Workflow Integrated** ✅ (2025-11-26) Session 6 fixed three user-reported GUI bugs: (1) file size rounding inconsistency (KB showing "1.5 KB" vs MB showing "2 MB" — now all units round to integers), (2) model dropdown selection not persisting (selecting second Ollama model would reset to first — now remembers user choice), (3) vocabulary extraction workflow completely missing (after documents processed, app would hang at "Processing complete" with no vocab extraction). Implemented async VocabularyWorker thread, fixed widget reference bug in queue_message_handler (was calling non-existent method on wrong widget), and added automatic spaCy model download. Resolved critical virtual environment PATH issue by using `sys.executable` instead of relying on `python` command resolution.

**Current Branch:** `main`
**Status:** 🔴 **CRITICAL GUI RESPONSIVENESS ISSUE | SESSION 13** - Session 13 (2025-11-28) implemented UI locking, cancel button, batch queue processing, and configurable vocabulary display limits. Fixed missing Path import. **CRITICAL UNRESOLVED ISSUE:** After processing 260-page PDFs, GUI becomes severely unresponsive (window dragging lags, view switching freezes, sometimes blank UI). Multiple optimization attempts helped but insufficient. Documented in scratchpad for next session investigation. User restarting computer to test.

**Latest Session (2025-11-28 Session 13 - GUI Responsiveness Improvements & Critical Issue Discovery):**
Implemented UI locking (slider/checkboxes disabled during processing), red cancel button (stops all workers, restores UI), batch queue processing (10 msgs/cycle to prevent "Not Responding"), configurable vocabulary display limits (150 default, 500 ceiling based on tkinter research). Fixed Path import bug in vocabulary_extractor. **CRITICAL ISSUE:** Large PDF (260 pages) causes severe GUI unresponsiveness even after all optimizations. Symptoms: window drag lag, view switching freeze, blank UI. Hypotheses: memory leak, threads not terminating, UI queue saturation, Treeview corruption, Windows-specific. Next steps: profile memory, verify thread termination, garbage collection, pagination.

**Previous Session (2025-11-28 Session 12 - Development Log Automatic Condensation Policy):**
Established automatic condensation system for development_log.md using entry-count thresholds (not date-based): most recent 5 sessions keep full detail, sessions 6-20 condensed to 50-100 lines, sessions 21+ very condensed (20-30 lines). Updated AI_RULES.md Section 2 with condensation policy and created new Section 11 "End-of-Session Documentation Workflow" with 4-step process, condensation decision tree, and before/after examples. Current file: 894 lines (compliant). Benefits: consistent maintenance (no more ad-hoc "too big" requests), token efficiency, better AI context balance, works for both Claude and Gemini.

**Previous Session (2025-11-27 Sessions 10-11 - Vocabulary Extraction Bug Fixes & Advanced Filtering):**
**Session 10** fixed 5 critical bugs: (1) Common words bypassing filters - added frequency check for single-word NER entities and medical terms, (2) Threshold too low at 75K - increased to 150K, (3) ALL CAPS names mis-categorized - updated regex patterns `[a-z]+` → `[a-zA-Z]+`, (4) Entity fragments - added `_clean_entity_text()` method, (5) Title abbreviations extracted - added `TITLE_ABBREVIATIONS` filter. **Session 11** added 6 advanced improvements: (1) Legal citation filtering (CPLR, Education Law patterns), (2) Legal boilerplate filtering (Verified Answer, Cause of Action), (3) Case citation filtering (X v. Y pattern), (4) Geographic code filtering (ZIP codes), (5) **Deduplication** - smart two-pass algorithm removes "Plaintiff XIANJUN LIANG" if "XIANJUN LIANG" exists, filters partial names, normalizes prefixes, (6) Law firm detection - correctly categorizes firms with ampersands and suffixes. Combined impact: 506 rows → 50-80 rows.

**Previous Session (2025-11-27 Session 9 - Vocabulary Extraction Redesign for Stenographers):**
Completely redesigned vocabulary extraction to serve stenographer workflow needs. **Major architectural change:** Created modular `RoleDetectionProfile` system (`src/vocabulary/role_profiles.py`) enabling profession-specific behavior without core logic changes. Implemented `StenographerProfile` with context-aware pattern matching: detects "plaintiff John Smith" → "Plaintiff", "Dr. Martinez" → "Treating physician", "Lenox Hill Hospital" → "Medical facility". Simplified categories from 7+ to 4 (Person/Place/Medical/Technical). Smart definitions: skip for people/places (stenographers need WHO/WHY, not dictionary meanings), provide for medical/technical terms. Enhanced regex filters for variations (`plaintiff(s)`, `defendants(s)`, possessives). Optimized rarity calculation: O(n) percentile → O(1) cached rank lookup (sorts 333K dataset once). Updated UI column headers: "Category" → "Type", "Relevance to Case" → "Role/Relevance". CSV transformation example: "Dr. Sarah Martinez, Proper Noun (Person), High, N/A" → "Dr. Sarah Martinez, Person, Treating physician, —". Net code: 473 insertions, 615 deletions (-142 lines). All 5 vocabulary tests passing. Future-ready: adding `LawyerProfile` or `ParalegalProfile` requires only 50 lines of pattern definitions.

**Previous Session (2025-11-26 Session 8 Part 5 - Google Word Frequency Dataset Integration):**
Integrated Google's 333K word frequency dataset into vocabulary extraction to eliminate false positives like "plaintiff(s)", "defendant(s)", and other common-word variations. New methods: `_load_frequency_dataset()` (parses tab-separated word\tcount format), `_matches_variation_filter()` (regex-based filtering), `_is_word_rare_enough()` (frequency-based rarity checking), `_sort_by_rarity()` (sorts results: unknown words first, then lowest frequency counts). User-customizable configuration: `VOCABULARY_RARITY_THRESHOLD` (default 75K out of 333K) and `VOCABULARY_SORT_BY_RARITY` (toggle sorting). Extensible variation filters via regex patterns (e.g., `r'^[a-z]+\(s\)$'` for "(s)" variations). Gracefully falls back to WordNet if frequency file missing. All 55 tests passing, zero regressions.

**Previous Session (2025-11-26 Session 8 Part 3 - Prompt Selection UI Refinement):**
Refined prompt selection based on user feedback. The dropdown now shows ALL .txt prompt files equally without any "(Custom)" suffix distinction. Implemented underscore prefix convention: `_template.txt` (skeleton for users to copy) and `_README.txt` (comprehensive guide) are auto-created in user's prompts folder but excluded from dropdown. Renamed quadrant to "Model & Prompt Selection" and updated tooltips to guide users to create custom prompts. README includes quick start, required format, variable placeholders, and tips for effective prompts.

**Previous Session (2025-11-26 Session 8 Part 2 - Prompt Selection UI):**
New "Prompt Style" dropdown in Model Selection quadrant lets users choose between summarization styles. Implemented dual-directory system: built-in prompts ship with app in `config/prompts/` while user prompts persist through updates in `%APPDATA%\LocalScribe\prompts/`. User prompts with same name override built-in. Auto-creates skeleton template (`custom-template.txt`) on first run with instructions and required Phi-3 tokens. Fixed critical bug where model name was incorrectly used as prompt ID.

**Previous Session (2025-11-26 Session 8 Part 1 - System Monitor, Tooltips, Vocabulary Table):**
Three UI enhancements: **(1) System Monitor:** RAM now displays as percentage (51%) instead of GB, CPU and RAM have independent color indicators (CPU green while RAM yellow), both show "!" at 90%+. **(2) Tooltips:** Complete rewrite — now position near mouse cursor (not fixed widget location), smart boundary detection flips tooltip if near screen edge, works correctly after window move/resize/maximize. **(3) Vocabulary Table:** Replaced CSV text display with Excel-like Treeview (frozen headers, scrollable content), added right-click "Exclude this term from future lists" with case-insensitive matching (excluding "New York" also blocks "NEW YORK"). User exclusions stored in `%APPDATA%\LocalScribe\config\user_vocab_exclude.txt`. All 55 tests passing.

**Previous Session (2025-11-26 Session 6 - UI Bug Fixes & Vocabulary Workflow Integration):**
Fixed three critical UI bugs. **Bug #1:** File size rounding inconsistency — KB showed decimals (1.5 KB) while MB showed integers (2 MB). Fixed by unifying all units to use `round(size)`. **Bug #2:** Model dropdown selection wouldn't persist — selecting second model in dropdown would reset to first. Fixed by implementing preference preservation logic in `refresh_status()`. **Bug #3:** Vocabulary extraction workflow completely missing — after document processing completed, app would silently fail to start vocabulary extraction, hanging at "Processing complete". Root causes: (a) `queue_message_handler.py:87` called non-existent `get_output_options()` method on wrong widget (`summary_results`), (b) `en_core_web_sm` spaCy model not installed, (c) subprocess PATH resolution used `python` command instead of venv Python. Fixed all three issues: (a) Changed to direct widget access reading checkbox states from `self.main_window.output_options`, (b) Added `_load_spacy_model()` with auto-download capability, (c) Used `sys.executable` for subprocess to guarantee venv Python. Implemented VocabularyWorker class (background thread with graceful fallback for missing config files), added `_combine_documents()` helper to main window, made vocabulary extractor config files optional. All 3 git commits successful.

**Previous Session (2025-11-24 Session 2 - Code Refactoring, Documentation Cleanup, Bug Fixes & Testing):**
Completed major code quality improvements and documentation consolidation. Refactored main_window.py from 428 → 290 lines (-32%) by extracting two new focused modules: quadrant_builder.py (UI layout, 221 lines) and queue_message_handler.py (async message routing, 156 lines). Consolidated redundant markdown files: deleted DEV_LOG.md, TODO.md, IN_PROGRESS.md, EDUCATION_INTERESTS.md, PREPROCESSING_PROPOSAL.md; fixed AI_RULES.md naming conflicts; merged PREPROCESSING_PROPOSAL into scratchpad (11 files → 6 files, -45% reduction). Fixed critical Unicode encoding bug in debug logger that was crashing application. Discovered and documented HIGH-PRIORITY blocking issue: text extraction produces characters that Ollama cannot process (redacted content ██, control chars, malformed UTF-8). Solution: Add Step 2.5 CharacterSanitizer pipeline before Phase 3 implementation. All code changes tested and verified; 4 git commits made.

**Session 2025-11-22 Improvements:**
1. **Tooltip System Redesign** - Implemented stable 500ms-delay tooltip system with proper event handling, eliminating flickering on all four help icons
2. **Menu Bar Dark Theme** - Changed menu bar from bright white to dark grey (#404040) matching CustomTkinter aesthetic
3. **Header Styling Enhancement** - Enlarged quadrant headers to 16pt bold and centered them for better visual hierarchy
4. **File Persistence** - Fixed issue where files disappeared during processing; they now remain visible with status updates
5. **Layout Reorganization** - Standardized all four quadrants with Row 0 (labels), Row 1 (icons), Row 2+ (content) structure
6. **Smart Tooltip Positioning** - Icons repositioned to top-left of quadrants with tooltips appearing to the right (ensures on-screen visibility)
7. **Consistent Icon Positioning** - All four help icons (📄, 🤖, 📝, ⚙️) now positioned consistently for predictable UX

**CRITICAL BUG FIXES (Session 2025-11-17):**

1. **GUI Crash After Summary Display (Root Cause: Qt Threading Issue):**
   - **Problem:** Application crashed immediately after summary was generated and displayed, with no error message
   - **Root Cause:** `_on_summary_complete()` event handler was updating GUI widgets from AIWorker QThread (non-GUI thread). Qt requires all GUI updates from the main GUI thread.
   - **Solution:** Wrapped all GUI operations in comprehensive try-except with step-by-step logging
   - **Result:** Summaries now display reliably; errors shown gracefully instead of crashing

2. **Performance Logging Failure:**
   - **Problem:** Performance tracker calls were crashing the worker thread
   - **Solution:** Wrapped in try-except so performance logging failures don't crash the application
   - **Result:** Non-critical logging no longer affects core functionality

3. **UI Progress Display Cleanup:**
   - Removed "words so far" from progress indicator (legacy from streaming implementation)
   - Before: "Generating 100-word summary... (0:14 elapsed, 0 words so far)"
   - After: "Generating 100-word summary... (0:14 elapsed)"

**VERIFICATION:**
Created comprehensive test_ollama_workflow.py with 4 automated tests:
- Test 1: Ollama Connection ✓ PASS
- Test 2: Model Availability ✓ PASS (found gemma3:1b)
- Test 3: Prompt Templates ✓ PASS (found 2 presets)
- Test 4: Summary Generation ✓ PASS (171 words in 20.6s)

**Vocabulary Extractor Verification:**
Created tests/test_vocabulary_extractor.py with 5 automated tests:
- test_load_word_list ✓ PASS
- test_is_unusual ✓ PASS
- test_get_category ✓ PASS
- test_get_definition ✓ PASS
- test_extract ✓ PASS

All integration tests passing. **Complete workflow now functional:**
1. Select documents → Processing
2. Choose prompt template
3. Click Generate → Ollama generates summary
4. **Summary displays in results panel**
5. User can copy to clipboard or save to file

**What Works ✅:**
- ✅ **Hierarchical Meta-Summary Generation** - Generates an overall summary from individual document summaries to handle large inputs.
- ✅ **Summary Options UI** - Controls for generating overall (meta) and per-document summaries with configurable lengths.
- ✅ **Vocabulary Extraction UI Integration** - A checkbox to enable CSV export of unusual terms.
- ✅ **Keyboard Shortcut for Generate Summaries** - Ctrl+G now triggers summary generation.
- ✅ **Ollama service integration** with REST API calls
- ✅ **Dynamic model dropdown** populated from Ollama available models
- ✅ **Model pull functionality** - Download new models via UI (qwen2.5:7b, llama3.2:3b, etc.)
- ✅ **Service health check** on startup with platform-specific instructions
- ✅ **Prompt template selection** with dropdown and live preview
- ✅ **Two analytical depth presets** (Factual Summary, Strategic Analysis)
- ✅ **User preferences** - Save default prompt per model
- ✅ **GUI remains fully responsive** during summary generation (no freezing!)
- ✅ **Streaming token display** with real-time "Updated: HH:MM:SS" timestamps
- ✅ **File selection** enables Generate button immediately (no need for "Select All")
- ✅ **File metadata display** shows actual file sizes and page counts
- ✅ **AI generation via Ollama** (qwen2.5:7b-instruct recommended, llama3.2:3b fallback)
- ✅ **Heartbeat monitoring** (warns if worker process stalls)
- ✅ **Comprehensive error handling** with user-friendly messages
- ✅ **Process isolation** (worker crashes don't affect GUI)
- ✅ **Cross-platform stability** (Windows, macOS, Linux - no DLL issues)
- ✅ **Vocabulary Extraction Module** - Extracts unusual terms, categorizes, defines them, and assigns relevance based on category and frequency.

**Issues Resolved This Session (2025-11-16):**
- ✅ **Generate Summary button** - Now enables intuitively after file selection
- ✅ **File size/page display** - Fixed key name mismatch (pages→page_count, size_mb→file_size)
- ⚠️ **Progress dialog responsiveness** - Improved with event loop fix, may need further refinement
- ✅ **Signal delivery** - Fixed checkbox state change signal timing in file table

**Local Development:** Activate the virtual environment: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux)

---

## Development Roadmap (2025-11-23)

**Strategic direction established for Phases 2.2 through 5.** All items are documented in `scratchpad.md` with implementation estimates and technical specifications.

### Immediate Next Steps (Quick Wins - 1 hour each)
1. **Test Larger AI Models** - Pull `llama2:13b` and `mistral:7b` to test summary quality improvement. Hypothesis: 7B-13B models provide substantially better reasoning than 1B models currently in use.

### Planned Development Phases (15-20 hours total)

| Phase | Feature | Time | Status | Spec Section |
|-------|---------|------|--------|--------------|
| 2.2 | Document Prioritization System | 3-4 hrs | Planned | Section 6 |
| 2.5 | Parallel Document Processing | 4-5 hrs | Planned | New |
| 2.6 | System Monitor Widget (CPU/RAM) | 1-2 hrs | Planned | New |
| 2.7 | Model-Aware Prompt Formatting | 1-2 hrs | Planned | New |
| 3 | License Server Integration | 4-6 hrs | Planned | Section 4 |
| 4 | Vocabulary Definitions (Enhanced) | 2-3 hrs | Planned | Section 7.5.2, 8.2 |
| 5 | Advanced Features | TBD | Future | Post-v1.0 |

### Key Architecture Decisions (Locked In)

✅ **Parallel Processing Design:**
- AsyncDocumentProcessor with queue-based job management
- User-controlled CPU allocation: 1/4, 1/2 (default), 3/4 cores
- Only meta-summary is blocking; all individual summaries process asynchronously
- Prevents system overload on shared machines

✅ **System Transparency:**
- Real-time CPU% and RAM display in status bar
- Color-coded: Green (<50%), Yellow (50-75%), Red (75%+)
- Hover tooltip reveals CPU model, core count, clock speeds
- Helps users diagnose bottlenecks and optimize concurrency

✅ **Model Compatibility:**
- All Ollama-downloaded models auto-discovered via `/api/tags`
- New `wrap_prompt_for_model()` detects model type and applies correct instruction format
- Supports Llama, Mistral, Gemma, Neural-Chat, Dolphin, and extensible for new models
- Enables users to freely experiment with different models without code changes

---

## File Directory

### Documentation Files
- **PROJECT_OVERVIEW.md** - Complete technical specification for LocalScribe (PRIMARY SOURCE OF TRUTH, 1148 lines)
- **development_log.md** - Timestamped log of all code changes and features (UPDATED with Session 8 Part 5 Google frequency dataset integration)
- **human_summary.md** - This file; high-level status report for human consumption
- **scratchpad.md** - Brainstorming document for future ideas and potential enhancements
- **README.md** - Project overview with installation and usage instructions
- **ONNX_MIGRATION_LOG.md** - Comprehensive technical log of ONNX Runtime migration (historical reference)

### Data Files
- **Word_rarity-count_1w.txt** - Google word frequency dataset (333,333 words, tab-separated format: word\tfrequency_count) - NEW in Session 8 Part 5

### Source Code
- **src/main.py** - Desktop GUI application entry point (uses CustomTkinter)
- **src/config.py** - Centralized configuration constants (file paths, limits, settings, model names, vocabulary rarity threshold and sorting)
- **src/logging_config.py** - **NEW (Session 7)** Unified logging system (260 lines) - single source of truth for debug_log, info, warning, error, Timer
- **src/debug_logger.py** - Backward compatibility wrapper - re-exports from logging_config.py
- **src/prompt_config.py** - User-configurable AI prompt parameters loader (singleton pattern)
- **src/prompt_template_manager.py** - Prompt template discovery, loading, validation, and formatting system
- **src/user_preferences.py** - User preferences manager (saves default prompts per model to JSON)
- **src/extraction/raw_text_extractor.py** (~700 lines) - Raw text extraction module (Steps 1-2 of pipeline): PDF/TXT/RTF extraction, OCR, basic text normalization, case number extraction, and progress callbacks
- **src/sanitization/character_sanitizer.py** - Character sanitization module (Step 2.5 of pipeline): Unicode normalization, mojibake fix, redaction handling
- **src/vocabulary/** - **NEW (Session 7), MAJOR REFACTOR (Session 9)** Vocabulary extraction package
  - **src/vocabulary/__init__.py** - Package init, exports VocabularyExtractor
  - **src/vocabulary/vocabulary_extractor.py** (600+ lines) - Extracts unusual terms using spaCy NER, NLTK WordNet, Google word frequency dataset with O(1) cached rarity lookups, and **NEW (Session 9)** modular role detection via profiles
  - **src/vocabulary/role_profiles.py** (280 lines) - **NEW (Session 9)** Modular profession-specific role detection system: RoleDetectionProfile base class, StenographerProfile implementation with pattern-based context matching, placeholders for future LawyerProfile/ParalegalProfile
- **src/ai/ollama_model_manager.py** - PRIMARY: Ollama REST API model manager (uses HTTP to communicate with local Ollama service)
- **src/ai/summary_post_processor.py** - **NEW (Session 8 Part 4)** Backend-agnostic summary length enforcement (199 lines) - uses dependency injection to work with any text generation function
- **src/ai/onnx_model_manager.py** - DEPRECATED: ONNX Runtime GenAI model manager (kept for reference)
- **src/ai/model_manager.py** - DEPRECATED: llama-cpp-python model manager (kept for reference only)
- **src/ai/__init__.py** - AI package initialization (exports OllamaModelManager as default ModelManager)
- **src/ui/main_window.py** (295 lines) - Main application window, coordinates orchestrator and message handler
- **src/ui/workflow_orchestrator.py** - **NEW (Session 7)** Workflow logic (180 lines) - decides workflow steps, manages state
- **src/ui/queue_message_handler.py** (210 lines) - Message routing and UI updates only (separation of concerns)
- **src/ui/widgets.py** (209 lines) - Custom widgets: FileReviewTable, ModelSelectionWidget, OutputOptionsWidget
- **src/ui/workers.py** - Background workers (ProcessingWorker, VocabularyWorker, OllamaAIWorkerManager)
- **src/ui/dialogs.py** - Progress dialogs (ModelLoadProgressDialog with timer, SimpleProgressDialog)
- **src/ui/system_monitor.py** - Real-time CPU/RAM display widget with independent color indicators and hover tooltip
- **src/ui/dynamic_output.py** - **UPDATED (Session 8)** Dynamic output display with Excel-like vocabulary Treeview and right-click exclusion menu
- **src/ui/tooltip_helper.py** - **REWRITTEN (Session 8)** Mouse-relative tooltip positioning with boundary detection
- **src/ui/__init__.py** - UI package initialization
- **src/utils/__init__.py** - Utils package initialization, re-exports logging functions
- **src/utils/logger.py** - Backward compatibility wrapper - re-exports from logging_config.py
- **src/utils/text_utils.py** - **NEW (Session 7)** Shared text utilities (55 lines) - combine_document_texts()
- **src/performance_tracker.py** - Performance tracking for time estimates
- **src/__init__.py** - Package initialization

### Tests
- **tests/test_raw_text_extractor.py** (24 unit tests - ALL PASSING) - Comprehensive test coverage for RawTextExtractor (Steps 1-2)
- **tests/sample_docs/test_complaint.txt** - Sample legal document for testing
- **tests/sample_docs/test_motion.rtf** - Sample RTF legal document for testing
- **tests/output/** - Test output directory (gitignored)

### Configuration
- **config/prompt_parameters.json** - User-editable AI settings (word count, temperature, top-p, etc.)
- **config/prompts/phi-3-mini/factual-summary.txt** - Objective fact-focused summary template
- **config/prompts/phi-3-mini/strategic-analysis.txt** - Deep analytical summary template
- **config/user_preferences.json** - User's saved default prompts per model (auto-created)
- **requirements.txt** - Python dependencies including onnxruntime-genai-directml, huggingface-hub, numpy<2.0
- **.gitignore** - Git ignore rules (venv/, cleaned/, *.log, etc.)
- **venv/** - Virtual environment (NOT in git, auto-created by session-start hook)
- **.claude/hooks/session-start.sh** - Auto-setup script (browser only, skips on Windows)
- **.claude/settings.local.json** - Local permissions configuration (not committed)

### Claude Code Browser Environment
- **Session-Start Hook:** Automatically installs Tesseract OCR, creates venv, installs all dependencies, downloads NLTK data
- **Zero Setup:** New browser sessions are instantly ready to run tests and process documents
- **Cached State:** Container caching makes subsequent sessions start in seconds

## Planned Future Directory Structure (v3.0)

When implementing the remaining pipeline steps, the codebase will be reorganized as:

```
src/
├── extraction/           (Steps 1-2: ✅ Implemented)
│   ├── raw_text_extractor.py
│   └── __init__.py
│
├── preprocessing/        (Step 3: Planned)
│   ├── base.py
│   ├── pipeline.py
│   ├── basic/
│   │   └── ocr_error_fixer.py
│   └── smart/
│       ├── line_number_remover.py
│       ├── header_footer_remover.py
│       └── ...
│
├── vocabulary/          (Step 4: Planned)
│   └── text_vocabulary_extractor.py
│
├── chunking/            (Step 5: Refactor from root)
│   └── engine.py
│
├── summarization/       (Step 6: Refactor from root)
│   └── progressive.py
│
└── ai/                  (Model integrations)
    └── ollama_model_manager.py
```

**Current Status:** Steps 1-2 complete in `src/extraction/`. Steps 3-6 will be refactored into this structure in v3.0.

## Phase 1 Accomplishments

### Core Document Processing ✅
✅ Multi-format support: PDF (digital & scanned), TXT, RTF
✅ OCR integration with Tesseract
✅ Dictionary-based confidence scoring for text quality
✅ Smart text normalization with legal document preservation (Step 2)

### Advanced Text Cleaning ✅
✅ De-hyphenation across line breaks
✅ Page number removal (multiple formats)
✅ Legal header preservation (SUPREME COURT, PLAINTIFF, etc.)
✅ Line filtering (removes short/junk lines while keeping important content)
✅ Whitespace normalization

### Legal Document Features ✅
✅ Case number extraction (Federal, NY Index, Docket numbers)
✅ Automatic case number detection and storage in results
✅ Legal keyword recognition for document classification

### Error Handling & UX ✅
✅ Specific error messages (password-protected PDFs, corruption, permissions)
✅ File type validation with helpful format suggestions
✅ Progress callback support for UI integration
✅ Debug mode with performance timing

### Development & Testing ✅
✅ 24 comprehensive unit tests (100% passing)
✅ Command-line interface for standalone use
✅ Session-start hook for Claude Code browser
✅ Complete documentation
✅ All code on GitHub

<h2>Phase 2.1 - UI Refactor Accomplishments</h2>

<h3>Desktop Application ✅</h3>
✅ Refactored main application window to use CustomTkinter
✅ Created a native-style menubar with File and Help dropdowns
✅ File selection dialog is functional

<h3>UI Widgets ✅</h3>
✅ Refactored `FileReviewTable`, `AIControlsWidget`, and `SummaryResultsWidget` to use CustomTkinter components
✅ Integrated the new widgets into the main window layout

<h3>Concurrency ✅</h3>
✅ Refactored background workers to use standard Python `threading` and `queue`
✅ UI remains responsive during background file processing
✅ Progress updates are successfully sent from worker threads to the UI
