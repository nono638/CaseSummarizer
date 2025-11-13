# LocalScribe - Project Overview

## What We're Building
LocalScribe is a **100% offline, private Windows desktop application** for court reporters. It processes multiple legal documents (complaints, answers, exhibits, motions) to generate ONE comprehensive case-level summary, ensuring PII/PHI never leaves the user's computer.

## Tech Stack
- **Language:** Python 3.10+
- **UI Framework:** PySide6 (Qt for Python)
- **Local AI:** llama-cpp-python (runs GGUF models on CPU)
- **OCR:** Tesseract (via pytesseract)
- **PDF Handling:** pdfplumber
- **PDF to Image:** pdf2image
- **NLP:** nltk
- **Packaging:** PyInstaller

## Project Structure
```
CaseSummarizer/
├── src/
│   ├── cleaner.py          # Document preprocessing engine
│   ├── ai_processor.py     # AI model integration
│   ├── ui/                 # PySide6 UI components
│   ├── license/            # License validation system
│   └── utils/              # Shared utilities
├── data/
│   ├── keywords/           # Legal keyword lists (jurisdiction-specific)
│   └── frequency/          # Google word frequency list
├── tests/                  # Unit and integration tests
├── requirements.txt        # Python dependencies
└── docs/                   # Additional documentation
```

## The 4-Step Pipeline
1. **File Ingest:** User selects documents (PDF, TXT, RTF)
2. **Pre-processing:** Extract clean text + OCR confidence scores
3. **File Selection:** User reviews and selects documents to process
4. **AI Processing:** Combined documents fed to local AI for case-level analysis
5. **Output:** Display case summary + vocabulary list

## Key Features
- **Digital PDF Text Extraction:** Fast extraction from digital PDFs
- **OCR for Scanned Documents:** Tesseract OCR with confidence scoring
- **Intelligent Text Cleaning:** Removes headers, footers, page numbers while preserving legal content
- **Document Prioritization:** Smart truncation based on document importance (complaint > exhibits)
- **Streaming AI Output:** Real-time text generation with cancel capability
- **Vocabulary Extraction:** Identifies rare terms and proper nouns with definitions
- **License System:** Download quotas for AI models via license server
- **Debug Mode:** Verbose logging and performance timing

## AI Models
- **Standard Model:** gemma-2-9b-it-q4_k_m.gguf (~7GB, 10-27 min processing)
- **Pro Model:** gemma-2-27b-it-q4_k_m.gguf (~22GB, 48-95 min processing)

Models hosted on Dropbox, downloaded via license validation system.

## Development Phases
**Current Phase:** Phase 1 - Pre-processing Engine
1. ✓ Phase 1: Pre-processing Engine (2-3 weeks) ← **YOU ARE HERE**
2. Phase 2: Basic UI Shell (2 weeks)
3. Phase 3: AI Integration (2-3 weeks)
4. Phase 4: Vocabulary & Definitions (1-2 weeks)
5. Phase 5: License System Integration (1 week)
6. Phase 6: Settings & Polish (1-2 weeks)
7. Phase 7: Packaging & Distribution (1 week)

**Estimated Timeline:** 10-14 weeks total

## Current Focus: Phase 1 Goals
Build a standalone, testable `cleaner.py` module that:
- Processes PDF, TXT, RTF files from command line
- Extracts text using pdfplumber
- Detects scanned PDFs and performs OCR
- Applies intelligent text cleaning rules
- Returns confidence scores and processing status
- Handles errors gracefully (corrupted files, password-protected, size limits)

## Coding Patterns
*To be documented as patterns emerge during development*

## Common Commands
```bash
# Run cleaner in debug mode
DEBUG=true python cleaner.py --input file.pdf

# Process multiple files
python cleaner.py --input file1.pdf file2.pdf --output-dir ./cleaned

# Run tests
pytest tests/
```

## File Boundaries
**Safe to Edit:**
- All files in `src/` during active development
- `requirements.txt` when adding dependencies
- Test files in `tests/`
- Documentation files (except project_overview.md without permission)

**Avoid Editing:**
- `Project_Specification_LocalScribe_v2.0_FINAL.md` (original specification, reference only)

## Reference Documentation
For complete technical specifications, see:
- `Project_Specification_LocalScribe_v2.0_FINAL.md` (sections 1-11)
- Section 5: Pre-processing Pipeline details
- Section 9.1: Phase 1 implementation requirements
