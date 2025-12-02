# Development Log

## Session 34 - Project Root Cleanup (2025-12-01)

**Objective:** Organize project root directory - move files to proper directories, clean up artifacts, and improve project structure.

### Part 1: Test File Cleanup

**Problem:** 8 test files in project root (unclear status, cluttering root)

**Solution:**
1. Deleted 2 orphaned ONNX test files (deprecated backend):
   - `test_onnx_simple.py`
   - `test_phi3_summary.py`

2. Created `tests/manual/` for 6 integration tests requiring Ollama:
   - `test_debug_mode.py`
   - `test_model_generation.py`
   - `test_model_quick.py`
   - `test_ollama_workflow.py`
   - `test_prompts.py`
   - `test_slider_config.py`

3. Created `tests/manual/README.md` documenting manual test procedures

### Part 2: Root Directory Organization

**Files Moved:**

| From | To | Code Updates |
|------|-----|--------------|
| `check_spacy.py` | `scripts/check_spacy.py` | None |
| `download_onnx_models.py` | `scripts/download_onnx_models.py` | None |
| `test_simple_case.txt` | `tests/sample_docs/test_simple_case.txt` | 1 file |
| `Word_rarity-count_1w.txt` | `data/frequency/Word_rarity-count_1w.txt` | 1 file |

**Code Path Updates:**
- `src/config.py:173` - Word frequency file path updated
- `tests/manual/test_ollama_workflow.py:87` - Test data path updated

**Files Created:**
- `scripts/README.md` - Documents utility scripts

**Configuration Updates:**
- `.gitignore` - Added `debug_flow.txt`, `generated_summary.txt`, `nul` (Windows artifact)
- `.gitignore` - Added exception for `!data/frequency/Word_rarity-count_1w.txt`

### Pattern: Project Root Organization

```
CaseSummarizer/
├── .gitignore, pytest.ini, ruff.toml, requirements.txt  # Config
├── README.md, ARCHITECTURE.md, TODO.md, etc.            # Docs
├── src/                    # Source code
├── tests/                  # Tests (unit + manual + sample_docs)
├── config/                 # Prompts and settings
├── data/                   # Data files (word frequencies)
└── scripts/                # Development utilities
```

Only essential config and docs in root - all code and data in directories.

### User Testing Note

Tested application workflow. Confirmed that the two-phase workflow is working correctly:
1. **Phase 1:** Add Files → extracts text (timer runs during extraction)
2. **Phase 2:** Perform Tasks → runs Q&A/Vocabulary/Summary (timer runs during tasks)

Timer correctly stops after each phase completes.

---

## Session 33 - Codebase Organization & Cleanup (2025-12-01)

**Objective:** Review and improve codebase organization, fix naming inconsistencies, and ensure documentation is up to date.

### Phase 1: Critical Cleanup

Deleted orphaned/obsolete files:
- `src/1_ingestion/` - Empty directory from failed numeric prefix attempt
- `src/vocabulary/vocabulary_extractor_backup.py` - Stale backup file
- Duplicate `SettingsDialog` class from `src/ui/dialogs.py` (newer version in `src/ui/settings/`)
- 15 `.tmp.*` temporary files

### Phase 2: Logging Standardization

Updated `src/extraction/raw_text_extractor.py` to use canonical logging import:
- Old: `from src.utils import Timer, debug, error, info, warning`
- New: `from src.logging_config import Timer, debug, error, info, warning`

The backward-compat wrapper in `src/utils/logger.py` remains for any external code.

### Phase 3: Created `src/prompting/` Package

Consolidated 4 orphan prompt-related files from `src/` root into a proper package:

| Old Location | New Location |
|--------------|--------------|
| `src/prompt_adapters.py` | `src/prompting/adapters.py` |
| `src/prompt_focus_extractor.py` | `src/prompting/focus_extractor.py` |
| `src/prompt_template_manager.py` | `src/prompting/template_manager.py` |
| `src/prompt_config.py` | `src/prompting/config.py` |

Created unified facade API in `src/prompting/__init__.py`:
```python
from src.prompting import (
    PromptTemplateManager, AIFocusExtractor, MultiDocPromptAdapter,
    PromptConfig, get_prompt_config,
)
```

