"""
Text Utility Functions

Common text processing functions used across the application.
"""

from typing import Dict, List, Optional


def combine_document_texts(
    documents: List[Dict],
    include_headers: bool = False,
    separator: str = "\n\n"
) -> str:
    """
    Combine extracted text from multiple documents into a single string.

    Args:
        documents: List of document result dictionaries. Each dict should have
                  'extracted_text' key (and optionally 'filename' for headers).
        include_headers: If True, prefix each document's text with its filename
                        formatted as "--- filename ---"
        separator: String to use between documents (default: double newline)

    Returns:
        Combined text from all documents. Documents without 'extracted_text'
        or with empty text are skipped.

    Example:
        >>> docs = [
        ...     {'filename': 'a.pdf', 'extracted_text': 'Hello'},
        ...     {'filename': 'b.pdf', 'extracted_text': 'World'}
        ... ]
        >>> combine_document_texts(docs)
        'Hello\\n\\nWorld'
        >>> combine_document_texts(docs, include_headers=True)
        '--- a.pdf ---\\nHello\\n\\n--- b.pdf ---\\nWorld'
    """
    combined_parts = []

    for doc in documents:
        text = doc.get('extracted_text', '')
        if not text:
            continue

        if include_headers:
            filename = doc.get('filename', 'Unknown')
            combined_parts.append(f"--- {filename} ---\n{text}")
        else:
            combined_parts.append(text)

    return separator.join(combined_parts)
