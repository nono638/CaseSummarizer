"""
Intelligent Document Chunking Engine

This module implements intelligent text chunking for long documents using:
1. Paragraph-aware splitting (respects paragraph boundaries)
2. Section detection (uses regex patterns to identify document structure)
3. Adaptive batch sizing (respects min/max word counts)

The chunking process preserves context and document structure, making it
suitable for legal documents with clear sections.
"""

import re
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import yaml

from src.config import DEBUG_MODE

logger = logging.getLogger(__name__)


def debug(msg: str):
    """Log debug message if DEBUG_MODE is enabled (with timestamp)."""
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.debug(f"[DEBUG {timestamp}] {msg}")


def debug_timing(operation: str, elapsed_seconds: float):
    """Log operation timing information."""
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Format timing in human-readable units
        if elapsed_seconds < 1:
            time_str = f"{elapsed_seconds*1000:.0f} ms"
        elif elapsed_seconds < 60:
            time_str = f"{elapsed_seconds:.2f}s"
        else:
            time_str = f"{elapsed_seconds/60:.1f}m"
        logger.debug(f"[DEBUG {timestamp}] {operation} took {time_str}")


def info(msg: str):
    """Log info message."""
    logger.info(msg)


def error(msg: str):
    """Log error message."""
    logger.error(msg)


@dataclass
class Chunk:
    """Represents a single text chunk with metadata."""
    chunk_num: int
    text: str
    word_count: int
    section_name: Optional[str] = None

    def __post_init__(self):
        """Validate chunk data."""
        if self.word_count != len(self.text.split()):
            # Recalculate to ensure consistency
            self.word_count = len(self.text.split())


