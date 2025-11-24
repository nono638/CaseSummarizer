# Preprocessing Pipeline for Model Inference
**Purpose:** Clean extracted text (post-OCR/extraction, pre-model) for better summarization quality

---

## Architecture Overview

```
Two-Stage Cleaning:

Steps 1-2 (Current - raw_text_extractor.py):
  PDF/TXT/RTF → Extract text → Normalize (de-hyphenation, page removal, line filtering) → Output
  (Handles: OCR, dictionary confidence, basic normalization)

Step 3 (Proposed - preprocessing/):
  Smart Preprocessed text → Model-ready text → Feed to Ollama
  (Handles: Title pages, line numbers, headers/footers, Q./A. formatting)
```

---

## Proposed Module Structure

```
src/preprocessing/
├── __init__.py                    (exports PreprocessingPipeline)
├── base.py                        (BasePreprocessor abstract class)
├── title_page_remover.py          (Remove title/cover pages)
├── line_number_remover.py         (Remove line numbers from margin)
├── header_footer_remover.py       (Remove headers/footers)
├── qa_converter.py                (Convert "Q. text" → "Question: text")
└── pipeline.py                    (Orchestrate all preprocessors)
```

---

## Proposed Functions (Detailed)

### **1. BasePreprocessor (Abstract Base Class)**
**File:** `src/preprocessing/base.py`

```python
class BasePreprocessor(ABC):
    """Abstract base for all preprocessor implementations."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.logs = []  # Collect logs for reporting

    @abstractmethod
    def process(self, text: str) -> str:
        """
        Process text and return modified version.
        Must handle errors gracefully - return original text if fail.
        """
        pass

    def log(self, level: str, message: str):
        """Log a message with context."""
        self.logs.append({"level": level, "preprocessor": self.name, "message": message})
```

---

### **2. TitlePageRemover**
**File:** `src/preprocessing/title_page_remover.py`

**Purpose:** Detect and remove title/cover pages (often contain case number, date, firm names, etc.)

**Logic:**
```python
class TitlePageRemover(BasePreprocessor):
    def process(self, text: str) -> str:
        """
        Detect title page patterns and remove first N lines/paragraphs.

        Heuristic: Title pages typically:
        - Have short lines (case numbers, names)
        - Have low word count in first 500 chars
        - Contain legal-specific metadata (docket, filed, etc.)
        - Are separated by blank lines from body
        """
        # Strategy: Find first paragraph with >100 words
        # Everything before it is likely title/metadata

        # If successful: log lines removed, character count before/after
        # If fails: log warning, return original text
```

