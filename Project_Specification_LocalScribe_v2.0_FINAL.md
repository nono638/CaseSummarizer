# Project Specification: LocalScribe (v2.0 - FINAL)

## 1. Core Mission
Build a **100% offline, private, commercial Windows desktop application** ("LocalScribe") for court reporters. The app's primary function is to solve the PII/PHI liability problem by ensuring sensitive legal documents *never* leave the user's computer.

**Key Principle:** This app processes MULTIPLE documents (complaint, answer, exhibits, motions, etc.) to generate ONE comprehensive case-level summary, not individual document summaries.

---

## 2. Core Features (The 4-Step Pipeline)

The app executes a 4-step process:

1.  **File Ingest:** User selects one or more documents (PDF, TXT, RTF).
2.  **Pre-processing (The "Sniffer" & "Cleaner"):** The app extracts clean, usable text from each document and provides OCR confidence scores.
3.  **File Selection:** User reviews OCR confidence scores and selects which documents to include in processing.
4.  **AI Processing (The "Brain"):** All selected documents are combined and fed to a local AI model for case-level analysis.
5.  **Output Generation:** The app displays two final products: a case summary and a vocabulary list.

---

## 3. Technical Stack

### 3.1 Required Technologies
* **Language:** Python 3.10+
* **UI Framework:** **PySide6** (Qt for Python - LGPL-licensed for commercial use)
* **Local AI Engine:** **`llama-cpp-python`** (to run GGUF models on CPU with streaming support)
* **Local OCR Engine:** **Tesseract** (via `pytesseract`). Must be bundled with the application.
* **PDF Handling:** **`pdfplumber`** (MIT license - safe for commercial use)
* **PDF to Image:** **`pdf2image`** (for OCR preprocessing)
* **NLP Tools:** **`nltk`** for word frequency lists and basic text processing
* **Packaging:** **PyInstaller** (to create standalone `.exe`)

### 3.2 External Data Dependencies
* **Google Word Frequency List:** For rare word detection (333k most common words)
* **Downloadable Filter Lists (from Dropbox):**
  * Legal keyword lists (e.g., `legal_keywords_ny.txt`, `legal_keywords_california.txt`)
  * Document type priority rules (e.g., `document_priority_ny.txt`)
* **AI Models:** Gemma 2 GGUF models (hosted on Dropbox, downloaded via license system)

### 3.3 License Compliance
* **Tesseract:** Apache 2.0 ✓
* **pdfplumber:** MIT ✓
* **PySide6:** LGPL ✓ (commercial use allowed)
* **Gemma 2 Models:** Google's terms allow commercial use with attribution ✓
* **Attribution requirement:** Display in About dialog: "Powered by Google Gemma 2 models"

---

## 4. Model Distribution & Licensing System

### 4.1 Model Hosting Strategy
* **Host models on Dropbox Business** account (1 TB bandwidth/day limit)
* Two model sizes available:
  * **Standard Model:** `gemma-2-9b-it-q4_k_m.gguf` (~7GB) - Fast, good quality
  * **Pro Model:** `gemma-2-27b-it-q4_k_m.gguf` (~22GB) - Slow, best quality
* Bandwidth capacity: ~143 downloads/day of Standard model within 1TB limit

### 4.2 License Server Integration

**Note:** The license server itself is a separate system (outside this spec). LocalScribe communicates with it via HTTP API.

**License System Flow:**
1.  **User Registration:** User obtains a license key through the developer's website/payment system
2.  **App Launch:** On first launch, LocalScribe prompts for license key
3.  **License Validation API Call:**
    ```
    POST /api/validate_license
    Body: {"license_key": "USER_KEY_HERE", "action": "download_request"}
    Response: {
      "valid": true/false,
      "download_allowed": true/false,
      "download_url": "https://dropbox.com/...",
      "quota_remaining": {"daily": 0, "weekly": 1, "monthly": 3, "annual": 10},
      "next_available": "2025-11-13T00:00:00Z"
    }
    ```
4.  **Download Quotas per License:**
    * Daily: 1 download
    * Weekly: 2 downloads
    * Monthly: 4 downloads
    * Annual: 12 downloads
5.  **Quota Exceeded Behavior:** Display message: "Download limit reached. Your license allows [X] downloads per [period]. Next download available on [date]."
6.  **Download Process:** If approved, use the returned Dropbox URL to download model with progress bar

**Implementation Notes:**
* Store license key locally (encrypted): `%APPDATA%/LocalScribe/license.dat`
* Cache license validation for 24 hours to avoid constant API calls
* Model storage: `%APPDATA%/LocalScribe/models/`
* Check for model updates weekly (compare file checksums via API)

