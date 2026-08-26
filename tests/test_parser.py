"""Tests for document_processing/parser.py."""

from document_processing.parser import extract_text
from tests.conftest import DOCUMENTS_DIR


def test_extract_text_from_valid_pdf():
    result = extract_text(DOCUMENTS_DIR / "C1002_bank_statement_july2026.pdf")

    assert result.success
    assert result.page_count == 1
    assert "C1002" in result.text
    assert "25,000.00" in result.text


def test_extract_text_from_corrupted_pdf_fails_gracefully():
    result = extract_text(DOCUMENTS_DIR / "invalid_corrupted.pdf")

    assert not result.success
    assert result.text == ""
    assert result.error


def test_extract_text_accepts_raw_bytes():
    path = DOCUMENTS_DIR / "C1002_bank_statement_july2026.pdf"
    result = extract_text(path.read_bytes())

    assert result.success
    assert "C1002" in result.text


def test_extract_text_missing_file_fails_gracefully():
    result = extract_text(DOCUMENTS_DIR / "does_not_exist.pdf")

    assert not result.success
    assert result.error
