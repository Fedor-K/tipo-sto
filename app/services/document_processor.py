# -*- coding: utf-8 -*-
"""
Document Processor - Extract text from PDF, DOCX, TXT, MD files
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
    """
    Extract text from a file based on its extension or content type.

    Args:
        file_path: Path to the file
        content_type: Optional MIME type hint

    Returns:
        Extracted text as string
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf" or (content_type and "pdf" in content_type):
        return _extract_pdf(path)
    elif suffix == ".docx" or (content_type and "wordprocessingml" in content_type):
        return _extract_docx(path)
    elif suffix in (".txt", ".md", ".markdown"):
        return _extract_text(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _is_garbled(text: str) -> bool:
    """Check if extracted text is garbled (encoding issues)."""
    if not text or len(text) < 50:
        return False
    sample = text[:500]
    # CID-mapped fonts produce (cid:NNN) sequences
    if '(cid:' in sample:
        return True
    cyrillic = sum(1 for c in sample if '\u0400' <= c <= '\u04FF')
    latin_diacritic = sum(1 for c in sample if '\u00C0' <= c <= '\u00FF')
    if latin_diacritic > len(sample) * 0.15 and cyrillic < latin_diacritic:
        return True
    return False


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF. Tries PyMuPDF first (best Cyrillic support),
    falls back to pypdf, then pdfminer."""
    # Try PyMuPDF first (best handling of non-standard font encodings)
    try:
        text = _extract_pdf_pymupdf(path)
        if text and not _is_garbled(text):
            logger.info(f"PyMuPDF successfully extracted text from {path.name}")
            return text
        logger.warning(f"PyMuPDF produced garbled text for {path.name}, trying pypdf")
    except Exception as e:
        logger.warning(f"PyMuPDF failed for {path.name}: {e}, trying pypdf")

    # Try pypdf
    text = _extract_pdf_pypdf(path)
    if not _is_garbled(text):
        logger.info(f"pypdf successfully extracted text from {path.name}")
        return text

    # Try pdfplumber (built on pdfminer with better Unicode normalization)
    logger.warning(f"pypdf produced garbled text for {path.name}, trying pdfplumber")
    try:
        text_plumber = _extract_pdf_pdfplumber(path)
        if text_plumber and not _is_garbled(text_plumber):
            logger.info(f"pdfplumber successfully extracted text from {path.name}")
            return text_plumber
    except Exception as e:
        logger.warning(f"pdfplumber failed for {path.name}: {e}")

    # Try pdfminer as last resort
    logger.warning(f"Trying pdfminer for {path.name}")
    try:
        text_pdfminer = _extract_pdf_pdfminer(path)
        if text_pdfminer and not _is_garbled(text_pdfminer):
            logger.info(f"pdfminer successfully extracted text from {path.name}")
            return text_pdfminer
    except Exception as e:
        logger.warning(f"pdfminer failed for {path.name}: {e}")

    logger.warning(f"All parsers produced garbled text for {path.name}, using best available")
    return text


def _detect_printed_page_number(text: str) -> Optional[int]:
    """Try to detect the printed page number from page text.

    Books typically have the page number as the first or last standalone
    number on the page.
    """
    import re
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if not lines:
        return None
    # Check last line first (most common for books), then first line
    for line in [lines[-1], lines[0]]:
        # Page number is a standalone number (1-999), possibly with some whitespace
        m = re.fullmatch(r'(\d{1,3})', line)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 999:
                return num
    return None


def _extract_pdf_pymupdf(path: Path) -> str:
    """Extract text from PDF using PyMuPDF (fitz). Best Cyrillic font support.

    Tries to detect printed page numbers from the text to use instead of
    PDF page indices, which may differ due to front matter.
    """
    import fitz

    doc = fitz.open(str(path))

    # First pass: detect page offset by comparing PDF index with printed numbers
    offset = None
    for i, page in enumerate(doc):
        text = page.get_text()
        if text:
            printed = _detect_printed_page_number(text)
            if printed and printed >= 1 and i >= 2:
                # Found a printed page number — calculate offset
                candidate_offset = (i + 1) - printed
                if 0 <= candidate_offset <= 20:  # reasonable offset
                    offset = candidate_offset
                    logger.info(f"Detected page offset: {offset} (PDF page {i+1} has printed number {printed})")
                    break

    parts = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if text and text.strip():
            if offset is not None:
                page_num = (i + 1) - offset
                if page_num < 1:
                    page_num = i + 1  # fallback for front matter
            else:
                page_num = i + 1
            parts.append(f"[PAGE:{page_num}]\n{text.strip()}")
    doc.close()
    return "\n\n".join(parts)


def _extract_pdf_pypdf(path: Path) -> str:
    """Extract text from PDF using pypdf. Inserts [PAGE:N] markers between pages."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))

    # Detect page offset
    offset = None
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            printed = _detect_printed_page_number(text)
            if printed and printed >= 1 and i >= 2:
                candidate_offset = (i + 1) - printed
                if 0 <= candidate_offset <= 20:
                    offset = candidate_offset
                    break

    parts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            if offset is not None:
                page_num = (i + 1) - offset
                if page_num < 1:
                    page_num = i + 1
            else:
                page_num = i + 1
            parts.append(f"[PAGE:{page_num}]\n{text}")
    return "\n\n".join(parts)


def _extract_pdf_pdfplumber(path: Path) -> str:
    """Extract text from PDF using pdfplumber (built on pdfminer, better Unicode)."""
    import pdfplumber

    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                parts.append(f"[PAGE:{i + 1}]\n{text.strip()}")
    return "\n\n".join(parts)


def _extract_pdf_pdfminer(path: Path) -> str:
    """Extract text from PDF using pdfminer.six (better encoding support)."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTTextContainer

    laparams = LAParams()
    parts = []
    for i, page_layout in enumerate(extract_pages(str(path), laparams=laparams)):
        page_text = ""
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                page_text += element.get_text()
        if page_text.strip():
            parts.append(f"[PAGE:{i + 1}]\n{page_text.strip()}")
    return "\n\n".join(parts)


def _extract_docx(path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    from docx import Document

    doc = Document(str(path))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_text(path: Path) -> str:
    """Read plain text / markdown file."""
    return path.read_text(encoding="utf-8")


def clean_text(text: str) -> str:
    """Clean extracted text: normalize whitespace, remove control chars."""
    import re

    # Remove control characters except newlines and tabs
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Normalize multiple blank lines to two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()
