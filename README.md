# LocalScribe

**100% Offline Legal Document Processor for Court Reporters**

LocalScribe is a private, secure Windows desktop application that processes legal documents entirely on your computer. No data ever leaves your machine, ensuring complete PII/PHI protection.

## Features

- **Multi-Document Processing:** Combine complaints, answers, exhibits, and motions into one comprehensive case summary
- **Smart OCR:** Automatic detection and OCR processing of scanned documents
- **Intelligent Text Cleaning:** Removes headers, footers, and junk while preserving legal content
- **Local AI:** Runs Google Gemma 2 models completely offline on your CPU
- **Vocabulary Extraction:** Identifies technical terms and proper nouns with definitions

## Current Status

**Phase 1: Pre-processing Engine** (In Progress)

The document cleaning module (`src/cleaner.py`) has been implemented with:
- PDF text extraction (digital PDFs)
- OCR processing for scanned documents
- Intelligent text cleaning rules
- Command-line interface for testing

### What's Working
- ✅ Text extraction from digital PDFs
- ✅ OCR processing with Tesseract
- ✅ Confidence scoring
- ✅ Text cleaning (line filtering, de-hyphenation, whitespace normalization)
- ✅ Error handling (file size limits, corrupted files, password-protected PDFs)
- ✅ Debug mode with performance timing

### What's Next
- Phase 2: PySide6 UI development
- Phase 3: AI model integration
- Phase 4: Vocabulary extraction
- Phase 5: License system
- Phase 6: Settings and polish
- Phase 7: Packaging for distribution

## Requirements

- Python 3.10+
- Windows 10/11 (64-bit)
- 16GB RAM minimum (32GB recommended)
- Tesseract OCR (for scanned documents)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd CaseSummarizer
```

2. Create and activate virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Mac/Linux
source venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install Tesseract OCR:
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Add to system PATH

5. Download NLTK data:
```python
python -c "import nltk; nltk.download('words')"
```

**IMPORTANT:** Always activate the virtual environment before running any code:
```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

## Usage (Phase 1 - Command Line)

**NOTE:** Make sure virtual environment is activated first: `venv\Scripts\activate`

### Basic Usage
```bash
python -m src.cleaner --input document.pdf
```

### Process Multiple Files
```bash
python -m src.cleaner --input complaint.pdf answer.pdf exhibit_a.pdf
```

### Specify Output Directory
```bash
python -m src.cleaner --input *.pdf --output-dir ./cleaned
```

### Debug Mode
```bash
# Windows PowerShell
$env:DEBUG="true"; python -m src.cleaner --input test.pdf

# Windows Command Prompt
set DEBUG=true && python -m src.cleaner --input test.pdf

# Mac/Linux
DEBUG=true python -m src.cleaner --input test.pdf
```

This will show:
- Verbose logging of all processing steps
- Performance timing for each operation
- Detailed error information

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_cleaner.py -v
```

## Project Structure

```
CaseSummarizer/
├── src/
│   ├── cleaner.py          # Document pre-processing engine
│   ├── config.py           # Configuration constants
│   └── utils/
│       └── logger.py       # Logging with debug mode support
├── tests/
│   └── test_cleaner.py     # Unit tests for cleaner module
├── data/
│   ├── keywords/           # Legal keyword lists (to be added)
│   └── frequency/          # Word frequency lists (to be added)
├── requirements.txt        # Python dependencies
└── docs/                   # Documentation

Documentation Files:
├── project_overview.md            # Main project reference
├── development_log.md             # Development history
├── human_summary.md               # High-level status
├── scratchpad.md                  # Future ideas
└── Project_Specification_LocalScribe_v2.0_FINAL.md  # Complete spec
```

## Documentation

- **project_overview.md** - Quick reference for project goals, tech stack, and current status
- **development_log.md** - Detailed log of all changes and features
- **Project_Specification_LocalScribe_v2.0_FINAL.md** - Complete technical specification (1148 lines)

## Development Guidelines

This project follows strict development guidelines documented in `claude.md`:

- **Modularity:** Code is modular and extensible
- **Debug Mode:** All features include verbose debug logging
- **Documentation:** All changes logged in development_log.md
- **File Size Limit:** No file exceeds 1500 lines
- **Error Handling:** User-friendly messages with detailed logging
- **Testing:** Tests for complex business logic

## License

[To be determined - Commercial application]

Models: Google Gemma 2 (requires attribution per Google's terms)

## Acknowledgments

Powered by Google Gemma 2 models
