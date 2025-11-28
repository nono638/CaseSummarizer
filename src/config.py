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

# Ensure directories exist
for directory in [APPDATA_DIR, MODELS_DIR, CACHE_DIR, LOGS_DIR, CONFIG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

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

# --- New Model Configuration System ---
MODEL_CONFIG_FILE = Path(__file__).parent.parent / "config" / "models.yaml"
MODEL_CONFIGS = {}

def load_model_configs():
    """Loads model configurations from config/models.yaml."""
    global MODEL_CONFIGS
    try:
        with open(MODEL_CONFIG_FILE, 'r') as f:
            data = yaml.safe_load(f)
            MODEL_CONFIGS = data.get('models', {})
        if DEBUG_MODE and MODEL_CONFIGS:
            print(f"[Config] Loaded {len(MODEL_CONFIGS)} model configurations from {MODEL_CONFIG_FILE}")
    except FileNotFoundError:
        if DEBUG_MODE:
            print(f"[Config] WARNING: Model config file not found at {MODEL_CONFIG_FILE}. Using fallback values.")
        MODEL_CONFIGS = {}
    except Exception as e:
        print(f"[Config] ERROR: Failed to load or parse model config file: {e}")
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
                print(f"[Config] Found partial match for '{model_name}': using config for '{name}'.")
            return config

    # 3. Fallback to the default model name if no match found
    if OLLAMA_MODEL_NAME in MODEL_CONFIGS:
        if DEBUG_MODE:
            print(f"[Config] WARNING: Model '{model_name}' not found. Falling back to default model '{OLLAMA_MODEL_NAME}'.")
        return MODEL_CONFIGS[OLLAMA_MODEL_NAME]

    # 4. Absolute fallback if config is empty or default is missing
    if DEBUG_MODE:
        print("[Config] WARNING: No model configurations found. Using hard-coded fallback values.")
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
# Words with rank >= 150,000 are considered rare (bottom 55% of 333K word vocabulary)
# This threshold filters common medical/legal words while preserving technical terms
# Examples: "medical" (rank 501) FILTERED, "adenocarcinoma" (rank >150K) EXTRACTED
# Set to -1 to disable frequency-based filtering (use WordNet only)
VOCABULARY_RARITY_THRESHOLD = 150000
# When enabled, sort CSV results by rarity (words not in dataset first, then lowest frequency count)
VOCABULARY_SORT_BY_RARITY = True

# GUI Display Limits for Vocabulary Table
# Based on tkinter Treeview performance testing:
# - < 100 rows: Excellent performance
# - 100-200 rows: Generally acceptable
# - 200+ rows: Performance degrades, especially with text wrapping
# Default: 50 rows (conservative for responsiveness)
# Maximum ceiling: 200 rows (hard limit to prevent GUI freezing)
VOCABULARY_DISPLAY_LIMIT = 50   # User-configurable default (conservative)
VOCABULARY_DISPLAY_MAX = 200    # Hard ceiling - cannot exceed this

# Vocabulary Extraction Performance Settings
# Max text size in KB for spaCy NLP processing
# spaCy processes ~10-20K words/sec; 200KB ≈ 35K words ≈ 2-3 seconds
# Larger documents are truncated (still captures most named entities from early pages)
VOCABULARY_MAX_TEXT_KB = 200  # 200KB max for NLP processing (200,000 characters)

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
