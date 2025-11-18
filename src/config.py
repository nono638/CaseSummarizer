"""
LocalScribe Configuration Module
Centralized configuration for the application.
"""

import os
from pathlib import Path

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
# Using Ollama for commercial viability and stability
# Qwen2.5:7b-instruct: Optimized for legal document summarization with excellent instruction-following
# and structured output capabilities. Requires 16GB+ RAM, ~4.7GB disk space (Q4_K_M quantization)
# Ollama models available at https://ollama.ai/library
OLLAMA_API_BASE = "http://localhost:11434"  # Default Ollama API endpoint
OLLAMA_MODEL_NAME = "gemma3:1b"  # TEST MODEL: Gemma 3 1B (small, fast, already downloaded on system)
OLLAMA_MODEL_FALLBACK = "gemma3:1b"  # Fallback: Same model for testing
# NOTE: For production, use qwen2.5:7b-instruct (excellent for legal docs) or llama3.2:3b-instruct (faster fallback)
OLLAMA_TIMEOUT_SECONDS = 600  # 10 minutes for long summaries
MAX_CONTEXT_TOKENS = 4096  # Safe for most Ollama models
SAFE_PROCESSING_TOKENS = 3000  # Conservative for performance

# Legacy model constants (for backwards compatibility with llama-cpp-python)
# These are no longer used but kept to avoid breaking imports in legacy code
STANDARD_MODEL_NAME = "Phi-3-mini-4k-instruct-q4.gguf"  # DEPRECATED
PRO_MODEL_NAME = "gemma-2-9b-it-q4_k_m.gguf"  # DEPRECATED

# Default Processing Settings
DEFAULT_SUMMARY_WORDS = 200
MIN_SUMMARY_WORDS = 100
MAX_SUMMARY_WORDS = 500

# Data Files
GOOGLE_FREQ_LIST = Path(__file__).parent.parent / "data" / "frequency" / "google_word_freq.txt"
LEGAL_KEYWORDS_NY = Path(__file__).parent.parent / "data" / "keywords" / "legal_keywords_ny.txt"
LEGAL_KEYWORDS_CA = Path(__file__).parent.parent / "data" / "keywords" / "legal_keywords_ca.txt"

# AI Prompt Templates
PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"
SUMMARY_PROMPT_TEMPLATE = Path(__file__).parent.parent / "config" / "summary_prompt_template.txt"  # Legacy, deprecated
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
