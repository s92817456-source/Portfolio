"""
pdf_reader.py  —  Section-aware PDF text extraction
Uses pdfplumber with layout-preserving extraction.
Supports both file paths and Streamlit UploadedFile objects.
"""

from __future__ import annotations
import io
import re
from typing import IO

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def extract_text(pdf_file: str | IO[bytes]) -> str:
    """
    Extract all text from a PDF, preserving layout as much as possible.
    Accepts:
      - str path to a PDF file
      - file-like object (Streamlit UploadedFile, BytesIO, etc.)
    """
    if not PDF_AVAILABLE:
        raise ImportError("pdfplumber is required: pip install pdfplumber")

    text_parts: list[str] = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # Use layout-preserving extraction
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if page_text:
                text_parts.append(page_text)

    raw = "\n".join(text_parts)
    return _clean_text(raw)


def _clean_text(text: str) -> str:
    """Normalise whitespace and remove junk characters while preserving structure."""
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove non-printable characters
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    # Normalise multiple spaces (but not newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_sections(pdf_file: str | IO[bytes]) -> dict[str, str]:
    """
    Extract text and attempt to split into resume sections.
    Returns dict with keys: raw, skills, experience, projects, education, summary.
    """
    raw = extract_text(pdf_file)
    sections: dict[str, str] = {"raw": raw}

    section_headers = {
        "summary": r"(?i)(summary|objective|profile|about me)",
        "skills": r"(?i)(skills|competencies|technologies|technical)",
        "experience": r"(?i)(experience|employment|work history|career)",
        "projects": r"(?i)(projects|portfolio|notable work)",
        "education": r"(?i)(education|academic|qualifications|degrees?)",
    }

    lines = raw.split("\n")
    current_section: str | None = None
    section_content: dict[str, list[str]] = {k: [] for k in section_headers}

    for line in lines:
        matched = False
        for section, pattern in section_headers.items():
            if re.match(pattern, line.strip()):
                current_section = section
                matched = True
                break
        if not matched and current_section:
            section_content[current_section].append(line)

    for section, content_lines in section_content.items():
        sections[section] = "\n".join(content_lines).strip()

    return sections
