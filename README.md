# LocalScribe

**100% Offline Legal Document Processor for Court Reporters**

LocalScribe is a private, secure Windows desktop application that processes legal documents entirely on your computer. No data ever leaves your machine, ensuring complete PII/PHI protection. Uses local Ollama AI models for document summarization with zero cloud connectivity.

## Document Processing Pipeline

LocalScribe implements a **6-step document processing pipeline**:

1. **Text Extraction** - Extracts raw text from PDFs (digital & OCR), TXT, RTF files with confidence scoring
2. **Basic Normalization** - Removes page numbers, de-hyphenates lines, filters junk content while preserving legal terms
3. **Smart Preprocessing** - Removes title pages, headers/footers, line numbers, converts Q./A. format (planned)
4. **Vocabulary Extraction** - Identifies unusual terms, categorizes them, and provides definitions
5. **Semantic Chunking** - Uses LangChain to split documents into semantically coherent chunks
6. **AI Summarization** - Generates both per-document and meta-summaries using local Ollama models

## Features

- **Multi-Document Processing:** Combine complaints, answers, exhibits, and motions into one comprehensive case summary
- **Smart OCR Detection:** Automatic OCR for scanned documents using Tesseract
- **Text Extraction & Normalization:** Removes headers, footers, and junk while preserving legal content (Steps 1-2)
- **Local AI Summarization:** Runs Ollama AI models completely offline on your CPU (no internet required)
- **Vocabulary Extraction:** Identifies technical terms and proper nouns with definitions (Step 4)
- **Parallel Processing:** Process multiple documents concurrently with user-controlled CPU allocation
- **Real-Time System Monitor:** View CPU and RAM usage in status bar
- **Model-Aware Formatting:** Automatically detects model type (Llama, Mistral, Gemma, etc.) and applies correct instruction format

## Current Status

**Phase 2.7: Complete** ✅ (Production-ready UI with system monitoring and model compatibility)

### Phase 1: Complete ✅
- ✅ Text extraction from digital PDFs, TXT, and RTF files (Step 1)
- ✅ OCR processing with Tesseract
- ✅ Basic text normalization (Step 2): de-hyphenation, page removal, whitespace normalization
- ✅ Case number extraction
- ✅ Confidence scoring with error handling
- ✅ 24 passing unit tests

### Phase 2: Complete ✅
- ✅ **2.1** - UI refactor to CustomTkinter with native look and feel
- ✅ **2.2** - Document prioritization system
- ✅ **2.3** - AI summary generation with Ollama integration
- ✅ **2.4** - Streaming token display with real-time updates
- ✅ **2.5** - Parallel document processing with CPU allocation control
- ✅ **2.6** - System monitor widget (CPU%, RAM display with CPU model on hover)
- ✅ **2.7** - Model-aware prompt formatting (auto-detects instruction format per model)

### Phase 3: Planned 🔜
- Smart preprocessing pipeline (remove title pages, headers/footers, convert Q./A. format)
- Enhanced vocabulary definitions
- License server integration
- Advanced features (post-v1.0)

### What's Next
- Phase 3: Advanced text preprocessing
- Phase 4+: Enhanced vocabulary, licensing, distribution packaging

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

### Command Line Interface (Text Extraction - Steps 1-2)

**NOTE:** Make sure virtual environment is activated first: `venv\Scripts\activate`

Extract and normalize text from legal documents:

### Basic Usage
```bash
python -m src.extraction.raw_text_extractor --input document.pdf
```

### Process Multiple Files
```bash
python -m src.extraction.raw_text_extractor --input complaint.pdf answer.pdf exhibit_a.pdf
```

### Specify Output Directory
```bash
python -m src.extraction.raw_text_extractor --input *.pdf --output-dir ./extracted
```

### Debug Mode
```bash
# Windows PowerShell
$env:DEBUG="true"; python -m src.extraction.raw_text_extractor --input test.pdf

# Windows Command Prompt
set DEBUG=true && python -m src.extraction.raw_text_extractor --input test.pdf

# Mac/Linux
DEBUG=true python -m src.extraction.raw_text_extractor --input test.pdf
```

This will show:
- Verbose logging of all processing steps
- Performance timing for each operation (Step 1, Step 2)
- Confidence scoring and text quality metrics
- Detailed error information

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run specific test file (Steps 1-2 extraction tests):
```bash
pytest tests/test_raw_text_extractor.py -v
```

## Project Structure