Updated all consumers to use new import paths:
- `src/ai/ollama_model_manager.py`
- `src/ai/summary_post_processor.py`
- `src/summarization/document_summarizer.py`
- `src/summarization/multi_document_orchestrator.py`
- `src/ui/main_window.py`
- `src/ui/workers.py`
- Test files

### Phase 4: UI Code Splitting

**4.1 - main_window.py refactored:**
- Created `src/ui/window_layout.py` with `WindowLayoutMixin`
- Extracted 6 UI creation methods (~260 lines) into the mixin
- `MainWindow` now inherits from `WindowLayoutMixin, ctk.CTk`
- Clean separation: layout code in mixin, business logic in main_window.py

**4.2 - workers.py assessed:**
- Reviewed `workers.py` (651 lines) - under 1000-line threshold
- 5 well-organized, cohesive worker classes (~75-170 lines each)
- Decision: No split needed - file is appropriately sized

### Pattern: Mixin for Layout Separation

```python
# window_layout.py
class WindowLayoutMixin:
    def _create_header(self): ...
    def _create_main_panels(self): ...
    def _create_status_bar(self): ...

# main_window.py
class MainWindow(WindowLayoutMixin, ctk.CTk):
    # Business logic only
```

This pattern separates visual layout from event handling/business logic.

### Files Changed

**Created:**
- `src/prompting/__init__.py` - Unified prompting API
- `src/prompting/adapters.py` - Stage-specific prompt generation
- `src/prompting/focus_extractor.py` - AI focus extraction
- `src/prompting/template_manager.py` - Template loading/management
- `src/prompting/config.py` - Prompt parameters
- `src/ui/window_layout.py` - UI layout mixin

**Deleted:**
- `src/1_ingestion/` (empty directory)
- `src/vocabulary/vocabulary_extractor_backup.py`
- `src/prompt_adapters.py`
- `src/prompt_focus_extractor.py`
- `src/prompt_template_manager.py`
- `src/prompt_config.py`
- Old `SettingsDialog` in `src/ui/dialogs.py`

---

## Session 32 - Unified Package APIs & Architecture Docs (2025-12-01)

**Objective:** Reorganize codebase to better match program flow (Input → Vocabulary → Q&A → Summaries) through unified package APIs rather than file moves.

### Problem Solved

User found code hard to follow because Q&A functionality was split across 3 packages (`qa/`, `vector_store/`, `retrieval/`). Rather than physically moving files (which would require 80+ import changes), we created **unified facade APIs**.

### Unified Q&A API (`src/qa/__init__.py`)

Everything Q&A-related is now importable from `src.qa`:

```python
from src.qa import (
    # Orchestration
    QAOrchestrator, QAResult, AnswerGenerator, AnswerMode,
    # Storage
    VectorStoreBuilder, QARetriever, QuestionFlowManager,
    # Retrieval
    HybridRetriever, ChunkMerger, BaseRetrievalAlgorithm,
)
```

The package re-exports from `src.vector_store` and `src.retrieval`, providing a single entry point.

### Unified Summarization API (`src/summarization/__init__.py`)

All summarization functionality accessible from `src.summarization`:

```python
from src.summarization import (
    ProgressiveSummarizer, ChunkingEngine, Chunk,  # Core
    MultiDocumentOrchestrator, MultiDocumentSummaryResult,  # Multi-doc
)
```

Orphan files (`progressive_summarizer.py`, `chunking_engine.py`) are re-exported without physical move.

### Architecture Documentation Updates

Updated `ARCHITECTURE.md` with:
- New Mermaid diagram showing hybrid retrieval architecture
- Hybrid retrieval section explaining BM25+/FAISS combination
- File directory updated with retrieval package entries
- Unified API documentation

### Note on Numeric Directory Prefixes

Initial plan was to use numbered prefixes (`1_ingestion/`, `2_vocabulary/`) for visual program flow, but **Python package names cannot start with digits**. Abandoned this approach in favor of unified APIs.

### Test Results

- **224 tests passing**
- Pre-existing UI test issue with `test_ui_startup.py` excluded (unrelated)

---

## Session 31 - Hybrid BM25+ Retrieval System (2025-12-01)

**Objective:** Replace FAISS-only Q&A retrieval with a hybrid BM25+ / FAISS system to fix "no information found" results. The semantic-only approach was failing because the embedding model wasn't trained on legal terminology.

