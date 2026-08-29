"""Tests for the Phase 24 multi-document analysis workflow
(agent/workflows.py::analyze_multiple_documents), against the seeded temp DB
and real synthetic PDFs (conftest)."""

from pathlib import Path

from agent.workflows import analyze_multiple_documents

DOCS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"


def _load(*filenames: str) -> list[tuple[bytes, str]]:
    return [((DOCS_DIR / name).read_bytes(), name) for name in filenames]


def test_unknown_client_returns_not_found():
    result = analyze_multiple_documents("C9999", _load("C1001_government_id.pdf"))
    assert result.success
    assert not result.found


def test_batch_reports_missing_categories():
    result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "C1001_proof_of_address.pdf", "C1001_bank_statement.pdf"),
    )
    assert result.success and result.found
    assert len(result.batch_items) == 3
    assert all(item.success for item in result.batch_items)
    assert "Completed Application Form" in result.missing_categories
    assert "Government-issued ID" not in result.missing_categories
    assert result.overall_status == "Partial"


def test_batch_flags_client_id_mismatch():
    result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "C1002_bank_statement.pdf"),
    )
    assert result.success and result.found
    assert result.client_id_mismatch
    assert set(result.client_ids_seen) == {"C1001", "C1002"}


def test_batch_without_mismatch_does_not_flag_it():
    result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "C1001_proof_of_address.pdf"),
    )
    assert result.success and result.found
    assert not result.client_id_mismatch


def test_failed_extraction_in_batch_is_reported_not_fatal():
    result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "invalid_corrupted.pdf"),
    )
    assert result.success and result.found
    assert len(result.batch_items) == 2
    assert any(not item.success for item in result.batch_items)
    assert any(item.success for item in result.batch_items)


def test_report_always_includes_human_review_notice():
    result = analyze_multiple_documents("C1001", _load("C1001_government_id.pdf"))
    assert "Human Review Required" in result.report
