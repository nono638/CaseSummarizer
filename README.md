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

**Phase 2: Desktop UI** (In Progress)

### Phase 1: Complete ✅
- ✅ Text extraction from digital PDFs, TXT, and RTF files
- ✅ OCR processing with Tesseract
- ✅ Confidence scoring
- ✅ Text cleaning (line filtering, de-hyphenation, whitespace normalization)
- ✅ Case number extraction
- ✅ Error handling (file size limits, corrupted files, password-protected PDFs)
- ✅ Debug mode with performance timing
- ✅ 24 passing unit tests

### Phase 2: Desktop UI (Current)
- ✅ PySide6 main window with file selection
- ✅ File Review Table showing processing results
- ✅ Background processing with progress indicators
- ✅ Status indicators (Ready/Warning/Failed)
- ✅ Integration with DocumentCleaner
- ✅ Error dialogs and user feedback

### What's Next
- Phase 3: AI model integration (summary generation)
- Phase 4: Vocabulary extraction
- Phase 5: License system
- Phase 6: Settings and polish
- Phase 7: Packaging for distribution

## Requirements

- Python 3.10+
- Windows 10/11 (64-bit)
- 8GB RAM minimum (16GB recommended)
- Tesseract OCR (for scanned documents)
- **Ollama** - For AI-powered document summarization (see setup below)

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

6. **Install and Configure Ollama** (for AI document summarization):

LocalScribe uses Ollama to run lightweight AI models locally. Ollama is a separate service that runs independently.

**Step 1: Download Ollama**
- Visit: https://ollama.ai
- Download the Windows installer
- Run the installer and follow the prompts
- This will start Ollama as a background service on port 11434

**Step 2: Download a model**
Open PowerShell or Command Prompt and run:
```bash
# Download Phi 1.5B (recommended - excellent quality, very fast)
ollama pull phi:1.5b

# Alternative: Download TinyLlama 1.1B (if you have limited resources)
ollama pull tinyllama:1.1b
```

This downloads the model (~1-2 GB) and may take a few minutes.

**Step 3: Verify Ollama is running**
Test the connection:
```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response listing available models.

**Note for Windows Users:**
- Ollama runs automatically in the background after installation
- You can verify it's running by checking the system tray (look for Ollama icon)
- If not running, search for "Ollama" in Windows search and launch it

**Available Models** (from https://ollama.ai/library):
- `phi:1.5b` - Recommended (excellent quality, very fast, ~2GB)
- `tinyllama:1.1b` - Ultra-light (~1.1GB)
- `neural-chat:7b` - Higher quality (~4GB, slower)

**IMPORTANT:** Always activate the virtual environment before running any code:
```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

## Usage

### Desktop GUI (Phase 2 - Recommended)

**NOTE:** Make sure virtual environment is activated first: `venv\Scripts\activate`

Launch the desktop application:
```bash
python -m src.main
```

**Features:**
- **File Selection:** Click "Select Files..." or use File → Select Files (Ctrl+O)
- **Automatic Processing:** Selected files are automatically processed with OCR detection
- **File Review Table:** View processing results with confidence scores
  - ✓ Ready (green): High confidence, ready for AI processing
  - ⚠ Warning (yellow): Low confidence (<70%), may be unreliable
  - ✗ Failed (red): Processing error
- **Include/Exclude:** Use checkboxes to select files for AI processing (Phase 3)
- **Progress Tracking:** Real-time progress bar and status updates

**Supported Formats:**
- PDF (digital and scanned)
- TXT (plain text)
- RTF (rich text format)

### Command Line Interface (Phase 1)

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
│   ├── main.py             # GUI application entry point
│   ├── cleaner.py          # Document pre-processing engine
│   ├── config.py           # Configuration constants
│   ├── ui/
│   │   ├── main_window.py  # Main application window
│   │   └── widgets.py      # Custom widgets (File Review Table)
│   └── utils/
│       └── logger.py       # Logging with debug mode support
├── tests/
│   ├── test_cleaner.py     # Unit tests for cleaner module
│   └── sample_docs/        # Sample documents for testing
├── data/
│   ├── keywords/           # Legal keyword lists (to be added)
│   └── frequency/          # Word frequency lists (to be added)
├── requirements.txt        # Python dependencies
└── docs/                   # Documentation

Documentation Files:
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