### Architecture

Created a new `src/retrieval/` package mirroring the vocabulary extraction pattern:

| Component | Location | Purpose |
|-----------|----------|---------|
| `BaseRetrievalAlgorithm` | `src/retrieval/base.py` | ABC for all retrieval algorithms |
| `BM25PlusRetriever` | `src/retrieval/algorithms/bm25_plus.py` | Lexical search with BM25+ scoring |
| `FAISSRetriever` | `src/retrieval/algorithms/faiss_semantic.py` | Semantic search with embeddings |
| `ChunkMerger` | `src/retrieval/chunk_merger.py` | Weighted result combination |
| `HybridRetriever` | `src/retrieval/hybrid_retriever.py` | Coordinates multiple algorithms |

### Why BM25+ Over Pure Semantic Search

- **Legal language is precise** - exact terms matter ("plaintiff" means plaintiff)
- **Embedding model not trained on legal text** - `all-MiniLM-L6-v2` doesn't understand legal terminology
- **BM25+ scores are more reliable** - deterministic, no neural model needed
- **Future ML integration** - same pattern as vocabulary extraction allows user preference learning

### Algorithm Weights (from config.py)

```python
RETRIEVAL_ALGORITHM_WEIGHTS = {
    "BM25+": 1.0,   # Primary - exact term matching
    "FAISS": 0.5,   # Secondary - semantic can help but less reliable
}
RETRIEVAL_MIN_SCORE = 0.1  # Lower than before (was 0.5)
```

### Key Changes

- **New package:** `src/retrieval/` with 6 new files
- **Refactored:** `src/vector_store/qa_retriever.py` now uses HybridRetriever internally
- **Config:** Added `RETRIEVAL_*` settings to `src/config.py`
- **Dependency:** Added `rank-bm25>=0.2.2` to requirements.txt
- **Tests:** Added 17 new tests in `tests/test_hybrid_retrieval.py`

### Test Results

- **224 tests passing** (207 existing + 17 new hybrid retrieval tests)
- Pre-existing UI test issue with `test_ui_startup.py` (unrelated to this session)

---

## Session 30 - Q&A/Vocabulary Integration Fixes (2025-12-01)

**Objective:** Wire up the Q&A and vocabulary systems to the new CustomTkinter UI and fix integration bugs.

### Fixed Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| UI freeze after processing | HuggingFaceEmbeddings loading blocked main thread | Moved to background `threading.Thread` |
| Placeholder Q&A code | `_start_qa_task()` was using fake QAResult dicts | Wired up real QAWorker with proper vector store |
| Vocabulary not in dropdown | `if self._outputs.get("key"):` returned False for empty `[]` | Changed to `is not None` check |
| Dropdown labels unclear | No indication of result count | Added counts: "Rare Word List (N terms)", "Q&A Results (N)" |

### Code Changes

**`src/ui/main_window.py`:**
- Added imports: `QAWorker`, `VectorStoreBuilder`
- Added Q&A infrastructure: `_embeddings`, `_vector_store_path`, `_qa_results`
- Added debug logging to `_start_vocabulary_extraction()`
- Rewrote `_start_qa_task()` with background thread for embeddings loading
- Added `_qa_init_complete()`, `_poll_qa_queue()`, `_on_qa_complete()` methods
- Updated `_ask_followup()` to use real QAOrchestrator

**`src/ui/dynamic_output.py`:**
- Changed `_refresh_dropdown()` truthiness checks to `is not None`
- Added item counts to dropdown labels
- Updated `_on_dropdown_change()` to use `startswith()` matching

### Known Issues (documented in TODO.md)

- 🔴 Vocabulary returns 0 terms (`combine_document_texts` may return empty)
- 🔴 Q&A answers all say "no information found" (relevance scores near 0 or negative)
- 🟡 Need to switch from FAISS cosine to BM25+ for better retrieval
- 🟡 Corpus name validation needed (prevent invalid filesystem characters)

---

## Session 29 - Q&A-First UI Pivot + Multi-Corpus Architecture (2025-11-30)

**Objective:** Strategic pivot from summarization-first to Q&A-first tool. Complete UI restructure with multi-corpus management system.

### Strategic Changes