### 4.3 Bandwidth Suspension Handling
* **Dropbox behavior:** If bandwidth limit exceeded, shared links are temporarily suspended for 24-72 hours (first offense), longer for subsequent offenses
* **User message if download fails:** "Model download temporarily unavailable. Please try again in 24 hours or contact support."
* **Mitigation:** License server tracks downloads and can rotate between multiple Dropbox accounts if needed

---

## 5. Pre-processing Pipeline (The "Cleaner")

### 5.1 Overview
The cleaner is the most critical component. It processes each document independently to extract clean, readable text and assign confidence scores.

**Input:** List of file paths (PDF, TXT, RTF)
**Output:** For each file:
* Clean text string
* OCR confidence score (0-100%)
* Processing status (success/warning/error)

### 5.2 Processing Flow (Per Document)

#### Step 1: File Type Detection
```python
if file.endswith('.txt') or file.endswith('.rtf'):
    text = read_text_file(file)
    confidence = 100
    method = "direct_read"
elif file.endswith('.pdf'):
    # Proceed to Step 2
```

#### Step 2: PDF Text Extraction
```python
import pdfplumber

text = ""
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text += page.extract_text() or ""
```

#### Step 3: Heuristic Check (Digital vs Scanned)
```python
# Load NLTK English words corpus
from nltk.corpus import words
english_words = set(words.words())

# Tokenize and check
tokens = text.lower().split()
valid_words = sum(1 for token in tokens if token in english_words)
total_words = len(tokens)

if total_words > 0:
    dictionary_percentage = (valid_words / total_words) * 100
else:
    dictionary_percentage = 0

# Decision logic
if dictionary_percentage > 60 and len(text) > 1000:
    confidence = 100
    method = "digital_text"
    # Skip to Step 5 (cleaning)
else:
    # Proceed to Step 4 (OCR)
```

#### Step 4: OCR Processing (If Needed)
```python
from pdf2image import convert_from_path
import pytesseract

# Convert PDF to images
images = convert_from_path(pdf_path, dpi=300)

# OCR each page
ocr_text = ""
for image in images:
    ocr_text += pytesseract.image_to_string(image) + "\n"

# Calculate confidence using same dictionary check
tokens = ocr_text.lower().split()
valid_words = sum(1 for token in tokens if token in english_words)
confidence = (valid_words / len(tokens)) * 100 if tokens else 0

text = ocr_text
method = "ocr"
```

#### Step 5: Text Cleaning Rules

**Load Dynamic Keyword Lists:**
```python
# Download and cache from Dropbox (check weekly for updates)
legal_keywords = load_keywords_list("legal_keywords_{jurisdiction}.txt")
# Example content: ["COURT", "PLAINTIFF", "DEFENDANT", "APPEARANCES", "SUPREME"]
```

**Rule 1: Line Filtering**
```python
cleaned_lines = []
for line in text.split('\n'):
    # Keep line if it passes ALL these tests:
    if len(line) > 15:  # Minimum length
        has_lowercase = any(c.islower() for c in line)
        is_legal_header = (line.isupper() and 
                          len(line) < 50 and 
                          any(keyword in line for keyword in legal_keywords))
        
        # Count character types
        alpha_count = sum(c.isalpha() for c in line)
        other_count = sum(not c.isalpha() and not c.isspace() for c in line)
        
        if (has_lowercase or is_legal_header) and alpha_count > other_count:
            cleaned_lines.append(line)
```

**Rule 2: De-hyphenation**
```python
# Rejoin words split by line breaks (e.g., "defen-\ndant" → "defendant")
text = '\n'.join(cleaned_lines)
text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

# Preserve legitimate hyphenated compounds (e.g., "attorney-client")
# This is handled by only removing hyphen+newline, not hyphen+space
```

**Rule 3: Whitespace Normalization**
```python
# Remove excess blank lines (keep max 1 between paragraphs)
text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
text = text.strip()
```

### 5.3 Error Handling During Pre-processing

**Zero-length cleaned text:**
```python
if len(cleaned_text.strip()) == 0:
    status = "error"
    message = "Unable to extract readable text. File may be corrupted or contain only images."
    # Mark file for skipping with warning dialog
```

**File size limits:**
```python
file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

if file_size_mb > 500:
    status = "error"
    message = "File exceeds maximum size (500MB). Please split file or extract relevant sections."
    # Reject file
elif file_size_mb > 100:
    # Show warning dialog: "Large file detected (XXX MB). Processing may take significantly longer. Continue?"
    # If user clicks No, skip file
```

**Password-protected PDFs:**
```python
try:
    with pdfplumber.open(pdf_path) as pdf:
        # Attempt to access
except Exception as e:
    if "password" in str(e).lower() or "encrypted" in str(e).lower():
        status = "error"
        message = "PDF is password-protected and cannot be processed."
```

