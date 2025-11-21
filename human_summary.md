# LocalScribe - Human Summary

## Project Status
**Phase 2.1 - UI Refactor Complete:** Application UI has been successfully migrated from Qt (PySide6/PyQt6) to **CustomTkinter**. This has resolved all critical, system-level DLL and threading issues, resulting in a stable and functional application.

**Current Branch:** `main`
**Status:** ✅ **MAIN BRANCH: PHASE 3 MERGED** - All critical issues resolved, application stable and production-ready

**Latest Session (2025-11-20 - Vocabulary Extractor Implementation):**
Implemented and tested the core logic for extracting unusual vocabulary, categorizing terms, and providing definitions for court reporters.

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

**Local Development:** Activate the virtual environment: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)

## File Directory

### Documentation Files
- **Project_Specification_LocalScribe_v2.0_FINAL.md** - Complete technical specification for LocalScribe (PRIMARY SOURCE OF TRUTH, 1148 lines)
- **development_log.md** - Timestamped log of all code changes and features (UPDATED with multiprocessing fix)
- **human_summary.md** - This file; high-level status report for human consumption
- **scratchpad.md** - Brainstorming document for future ideas and potential enhancements
- **README.md** - Project overview with installation and usage instructions
- **ONNX_MIGRATION_LOG.md** - Comprehensive technical log of ONNX Runtime migration (historical reference)

### Source Code
- **src/main.py** - Desktop GUI application entry point (uses CustomTkinter).
- **src/cleaner.py** (~700 lines) - Main document processing module with PDF/TXT/RTF extraction, OCR, text cleaning, case number extraction, and progress callbacks
- **src/config.py** - Centralized configuration constants (file paths, limits, settings, model names)
- **src/prompt_config.py** - User-configurable AI prompt parameters loader (singleton pattern)
- **src/prompt_template_manager.py** - Prompt template discovery, loading, validation, and formatting system
- **src/user_preferences.py** - User preferences manager (saves default prompts per model to JSON)
- **src/ai/ollama_model_manager.py** - PRIMARY: Ollama REST API model manager (uses HTTP to communicate with local Ollama service)
- **src/ai/onnx_model_manager.py** - DEPRECATED: ONNX Runtime GenAI model manager (kept for reference, see development_log.md for why replaced)
- **src/ai/model_manager.py** - DEPRECATED: llama-cpp-python model manager (kept for reference only)
- **src/ai/__init__.py** - AI package initialization (exports OllamaModelManager as default ModelManager)
- **src/ui/main_window.py** - Main application window (uses AIWorkerProcess, heartbeat monitoring, prompt dropdown population)
- **src/ui/widgets.py** - Custom widgets including FileReviewTable, AIControlsWidget (with prompt selector/preview), SummaryResultsWidget
- **src/ui/workers.py** - Background workers (multiprocessing-based AIWorkerProcess with preset_id support, QThread-based ProcessingWorker)
- **src/ui/dialogs.py** - Progress dialogs (ModelLoadProgressDialog with timer, SimpleProgressDialog)
- **src/ui/__init__.py** - UI package initialization
- **src/utils/logger.py** - Debug mode logging with performance timing using Timer context manager
- **src/debug_logger.py** - Debug logging utility for troubleshooting
- **src/performance_tracker.py** - Performance tracking for time estimates
- **src/__init__.py** - Package initialization
- **src/utils/__init__.py** - Utils package initialization

### Tests
- **tests/test_cleaner.py** (24 unit tests - ALL PASSING) - Comprehensive test coverage for DocumentCleaner
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

## Phase 1 Accomplishments

### Core Document Processing ✅
✅ Multi-format support: PDF (digital & scanned), TXT, RTF
✅ OCR integration with Tesseract
✅ Dictionary-based confidence scoring for text quality
✅ Smart text cleaning with legal document preservation

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
