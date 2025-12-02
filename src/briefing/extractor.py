"""
Chunk Extractor for Case Briefing Generator.

Extracts structured information from document chunks using Ollama's
structured output mode. This is the MAP phase of the Map-Reduce pattern.

Each chunk is processed independently to extract:
- Parties (plaintiffs, defendants)
- Allegations and claims
- Defenses (if present)
- Names mentioned with roles
- Key facts and dates
- Case type hints

The extracted data is later aggregated by the DataAggregator (REDUCE phase).
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.ai.ollama_model_manager import OllamaModelManager
from src.logging_config import debug_log

from .chunker import BriefingChunk


# JSON Schema for chunk extraction
EXTRACTION_SCHEMA = """{
  "parties": {
    "plaintiffs": ["John Smith"],
    "defendants": ["Dr. Wilson", "Memorial Hospital"]
  },
  "allegations": ["Defendant failed to diagnose condition", "Defendant was negligent in treatment"],
  "defenses": ["Standard of care was met", "Plaintiff's injuries were pre-existing"],
  "names_mentioned": [
    {"name": "Dr. James Wilson", "role": "defendant physician", "category": "PARTY"},
    {"name": "Dr. Sarah Chen", "role": "treating physician (not a party)", "category": "MEDICAL"},
    {"name": "John Smith", "role": "plaintiff/patient", "category": "PARTY"}
  ],
  "key_facts": ["Patient presented with chest pain on March 15", "Surgery performed on March 20"],
  "dates_mentioned": ["March 15, 2023", "March 20, 2023"],
  "case_type_hints": ["medical malpractice", "negligence"]
}"""


@dataclass
class ChunkExtraction:
    """
    Extracted data from a single document chunk.

    Represents the output of processing one chunk through the LLM.
    Multiple ChunkExtraction objects are later merged by the DataAggregator.

    Attributes:
        chunk_id: ID of the source chunk
        source_document: Original filename
        document_type: Type of legal document
        parties: Dict with plaintiffs and defendants lists
        allegations: List of allegation strings
        defenses: List of defense strings
        names_mentioned: List of name dicts with name, role, category
        key_facts: List of key fact strings
        dates_mentioned: List of date strings
        case_type_hints: List of case type indicator strings
        extraction_success: Whether extraction succeeded
        raw_response: Raw JSON response for debugging
    """

    chunk_id: int
    source_document: str
    document_type: str
    parties: dict = field(default_factory=lambda: {"plaintiffs": [], "defendants": []})
    allegations: list[str] = field(default_factory=list)
    defenses: list[str] = field(default_factory=list)
    names_mentioned: list[dict] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    dates_mentioned: list[str] = field(default_factory=list)
    case_type_hints: list[str] = field(default_factory=list)
    extraction_success: bool = True
    raw_response: dict | None = None


class ChunkExtractor:
    """
    Extracts structured information from document chunks via Ollama.

    Uses the generate_structured() method with JSON format mode for
    reliable extraction. Each chunk is processed with a consistent
    prompt template that includes the expected JSON schema.

    Example:
        extractor = ChunkExtractor()
        extraction = extractor.extract(chunk)
        print(extraction.parties)
    """

    # Prompt template for chunk extraction
    EXTRACTION_PROMPT = """Extract information from this legal document chunk.
Return ONLY valid JSON matching the schema below.
Do not include any commentary, explanation, or text outside the JSON.

IMPORTANT - IDENTIFYING PARTIES:
- PLAINTIFFS are the people/entities who FILED the lawsuit (the accusing party, the injured party)
- DEFENDANTS are the people/entities BEING SUED (the accused party)
- Look for labels like "Plaintiff" or "Defendant" after names
- In case captions, format is usually: "PLAINTIFF NAME, Plaintiff, v. DEFENDANT NAME, Defendant"
- In medical malpractice: the patient or injured person is typically the PLAINTIFF; doctors/hospitals being sued are DEFENDANTS
- In personal injury: the injured person is the PLAINTIFF; the party who caused injury is the DEFENDANT

EXTRACTION RULES:
- If a field has no relevant information in the chunk, use an empty list []
- For names_mentioned category:
  - "PARTY" for plaintiffs/defendants (parties to the lawsuit)
  - "MEDICAL" for doctors/nurses/medical staff who are NOT defendants
  - "WITNESS" for witnesses mentioned
  - "OTHER" for other individuals

