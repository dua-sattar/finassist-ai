"""Tests for document_processing/extractor.py."""

from document_processing.extractor import process_document
from tests.conftest import DOCUMENTS_DIR


def test_process_valid_complete_bank_statement():
    result = process_document(DOCUMENTS_DIR / "C1002_bank_statement_july2026.pdf")

    assert result.success
    assert result.document_type == "bank_statement"
    assert result.extracted_fields["client_id"] == "C1002"
    assert result.extracted_fields["closing_balance"] == 29300.0
    assert result.missing_fields == []
    assert result.summary


def test_process_incomplete_document_reports_missing_fields():
    result = process_document(DOCUMENTS_DIR / "C1002_bank_statement.pdf")

    assert result.success  # a missing optional field is not a failure
    assert result.document_type == "bank_statement"
    assert "closing_balance" in result.missing_fields


def test_process_corrupted_document_fails_gracefully():
    result = process_document(DOCUMENTS_DIR / "invalid_corrupted.pdf")

    assert not result.success
    assert result.document_type == "unknown"
    assert result.error


def test_process_government_id_and_proof_of_address():
    gov_id = process_document(DOCUMENTS_DIR / "C1003_government_id.pdf")
    proof = process_document(DOCUMENTS_DIR / "C1002_proof_of_address.pdf")

    assert gov_id.success and gov_id.document_type == "government_id"
    assert proof.success and proof.document_type == "proof_of_address"
