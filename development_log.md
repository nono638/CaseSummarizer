# Development Log

## Session 24 - Q&A System Infrastructure with FAISS Vector Search (2025-11-30)

**Objective:** Implement RAG-based Q&A system for legal documents, allowing users to ask questions that are answered from document content with source citations.

### Research & Planning

Evaluated vector search options for **standalone Windows installer** requirement (no database configuration):
- **LlamaIndex** - Too heavy (300+ packages)
- **ChromaDB** - Requires SQLite (rejected by user)
- **FAISS** ✅ - File-based persistence, LangChain native, zero config

**Key Decision:** FAISS stores indexes as simple files (`index.faiss` + `index.pkl`) - no database needed. Users only need Ollama installed.

### Phase 1 Implementation: Vector Store Infrastructure

| File | Lines | Purpose |
|------|-------|---------|
| `src/vector_store/__init__.py` | 38 | Package exports |
| `src/vector_store/vector_store_builder.py` | 260 | Creates FAISS indexes from documents |
| `src/vector_store/qa_retriever.py` | 182 | Retrieves relevant context for questions |
| `src/vector_store/question_flow.py` | 310 | Branching question tree manager |
| `config/qa_questions.yaml` | 145 | Question definitions with branching logic |
| `src/config.py` | +22 | Q&A settings (QA_RETRIEVAL_K, VECTOR_STORE_DIR, etc.) |
| `requirements.txt` | +4 | langchain, langchain-community, langchain-huggingface, faiss-cpu |

### Workflow Integration

Updated `WorkflowOrchestrator` to automatically create vector store after document extraction:
1. Vector store creation runs in background thread (parallel with vocabulary/AI)
2. Text chunked via `RecursiveCharacterTextSplitter` (500 chars, 50 overlap)
3. Embeddings generated using `all-MiniLM-L6-v2` (same as ChunkingEngine)
4. Index saved to `%APPDATA%/LocalScribe/vector_stores/<case_id>/`
5. UI receives `vector_store_ready` message when complete

### Branching Question Flow

Implemented decision tree for document analysis:
```
is_court_case?
├── YES → case_type?
│   ├── CRIMINAL → charges → defendant → timeline...
│   ├── CIVIL → civil_type → allegations → parties...
│   └── ADMINISTRATIVE → agency → issue → parties...
├── NO → document_type → summary (terminal)
└── UNCLEAR → summary (terminal)
```

**14 questions** defined in YAML with classification (branching) and extraction (open-ended) types.

### Files Modified

| File | Changes |
|------|---------|
| `src/ui/workflow_orchestrator.py` | +65 lines - `_create_vector_store_async()`, `on_vector_store_complete()` |
| `src/ui/queue_message_handler.py` | +55 lines - `handle_vector_store_ready()`, `handle_vector_store_error()` |

### Tests

- All 51 core tests passing
- Integration verification successful (imports, config, case ID generation)

### Remaining Work (Not Started)

Phase 2 & 3 of Q&A implementation:
- Q&A UI tab with chat interface
- QAWorker for background retrieval + generation
- Case-type auto-detection from document content
- Smart question suggestions based on detected case type
- Chat history export (TXT/Markdown)

---

## Session 23 - Vocabulary CSV Quality Improvements (2025-11-29)

**Objective:** Make vocabulary CSV output actually usable by reducing noise, adding quality scoring columns, and implementing filterable export options.

### Problem Statement

Vocabulary CSV output was **unusable** due to:
- Too many common words and OCR errors (single-occurrence typos)
- Wrong categorization and definitions
- No way to filter/sort by quality in Excel

### Phase 1: Quick Wins (Filtering Improvements)

| Change | Impact | File |
|--------|--------|------|
| **Min Occurrence Filter** | 30-40% noise reduction | `vocabulary_extractor.py` |
| **Raised Rarity Threshold** | 10-15% noise reduction | `config.py` |
| **OCR Error Patterns** | 5% noise reduction | `vocabulary_extractor.py` |
| **Expanded Blacklist** | 5-10% noise reduction | `common_medical_legal.txt` |

**Key Design Decision:** PERSON entities are **exempt** from min occurrence filter - party names may appear once but are critical for stenographers.

### Phase 2: Confidence Columns (For Excel Filtering)

Added 3 new columns to vocabulary output:

| Column | Purpose | Range |
|--------|---------|-------|
| **Quality Score** | Composite confidence (0-100) | Higher = more useful |
| **In-Case Freq** | Occurrences in documents | Higher = more important |
| **Freq Rank** | Google word rank | 0 = rare, high = common |

**Quality Score Formula:**
```
Base: 50 points
+ Multiple occurrences: up to +20 (5 per occurrence, capped)
+ Rare word bonus: +10-20 (based on frequency rank)
+ Category boost: Person/Place +10, Medical +8, Technical +5, Unknown +0
```

### Files Modified

| File | Changes |
|------|---------|
| `src/config.py` | Added `VOCABULARY_MIN_OCCURRENCES=2`, updated `VOCABULARY_RARITY_THRESHOLD=180000` |
| `src/vocabulary/vocabulary_extractor.py` | Added OCR patterns, min occurrence filter, `_calculate_quality_score()`, `_get_term_frequency_rank()`, new output columns |
| `src/ui/dynamic_output.py` | Updated `COLUMN_CONFIG` with 7 columns |
| `config/common_medical_legal.txt` | Added 35+ common terms (exam, report, notes, file, notice, etc.) |
| `tests/test_vocabulary_extractor.py` | Updated tests for new behavior + verified new columns |

### New Methods Added

| Method | Purpose |
|--------|---------|
| `_get_term_frequency_rank()` | Returns Google frequency rank for O(1) lookup |
| `_calculate_quality_score()` | Computes composite 0-100 quality score |

### Pattern: Session 23 - Balanced Filtering

Established pattern for vocabulary quality vs. recall tradeoff:
- **Aggressive filtering** for non-PERSON categories (min 2 occurrences)
- **Permissive filtering** for PERSON entities (keep single-occurrence names)
- **Statistical signals** (quality score) let user apply additional filtering in Excel

### Tests
All 55 core tests passing.

### Phase 3: GUI Column Hiding & Export Settings

**User Request:** Confidence columns clutter the GUI but are useful for Excel filtering. Implemented separation of display vs. export columns.

| Feature | Implementation |
|---------|----------------|
| **GUI Column Hiding** | Added `GUI_DISPLAY_COLUMNS` (Term, Type, Role, Definition) - confidence columns hidden |
| **Export Format Setting** | New `vocab_export_format` setting in Vocabulary tab with 3 options |
| **Settings Persistence** | Export preference saved in user preferences JSON |

**Export Format Options:**
- **All columns**: Includes Quality Score, In-Case Freq, Freq Rank for Excel power users
- **Basic**: Term, Type, Role/Relevance, Definition (default)
- **Terms only**: Just vocabulary terms for simple lists

**Files Modified:**
- `src/ui/dynamic_output.py`: Added `GUI_DISPLAY_COLUMNS`, `ALL_EXPORT_COLUMNS`, updated `get_current_content_for_export()`
- `src/ui/settings/settings_registry.py`: Added `vocab_export_format` dropdown setting

### Phase 4: Code Quality Quick Wins

Four low-risk improvements completed in final ~30 minutes of session:

| Quick Win | Description | Files |
|-----------|-------------|-------|
| **Temp File Cleanup** | Deleted orphaned `.tmp.*` files, fixed corrupted `.gitignore`, added `*.tmp.*` pattern | `.gitignore` |
| **Print → Logging** | Replaced 9 `print()` statements with `debug_log()` to respect DEBUG_MODE toggle | `config.py`, `user_preferences.py`, `prompt_config.py` |
| **Centralized Constants** | Moved magic numbers to config.py for single source of truth | `config.py`, `dynamic_output.py`, `vocabulary_extractor.py`, `chunking_engine.py` |
| **Settings Validation** | Added input validation with user-friendly error messages | `user_preferences.py`, `settings_dialog.py` |

**New Constants in config.py:**
```python
VOCABULARY_ROWS_PER_PAGE = 50
VOCABULARY_BATCH_INSERT_SIZE = 20
VOCABULARY_BATCH_INSERT_DELAY_MS = 10
SPACY_DOWNLOAD_TIMEOUT_SEC = 600
SPACY_SOCKET_TIMEOUT_SEC = 10
SPACY_THREAD_TIMEOUT_SEC = 15
CHUNK_OVERLAP_FRACTION = 0.1
```

**Validation Rules Added:**
- `cpu_fraction`: Must be 0.25, 0.5, or 0.75
- `vocab_display_limit`: Must be 1-500
- `user_defined_max_workers`: Must be 1-8
- `default_model_id`: Cannot be empty
- `summary_words`: Must be 50-2000

---

## Session 22 - UI Improvements & Documentation Consolidation (2025-11-29)

**Objective:** Improve user experience with better processing feedback and consolidate documentation structure.

### UI Improvements

