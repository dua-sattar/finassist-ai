"""Manual verification for Phase 30 (broader human-approval gate): confirms
propose_client_update / propose_lead_update never apply a change
immediately, that approving a pending change actually updates the
underlying record, that rejecting one leaves the record untouched, that a
change can't be decided twice, and that the AI Action Center surfaces
pending changes as action items. Not a pytest suite (that's
tests/test_pending_approvals.py)."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database import crud  # noqa: E402
from database.database import init_db  # noqa: E402
from database.seed import main as seed_main  # noqa: E402
from tools.action_center_tools import get_action_center_summary  # noqa: E402
from tools.crm_tools import propose_client_update, propose_lead_update  # noqa: E402


def main() -> None:
    init_db()
    seed_main()

    print("=== propose_client_update never applies immediately ===")
    before = crud.get_client("C1001")
    before_status = before.account_status
    proposed_status = "Closed" if before_status != "Closed" else "Active"
    result = propose_client_update("C1001", "Client requested account closure.", account_status=proposed_status)
    assert result.success, result.error
    assert result.change_id is not None
    after = crud.get_client("C1001")
    assert after.account_status == before_status, "account_status changed before approval!"
    print(f"before={before_status} proposed={proposed_status} still={after.account_status}")
    print("OK\n")

    print("=== Approving a pending change actually applies it ===")
    approved = crud.approve_pending_change(result.change_id)
    assert approved is not None
    assert approved.status == "Approved"
    updated = crud.get_client("C1001")
    assert updated.account_status == proposed_status
    print(f"after approval: {updated.account_status}")
    print("OK\n")

    print("=== A change cannot be decided twice ===")
    second_attempt = crud.approve_pending_change(result.change_id)
    assert second_attempt is None
    print("OK\n")

    print("=== Rejecting a pending change leaves the record untouched ===")
    before_lead = crud.get_lead("L1001")
    before_lead_status = before_lead.status
    proposed_lead_status = "Qualified" if before_lead_status != "Qualified" else "Contacted"
    lead_result = propose_lead_update("L1001", "Lead expressed strong interest on the last call.", status=proposed_lead_status)
    assert lead_result.success, lead_result.error
    rejected = crud.reject_pending_change(lead_result.change_id)
    assert rejected is not None and rejected.status == "Rejected"
    still_unchanged = crud.get_lead("L1001")
    assert still_unchanged.status == before_lead_status
    print(f"lead status unchanged after rejection: {still_unchanged.status}")
    print("OK\n")

    print("=== Proposing with no fields fails gracefully ===")
    empty_result = propose_client_update("C1001", "No actual change.")
    assert not empty_result.success
    print("OK\n")

    print("=== Proposing for an unknown client/lead fails gracefully ===")
    unknown_client = propose_client_update("C9999", "test", account_status="Active")
    assert not unknown_client.success
    unknown_lead = propose_lead_update("L9999", "test", status="Qualified")
    assert not unknown_lead.success
    print("OK\n")

    print("=== AI Action Center surfaces pending changes ===")
    propose_client_update("C1002", "Advisor reassignment requested.", assigned_advisor="Morgan Ellis")
    summary = get_action_center_summary()
    assert summary.success
    assert summary.pending_changes_count >= 1
    assert any(item.category == "Pending Approval" for item in summary.items)
    print(f"pending_changes_count={summary.pending_changes_count}")
    print("OK\n")

    print("All Pending Approvals checks passed.")


if __name__ == "__main__":
    main()
