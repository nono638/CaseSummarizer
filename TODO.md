# LocalScribe TODO

> **Purpose:** Backlog of future features, improvements, and ideas. Items here are not yet implemented.
> Updated: 2025-11-29 (Session 21)

---

## High Priority

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
