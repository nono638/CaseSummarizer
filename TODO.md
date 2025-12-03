# LocalScribe TODO

> **Purpose:** Backlog of future features, improvements, and ideas. Items here are not yet implemented.
> Updated: 2025-12-03 (Session 40 - continued)

---

## High Priority

### ✅ Case Briefing Generator - Empty Extraction Bug (FIXED - Session 40)

**Status:** FIXED - Root cause identified and resolved
**Resolution:** DocumentChunker paragraph splitting bug

#### Root Cause (Identified Session 40 continuation)

The `DocumentChunker._split_into_paragraphs()` method split on double newlines (`\n\s*\n`), but:
1. OCR/PDF extracted text often uses **single newlines** only
2. When no double newlines exist, the entire 43,262-char document became ONE "paragraph"
3. The chunking logic couldn't split an oversized first paragraph (empty `current_text_parts` check failed)
4. LLM couldn't process 43K chars → returned empty JSON arrays

#### Fix Applied (src/briefing/chunker.py)

1. **Line-based fallback**: If any paragraph > max_chars, re-split using single newlines
2. **Force-split oversized**: Last-resort splitting at sentence/word boundaries for any remaining large segments
3. **Three-tier splitting**: Double newlines → Single newlines → Character-based

#### Test Results

- Before fix: 43,262 chars → 1 chunk
- After fix: 43,262 chars → ~24 chunks (avg 1,750 chars each)
- All 224 tests pass

#### Next Steps

- [ ] Re-test Case Briefing with real documents through the UI
- [ ] Verify extraction produces actual party/allegation data
- [ ] Consider adding DEBUG_MODE logging for chunk contents

#### Architecture Question (Sleep On It)

Should Case Briefing use semantic gradient chunking (from `ChunkingEngine`) instead of character-based splitting?

**Current recommendation:** Keep separate chunkers
- Legal docs have explicit section markers → section-aware splitting is better
- Embedding overhead not justified for extraction task
- See plan file: `C:\Users\noahc\.claude\plans\sparkling-wondering-turtle.md`

---

### 🟡 Session 30-31 Bug Fixes (In Progress)

**Status:** Q&A retrieval fixed (Session 31), vocabulary still needs work
**Priority:** HIGH - Need to test Q&A with real documents

#### Fixed Issues ✅

5. **~~Change Q&A retrieval algorithm from BM25 to BM25+~~** ✅ COMPLETE (Session 31)
   - Created new `src/retrieval/` package with hybrid BM25+/FAISS system
   - BM25+ is now primary retriever (weight 1.0), FAISS secondary (weight 0.5)
   - Lowered threshold from 0.5 to 0.1 for more results
   - 17 new tests passing

#### Remaining Issues

1. **Vocabulary returns 0 terms despite documents having text**
   - `combine_document_texts()` may be returning empty string
   - Debug logging added but not appearing (check if DEBUG_MODE is True)
   - spaCy NER may not be finding entities in legal documents

2. **Q&A may still return "no information found"** - NEEDS TESTING
   - Hybrid retrieval infrastructure complete but not tested with real documents
   - Run app with DEBUG_MODE=True to verify BM25+ is working
   - Check log for `[BM25+]` and `[HybridRetriever]` messages

3. **Q&A not appearing in dropdown despite running**
   - QAWorker runs (we see retriever warnings in log)
   - But `update_outputs(qa_results=...)` may be called with empty list
   - Or ordering issue with vocab vs Q&A dropdown refresh

4. **"Not yet generated" shown for empty vocab list**
   - Confusing UX - should say "No vocabulary terms found"
   - Fix: Update `_display_csv()` message for empty vs None cases

6. **Add corpus name validation (prevent invalid directory characters)**
   - User can enter slashes, periods, or other problematic characters
   - Need to sanitize corpus names before creating directories
   - Add validation in `CorpusDialog` when user creates/renames corpus
   - Invalid chars: `\ / : * ? " < > |` (Windows filesystem)

#### Next Session Testing Steps

```bash
# 1. Enable DEBUG_MODE in config.py (if not already)
# 2. Run app and process a real legal document
# 3. Check log for new hybrid retrieval messages:
#    - "[BM25+] Indexed X chunks..."
#    - "[HybridRetriever] Query: ..."
#    - "[QARetriever] Retrieved X chunks..."
# 4. Verify Q&A answers are no longer "no information found"
# 5. If still broken, check min_score threshold in config.py
```

