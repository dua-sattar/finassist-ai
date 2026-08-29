"""Tests for the Phase 22 AI Action Center tool
(tools/action_center_tools.py), against the seeded temp DB (conftest)."""

from agent.workflows import qualify_lead, review_client_documents
from tools.action_center_tools import get_action_center_summary


def test_get_action_center_summary_succeeds_on_fresh_seed():
    result = get_action_center_summary()
    assert result.success
    assert result.new_leads_count > 0
    assert result.documents_pending_count > 0


def test_get_action_center_summary_reflects_new_task_and_draft():
    before = get_action_center_summary()
    review_client_documents("C1003")
    after = get_action_center_summary()

    assert after.success
    assert after.followups_count >= before.followups_count + 1
    assert after.emails_awaiting_approval_count >= before.emails_awaiting_approval_count + 1
    assert after.high_priority_count >= 1


def test_get_action_center_summary_items_sorted_high_priority_first():
    review_client_documents("C1004")
    result = get_action_center_summary()

    priorities = [item.priority for item in result.items]
    first_non_high = next((i for i, p in enumerate(priorities) if p != "High"), len(priorities))
    assert all(p == "High" for p in priorities[:first_non_high])


def test_get_action_center_summary_includes_new_lead_items():
    result = get_action_center_summary()
    new_lead_items = [item for item in result.items if item.category == "New Lead"]
    assert len(new_lead_items) == result.new_leads_count
    if new_lead_items:
        assert new_lead_items[0].recommended_action == "Review Qualification"


def test_get_action_center_summary_task_without_client_or_lead_gets_readable_id():
    from tools.contact_tools import create_contact_submission
    from tools.task_tools import create_followup_task

    create_contact_submission(name="Test", email="test@example.com", subject="s", message="m")
    task = create_followup_task(description="Review an unlinked ticket", task_type="contact_ticket")

    result = get_action_center_summary()
    matching = [item for item in result.items if item.key == f"task-{task.task_id}"]
    assert matching
    assert matching[0].record_id == f"Task #{task.task_id}"


def test_qualify_lead_removes_lead_from_new_leads_count():
    before = get_action_center_summary()
    before_new_count = sum(1 for item in before.items if item.category == "New Lead")

    # find any lead currently counted as New
    from database import crud

    new_leads = crud.list_leads(status="New")
    assert new_leads, "expected at least one New lead in the seeded data"
    qualify_lead(new_leads[0].lead_id)

    after = get_action_center_summary()
    after_new_count = sum(1 for item in after.items if item.category == "New Lead")
    assert after_new_count == before_new_count - 1
