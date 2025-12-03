# LocalScribe - Human Summary

## Project Status

**Current Branch:** `main`
**Application State:** ✅ Case Briefing Generator complete with few-shot prompting
**Tests:** 224 passing
**Sessions:** 42 completed
**Last Updated:** 2025-12-03 (Session 42 Part 3)

---

## Latest Session (Session 42 - Architecture + Performance + Prompt Engineering)

**Focus:** Finalize chunking architecture, fix performance, and improve extraction accuracy.

### Part 1: Architecture Decision ✅

**Decision:** Keep `DocumentChunker` for Case Briefing extraction.
- Neither chunker uses true semantic chunking — both are regex-based
- `DocumentChunker` has 45 legal-specific patterns vs. 8 in `ChunkingEngine`

### Part 2: Performance Fix 🚀

**Problem:** Case Briefing was intolerably slow (7 minutes for 7/155 chunks).
**Root Cause:** Hardcoded `max_workers=2` regardless of system resources.

**Solution:** Dynamic worker scaling based on CPU/RAM:

| File | Change |
|------|--------|
| `src/system_resources.py` | NEW: Calculates optimal workers |
| Settings slider | Resource usage (25-100%, default 75%) |
| `src/briefing/extractor.py` | Uses dynamic workers |

**Result on 12-core/16GB machine:**
- Before: 2 workers → After: 6 workers
- **~3x faster extraction**

### Part 3: Prompt Engineering - Preventing Hallucinations 🎯

**Problem:** LLM extracted example names from JSON schema (e.g., "John Smith").

**Research:**
- Google's Gemma 3 guidance: "Show patterns to follow, not anti-patterns to avoid"
- Few-shot prompting improves accuracy 10-12% over zero-shot
- Negative instructions ("don't hallucinate") are ineffective

**Solution:** External prompt file with 3 few-shot examples.

| File | Change |
|------|--------|
| `config/briefing_extraction_prompt.txt` | NEW: External prompt with 3 realistic examples |
| `src/briefing/extractor.py` | Loads prompt from external file (easy iteration) |
| `src/briefing/aggregator.py` | Added vocabulary aggregation |
| `src/briefing/formatter.py` | Added vocabulary section to output |

**Key Design:**
- 3 few-shot examples: complaint, answer/defense, medical records
- Consistent JSON structure across all examples
- New "vocabulary" field extracts technical/unusual terms for laypersons
- External file allows prompt iteration without code changes

### Session 42 Complete ✅

Architecture decided, performance optimized, hallucinations addressed.

---

## Previous Session (Session 40 - Bug Discovery & Fix)

**Focus:** Test Case Briefing feature with real documents — found and fixed critical bug.

### Bug Found & Fixed: DocumentChunker Paragraph Splitting

- **Symptom:** 5 docs → 5 chunks → 0 data extracted
- **Root Cause:** `_split_into_paragraphs()` split on double newlines, but OCR output uses single newlines
- **Result:** 43,262-char document became 1 chunk (too large for LLM)
- **Fix:** Added line-based fallback + force-split for oversized paragraphs

### Changes Made

| File | Changes |
|------|---------|
| `src/briefing/chunker.py` | Added `_split_on_lines()`, `_force_split_oversized()`, updated `_split_into_paragraphs()` |

### Test Results

- Before fix: 43,262 chars → 1 chunk
- After fix: 43,262 chars → ~24 chunks (avg 1,750 chars)
- All 224 tests pass

---

## Previous Session (Session 39 - UI Integration + Phase 4 Optimizations)

**Focus:** Integrate Case Briefing Generator into the UI and add performance optimizations.

### Part 1: UI Integration Complete

**Files Modified:**

| File | Changes |
|------|---------|
| `src/ui/workers.py` | Added `BriefingWorker` (background processing) |
| `src/ui/main_window.py` | Briefing task flow integration |
| `src/ui/dynamic_output.py` | Briefing display + export support |