---

### 🔴 Q&A System Implementation (RAG with FAISS) - IN PROGRESS

**Status:** Phase 1 COMPLETE (infrastructure), Phases 2-3 NOT STARTED (UI & advanced features)
**Priority:** HIGH - Primary new feature for LocalScribe
**Estimated Time:** 2-3 weeks total (Phase 1 done, ~2 weeks remaining)

#### What's Done ✅ (Session 24)

| Component | Status | Notes |
|-----------|--------|-------|
| FAISS vector store | ✅ Complete | File-based, no database needed |
| VectorStoreBuilder | ✅ Complete | Creates indexes from documents |
| QARetriever | ✅ Complete | Retrieves context with source citations |
| QuestionFlowManager | ✅ Complete | Branching question tree (14 questions) |
| Workflow integration | ✅ Complete | Auto-creates vector store after extraction |
| Config & dependencies | ✅ Complete | langchain, faiss-cpu installed |

#### Phase 2: Q&A UI Component (NOT STARTED)

**Estimated Time:** 1 week

- [ ] Add "Q&A Session" tab to DynamicOutputWidget
- [ ] Create chat-style interface (CTkTextbox with scrolling)
- [ ] Question input field with "Ask" button
- [ ] Display answers with source citations
- [ ] Create `QAWorker` class (background thread for retrieval + generation)
- [ ] Add typing indicator while generating
- [ ] Handle `qa_result` message in queue handler
- [ ] Enable/disable Q&A tab based on vector store status

**UI Design:**
```
┌─────────────────────────────────────────────────┐
│  Chat History (scrollable)                      │
│  Q: Who are the plaintiffs?                     │
│  A: The plaintiffs are John Doe and Jane Smith. │
│     Sources: complaint.pdf (Section Parties)    │
├─────────────────────────────────────────────────┤
│  [Ask a question...        ] [Ask] ⏳           │
└─────────────────────────────────────────────────┘
```

#### Phase 3: Smart Questions & Advanced Features (NOT STARTED)

**Estimated Time:** 1 week

- [ ] Auto-detect case type from document content (CaseClassifier)
- [ ] Display suggested questions based on detected case type
- [ ] Implement multi-turn conversation context (include last 3 Q&A pairs)
- [ ] Add "Run All Questions" button (execute branching flow automatically)
- [ ] Chat history export (TXT and Markdown formats)
- [ ] Progress indicator for automated question flow
- [ ] Allow users to edit/add questions in YAML config

#### Key Files

| File | Purpose |
|------|---------|
| `src/vector_store/vector_store_builder.py` | Creates FAISS indexes |
| `src/vector_store/qa_retriever.py` | Retrieves relevant chunks |
| `src/vector_store/question_flow.py` | Branching question logic |
| `config/qa_questions.yaml` | Question definitions (editable) |
| `src/ui/dynamic_output.py` | Will add Q&A tab here |
| `src/ui/workers.py` | Will add QAWorker here |

#### Architecture Notes

- **Vector store** auto-created after document extraction (background thread)
- **File-based persistence** - no database config needed for Windows installer
- **FAISS indexes** stored in `%APPDATA%/LocalScribe/vector_stores/<case_id>/`
- **Embeddings** use same model as ChunkingEngine (`all-MiniLM-L6-v2`)
- **Chunking** for Q&A uses 500 char chunks with 50 char overlap (optimized for retrieval)

---

### 🔴 Vocabulary CSV Quality - Needs Brainstorming

**Status:** Unsatisfactory - requires fundamental rethinking
**Priority:** HIGH

The current vocabulary extraction output is not meeting user needs. Before implementing specific fixes, we need to brainstorm the core approach.

#### Current Problems
- Too many false positives (OCR errors, typos, irrelevant terms)
- Single-occurrence terms cluttering results
- Unclear what makes a term "useful" for a stenographer

#### Brainstorming Directions

