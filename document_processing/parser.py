"""PDF text extraction for the FinAssist AI document-processing pipeline.

This module is intentionally limited to getting raw text out of a PDF reliably.
Structured field extraction and Pydantic validation happen downstream in
document_processing/extractor.py and document_processing/schemas.py.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    success: bool
    text: str
    page_count: int
    error: str | None = None


def extract_text(source: str | Path | bytes) -> ParsedDocument:
    """Extract concatenated text from a PDF.

    `source` may be a file path (str/Path) or raw PDF bytes (e.g. from a
    Streamlit file uploader). Never raises -- PDF errors are caught and
    reported via ParsedDocument.success / .error so callers can show a
    friendly message instead of a stack trace.
    """
    try:
        if isinstance(source, (str, Path)):
            doc = fitz.open(str(source))
        else:
            doc = fitz.open(stream=source, filetype="pdf")
    except Exception as exc:
        logger.warning("Failed to open PDF %r: %s", source, exc)
        return ParsedDocument(success=False, text="", page_count=0, error=str(exc))

    try:
        if doc.page_count == 0:
            return ParsedDocument(success=False, text="", page_count=0, error="PDF has no pages")

        pages_text = [page.get_text() for page in doc]
        text = "\n".join(pages_text).strip()

        if not text:
            return ParsedDocument(
                success=False,
                text="",
                page_count=doc.page_count,
                error="No extractable text found (possibly a scanned/image-only PDF)",
            )

        return ParsedDocument(success=True, text=text, page_count=doc.page_count)
    except Exception as exc:
        logger.warning("Failed to read pages from PDF %r: %s", source, exc)
        return ParsedDocument(success=False, text="", page_count=0, error=str(exc))
    finally:
        doc.close()