### 5.4 Multi-File Summary & User Selection Interface

After processing all files, display a **File Review Table**:

| Filename | Status | Method | OCR Confidence | Pages | Size | Include |
|----------|--------|--------|----------------|-------|------|---------|
| complaint.pdf | ✓ Ready | Digital | 100% | 45 | 2.3 MB | ☑ |
| exhibit_a.pdf | ⚠ Low Quality | OCR | 60% | 12 | 856 KB | ☐ |
| exhibit_b.pdf | ⚠ Warning | OCR | 75% | 8 | 1.1 MB | ☑ |
| deposition.pdf | ✓ Ready | OCR | 89% | 120 | 8.7 MB | ☑ |
| motion.pdf | ✓ Ready | Digital | 100% | 23 | 1.8 MB | ☑ |
| corrupted.pdf | ✗ Failed | Error | 0% | - | - | - |

**UI Elements:**
* **Warning banner:** "⚠ Files with confidence <70% may produce unreliable results"
* **Checkboxes:** Pre-checked for files with confidence ≥70%, unchecked for <70%
* **Status icons:** ✓ (green), ⚠ (yellow), ✗ (red)
* **Buttons:**
  * "Select All" / "Deselect All"
  * "Process Selected Files" (shows estimated time: "~12 minutes with Standard model")
  * "Cancel" (return to file selection)

**Failed files behavior:**
* Show warning dialog listing failed files: "The following files could not be processed: [list]. Continue with remaining files?"
* Remove failed files from processing queue
* Log errors to `%APPDATA%/LocalScribe/logs/processing.log`

---

## 6. Document Prioritization System

### 6.1 Purpose
When combined document text exceeds the AI model's context window (~6000 tokens for safe processing), the app must intelligently truncate less important documents while preserving critical case documents in full.

### 6.2 User Settings (Set Once, Use Always)

**Settings Menu → Document Priority Rules**

Users configure document priority ONCE based on their workflow. This becomes their default for all future cases.

**Configuration Interface:**
```
┌─────────────────────────────────────────────┐
│ Document Priority Rules                      │
│                                              │
│ Jurisdiction Preset: [New York State ▼]     │
│                                              │
│ HIGH PRIORITY (never truncated):             │
│ ┌──────────────────────────────────────────┐│
│ │ • complaint                               ││
│ │ • answer                                  ││
│ │ • bill of particulars                     ││
│ │ • summons                                 ││
│ └──────────────────────────────────────────┘│
│                                              │
│ MEDIUM PRIORITY (truncate proportionally):   │
│ ┌──────────────────────────────────────────┐│
│ │ • motion                                  ││
│ │ • affidavit                               ││
│ │ • exhibit                                 ││
│ └──────────────────────────────────────────┘│
│                                              │
│ LOW PRIORITY (truncate first):               │
│ ┌──────────────────────────────────────────┐│
│ │ • notice                                  ││
│ │ • certificate                             ││
│ │ • cover                                   ││
│ │ • stipulation                             ││
│ └──────────────────────────────────────────┘│
│                                              │
│ [Load Preset ▼] [Save as Custom] [Reset]    │
└─────────────────────────────────────────────┘
```

**Preset Options:**
* New York State (default shown above)
* California
* Federal Court
* Custom (user-defined)

**Settings Storage:**
```json
// %APPDATA%/LocalScribe/config/priority_rules.json
{
  "jurisdiction": "new_york",
  "high_priority_keywords": ["complaint", "answer", "bill of particulars", "summons"],
  "medium_priority_keywords": ["motion", "affidavit", "exhibit", "deposition"],
  "low_priority_keywords": ["notice", "certificate", "cover", "stipulation"]
}
```

### 6.3 Auto-Categorization at Runtime

**When user selects files for processing:**
```python
def categorize_document(filename, priority_rules):
    filename_lower = filename.lower()
    
    # Check high priority keywords
    for keyword in priority_rules['high_priority_keywords']:
        if keyword in filename_lower:
            return "HIGH"
    
    # Check medium priority
    for keyword in priority_rules['medium_priority_keywords']:
        if keyword in filename_lower:
            return "MEDIUM"
    
    # Check low priority
    for keyword in priority_rules['low_priority_keywords']:
        if keyword in filename_lower:
            return "LOW"
    
    # Default to MEDIUM if no match
    return "MEDIUM"
```

**Display in File Review Table:**
Add a "Priority" column showing HIGH/MEDIUM/LOW auto-assignment based on filename.

### 6.4 Truncation Logic (When Context Window Exceeded)

