"""
Document Chunker for Case Briefing Generator.

Provides section-aware document splitting optimized for legal documents.
Chunks are sized to fit within Ollama's context window while preserving
semantic boundaries (paragraphs, legal sections).

Key Features:
- Legal section detection (CAUSES OF ACTION, WHEREFORE, etc.)
- Document source tracking (which file each chunk came from)
- Configurable chunk size targeting ~1500-2000 characters
- Paragraph-aware splitting to avoid mid-sentence breaks
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from src.logging_config import debug_log


@dataclass
class BriefingChunk:
    """
    A chunk of document text with metadata for briefing extraction.

    Attributes:
        chunk_id: Unique identifier for this chunk
        text: The chunk text content
        char_count: Number of characters in the chunk
        source_document: Original filename this chunk came from
        document_type: Detected document type (complaint, answer, transcript, etc.)
        section_hint: Detected legal section name if any
        chunk_index: Position of this chunk within its source document
        document_date: Date associated with the document (for transcript weighting)
    """

    chunk_id: int
    text: str
    char_count: int
    source_document: str
    document_type: str = "unknown"
    section_hint: str | None = None
    chunk_index: int = 0
    document_date: datetime | None = None

    def __post_init__(self):
        """Ensure char_count is accurate."""
        if self.char_count != len(self.text):
            self.char_count = len(self.text)


class DocumentChunker:
    """
    Section-aware document chunker for legal documents.

    Splits documents into chunks suitable for LLM extraction while:
    - Respecting paragraph boundaries
    - Detecting legal section headers
    - Tracking document source metadata
    - Targeting chunk sizes that fit context windows

    Example:
        chunker = DocumentChunker(target_chars=1800)
        chunks = chunker.chunk_documents([
            {"filename": "complaint.pdf", "text": "...", "doc_type": "complaint"},
            {"filename": "answer.pdf", "text": "...", "doc_type": "answer"},
        ])
    """

    # Legal section patterns (compiled for performance)
    SECTION_PATTERNS = [
        # Complaint sections
        (re.compile(r"^\s*(FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+CAUSE\s+OF\s+ACTION", re.IGNORECASE | re.MULTILINE), "cause_of_action"),
        (re.compile(r"^\s*COUNT\s+[IVX\d]+", re.IGNORECASE | re.MULTILINE), "count"),
        (re.compile(r"^\s*WHEREFORE", re.IGNORECASE | re.MULTILINE), "wherefore"),
        (re.compile(r"^\s*PRAYER\s+FOR\s+RELIEF", re.IGNORECASE | re.MULTILINE), "prayer"),
        (re.compile(r"^\s*STATEMENT\s+OF\s+FACTS", re.IGNORECASE | re.MULTILINE), "facts"),
        (re.compile(r"^\s*NATURE\s+OF\s+(THE\s+)?ACTION", re.IGNORECASE | re.MULTILINE), "nature"),
        (re.compile(r"^\s*PARTIES", re.IGNORECASE | re.MULTILINE), "parties"),
        (re.compile(r"^\s*JURISDICTION", re.IGNORECASE | re.MULTILINE), "jurisdiction"),

        # Answer sections
        (re.compile(r"^\s*AFFIRMATIVE\s+DEFENSES?", re.IGNORECASE | re.MULTILINE), "affirmative_defenses"),
        (re.compile(r"^\s*(FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+AFFIRMATIVE\s+DEFENSE", re.IGNORECASE | re.MULTILINE), "affirmative_defense"),
        (re.compile(r"^\s*ANSWER", re.IGNORECASE | re.MULTILINE), "answer"),
        (re.compile(r"^\s*DENIALS?", re.IGNORECASE | re.MULTILINE), "denials"),

        # Transcript sections
        (re.compile(r"^\s*DIRECT\s+EXAMINATION", re.IGNORECASE | re.MULTILINE), "direct_examination"),
        (re.compile(r"^\s*CROSS[- ]?EXAMINATION", re.IGNORECASE | re.MULTILINE), "cross_examination"),
        (re.compile(r"^\s*REDIRECT\s+EXAMINATION", re.IGNORECASE | re.MULTILINE), "redirect_examination"),
        (re.compile(r"^\s*(THE\s+)?WITNESS:", re.IGNORECASE | re.MULTILINE), "witness_statement"),
        (re.compile(r"^\s*BY\s+(MR\.|MS\.|MRS\.)\s+\w+:", re.IGNORECASE | re.MULTILINE), "attorney_question"),

        # General sections
        (re.compile(r"^\s*INTRODUCTION", re.IGNORECASE | re.MULTILINE), "introduction"),
        (re.compile(r"^\s*BACKGROUND", re.IGNORECASE | re.MULTILINE), "background"),
        (re.compile(r"^\s*ALLEGATIONS?", re.IGNORECASE | re.MULTILINE), "allegations"),
    ]

    # Document type detection patterns
    DOC_TYPE_PATTERNS = [
        (re.compile(r"COMPLAINT|PETITION|SUMMONS", re.IGNORECASE), "complaint"),
        (re.compile(r"ANSWER\s+(TO|AND)|DEFENDANT.{0,20}ANSWER", re.IGNORECASE), "answer"),
        (re.compile(r"DEPOSITION|TRANSCRIPT|EXAMINATION", re.IGNORECASE), "transcript"),
        (re.compile(r"BILL\s+OF\s+PARTICULARS", re.IGNORECASE), "bill_of_particulars"),
        (re.compile(r"MOTION|ORDER|RULING", re.IGNORECASE), "motion"),
    ]

    def __init__(
        self,
        target_chars: int = 1800,
        max_chars: int = 2500,
        min_chars: int = 500,
    ):
        """
        Initialize the document chunker.

        Args:
            target_chars: Target chunk size in characters (~1800 for 2048 token window)
            max_chars: Maximum chunk size (hard limit)
            min_chars: Minimum chunk size (avoids tiny chunks)
        """
        self.target_chars = target_chars
        self.max_chars = max_chars
        self.min_chars = min_chars

        debug_log(f"[DocumentChunker] Initialized: target={target_chars}, max={max_chars}, min={min_chars}")

    def chunk_documents(
        self,
        documents: list[dict],
    ) -> list[BriefingChunk]:
        """
        Chunk multiple documents into BriefingChunk objects.

        Args:
            documents: List of dicts with keys:
                - filename: Original filename
                - text: Document text content
                - doc_type: (optional) Pre-classified document type
                - date: (optional) Document date for transcript weighting

        Returns:
            List of BriefingChunk objects with metadata
        """
        all_chunks = []
        chunk_id = 0

        for doc in documents:
            filename = doc.get("filename", "unknown")
            text = doc.get("text", "")
            doc_type = doc.get("doc_type") or self._detect_document_type(text, filename)
            doc_date = doc.get("date")

            if not text.strip():
                debug_log(f"[DocumentChunker] Skipping empty document: {filename}")
                continue

            # Chunk this document
            doc_chunks = self._chunk_single_document(
                text=text,
                source_document=filename,
                document_type=doc_type,
                document_date=doc_date,
                start_chunk_id=chunk_id,
            )

            all_chunks.extend(doc_chunks)
            chunk_id += len(doc_chunks)

            debug_log(f"[DocumentChunker] {filename}: {len(doc_chunks)} chunks, type={doc_type}")

        debug_log(f"[DocumentChunker] Total: {len(all_chunks)} chunks from {len(documents)} documents")
        return all_chunks

    def _detect_document_type(self, text: str, filename: str) -> str:
        """
        Detect document type from content and filename.

        Args:
            text: Document text
            filename: Original filename

        Returns:
            Detected document type string
        """
        # Check filename first
        filename_lower = filename.lower()
        if "complaint" in filename_lower:
            return "complaint"
        if "answer" in filename_lower:
            return "answer"
        if "transcript" in filename_lower or "depo" in filename_lower:
            return "transcript"
        if "bill" in filename_lower and "particulars" in filename_lower:
            return "bill_of_particulars"

        # Check content patterns
        first_5000 = text[:5000]
        for pattern, doc_type in self.DOC_TYPE_PATTERNS:
            if pattern.search(first_5000):
                return doc_type

        return "unknown"

    def _chunk_single_document(
        self,
        text: str,
        source_document: str,
        document_type: str,
        document_date: datetime | None,
        start_chunk_id: int,
    ) -> list[BriefingChunk]:
        """
        Chunk a single document respecting paragraph and section boundaries.

        Args:
            text: Document text
            source_document: Original filename
            document_type: Type of legal document
            document_date: Date for transcript weighting
            start_chunk_id: Starting chunk ID number

        Returns:
            List of BriefingChunk objects
        """
        # Split into paragraphs
        paragraphs = self._split_into_paragraphs(text)

        if not paragraphs:
            return []

        chunks = []
        current_text_parts = []
        current_chars = 0
        current_section = None
        chunk_index = 0

        for para in paragraphs:
            para_chars = len(para)

            # Detect section header in this paragraph
            detected_section = self._detect_section(para)
            if detected_section:
                current_section = detected_section

            # Check if adding this paragraph would exceed max
            would_exceed_max = (current_chars + para_chars) > self.max_chars

            # Check if we should start a new chunk
            should_split = False

            # Split if exceeding max and we have content
            if would_exceed_max and current_text_parts:
                should_split = True
            # Split if we're at target and this paragraph would push us well over
            elif current_chars >= self.target_chars and para_chars > 200:
                should_split = True
            # Split at major section boundaries if we have reasonable content
            elif detected_section and current_chars >= self.min_chars:
                should_split = True

            if should_split:
                # Save current chunk
                chunk_text = "\n\n".join(current_text_parts)
                chunk = BriefingChunk(
                    chunk_id=start_chunk_id + len(chunks),
                    text=chunk_text,
                    char_count=len(chunk_text),
                    source_document=source_document,
                    document_type=document_type,
                    section_hint=current_section,
                    chunk_index=chunk_index,
                    document_date=document_date,
                )
                chunks.append(chunk)
                chunk_index += 1

                # Start new chunk with this paragraph
                current_text_parts = [para]
                current_chars = para_chars
                if detected_section:
                    current_section = detected_section
            else:
                # Add to current chunk
                current_text_parts.append(para)
                current_chars += para_chars

        # Don't forget the last chunk
        if current_text_parts:
            chunk_text = "\n\n".join(current_text_parts)
            chunk = BriefingChunk(
                chunk_id=start_chunk_id + len(chunks),
                text=chunk_text,
                char_count=len(chunk_text),
                source_document=source_document,
                document_type=document_type,
                section_hint=current_section,
                chunk_index=chunk_index,
                document_date=document_date,
            )
            chunks.append(chunk)

        return chunks

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """
        Split text into paragraphs.

        Handles various paragraph break patterns:
        - Double newlines
        - Single newlines followed by uppercase (common in legal docs)
        - Page breaks

        Args:
            text: Document text

        Returns:
            List of paragraph strings
        """
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Split on double newlines (standard paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', text)

        # Filter empty paragraphs and strip whitespace
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        return paragraphs

    def _detect_section(self, text: str) -> str | None:
        """
        Detect if text contains a legal section header.

        Args:
            text: Paragraph text

        Returns:
            Section type identifier or None
        """
        # Only check first 200 chars for section headers
        check_text = text[:200]

        for pattern, section_type in self.SECTION_PATTERNS:
            if pattern.search(check_text):
                return section_type

        return None

    def get_chunks_by_document(
        self,
        chunks: list[BriefingChunk],
    ) -> dict[str, list[BriefingChunk]]:
        """
        Group chunks by source document.

        Args:
            chunks: List of BriefingChunk objects

        Returns:
            Dict mapping filename to list of chunks from that file
        """
        by_doc = {}
        for chunk in chunks:
            if chunk.source_document not in by_doc:
                by_doc[chunk.source_document] = []
            by_doc[chunk.source_document].append(chunk)
        return by_doc

    def get_chunks_by_type(
        self,
        chunks: list[BriefingChunk],
    ) -> dict[str, list[BriefingChunk]]:
        """
        Group chunks by document type.

        Args:
            chunks: List of BriefingChunk objects

        Returns:
            Dict mapping document type to list of chunks of that type
        """
        by_type = {}
        for chunk in chunks:
            if chunk.document_type not in by_type:
                by_type[chunk.document_type] = []
            by_type[chunk.document_type].append(chunk)
        return by_type
