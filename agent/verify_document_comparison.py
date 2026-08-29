"""Manual verification for Phase 25 (Document Comparison): confirms two
documents for one client are diffed field-by-field, numeric deltas compute
correctly, a document-type mismatch is flagged, and a failed extraction is
handled without crashing. Not a pytest suite (that's
tests/test_document_comparison.py)."""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import compare_documents  # noqa: E402
from database.seed import main as seed_main  # noqa: E402

DOCS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"


def _load(filename: str) -> tuple[bytes, str]:
    return (DOCS_DIR / filename).read_bytes(), filename


def main() -> None:
    seed_main()

    print("=== Unknown client fails gracefully ===")
    result = compare_documents(
        "C9999", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement_july2026.pdf")
    )
    assert result.success
    assert not result.found
    print("OK\n")

    print("=== Same-type comparison: two C1002 bank statements from different periods ===")
    result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement_july2026.pdf")
    )
    assert result.success and result.found
    assert not result.document_type_mismatch
    assert result.document_a.success and result.document_b.success

    by_field = {c.field: c for c in result.field_comparisons}
    assert by_field["account_number"].changed
    assert by_field["statement_period"].changed
    assert by_field["opening_balance"].changed
    assert by_field["opening_balance"].delta == round(25000.0 - 24145.94, 2)
    assert by_field["total_deposits"].delta == round(12500.0 - 13735.86, 2)
    assert by_field["total_withdrawals"].delta == round(8200.0 - 2539.63, 2)
    # closing_balance is missing in A (None) and present in B -- still a change, but no numeric delta.
    assert by_field["closing_balance"].changed
    assert by_field["closing_balance"].delta is None
    assert "closing_balance" in result.changed_fields
    assert result.ai_observation
    assert result.recommended_action
    assert "Human Review Required" in result.report
    print(f"changed_fields={result.changed_fields}")
    print(f"ai_observation={result.ai_observation}")
    print(f"recommended_action={result.recommended_action}")
    print("OK\n")

    print("=== Document type mismatch is flagged ===")
    mismatch_result = compare_documents(
        "C1001", _load("C1001_government_id.pdf"), _load("C1001_proof_of_address.pdf")
    )
    assert mismatch_result.success and mismatch_result.found
    assert mismatch_result.document_type_mismatch
    assert "different types" in mismatch_result.recommended_action.lower()
    print(f"recommended_action={mismatch_result.recommended_action}")
    print("OK\n")

    print("=== Identical document compared against itself has no changes ===")
    same_result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("C1002_bank_statement.pdf")
    )
    assert same_result.success and same_result.found
    assert not same_result.changed_fields
    assert "no differences" in same_result.recommended_action.lower()
    print("OK\n")

    print("=== A failed extraction is reported, not fatal ===")
    failed_result = compare_documents(
        "C1002", _load("C1002_bank_statement.pdf"), _load("invalid_corrupted.pdf")
    )
    assert failed_result.success and failed_result.found
    assert failed_result.document_a.success
    assert not failed_result.document_b.success
    assert "Human Review Required" in failed_result.report
    print("OK\n")

    print("All Document Comparison checks passed.")


if __name__ == "__main__":
    main()