```
CaseSummarizer/
├── src/
│   ├── main.py              # GUI application entry point
│   ├── config.py            # Configuration constants
│   ├── logging_config.py    # Unified logging with debug mode
│   ├── extraction/          # Steps 1-2: Text extraction & basic normalization
│   │   ├── raw_text_extractor.py  # Core extraction engine
│   │   └── __init__.py            # Package exports
│   ├── ai/
│   │   ├── ollama_model_manager.py  # Ollama integration (Step 6)
│   │   └── prompt_formatter.py      # Model-aware prompt formatting
│   ├── prompting/           # Session 33: Unified prompt management
│   │   ├── __init__.py            # Facade API exports
│   │   ├── template_manager.py    # Prompt discovery & validation
│   │   ├── focus_extractor.py     # AI focus area extraction
│   │   ├── adapters.py            # Stage-specific prompt generation
│   │   └── config.py              # Prompt parameters
│   ├── ui/
│   │   ├── main_window.py   # Main application window (business logic)
│   │   ├── window_layout.py # Session 33: UI layout mixin
│   │   ├── workers.py       # Background processing threads
│   │   ├── widgets.py       # Custom widgets (file table, summary display)
│   │   ├── system_monitor.py # Real-time CPU/RAM monitor
│   │   ├── dynamic_output.py # Results display widget
│   │   └── dialogs.py       # Progress dialogs
│   ├── summarization/       # Multi-document summarization
│   ├── vocabulary/          # Multi-algorithm vocabulary extraction
│   ├── qa/                  # Q&A orchestration
│   ├── retrieval/           # Hybrid BM25+/FAISS retrieval
│   ├── vector_store/        # FAISS vector indexes
│   ├── user_preferences.py  # User settings persistence
│   └── utils/
│       └── logger.py        # Backward-compat logging wrapper
├── tests/                   # 224 unit tests
│   └── manual/              # Manual integration tests (require Ollama)
├── config/
│   ├── prompt_parameters.json  # AI model settings (temperature, top_p, etc.)
│   └── prompts/                # Prompt templates by model
├── requirements.txt         # Python dependencies
└── README.md               # This file

Documentation Files:
├── ARCHITECTURE.md                       # Mermaid architecture diagrams
├── development_log.md                    # Timestamped development history
├── human_summary.md                      # High-level project status
└── PROJECT_OVERVIEW.md                   # Complete technical spec (PRIMARY SOURCE OF TRUTH)
```

### Planned Directory Structure (v3.0)

When Steps 3-6 are refactored into modular packages:

```
src/
├── extraction/           (Steps 1-2: ✅ Implemented)
├── preprocessing/        (Step 3: Planned)
├── vocabulary/          (Step 4: Planned refactor)
├── chunking/            (Step 5: Planned refactor)
├── summarization/       (Step 6: Planned refactor)
└── ai/                  (Model integrations)
```

## Documentation

**PRIMARY SOURCE OF TRUTH:**
- **PROJECT_OVERVIEW.md** - Complete technical specification with architecture, implementation details, and design decisions

**Development & Status:**
- **development_log.md** - Timestamped log of all code changes, features, and bug fixes
- **human_summary.md** - High-level status report updated at end of each session
- **PREPROCESSING_PROPOSAL.md** - Detailed design for Step 3 (Smart Preprocessing Pipeline)
- **scratchpad.md** - Brainstorming document for future ideas and refinements

## Development Guidelines

This project follows strict development guidelines documented in `claude.md`:

- **Modularity:** Code is modular and extensible
- **Debug Mode:** All features include verbose debug logging
- **Documentation:** All changes logged in development_log.md
- **File Size Limit:** No file exceeds 1500 lines
- **Error Handling:** User-friendly messages with detailed logging
- **Testing:** Tests for complex business logic

## Models & AI Integration

LocalScribe uses **Ollama** for local AI model execution. The following models are compatible and recommended:

- **Phi 3.5/3.1** (1-3.8B parameters) - Excellent quality, very fast (recommended)
- **Mistral 7B** (7B parameters) - Higher quality summaries, moderate speed
- **Llama 2 13B** (13B parameters) - Highest quality, slower on CPU
- **Gemma 2B/7B** - Google's open models, good performance
- **TinyLlama 1.1B** - Ultra-lightweight, good for resource-constrained systems

All models run entirely offline on your CPU with zero cloud connectivity. Download via Ollama:
```bash
ollama pull phi:3.5
ollama pull mistral:7b
```

## License

[To be determined - Commercial application]

Model Requirements:
- Ollama models are open-source and respect their respective licenses (Meta Llama, Mistral AI, etc.)
- No external API calls or cloud dependencies
- Complete data privacy guaranteed

## Project Information

**Architecture:** 6-step document processing pipeline
**Tech Stack:** Python 3.10+, CustomTkinter (UI), Ollama (AI), Tesseract (OCR), LangChain (chunking)
**Primary Source of Truth:** PROJECT_OVERVIEW.md
**Status:** Phase 2.7 Complete - Production-Ready UI with AI Integration
