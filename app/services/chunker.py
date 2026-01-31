# -*- coding: utf-8 -*-
"""
Text Chunker - Split text into token-sized chunks with overlap using tiktoken.
"""
import logging
import re
from typing import Dict, List, Tuple

import tiktoken

logger = logging.getLogger(__name__)

# Reuse encoder across calls
_encoder = tiktoken.get_encoding("cl100k_base")


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> List[str]:
    """
    Split text into chunks of approximately `chunk_size` tokens
    with `chunk_overlap` token overlap between consecutive chunks.

    Args:
        text: Source text to split
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Number of overlapping tokens between chunks

    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []

    tokens = _encoder.encode(text)

    if len(tokens) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    step = chunk_size - chunk_overlap

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = _encoder.decode(chunk_tokens)
        chunks.append(chunk_text_str)

        if end >= len(tokens):
            break
        start += step

    logger.debug(f"Split {len(tokens)} tokens into {len(chunks)} chunks")
    return chunks


def count_tokens(text: str) -> int:
    """Count tokens in text using cl100k_base encoding."""
    return len(_encoder.encode(text))


def extract_pages_from_chunk(chunk_text: str) -> str:
    """
    Extract page numbers from [PAGE:N] markers in a chunk.
    Returns a string like "191" or "191-192".
    """
    pages = [int(m) for m in re.findall(r"\[PAGE:(\d+)\]", chunk_text)]
    if not pages:
        return ""
    if len(pages) == 1 or pages[0] == pages[-1]:
        return str(pages[0])
    return f"{pages[0]}-{pages[-1]}"