```python
def prepare_combined_text(selected_files, priority_rules, max_tokens=6000):
    """
    Combine text from multiple documents, truncating intelligently if needed.
    """
    # Categorize files
    high_priority = [f for f in selected_files if f.priority == "HIGH"]
    medium_priority = [f for f in selected_files if f.priority == "MEDIUM"]
    low_priority = [f for f in selected_files if f.priority == "LOW"]
    
    # Estimate tokens (rough: 1 token ≈ 0.75 words)
    def estimate_tokens(text):
        return int(len(text.split()) / 0.75)
    
    combined_text = ""
    total_tokens = 0
    truncation_occurred = False
    
    # Add HIGH priority documents in full (never truncate)
    for doc in high_priority:
        separator = f"\n\n--- DOCUMENT: {doc.filename} ---\n\n"
        combined_text += separator + doc.clean_text
        total_tokens += estimate_tokens(separator + doc.clean_text)
    
    # Calculate remaining budget
    remaining_tokens = max_tokens - total_tokens
    
    if remaining_tokens <= 0:
        # Even high priority docs exceed limit - truncate proportionally
        # (This should be rare with typical case documents)
        truncation_occurred = True
        combined_text = truncate_proportionally(high_priority, max_tokens)
        return combined_text, truncation_occurred
    
    # Add MEDIUM priority (truncate proportionally if needed)
    medium_text = ""
    for doc in medium_priority:
        separator = f"\n\n--- DOCUMENT: {doc.filename} ---\n\n"
        medium_text += separator + doc.clean_text
    
    medium_tokens = estimate_tokens(medium_text)
    
    if medium_tokens <= remaining_tokens:
        combined_text += medium_text
        remaining_tokens -= medium_tokens
    else:
        # Truncate medium priority proportionally
        truncation_occurred = True
        truncation_ratio = remaining_tokens / medium_tokens
        for doc in medium_priority:
            separator = f"\n\n--- DOCUMENT: {doc.filename} ---\n\n"
            truncated = doc.clean_text[:int(len(doc.clean_text) * truncation_ratio)]
            combined_text += separator + truncated + "\n[...truncated...]"
        remaining_tokens = 0
    
    # Add LOW priority only if budget remains
    if remaining_tokens > 0:
        for doc in low_priority:
            separator = f"\n\n--- DOCUMENT: {doc.filename} ---\n\n"
            doc_text = separator + doc.clean_text
            doc_tokens = estimate_tokens(doc_text)
            
            if doc_tokens <= remaining_tokens:
                combined_text += doc_text
                remaining_tokens -= doc_tokens
            else:
                # Truncate this low priority doc
                truncation_occurred = True
                truncation_ratio = remaining_tokens / doc_tokens
                truncated = doc.clean_text[:int(len(doc.clean_text) * truncation_ratio)]
                combined_text += separator + truncated + "\n[...truncated...]"
                break
    
    return combined_text, truncation_occurred

# Display warning if truncation occurred
if truncation_occurred:
    show_warning("⚠ Some documents truncated to fit processing limits. High priority documents (complaint, answer, bill of particulars) were preserved in full.")
```

---

## 7. AI Processing (The "Brain")

### 7.1 Model Management

**Model Locations:**
* Standard Model: `%APPDATA%/LocalScribe/models/gemma-2-9b-it-q4_k_m.gguf`
* Pro Model: `%APPDATA%/LocalScribe/models/gemma-2-27b-it-q4_k_m.gguf`

**Model Loading:**
```python
from llama_cpp import Llama

def load_model(model_path, n_ctx=8192):
    """
    Load GGUF model with llama-cpp-python
    n_ctx: Context window size in tokens
    """
    llm = Llama(
        model_path=model_path,
        n_ctx=n_ctx,
        n_threads=4,  # Adjust based on CPU cores
        n_gpu_layers=0,  # CPU-only (set to >0 if GPU available)
        verbose=False
    )
    return llm
```

### 7.2 User-Controlled Settings

**Model Selection:**
* Dropdown in UI: "Standard (9B - Fast)" or "Pro (27B - Best Quality)"
* Pro model shows warning: "⚠ Pro mode takes 30-60 minutes per processing job. Best for overnight batch processing."

**Summary Length:**
* Slider: 100-500 words (default: 200)
* Real-time estimate updates as slider moves:
  * 100 words + Standard: "~5 min"
  * 200 words + Standard: "~8 min"
  * 500 words + Standard: "~15 min"
  * 200 words + Pro: "~35 min"
* Tooltip: "Longer summaries take more time to generate"

### 7.3 User Tips (Display Before Processing)

Show these tips in a collapsible panel:
```
💡 Tips for Best Results:
• Process only the most relevant documents to save time
• Extract key sections from large documents rather than processing entire files
• Start with Standard mode to preview results before using Pro mode
• Pro mode is ideal for complex medical malpractice or multi-defendant cases
• Summary length: 200 words is optimal for most cases
```

### 7.4 Realistic Time Estimates

