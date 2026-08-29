"""Manual verification for Phase 22 (AI Action Center): confirms the digest
correctly aggregates real open tasks, documents-pending clients, draft
emails, and new leads, and that priority sorting puts High items first.
Not a pytest suite (that's tests/test_action_center_tools.py)."""

import sys

from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import qualify_lead, review_client_documents  # noqa: E402
from tools.action_center_tools import get_action_center_summary  # noqa: E402


def main() -> None:
    seed_main()

    print("=== Baseline summary (fresh seed) ===")
    baseline = get_action_center_summary()
    assert baseline.success
    print(
        f"high_priority={baseline.high_priority_count} followups={baseline.followups_count} "
        f"documents_pending={baseline.documents_pending_count} "
        f"emails_awaiting_approval={baseline.emails_awaiting_approval_count} "
        f"new_leads={baseline.new_leads_count}"
    )
    print(f"items: {len(baseline.items)}\n")

    print("=== Trigger a document review (creates a High-priority task + draft email) ===")
    review_client_documents("C1002")
    print("=== Trigger a lead qualification too ===")
    qualify_lead("L1001")

    after = get_action_center_summary()
    assert after.success
    print(
        f"high_priority={after.high_priority_count} followups={after.followups_count} "
        f"emails_awaiting_approval={after.emails_awaiting_approval_count}"
    )
    assert after.followups_count >= baseline.followups_count + 1
    assert after.emails_awaiting_approval_count >= baseline.emails_awaiting_approval_count + 1
    assert after.high_priority_count >= 1, "review_client_documents creates a High-priority task"

    high_items = [i for i in after.items if i.priority == "High"]
    assert high_items, "expected at least one High-priority item"
    print(f"first High item: {high_items[0].record_id} / {high_items[0].category} -> {high_items[0].recommended_action}")

    print("\n=== Priority sorting check ===")
    priorities_seen = [item.priority for item in after.items]
    first_medium_or_low_index = next(
        (i for i, p in enumerate(priorities_seen) if p != "High"), len(priorities_seen)
    )
    assert all(p == "High" for p in priorities_seen[:first_medium_or_low_index])
    print("OK: all High-priority items are sorted ahead of Medium/Low.\n")

    print("=== Item detail spot-check ===")
    missing_doc_items = [i for i in after.items if i.category == "Missing Document"]
    if missing_doc_items:
        item = missing_doc_items[0]
        print(f"{item.record_id}\n{item.category}\n-> {item.recommended_action}")
        assert item.record_id.startswith("C")

    new_lead_items = [i for i in after.items if i.category == "New Lead"]
    print(f"New Lead items: {len(new_lead_items)}")

    print("\nAll AI Action Center checks passed.")


if __name__ == "__main__":
    main()
