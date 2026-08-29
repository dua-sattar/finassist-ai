"""Manual verification for Phase 21 (AI Client Case Summary): confirms the
report matches the spec section 12 example shape and that real recent
activity (documents/tasks/follow-ups) is correctly gathered and ordered.
Not a pytest suite (that's tests/test_summary_tools.py)."""

import sys

from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import review_client_documents  # noqa: E402
from tools.summary_tools import generate_case_summary  # noqa: E402


def main() -> None:
    seed_main()

    print("=== C1002 (has real document/task/followup activity from other phases) ===")
    result = generate_case_summary("C1002")
    print(result.report)
    print()

    assert result.success and result.found
    assert result.client_name == "Noah Rhodes"
    assert result.service == "Retirement Planning"
    assert "CLIENT CASE SUMMARY" in result.report
    assert "Documents:" in result.report
    assert "Recent Activity:" in result.report
    assert "AI Summary:" in result.report
    assert "Recommended Action:" in result.report
    assert "Human Review Required" in result.report
    assert result.ai_summary
    assert result.recommended_action
    print(f"OK: report has all required sections. recent_activity items: {len(result.recent_activity)}\n")

    print("=== Trigger a document review first, then confirm activity picks it up ===")
    review_client_documents("C1001")
    result2 = generate_case_summary("C1001")
    print(f"recent_activity for C1001: {result2.recent_activity}")
    assert result2.success and result2.found
    assert len(result2.recent_activity) > 0, "expected activity after running the document-review workflow"
    print("OK: recent activity reflects real DB state.\n")

    print("=== Unknown client ===")
    result3 = generate_case_summary("C9999")
    print(f"success={result3.success} found={result3.found}")
    assert result3.success and not result3.found
    print("OK: unknown client handled gracefully, no crash.")

    print("\nAll Case Summary checks passed.")


if __name__ == "__main__":
    main()