class ChunkingEngine:
    """
    Intelligent document chunking engine.

    Features:
    - Paragraph-aware splitting
    - Section detection via regex patterns
    - Adaptive batch sizing (min/max constraints)
    - Preserves document structure
    """

    def __init__(self, config_path: Path = None):
        """
        Initialize chunking engine.

        Args:
            config_path: Path to chunking_config.yaml. If None, uses default.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "chunking_config.yaml"

        self.config = self._load_config(config_path)
        self.patterns = self._load_patterns()
        self.compiled_patterns = self._compile_patterns()

    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            debug(f"Loaded chunking config from {config_path}")
            return config
        except Exception as e:
            error(f"Failed to load config from {config_path}: {e}")
            raise

    def _load_patterns(self) -> List[str]:
        """Load regex patterns from patterns file."""
        patterns_file = Path(__file__).parent.parent / self.config['chunking']['patterns_file']

        patterns = []
        try:
            with open(patterns_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        patterns.append(line)

            debug(f"Loaded {len(patterns)} chunking patterns from {patterns_file}")
            return patterns
        except Exception as e:
            error(f"Failed to load patterns from {patterns_file}: {e}")
            return []

    def _compile_patterns(self) -> List[re.Pattern]:
        """Compile all regex patterns."""
        compiled = []
        for pattern in self.patterns:
            try:
                compiled.append(re.compile(pattern, re.MULTILINE | re.IGNORECASE))
            except re.error as e:
                error(f"Invalid regex pattern '{pattern}': {e}")
        return compiled

    def _split_into_paragraphs(self, text: str) -> List[Tuple[str, int]]:
        """
        Split text into paragraphs while preserving word counts.

        Returns:
            List of (paragraph_text, word_count) tuples
        """
        # Split on double newlines (standard paragraph break)
        # Also handle single newlines followed by uppercase (common in PDFs)
        paragraphs_raw = re.split(r'\n\s*\n', text)

        paragraphs = []
        for para in paragraphs_raw:
            para = para.strip()
            if para:  # Skip empty paragraphs
                word_count = len(para.split())
                paragraphs.append((para, word_count))

        debug(f"Split text into {len(paragraphs)} paragraphs")
        return paragraphs

    def _detect_section(self, text: str) -> Optional[str]:
        """
        Detect section name from paragraph text using regex patterns.

        Returns:
            Section name if matched, None otherwise
        """
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                # Extract the matched text as section name (first 50 chars)
                matched_text = match.group(0)
                section_name = matched_text[:50] if len(matched_text) > 50 else matched_text
                return section_name
        return None

    def _build_chunks(self, paragraphs: List[Tuple[str, int]]) -> List[Chunk]:
        """
        Build chunks from paragraphs respecting size and boundary constraints.

        Args:
            paragraphs: List of (text, word_count) tuples

        Returns:
            List of Chunk objects
        """
        config_chunking = self.config['chunking']
        max_words = config_chunking['max_chunk_words']
        min_words = config_chunking['min_chunk_words']
        hard_limit = config_chunking['max_chunk_words_hard_limit']

        chunks = []
        current_chunk_text = []
        current_chunk_words = 0
        current_section = None
        chunk_num = 1

        for para_text, para_words in paragraphs:
            # Detect section if it's a new one
            detected_section = self._detect_section(para_text)

            # Check if we should start a new chunk
            should_start_new = False

            # Reason 1: Section boundary and we have content
            if detected_section and current_chunk_text:
                should_start_new = True
                reason = "section_boundary"

            # Reason 2: Size limit reached
            elif current_chunk_words + para_words > max_words and current_chunk_text:
                should_start_new = True
                reason = "size_limit"

            if should_start_new:
                # Save current chunk
                chunk_text = "\n\n".join(current_chunk_text)
                chunk = Chunk(
                    chunk_num=chunk_num,
                    text=chunk_text,
                    word_count=current_chunk_words,
                    section_name=current_section
                )
                chunks.append(chunk)
                debug(f"Created chunk {chunk_num}: {current_chunk_words} words, section='{current_section}'")

                # Start new chunk
                current_chunk_text = [para_text]
                current_chunk_words = para_words
                current_section = detected_section
                chunk_num += 1
            else:
                # Add to current chunk
                current_chunk_text.append(para_text)
                current_chunk_words += para_words

                # Update section if detected in this paragraph
                if detected_section:
                    current_section = detected_section

        # Don't forget the last chunk
        if current_chunk_text:
            chunk_text = "\n\n".join(current_chunk_text)
            chunk = Chunk(
                chunk_num=chunk_num,
                text=chunk_text,
                word_count=current_chunk_words,
                section_name=current_section
            )
            chunks.append(chunk)
            debug(f"Created chunk {chunk_num}: {current_chunk_words} words, section='{current_section}'")

        info(f"Created {len(chunks)} total chunks from document")
        return chunks

    def chunk_text(self, text: str) -> List[Chunk]:
        """
        Split document text into intelligent chunks.

        Args:
            text: Full document text

        Returns:
            List of Chunk objects with metadata
        """
        start_time = time.time()
        debug("Starting ChunkingEngine.chunk_text()...")

        # Validate input
        if not text or not text.strip():
            error("Empty text provided to chunking engine")
            return []

        original_words = len(text.split())
        debug(f"Input document: {original_words} words")

        # Step 1: Split into paragraphs
        step_start = time.time()
        debug("Step 1: Splitting text into paragraphs...")
        paragraphs = self._split_into_paragraphs(text)
        step_time = time.time() - step_start
        debug_timing("Paragraph splitting", step_time)

        if not paragraphs:
            error("No paragraphs extracted from text")
            return []

        debug(f"Extracted {len(paragraphs)} paragraphs")

        # Step 2: Build chunks
        step_start = time.time()
        debug("Step 2: Building chunks from paragraphs...")
        chunks = self._build_chunks(paragraphs)
        step_time = time.time() - step_start
        debug_timing("Chunk building", step_time)

        debug(f"Created {len(chunks)} chunks")

        # Step 3: Validate chunks
        total_words = sum(chunk.word_count for chunk in chunks)

        if total_words != original_words:
            # This can happen due to whitespace differences; log but don't fail
            debug(f"Word count mismatch: original={original_words}, chunked={total_words}")

        total_time = time.time() - start_time
        debug_timing("ChunkingEngine.chunk_text() complete", total_time)

        return chunks


def create_chunking_engine(config_path: Path = None) -> ChunkingEngine:
    """Factory function to create a ChunkingEngine instance."""
    return ChunkingEngine(config_path)