The application has pivoted from a summarization-first tool to a Q&A-first document analysis tool. Key reasons:
- Court reporters need quick case familiarization (30+ minute summaries are impractical)
- Q&A results serve as handoff documents for colleagues
- Corpus-based vocabulary requires user's own transcripts to identify what's "unusual"

### New Components Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/vocabulary/corpus_registry.py` | 415 | Multi-corpus management with JSON registry |
| `src/ui/corpus_dialog.py` | 785 | Full-featured corpus management dialog |
| `src/ui/main_window.py` | 765 | Complete CustomTkinter rewrite with two-panel layout |

### Main Window Restructure

Migrated from PySide6 to CustomTkinter with new two-panel layout:
- **Header:** App title + Corpus dropdown + Manage button + Settings button
- **Warning Banner:** Shown when no corpus configured
- **Left Panel:** Session Documents list + Task checkboxes + "Perform N Tasks" button
- **Right Panel:** Results display with output selector + Follow-up input
- **Status Bar:** Status text + Corpus info + Processing timer

### Multi-Corpus Features

1. **CorpusRegistry:** Manages multiple named corpora (Criminal, Civil, etc.)
2. **Preprocessing:** `_preprocessed.txt` suffix for cached extracted text
3. **UI Integration:** Corpus dropdown in header, Manage button opens full dialog
4. **Persistence:** Active corpus stored in user preferences

### Corpus Dialog Features

- Educational header explaining what a corpus is
- BM25 Wikipedia link for curious users
- Create, delete, combine corpora
- Add files with immediate preprocessing
- View preprocessing status (✓ Ready / ⏳ Pending)
- Open folder in system explorer

### Task Workflow Changes

- **Q&A (default ON):** Fast case familiarization
- **Vocabulary (default ON):** Uses corpus for BM25
- **Summary (default OFF):** Warning dialog about 30+ minute processing

---

## Session 28 - Q&A Results Display Bug Fix (2025-11-30)

**Objective:** Fix Q&A results not appearing in the UI despite status showing "14 questions answered."

### Root Cause

The Q&A message handlers in [queue_message_handler.py](src/ui/queue_message_handler.py) were referencing `self.main_window.dynamic_output`, but the actual widget attribute is `self.main_window.summary_results`. This attribute name mismatch prevented Q&A results from reaching the display widget.

### Fix Applied

| File | Line | Change |
|------|------|--------|
| `src/ui/queue_message_handler.py` | 380-381 | `dynamic_output` → `summary_results` |
| `src/ui/queue_message_handler.py` | 400-401 | `dynamic_output` → `summary_results` |

### Verification

- ✅ All 207 tests pass
- ✅ All Q&A module imports work correctly
- ✅ 20 Q&A-specific tests pass

### What Now Works

- Q&A results appear in "Q&A Results" dropdown option
- QAPanel displays questions and answers
- Follow-up questions update the display correctly

---

## Session 27 - Q&A Panel Feature with Vector Search (2025-11-30)

**Objective:** Implement complete Q&A UI leveraging the FAISS vector search infrastructure (Session 24).

### Architecture

| File | Lines | Purpose |
|------|-------|---------|
| `src/qa/__init__.py` | 25 | Package exports |
| `src/qa/qa_orchestrator.py` | 210 | Coordinates Q&A: question loading, vector search, answer generation |
| `src/qa/answer_generator.py` | 250 | Two modes: extraction (fast) vs Ollama (AI-synthesized) |
| `src/ui/qa_panel.py` | 420 | Plain text Q&A display with toggle list, follow-up input |
| `src/ui/qa_question_editor.py` | 380 | GUI for editing default questions (YAML) |
| `src/ui/workers.py` | +115 | QAWorker for background processing |
| `tests/test_qa_orchestrator.py` | 280 | 20 tests for Q&A system |

### Key Features

1. **Dual Answer Modes:** Extraction (keyword matching, fast) vs Ollama (AI synthesis)
2. **Q&A Panel UI:** Scrollable display, checkbox toggles for export, follow-up input
3. **Question Editor:** Add/Edit/Delete/Reorder questions, saves to YAML
4. **Settings Integration:** New "Q&A" tab with answer mode and auto-run options

---

## Session 26 - BM25 Corpus-Based Vocabulary Extraction (2025-11-30)

**Objective:** Add BM25 as third vocabulary algorithm identifying terms unusual compared to user's corpus.

### Implementation