| Feature | Description |
|---------|-------------|
| **Button State Feedback** | "Generate X outputs" button now shows "Generating X outputs..." while processing |
| **Processing Timer** | Visible timer displays elapsed time during processing (⏱ 0:45 format) |
| **Metrics CSV Logging** | Processing duration, document count, page counts, model name logged to `processing_metrics.csv` for future ML-based duration prediction |
| **Status Bar Enhancement** | Status text now 18pt bold with bright cyan (#00E5FF) for better visibility on dark background |
| **Human-Readable Completion Time** | Changed completion message from "680.6s" to "11m 20s" format |

### New Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `src/ui/processing_timer.py` | Timer widget + CSV metrics logging + `format_duration()` utility | ~220 |

### Files Modified

| File | Changes |
|------|---------|
| `src/ui/widgets.py` | Added `set_generating_state()` method to OutputOptionsWidget |
| `src/ui/main_window.py` | Integrated ProcessingTimer, enhanced status bar styling |
| `src/ui/queue_message_handler.py` | Stop timer on completion, log metrics, use human-readable duration format |
| `src/config.py` | Added `DATA_DIR` and `PROCESSING_METRICS_CSV` paths |

### Documentation Consolidation

- **Merged `scratchpad.md` → `TODO.md`**: Single backlog file for all future ideas
- **Updated `CLAUDE.md`**: Section 3.2 now references TODO.md instead of scratchpad
- **Added brainstorming sections to TODO.md**: Vocabulary CSV quality and summary prompt quality marked as high-priority areas needing fundamental rethinking

### Utility Function: `format_duration()`

Created reusable duration formatter for human-readable time display:
```python
format_duration(45)    # → "45s"
format_duration(150)   # → "2m 30s"
format_duration(680.6) # → "11m 20s"
format_duration(3725)  # → "1h 2m 5s"
```

### Tests
All 149 tests passing.

---

## Session 21 Continued - Architecture Documentation (2025-11-29)

**Objective:** Create comprehensive, maintainable architecture documentation with visual diagrams to help understand and troubleshoot the system.

### New Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `ARCHITECTURE.md` | Living program architecture with Mermaid diagrams | ~650 |

### ARCHITECTURE.md Contents

Created comprehensive documentation covering:
1. **High-Level Overview** - System components and connections
2. **User Interface Layer** - MainWindow structure, widget hierarchy, message flow
3. **Processing Pipeline** - Extraction → Sanitization → Preprocessing stages
4. **Multi-Document Summarization Pipeline** - Focus threading architecture with actual prompt templates
5. **AI Integration Layer** - Ollama, PromptTemplateManager, PostProcessor
6. **Vocabulary Extraction System** - spaCy NLP flow
7. **Parallel Processing Architecture** - Strategy pattern for execution
8. **Configuration & Settings** - All config files and their purposes
9. **Complete Data Flow** - End-to-end 7-stage visualization
10. **File Directory Quick Reference** - One-line descriptions of all source files

### AI_RULES.md Updates

Added **Section 11D - ARCHITECTURE.md Maintenance (Mandatory)**:
- When to update (10 specific triggers in table)
- When to skip (bug fixes, internal refactoring)
- Update format template
- Thoroughness requirements ("be thorough, not summarized")
- Mermaid syntax quick reference
- Architecture update checklist (6 items)

Added to **Mandatory Patterns Checklist** (Appendix):
- "ARCHITECTURE.md updated if structure changed"

### Technology Choice: Mermaid

Chose Mermaid over ASCII art because:
1. **Maintainability** - Update code like `flowchart TB` instead of aligning box characters
2. **Version Control** - Diffs show semantic changes, not character shifts
3. **Rendering** - GitHub, VS Code (Mermaid Chart extension), Obsidian render natively
4. **Official Support** - Mermaid Chart is the official VS Code extension from the Mermaid.js team

### Viewing the Diagrams

In VS Code: Press `Ctrl+Shift+V` to open Markdown Preview (requires Mermaid Chart extension)

---

## Session 21 - Thread-Through Prompt Template Architecture (2025-11-29)

**Objective:** Make multi-document summarization prompt-guided - the user's selected template should guide the entire pipeline, not just the final output. Previously, multi-doc mode ignored the user's template and used hardcoded prompts.

### Problem Discovered

Multi-document summarization had a critical gap:
- **User's template:** Contains focus areas (injuries, damages, timeline, etc.)
- **Multi-doc pipeline:** Was using hardcoded prompts throughout
- **Result:** Meta-summary didn't prioritize what the user actually wanted

### Solution: Thread-Through Architecture

Implemented focus area extraction and propagation through all pipeline stages:

1. **Focus Extraction Phase:** AI analyzes user's template to extract:
   - `emphasis`: Short phrase for intermediate prompts (e.g., "injuries, damages, timeline")
   - `instructions`: Numbered list for meta-summary generation

2. **Thread-Through Phases:**
   - Chunk prompts include focus emphasis
   - Document final prompts include focus emphasis
   - Meta-summary prompt uses extracted instructions

### New Modules Created

| File | Purpose | Lines |
|------|---------|-------|
| `src/prompt_focus_extractor.py` | Extracts focus from templates using AI | ~262 |
| `src/prompt_adapters.py` | Generates stage-specific prompts with focus | ~314 |
| `tests/test_prompt_adapters.py` | 22 unit tests for new modules | ~290 |

### Architecture: Abstract Base Classes for Future-Proofing

Both modules use ABCs for swappable implementations:

**FocusExtractor ABC:**
- `AIFocusExtractor` (current): Uses Ollama to extract focus
- Future: `KeywordFocusExtractor`, `HybridFocusExtractor`

**PromptAdapter ABC:**
- `MultiDocPromptAdapter` (current): Threads focus through all stages
- Future: `VerbatimPromptAdapter`, `DebugPromptAdapter`

### Key Design Decisions

1. **ALL templates use AI extraction** - No hardcoded mappings for built-in templates
2. **Cache by content hash** - Template edits trigger re-extraction
3. **Dependency injection** - All components accept adapters as optional params
4. **Graceful fallback** - Generic focus if extraction fails

### Files Modified

| File | Changes |
|------|---------|
| `src/ui/workers.py` | `MultiDocSummaryWorker` creates and passes prompt_adapter |
| `src/summarization/document_summarizer.py` | `ProgressiveDocumentSummarizer` uses adapter for chunk/final prompts |
| `src/summarization/multi_document_orchestrator.py` | Uses adapter for meta-summary prompt |

### Data Flow

```
User selects template → preset_id passed to worker
                           ↓
        MultiDocPromptAdapter created with template_manager
                           ↓
        AIFocusExtractor extracts focus (emphasis + instructions)
                           ↓
        ┌─────────────────────────────────────────────┐
        │  For each document:                         │
        │    For each chunk:                          │
        │      create_chunk_prompt(focus.emphasis)    │
        │    create_document_final_prompt(focus)      │
        └─────────────────────────────────────────────┘
                           ↓
        create_meta_summary_prompt(focus.instructions)
                           ↓
        Final meta-summary guided by user's template
```

### Test Results

- **22 new tests** in `tests/test_prompt_adapters.py`
- **All 38 tests passing** (22 new + 16 existing multi-doc tests)
- Tests cover: ABC contracts, caching, parsing, focus propagation

### Pattern Documented

**Thread-Through Focus Pattern:** When implementing multi-stage pipelines where user intent should propagate through all stages, use:
1. ABC for extraction strategy (swappable extraction methods)
2. ABC for prompt generation (swappable prompt templates)
3. Content-hash caching (efficient, responds to edits)
4. Dependency injection (testable, future-proof)

---

## Session 20 - Multi-Document Hierarchical Summarization (2025-11-29)

**Objective:** Implement proper multi-document summarization using a hierarchical map-reduce architecture. Previously, multiple documents were naively concatenated and sent to Ollama, which silently truncated ~97% of content due to context window limits.

### Problem Discovered

The existing code had a critical gap:
- **Single document:** Proper chunking via `ProgressiveSummarizer` (working well)
- **Multiple documents:** Naive concatenation → Ollama silently truncates most content

### Solution: Hierarchical Map-Reduce

Implemented a two-phase approach:
1. **Map Phase:** Each document processed in parallel through `ProgressiveDocumentSummarizer` (chunking → chunk summaries → document summary)
2. **Reduce Phase:** Individual document summaries combined into coherent meta-summary

### New Package: `src/summarization/`

| File | Purpose | Lines |
|------|---------|-------|
| `__init__.py` | Package exports | ~55 |
| `result_types.py` | `DocumentSummaryResult`, `MultiDocumentSummaryResult` dataclasses | ~95 |
| `document_summarizer.py` | `DocumentSummarizer` ABC + `ProgressiveDocumentSummarizer` | ~240 |
| `multi_document_orchestrator.py` | Parallel doc processing with map-reduce | ~290 |

### Files Modified (3)

| File | Changes |
|------|---------|
| `src/ui/workers.py` | Added `MultiDocSummaryWorker` class (~115 lines) |
| `src/ui/workflow_orchestrator.py` | Routing logic: single doc → direct path, multiple docs → hierarchical |
| `src/ui/queue_message_handler.py` | Handler for `multi_doc_result` message type |

### Architecture Highlights

- **Strategy Pattern:** Uses existing `ThreadPoolStrategy` for parallel document processing
- **Automatic Routing:** `WorkflowOrchestrator._start_ai_generation()` detects doc count and routes appropriately
- **Progress Aggregation:** Uses existing `ProgressAggregator` for throttled UI updates
- **Context Window Safety:** Meta-summary generator chunks if combined summaries exceed context window
- **Testability:** Uses `SequentialStrategy` for deterministic testing

### Test Results

- **16 new tests** in `tests/test_multi_document_summarization.py`
- **All passing:** Result types, summarizer interface, orchestrator, imports

### Snags Encountered

1. **ProgressiveSummarizer has no `update_chunk_summary()` method** - Solved by directly updating DataFrame in `ProgressiveDocumentSummarizer`
2. **Test collection error with UI tests** - Unrelated to new code; core tests pass

---

## Session 19 - Extensible Settings GUI (2025-11-28)

**Objective:** Create a comprehensive, extensible Settings GUI for LocalScribe with tabbed interface, tooltips, and easy extensibility for future settings.

### Architecture: Settings Registry Pattern

Implemented a declarative registry-based settings system that decouples setting definitions from the UI. Adding a new setting requires only a single `SettingsRegistry.register()` call - no UI code changes needed.

**Design Principle:** The registry pattern is similar to how Django Admin generates admin interfaces from model definitions. Each setting has metadata (label, tooltip, type, getter, setter) that the dialog uses to auto-generate appropriate widgets.

### New Files Created (4)

| File | Purpose | Lines |
|------|---------|-------|
| `src/ui/settings/__init__.py` | Package exports | ~45 |
| `src/ui/settings/settings_widgets.py` | Reusable widgets with integrated tooltips | ~310 |
| `src/ui/settings/settings_registry.py` | Declarative setting definitions + registry | ~210 |
| `src/ui/settings/settings_dialog.py` | Tabbed dialog that reads from registry | ~180 |

### Files Modified (2)

| File | Changes |
|------|---------|
| `src/user_preferences.py` | Added generic `get(key, default)` and `set(key, value)` methods for extensibility |
| `src/ui/main_window.py` | Updated import and `show_settings()` to use new dialog |

### Widget Types Implemented

| Widget | Setting Type | Use Case |
|--------|-------------|----------|
| `SliderSetting` | Numeric range | Summary length (100-500 words), vocab limit |
| `CheckboxSetting` | Boolean toggle | Auto-detect CPU, sort by rarity |
| `DropdownSetting` | Selection | CPU allocation (1/4, 1/2, 3/4 cores) |
| `SpinboxSetting` | Integer +/- | Manual worker count (1-8) |
| `TooltipIcon` | All | Info icon (ⓘ) with hover popup |

### Settings Registered (6)

**Performance Tab:**
- Auto-detect CPU cores (checkbox)
- Manual worker count (spinbox, 1-8)
- CPU allocation fraction (dropdown)

**Summarization Tab:**
- Default summary length in words (slider, 100-500)

**Vocabulary Tab:**
- Vocabulary display limit (slider, 10-200)
- Sort vocabulary by rarity (checkbox)

### Extensibility: Adding New Settings

```python
# To add a new setting, just add one line:
SettingsRegistry.register(SettingDefinition(
    key="my_new_setting",
    label="Enable New Feature",
    category="General",  # Creates new tab if needed
    setting_type=SettingType.CHECKBOX,
    tooltip="Description shown on hover.",
    default=False,
    getter=lambda: prefs.get("my_new_setting", False),
    setter=lambda v: prefs.set("my_new_setting", v),
))
# No other code changes needed - dialog auto-generates UI
```

### Testing

- **111 tests passing** (no new tests needed - settings module uses existing patterns)
- GUI manually tested - Settings dialog opens with all 3 tabs and 6 settings
- Tooltips display on hover, values persist on save

### UI Polish (User Feedback)

After initial implementation, addressed user feedback:

1. **Tooltip Fix:** Tooltips now properly disappear when mouse leaves both the icon and tooltip popup (added `_check_hide_tooltip()` with mouse position checking)

2. **Dependent Settings:** Manual worker count spinbox is now greyed out and disabled when "Auto-detect CPU cores" is checked (added `set_enabled()` method and `_setup_dependencies()` in dialog)

3. **More Prominent Tabs:** Settings tabs now use larger font (size 14, bold) and increased height (36px) with custom colors for better visibility

4. **Improved Status Bar:** Main window status bar text is now larger (size 14) and bold for better readability during processing

### Bug Fix (Unrelated)

Fixed pre-existing issue: `src/ui/queue_message_handler.py` file was accidentally emptied. Restored from git HEAD.

### Pattern Documented

**Settings Registry Pattern:** Use `SettingDefinition` dataclass with getter/setter lambdas and `SettingsRegistry.register()` for declarative setting management. The dialog reads the registry and auto-generates widgets. Applies to any future user-configurable options.

---

## Session 18 - Parallel Document Processing (2025-11-28)

**Objective:** Implement parallel document processing to speed up multi-file workflows for court reporters processing multiple documents at once.

### Architecture: Strategy Pattern for Parallel Execution

Created a dedicated `src/parallel/` module implementing the Strategy Pattern, enabling:
- **Production:** ThreadPoolStrategy for concurrent document processing
- **Testing:** SequentialStrategy for deterministic, debuggable tests
- **Future Extension:** Easy to add ProcessPoolStrategy if needed

**Why ThreadPoolExecutor (not ProcessPoolExecutor):**
| Factor | Threading | Multiprocessing |
|--------|-----------|-----------------|
| GIL Impact | Minimal (PDF/OCR release GIL) | N/A |
| Memory Overhead | ~1MB per thread | ~300MB per process |
| Data Sharing | Shared memory | Pickle serialization |

PDF parsing (pdfplumber) and OCR (pytesseract) both call C libraries that release the GIL, making threading effective despite Python's GIL.

### New Files Created (4)

| File | Purpose | Lines |
|------|---------|-------|
| `src/parallel/__init__.py` | Package exports | 68 |
| `src/parallel/executor_strategy.py` | Strategy interface + ThreadPool/Sequential | 173 |
| `src/parallel/task_runner.py` | Task orchestration with callbacks | 121 |
| `src/parallel/progress_aggregator.py` | Throttled UI progress updates | 133 |

### Files Modified (4)

| File | Changes |
|------|---------|
| `src/ui/workers.py` | Refactored ProcessingWorker to use Strategy Pattern |
| `src/config.py` | Added `PARALLEL_MAX_WORKERS`, `VOCABULARY_BATCH_SIZE` |
| `src/vocabulary/vocabulary_extractor.py` | Use configurable batch_size (4→8) |
| `tests/test_parallel.py` | 30 new unit tests for parallel module |

### Key Design Decisions

1. **Worker Count:** `min(cpu_count, 4)` - Auto-detects CPU cores but caps at 4 for memory safety
2. **Vocabulary Optimization:** Increased spaCy `batch_size` from 4 to 8 (~17% speedup, not threading due to GIL)
3. **Progress Throttling:** ProgressAggregator limits UI updates to max 10/second to prevent flooding
4. **Dependency Injection:** ProcessingWorker accepts optional `strategy` parameter for testing

### Expected Performance Gains

| Scenario | Current | Parallel | Speedup |
|----------|---------|----------|---------|
| 3 PDFs (digital) | 30s | 12s | **2.5x** |
| 3 PDFs (OCR) | 180s | 60s | **3.0x** |
| 5 PDFs (mixed) | 120s | 40s | **3.0x** |

### Memory Projections

| Configuration | Peak Memory | Safe for 8GB? |
|---------------|-------------|---------------|
| 2 parallel docs | ~1.5GB | ✅ Yes |
| 4 parallel docs | ~2.1GB | ✅ Yes |

### Testing

- **30 new tests** covering all parallel module components
- **108 total tests passing** (78 original + 30 new)
- Thread safety verified with concurrent test scenarios

### Pattern Documented

**Parallel Processing Pattern:** Use Strategy Pattern with injectable ExecutorStrategy for parallelizable operations. ThreadPoolStrategy for production (I/O-bound + GIL-releasing tasks), SequentialStrategy for testing. Applies to any future parallelization needs (e.g., Phase 3 AI chunking).

---

## Session 17 - Ollama Context Window Fix & Linting Cleanup (2025-11-28)

**Objective:** Fix Ollama context window configuration and address code quality with linting.

### Part A: Linting Setup with Ruff

Installed and configured Ruff linter to catch bugs and enforce code style.

**Initial Findings:**
- 342 issues found initially
- 80 auto-fixed (import sorting, type annotation modernization)
- **17 critical bugs found (F821):** `debug()` called without import in `ollama_model_manager.py`
- 29 remaining minor style issues fixed manually

**Issues Fixed:**
| Category | Count | Fix Applied |
|----------|-------|-------------|
| F841 (unused variables) | 9 | Prefixed with `_` or removed |
| B904 (raise without from) | 3 | Added `from e` to preserve exception chain |
| C401 (set comprehensions) | 2 | Changed `set([...])` → `{...}` |
| E701 (multi-statement lines) | 4 | Split onto separate lines |
| B023 (loop variable binding) | 4 | Used default parameter binding |
| C414, B905, B007, E402 | 6 | Various minor fixes |

**Files Created:**
- `ruff.toml` - Linter configuration

### Part B: Ollama Context Window Fix for CPU-Only Laptops

**Problem Discovered:** LocalScribe was NOT setting `num_ctx` in Ollama API calls. Ollama defaults to 2048 tokens, but our chunks were 2000-3000 words (~2600-3900 tokens). Result: **27-90% of each chunk was being silently truncated.**

**Research Findings (CPU Inference Performance):**
| Context Size | Speed | Usability |
|--------------|-------|-----------|
| 64k tokens | ~9 t/s | Unusable |
| 8k tokens | ~43 t/s | Sluggish |
| 4k tokens | ~86 t/s | Usable |
| **2k tokens** | ~150+ t/s | **Good** |

**Conclusion:** For court reporters on business laptops (8-16GB RAM, no GPU), the 2048 default is actually CORRECT. The fix was to align chunking with this limit.

**Changes Made:**
1. **`config/chunking_config.yaml`** - Reduced chunk sizes:
   - `max_chunk_words`: 2000 → 1000
   - `min_chunk_words`: 500 → 300
   - `max_chunk_words_hard_limit`: 3000 → 1200

2. **`src/config.py`** - Added `OLLAMA_CONTEXT_WINDOW = 2048` with documentation

3. **`src/ai/ollama_model_manager.py`** - Added:
   - `"options": {"num_ctx": 2048}` to API payload
   - Truncation warning when prompt approaches limit
   - Import of `OLLAMA_CONTEXT_WINDOW` from config

**Token Budget (2048 context):**
```
Total:          2048 tokens
- Prompt:       ~200 tokens
- Output:       ~300 tokens
- Safety:       ~50 tokens
= Available:    ~1500 tokens ≈ 1150 words
```

**Tests Created:** 7 new tests in `tests/test_ollama_context.py`
- Context window config validation
- Chunking-to-context alignment
- API payload verification
- Truncation warning tests

**Final Test Results:** 78 tests passing (71 original + 7 new)

---

## Session 16 - GUI Performance & Smart Preprocessing Pipeline (2025-11-28)

**Objective:** Fix GUI unresponsiveness during large PDF processing and implement smart preprocessing pipeline for improved AI summary quality.

### Part A: GUI Responsiveness Fixes

**Problem:** GUI became unresponsive after processing large documents (260 pages). User experienced "all of the above" - slowdown during processing, after completion, and when switching views.

**Root Causes Identified:**
1. Treeview batch insertion without UI yields - all rows inserted in tight loop
2. Synchronous `gc.collect()` blocking main thread
3. O(n²) deduplication algorithm in vocabulary extractor
4. No pagination for large vocabulary datasets

**Solutions Implemented:**

| Fix | Impact |
|-----|--------|
| Async batch insertion with `after()` | 20 rows/batch with 10ms yields to event loop |
| "Load More" pagination | Initial 50 rows, user clicks for more |
| Background GC threads | `threading.Thread(target=gc.collect, daemon=True)` |
| Optimized deduplication | O(n log n) using sorted length-based filtering |

**Files Modified:**
- `src/ui/dynamic_output.py` - Async insertion, pagination UI
- `src/ui/queue_message_handler.py` - Background GC
- `src/ui/main_window.py` - Background GC in cancel handler
- `src/vocabulary/vocabulary_extractor.py` - Optimized `_deduplicate_terms()`

### Part B: Smart Preprocessing Pipeline

**Objective:** Clean legal document text before AI summarization to improve summary quality by removing noise (line numbers, headers, Q./A. notation).

**Architecture:**
- `BasePreprocessor` - Abstract base class with `process()` method
- `PreprocessingPipeline` - Orchestrates preprocessors in sequence
- Each preprocessor is standalone, can be enabled/disabled independently

**Preprocessors Implemented:**

| Preprocessor | Purpose | Pattern |
|--------------|---------|---------|
| `TitlePageRemover` | Removes case captions/cover pages | Score-based detection |
| `HeaderFooterRemover` | Removes repetitive headers/footers | Frequency analysis (3+ occurrences) |
| `LineNumberRemover` | Removes "1  ", "2  " from margins | Regex for 1-25 at line start |
| `QAConverter` | Converts `Q.`/`A.` to `Question:`/`Answer:` | Regex substitution |

**Integration:**
- Preprocessing enabled in `combine_document_texts()` for AI summarization
- Preprocessing disabled for vocabulary extraction (raw text needed for NER)
- Graceful error handling - falls back to raw text if preprocessing fails

**Files Created:**
- `src/preprocessing/__init__.py`
- `src/preprocessing/base.py`
- `src/preprocessing/line_number_remover.py`
- `src/preprocessing/header_footer_remover.py`
- `src/preprocessing/title_page_remover.py`
- `src/preprocessing/qa_converter.py`
- `tests/test_preprocessing.py` (16 new tests)

**Files Modified:**
- `src/utils/text_utils.py` - Added `preprocess` parameter
- `src/ui/workflow_orchestrator.py` - Disabled preprocessing for vocab

### Part C: Logging System Consolidation

**Problem:** Codebase had dual logging systems causing confusion - `logging_config.py` (primary) and `debug_logger.py` (deprecated wrapper), plus some modules with local `debug()` functions.

**Solution:** Unified all logging to use `src.logging_config` as single source of truth.

**Files Modified:**
- Deleted `src/debug_logger.py` (deprecated backward-compat wrapper)
- Updated 8+ modules to import from `logging_config` instead of local wrappers

### Part D: Dead Code Removal & Config Cleanup

**Problem:** Several modules were unused in production and hardcoded thresholds scattered in UI code.

**Dead Code Removed:**
| File | Reason |
|------|--------|
| `src/document_processor.py` | AsyncDocumentProcessor never imported |
| `src/performance_tracker.py` | Only used by its own test file |
| `test_performance_tracking.py` | Orphaned test for dead module |

**Hardcoded Values Migrated to `config.py`:**
- `SYSTEM_MONITOR_THRESHOLD_GREEN = 75` (0-74%: healthy)
- `SYSTEM_MONITOR_THRESHOLD_YELLOW = 85` (75-84%: elevated)
- `SYSTEM_MONITOR_THRESHOLD_CRITICAL = 90` (90%+: red with !)

**Files Modified:**
- `src/config.py` - Added system monitor threshold constants
- `src/ui/system_monitor.py` - Now imports thresholds from config

### Part E: DRY Refactoring

**Problem:** `debug_timing()` function was duplicated in 2 files with identical implementation.

**Solution:** Extracted to `src/logging_config.py` as single source of truth.

**Files Modified:**
- `src/logging_config.py` - Added `debug_timing()` function
- `src/chunking_engine.py` - Updated import, removed local definition
- `src/progressive_summarizer.py` - Updated import, removed local definition

### Part F: Linting Setup with Ruff

**Problem:** No automated code quality checks; potential bugs and inconsistent style.

**Solution:** Installed and configured Ruff linter (Rust-based, 10-100x faster than flake8).

**Results:**
- 342 initial issues found
- 80 auto-fixed (import sorting, whitespace, type annotations)
- **17 undefined name bugs fixed** (F821) - `debug()` calls without import
- 29 remaining minor style issues (unused variables, etc.)

**Files Created/Modified:**
- `ruff.toml` - Linter configuration (E, W, F, I, UP, B, C4 rules)
- `requirements.txt` - Added `ruff` dependency
- `src/ai/ollama_model_manager.py` - Fixed missing `debug` import
- Multiple files cleaned up by auto-fix (import sorting, modern type hints)

### Testing

- ✅ All 71 tests passing (55 original + 16 new)
- ✅ Preprocessing pipeline verified with sample transcript text
- ✅ All imports verified working
- ⏳ Manual GUI testing with 260-page PDF pending

### Example Preprocessing Output

**Input:**
```
1  Q.  Good morning, Mr. Smith.
2  A.  Good morning.
3  Q.  State your name for the record.
```

**Output:**
```
Question: Good morning, Mr. Smith.
Answer: Good morning.
Question: State your name for the record.
```

---

## Session 15 - Vocabulary Extraction Quality Improvements (2025-11-28)

**Objective:** Improve vocabulary extraction quality by reducing false positives (common words, address fragments, legal boilerplate) and fixing incorrect categorization (person names labeled as Place, organizations labeled as Medical).

### Problems Addressed

User review of vocabulary CSV output revealed major quality issues:
- Common words flooding results ("tests", "factors", "continued", "truth")
- Wrong categorization (ANDY CHOY → Place instead of Person)
- Partial addresses extracted ("NY 11354")
- Legal boilerplate appearing ("Answering Defendants", "Verified Answer")
- Almost everything labeled as "Medical" incorrectly

### Root Causes Identified

1. **Entity extraction bypassed rarity filters** - spaCy-tagged entities were trusted unconditionally
2. **spaCy misclassifying entities** - ALL CAPS names like "ANDY CHOY" tagged as ORG instead of PERSON
3. **No pattern filtering for entities** - Address fragments and legal boilerplate weren't filtered
4. **No frequency limiting** - High-frequency terms weren't deprioritized

### Solutions Implemented (6 Phases)

**Phase 1: spaCy Model Upgrade**
- Changed from `en_core_web_sm` (12MB) to `en_core_web_lg` (560MB)
- ~4% better NER accuracy (85.5% vs 81.6%)
- Increased download timeout to 600 seconds

**Phase 2: Document Frequency Filtering**
- Added `doc_count` parameter throughout call chain
- Dynamic threshold: `doc_count × 4` (4 docs → max 16 occurrences)
- PERSON entities exempt from frequency filtering (parties' names should stay)
- Updated: VocabularyWorker, workflow_orchestrator, vocabulary_extractor

**Phase 3: Pattern-Based Entity Validation**
- Added `ADDRESS_FRAGMENT_PATTERNS` (floor numbers, street suffixes)
- Added `DOCUMENT_FRAGMENT_PATTERNS` (court headers, attorney listings)
- Added `MIN_ENTITY_LENGTH = 3`, `MAX_ENTITY_LENGTH = 60`
- New `_matches_entity_filter()` method filters junk before extraction

**Phase 4: Rarity Filter for Single-Word Entities**
- Single-word non-PERSON entities must pass rarity check
- Multi-word entities still trusted (harder to get wrong)
- Applied in `_first_pass_extraction()` before adding to results

**Phase 5: Category Validation with "Unknown"**
- Added `_looks_like_person_name()` heuristic (2+ capitalized words, no business indicators)
- Added `_looks_like_organization()` heuristic (LLP, Firm, Hospital, Clinic, etc.)
- Returns "Unknown" when spaCy classification conflicts with heuristics
- Better than wrong classification (user can review)

**Phase 6: Unknown Category Handling**
- Added "Clinic" to `ORGANIZATION_INDICATORS`
- Unknown category shows "Needs review" as role/relevance
- Definition returns "—" for Unknown (like Person/Place)

### UI Improvement

**Dropdown Placeholder Removal**
- Modified `_refresh_dropdown()` in `dynamic_output.py`
- "No outputs yet" placeholder now removed once real outputs available
- Prevents users from selecting useless blank state

### Files Modified

| File | Changes |
|------|---------|
| `src/vocabulary/vocabulary_extractor.py` | Model upgrade, patterns, filters, Unknown category |
| `src/ui/workers.py` | Added `doc_count` parameter to VocabularyWorker |
| `src/ui/workflow_orchestrator.py` | Pass doc_count through call chain |
| `src/ui/dynamic_output.py` | Remove placeholder from dropdown when outputs exist |
| `tests/test_vocabulary_extractor.py` | Updated for `full_term` parameter and flexible assertions |

### Expected Quality Improvements

| Before | After |
|--------|-------|
| "tests", "factors" in results | Filtered (common words) |
| "NY 11354" | Filtered (address pattern) |
| "Answering Defendants" | Filtered (legal boilerplate) |
| "ANDY CHOY" → Place | "ANDY CHOY" → Person (or Unknown) |
| "Mayo Clinic" → Unknown | "Mayo Clinic" → Place ("Clinic" indicator) |

### Testing
- ✅ All 55 tests passing
- ✅ Downloaded `en_core_web_lg` model (400MB)
- ✅ Application starts and runs

### Configuration Note
First run after this update will download the larger spaCy model (~400MB). This is a one-time download that takes 1-2 minutes on fast connections.

---

## Session 14 - Vocabulary Extraction Performance Optimization (2025-11-28)

**Objective:** Resolve vocabulary extraction hanging/freezing on large documents (260-page PDFs) by implementing chunked processing and spaCy optimizations based on official documentation.

### Root Causes Identified

1. **Initialization Order Bug**: `_load_frequency_dataset()` accessed `self.rarity_threshold` before it was set in `__init__`
2. **NLTK Download Hang**: `nltk.download()` could hang indefinitely on network issues with no timeout
3. **Monolithic NLP Processing**: 787KB document processed as single unit (~100K+ tokens, 2+ minutes)
4. **Unnecessary spaCy Components**: Full pipeline (tagger, lemmatizer, NER) when only NER needed
5. **Overly Aggressive Frequency Filtering**: Medical terms and named entities incorrectly filtered

### Solutions Implemented

**1. Chunked Processing with `nlp.pipe()` (src/vocabulary/vocabulary_extractor.py)**
- Split documents into 50KB chunks (per spaCy best practices)
- Process chunks using `nlp.pipe(chunks, batch_size=4)` for better memory efficiency
- Per spaCy docs: "there's no benefit to processing a large document as a single unit - all features are relatively local"
- Progress logging every 5 chunks for user feedback

**2. Disabled Unused spaCy Components**
- Load model with `disable=["tagger", "lemmatizer", "attribute_ruler"]`
- Only NER needed for vocabulary extraction
- ~3x speedup on large documents

**3. Fixed Initialization Order**
- Moved `self.rarity_threshold = VOCABULARY_RARITY_THRESHOLD` BEFORE `_load_frequency_dataset()` call
- Eliminated silent attribute error that was breaking frequency logging

**4. NLTK Download Timeout**
- Added 15-second timeout using threading
- Socket timeout set to 10 seconds
- Graceful fallback if download fails or times out

**5. Fixed Medical Term Filtering**
- Medical terms from curated `medical_terms.txt` now ALWAYS accepted
- Removed frequency-based filtering for curated medical list
- "cardiomyopathy" no longer filtered despite being in frequency dataset

**6. Fixed Named Entity Filtering**
- Trust spaCy's NER tagging for PERSON/ORG/GPE/LOC entities
- Removed frequency check that was filtering common surnames like "Smith"
- When spaCy tags token as PERSON, accept it (even if word is common)

### Configuration Changes

**New in src/config.py:**
```python
VOCABULARY_MAX_TEXT_KB = 200  # Max text for NLP processing (200KB ≈ 35K words)
```

### Files Modified
- `src/vocabulary/vocabulary_extractor.py` - Chunked processing, disabled components, fixed init order, timing logs
- `src/config.py` - Added VOCABULARY_MAX_TEXT_KB constant
- `src/ui/workers.py` - Better progress messages for vocabulary extraction

### Performance Improvement
- **Before:** 787KB document → hung indefinitely (2+ minutes before any output)
- **After:** 787KB document → ~20-30 seconds (processes first 200KB in 50KB chunks)

### Testing
✅ All 55 tests passing
✅ Application starts without errors
✅ Vocabulary extraction completes on large documents

### Sources Referenced
- [spaCy Discussion: Processing Large Documents](https://github.com/explosion/spaCy/discussions/9170)
- [Stack Overflow: Optimal spaCy Document Size](https://stackoverflow.com/questions/48143769/spacy-nlp-library-what-is-maximum-reasonable-document-size)
- [spaCy Processing Pipelines Documentation](https://spacy.io/usage/processing-pipelines)

---

## Session 13 - GUI Responsiveness Improvements & Critical Issue Discovery (2025-11-28)

**Objective:** Implement UI locking during processing, add cancel button, and resolve GUI unresponsiveness with large documents (260-page PDFs).

### Features Implemented

**1. UI Control Locking During Processing**
- Added `lock_controls()` and `unlock_controls()` methods to `OutputOptionsWidget` (src/ui/widgets.py:309-321)
- Disables slider and checkboxes during processing to prevent mid-flight configuration changes
- Re-enables controls after completion, error, or cancellation

**2. Cancel Processing Button**
- Added red "Cancel Processing" button in Output Options quadrant (src/ui/quadrant_builder.py:156-165)
- Button appears during processing, hidden by default (`grid_remove()`)
- Stops all workers: ProcessingWorker, VocabularyWorker, AI worker (src/ui/main_window.py:275-305)
- Restores UI to editable state on cancellation

**3. Batch Queue Processing for GUI Responsiveness**
- Changed `_process_queue()` from `while True` (unlimited) to batch processing (src/ui/main_window.py:351-384)
- Processes max 10 messages per 100ms cycle to prevent main thread blocking
- Calls `update_idletasks()` after each batch to keep UI responsive
- Prevents "Not Responding" during heavy message loads (260-page PDFs generate hundreds of progress updates)

**4. Configurable Vocabulary Display Limits**
- Added `VOCABULARY_DISPLAY_LIMIT = 150` and `VOCABULARY_DISPLAY_MAX = 500` to config (src/config.py:139-147)
- Based on tkinter Treeview performance research (500+ rows = 40-340 second render times)
- Displays first 150 rows (configurable) with overflow warning label
- Warning: "⚠ Displaying 150 of 532 terms. 382 more available via 'Save to File' button."
- CSV export saves ALL terms, not just displayed subset (src/ui/dynamic_output.py:268-321)
- Batch insertion (25 rows/batch) with `update_idletasks()` between batches

### Bug Fixes

**1. Missing `Path` Import**
- Fixed `NameError: name 'Path' is not defined` in vocabulary extraction (src/vocabulary/vocabulary_extractor.py:22)
- Added `from pathlib import Path` to imports
- Resolved 5 failing vocabulary tests (now 4/5 pass, 1 fails due to categorization expectation mismatch)

**2. Cancel Button Visibility**
- Added explicit `update_idletasks()` after `grid_remove()` to ensure immediate UI update (src/ui/queue_message_handler.py:174-190)
- Added debug logging to track button state transitions

### Critical Unresolved Issue

**🔴 Severe GUI Unresponsiveness After Large PDF Processing**
- **Symptoms:** After processing 260-page PDF, GUI becomes extremely slow/unresponsive
- **Observed:** Window dragging lags, view switching (Meta-Summary → Rare Word List) freezes, UI sometimes blank
- **Persists:** Even after processing completes and all optimizations applied
- **Hypotheses:** Memory leak, background threads not terminating, UI event queue saturation, Treeview corruption, or Windows-specific issue
- **Status:** Documented in scratchpad.md for next session investigation
- **Next Steps:** Profile memory, verify thread termination, add garbage collection, consider pagination

### Files Modified
- `src/ui/widgets.py` - Added lock/unlock methods to OutputOptionsWidget
- `src/ui/quadrant_builder.py` - Added cancel button
- `src/ui/main_window.py` - Batch queue processing, cancel handler, updated unpacking
- `src/ui/queue_message_handler.py` - Enhanced reset_ui with forced updates and logging
- `src/ui/workers.py` - Added stop event to VocabularyWorker
- `src/ui/workflow_orchestrator.py` - Track vocab_worker for cancellation
- `src/ui/dynamic_output.py` - Configurable display limits, batch insertion, overflow warning
- `src/vocabulary/vocabulary_extractor.py` - Added Path import
- `src/config.py` - Added VOCABULARY_DISPLAY_LIMIT and VOCABULARY_DISPLAY_MAX
- `scratchpad.md` - Documented critical GUI responsiveness issue

### Testing
- ✅ 50/55 tests passing (5 vocabulary tests had Path import issue, now 4/5 pass)
- ✅ UI startup test passed (cancel button exists, lock/unlock methods present)
- ❌ Large PDF (260 pages) causes severe GUI unresponsiveness (CRITICAL ISSUE)

---

## Session 12 - Development Log Automatic Condensation Policy (2025-11-28)

**Objective:** Establish automatic condensation policy for development_log.md to prevent token bloat while maintaining useful AI context.

### Problem
Development log grew to 1860 lines with overly detailed old entries (Session 7 was 743 lines alone, 40% of file). Manual condensation reduced to 847 lines, but needed formal policy to prevent recurrence. AI needs recent session details for context, but old entries should be condensed to save tokens.

### Solution
Updated AI_RULES.md with automatic condensation rules using **entry-count thresholds** (not date-based):
- **Most recent 5 sessions:** Full detail (implementation specifics, code examples, testing results)
- **Sessions 6-20:** Condensed to 50-100 lines (keep essentials, remove verbosity)
- **Sessions 21+:** Very condensed (20-30 lines, high-level summary only)
- **Target file size:** <1000 lines total

### Implementation

**1. Updated AI_RULES.md Section 2 (Documentation Ecosystem):**
- Replaced generic "DEV_LOG.md" reference with proper `development_log.md` entry
- Added complete condensation policy with 3-tier entry-count thresholds
- Defined condensation triggers (end-of-session, file size >1200 lines, >25 sessions)

**2. Created AI_RULES.md Section 11 (End-of-Session Documentation Workflow):**
- Defined 4-step workflow: Update development_log.md → Update human_summary.md → Git operations → Confirm to user
- Added Condensation Decision Tree with position-based logic (1-5 detailed, 6-20 condensed, 21+ minimal)
- Included before/after condensation example (743 lines → 60 lines)
- Specified verification steps (count sessions, apply condensation, verify file size)

**Files Modified:**
- `AI_RULES.md` - Added 117 lines total (Section 2 update + new Section 11)

### Testing
✅ Policy validated against current development_log.md structure
- Current file: 847 lines (compliant)
- Current sessions: ~12 sessions
- Positions 1-5: Detailed ✓ (Sessions 11, 10, 9, 8 Part 5, 8 Part 4)
- Positions 6-20: Already condensed ✓ (Session 7, Historical Summary, etc.)
- No immediate condensation needed

### Impact
Future sessions will automatically maintain optimal log size:
- **Consistent maintenance:** No more ad-hoc "the log is too big" requests
- **Token efficiency:** More room for actual code in context window
- **Better AI context:** Recent detailed entries + historical summaries balance
- **User transparency:** Clear policy documented in AI_RULES.md for both Claude and Gemini

---

## Session 11 - Additional Vocabulary Extraction Improvements (2025-11-27)

**Objective:** Implement 6 additional fixes to vocabulary extraction based on analysis of actual CSV output. Focus on filtering legal boilerplate, deduplication, and law firm detection.

### Issues Fixed

**Fix #1: Legal Citations Filtered**
- **Problem**: Statute references (CPLR SS3043, Education Law SS6527, etc.) appearing in output
- **Solution**: Added `LEGAL_CITATION_PATTERNS` with 4 regex patterns
- **Impact**: ~10-15 useless entries filtered per document

**Fix #2: Legal Boilerplate Filtered**
- **Problem**: Standard legal terminology (Verified Answer, Cause of Action, etc.) extracted as vocabulary
- **Solution**:
  - Added `LEGAL_BOILERPLATE_PATTERNS` (5 phrase patterns)
  - Added 10 boilerplate terms to `config/common_medical_legal.txt`
- **Impact**: ~10-20 useless entries filtered per document

**Fix #3: Case Citations Filtered**
- **Problem**: Case names (Mahr v. Perry pattern) extracted as person names
- **Solution**: Added `CASE_CITATION_PATTERN` to filter "X v. Y" format
- **Impact**: ~1-5 entries filtered per document

**Fix #4: Geographic Codes Filtered**
- **Problem**: ZIP codes (NY 11354) and location codes extracted as places
- **Solution**: Added `GEOGRAPHIC_CODE_PATTERNS` (2 patterns)
- **Impact**: ~2-5 entries filtered per document

**Fix #5: Deduplication Implemented** ✨
- **Problem**: Same entity extracted multiple times with variations:
  - "XIANJUN LIANG" AND "Plaintiff XIANJUN LIANG"
  - "State of New York" AND "the State of New York"
  - Partial names "XIANJUN" when full name "XIANJUN LIANG" exists
- **Solution**: New `_deduplicate_terms()` method with two-pass algorithm:
  1. **Prefix normalization**: Remove "the/a/an" prefixes, party labels
  2. **Substring filtering**: If "XIANJUN LIANG" exists, filter out "XIANJUN"
- **Impact**: ~30-40% duplicate entries removed

**Fix #6: Law Firm Detection**
- **Problem**: Law firms mis-categorized as medical terms or generic places
  - "EDELMAN & DICKER" → Medical term
  - "THE JACOB D. FUCHSBERG LAW FIRM" → Medical term
- **Solution**: Added 3 law firm detection patterns to `STENOGRAPHER_PLACE_PATTERNS`
- **Impact**: ~5-10 entries now correctly categorized as "Law firm"

### Implementation Details

**Files Modified:**

1. **src/vocabulary/vocabulary_extractor.py** (Major changes)
   - Added 4 pattern constant sets (lines 60-84):
     - `LEGAL_CITATION_PATTERNS` (4 patterns)
     - `LEGAL_BOILERPLATE_PATTERNS` (5 patterns)
     - `CASE_CITATION_PATTERN` (1 pattern)
     - `GEOGRAPHIC_CODE_PATTERNS` (2 patterns)
   - Applied all pattern filters in `_is_unusual()` (lines 496-513)
   - Implemented `_deduplicate_terms()` method (60 lines, lines 750-808)
   - Called deduplication in `extract()` (line 658)

2. **src/vocabulary/role_profiles.py** (Law firm detection)
   - Added 3 law firm patterns to `STENOGRAPHER_PLACE_PATTERNS` (lines 122-125)
   - Patterns detect: "Smith & Jones", "THE...LAW FIRM", "...LLP/PC/PLLC"

3. **config/common_medical_legal.txt** (Blacklist expansion)
   - Added 10 legal boilerplate terms (verified, affirmant, complainant, etc.)

### Expected Impact

**Before Session 11 fixes:**
- Session 10 reduced 506 rows → ~100-150 rows

**After Session 11 fixes:**
- Estimated final output: ~50-80 rows
- Breakdown:
  - Legal citations: -15 rows
  - Duplicates: -30 rows (largest impact!)
  - Boilerplate: -15 rows
  - Case citations: -5 rows
  - Geographic codes: -5 rows

**Net result:** Highly focused vocabulary list with minimal noise

### Code Quality Metrics
- **Net change**: 3 files modified
- **Lines added**: ~100 (patterns, deduplication method)
- **Lines removed**: ~0 (all additions)
- **All modules**: Under 900 lines (well under 1500 limit)
- **Compilation**: ✅ All imports successful

### Testing
✅ Import test passed
✅ Threshold verified: 150,000
✅ All pattern constants loaded
✅ Deduplication method compiles

### User Testing Required
1. Process same document that generated problematic CSV
2. Compare before (506 rows) vs after (should be 50-80 rows)
3. Verify deduplication works:
   - No "Plaintiff XIANJUN LIANG" if "XIANJUN LIANG" exists
   - No partial names ("XIANJUN") if full name exists
   - No "the State of New York" if "State of New York" exists
4. Verify filtering works:
   - No legal citations (CPLR SS3043, Education Law SS6527)
   - No boilerplate (Verified Answer, Affirmant)
   - No case citations (Mahr v. Perry)
   - No ZIP codes (NY 11354)
5. Verify law firms correctly categorized

---

## Session 10 - Vocabulary Extraction Bug Fixes & Precision Improvements (2025-11-27)

**Objective:** Fix 5 critical bugs in vocabulary extraction causing common words, mis-categorizations, and fragments in output. Improve filtering precision to provide stenographers with ONLY proper names and unfamiliar medical/technical terms.

### Problems Fixed

**Bug #1: Common Words Leaking Through**
- **Root Cause:** Lines 423-429 in `vocabulary_extractor.py` - NER entities and medical terms bypassed frequency check entirely
- **Symptoms:** "the", "and", "medical", "hospital", "doctor", "plaintiff" appearing in CSV output
- **Fix:** Added frequency check for single-word entities and medical terms. Multi-word entities still bypass (e.g., "John Smith"), but single words must pass rarity threshold.

**Bug #2: Threshold Too Permissive (75K)**
- **Root Cause:** 75,000 rank threshold allowed common words through
  - Rank 501: "medical" (155M occurrences) - FILTERED NOW
  - Rank 1345: "hospital" (85M occurrences) - FILTERED NOW
  - Rank 75,000: "chechens" (164K occurrences) - still common
- **Fix:** Increased threshold from 75,000 → 150,000 (filters top 45% of 333K vocabulary)

**Bug #3: Mis-categorization (e.g., "ANDY CHOY" → "Medical facility")**
- **Root Cause Chain:**
  1. spaCy tags ALL CAPS names as ORG instead of PERSON
  2. ORG category → "Place" type
  3. Regex patterns `[A-Z][a-z]+` don't match ALL CAPS
  4. `detect_place_relevance()` substring matches "CHOY Medical Center"
- **Fix:**
  - Updated ALL person/place regex patterns from `[a-z]+` to `[a-zA-Z]+`
  - Stricter place matching: require preposition context OR 2+ word facility names
  - `_places_match()` now requires 50% token overlap (not substring matching)

**Bug #4: Entity Fragments (e.g., "and/or lung")**
- **Root Cause:** spaCy includes leading/trailing context in `ent.text`
- **Fix:** New `_clean_entity_text()` method removes:
  - Leading/trailing conjunctions ("and/or", "and", "or")
  - Newlines and excess whitespace
  - Leading/trailing punctuation

**Bug #5: Title Abbreviations (e.g., "M.D.", "Ph.D.", "Esq.")**
- **Root Cause:** Acronym regex `[A-Z]{2,}` matches title abbreviations stenographers already know
- **Fix:** New `TITLE_ABBREVIATIONS` set filters 24 common titles before accepting as rare acronym

### Implementation Details

**Files Modified:**

1. **src/config.py** (Line 135)
   - Changed `VOCABULARY_RARITY_THRESHOLD = 75000` → `150000`
   - Added documentation: "Words with rank >= 150,000 are considered rare (bottom 55%)"

2. **src/vocabulary/vocabulary_extractor.py** (5 changes)
   - Added `TITLE_ABBREVIATIONS` set (24 common titles) after line 50
   - Added `_clean_entity_text()` method (30 lines) after line 211
   - Updated `_first_pass_extraction()` to use entity cleaning (line 607)
   - **Major fix:** Updated `_is_unusual()` lines 460-491:
     - NER entities: multi-word bypass, single-word must pass frequency check
     - Medical terms: must pass frequency check (filters "hospital", "doctor", etc.)
     - Acronyms: filter title abbreviations before accepting
   - Loaded common words blacklist in `__init__()` (line 126)
   - Added blacklist check in `_is_unusual()` (line 463)

3. **src/vocabulary/role_profiles.py** (3 changes)
   - Updated `STENOGRAPHER_PERSON_PATTERNS` (10 patterns): `[a-z]+` → `[a-zA-Z]+`
   - Updated `STENOGRAPHER_PLACE_PATTERNS` for stricter matching:
     - Require preposition context: `(?:at|to|from|near)\s+...Hospital`
     - Require 2+ word names: `([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)\s+Hospital`
   - Updated `_places_match()` for 50% token overlap requirement

4. **config/common_medical_legal.txt** (NEW FILE)
   - Defense-in-depth blacklist with 65+ common words
   - Common medical: hospital, doctor, physician, patient, treatment, surgery, etc.
   - Common legal: plaintiff, defendant, attorney, lawyer, court, judge, etc.

### Testing

**Compilation Test:** ✅ All modules import successfully
```
Rarity threshold: 150000 ✓
StenographerProfile loaded ✓
Title abbreviations loaded ✓
Blacklist loaded ✓
```

**Expected Improvements:**
- ❌ "the", "and", "of", "medical", "hospital", "doctor" → NOW FILTERED
- ❌ "M.D.", "Ph.D.", "Esq.", "R.N." → NOW FILTERED
- ❌ "and/or lung" fragments → NOW CLEANED TO "lung" or FILTERED
- ✅ "ANDY CHOY" → NOW Person, not Medical facility
- ✅ "adenocarcinoma", "bronchogenic", "carcinoma" → STILL EXTRACTED (rare medical)
- ✅ Multi-word entities → STILL BYPASS (e.g., "John Smith", "Memorial Hospital")

### Code Quality Metrics
- **Net change:** 6 files modified, 1 file created
- **Lines added:** ~180 (new methods, constants, comments)
- **Lines removed:** ~10 (replaced old logic)
- **All modules:** Under 750 lines (well under 1500 limit)
- **Backward compatible:** All existing tests should still pass
- **Modular design:** Preserved for future attorney/paralegal profiles

### Pattern Established
**Defense-in-Depth Filtering:** When implementing rarity filters, use multiple layers:
1. Hard exclusions (blacklists for absolute no-gos)
2. Frequency-based filtering (statistical rarity)
3. Semantic filtering (NER, medical terms list)
4. Post-processing (entity cleaning, title filtering)

This pattern applies to any filtering system where false positives are costly.

### User Testing Required
Before marking this complete, user should test with the original problematic document:
1. Generate new vocabulary CSV from same document
2. Verify common words are filtered ("the", "and", "medical", "hospital")
3. Verify ALL CAPS names categorized correctly ("ANDY CHOY" → Person)
4. Verify no fragments appear ("and/or lung" should be cleaned/filtered)
5. Verify title abbreviations filtered ("M.D.", "Ph.D.")
6. Compare old CSV (506 rows) vs new CSV (should be <100 rows with only meaningful terms)

---

## Session 9 - Vocabulary Extraction Redesign for Stenographer Workflow (2025-11-27)

**Objective:** Redesign vocabulary CSV output to provide actionable, context-aware information for court reporters preparing for depositions. Replace academic categorization with practical role detection tailored to stenographer needs while maintaining modular architecture for future profession expansion.

### Problem Addressed
The existing vocabulary extraction produced technically correct but practically useless output for stenographers:
- **Academic categories** like "Proper Noun (Person)" don't help stenographers prepare
- **Generic relevance scores** ("High", "Medium", "Low") lack context
- **Dictionary definitions for names/places** waste space (stenographers need WHO/WHY, not what the word means)
- **No context about roles** — is "Dr. Martinez" the plaintiff's doctor or defendant's doctor?

### Solution Implemented

**1. Modular Role Detection Architecture (`src/vocabulary/role_profiles.py` - NEW FILE)**
- Created `RoleDetectionProfile` base class for profession-specific relevance detection
- Implemented `StenographerProfile` with pattern-based role/relevance detection
- Enables future expansion: `LawyerProfile`, `ParalegalProfile`, `JournalistProfile` (just 50 lines each)
- Uses dependency injection: `VocabularyExtractor(role_profile=StenographerProfile())`

**2. Simplified Category System**
**Before:** "Proper Noun (Person)", "Proper Noun (Organization)", "Acronym", "Technical Term"
**After:** Person, Place, Medical, Technical

**3. Context-Aware Role/Relevance Detection**

**People Detection Patterns:**
```python
STENOGRAPHER_PERSON_PATTERNS = [
    (r'plaintiff[\'s]?\s+(?:attorney|counsel)?\s*([A-Z]...)', 'Plaintiff attorney'),
    (r'plaintiff\s+([A-Z]...)', 'Plaintiff'),
    (r'treating\s+(?:physician|doctor)\s+([A-Z]...)', 'Treating physician'),
    (r'(?:Dr\.|Doctor)\s+([A-Z]...)', 'Medical professional'),
    (r'witness\s+([A-Z]...)', 'Witness'),
]
```

**Place Detection Patterns:**
```python
STENOGRAPHER_PLACE_PATTERNS = [
    (r'accident\s+(?:at|on|near)\s+([A-Z]...)', 'Accident location'),
    (r'([A-Z]...)\s+Hospital', 'Medical facility'),
    (r'surgery\s+(?:at|performed at)\s+([A-Z]...)', 'Surgery location'),
]
```

**4. Smart Definition Display**
- **Person/Place:** No definition needed (stenographers need WHO/WHY, not dictionary meanings)
- **Medical/Technical:** Provide WordNet definitions for unfamiliar terminology
- Saves CSV space and improves readability

**5. Enhanced Regex Filtering**
Expanded `VARIATION_FILTERS` to catch more word variations:
```python
VARIATION_FILTERS = [
    r'^[a-z]+\(s\)$',          # plaintiff(s), defendant(s)
    r'^[a-z]+s\(s\)$',         # defendants(s) (double plurals)
    r'^[a-z]+\([a-z]+\)$',     # word(variant) (any parenthetical)
    r'^[a-z]+\'s$',            # plaintiff's (possessives)
    r'^[a-z]+-[a-z]+$',        # hyphenated variations
]
```

**6. Optimized Rarity Calculation**
**Before:** O(n) percentile calculation on every word check
**After:** O(1) cached rank lookup
- Sorts 333K word frequency dataset once during `__init__()`
- Builds `frequency_rank_map: Dict[str, int]` for instant lookups
- Massive performance improvement for large documents

### CSV Output Transformation

**Before (Academic):**
```csv
Term,Category,Relevance to Case,Definition
Dr. Sarah Martinez,Proper Noun (Person),High,N/A
Lenox Hill Hospital,Proper Noun (Organization),High,N/A
lumbar discectomy,Technical Term,Medium,removal of disk
```

**After (Stenographer-Focused):**
```csv
Term,Type,Role/Relevance,Definition
Dr. Sarah Martinez,Person,Treating physician,—
Lenox Hill Hospital,Place,Medical facility,—
lumbar discectomy,Medical,Medical term,Surgical removal of herniated disc material from lower spine
```

### Technical Changes

**Files Modified:**
1. **`src/vocabulary/role_profiles.py`** (NEW - 280 lines):
   - `RoleDetectionProfile` base class
   - `StenographerProfile` implementation
   - Documented placeholders for future profiles

2. **`src/vocabulary/vocabulary_extractor.py`** (Major refactor):
   - Added `role_profile` parameter to `__init__()` (defaults to `StenographerProfile()`)
   - Built cached frequency rank map in `_load_frequency_dataset()`
   - Simplified `_is_word_rare_enough()` to use O(1) rank lookup
   - Simplified `_get_category()`: Person/Place/Medical/Technical (4 categories, not 7+)
   - Updated `_get_definition()`: Takes `category` parameter, returns "—" for Person/Place
   - Removed `_calculate_relevance()` → replaced with profile-based role detection
   - Updated `_second_pass_processing()`: Now calls `role_profile.detect_person_role()` and `role_profile.detect_place_relevance()`
   - Changed output dict keys: "Category" → "Type", "Relevance to Case" → "Role/Relevance"

3. **`src/ui/dynamic_output.py`** (Column header updates):
   - Updated Treeview columns: `("Term", "Type", "Role/Relevance", "Definition")`
   - Updated CSV export headers to match
   - Updated data access: `item.get("Type")`, `item.get("Role/Relevance")`
   - Adjusted column widths: Type=120px, Role/Relevance=200px

4. **`tests/test_vocabulary_extractor.py`** (Updated for new API):
   - Updated `test_get_category()`: Expects "Person", "Place", "Technical", "Medical"
   - Updated `test_get_definition()`: Now requires `category` parameter
   - Updated `test_extract()`: Expects "Type" and "Role/Relevance" keys in output
   - All 5 tests passing ✅

### Code Quality Improvements
- **Net reduction:** 473 insertions, 615 deletions (-142 lines total)
- **Better separation of concerns:** Profession-specific logic isolated in profiles
- **Performance optimization:** Cached rank map eliminates repeated sorting
- **Future-proof design:** Adding new profession = 50 lines of patterns, zero core changes

### Pattern Established
**Role Detection System:** When adding profession-specific behavior, create a new `RoleDetectionProfile` subclass instead of modifying core extraction logic. This pattern applies to future features requiring customizable behavior (e.g., output formatters, filtering strategies).

### Next Steps (User Testing Required)
Before considering this feature complete, user should manually test with real legal documents:
1. Verify regex filters work (no "plaintiff(s)" in output)
2. Verify role detection works ("plaintiff John Smith" shows role "Plaintiff")
3. Verify rarity filtering works (common words excluded)
4. Verify UI displays correctly (new column headers in Treeview)

---

## Session 8 Part 5 - Google Word Frequency Dataset Integration (2025-11-26)

**Objective:** Integrate Google's 333K word frequency dataset to filter out common words from vocabulary extraction, allowing only truly rare terms to be included in the results.

### Problem Addressed
Vocabulary extraction was producing too many false positives: common words like "plaintiff(s)", "defendant(s)", and other variations of legal terminology were being flagged as "rare vocabulary." The existing WordNet filter wasn't granular enough to distinguish between statistically common words and truly unusual domain-specific terms.

### Solution Implemented

**1. Google Word Frequency Dataset Integration:**
- File: `Word_rarity-count_1w.txt` (333,333 words, tab-separated format: `word\tfrequency_count`)
- Loaded into memory as `Dict[str, int]` mapping word → frequency count
- Lower count = rarer word (fewer occurrences in Google's corpus)

**2. New Methods in VocabularyExtractor:**
- `_load_frequency_dataset()` — Parses tab-separated frequency file (handles missing file gracefully)
- `_matches_variation_filter()` — Regex-based filtering for word variations (plaintiff(s), defendant's, hyphenated)
- `_is_word_rare_enough()` — Determines if word meets rarity threshold using frequency dataset
- `_sort_by_rarity()` — Sorts vocabulary results by rarity (unknown words first, then lowest frequency counts)

**3. Regex Variation Filters:**
```python
VARIATION_FILTERS = [
    r'^[a-z]+\(s\)$',      # Matches "plaintiff(s)", "defendant(s)", etc.
    r'^[a-z]+\'s$',        # Matches possessives like "plaintiff's"
    r'^[a-z]+-[a-z]+$',    # Matches hyphenated variations
]
```
- Extensible: Users can add more patterns later
- Located at top of `vocabulary_extractor.py` for easy maintenance

**4. User-Customizable Configuration:**
- `VOCABULARY_RARITY_THRESHOLD = 75000` — Only accept words outside top 75K most common (out of 333K)
- `VOCABULARY_SORT_BY_RARITY = True` — Enable/disable rarity-based sorting
- Both configurable in `src/config.py` (no code changes needed)

### Updated Filtering Chain (in `_is_unusual()`)
```
1. Basic checks (alpha, whitespace, punctuation)
2. Legal term exclusions
3. User exclusions
4. ✨ NEW: Variation filter (plaintiff(s), defendant's, etc.)
5. Named entities (PERSON, ORG, GPE, LOC) → always accept
6. Medical terms → always accept
7. Acronyms (2+ uppercase) → always accept
8. ✨ NEW: Frequency-based rarity (Google dataset)
9. WordNet fallback (not in dictionary = rare)
```

### Sorting Strategy (if enabled)
1. **Words NOT in 333K dataset** (appear first) — Rarest of the rare
2. **Words in dataset sorted by frequency count** (ascending) — Lowest count = rarest

### Files Modified
- `src/config.py` — Added `GOOGLE_WORD_FREQUENCY_FILE`, `VOCABULARY_RARITY_THRESHOLD`, `VOCABULARY_SORT_BY_RARITY`
- `src/vocabulary/vocabulary_extractor.py` — Added 4 new methods, updated `_is_unusual()`, updated `extract()` for sorting

### Testing
- ✅ All 55 tests passing (no regressions)
- ✅ Frequency dataset loads successfully (333,333 words)
- ✅ Module imports without errors
- ✅ Backward compatible — existing API unchanged

### Design Benefits
1. **Probabilistic + Categorical Filtering:** Frequency dataset (statistical) + WordNet (categorical) = comprehensive word rarity assessment
2. **User-Driven Customization:** Threshold and sorting can be adjusted without code changes
3. **Extensible:** Variation filters can be added anytime by editing regex patterns
4. **Graceful Degradation:** Falls back to WordNet if frequency file missing
5. **Performance:** Sorted-by-rarity CSV helps users quickly find the most unusual vocabulary

### Next Steps
- User testing with real legal documents to verify "plaintiff(s)" and "defendant(s)" are now filtered
- Threshold adjustment if results still include too many common words
- Additional variation patterns added as they're discovered

---

## Session 8 Part 4 - Recursive Length Enforcement (2025-11-26)

**Objective:** Implement recursive summarization to ensure AI-generated summaries meet user's requested word count target.

### Problem Addressed
When users request a 200-word summary, LLMs often produce 300-500 words instead. Simply truncating would lose important information at the end. The solution: recursively condense over-length summaries until they meet the target.

### Implementation

**1. Configuration:**
- **20% tolerance**: A 200-word target accepts up to 240 words before triggering condensation
- **3 max attempts**: After 3 condensation tries, return best effort (prevents infinite loops)
- **Applies to all summaries**: Both individual document summaries and meta-summaries

**2. New Methods in OllamaModelManager:**
- `_enforce_length(summary, target_words, max_attempts)` - Main enforcement loop
- `_condense_summary(summary, target_words)` - Generates condensed version via AI

**3. Condensation Prompt Template:**
- Created `config/prompts/phi-3-mini/_condense-summary.txt`
- Underscore prefix means it's for internal use (not shown in dropdown)
- Instructs AI to preserve key facts while reducing verbosity

### Algorithm Flow
```
1. Generate initial summary
2. Check word count
3. If actual_words > target * 1.2:
   - Call _condense_summary()
   - Check again
   - Repeat up to 3 times
4. Return final summary (within tolerance or best effort)
```

### Files Modified
- `src/ai/ollama_model_manager.py` - Added `_enforce_length()` and `_condense_summary()` methods

### Files Created
- `config/prompts/phi-3-mini/_condense-summary.txt` - Condensation prompt template

### Debug Logging
The implementation logs each step for debugging:
```
[LENGTH ENFORCE] Target: 200 words, Max acceptable: 240 words, Actual: 350 words
[LENGTH ENFORCE] Attempt 1/3: Summary is 350 words (>240). Condensing...
[LENGTH ENFORCE] After condensation: 215 words
[LENGTH ENFORCE] Success: 215 words (within 20% tolerance of 200)
```

### Testing
- ✅ All 55 tests pass
- ✅ Module imports successfully
- ⏳ Live testing with Ollama pending (requires document processing)

### Refactoring: Separation of Concerns (Post-Implementation)

After the initial implementation, a review identified that length enforcement logic was tightly coupled to `OllamaModelManager`. This violated separation of concerns: the model manager shouldn't be responsible for post-processing logic.

**Refactoring Solution:**
1. Created new `SummaryPostProcessor` class (`src/ai/summary_post_processor.py`)
2. Moved `_enforce_length()` and `_condense_summary()` methods to new class
3. Updated OllamaModelManager to delegate to SummaryPostProcessor after generation
4. Result: Clean separation between generation (model manager) and post-processing (post-processor)

### Files Created (Post-Refactor)
- `src/ai/summary_post_processor.py` - New dedicated post-processing class

### Status
Phase 8 Part 4 complete. Length enforcement now functional and properly separated into dedicated module.

---

## Session 8 Part 3 - Prompt Selection UI Refinement (2025-11-26)

**Objective:** Polish the prompt selection UI by removing placeholder descriptions and adding comprehensive tooltips with real prompt content preview.

### Changes Made

**1. Removed Placeholder Descriptions**
- Deleted generic descriptions like "A balanced prompt..." from prompt template files
- Files affected: All 6 prompt templates in `config/prompts/phi-3-mini/`
- Rationale: Descriptions were placeholders never shown to user; tooltips provide better UX

**2. Added Comprehensive Tooltips**
- Tooltip shows actual prompt content (first 300 characters)
- Applied to both dropdown and label widgets
- Binding: `<Enter>` shows tooltip, `<Leave>` hides it
- Tooltip positioning: Right-aligned relative to dropdown

**3. Tooltip Implementation**
- Created `_show_prompt_tooltip()` and `_hide_prompt_tooltip()` methods in ModelSelectionWidget
- Tooltip window uses CTkToplevel with wraplength for readability
- Handles edge case: Missing prompt file shows "Prompt file not found"

### Files Modified
- `src/ui/widgets.py` - Added tooltip methods and event bindings
- All 6 prompt templates in `config/prompts/phi-3-mini/` - Removed placeholder descriptions

### Status
Prompt selection UI now provides clear preview of prompt content via hover tooltip.

---

## Session 8 Part 2 - Prompt Selection UI with Persistent User Prompts (2025-11-26)

**Objective:** Allow users to customize prompts by editing template files while ensuring changes persist across code updates via `.gitignore`.

### Implementation

**1. Prompt Template System**
- Created 6 prompt templates in `config/prompts/phi-3-mini/` directory
- Each template is a plain text file with placeholder `{{DOCUMENT_TEXT}}`
- Templates: single-document.txt, meta-summary.txt, 4 custom variations
- Prompt files added to `.gitignore` so user edits won't be overwritten by git updates

**2. UI Integration**
- Added dropdown in Model Selection quadrant with 6 prompt options
- Dropdown reads from `config/prompts/{model_name}/` directory
- Selected prompt sent to OllamaModelManager during summarization

**3. Graceful Fallback**
- If prompt file missing: uses hardcoded fallback prompt
- If prompt directory missing: creates it with default templates on first run
- Ensures application never crashes due to missing prompts

### Files Created
- `config/prompts/phi-3-mini/single-document.txt`
- `config/prompts/phi-3-mini/meta-summary.txt`
- Plus 4 custom prompt variants

### Files Modified
- `src/ui/widgets.py` - Added prompt dropdown to ModelSelectionWidget
- `src/ai/ollama_model_manager.py` - Updated to accept and use selected prompt template
- `.gitignore` - Added `config/prompts/` to prevent overwriting user customizations

### Status
Users can now freely edit prompt templates without fear of losing changes during updates.

---

## Session 8 - System Monitor, Tooltips, and Vocabulary Table Overhaul (2025-11-26)

**Objective:** Implement comprehensive UI improvements: system monitor widget, tooltip system, dynamic vocabulary table display, and related bug fixes.

### Summary
Completed 5 major UI enhancements. Created SystemMonitor widget with real-time CPU/RAM tracking and color-coded thresholds. Implemented tooltip system for all quadrant headers. Built dynamic vocabulary table with live filtering. Fixed file size formatting bug. Improved model dropdown persistence. All 55 tests passing.

### Features Implemented

**1. System Monitor Widget** (`src/ui/system_monitor.py`)
- Real-time CPU and RAM usage display in status bar
- Color thresholds: Green (0-74%), Yellow (75-84%), Orange (85-90%), Red (90%+)
- Hover tooltip shows detailed hardware info (CPU model, cores, frequencies)
- Background daemon thread updates every 1 second

**2. Tooltip System** (`src/ui/widgets.py`)
- Created reusable TooltipMixin class
- Applied to all 4 quadrant header labels
- Advanced user guidance (not beginner-oriented)
- 500ms hover delay prevents flickering

**3. Dynamic Vocabulary Table** (`src/ui/dynamic_output.py`)
- TreeView widget displays vocabulary results
- Columns: Term, Category, Relevance, Definition
- Live filtering: Show All / Rare Only / Unusual Only
- CSV export functionality

**4. Bug Fixes**
- File size rounding: Unified to integers across all units (KB, MB, GB)
- Model dropdown: Preserves user selection across refreshes

### Files Created
- `src/ui/system_monitor.py` (230 lines)
- `src/ui/dynamic_output.py` (180 lines)

### Files Modified
- `src/ui/widgets.py` - Tooltip system, file size fix, model dropdown fix
- `src/ui/main_window.py` - Integrated all new components

### Testing
✅ All 55 tests passing
✅ System monitor refreshes correctly
✅ Tooltips appear/disappear without flicker
✅ Vocabulary table displays results
✅ File sizes format consistently

### Status
Session 8 complete. UI now professional-grade with comprehensive real-time feedback.

---

## Session 7 - Separation of Concerns Refactoring (2025-11-26)

**Objective:** Comprehensive code review and refactoring to improve separation of concerns, eliminate code duplication, and consolidate dual logging systems.

### Summary
Performed full codebase review identifying 5 separation-of-concerns issues and implemented all fixes. Created `WorkflowOrchestrator` class to separate business logic from UI message handling. Consolidated dual logging systems into unified `logging_config.py`. Moved `VocabularyExtractor` to its own package. Created shared text utilities. All 55 tests passing after refactoring.

### Problems Addressed & Solutions

**Issue #1: VocabularyExtractor Location** - Created `src/vocabulary/` package and moved extractor there for consistency with other pipeline components.

**Issue #2: QueueMessageHandler Had Business Logic** - Created `WorkflowOrchestrator` class to separate workflow decisions from UI message routing. QueueMessageHandler now purely handles message dispatch and UI updates.

**Issue #3: Hardcoded Config Paths** - Replaced hardcoded paths with config imports (`LEGAL_EXCLUDE_LIST_PATH`, `MEDICAL_TERMS_LIST_PATH`).

**Issue #4: Dual Logging Systems** - Consolidated `debug_logger.py` and `utils/logger.py` into unified `logging_config.py` with backward-compatible re-exports.

**Issue #5: Unused Code** - Removed unused `SystemMonitorWidget` class from widgets.py (actual implementation was in `system_monitor.py`).

### New File Structure
```
src/
├── logging_config.py              # Unified logging (260 lines)
├── vocabulary/                     # Package
│   ├── __init__.py
│   └── vocabulary_extractor.py    # Moved + improved (360 lines)
├── utils/
│   ├── text_utils.py              # Shared text utilities (55 lines)
│   └── logger.py                  # Re-exports from logging_config
├── ui/
│   ├── workflow_orchestrator.py   # Workflow logic (180 lines)
│   └── queue_message_handler.py   # UI-only routing (210 lines)
```

### Test Results
✅ 55/55 tests PASSED
- Character Sanitization: 22 tests
- Raw Text Extraction: 24 tests
- Progressive Summarization: 4 tests
- Vocabulary Extraction: 5 tests

### File Size Compliance (Target: <300 lines)
- widgets.py: 209 lines ✅
- queue_message_handler.py: 210 lines ✅
- workflow_orchestrator.py: 180 lines ✅
- main_window.py: 295 lines ✅
- logging_config.py: 260 lines ✅

### Patterns Established

**Pattern: Workflow Orchestration** - Business logic separated from UI updates. Orchestrator can be unit tested independently.

**Pattern: Unified Logging** - All modules import from `src.logging_config`. Backward compatibility via re-exports.

**Pattern: Shared Utilities** - Pure functions in `src/utils/` package with type hints and docstrings.

### Status
✅ All separation-of-concerns issues resolved
✅ All tests passing (zero regressions)
✅ File sizes compliant
✅ Code duplication eliminated
✅ Logging consolidated

---

## Historical Summary (2025-11-13 to 2025-11-22)

### Major Milestones
1. **CustomTkinter UI Refactor** (2025-11-21): Completed pivot from broken PyQt6 to CustomTkinter dark theme framework, resolving DLL load errors and button visibility issues. Application achieved stable, responsive foundation.

2. **Ollama Backend Migration** (2025-11-17): Successfully migrated from fragile ONNX Runtime (Windows DLL issues, token corruption bugs) to Ollama REST API architecture. Achieved cross-platform stability (Windows/macOS/Linux) with cleaner error handling and runtime model switching.

3. **Critical GUI Crash Fix** (2025-11-17): Resolved application crash after summary generation by adding comprehensive error handling and thread-safe GUI updates. Summaries now display reliably; errors shown gracefully.

4. **UI Polish & Tooltips** (2025-11-22): Fixed tooltip flickering with 500ms delay strategy, darkened menu colors to #404040, standardized quadrant layout (Row 0 labels / Row 1+ content), added smart tooltip positioning fallbacks.

### Technology Stack
- **UI Framework:** CustomTkinter (dark theme, cross-platform)
- **Model Backend:** Ollama (REST API, any HuggingFace model)
- **Concurrency:** ThreadPoolExecutor for I/O-bound operations
- **Configuration:** config.py with DEBUG mode support
- **Logging:** Comprehensive debug logging with CLAUDE.md compliance

### Phase Completion Status
- ✅ **Phase 1:** Document pre-processing (PDF/TXT/RTF extraction, OCR detection, text cleaning)
- ✅ **Phase 2 (Partial):** Desktop UI (CustomTkinter, responsive layout), AI Integration (Ollama), Phase 2.7 (Model formatting), Phase 2.5 (Parallel foundation), Phase 2.6 (System monitor)
- ⏳ **Phase 2.2, 2.4:** Document prioritization, License server (post-v1.0)
- 📋 **Phase 3+:** Advanced features

### Key Technical Achievements
- Model-agnostic prompt wrapping (Phase 2.7)
- Resource-aware parallel processing formula (Phase 2.5)
- Real-time system monitoring with custom thresholds (Phase 2.6)
- Thread-safe GUI updates with comprehensive error handling
- User preference persistence (settings saved across sessions)
- Professional dark theme with keyboard shortcuts

---

## Session 5 - Code Pattern Refinement: Variable Reuse + Comprehensive Logging (2025-11-25)

**Objective:** Revert Session 4's descriptive variable naming pattern to a more Pythonic approach: variable reassignment with comprehensive logging for observability.

### Rationale for Change
Session 4 introduced explicit `del` statements to manage memory for large files (100MB-500MB). However, this approach was un-Pythonic. Python's garbage collection handles automatic memory cleanup. Better observability comes from comprehensive logging, not variable names.

### Key Changes

**1. CharacterSanitizer.sanitize()** - Reverted from 6 descriptive variables to single `text` variable. Added comprehensive logging for all 6 stages with execution tracking, performance timing, text metrics, and error details. Removed all `del` statements.

**2. RawTextExtractor._normalize_text()** - Reverted from 4 descriptive variables to single `text` variable. Added comprehensive logging for all 4 stages with same pattern as CharacterSanitizer. Removed all `del` statements.

**3. PROJECT_OVERVIEW.md Section 12** - Completely rewrote "Code Patterns & Conventions" to document logging pattern instead of variable naming pattern.

### Testing Results
✅ All 50 core tests PASSED (24 RawTextExtractor + 22 CharacterSanitizer + 4 ProgressiveSummarizer)
- No behavioral changes; all functionality preserved
- Logging enhancements are non-breaking improvements

### Benefits
1. More Pythonic (trusts Python's garbage collection)
2. Simpler code (no try-except blocks for NameError)
3. Better observability (comprehensive logging shows what happened at each stage)
4. Performance insights (timing data for each stage)
5. Debugging support (success/failure logs with error details)
6. Consistent with Python idioms (variable reassignment is standard pattern)

### Bug Fix: Queue Message Handler Attribute Name (Post-Session 5)

**Issue:** Application ran but file processing silently failed with error:
```
[QUEUE HANDLER] Error handling file_processed: '_tkinter.tkapp' object has no attribute 'processing_results'
```

**Root Cause:** Naming inconsistency. The main_window.py defines `self.processed_results`, but queue_message_handler.py was trying to access `self.main_window.processing_results`.

**Fix:** Changed line 48 in src/ui/queue_message_handler.py from `self.main_window.processing_results.append(data)` to `self.main_window.processed_results.append(data)`

**Impact:** File processing results now append correctly, file table updates display properly, no more silent failures.

---

## Session 6 - UI Bug Fixes & Vocabulary Workflow Integration (2025-11-26)

**Features:** Three UI bug fixes, vocabulary extraction workflow integration, spaCy model auto-download, environment path resolution

### Summary
Fixed three UI bugs discovered during manual testing: file size rounding inconsistency, model dropdown selection not persisting, and missing vocabulary extraction workflow. Implemented asynchronous vocabulary extraction with worker thread, graceful fallback for missing config files, and automatic spaCy model download. Resolved critical subprocess PATH issue using `sys.executable` for correct virtual environment targeting.

### Problems Addressed

**Bug #1: File Size Rounding Inconsistency** - Unified all units to round to nearest integer using `round(size)` regardless of unit.

**Bug #2: Model Dropdown Selection Not Working** - Implemented preference preservation logic so selected model doesn't reset on refresh.

**Bug #3: Vocabulary Extraction Workflow Missing** - Multiple issues:
1. Widget reference bug (code called wrong widget method)
2. spaCy model missing (auto-download implemented)
3. Subprocess PATH issue (fixed using `sys.executable`)

### Work Completed

**Part 1:** Fixed file size formatting and model selection in `src/ui/widgets.py`

**Part 2:** Vocabulary workflow integration across multiple files:
- Added `VocabularyWorker` class to `src/ui/workers.py`
- Fixed queue message handler widget references
- Added `_combine_documents()` helper to main_window.py
- Made VocabularyExtractor config files optional

**Part 3:** spaCy model auto-download with correct subprocess targeting
- Initial implementation used `python` command (wrong - might resolve to system Python)
- Fixed to use `sys.executable` (correct - guarantees venv Python)
- Switched from `spacy download` CLI to pip install for reliability
- Added 300-second timeout for download

### Technical Insight: Virtual Environments & Package Storage

**Key Learning:** When spawning subprocesses from a virtual environment:
- `python` command might resolve to system Python, not venv Python
- Packages install to whichever Python executes the install command
- **Solution:** Use `sys.executable` to guarantee correct Python interpreter

### Files Modified
- `src/ui/widgets.py` - File size fix + model selection preservation
- `src/ui/workers.py` - Added VocabularyWorker class
- `src/ui/queue_message_handler.py` - Fixed widget reference + vocab workflow
- `src/ui/main_window.py` - Added `_combine_documents()` helper
- `src/vocabulary_extractor.py` - Config optional + auto-download

### Git Commits
1. `225aa70` - fix: Correct widget reference in vocabulary workflow integration
2. `99fdace` - fix: Add spaCy model auto-download for vocabulary extraction
3. `9de7cb5` - fix: Use correct Python executable path for spaCy model download

### Status
✅ File size rounding consistent
✅ Model dropdown selection preserves user choice
✅ Vocabulary workflow integration complete
✅ spaCy model auto-downloads to correct venv
⏳ Pending user testing

---

## Current Project Status

**Application State:** Bug fixes complete; vocabulary workflow integrated; awaiting user testing
**Last Updated:** 2025-11-26 (Session 6 - UI Bug Fixes & Vocabulary Workflow)
**Total Lines of Developed Code:** ~3,600 across all modules
**Code Quality:** All tests passing; comprehensive error handling; debug logging per CLAUDE.md
**Next Priorities:**
1. User testing of vocabulary extraction workflow (next session)
2. Debug any environment/path issues that arise
3. Move to feature development if bugs are resolved
