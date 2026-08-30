"""Tests for the Phase 30 human-approval gate (database.crud pending-change
functions + tools.crm_tools.propose_client_update/propose_lead_update),
against the seeded temp DB (conftest)."""

from database import crud
from tools.action_center_tools import get_action_center_summary
from tools.crm_tools import propose_client_update, propose_lead_update


def test_propose_client_update_does_not_apply_immediately():
    before = crud.get_client("C1001").account_status
    proposed = "Closed" if before != "Closed" else "Active"
    result = propose_client_update("C1001", "Test reason.", account_status=proposed)
    assert result.success
    assert result.change_id is not None
    assert crud.get_client("C1001").account_status == before


def test_approving_a_pending_change_applies_it():
    before = crud.get_client("C1002").account_status
    proposed = "Closed" if before != "Closed" else "Active"
    result = propose_client_update("C1002", "Test reason.", account_status=proposed)
    approved = crud.approve_pending_change(result.change_id)
    assert approved is not None
    assert approved.status == "Approved"
    assert crud.get_client("C1002").account_status == proposed


def test_rejecting_a_pending_change_leaves_record_untouched():
    before = crud.get_lead("L1002").status
    proposed = "Qualified" if before != "Qualified" else "Contacted"
    result = propose_lead_update("L1002", "Test reason.", status=proposed)
    rejected = crud.reject_pending_change(result.change_id)
    assert rejected is not None
    assert rejected.status == "Rejected"
    assert crud.get_lead("L1002").status == before


def test_a_change_cannot_be_decided_twice():
    result = propose_client_update("C1003", "Test reason.", assigned_advisor="Someone New")
    first = crud.approve_pending_change(result.change_id)
    assert first is not None
    second = crud.approve_pending_change(result.change_id)
    assert second is None


def test_a_rejected_change_cannot_later_be_approved():
    result = propose_client_update("C1004", "Test reason.", assigned_advisor="Someone New")
    crud.reject_pending_change(result.change_id)
    later_approve = crud.approve_pending_change(result.change_id)
    assert later_approve is None


def test_propose_update_with_no_fields_fails_gracefully():
    result = propose_client_update("C1001", "No actual change.")
    assert not result.success


def test_propose_update_for_unknown_client_fails_gracefully():
    result = propose_client_update("C9999", "test", account_status="Active")
    assert not result.success


def test_propose_update_for_unknown_lead_fails_gracefully():
    result = propose_lead_update("L9999", "test", status="Qualified")
    assert not result.success


def test_list_pending_changes_filters_by_status():
    result = propose_client_update("C1005", "Test reason.", account_status="Active")
    pending = crud.list_pending_changes(status="Pending")
    assert any(c.id == result.change_id for c in pending)

    crud.approve_pending_change(result.change_id)
    pending_after = crud.list_pending_changes(status="Pending")
    assert not any(c.id == result.change_id for c in pending_after)
    approved_after = crud.list_pending_changes(status="Approved")
    assert any(c.id == result.change_id for c in approved_after)


def test_action_center_surfaces_pending_changes():
    propose_client_update("C1006", "Advisor reassignment requested.", assigned_advisor="Priya Nandakumar")
    summary = get_action_center_summary()
    assert summary.success
    assert summary.pending_changes_count >= 1
    assert any(item.category == "Pending Approval" for item in summary.items)
