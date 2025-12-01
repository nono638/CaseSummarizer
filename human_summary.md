# LocalScribe - Human Summary

## Project Status

**Current Branch:** `main`
**Application State:** 🟡 Q&A-first tool - Integration bugs being fixed
**Tests:** 207 passing
**Sessions:** 30 completed
**Last Updated:** 2025-12-01 (Session 30)

---

## Latest Session (Session 30 - Q&A/Vocab Integration Fixes)

**Focus:** Wire up the Q&A and vocabulary systems to the new CustomTkinter UI.

**Fixed:**
- ✅ UI freeze during Q&A (moved embeddings loading to background thread)
- ✅ Placeholder Q&A replaced with real QAWorker integration
- ✅ Dropdown visibility for empty result lists (`is not None` check)
- ✅ Added item counts to dropdown: "Rare Word List (N terms)", "Q&A Results (N)"

**Known Issues (see TODO.md):**
- 🔴 Vocabulary returns 0 terms (combine_document_texts may return empty)
- 🔴 Q&A answers all say "no information found" (low relevance scores)
- 🔴 Q&A not appearing in dropdown despite running
- 🟡 Need to switch from FAISS to BM25+ for better retrieval
- 🟡 Corpus name validation needed (prevent invalid filesystem chars)

---

## Recent Sessions Summary

### Session 29 - Q&A-First Pivot (2025-11-30)
**Strategic Pivot:** From summarization-first to Q&A-first document analysis tool.
Complete UI rewrite: PySide6 → CustomTkinter with two-panel layout. Multi-corpus management system (Criminal, Civil, etc.). Task checkboxes: Q&A (ON), Vocabulary (ON), Summary (OFF with warning).

### Session 28 - Q&A Display Bug Fix (2025-11-30)
Fixed Q&A results not appearing in UI. Changed `dynamic_output` → `summary_results` in queue_message_handler.py.

### Session 27 - Q&A Panel Feature (2025-11-30)
Complete Q&A UI leveraging FAISS vector search. New `src/qa/` package with QAOrchestrator, AnswerGenerator. Dual answer modes: Extraction (keyword, fast) vs Ollama (AI synthesis). QAPanel with toggle list for selective export, follow-up input, question editor dialog. 20 new tests.

### Session 26 - BM25 Corpus-Based Vocabulary (2025-11-30)
Third vocabulary algorithm using user's corpus. Auto-enables at ≥5 docs in `%APPDATA%/LocalScribe/corpus/`. Algorithm weights: NER (1.0), BM25 (0.8), RAKE (0.7). 20 new tests.

### Session 25 - Multi-Algorithm Vocabulary + ML Feedback (2025-11-30)
Refactored vocabulary_extractor.py (1336→580 lines). Pluggable algorithms (NER, RAKE), registry pattern. ML feedback system with 👍/👎 columns, logistic regression meta-learner. 23 new tests.

### Session 24 - FAISS Vector Store Infrastructure (2025-11-30)
RAG-based Q&A infrastructure. FAISS for file-based indexes (no database). Auto-creates vector store after extraction. 14 branching questions in YAML.

### Sessions 20-23 - Summarization & Quality (2025-11-29)
- Multi-document hierarchical map-reduce (Session 20)
- Thread-through prompt focus architecture (Session 21)
- Processing timer, human-readable durations (Session 22)
- Vocabulary CSV quality improvements, 40-60% noise reduction (Session 23)

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

### Q&A System (NEW)
- FAISS vector search
- Dual modes: Extraction & Ollama
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
├── summarization/             # Multi-doc hierarchical summarization
├── vocabulary/                # Multi-algorithm extraction + ML feedback
│   └── algorithms/            # NER, RAKE, BM25 plugins
├── vector_store/              # FAISS indexes
├── qa/                        # Q&A orchestrator + answer generator
└── ui/                        # CustomTkinter GUI
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