- `src/vocabulary/corpus_manager.py` (430 lines): Corpus folder, IDF index, caching
- `src/vocabulary/algorithms/bm25_algorithm.py` (210 lines): BM25 scoring
- Auto-enables when corpus has ≥5 documents in `%APPDATA%/LocalScribe/corpus/`
- Algorithm weights: NER (1.0), BM25 (0.8), RAKE (0.7)
- 20 new tests pass; full suite: 187 tests

---

## Session 25 - Multi-Algorithm Vocabulary with ML Feedback Learning (2025-11-30)

**Objective:** Extensible multi-algorithm vocabulary extraction with user feedback learning.

### Architecture Refactor

Refactored monolithic `vocabulary_extractor.py` (1336→580 lines, 57% reduction):

| File | Purpose |
|------|---------|
| `src/vocabulary/algorithms/base.py` | ABC, CandidateTerm dataclass |
| `src/vocabulary/algorithms/ner_algorithm.py` | spaCy NER extraction |
| `src/vocabulary/algorithms/rake_algorithm.py` | RAKE keyword extraction |
| `src/vocabulary/result_merger.py` | Weighted confidence combination |
| `src/vocabulary/feedback_manager.py` | CSV-based feedback storage |
| `src/vocabulary/meta_learner.py` | Logistic regression for preference learning |

### ML Feedback System

- 👍/👎 columns in vocabulary table for user feedback
- Features: quality_score, frequencies, algorithm flags, type one-hot
- Training threshold: 30 samples minimum, retrain every 10 new samples
- New dependencies: `rake-nltk`, `scikit-learn`

---

## Session 24 - Q&A Infrastructure with FAISS Vector Search (2025-11-30)

**Objective:** RAG-based Q&A for legal documents with source citations.

### Implementation

- Chose FAISS over ChromaDB (file-based, no database config needed)
- `src/vector_store/vector_store_builder.py`: Creates FAISS indexes
- `src/vector_store/qa_retriever.py`: Retrieves context for questions
- `config/qa_questions.yaml`: 14 branching questions for case analysis
- Vector store created automatically after extraction, saved to `%APPDATA%/LocalScribe/vector_stores/`
- Uses `all-MiniLM-L6-v2` embeddings, 500-char chunks with 50 overlap

---

## Session 23 - Vocabulary CSV Quality Improvements (2025-11-29)

**Objective:** Make vocabulary CSV usable by reducing noise and adding quality scoring.

### Key Changes

| Change | Impact |
|--------|--------|
| Min occurrence filter (2+) | 30-40% noise reduction |
| Raised rarity threshold (150K→180K) | 10-15% reduction |
| OCR error pattern filtering | 5% reduction |
| Quality Score column (0-100) | Excel filtering |
| In-Case Freq & Freq Rank columns | Statistical signals |
| Export format options (all/basic/terms) | User preference |

**Design Decision:** PERSON entities exempt from min occurrence filter (party names critical even if mentioned once).

---

## Session 22 - UI Improvements & Documentation (2025-11-29)

### Features

- Processing timer with elapsed time display (⏱ 0:45 format)
- Button state feedback ("Generating..." during processing)
- Metrics CSV logging for future ML duration prediction
- Human-readable completion time (11m 20s vs 680.6s)
- `format_duration()` utility function

### Documentation

- Merged `scratchpad.md` → `TODO.md`
- Created `ARCHITECTURE.md` with Mermaid diagrams

---

## Sessions 20-21 - Multi-Document Summarization & Thread-Through Architecture (2025-11-29)

### Session 20: Hierarchical Map-Reduce

Implemented proper multi-document summarization (previously naive concatenation truncated ~97% of content):
- **Map Phase:** Each document processed through ProgressiveDocumentSummarizer
- **Reduce Phase:** Individual summaries combined into meta-summary
- New package: `src/summarization/` with result types, orchestrator, document summarizer
- 16 new tests pass

### Session 21: Thread-Through Focus

User's selected template now guides entire pipeline (not just final output):
- `PromptFocusExtractor`: AI extracts focus areas from template
- `MultiDocPromptAdapter`: Threads focus through chunk→doc→meta stages
- Content-hash caching for efficiency
- 22 new tests pass

---

## Sessions 16-19 - Performance & Settings (2025-11-28)