**Standard Model (9B):**
* Summary generation: 5-15 minutes (depends on combined document length and summary word count)
* Vocabulary extraction: 2-5 minutes
* Definitions (50 terms): 3-7 minutes
* **Total: 10-27 minutes**

**Pro Model (27B):**
* Summary generation: 30-60 minutes
* Vocabulary extraction: 8-15 minutes
* Definitions (50 terms): 10-20 minutes
* **Total: 48-95 minutes**

**Factors affecting speed:**
* CPU performance (more cores = faster)
* Total token count in combined documents
* Requested summary length
* Number of vocabulary terms requiring definitions

### 7.5 Prompt Engineering

#### 7.5.1 Summary Prompt

**Purpose:** Generate ONE cohesive case-level summary from multiple documents.

**Prompt Template:**
```
You are assisting a court reporter who needs a case overview. Multiple legal documents are provided below (complaint, answer, bill of particulars, motions, exhibits, etc.). Each document is marked with a separator.

Synthesize information across ALL documents to create ONE coherent case summary of approximately {USER_WORD_COUNT} words.

Focus on:
- Main plaintiff(s) and defendant(s)
- Core legal claims (e.g., negligence, breach of contract, medical malpractice)
- Defendant's defenses or counterclaims (if mentioned in answer or motion)
- Key factual events and timeline (e.g., dates of injury, surgery, incident)

Be concise, factual, and use plain language. Ignore metadata like page numbers, filing dates, and docket numbers. If documents contain conflicting information, note it briefly.

Do not list documents individually - synthesize them into one narrative.

{COMBINED_DOCUMENT_TEXT}

Now provide the case summary:
```

**Token Budget:**
* Prompt overhead: ~150 tokens
* Input documents: 4000-6000 tokens (after truncation if needed)
* Output summary: 
  * 100 words = ~133 tokens
  * 200 words = ~267 tokens
  * 500 words = ~667 tokens
* **Total: 4300-6800 tokens** (safely within 8K context window)

**Implementation Notes:**
* Replace `{USER_WORD_COUNT}` with slider value
* Replace `{COMBINED_DOCUMENT_TEXT}` with output from truncation logic (section 6.4)
* Strip any extra whitespace from combined text to save tokens

#### 7.5.2 Vocabulary Extraction Prompt

**Purpose:** Extract only rare/unusual terms and proper nouns from combined case documents.

**Prompt Template:**
```
Extract ONLY unusual or specialized terms from the provided legal documents below. Include:

1. Proper nouns: People's names, hospitals, law firms, specific locations, company names
2. Technical/medical terms: Medical procedures, diagnoses, specialized legal terminology, drug names, medical equipment

EXCLUDE common words and basic legal vocabulary (court, plaintiff, defendant, attorney, judge, lawsuit, claim, motion, exhibit, etc.)

Rules:
- NO duplicates (case-insensitive)
- NO possessives (convert "Smith's" to "Smith")
- Use title case
- Include multi-word proper nouns as single entries (e.g., "New York Supreme Court")

Output format: Python list of strings ONLY. No explanations, no other text.

Example output format:
['Dr. Sarah Martinez', 'lumbar discectomy', 'Lenox Hill Hospital', 'subarachnoid hemorrhage', 'acetaminophen', 'Northwell Health']

{COMBINED_DOCUMENT_TEXT}

Now provide the vocabulary list:
```

**Token Budget:**
* Prompt overhead: ~140 tokens
* Input documents: 4000-6000 tokens (same text as summary)
* Output vocabulary list (50 terms avg): ~100 tokens
* **Total: 4240-6240 tokens**

**Post-Processing (Client-Side):**
```python
import re
import json

def parse_vocab_list(ai_output):
    """
    Extract Python list from AI output, handling various formats.
    """
    # Try to find list in output
    match = re.search(r'\[.*\]', ai_output, re.DOTALL)
    if match:
        try:
            vocab_list = json.loads(match.group(0))
            return vocab_list
        except json.JSONDecodeError:
            # Fallback: parse as Python literal
            try:
                vocab_list = eval(match.group(0))
                return vocab_list
            except:
                return None
    return None

def filter_vocab_with_frequency(vocab_list, google_freq_list, threshold=258000):
    """
    Filter vocab to only include rare words (not in top 258k most common).
    Also keep all proper nouns (capitalized).
    """
    filtered = []
    for term in vocab_list:
        # Always keep proper nouns (starts with capital)
        if term[0].isupper():
            filtered.append(term)
        # Keep rare words (below frequency threshold)
        elif term.lower() not in google_freq_list[:threshold]:
            filtered.append(term)
    
    return filtered

def apply_user_exclusions(vocab_list, excluded_terms_file):
    """
    Remove terms that user has manually excluded.
    """
    with open(excluded_terms_file, 'r') as f:
        excluded = set(line.strip().lower() for line in f)
    
    return [term for term in vocab_list if term.lower() not in excluded]
```

