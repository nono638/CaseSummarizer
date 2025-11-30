"""
LocalScribe Configuration Module
Centralized configuration for the application.
"""

import os
from pathlib import Path

import yaml

# Debug Mode Configuration
DEBUG_MODE = os.environ.get('DEBUG', 'false').lower() == 'true'

# Application Paths
APP_NAME = "LocalScribe"
APPDATA_DIR = Path(os.environ.get('APPDATA', os.path.expanduser('~/.config'))) / APP_NAME
MODELS_DIR = APPDATA_DIR / "models"
CACHE_DIR = APPDATA_DIR / "cache"
LOGS_DIR = APPDATA_DIR / "logs"
CONFIG_DIR = APPDATA_DIR / "config"

# Data directory for ML training data
DATA_DIR = APPDATA_DIR / "data"

# Ensure directories exist
for directory in [APPDATA_DIR, MODELS_DIR, CACHE_DIR, LOGS_DIR, CONFIG_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Processing Metrics CSV (for future ML prediction of processing time)
PROCESSING_METRICS_CSV = DATA_DIR / "processing_metrics.csv"

# File Processing Limits
MAX_FILE_SIZE_MB = 500
LARGE_FILE_WARNING_MB = 100
MIN_LINE_LENGTH = 15
MIN_DICTIONARY_CONFIDENCE = 60  # Percentage

# OCR Configuration
OCR_DPI = 300
OCR_CONFIDENCE_THRESHOLD = 70  # Files below this are pre-unchecked

# AI Model Configuration
OLLAMA_API_BASE = "http://localhost:11434"  # Default Ollama API endpoint
OLLAMA_MODEL_NAME = "gemma3:1b"  # Default model for the application
OLLAMA_MODEL_FALLBACK = "gemma3:1b"  # Fallback if the primary model fails
OLLAMA_TIMEOUT_SECONDS = 600  # 10 minutes for long summaries
QUEUE_TIMEOUT_SECONDS = 2.0  # Timeout for multiprocessing queue operations

# Context Window Configuration
# Optimized for CPU inference on business laptops (8-16GB RAM, no GPU)
# Research shows: 2k context = ~150 tokens/sec, 8k = ~43 t/s, 64k = ~9 t/s
OLLAMA_CONTEXT_WINDOW = 2048  # Tokens - matches Ollama's default for CPU performance

# --- New Model Configuration System ---
MODEL_CONFIG_FILE = Path(__file__).parent.parent / "config" / "models.yaml"
MODEL_CONFIGS = {}

def load_model_configs():
    """Loads model configurations from config/models.yaml."""
    global MODEL_CONFIGS
    try:
        with open(MODEL_CONFIG_FILE) as f:
            data = yaml.safe_load(f)
            MODEL_CONFIGS = data.get('models', {})
        if DEBUG_MODE and MODEL_CONFIGS:
            from src.logging_config import debug_log
            debug_log(f"[Config] Loaded {len(MODEL_CONFIGS)} model configurations from {MODEL_CONFIG_FILE}")
    except FileNotFoundError:
        if DEBUG_MODE:
            from src.logging_config import debug_log
            debug_log(f"[Config] WARNING: Model config file not found at {MODEL_CONFIG_FILE}. Using fallback values.")
        MODEL_CONFIGS = {}
    except Exception as e:
        from src.logging_config import debug_log
        debug_log(f"[Config] ERROR: Failed to load or parse model config file: {e}")
        MODEL_CONFIGS = {}

def get_model_config(model_name: str) -> dict:
    """
    Returns the configuration for a specific model, with fallbacks.

    Args:
        model_name: The name of the model (e.g., 'gemma3:1b').

    Returns:
        A dictionary containing the model's configuration.
    """
    if not MODEL_CONFIGS:
        load_model_configs()

    # 1. Try to find the exact model name
    if model_name in MODEL_CONFIGS:
        return MODEL_CONFIGS[model_name]

    # 2. Fallback for base names (e.g., user has 'gemma3:1b-instruct', config has 'gemma3:1b')
    base_name = model_name.split(':')[0]
    for name, config in MODEL_CONFIGS.items():
        if name.startswith(base_name):
            if DEBUG_MODE:
                from src.logging_config import debug_log
                debug_log(f"[Config] Found partial match for '{model_name}': using config for '{name}'.")
            return config

    # 3. Fallback to the default model name if no match found
    if OLLAMA_MODEL_NAME in MODEL_CONFIGS:
        if DEBUG_MODE:
            from src.logging_config import debug_log
            debug_log(f"[Config] WARNING: Model '{model_name}' not found. Falling back to default model '{OLLAMA_MODEL_NAME}'.")
        return MODEL_CONFIGS[OLLAMA_MODEL_NAME]

    # 4. Absolute fallback if config is empty or default is missing
    if DEBUG_MODE:
        from src.logging_config import debug_log
        debug_log("[Config] WARNING: No model configurations found. Using hard-coded fallback values.")
    return {
        'context_window': 4096,
        'max_input_tokens': 2048,
    }

# Load configs on module import
load_model_configs()
# --- End New Model Configuration System ---


# Default Processing Settings
DEFAULT_SUMMARY_WORDS = 200
MIN_SUMMARY_WORDS = 100
MAX_SUMMARY_WORDS = 500

# Summary Length Enforcement Settings
# When a generated summary exceeds target by more than TOLERANCE, it will be condensed
SUMMARY_LENGTH_TOLERANCE = 0.20  # 20% overage allowed (200 words → accepts up to 240)
SUMMARY_MAX_CONDENSE_ATTEMPTS = 3  # Maximum condensation attempts before returning best effort

# Data Files
GOOGLE_FREQ_LIST = Path(__file__).parent.parent / "data" / "frequency" / "google_word_freq.txt"
LEGAL_KEYWORDS_NY = Path(__file__).parent.parent / "data" / "keywords" / "legal_keywords_ny.txt"
LEGAL_KEYWORDS_CA = Path(__file__).parent.parent / "data" / "keywords" / "legal_keywords_ca.txt"

# New: Vocabulary Extractor Data Files
LEGAL_EXCLUDE_LIST_PATH = Path(__file__).parent.parent / "config" / "legal_exclude.txt"
MEDICAL_TERMS_LIST_PATH = Path(__file__).parent.parent / "config" / "medical_terms.txt"
# User-specific vocabulary exclusions (stored in AppData, user can add via right-click)
USER_VOCAB_EXCLUDE_PATH = CONFIG_DIR / "user_vocab_exclude.txt"

# Vocabulary Extraction Rarity Settings
# Path to Google word frequency dataset (word\tfrequency_count format)
GOOGLE_WORD_FREQUENCY_FILE = Path(__file__).parent.parent / "Word_rarity-count_1w.txt"
# Words with rank >= threshold are considered rare
# Higher threshold = more aggressive filtering (fewer terms extracted)
# 150000 = bottom 55% of vocabulary (original, too permissive)
# 180000 = bottom 46% of vocabulary (balanced)
# 200000 = bottom 40% of vocabulary (aggressive)
# Examples: "medical" (rank 501) FILTERED, "adenocarcinoma" (rank >180K) EXTRACTED
# Set to -1 to disable frequency-based filtering (use WordNet only)
VOCABULARY_RARITY_THRESHOLD = 180000
# When enabled, sort CSV results by rarity (words not in dataset first, then lowest frequency count)
VOCABULARY_SORT_BY_RARITY = True

# Minimum occurrences for term extraction (filters single-occurrence OCR errors/typos)
# Set to 1 to disable (extract all terms regardless of frequency)
# Set to 2 to require terms appear at least twice (recommended - filters OCR errors)
# Set to 3+ for very conservative filtering
# Note: PERSON entities are exempt (party names may appear once but are important)
VOCABULARY_MIN_OCCURRENCES = 2

# GUI Display Limits for Vocabulary Table
# Based on tkinter Treeview performance testing:
# - < 100 rows: Excellent performance
# - 100-200 rows: Generally acceptable
# - 200+ rows: Performance degrades, especially with text wrapping
# Default: 50 rows (conservative for responsiveness)
# Maximum ceiling: 200 rows (hard limit to prevent GUI freezing)
VOCABULARY_DISPLAY_LIMIT = 50   # User-configurable default (conservative)
VOCABULARY_DISPLAY_MAX = 200    # Hard ceiling - cannot exceed this

# Vocabulary Display Pagination (Session 16 - GUI responsiveness)
# Controls async batch insertion to prevent GUI freezing during large loads
VOCABULARY_ROWS_PER_PAGE = 50     # Initial rows shown; "Load More" adds more
VOCABULARY_BATCH_INSERT_SIZE = 20  # Rows inserted per async batch
VOCABULARY_BATCH_INSERT_DELAY_MS = 10  # Delay between batches (ms)

# spaCy Model Download Timeouts (Session 15)
# Controls timeout behavior during automatic spaCy model downloads
SPACY_DOWNLOAD_TIMEOUT_SEC = 600   # Overall timeout: 10 minutes
SPACY_SOCKET_TIMEOUT_SEC = 10      # Socket timeout per request
SPACY_THREAD_TIMEOUT_SEC = 15      # Thread termination timeout

# Document Chunking (Session 20 - hierarchical summarization)
# Overlap fraction prevents context loss at chunk boundaries
CHUNK_OVERLAP_FRACTION = 0.1  # 10% overlap between chunks

# System Monitor Color Thresholds (CPU and RAM)
# Used for color-coded status indicators in the system monitor widget
# Applied independently to both CPU and RAM percentages
SYSTEM_MONITOR_THRESHOLD_GREEN = 75    # 0-74%: Green (healthy)
SYSTEM_MONITOR_THRESHOLD_YELLOW = 85   # 75-84%: Yellow (elevated)
SYSTEM_MONITOR_THRESHOLD_CRITICAL = 90 # 90%+: Red with "!" indicator

# Vocabulary Extraction Performance Settings
# Max text size in KB for spaCy NLP processing
# spaCy processes ~10-20K words/sec; 200KB ≈ 35K words ≈ 2-3 seconds
# Larger documents are truncated (still captures most named entities from early pages)
VOCABULARY_MAX_TEXT_KB = 200  # 200KB max for NLP processing (200,000 characters)

# spaCy batch processing - higher values process faster with more memory
# Testing shows: batch_size=4 (baseline), 8 (~17% faster), 16 (~25% faster but +100MB RAM)
# Default: 8 for optimal balance on 8-16GB systems
VOCABULARY_BATCH_SIZE = 8

# Parallel Processing Configuration
# Controls concurrent document extraction for multi-file workflows
#
# User Override Options:
# - USER_PICKS_MAX_WORKER_COUNT: If True, use USER_DEFINED_MAX_WORKER_COUNT
#   instead of auto-detection. Default: False (auto-detect based on CPU)
# - USER_DEFINED_MAX_WORKER_COUNT: Manual worker count when override enabled.
#   Range: 1-8. Default: 2 (conservative for most systems)
#
# Auto-detection (when USER_PICKS_MAX_WORKER_COUNT=False):
# - Uses min(cpu_count, 4) - caps at 4 for memory safety
# - Memory profile: Each document can use 200-500MB during processing
# - With 4 workers: ~2.1GB peak memory usage (safe for 8GB systems)

# User override settings (change these to customize)
USER_PICKS_MAX_WORKER_COUNT = False  # Set to True to use manual worker count
USER_DEFINED_MAX_WORKER_COUNT = 2    # Manual count when override enabled (1-8)

# Enforce bounds on user-defined count (1 minimum, 8 maximum)
_user_workers = max(1, min(8, USER_DEFINED_MAX_WORKER_COUNT))

# Compute actual max workers based on settings
if USER_PICKS_MAX_WORKER_COUNT:
    PARALLEL_MAX_WORKERS = _user_workers
else:
    # Auto-detect: min(cpu_count, 4) for memory safety
    PARALLEL_MAX_WORKERS = min(os.cpu_count() or 4, 4)

# AI Prompt Templates
PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"
USER_PROMPTS_DIR = APPDATA_DIR / "prompts"  # User-created prompts survive app updates

# Ensure user prompts directory exists
USER_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
LEGAL_KEYWORDS_FEDERAL = Path(__file__).parent.parent / "data" / "keywords" / "legal_keywords_federal.txt"

# License Configuration
LICENSE_FILE = CONFIG_DIR / "license.dat"
LICENSE_API_BASE_URL = "https://api.localscribe.example.com"  # Placeholder - will be updated
LICENSE_CACHE_HOURS = 24

# Logging Configuration
LOG_FILE = LOGS_DIR / "processing.log"
LOG_FORMAT = "[%(levelname)s %(asctime)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

# Debug Mode Default File (for streamlined testing)
DEBUG_DEFAULT_FILE = Path(__file__).parent.parent / "tests" / "sample_docs" / "test_complaint.pdf"

# ============================================================================
# Q&A / Vector Search Configuration (Session 24 - RAG-based Q&A)
# ============================================================================

# Vector Store Settings
# Stores FAISS indexes as files in user's AppData directory
VECTOR_STORE_DIR = APPDATA_DIR / "vector_stores"
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

# Q&A Retrieval Settings
QA_RETRIEVAL_K = 4              # Number of chunks to retrieve per question
QA_MAX_TOKENS = 300             # Maximum tokens for generated answer
QA_TEMPERATURE = 0.1            # Low temperature for factual, consistent answers
QA_SIMILARITY_THRESHOLD = 0.5   # Minimum relevance score for chunks

# Q&A Context Window
# Higher than summarization because we need question + context + answer
# Adjust based on model capability (most Ollama models support 4096)
QA_CONTEXT_WINDOW = 4096        # Tokens for RAG context

# Chat History Settings
QA_CONVERSATION_CONTEXT_PAIRS = 3  # Include last N Q&A pairs in follow-up questions
