# Scratchpad - Future Ideas & Refinements

## 🔴 CRITICAL ISSUE: GUI Severe Unresponsiveness After Large PDF Processing (Session 13)
**Priority:** HIGH - Blocking user workflow
**Status:** Unresolved - needs investigation
**Added:** 2025-11-28

### Symptoms
- After processing 260-page PDF, GUI becomes severely unresponsive
- Dragging window causes freezing/lag
- Switching output views (Meta-Summary → Rare Word List) extremely slow
- UI sometimes renders blank (only "Generate All Outputs" button visible)
- Persists even after processing completes

### Attempted Fixes (Session 13)
✅ Batch queue processing (10 messages/cycle) - helped but insufficient
✅ Vocabulary display limit (150 rows default, 500 ceiling) - helped but insufficient
✅ Forced UI updates with `update_idletasks()` - helped but insufficient
✅ Cancel button implementation - works but doesn't fix responsiveness

### Hypotheses to Investigate
1. **Memory leak**: Large PDF (260 pages) may be creating thousands of objects not being garbage collected
2. **Background threads not terminating**: AI worker, vocabulary worker, or processing worker may still be running
3. **UI event queue saturation**: Too many pending UI updates from large document
4. **Treeview/widget corruption**: Switching views may be triggering expensive redraws
5. **Windows-specific issue**: May need platform-specific optimizations

### Next Steps
1. Profile memory usage during/after 260-page PDF processing
2. Check if all worker threads properly terminate after completion
3. Add explicit garbage collection after large document processing
4. Consider splitting vocabulary display into pages (e.g., 50 rows/page with pagination)
5. Test on different system specs to isolate hardware vs. software issue

---

## Session 8 Testing Checklist (Vocabulary Workflow Verification)
**Status:** Awaiting user testing
**Time estimate:** 15-20 minutes
**Prerequisites:** Session 6 & 7 code changes (all 55 tests passing)

### Checklist (Copy this for next session testing)

**Test Environment Setup:**
- [ ] Start application with fresh run (no prior spaCy model installed)
- [ ] Have 2-3 legal documents ready (PDF/TXT/RTF)
- [ ] Monitor debug logs throughout (check for expected log messages)