**Error Handling:**
```python
# If parsing fails on first attempt
if vocab_list is None:
    # Retry with simpler prompt
    simplified_prompt = """
    List unusual words from this text, one per line. Include only proper nouns and technical terms.
    
    {COMBINED_DOCUMENT_TEXT}
    """
    # Try again with simplified prompt
    
# If second attempt fails
if vocab_list is None:
    # Skip vocabulary generation, still show summary
    show_error("⚠ Vocabulary extraction failed. Summary generated successfully.")
    vocab_list = []
```

#### 7.5.3 Definition Prompt (Per Term)

**Purpose:** Generate concise definitions for terms in the vocabulary list.

**Prompt Template:**
```
Define the term '{TERM}' in one concise sentence (10-15 words maximum).

If it's a proper noun (person, place, organization), respond with: 'Proper noun - [type]'
Examples:
- 'Proper noun - hospital name'
- 'Proper noun - person's name'
- 'Proper noun - medical practice'

Be direct and factual only. No extra explanation.
```

**Token Budget (Per Term):**
* Prompt + term: ~30 tokens
* Output definition: ~20 tokens
* **Total per term: ~50 tokens**

**Batch Processing:**
* Process definitions sequentially (not all at once)
* Update progress: "Generating definitions... (12/50)"
* Cancel button available during this phase

**Caching Strategy:**
```python
# Cache definitions locally to avoid re-processing common terms
# %APPDATA%/LocalScribe/cache/definitions.json
{
  "mri": "Medical imaging technique using magnetic fields to visualize internal body structures.",
  "deposition": "Proper noun - legal term",  # User might manually edit this
  "dr. john smith": "Proper noun - person's name"
}

def get_definition(term, cache, model, use_ai=True):
    """
    Get definition from cache or generate with AI.
    """
    term_lower = term.lower()
    
    # Check cache first
    if term_lower in cache:
        return cache[term_lower]
    
    # Generate with AI if enabled
    if use_ai:
        definition = generate_definition_with_ai(term, model)
        # Cache for future use
        cache[term_lower] = definition
        save_cache(cache)
        return definition
    else:
        return "No definition available"
```

### 7.6 Streaming Implementation

**Purpose:** Display generated text in real-time so users see progress and can cancel if output is incorrect.

**Implementation with PySide6 + llama-cpp:**

```python
from PySide6.QtCore import QThread, Signal
from llama_cpp import Llama

class AIWorkerThread(QThread):
    """
    Worker thread for AI processing with streaming output.
    """
    # Signals
    token_generated = Signal(str)  # Emits each new token
    progress_update = Signal(int, str)  # Emits (percentage, status_message)
    finished = Signal(str)  # Emits complete output
    error = Signal(str)  # Emits error message
    
    def __init__(self, model_path, prompt, max_tokens=500):
        super().__init__()
        self.model_path = model_path
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.cancelled = False
    
    def run(self):
        try:
            # Load model
            self.progress_update.emit(0, "Loading model...")
            llm = Llama(model_path=self.model_path, n_ctx=8192, verbose=False)
            
            # Generate with streaming
            self.progress_update.emit(10, "Generating response...")
            
            full_response = ""
            token_count = 0
            
            # Stream tokens one by one
            for output in llm(
                self.prompt,
                max_tokens=self.max_tokens,
                stream=True,
                temperature=0.7,
                top_p=0.9
            ):
                if self.cancelled:
                    self.error.emit("Generation cancelled by user")
                    return
                
                # Extract token from output
                token = output['choices'][0]['text']
                full_response += token
                token_count += 1
                
                # Emit token for real-time display
                self.token_generated.emit(token)
                
                # Update progress
                progress_pct = min(95, int((token_count / self.max_tokens) * 100))
                self.progress_update.emit(progress_pct, f"Generating... ({token_count} tokens)")
            
            # Finished
            self.progress_update.emit(100, "Complete")
            self.finished.emit(full_response)
            
        except Exception as e:
            self.error.emit(f"Error during generation: {str(e)}")
    
    def cancel(self):
        self.cancelled = True

# In main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        # ... UI setup ...
    
    def start_generation(self):
        # Disable UI elements
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        
        # Clear previous output
        self.summary_text_edit.clear()
        
        # Create worker thread
        self.worker = AIWorkerThread(
            model_path=self.model_path,
            prompt=self.build_prompt(),
            max_tokens=self.calculate_max_tokens()
        )
        
        # Connect signals
        self.worker.token_generated.connect(self.append_token)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.on_generation_complete)
        self.worker.error.connect(self.on_generation_error)
        
        # Start thread
        self.worker.start()
    
    def append_token(self, token):
        """Append token to text display in real-time."""
        cursor = self.summary_text_edit.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(token)
        self.summary_text_edit.setTextCursor(cursor)
        # Auto-scroll to bottom
        scrollbar = self.summary_text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_progress(self, percentage, message):
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)
    
    def on_generation_complete(self, full_text):
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("✓ Generation complete")
        # Save to results
        self.current_summary = full_text
    
    def on_generation_error(self, error_msg):
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Error", error_msg)
    
    def cancel_generation(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("Cancelling...")
```

