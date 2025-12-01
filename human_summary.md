# LocalScribe - Human Summary

## Project Status

**Current Branch:** `main`
**Application State:** 🟢 Codebase organized - ready for testing
**Tests:** 224 passing
**Sessions:** 34 completed
**Last Updated:** 2025-12-01 (Session 34)

---

## Latest Session (Session 34 - Project Root Cleanup)

**Focus:** Organize project root - move files to proper directories, clean up artifacts.

**Part 1 - Test File Cleanup:**
- ✅ **Deleted 2 orphaned test files** - `test_onnx_simple.py`, `test_phi3_summary.py`
- ✅ **Created `tests/manual/`** - new directory for 6 manual integration tests

**Part 2 - Root Directory Cleanup:**
- ✅ **Created `scripts/`** - moved utility scripts (`check_spacy.py`, `download_onnx_models.py`)
- ✅ **Moved test data** - `test_simple_case.txt` → `tests/sample_docs/`
- ✅ **Moved word frequency file** - `Word_rarity-count_1w.txt` → `data/frequency/`
- ✅ **Updated `.gitignore`** - added `debug_flow.txt`, `generated_summary.txt`
- ✅ **Updated code references** - `src/config.py`, `tests/manual/test_ollama_workflow.py`

**Root Directory After Cleanup:**
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

---

## Recent Sessions Summary

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
├── prompting/                 # NEW (Session 33): Unified prompting API
│   ├── __init__.py            # Facade exports
│   ├── template_manager.py    # Template loading/management
│   ├── focus_extractor.py     # AI focus extraction
│   ├── adapters.py            # Stage-specific prompts
│   └── config.py              # Prompt parameters
├── summarization/             # Multi-doc hierarchical summarization
├── vocabulary/                # Multi-algorithm extraction + ML feedback
│   └── algorithms/            # NER, RAKE, BM25 plugins
├── retrieval/                 # Hybrid retrieval system
│   └── algorithms/            # BM25+, FAISS plugins
├── vector_store/              # FAISS indexes + QARetriever
├── qa/                        # Q&A orchestrator + answer generator
└── ui/                        # CustomTkinter GUI
    ├── main_window.py         # Business logic
    ├── window_layout.py       # NEW (Session 33): Layout mixin
    └── settings/              # Settings dialog system
```

### Documentation
- **PROJECT_OVERVIEW.md** - Technical specification (primary source of truth)
- **ARCHITECTURE.md** - Mermaid diagrams
- **development_log.md** - Timestamped change log
- **TODO.md** - Feature backlog

### Configuration
- `config/prompts/` - Prompt templates
- `config/qa_questions.yaml` - Q&A questions
- `config/common_medical_legal.txt` - Vocabulary blacklist

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
