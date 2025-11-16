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
# Standard: Phi-3 Mini 3.8B (CPU-optimized, fast, good quality)
# Pro: Gemma 2 9B (Requires GPU for reasonable performance)
STANDARD_MODEL_NAME = "Phi-3-mini-4k-instruct-q4.gguf"
PRO_MODEL_NAME = "gemma-2-9b-it-q4_k_m.gguf"
MAX_CONTEXT_TOKENS = 4096  # Phi-3 Mini context window
SAFE_PROCESSING_TOKENS = 3000  # Conservative for CPU performance

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