### Session 16: GUI Performance & Preprocessing

- Async batch insertion with pagination (50 rows initial, "Load More")
- Background GC threads
- Smart preprocessing pipeline (HeaderFooterRemover, LineNumberRemover, QAConverter)
- 16 new preprocessing tests

### Session 17: Ollama Context Window Fix

- Aligned chunking to 2048 token context window (max 1000 words/chunk)
- Added `num_ctx` to API payload
- Ruff linting: fixed 17 critical bugs, 342→0 issues

### Session 18: Parallel Document Processing

- `src/parallel/` module with Strategy Pattern
- ThreadPoolStrategy for production, SequentialStrategy for testing
- ProgressAggregator for throttled UI updates
- 2.5-3x speedup for multi-document processing
- 30 new tests

### Session 19: Extensible Settings GUI

- Registry-based settings system (add setting = one register() call)
- Tabbed dialog with SliderSetting, CheckboxSetting, DropdownSetting widgets
- Tooltip system with hover delay
- 6 settings across Performance/Summarization/Vocabulary tabs

---

## Sessions 13-15 - Vocabulary Quality & GUI Responsiveness (2025-11-28)

### Session 13: UI Locking & Cancel Button

- Lock/unlock controls during processing
- Red cancel button stops all workers
- Batch queue processing (10 messages/100ms cycle)
- Configurable vocab display limits (150 rows default)

### Session 14: Vocabulary Performance

- Chunked processing with `nlp.pipe()` (50KB chunks)
- Disabled unused spaCy components (3x speedup)
- NLTK download timeout (15 seconds)
- Fixed medical term filtering

### Session 15: NER Quality Improvements

- Upgraded to `en_core_web_lg` model (4% better accuracy)
- Document frequency filtering (dynamic threshold)
- Pattern-based entity validation
- "Unknown" category for ambiguous classifications

---

## Sessions 9-12 - Vocabulary System Redesign (2025-11-27)

### Session 9: Stenographer-Focused Output

Created modular role detection system (`src/vocabulary/role_profiles.py`):
- Categories: Person, Place, Medical, Technical (not academic terms)
- Context-aware role detection (Plaintiff, Treating physician, etc.)
- O(1) cached frequency rank lookup

### Sessions 10-11: Bug Fixes & Filtering

- Fixed common words leaking (threshold 75K→150K)
- Fixed ALL CAPS name misclassification
- Entity cleaning (removes "and/or lung" fragments)
- Legal citation/boilerplate filtering
- Deduplication algorithm (30-40% reduction)

### Session 12: Condensation Policy

Established automatic log condensation rules: 5 recent detailed, 6-20 condensed, 21+ minimal.

---

## Sessions 5-8 - Core Features (2025-11-25 to 2025-11-26)

### Session 8: System Monitor & UI

- Real-time CPU/RAM display with color thresholds
- Tooltip system for quadrant headers
- Dynamic vocabulary table with filtering
- Prompt selection UI with persistent user prompts
- Recursive length enforcement for summaries

### Sessions 5-7: Refactoring

- Created `WorkflowOrchestrator` (business logic separate from UI)
- Unified logging system (`src/logging_config.py`)
- `src/vocabulary/` package created
- Comprehensive debug logging pattern

### Session 6: Vocabulary Workflow

- `VocabularyWorker` class for async extraction
- spaCy auto-download using `sys.executable`
- Config files made optional

---

## Historical Summary (Pre-Session 5)

### Technology Stack Established

- **UI:** CustomTkinter dark theme (replaced broken PyQt6)
- **AI Backend:** Ollama REST API (replaced fragile ONNX Runtime)
- **Concurrency:** ThreadPoolExecutor for I/O-bound operations
- **Configuration:** config.py with DEBUG mode

### Phase Completion

- ✅ Phase 1: Document pre-processing (PDF/TXT/RTF, OCR detection)
- ✅ Phase 2 (Partial): Desktop UI, AI integration, parallel processing
- ⏳ Phase 2.2, 2.4: Document prioritization, license server (post-v1.0)

---

## Current Status

**Application State:** Q&A-first tool - Integration bugs being fixed
**Tests:** 207 passing
**Sessions:** 30 completed
**Last Updated:** 2025-12-01 (Session 30 - Q&A/Vocabulary Integration Fixes)