**How It Works:**
1. User enables Q&A checkbox → triggers Case Briefing (replaces legacy Q&A)
2. `BriefingWorker` runs in background thread (doesn't freeze UI)
3. Progress shown in status bar
4. Output appears in dropdown as "Case Briefing"
5. Copy/Save to file works for briefing

### Part 2: Phase 4 Optimizations

**1. Parallelization:**
- Chunk extraction now uses `ThreadPoolExecutor`
- Default: 2 workers (conservative for Ollama GPU memory)
- Expected speedup: ~40% for multi-chunk documents

**2. Improved Prompts:**
- Explicit party identification rules in extraction prompt
- Clear definitions: plaintiff = filed lawsuit, defendant = being sued
- Medical malpractice hints: patient = plaintiff, doctor = defendant
- Better example schema with realistic names

### Case Briefing Generator: COMPLETE ✅

The full Map-Reduce pipeline is now production-ready:
```
Documents → Chunk → Extract → Aggregate → Synthesize → Format → Display
              ↓         ↓          ↓           ↓          ↓         ↓
          Section    Parallel   Fuzzy Name   Narrative  Plain/MD   UI Panel
          -aware    extraction  matching     from LLM   export     dropdown
```

---

## Previous Sessions (Sessions 36-38)

**Session 38 - Phase 3:** BriefingOrchestrator, BriefingFormatter, end-to-end test

**Session 37 - Phase 2:** DataAggregator (fuzzy name matching), NarrativeSynthesizer

**Session 36 - Phase 1:** DocumentChunker, ChunkExtractor, `generate_structured()` method

---

## Recent Sessions Summary

### Session 34 - Project Root Cleanup (2025-12-01)
Organized project root, created `scripts/` and `tests/manual/`, moved data files to proper directories. Workflow verified working.

### Session 33 - Codebase Organization & Cleanup (2025-12-01)
Created `src/prompting/` package from 4 orphan files, split `main_window.py` using mixin pattern, standardized logging imports. Cleaned up technical debt (empty dirs, backups, duplicates).

### Session 32 - Unified Package APIs (2025-12-01)
Created unified facade APIs for Q&A and summarization packages. All Q&A imports now from `src.qa`, all summarization from `src.summarization`. Updated ARCHITECTURE.md with hybrid retrieval diagrams.

### Session 31 - Hybrid BM25+ Retrieval (2025-12-01)
Created `src/retrieval/` package with BM25+ lexical search + FAISS semantic search. Hybrid approach solves "no information found" issue caused by embedding model not understanding legal terminology.

### Session 30 - Q&A/Vocab Integration Fixes (2025-12-01)
Fixed UI freeze during Q&A (background thread), placeholder code replaced with real QAWorker, dropdown visibility fixes. Identified root causes of "no information found" issue.

### Session 29 - Q&A-First Pivot (2025-11-30)
**Strategic Pivot:** From summarization-first to Q&A-first document analysis tool.
Complete UI rewrite: PySide6 → CustomTkinter with two-panel layout. Multi-corpus management system (Criminal, Civil, etc.). Task checkboxes: Q&A (ON), Vocabulary (ON), Summary (OFF with warning).

### Session 27-28 - Q&A Panel Feature (2025-11-30)
Complete Q&A UI leveraging FAISS vector search. New `src/qa/` package with QAOrchestrator, AnswerGenerator. Dual answer modes: Extraction (keyword, fast) vs Ollama (AI synthesis). 20 new tests.

### Session 25-26 - Multi-Algorithm Vocabulary + BM25 Corpus (2025-11-30)
Pluggable algorithms (NER, RAKE, BM25), registry pattern. ML feedback system with 👍/👎 columns, logistic regression meta-learner. BM25 corpus-based vocabulary (auto-enables at ≥5 docs).

---

## Key Features

### Document Processing
- Multi-format: PDF (digital & scanned), TXT, RTF
- OCR with Tesseract
- Smart preprocessing (headers, line numbers, Q&A notation)
- Parallel processing (2.5-3x speedup)

### AI Summarization
- Ollama backend (any model)
- Hierarchical map-reduce for multi-document
- Thread-through prompt templates
- Recursive length enforcement

### Vocabulary Extraction
- Multi-algorithm: NER + RAKE + BM25
- ML feedback learning
- Context-aware role detection
- Quality scoring and filtering

### Q&A System
- **NEW:** Hybrid retrieval (BM25+ + FAISS)
- BM25+ for exact legal terminology
- FAISS for semantic similarity
- Dual answer modes: Extraction & Ollama
- Selective export with checkboxes
- Follow-up questions

---

## File Directory (Key Files)

### Source Code Structure
```
src/
├── main.py                    # Entry point
├── config.py                  # Configuration constants
├── logging_config.py          # Unified logging
├── ai/                        # Ollama integration
├── extraction/                # PDF/TXT/RTF extraction
├── sanitization/              # Character sanitization
├── preprocessing/             # Header/footer removal, Q&A conversion
├── prompting/                 # Unified prompting API (Session 33)
│   ├── __init__.py            # Facade exports
│   ├── template_manager.py    # Template loading/management
│   ├── focus_extractor.py     # AI focus extraction
│   ├── adapters.py            # Stage-specific prompts
│   └── config.py              # Prompt parameters
├── briefing/                  # Case Briefing Generator (Sessions 36-38)
│   ├── __init__.py            # Package exports (all phases)
│   ├── chunker.py             # Phase 1: Section-aware document splitting
│   ├── extractor.py           # Phase 1: Per-chunk LLM extraction
│   ├── aggregator.py          # Phase 2: Merge/deduplicate with fuzzy matching
│   ├── synthesizer.py         # Phase 2: Narrative generation
│   ├── orchestrator.py        # Phase 3: Pipeline coordinator
│   └── formatter.py           # Phase 3: Output formatting
├── summarization/             # Multi-doc hierarchical summarization
├── vocabulary/                # Multi-algorithm extraction + ML feedback
│   └── algorithms/            # NER, RAKE, BM25 plugins
├── retrieval/                 # Hybrid retrieval system
│   └── algorithms/            # BM25+, FAISS plugins
├── vector_store/              # FAISS indexes + QARetriever
├── qa/                        # Q&A orchestrator + answer generator (being replaced)
└── ui/                        # CustomTkinter GUI
    ├── main_window.py         # Business logic
    ├── window_layout.py       # Layout mixin (Session 33)
    └── settings/              # Settings dialog system
```

### Documentation
- **PROJECT_OVERVIEW.md** - Technical specification (primary source of truth)
- **ARCHITECTURE.md** - Mermaid diagrams
- **development_log.md** - Timestamped change log
- **TODO.md** - Feature backlog

### Configuration
- `config/prompts/` - Summarization prompt templates
- `config/qa_questions.yaml` - Q&A questions
- `config/common_medical_legal.txt` - Vocabulary blacklist
- `config/briefing_extraction_prompt.txt` - Case Briefing few-shot prompt

---

## Development Setup

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Run tests
python -m pytest tests/ -v

# Start application
python src/main.py
```

**Requirements:** Python 3.11+, Ollama running locally, spaCy en_core_web_lg model