**Benefits of Streaming:**
* Users see immediate feedback (text appearing word-by-word)
* Can cancel generation early if output is wrong
* Better UX during long waits (reduces perceived time)
* Easier debugging (see exactly where generation failed)

---

## 8. Output Generation & Display

### 8.1 Summary Display

**UI Component:** Read-only `QTextEdit` with rich text formatting

**Features:**
* Word-wrapped, scrollable text area
* "Copy to Clipboard" button
* "Save as TXT" button → saves to `Documents/LocalScribe/Summaries/case_summary_YYYY-MM-DD_HHMMSS.txt`
* Character count displayed: "Summary: 247 words"

### 8.2 Vocabulary List Display & Management

**UI Component:** `QTableWidget` with 4 columns

| Term | Category | Definition | Actions |
|------|----------|------------|---------|
| Dr. Robert Chen | Proper Noun | Proper noun - person's name | 🗑️ |
| lumbar discectomy | Technical | Surgical removal of herniated disc material in lower spine. | 🗑️ |
| Lenox Hill Hospital | Proper Noun | Proper noun - hospital name | 🗑️ |
| spondylosis | Technical | Degenerative condition affecting spinal discs and joints. | 🗑️ |

**Columns:**
1. **Term** (sortable alphabetically)
2. **Category:** "Proper Noun" or "Technical"
3. **Definition:** 
   * From AI if generated
   * "No definition available" if Standard mode (no AI definitions)
   * "(AI-Generated)" label appended for AI definitions in Pro mode
4. **Actions:** 
   * 🗑️ "Hide" button → adds term to exclusion list

**Features:**
* Sortable by column (click headers)
* Filter dropdown: "Show All" / "Proper Nouns Only" / "Technical Terms Only"
* "Export as CSV" button → saves to `Documents/LocalScribe/Vocabulary/vocab_YYYY-MM-DD_HHMMSS.csv`
* Row count displayed: "50 terms found"

**User Exclusion System:**
```python
# When user clicks "Hide" button
def exclude_term(term):
    # Add to local exclusion file
    exclusion_file = os.path.join(APPDATA, "LocalScribe", "excluded_vocab.txt")
    with open(exclusion_file, 'a') as f:
        f.write(term.lower() + '\n')
    
    # Remove from current display
    table.removeRow(term_row_index)
    
    # Show confirmation
    status_bar.showMessage(f"'{term}' will be excluded from future vocabulary lists", 3000)

# Load exclusions on startup
def load_exclusions():
    exclusion_file = os.path.join(APPDATA, "LocalScribe", "excluded_vocab.txt")
    if os.path.exists(exclusion_file):
        with open(exclusion_file, 'r') as f:
            return set(line.strip().lower() for line in f)
    return set()
```

**Vocabulary Settings (in Preferences):**
* "Reset Exclusion List" button → clears all user exclusions with confirmation
* "Edit Exclusion List" button → opens text file in system editor
* Display count: "Currently excluding 23 terms"

### 8.3 CSV Export Format

**File structure:**
```csv
Term,Category,Definition,Source
Dr. Robert Chen,Proper Noun,Proper noun - person's name,AI
lumbar discectomy,Technical,Surgical removal of herniated disc material in lower spine.,AI
Lenox Hill Hospital,Proper Noun,Proper noun - hospital name,AI
spondylosis,Technical,Degenerative condition affecting spinal discs and joints.,AI
NYSCEF,Technical,No definition available,None
```

**Export Implementation:**
```python
import csv

def export_vocabulary_csv(vocab_table, output_path):
    """
    Export vocabulary table to CSV.
    """
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow(['Term', 'Category', 'Definition', 'Source'])
        
        # Data rows
        for row_idx in range(vocab_table.rowCount()):
            term = vocab_table.item(row_idx, 0).text()
            category = vocab_table.item(row_idx, 1).text()
            definition = vocab_table.item(row_idx, 2).text()
            
            # Determine source
            if "No definition" in definition:
                source = "None"
            else:
                source = "AI"
            
            writer.writerow([term, category, definition, source])
    
    return output_path
```

---

## 9. First Priority Tasks for Implementation

