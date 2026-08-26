"""Phase 10 verification: run the client document-review workflow against
the C1002 scenario (missing Government-issued ID, per Phase 3) and confirm
the report matches spec section 12's example shape. Also checks C1001 (a
different missing category) and an unknown client. Not a pytest suite
(that's Phase 15)."""

import sys

from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import review_client_documents  # noqa: E402


def main() -> None:
    seed_main()

    print("=== C1002 (expect missing: Government-issued ID) ===")
    result = review_client_documents("C1002")
    print(result.report)
    print()
    assert result.success and result.found
    assert result.missing_categories == ["Government-issued ID"]
    assert result.onboarding_status == "Documents Pending"
    assert result.task_id is not None, "expected a follow-up task to be created"
    assert result.followup_id is not None, "expected a draft follow-up email to be created"
    assert "✗ Government-issued ID" in result.report
    assert "Status: Documents Pending" in result.report
    assert "Recommended Next Action:" in result.report
    assert "Human review required" in result.report
    print("OK: C1002 report matches spec section 12's example shape.\n")

    print("=== C1001 (expect missing: Completed Application Form) ===")
    result = review_client_documents("C1001")
    print(result.report)
    print()
    assert result.missing_categories == ["Completed Application Form"]
    print("OK: C1001 correctly shows a different missing category.\n")

    print("=== C9999 (unknown client) ===")
    result = review_client_documents("C9999")
    print(f"success={result.success} found={result.found}")
    assert result.success and not result.found
    print("OK: unknown client handled gracefully, no crash.")


if __name__ == "__main__":
    main()