**Data Science Approaches:**
- [ ] Clustering similar terms (group "McDonaId" with "McDonald" via edit distance)
- [ ] TF-IDF scoring across document corpus (what's rare globally but common locally?)
- [ ] Train a classifier on user-excluded terms (learn what users DON'T want)
- [ ] Use word embeddings to find semantically related terms
- [ ] Analyze the processing_metrics.csv to find patterns in "good" vs "bad" runs

**Rule-Based Approaches:**
- [ ] Frequency thresholds (minimum 2 occurrences)
- [ ] Cross-document analysis (terms in multiple docs = case-relevant)
- [ ] OCR confidence scoring per term
- [ ] Legal/medical domain dictionaries for validation

**User Experience Approaches:**
- [ ] Let users rate terms (thumbs up/down) to build training data
- [ ] Show "confidence" column so users can filter
- [ ] Provide preset filters (e.g., "Names only", "Medical terms only")

#### Questions to Answer
- What does the user actually DO with this vocabulary list?
- What's the workflow after exporting the CSV?
- Are there existing tools/formats stenographers expect?

---

### 🔴 Summary Prompt Quality - Needs Brainstorming

**Status:** Unsatisfactory - summaries don't capture what users need
**Priority:** HIGH

The current AI-generated summaries are not meeting user expectations. Need to fundamentally rethink the prompting strategy.

#### Current Problems
- Summaries may be too generic / not actionable
- May miss key details that matter to the user's workflow
- Unclear if the "thread-through focus" architecture is working as intended
- Model size vs. quality tradeoffs not fully explored

#### Brainstorming Directions

**Prompt Engineering:**
- [ ] A/B test different prompt structures (bullet points vs. narrative)
- [ ] Add explicit "do not include" instructions (boilerplate, procedural text)
- [ ] Chain-of-thought prompting (ask model to reason before summarizing)
- [ ] Few-shot examples of "good" summaries in the prompt
- [ ] Role-specific prompts ("You are a court reporter preparing a case summary...")

**Model & Architecture:**
- [ ] Test larger models (7B, 13B) for quality improvement
- [ ] Fine-tune on legal document summaries (if training data available)
- [ ] Ensemble approach: generate multiple summaries, pick best
- [ ] Retrieval-augmented generation (RAG) with legal knowledge base

**Evaluation:**
- [ ] Create a rubric for "good" summaries (accuracy, completeness, actionability)
- [ ] Side-by-side comparison tool for different prompt versions
- [ ] User feedback collection mechanism
- [ ] Automated metrics (ROUGE, semantic similarity to reference summaries)

**Output Format:**
- [ ] Structured output (JSON with sections) vs. free-form text
- [ ] Templated summaries with fill-in-the-blanks
- [ ] Hierarchical summaries (executive summary → detailed sections)

#### Questions to Answer
- What does the user DO with these summaries?
- What information is CRITICAL vs. nice-to-have?
- Are there existing summary formats in the legal/stenography industry?
- Would users prefer shorter, more frequent summaries or longer comprehensive ones?

---

### Vocabulary CSV Quality Improvements

**Problem:** The current vocabulary extraction produces unsatisfactory results with too many false positives (OCR errors, typos, one-off terms).

#### Proposed Solution: Unified CSV with Filtering Columns

Instead of filtering terms out during extraction, create a **cohesive CSV with all candidate terms** and add columns that enable filtering:

| Column | Description | Use Case |
|--------|-------------|----------|
| `term` | The extracted word/phrase | Primary data |
| `total_frequency` | Total occurrences across ALL documents | Filter: `>= 2` to exclude one-offs |
| `document_count` | Number of documents containing this term | Filter: terms in 2+ docs may be case-relevant |
| `max_doc_frequency` | Highest frequency in any single document | Recurrent in one doc = likely intentional |
| `category` | NER category (Person, Org, Medical, etc.) | Group by type |
| `is_likely_ocr_error` | Boolean flag for suspected OCR issues | Filter out noise |
| `is_likely_typo` | Boolean flag for suspected typos | Filter out noise |

#### Filtering Logic

1. **Minimum frequency threshold**: Only include terms where `total_frequency >= 2`
   - Rationale: Single occurrences are often OCR errors or typos

2. **Recurrence exception**: Even if `document_count == 1`, if `max_doc_frequency >= 3` in that document, include it
   - Rationale: A term appearing 3+ times in one document is probably intentional, not a typo

3. **OCR error detection heuristics**:
   - Contains unusual character sequences (e.g., `rn` that should be `m`)
   - Mixed case in unexpected patterns (e.g., `McDonaId` instead of `McDonald`)
   - Contains digit-letter confusion (e.g., `0` vs `O`, `1` vs `l`)

4. **Typo detection heuristics**:
   - Levenshtein distance of 1-2 from a common word
   - Missing doubled letters
   - Adjacent key substitutions

#### Benefits of This Approach

- **User Control**: Users can apply their own filters in Excel/Sheets
- **Transparency**: See WHY a term was flagged rather than it silently disappearing
- **ML Training Data**: The filtered CSV becomes training data for better future extraction
- **No Information Loss**: Raw data preserved, filtering is additive

#### Implementation Steps

- [ ] Update `VocabularyExtractor` to track per-document frequency
- [ ] Add frequency aggregation across documents
- [ ] Implement OCR error detection heuristics
- [ ] Implement typo detection heuristics
- [ ] Add new columns to CSV output
- [ ] Update UI to show filter summary (e.g., "Showing 45 of 120 terms (75 filtered)")
- [ ] Consider adding filter controls to vocabulary table UI

---

## Medium Priority

### Phase 2.2: Document Prioritization System (Est. 3-4 hours)
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

### Phase 2.7: Model-Aware Prompt Formatting (Est. 1-2 hours)

Detect model type and wrap prompts in model-specific instruction formats.

**The Problem:**
Current code sends raw prompts to all models. Most instruction-tuned models work, but:
- Chat-only models may refuse or produce garbage
- Some models need special formatting (`[INST]...[/INST]`)
- Vocabulary extraction (requiring JSON output) may fail silently

**Implementation:**
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
        return prompt  # Default: try raw prompt
```

**Why This Matters:**
- Future-proofs the app for any Ollama model
- User can freely experiment with different models without code changes
- Prevents silent failures (model returns garbage because prompt format is wrong)

---

### Vocabulary Extraction Enhancement (Est. 2-3 hours)
**Spec Reference:** Section 7.5.2 & 8.2 of PROJECT_OVERVIEW.md

Complete the vocabulary extraction pipeline with per-term definitions:
- Extract rare/technical terms + proper nouns (already working)
- **Batch-generate definitions** for all terms with progress indicator
- **Cache definitions locally** in `%APPDATA%/LocalScribe/cache/definitions.json` to avoid re-processing
- CSV export with Term, Category, Definition, Source columns
- User exclusion system (hide terms from future vocabulary lists)

---

## Lower Priority / Future Phases

### UX: Two-Phase Workflow Clarity (Session 34 observation)

**Current Behavior:** Application has two distinct phases:
1. "Add Files" button → extracts text (timer runs, stops when done)
2. "Perform Tasks" button → runs Q&A/Vocabulary/Summary (user must click)

**Potential Confusion:** User may expect tasks to run automatically after file extraction.

**Possible Improvements:**
- [ ] Add visual cue (highlight/pulse) on "Perform Tasks" button after extraction completes
- [ ] Add notification banner: "Files ready! Click 'Perform Tasks' to continue"
- [ ] Consider auto-start option in settings (for power users)
- [ ] Update status text to be more directive: "Ready to process. Click 'Perform Tasks' to begin."

**Current Status:** Working as designed, but UX could be clearer.

---

### Phase 3: License Server Integration (Est. 4-6 hours)
**Spec Reference:** Section 4 of PROJECT_OVERVIEW.md

Users need to validate licenses and download commercial models via Dropbox:
- License key validation API (HTTP POST to `/api/validate_license`)
- Quota tracking (daily/weekly/monthly/annual limits per license)
- Dropbox model download with progress bar
- Model storage management in `%APPDATA%/LocalScribe/models/`
- License caching (24-hour validity before re-validation)

**Current State:** Not implemented. App uses free Ollama models.

---

### Phase 5: Advanced Features (Post-v1.0)
- Batch processing mode (process multiple cases overnight)
- Template system for custom summary formats
- Integration with court reporter workflow tools
- Export to Word/PDF with formatting
- Compare mode (diff between versions of documents)

---

## Questions to Address Later

- Should we support other file formats (DOCX, ODT)?
- What's the best way to handle multi-language documents?
- Should we add a "confidence threshold" setting that auto-rejects low-quality OCR?
- Which larger model (7B, 13B) offers the best quality/speed trade-off for legal documents?

---

## Technical Debt to Monitor

- None critical at present

---

*This file captures backlog items and future feature ideas. For current session work, see `development_log.md`.*