### 9.1 Phase 1: Pre-processing Engine (IMPLEMENT FIRST)

**Goal:** Build a standalone, testable `cleaner.py` module that can process documents from the command line.

**Requirements:**
```bash
# Command line interface
python cleaner.py --input file1.pdf file2.pdf --output-dir ./cleaned --jurisdiction ny

# Output:
# - Creates ./cleaned/file1_cleaned.txt
# - Creates ./cleaned/file2_cleaned.txt
# - Prints summary report to console
```

**Module Structure:**
```python
# cleaner.py
class DocumentCleaner:
    def __init__(self, jurisdiction="ny"):
        self.jurisdiction = jurisdiction
        self.legal_keywords = self.load_keywords()
        self.english_words = self.load_dictionary()
    
    def process_document(self, file_path):
        """
        Process a single document.
        Returns: (cleaned_text, confidence, method, status, error_message)
        """
        pass
    
    def sniff_file_type(self, file_path):
        """Detect if PDF, TXT, RTF."""
        pass
    
    def extract_text_from_pdf(self, pdf_path):
        """Use pdfplumber to extract text."""
        pass
    
    def calculate_dictionary_confidence(self, text):
        """Calculate % of words that are valid English."""
        pass
    
    def perform_ocr(self, pdf_path):
        """Run Tesseract OCR and return text + confidence."""
        pass
    
    def clean_text(self, raw_text):
        """Apply cleaning rules 1-3."""
        pass
    
    def load_keywords(self):
        """Load legal keywords for jurisdiction."""
        pass
    
    def load_dictionary(self):
        """Load NLTK English words."""
        pass

# Test it
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean legal documents")
    parser.add_argument("--input", nargs="+", required=True, help="Input files")
    parser.add_argument("--output-dir", default="./cleaned", help="Output directory")
    parser.add_argument("--jurisdiction", default="ny", help="Jurisdiction (ny, ca, federal)")
    
    args = parser.parse_args()
    
    cleaner = DocumentCleaner(jurisdiction=args.jurisdiction)
    
    results = []
    for file_path in args.input:
        result = cleaner.process_document(file_path)
        results.append(result)
        
        # Save cleaned text
        if result['status'] == 'success':
            output_file = os.path.join(args.output_dir, f"{result['filename']}_cleaned.txt")
            with open(output_file, 'w') as f:
                f.write(result['cleaned_text'])
    
    # Print summary report
    print("\n=== PROCESSING SUMMARY ===")
    for result in results:
        print(f"{result['filename']}: {result['status']} - {result['method']} - {result['confidence']}%")
```

**Testing Checklist:**
- [ ] Extract text from digital PDFs correctly
- [ ] Detect scanned PDFs and trigger OCR
- [ ] OCR produces readable text with reasonable confidence
- [ ] Cleaning rules remove junk while preserving content
- [ ] De-hyphenation works correctly
- [ ] Legal headers (ALL CAPS) are preserved
- [ ] Handle password-protected PDFs gracefully
- [ ] Handle corrupted files gracefully
- [ ] Handle files >500MB correctly
- [ ] Process multiple files in batch

**Deliverable:** A working `cleaner.py` that can be run independently before UI development begins.

---

## 10. Development Phases Summary

### Phase 1: Pre-processing Engine (2-3 weeks)
**Deliverable:** Command-line `cleaner.py` module

### Phase 2: Basic UI Shell (2 weeks)
**Deliverable:** PySide6 main window with file selection and preprocessing integration

### Phase 3: AI Integration (2-3 weeks)
**Deliverable:** Model loading, streaming generation, summary display

### Phase 4: Vocabulary & Definitions (1-2 weeks)
**Deliverable:** Vocab extraction, filtering, definitions, table display

### Phase 5: License System Integration (1 week)
**Deliverable:** License validation, model downloads, quota tracking

### Phase 6: Settings & Polish (1-2 weeks)
**Deliverable:** Document priority config, preferences, final error handling

### Phase 7: Packaging & Distribution (1 week)
**Deliverable:** PyInstaller executable, installer, documentation

**Total Estimated Timeline: 10-14 weeks**

---

## 11. System Requirements

### Minimum Requirements
* **CPU:** Intel Core i5 / AMD Ryzen 5 (4+ cores)
* **RAM:** 16 GB (8 GB minimum but slow)
* **Storage:** 50 GB free space
* **OS:** Windows 10/11 (64-bit)

### Recommended Requirements
* **CPU:** Intel Core i7/i9 / AMD Ryzen 7/9 (8+ cores)
* **RAM:** 32 GB
* **Storage:** 100 GB free (SSD)
* **OS:** Windows 11 (64-bit)

---

**Document Version:** 2.0 (Final)  
**Date:** November 12, 2025  
**Status:** Ready for Implementation
