"""Manual verification for Phase 24 (Multi-Document Analysis): confirms a
batch of documents for one client is analyzed together, category coverage
and consistency checks are computed correctly, and mismatched client IDs
across a batch are flagged. Not a pytest suite (that's
tests/test_multi_document.py)."""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import analyze_multiple_documents  # noqa: E402
from database.seed import main as seed_main  # noqa: E402

DOCS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"


def _load(*filenames: str) -> list[tuple[bytes, str]]:
    return [((DOCS_DIR / name).read_bytes(), name) for name in filenames]


def main() -> None:
    seed_main()

    print("=== Unknown client fails gracefully ===")
    result = analyze_multiple_documents("C9999", _load("C1001_government_id.pdf"))
    assert result.success
    assert not result.found
    print("OK\n")

    print("=== Consistent batch for C1001: coverage + consistency ===")
    result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "C1001_proof_of_address.pdf", "C1001_bank_statement.pdf"),
    )
    assert result.success and result.found
    assert len(result.batch_items) == 3
    assert all(item.success for item in result.batch_items), result.batch_items
    assert not result.client_id_mismatch, result.client_ids_seen
    assert "Government-issued ID" not in result.missing_categories
    assert "Proof of Address" not in result.missing_categories
    assert "Recent Financial Statement" not in result.missing_categories
    assert "Completed Application Form" in result.missing_categories
    assert result.overall_status == "Partial"
    assert result.ai_observation
    assert result.recommended_action
    assert "Human Review Required" in result.report
    print(f"missing_categories={result.missing_categories}")
    print(f"ai_observation={result.ai_observation}")
    print(f"recommended_action={result.recommended_action}")
    print("OK\n")

    print("=== Mismatched client IDs across a batch are flagged ===")
    mismatch_result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "C1002_bank_statement.pdf"),
    )
    assert mismatch_result.success and mismatch_result.found
    assert mismatch_result.client_id_mismatch, mismatch_result.client_ids_seen
    assert set(mismatch_result.client_ids_seen) == {"C1001", "C1002"}
    assert "different client identities" in mismatch_result.recommended_action.lower()
    print(f"client_ids_seen={mismatch_result.client_ids_seen}")
    print(f"recommended_action={mismatch_result.recommended_action}")
    print("OK\n")

    print("=== A failed extraction in the batch is reported, not fatal ===")
    mixed_result = analyze_multiple_documents(
        "C1001",
        _load("C1001_government_id.pdf", "invalid_corrupted.pdf"),
    )
    assert mixed_result.success and mixed_result.found
    assert len(mixed_result.batch_items) == 2
    assert any(not item.success for item in mixed_result.batch_items)
    assert any(item.success for item in mixed_result.batch_items)
    print("OK\n")

    print("All Multi-Document Analysis checks passed.")


if __name__ == "__main__":
    main()