**Test 1: spaCy Auto-Download (First Run)**
- [ ] Load first document for processing
- [ ] Check debug log for: `[VOCAB] Loading spaCy model 'en_core_web_sm'...`
- [ ] Check for: `[VOCAB] spaCy model 'en_core_web_sm' not found. Attempting to download...`
- [ ] Watch for download progress (should show pip install in debug)
- [ ] Verify: `[VOCAB] Successfully downloaded spaCy model 'en_core_web_sm'`
- [ ] Check that model is cached (doesn't re-download on second run)

**Test 2: Vocabulary Extraction Progress Messages**
- [ ] Trigger vocabulary extraction (enable "Rare Word List" checkbox)
- [ ] Observe progress bar updates at expected percentages:
  - [ ] 30% with message "Extracting vocabulary..."
  - [ ] 50% with message "Categorizing terms..."
  - [ ] 70% with message "Vocabulary extraction complete"
- [ ] Check debug log contains all three progress messages

**Test 3: Widget Reference Fix (output_options)**
- [ ] Select multiple documents
- [ ] Enable "Individual Summaries" checkbox
- [ ] Enable "Meta Summary" checkbox
- [ ] Enable "Rare Word List" checkbox
- [ ] Start processing
- [ ] Verify all three options are read correctly (no "object has no attribute" errors)
- [ ] Check debug log: `[QUEUE HANDLER] Started vocabulary extraction worker thread.`

**Test 4: Graceful Fallback (Missing Config Files)**
- [ ] Temporarily rename/move `config/legal_exclude.txt` and `config/medical_terms.txt`
- [ ] Run vocabulary extraction
- [ ] Check debug log for: `[VOCAB] Word list file not found at ... Using empty list`
- [ ] Verify extraction still completes (uses empty exclusion lists)
- [ ] Restore config files

**Test 5: Error Handling**
- [ ] Trigger an error condition (e.g., kill Ollama service mid-extraction)
- [ ] Check that error message appears in UI (not silent failure)
- [ ] Verify debug log shows full exception traceback
- [ ] Application remains responsive (can try again)

**Test 6: CSV Output Accuracy**
- [ ] Complete a full vocabulary extraction
- [ ] Verify CSV output contains:
  - [ ] Term column (unusual words)
  - [ ] Category column (legal, medical, etc.)
  - [ ] Definition column (populated from WordNet)
  - [ ] Source column (document filename)
- [ ] Check for expected legal/medical terms in output

### Expected Debug Log Sequence
```
[VOCAB] Loading spaCy model 'en_core_web_sm'...
[VOCAB] spaCy model 'en_core_web_sm' not found. Attempting to download...
[VOCAB] Successfully downloaded spaCy model 'en_core_web_sm'
[QUEUE HANDLER] Started vocabulary extraction worker thread.
[VOCAB WORKER] Vocabulary extraction completed successfully.
```

### Known Issues (If Any)
*Will be populated during testing*

### Notes for Debugging
- Enable DEBUG mode in config.py for verbose logging
- Check `.venv\Lib\site-packages\spacy\` for installed model
- Vocabulary CSV files saved to `outputs/` directory
- If timeout occurs, increase `timeout=300` in vocabulary_extractor.py:51

---

## Development Roadmap (Spec-Driven Phases)

### **Phase 2.2: Document Prioritization System** (Est. 3-4 hours)
**Spec Reference:** Section 6 of PROJECT_OVERVIEW.md

When combined document text exceeds AI model context window (~6000 tokens), intelligently truncate based on priority:
- **HIGH Priority:** complaint, answer, bill of particulars, summons (never truncated)
- **MEDIUM Priority:** motion, affidavit, exhibit, deposition (truncate proportionally)
- **LOW Priority:** notice, certificate, cover, stipulation (truncate first)

**Implementation Steps:**
1. Create `DocumentPriority` enum and priority assignment logic
2. Implement token estimation and truncation algorithm (Section 6.4 of spec)
3. Add "Priority" column to File Review Table
4. Add Settings menu for jurisdiction presets (NY, California, Federal, Custom)
5. Integrate with Ollama text generation pipeline

---

### **Phase 3: License Server Integration** (Est. 4-6 hours)
**Spec Reference:** Section 4 of PROJECT_OVERVIEW.md

Users need to validate licenses and download commercial models via Dropbox:
- License key validation API (HTTP POST to `/api/validate_license`)
- Quota tracking (daily/weekly/monthly/annual limits per license)
- Dropbox model download with progress bar
- Model storage management in `%APPDATA%/LocalScribe/models/`
- License caching (24-hour validity before re-validation)

**Current State:** Not implemented. App uses free Ollama models (gemma3:1b).

---

### **Phase 4: Vocabulary Extraction Enhancement** (Est. 2-3 hours)
**Spec Reference:** Section 7.5.2 & 8.2 of PROJECT_OVERVIEW.md

Complete the vocabulary extraction pipeline with per-term definitions:
- Extract rare/technical terms + proper nouns (already working)
- **Batch-generate definitions** for all terms with progress indicator
- **Cache definitions locally** in `%APPDATA%/LocalScribe/cache/definitions.json` to avoid re-processing
- CSV export with Term, Category, Definition, Source columns
- User exclusion system (hide terms from future vocabulary lists)

---

### **Phase 5: Advanced Features** (Post-v1.0)
- Batch processing mode (process multiple cases overnight)
- Template system for custom summary formats
- Integration with court reporter workflow tools
- Export to Word/PDF with formatting
- Compare mode (diff between versions of documents)

---

## Model Compatibility & Prompt Format (Discussion: 2025-11-23)

### **Current State: Model-Agnostic Discovery, Prompt Format Incompatibility**

**Question Addressed:** Will all Ollama-downloaded models work with LocalScribe?

**Answer:**
- ✅ **Model discovery:** Yes. Code queries `/api/tags`, which lists all downloaded models automatically
- ⚠️ **Prompt compatibility:** No. Different models expect different prompt formats (Llama vs. Mistral vs. Gemma instruction formats)

**The Problem:**
Current code sends raw prompts to all models. Most instruction-tuned models work, but:
- Chat-only models may refuse or produce garbage
- Some models need special formatting (`[INST]...[/INST]`)
- Vocabulary extraction (requiring JSON output) may fail silently

**Decision: Implement Prompt Format Wrapping (Option A)**

#### **Phase 2.7: Model-Aware Prompt Formatting** (Est. 1-2 hours)
Detect model type and wrap prompts in model-specific instruction formats.

**Implementation:**
1. Add `wrap_prompt_for_model(model_name: str, prompt: str) -> str` method to `OllamaModelManager`
2. Detect model type from model name:
   ```python
   def wrap_prompt_for_model(self, model_name: str, prompt: str) -> str:
       """Wrap prompt in model-specific format based on model type."""
       base_model = model_name.split(':')[0].lower()

       if 'llama' in base_model:
           return f"[INST] {prompt} [/INST]"
       elif 'mistral' in base_model:
           return f"[INST] {prompt} [/INST]"
       elif 'gemma' in base_model:
           return prompt  # No special wrapping needed
       elif 'neural-chat' in base_model:
           return f"### User:\n{prompt}\n\n### Assistant:"
       elif 'dolphin' in base_model:
           return f"### User\n{prompt}\n### Assistant"
       else:
           # Default: try raw prompt (might work with instruction-tuned models)
           return prompt
   ```

3. Use wrapped prompt in `generate()` method (line ~242):
   ```python
   wrapped_prompt = self.wrap_prompt_for_model(self.model_name, prompt)
   payload = {
       "model": self.model_name,
       "prompt": wrapped_prompt,  # Use wrapped version
       "temperature": temperature,
       ...
   }
   ```

4. Test compatibility matrix:
   - ✅ gemma3:1b (no wrapping)
   - ✅ llama2:7b (Llama format)
   - ✅ mistral:7b (Mistral format)
   - ✅ neural-chat:7b (special format)
   - ? Other models (test as user adds them)

**Why This Matters:**
- Future-proofs the app for any Ollama model
- User can freely experiment with different models without code changes
- Prevents silent failures (model returns garbage because prompt format is wrong)

**Documentation:**
Add tooltip to model dropdown: "Select any Ollama model. LocalScribe automatically adapts prompt format for compatibility."

---

## Summary Quality Improvements (Discussion: 2025-11-23)

### **Current Issue: Summaries Are Unsatisfactory**

**Identified Problem:** Current summaries (using gemma3:1b) lack depth and nuance; they read as generic case overviews rather than insightful, strategic analysis.

**Root Cause Analysis:**
- Model size: gemma3:1b is a 1-billion-parameter model optimized for speed, not quality
- Context limitation: Truncation may be cutting off important details before summarization
- Prompt engineering: Current prompts may not be extracting "why" and strategic implications

### **Solution: Multi-Pronged Approach**

#### **1. Upgrade to Larger Model** (Quick Win - Est. 1 hour)
Test with **llama2:13b** or **mistral:7b** via Ollama:
```bash
ollama pull llama2:13b
ollama pull mistral:7b
```

**Hypothesis:** 7B-13B models have substantially better reasoning than 1B models. This alone may significantly improve summary quality.

**Next Steps:**
1. Update model dropdown to offer both 1B (fast, basic) and 7B (slower, better quality) options
2. Update time estimates in UI (7B will be 3-5x slower)
3. A/B test output quality with same documents
4. Log which model produces "best" summaries for future tuning

---

#### **2. Parallel Document Processing (Feature: Phase 2.5)** ⭐ **NEW PRIORITY**
**User Request:** Process multiple documents simultaneously through Ollama with responsible CPU throttling.

**Design Principles:**
- **Non-blocking architecture:** Only the final meta-summary (combining individual summaries) is blocking
- **User-controlled concurrency:** Let user choose CPU allocation:
  - 1/4 cores: Low impact on laptop responsiveness
  - 1/2 cores: Balanced (RECOMMENDED)
  - 3/4 cores: Aggressive (for server/powerful machines)
- **Graceful scaling:** On 12-core machine with 1/2 option → process 6 documents simultaneously

**Implementation Sketch:**
```python
class AsyncDocumentProcessor:
    def __init__(self, cpu_fraction=0.5):
        """
        cpu_fraction: 0.25 (1/4), 0.5 (1/2), 0.75 (3/4)
        Calculates max_concurrent_jobs = ceil(cpu_count() * cpu_fraction)
        """
        self.max_concurrent = ceil(os.cpu_count() * cpu_fraction)
        self.job_queue = asyncio.Queue()
        self.active_jobs = {}

    async def process_document_batch(self, documents):
        """
        - Spawn up to max_concurrent tasks to Ollama
        - Each task: summarize one document independently
        - Wait for all to complete
        - Then generate meta-summary (blocking, single call)
        """
```

**GUI Changes:**
1. Add "Processing Concurrency" setting: Dropdown [1/4 cores | 1/2 cores | 3/4 cores]
2. Display active job count: "Processing 4/6 documents... (4 cores active)"
3. Progress bar per document (indeterminate, updates as they complete)

---

#### **3. System Monitor in GUI** ⭐ **NEW FEATURE**
**User Request:** Display real-time CPU and RAM usage to diagnose bottlenecks and optimize concurrency settings.

**Design:** Minimal, always visible; detailed info on hover.

**Implementation:**
1. **Status bar (bottom of window):** `CPU: 45% | RAM: 8.2 / 16 GB`
2. **Update frequency:** Every 1 second via background thread (psutil library)
3. **Color coding:**
   - Green: <50% (plenty of headroom)
   - Yellow: 50-75% (moderate usage, can increase async jobs)
   - Red: 75%+ (bottlenecked, reduce async concurrency)
4. **Hover tooltip (on status bar):** Reveals detailed specs
   ```
   Intel Core i7-11700K (8 physical cores, 16 logical threads)
   Base: 3.6 GHz | Turbo: 5.0 GHz
   Current CPU usage: 45% (3.6/8 cores active)
   ```

**Use Cases:**
- User sees CPU: 28% → "I can crank up concurrency from 1/2 to 3/4 cores"
- User sees CPU: 85% → "System is bottlenecked, reduce to 1/4 cores"
- User hovers tooltip → understands their hardware context for performance expectations

```python
import psutil

def get_system_stats():
    """Returns CPU%, RAM usage, and CPU model info."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()

    # CPU model (platform-dependent)
    try:
        import platform
        cpu_model = platform.processor()  # e.g., "Intel Core i7-11700K"
    except:
        cpu_model = "Unknown CPU"

    core_count = os.cpu_count()

    return {
        'cpu_percent': cpu_percent,
        'ram_used_gb': memory.used / 1024**3,
        'ram_total_gb': memory.total / 1024**3,
        'cpu_model': cpu_model,
        'core_count': core_count
    }
```

---

## Summary Quality Roadmap (Approved Discussion Items)

### **Immediate Actions (Next Session)**
1. ✅ Test llama2:13b and mistral:7b with sample case documents
2. ✅ Measure: time to generate summary + quality improvement vs 1B model
3. ✅ Decision: Which model to recommend as default? (Likely 7B)

### **Phase 2.5: Parallel Processing** (Est. 4-5 hours)
- CPU fraction selector in Settings (1/4, 1/2, 3/4 cores)
- AsyncDocumentProcessor with job queue
- Progress UI showing "X/Y documents processing"
- Per-document summary generation (no blocking until meta-summary)

### **Phase 2.6: System Monitor Widget** (Est. 1-2 hours)
- CPU% and RAM usage display in status bar
- Background thread updating every 1 second
- Color-coded indicators (Green/Yellow/Red)
- Optional tooltip with system details

### **Why This Matters:**
- **Quality:** Larger models → better reasoning → more useful summaries
- **Performance:** Parallel processing → faster overall throughput (e.g., 6 docs in ~5 min vs 6×2 min sequentially)
- **Transparency:** User sees system impact of their choices (CPU%, RAM) → builds trust
- **Responsible:** User controls concurrency → avoids system overload

---

## Questions to Address Later
- Should we support other file formats (DOCX, ODT)?
- What's the best way to handle multi-language documents?
- Should we add a "confidence threshold" setting that auto-rejects low-quality OCR?
- Which larger model (7B, 13B) offers the best quality/speed trade-off for legal documents?

## Technical Debt to Monitor
- None critical at present

---

## Session Notes
**2025-11-23 Discussion Summary:**
- Current summaries unsatisfactory; likely due to 1B model limitations
- Parallel document processing identified as high-priority feature for throughput
- CPU core allocation strategy approved (user-controlled: 1/4, 1/2, 3/4)
- System monitor (CPU%, RAM) requested for transparency
- Meta-summary remains blocking (correct; prevents premature aggregation)

---

## Phase 3: Smart Preprocessing Pipeline (Step 3 Architecture)
**Status:** Detailed design ready, awaiting implementation
**Spec Reference:** PROJECT_OVERVIEW.md Section 5 (preprocessing overview)

### Purpose
Clean extracted text (post-OCR/extraction, pre-model) for better summarization quality. Handles title pages, line numbers, headers/footers, and Q./A. formatting.

### Module Structure
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

### Implementation Details
- **BasePreprocessor:** Abstract class with `process(text) → str` method
- **TitlePageRemover:** Detect and remove metadata-heavy first sections (case numbers, dates, firm names)
- **LineNumberRemover:** Remove margins with line numbers (1, 2, 3... 123, 124...)
- **HeaderFooterRemover:** Identify and remove repetitive page headers/footers (case name, page X of Y)
- **QAConverter:** Expand Q./A. notation to "Question:"/"Answer:" for deposition text clarity
- **PreprocessingPipeline:** Orchestrate all preprocessors; return text + logs + stats

### Integration Strategy
1. Call `PreprocessingPipeline.process(combined_text)` in `src/ui/workers.py` before AI generation
2. Feed preprocessed text to `OllamaModelManager.generate_text()`
3. Log preprocessing results (which preprocessors ran, what was removed)
4. Graceful failure: Return original text if any preprocessor fails

### Testing Approach
- Unit tests for each preprocessor with sample documents
- Integration test: full pipeline with broken preprocessor (verify graceful degradation)
- Debug logging: show what was removed and why

### Implementation Estimate
- Base class + 4 preprocessors: 50 min
- Pipeline orchestrator: 15 min
- Worker integration: 10 min
- Tests: 15 min
- **Total: ~1.5 hours**

### Next Steps When Implementing
1. Create `src/preprocessing/` package
2. Implement from BasePreprocessor → specific preprocessors → pipeline
3. Add integration tests before hooking into workers
4. Update development_log.md with completion
5. Update human_summary.md file directory

---

## CRITICAL: Character Sanitization Step (Between Steps 2→3)
**Status:** Issue discovered during testing 2025-11-24
**Priority:** HIGH (blocks AI generation on problematic documents)

### Problem
After RawTextExtractor (Step 2) completes successfully, extracted text sometimes contains:
- Control characters (non-breaking spaces, zero-width characters, etc.)
- Redacted/masked characters (██ from PDFs with redaction)
- Malformed UTF-8 sequences (especially from OCR)
- Special Unicode characters that Ollama can't process

These characters cause Ollama to hang or return garbled output during summarization.

### Solution Required
**Add Step 2.5: Character Sanitization Pipeline** (before Step 3 Smart Preprocessing)

This should:
1. Detect problematic character ranges (control chars, private-use Unicode, etc.)
2. Replace with safe equivalents:
   - Redacted chars (██) → [REDACTED]
   - Non-breaking spaces → regular spaces
   - Control characters → remove or replace with space
   - Invalid UTF-8 sequences → remove or replace with ?
3. Preserve document integrity (don't remove important content)
4. Log what was sanitized for debugging

### Implementation Location
```
Step 2: RawTextExtractor (✅ complete)
Step 2.5: CharacterSanitizer (⬅️ NEW - add here)
Step 3: SmartPreprocessingPipeline (planned)
Step 4: VocabularyExtraction (existing)
```

### Testing Notes
- Test with OCR documents (likely to have spurious chars)
- Test with redacted PDFs (██ characters)
- Test with mixed-encoding documents
- Verify Ollama receives clean, processable text

---

*This file captures approved roadmap items and discussion outcomes. Items here are ready for implementation unless explicitly marked as "Future Consideration."*