**Returns:** Text with title page removed (or original if couldn't determine)

---

### **3. LineNumberRemover**
**File:** `src/preprocessing/line_number_remover.py`

**Purpose:** Remove line numbers (1, 2, 3... 123, 124... etc.) that appear at line start

**Logic:**
```python
class LineNumberRemover(BasePreprocessor):
    def process(self, text: str) -> str:
        """
        Remove line numbers from left margin.

        Patterns to detect:
        - "^\\d+\\s+" (line start: "123 ")
        - "^\\d+\\\\s+text" (number, spaces, text)
        - Typically 1-4 digits followed by 2-4 spaces

        Algorithm:
        1. Split text into lines
        2. For each line, check if starts with numbers + spaces
        3. If regex matches AND rest of line is substantive, remove numbers
        4. Rejoin lines

        Safety: Don't remove if it looks like actual content (dates, quantities)
        """
        # Regex: ^\d{1,4}\s{2,4}(?=[A-Z])
        # Only remove if followed by capital letter (sentence start)

        # If successful: log count of removed numbers, sample before/after
        # If fails: log warning, return original
```

**Returns:** Text with line numbers removed

---

### **4. HeaderFooterRemover**
**File:** `src/preprocessing/header_footer_remover.py`

**Purpose:** Remove repetitive headers/footers that appear on every page

**Logic:**
```python
class HeaderFooterRemover(BasePreprocessor):
    def process(self, text: str) -> str:
        """
        Detect and remove repetitive headers/footers.

        Heuristic: Headers/footers are:
        - Repeated on multiple pages (appear 3+ times)
        - Short (usually <20 words)
        - Contain case/page metadata (case number, page numbers, firm name)
        - Separated by page breaks or line groups

        Algorithm:
        1. Split into potential page sections (separated by \n\n\n+)
        2. Extract first/last 2 lines of each section
        3. Find patterns that repeat across sections
        4. Remove identified patterns

        Common patterns:
        - "Page X of Y"
        - "Case No. XXX" (repeated)
        - "Smith & Associates" (firm name)
        - "---" (separators)
        """
        # If successful: log pattern count, total lines removed
        # If fails: log warning, return original
```

**Returns:** Text with headers/footers removed

---

### **5. QAConverter**
**File:** `src/preprocessing/qa_converter.py`

**Purpose:** Convert deposition Q./A. format to clearer format for model

**Logic:**
```python
class QAConverter(BasePreprocessor):
    def process(self, text: str) -> str:
        """
        Convert "Q. text" / "A. text" to "Question: text" / "Answer: text"

        This helps model understand conversational structure better.

        Patterns to convert:
        - "^Q\\s+(.+)$" → "Question: $1"
        - "^A\\s+(.+)$" → "Answer: $1"
        - Handles variations: "Q:", "Q -", "A:", "A -", etc.

        Algorithm:
        1. Detect if text contains Q./A. patterns (sample first 100 lines)
        2. If Q./A. found in >5% of lines, apply conversion
        3. Use regex to replace patterns
        4. Preserve line breaks

        Safety: Only apply if text clearly uses Q./A. format
        """
        # If successful: log count of Q./A. converted
        # If none found: log info "No Q./A. patterns detected", return original
        # If fails: log warning, return original
```

**Returns:** Text with Q./A. expanded to full words

---

### **6. PreprocessingPipeline**
**File:** `src/preprocessing/pipeline.py`

**Purpose:** Orchestrate all preprocessors and handle failures gracefully

**Logic:**
```python
class PreprocessingPipeline:
    def __init__(self):
        self.preprocessors = [
            TitlePageRemover("title_page_removal"),
            LineNumberRemover("line_number_removal"),
            HeaderFooterRemover("header_footer_removal"),
            QAConverter("qa_conversion"),
        ]
        self.logs = []

    def process(self, text: str, filename: str = "") -> dict:
        """
        Run all preprocessors in sequence.

        Args:
            text: Cleaned text from cleaner.py
            filename: Optional filename for context in logs

        Returns:
            {
                "text": preprocessed text (or original if all fail),
                "logs": list of log entries from each preprocessor,
                "stats": {
                    "original_chars": N,
                    "final_chars": N,
                    "preprocessors_applied": ["title_page", "qa_conversion"],
                    "preprocessing_status": "success" | "partial" | "skipped"
                }
            }
        """

        current_text = text
        stats = {
            "original_chars": len(text),
            "preprocessors_applied": [],
            "preprocessing_status": "success"
        }

        for preprocessor in self.preprocessors:
            try:
                new_text = preprocessor.process(current_text)
                if new_text != current_text:
                    stats["preprocessors_applied"].append(preprocessor.name)
                current_text = new_text
                self.logs.extend(preprocessor.logs)
            except Exception as e:
                # Fail gracefully
                self.logs.append({
                    "level": "ERROR",
                    "preprocessor": preprocessor.name,
                    "message": f"Exception in {preprocessor.name}: {str(e)}. Continuing with original text."
                })
                stats["preprocessing_status"] = "partial"
                # Continue with current text (not modified by this preprocessor)

        stats["final_chars"] = len(current_text)

        return {
            "text": current_text,
            "logs": self.logs,
            "stats": stats
        }
```

**Usage in model inference:**
```python
# In OllamaModelManager.generate_text() before calling Ollama:
pipeline = PreprocessingPipeline()
result = pipeline.process(combined_text, filename="case_documents")
text_for_model = result["text"]

# Log preprocessing results
for log in result["logs"]:
    if log["level"] == "ERROR":
        logger.error(f"{log['preprocessor']}: {log['message']}")
    else:
        logger.debug(f"{log['preprocessor']}: {log['message']}")
```

---

## Graceful Failure Strategy

Each preprocessor:
1. **Attempts** its transformation
2. **Catches exceptions** and logs them
3. **Returns original text** if transformation fails
4. **Logs what happened** so user/developer knows

Benefits:
- ✅ Text never gets corrupted
- ✅ Model inference always runs (even if preprocessing partially fails)
- ✅ Logs show what worked and what didn't
- ✅ Users can see in debug logs why certain cleanups didn't apply

---

## Integration Points

**When to call PreprocessingPipeline:**

```
User Flow:
1. Select documents → cleaner.py processes them
2. Choose model & summary options
3. Click "Generate Summary"
4. [NEW] PreprocessingPipeline.process(combined_text)
5. Feed result["text"] to OllamaModelManager.generate_text()
6. Display logs in debug panel if DEBUG=true
```

**File modifications needed:**
- `src/ui/workers.py`: Call pipeline before `model_manager.generate_text()`
- `src/ai/ollama_model_manager.py`: Accept preprocessed text
- `config.py`: Add `PREPROCESSING_DEBUG = DEBUG` flag

---

## Testing Strategy

```python
# tests/test_preprocessing.py

def test_title_page_remover():
    """Test with sampleDocuments PDFs."""
    text = load_sample_pdf()
    result = TitlePageRemover().process(text)
    assert "CASE NO." not in result[:200]  # Title page removed
    assert "plaintiff" in result  # Body preserved

def test_line_number_remover():
    """Test with transcript containing line numbers."""
    text = "1   Q. What happened next?\n2   A. The defendant..."
    result = LineNumberRemover().process(text)
    assert "Q. What happened" in result
    assert "1   Q." not in result

def test_qa_converter():
    """Test Q./A. expansion."""
    text = "Q. What is your name?\nA. John Smith."
    result = QAConverter().process(text)
    assert "Question:" in result
    assert "Answer:" in result

def test_pipeline_graceful_failure():
    """Test that pipeline doesn't crash if one preprocessor fails."""
    bad_preprocessor = MockBrokenPreprocessor()
    pipeline = PreprocessingPipeline()
    result = pipeline.process("test text")
    assert result["text"] == "test text"  # Original preserved
    assert "ERROR" in str(result["logs"])  # Error logged
```

---

## Documentation Updates Needed

1. **CLAUDE.md** - Add Phase 3 definition: "Preprocessing for Model Inference"
2. **human_summary.md** - Add to Phase 2 progress
3. **development_log.md** - Log completion of preprocessing module
4. **Project_Specification** - Add Section 5.5: "Pre-Model Text Preprocessing"
5. **README.md** - Document preprocessing pipeline usage

---

## Implementation Estimate

- Create base.py: 10 min
- Create 4 preprocessors: 40 min (10 min each)
- Create pipeline: 15 min
- Integration into workers.py: 10 min
- Tests: 15 min
- Documentation updates: 10 min

**Total: ~1.5 hours**

You have ~1.5 hours remaining. This is a perfect scope match!

---

**Ready to implement? Or would you like me to adjust the design first?**