EXPECTED JSON SCHEMA:
{schema}

DOCUMENT TYPE: {doc_type}
DOCUMENT: {source}

DOCUMENT CHUNK:
{chunk_text}

JSON OUTPUT:"""

    def __init__(
        self,
        ollama_manager: OllamaModelManager | None = None,
        max_tokens: int = 1000,
    ):
        """
        Initialize the chunk extractor.

        Args:
            ollama_manager: OllamaModelManager instance (creates new if None)
            max_tokens: Maximum tokens for extraction response
        """
        self.ollama_manager = ollama_manager or OllamaModelManager()
        self.max_tokens = max_tokens

        debug_log(f"[ChunkExtractor] Initialized with max_tokens={max_tokens}")

    def extract(self, chunk: BriefingChunk) -> ChunkExtraction:
        """
        Extract structured data from a single chunk.

        Args:
            chunk: BriefingChunk to process

        Returns:
            ChunkExtraction with extracted data
        """
        debug_log(f"[ChunkExtractor] Processing chunk {chunk.chunk_id} from {chunk.source_document}")

        # Build the prompt
        prompt = self.EXTRACTION_PROMPT.format(
            schema=EXTRACTION_SCHEMA,
            doc_type=chunk.document_type,
            source=chunk.source_document,
            chunk_text=chunk.text,
        )

        # Call Ollama structured output
        try:
            response = self.ollama_manager.generate_structured(
                prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=0.0,  # Deterministic for extraction
            )

            if response is None:
                debug_log(f"[ChunkExtractor] No response for chunk {chunk.chunk_id}")
                return self._empty_extraction(chunk, success=False)

            # Parse the response into ChunkExtraction
            extraction = self._parse_response(chunk, response)
            debug_log(f"[ChunkExtractor] Chunk {chunk.chunk_id}: extracted {self._count_items(extraction)} items")

            return extraction

        except Exception as e:
            debug_log(f"[ChunkExtractor] Error processing chunk {chunk.chunk_id}: {e}")
            return self._empty_extraction(chunk, success=False)

    def extract_batch(
        self,
        chunks: list[BriefingChunk],
        progress_callback: Callable[[int, int], None] | None = None,
        parallel: bool = True,
        max_workers: int = 2,
    ) -> list[ChunkExtraction]:
        """
        Extract structured data from multiple chunks.

        Supports parallel processing for improved performance. Default is 2
        workers to balance speed vs Ollama resource usage.

        Args:
            chunks: List of BriefingChunk objects
            progress_callback: Optional callback(current, total) for progress
            parallel: Whether to use parallel processing (default True)
            max_workers: Max concurrent extractions (default 2)

        Returns:
            List of ChunkExtraction objects, ordered by chunk_id
        """
        if not chunks:
            return []

        total = len(chunks)

        # Use sequential processing if parallel is disabled or only one chunk
        if not parallel or total <= 1 or max_workers <= 1:
            return self._extract_sequential(chunks, progress_callback)

        return self._extract_parallel(chunks, progress_callback, max_workers)

    def _extract_sequential(
        self,
        chunks: list[BriefingChunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ChunkExtraction]:
        """
        Extract chunks sequentially (fallback mode).

        Args:
            chunks: Chunks to process
            progress_callback: Progress callback

        Returns:
            List of extractions in order
        """
        extractions = []
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i, total)

            extraction = self.extract(chunk)
            extractions.append(extraction)

        if progress_callback:
            progress_callback(total, total)

        debug_log(f"[ChunkExtractor] Sequential batch complete: {len(extractions)} chunks")
        return extractions

    def _extract_parallel(
        self,
        chunks: list[BriefingChunk],
        progress_callback: Callable[[int, int], None] | None = None,
        max_workers: int = 2,
    ) -> list[ChunkExtraction]:
        """
        Extract chunks in parallel using ThreadPoolExecutor.

        Results are returned in chunk_id order regardless of completion order.

        Args:
            chunks: Chunks to process
            progress_callback: Progress callback
            max_workers: Maximum concurrent workers

        Returns:
            List of extractions ordered by chunk_id
        """
        total = len(chunks)
        completed_count = 0
        count_lock = threading.Lock()

        # Dict to store results by chunk_id for ordering
        results: dict[int, ChunkExtraction] = {}

        debug_log(f"[ChunkExtractor] Starting parallel extraction: {total} chunks, {max_workers} workers")

        def extract_with_tracking(chunk: BriefingChunk) -> ChunkExtraction:
            """Extract a chunk and track progress."""
            nonlocal completed_count
            result = self.extract(chunk)

            with count_lock:
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total)

            return result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(extract_with_tracking, chunk): chunk
                for chunk in chunks
            }

            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    extraction = future.result()
                    results[chunk.chunk_id] = extraction
                except Exception as e:
                    debug_log(f"[ChunkExtractor] Parallel extraction error for chunk {chunk.chunk_id}: {e}")
                    results[chunk.chunk_id] = self._empty_extraction(chunk, success=False)

        # Sort by chunk_id to maintain order
        extractions = [results[cid] for cid in sorted(results.keys())]

        debug_log(f"[ChunkExtractor] Parallel batch complete: {len(extractions)} chunks processed")
        return extractions

    def _parse_response(
        self,
        chunk: BriefingChunk,
        response: dict[str, Any],
    ) -> ChunkExtraction:
        """
        Parse Ollama JSON response into ChunkExtraction dataclass.

        Handles missing fields gracefully by using defaults.

        Args:
            chunk: Source chunk for metadata
            response: Parsed JSON response from Ollama

        Returns:
            ChunkExtraction with parsed data
        """
        # Extract parties
        parties_data = response.get("parties", {})
        parties = {
            "plaintiffs": self._ensure_list(parties_data.get("plaintiffs", [])),
            "defendants": self._ensure_list(parties_data.get("defendants", [])),
        }

        # Extract names with normalization
        names_raw = response.get("names_mentioned", [])
        names_mentioned = []
        for name_entry in self._ensure_list(names_raw):
            if isinstance(name_entry, dict):
                names_mentioned.append({
                    "name": str(name_entry.get("name", "")),
                    "role": str(name_entry.get("role", "")),
                    "category": str(name_entry.get("category", "OTHER")).upper(),
                })
            elif isinstance(name_entry, str):
                # Handle simple string names
                names_mentioned.append({
                    "name": name_entry,
                    "role": "",
                    "category": "OTHER",
                })

        return ChunkExtraction(
            chunk_id=chunk.chunk_id,
            source_document=chunk.source_document,
            document_type=chunk.document_type,
            parties=parties,
            allegations=self._ensure_string_list(response.get("allegations", [])),
            defenses=self._ensure_string_list(response.get("defenses", [])),
            names_mentioned=names_mentioned,
            key_facts=self._ensure_string_list(response.get("key_facts", [])),
            dates_mentioned=self._ensure_string_list(response.get("dates_mentioned", [])),
            case_type_hints=self._ensure_string_list(response.get("case_type_hints", [])),
            extraction_success=True,
            raw_response=response,
        )

    def _empty_extraction(
        self,
        chunk: BriefingChunk,
        success: bool = False,
    ) -> ChunkExtraction:
        """
        Create an empty extraction for failed/skipped chunks.

        Args:
            chunk: Source chunk for metadata
            success: Whether this should be marked as successful

        Returns:
            ChunkExtraction with empty data
        """
        return ChunkExtraction(
            chunk_id=chunk.chunk_id,
            source_document=chunk.source_document,
            document_type=chunk.document_type,
            extraction_success=success,
        )

    def _ensure_list(self, value: Any) -> list:
        """Ensure value is a list."""
        if isinstance(value, list):
            return value
        if value is None:
            return []
        return [value]

    def _ensure_string_list(self, value: Any) -> list[str]:
        """Ensure value is a list of strings."""
        items = self._ensure_list(value)
        return [str(item) for item in items if item]

    def _count_items(self, extraction: ChunkExtraction) -> int:
        """Count total items extracted for logging."""
        count = 0
        count += len(extraction.parties.get("plaintiffs", []))
        count += len(extraction.parties.get("defendants", []))
        count += len(extraction.allegations)
        count += len(extraction.defenses)
        count += len(extraction.names_mentioned)
        count += len(extraction.key_facts)
        count += len(extraction.dates_mentioned)
        count += len(extraction.case_type_hints)
        return count
