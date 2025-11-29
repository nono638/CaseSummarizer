# LocalScribe Program Architecture

> **Maintainability Note**: This document uses [Mermaid](https://mermaid.js.org/) diagrams for easy updates. When the codebase changes, update the relevant diagram section. Most Markdown viewers (GitHub, VS Code, Obsidian) render Mermaid natively.

## Quick Navigation

- [High-Level Overview](#high-level-overview)
- [User Interface Layer](#user-interface-layer)
- [Processing Pipeline](#processing-pipeline)
- [Multi-Document Summarization Pipeline](#multi-document-summarization-pipeline)
- [AI Integration Layer](#ai-integration-layer)
- [Vocabulary Extraction System](#vocabulary-extraction-system)
- [Parallel Processing Architecture](#parallel-processing-architecture)
- [Configuration & Settings](#configuration--settings)
- [Complete Data Flow](#complete-data-flow-diagram)
- [File Directory](#file-directory-quick-reference)

---

## High-Level Overview

```mermaid
flowchart TB
    subgraph USER["User Input"]
        Files["PDF/TXT/RTF Files"]
        Settings["Settings & Preferences"]
    end

    subgraph UI["UI LAYER (CustomTkinter)"]
        MainWindow["MainWindow<br/>src/ui/main_window.py"]
        Widgets["Widgets<br/>FileTable, ModelSelector"]
        Output["DynamicOutput<br/>Results Display"]
    end

    subgraph WORKERS["WORKER THREADS"]
        ProcessingWorker["ProcessingWorker<br/>Document Extraction"]
        VocabWorker["VocabularyWorker<br/>Term Extraction"]
        AIWorker["AIWorkerManager<br/>Summarization"]
    end

    subgraph PIPELINE["PROCESSING PIPELINE"]
        Extract["EXTRACT<br/>PDF/TXT/RTF"]
        Sanitize["SANITIZE<br/>Unicode/Mojibake"]
        Preprocess["PREPROCESS<br/>Headers/Q&A"]
        Summarize["SUMMARIZE<br/>AI/Ollama"]
    end

    subgraph SUPPORT["SUPPORT SYSTEMS"]
        Config["CONFIG<br/>config/"]
        Logging["LOGGING<br/>debug mode"]
        Vocab["VOCABULARY<br/>spaCy/NER"]
        Prefs["SETTINGS<br/>user prefs"]
    end

    Files --> UI
    Settings --> UI
    UI <-->|ui_queue| WORKERS
    WORKERS --> PIPELINE
    PIPELINE --> Output
    SUPPORT -.-> PIPELINE
```

### Core Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Separation of Concerns** | UI, messaging, workflow, and processing are decoupled |
| **Non-blocking UI** | All heavy processing in background threads/processes |
| **Parallel Processing** | Strategy Pattern enables swappable execution modes |
| **Graceful Degradation** | Fallbacks at every stage if components fail |
| **Dependency Injection** | All major components accept optional adapters for testing |

---

## User Interface Layer

### MainWindow Structure

```mermaid
flowchart TB
    subgraph MainWindow["MainWindow (ctk.CTk)"]
        subgraph Toolbar
            SelectFiles["Select Files Button"]
            FileCount["Files Count Label"]
            MenuBar["Menu Bar (File, Help)"]
        end

        subgraph Quadrants["4-Quadrant Layout"]
            subgraph TL["Top-Left"]
                FileTable["FileReviewTable<br/>Treeview with status"]
            end
            subgraph TR["Top-Right"]
                ModelSelect["ModelSelectionWidget<br/>Model + Prompt dropdowns"]
            end
            subgraph BL["Bottom-Left"]
                OutputOpts["OutputOptionsWidget<br/>Checkboxes + Slider"]
            end
            subgraph BR["Bottom-Right"]
                DynamicOut["DynamicOutputWidget<br/>Results + Copy/Save"]
            end
        end

        subgraph StatusBar
            StatusLabel["Status Label"]
            ProgressBar["Progress Bar"]
            SysMon["SystemMonitor<br/>CPU/RAM"]
        end

        subgraph Background["Background Components"]
            Queue["ui_queue (Queue)"]
            Handler["QueueMessageHandler"]
            Orchestrator["WorkflowOrchestrator"]
        end
    end

    Toolbar --> Quadrants
    Quadrants --> StatusBar
    Queue <--> Handler
    Handler --> Quadrants
```

### UI Component Hierarchy

| Component | Location | Purpose |
|-----------|----------|---------|
| `MainWindow` | `src/ui/main_window.py` | Central UI coordinator |
| `FileReviewTable` | `src/ui/widgets.py` | File list with status/confidence |
| `ModelSelectionWidget` | `src/ui/widgets.py` | Model + prompt dropdown selection |
| `OutputOptionsWidget` | `src/ui/widgets.py` | Output toggles + word count slider |
| `DynamicOutputWidget` | `src/ui/dynamic_output.py` | Tabbed results display |
| `SystemMonitor` | `src/ui/system_monitor.py` | CPU/RAM usage display |
| `QueueMessageHandler` | `src/ui/queue_message_handler.py` | Routes worker messages to UI |
| `WorkflowOrchestrator` | `src/ui/workflow_orchestrator.py` | Processing state machine |

### Message Flow

```mermaid
sequenceDiagram
    participant UI as MainWindow
    participant Queue as ui_queue
    participant Handler as QueueMessageHandler
    participant Worker as Worker Threads

    UI->>Worker: Start processing
    loop Every 100ms
        UI->>Queue: Poll for messages
        Queue-->>UI: Message batch
        UI->>Handler: Route messages
        Handler->>UI: Update widgets
    end
    Worker->>Queue: progress
    Worker->>Queue: file_processed
    Worker->>Queue: summary_result
    Worker->>Queue: processing_finished
```

**Message Types:**
- `progress` → Progress bar + status label
- `file_processed` → FileReviewTable row update
- `processing_finished` → WorkflowOrchestrator.on_extraction_complete()
- `vocab_csv_generated` → DynamicOutputWidget vocabulary tab
- `summary_result` → DynamicOutputWidget summary tab
- `multi_doc_result` → DynamicOutputWidget (all summaries)
- `error` → Error dialog + UI reset

---

## Processing Pipeline

### Document Processing Stages

```mermaid
flowchart TB
    Input["User selects files<br/>(PDF, TXT, RTF)"]

    subgraph Stage1["STEP 1-2: EXTRACTION & NORMALIZATION"]
        direction TB
        PDF["PDF (text)<br/>pdfplumber"]
        TXT["TXT<br/>direct read"]
        RTF["RTF<br/>striprtf"]
        OCR["PDF (scanned)<br/>pdf2image + pytesseract"]

        Normalize["BASIC NORMALIZATION<br/>• De-hyphenation<br/>• Page number removal<br/>• Whitespace cleanup"]

        PDF --> Normalize
        TXT --> Normalize
        RTF --> Normalize
        OCR --> Normalize
    end

    subgraph Stage2["STEP 2.5: CHARACTER SANITIZATION"]
        Sanitize["CharacterSanitizer.sanitize()"]
        S1["1. Fix mojibake (ftfy)"]
        S2["2. Unicode normalization (NFKC)"]
        S3["3. Transliterate accents (unidecode)"]
        S4["4. Remove control characters"]
        S5["5. Handle redactions → [REDACTED]"]
        S6["6. Whitespace normalization"]

        Sanitize --> S1 --> S2 --> S3 --> S4 --> S5 --> S6
    end

    subgraph Stage3["STEP 3: SMART PREPROCESSING"]
        Pipeline["PreprocessingPipeline.process()"]
        P1["TitlePageRemover<br/>Score-based cover detection"]
        P2["HeaderFooterRemover<br/>Frequency analysis"]
        P3["LineNumberRemover<br/>Transcript line numbers"]
        P4["QAConverter<br/>Q./A. → Question:/Answer:"]

        Pipeline --> P1 --> P2 --> P3 --> P4
    end

    Output["Clean text ready for<br/>AI summarization"]

    Input --> Stage1
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Output
```

**File Locations:**
- Extraction: `src/extraction/raw_text_extractor.py`
- Sanitization: `src/sanitization/character_sanitizer.py`
- Preprocessing: `src/preprocessing/` (pipeline.py, title_page_remover.py, etc.)

---

## Multi-Document Summarization Pipeline

### Overview: Thread-Through Focus Architecture

This is the core innovation - user's focus areas are threaded through every stage.

```mermaid
flowchart TB
    Template["User's Template Selection<br/>e.g., 'injuries-focus.txt'"]

    subgraph Stage0["STAGE 0: FOCUS EXTRACTION"]
        FocusExtract["AIFocusExtractor<br/>src/prompt_focus_extractor.py"]
        FocusResult["Focus = {<br/>  emphasis: 'injuries, timeline...',<br/>  instructions: '1. Identify injuries...'<br/>}"]
        FocusExtract --> FocusResult
    end

    subgraph Docs["Input Documents"]
        Doc1["Document 1<br/>complaint.pdf"]
        Doc2["Document 2<br/>deposition.pdf"]
        Doc3["Document 3<br/>motion.pdf"]
    end

    subgraph Stage1["STAGE 1: CHUNKING"]
        Chunk["Split into ~1000-word chunks<br/>src/progressive_summarizer.py"]
    end

    subgraph Stage2["STAGE 2: CHUNK SUMMARIZATION"]
        ChunkSum["Focus-Aware Prompts<br/>src/summarization/document_summarizer.py"]
        ChunkPrompt["'Pay attention to: {emphasis}'"]
        ChunkSum --> ChunkPrompt
    end

    subgraph Stage3["STAGE 3: PER-DOCUMENT SUMMARY"]
        DocSum["Combine chunk summaries<br/>create_document_final_prompt()"]
        DocPrompt["'Preserve info about: {emphasis}'"]
        DocSum --> DocPrompt
    end

    subgraph Stage4["STAGE 4: META-SUMMARY"]
        Meta["Synthesize all documents<br/>create_meta_summary_prompt()"]
        MetaPrompt["'Create summary that:<br/>{instructions}'"]
        Meta --> MetaPrompt
    end

    FinalOutput["MultiDocumentSummaryResult<br/>• individual_summaries<br/>• meta_summary"]

    Template --> Stage0
    Stage0 --> Stage1
    Docs --> Stage1
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Stage4
    Stage4 --> FinalOutput
```

### Focus Threading Summary

| Stage | What's Used | Purpose |
|-------|-------------|---------|
| **Focus Extraction** | Full template content | AI extracts emphasis + instructions |
| **Chunk Prompts** | `emphasis` string | Capture focus-related details early |
| **Document Final** | `emphasis` string | Preserve focus info in doc summary |
| **Meta-Summary** | `instructions` list | Structure final output per user's needs |

### Actual Prompt Templates

#### Chunk Summarization Prompt (Stage 2)

```
<|system|>
You are a legal case summarizer analyzing sections of a long document.
Your summaries will be combined to create overview.
<|end|>
<|user|>
DOCUMENT CONTEXT: {progressive_summary_so_far}
PREVIOUS SECTION: {previous_chunk_summary}

Summarize this section in approximately 75 words.

Focus on key facts, developments, and decisions.
Pay particular attention to: {focus.emphasis}  ← USER'S FOCUS

Preserve any information related to these focus areas.

SECTION TEXT: {chunk_text}
<|end|>
<|assistant|>
```

#### Document Final Summary Prompt (Stage 3)

```
<|system|>
You are creating a comprehensive summary of a legal document.
<|end|>
<|user|>
Create a 200-word summary of "{filename}" from these sections.

Pay particular attention to: {focus.emphasis}  ← USER'S FOCUS

Preserve any information related to these focus areas.
Present in logical, chronological order where possible.

SECTION SUMMARIES:
{all_chunk_summaries_joined}
<|end|>
<|assistant|>
```

#### Meta-Summary Prompt (Stage 4)

```
<|system|>
You are a legal document analyst reviewing summaries of {doc_count}
documents from a single case.
<|end|>
<|user|>
Individual document summaries:

--- complaint.pdf ---
{document_1_summary}

--- deposition.pdf ---
{document_2_summary}

Create a comprehensive meta-summary (350-500 words) that:
{focus.instructions}  ← FULL INSTRUCTIONS FROM USER'S TEMPLATE

Present in logical, chronological order where appropriate.
Synthesize information across documents.
<|end|>
<|assistant|>
```

### Caching Strategy

```mermaid
flowchart LR
    subgraph Level1["Level 1: Class Cache"]
        L1["AIFocusExtractor._cache<br/>Key: MD5(template_content)[:8]"]
    end

    subgraph Level2["Level 2: Instance Cache"]
        L2["MultiDocPromptAdapter._focus_cache<br/>Key: '{model}/{preset}'"]
    end

    Request["get_focus_for_preset()"]

    Request --> L2
    L2 -->|MISS| L1
    L1 -->|MISS| AI["Call Ollama AI"]
    L1 -->|HIT| Return1["Return cached"]
    L2 -->|HIT| Return2["Return cached"]
    AI --> L1
```

**Why content hash?** If user edits their template file, the hash changes and focus is re-extracted. The `preset_id` alone wouldn't detect file changes.

---

## AI Integration Layer

```mermaid
flowchart TB
    subgraph OllamaManager["OllamaModelManager<br/>src/ai/ollama_model_manager.py"]
        API["REST API Client"]
        Methods["Methods:<br/>• get_available_models()<br/>• load_model(name)<br/>• generate_text(prompt)<br/>• health_check()"]
    end

    subgraph Ollama["Ollama Service<br/>localhost:11434"]
        Tags["/api/tags - list models"]
        Generate["/api/generate - generate text"]
        Pull["/api/pull - download model"]
    end

    subgraph TemplateManager["PromptTemplateManager<br/>src/prompt_template_manager.py"]
        BuiltIn["Built-in Prompts<br/>config/prompts/"]
        UserPrompts["User Prompts<br/>%APPDATA%/LocalScribe/prompts/"]
    end

    subgraph PostProcessor["SummaryPostProcessor<br/>src/ai/summary_post_processor.py"]
        LengthEnforce["Enforce length constraints<br/>Condense if > target + 20%"]
    end

    OllamaManager <-->|HTTP| Ollama
    TemplateManager --> OllamaManager
    OllamaManager --> PostProcessor
```

**Configuration (from `src/config.py`):**
- `OLLAMA_API_BASE = "http://localhost:11434"`
- `OLLAMA_CONTEXT_WINDOW = 2048` tokens
- `OLLAMA_TIMEOUT_SECONDS = 600`

---

## Vocabulary Extraction System

```mermaid
flowchart TB
    Input["Sanitized Document Text"]

    subgraph VocabExtractor["VocabularyExtractor<br/>src/vocabulary/vocabulary_extractor.py"]
        SpaCy["spaCy NLP<br/>en_core_web_sm model"]

        subgraph Extraction
            NER["Named Entity Recognition<br/>PERSON, ORG, GPE, DATE..."]
            Technical["Technical Terms<br/>Legal/medical vocabulary"]
            Rare["Rare Words<br/>Frequency analysis"]
        end

        subgraph Filtering
            StopWords["Remove stopwords"]
            CommonFilter["Remove common words"]
            Dedupe["Deduplicate"]
        end
    end

    Output["VocabularyResult<br/>• term, category, frequency, context<br/>• CSV export ready"]

    Input --> SpaCy
    SpaCy --> Extraction
    Extraction --> Filtering
    Filtering --> Output
```

**Categories Extracted:**
- **PERSON**: Names of individuals
- **ORG**: Organizations, companies
- **GPE**: Geographic locations
- **DATE**: Dates and time expressions
- **LEGAL**: Legal terms (plaintiff, defendant, motion)
- **MEDICAL**: Medical terminology
- **TECHNICAL**: Domain-specific terms
- **UNKNOWN**: Rare words not categorized

---

## Parallel Processing Architecture

```mermaid
flowchart TB
    subgraph Strategies["Execution Strategies<br/>src/summarization/execution_strategies.py"]
        Sequential["SequentialStrategy<br/>One doc at a time"]
        Parallel["ParallelStrategy<br/>ThreadPoolExecutor"]
    end

    subgraph Orchestrator["MultiDocumentOrchestrator<br/>src/summarization/multi_document_orchestrator.py"]
        Map["MAP PHASE<br/>Per-document summaries"]
        Reduce["REDUCE PHASE<br/>Meta-summary"]
    end

    Documents["Documents to Process"]

    Documents --> Orchestrator
    Orchestrator --> Strategies

    Sequential -->|"For testing/debugging"| Map
    Parallel -->|"For production"| Map
    Map --> Reduce
```

**Strategy Selection:**
- `SequentialStrategy`: Processes one document at a time (safer, easier to debug)
- `ParallelStrategy`: Uses ThreadPoolExecutor for concurrent processing (faster)

---

## Configuration & Settings

### Configuration Files

| File | Purpose |
|------|---------|
| `config/settings.json` | Runtime settings (Ollama URL, timeouts) |
| `config/chunking_config.yaml` | Chunking parameters (words per chunk, overlap) |
| `config/prompts/{model}/` | Model-specific prompt templates |
| `config/vocabulary_settings.yaml` | Vocabulary extraction settings |

### User Settings Location

```
%APPDATA%/LocalScribe/
├── settings.json          # User preferences
├── prompts/               # Custom prompt templates
│   └── phi-3-mini/
│       └── my-custom.txt
└── logs/                  # Debug logs (if enabled)
```

### Settings GUI

```mermaid
flowchart TB
    subgraph SettingsDialog["SettingsDialog<br/>src/ui/settings/"]
        GeneralTab["General Tab<br/>• Debug mode toggle<br/>• Default paths"]
        OllamaTab["Ollama Tab<br/>• API URL<br/>• Timeouts"]
        ProcessingTab["Processing Tab<br/>• Parallel processing<br/>• Chunk sizes"]
    end

    SettingsManager["SettingsManager<br/>src/settings_manager.py"]

    SettingsDialog <--> SettingsManager
    SettingsManager -->|Save| ConfigFile["settings.json"]
```

---

## Complete Data Flow Diagram

```mermaid
flowchart TB
    subgraph Input["1. USER INPUT"]
        Files["Select PDF/TXT/RTF files"]
        Model["Select AI model"]
        Prompt["Select prompt template"]
        Options["Set output options"]
    end

    subgraph Extract["2. EXTRACTION"]
        RawText["RawTextExtractor<br/>PDF → pdfplumber<br/>RTF → striprtf<br/>Scanned → OCR"]
    end

    subgraph Clean["3. CLEANING"]
        Sanitize["CharacterSanitizer<br/>Fix encoding, mojibake"]
        Preprocess["PreprocessingPipeline<br/>Remove headers, convert Q&A"]
    end

    subgraph Focus["4. FOCUS EXTRACTION"]
        FocusAI["AIFocusExtractor<br/>Analyze template → emphasis + instructions"]
    end

    subgraph Summarize["5. SUMMARIZATION"]
        Chunk["Progressive Chunking<br/>~1000 words each"]
        ChunkSum["Chunk Summaries<br/>Focus-aware prompts"]
        DocSum["Document Summaries<br/>Combine chunks"]
        MetaSum["Meta-Summary<br/>Synthesize all docs"]
    end

    subgraph Vocab["6. VOCABULARY (Optional)"]
        VocabExt["VocabularyExtractor<br/>spaCy NER + rare words"]
    end

    subgraph Output["7. OUTPUT"]
        Display["DynamicOutputWidget<br/>View summaries"]
        Export["Export Options<br/>Copy, Save, CSV"]
    end

    Input --> Extract
    Extract --> Clean
    Clean --> Focus
    Focus --> Summarize
    Clean --> Vocab
    Summarize --> Output
    Vocab --> Output
```

---

## File Directory Quick Reference

### Core Application

| File | Purpose |
|------|---------|
| `src/main.py` | Application entry point |
| `src/config.py` | Global configuration constants |
| `src/logging_config.py` | Debug logging setup |
| `src/settings_manager.py` | User preferences management |

### Extraction & Processing

| File | Purpose |
|------|---------|
| `src/extraction/raw_text_extractor.py` | PDF/TXT/RTF text extraction |
| `src/sanitization/character_sanitizer.py` | Unicode normalization, mojibake fixes |
| `src/preprocessing/pipeline.py` | Preprocessing pipeline orchestrator |
| `src/preprocessing/title_page_remover.py` | Cover page detection/removal |
| `src/preprocessing/header_footer_remover.py` | Repeated header/footer removal |
| `src/preprocessing/line_number_remover.py` | Transcript line number removal |
| `src/preprocessing/qa_converter.py` | Q./A. to Question:/Answer: conversion |

### AI & Summarization

| File | Purpose |
|------|---------|
| `src/ai/ollama_model_manager.py` | Ollama REST API client |
| `src/prompt_template_manager.py` | Prompt template loading/management |
| `src/prompt_focus_extractor.py` | AI-based focus area extraction |
| `src/prompt_adapters.py` | Stage-specific prompt generation |
| `src/progressive_summarizer.py` | Chunking and progressive context |
| `src/summarization/document_summarizer.py` | Single document summarization |
| `src/summarization/multi_document_orchestrator.py` | Multi-doc coordination |
| `src/summarization/execution_strategies.py` | Sequential/parallel execution |
| `src/summarization/result_types.py` | Result dataclasses |
| `src/ai/summary_post_processor.py` | Length enforcement |

### Vocabulary

| File | Purpose |
|------|---------|
| `src/vocabulary/vocabulary_extractor.py` | spaCy-based term extraction |

### User Interface

| File | Purpose |
|------|---------|
| `src/ui/main_window.py` | Central UI coordinator |
| `src/ui/quadrant_builder.py` | 4-quadrant layout construction |
| `src/ui/widgets.py` | FileTable, ModelSelector, OutputOptions |
| `src/ui/workers.py` | ProcessingWorker, VocabularyWorker, etc. |
| `src/ui/workflow_orchestrator.py` | Processing state machine |
| `src/ui/queue_message_handler.py` | Worker → UI message routing |
| `src/ui/dynamic_output.py` | Results display widget |
| `src/ui/system_monitor.py` | CPU/RAM usage display |
| `src/ui/settings/` | Settings dialog components |

---

## Updating This Document

When making changes to LocalScribe:

1. **New component added?** Add to the relevant section's Mermaid diagram
2. **File moved/renamed?** Update the File Directory table
3. **New message type?** Add to Message Flow section
4. **Processing stage changed?** Update the Complete Data Flow diagram

Mermaid diagrams can be previewed in:
- GitHub (native support)
- VS Code (with Markdown Preview Mermaid extension)
- [Mermaid Live Editor](https://mermaid.live/)

---

*This document serves as the architectural reference for LocalScribe. Last updated: Session 21 (2025-11-29)*
