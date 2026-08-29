"""Tests for the Phase 25 document comparison workflow
(agent/workflows.py::compare_documents), against the seeded temp DB and real
synthetic PDFs (conftest)."""

from pathlib import Path

from agent.workflows import compare_documents

DOCS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"


def _load(filename: str) -> tuple[bytes, str]:
    return (DOCS_DIR / filename).read_bytes(), filename


def test_unknown_client_returns_not_found():
    result = compare_documents(
        "C9999", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement_july2026.pdf")
    )
    assert result.success
    assert not result.found


def test_same_type_comparison_computes_field_deltas():
    result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement_july2026.pdf")
    )
    assert result.success and result.found
    assert not result.document_type_mismatch

    by_field = {c.field: c for c in result.field_comparisons}
    assert by_field["opening_balance"].changed
    assert by_field["opening_balance"].delta == round(25000.0 - 24145.94, 2)
    assert by_field["total_deposits"].delta == round(12500.0 - 13735.86, 2)
    assert "account_number" in result.changed_fields
    assert "statement_period" in result.changed_fields


def test_missing_field_in_one_document_is_changed_without_delta():
    result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement_july2026.pdf")
    )
    by_field = {c.field: c for c in result.field_comparisons}
    assert by_field["closing_balance"].value_a is None
    assert by_field["closing_balance"].changed
    assert by_field["closing_balance"].delta is None


def test_document_type_mismatch_is_flagged():
    result = compare_documents(
        "C1001", _load("C1001_government_id.pdf"), _load("C1001_proof_of_address.pdf")
    )
    assert result.success and result.found
    assert result.document_type_mismatch
    assert "different types" in result.recommended_action.lower()


def test_identical_document_has_no_changes():
    result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement.pdf")
    )
    assert result.success and result.found
    assert result.changed_fields == []
    assert "no differences" in result.recommended_action.lower()


def test_failed_extraction_is_reported_not_fatal():
    result = compare_documents("C1002", _load("C1002_bank_statement.pdf"), _load("invalid_corrupted.pdf"))
    assert result.success and result.found
    assert result.document_a.success
    assert not result.document_b.success
    assert "Human Review Required" in result.report


def test_report_always_includes_human_review_notice():
    result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement_july2026.pdf")
    )
    assert "Human Review Required" in result.report
