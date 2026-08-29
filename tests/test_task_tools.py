"""Tests for the Phase 23 task lifecycle (tools/task_tools.py), against the
seeded temp DB (conftest)."""

from datetime import date, timedelta

from database import crud
from tools.task_tools import complete_task, create_followup_task


def test_create_followup_task_assigns_due_date_by_priority():
    today = date.today()
    high = create_followup_task(description="t", priority="High")
    medium = create_followup_task(description="t", priority="Medium")
    low = create_followup_task(description="t", priority="Low")
    unset = create_followup_task(description="t")

    assert high.due_date == today + timedelta(days=1)
    assert medium.due_date == today + timedelta(days=3)
    assert low.due_date == today + timedelta(days=7)
    assert unset.due_date == today + timedelta(days=5)


def test_create_followup_task_explicit_due_date_is_not_overridden():
    explicit = date.today() + timedelta(days=30)
    result = create_followup_task(description="t", due_date=explicit)
    assert result.due_date == explicit


def test_complete_task_moves_task_from_open_to_completed():
    created = create_followup_task(description="Complete me")
    assert any(t.id == created.task_id for t in crud.list_tasks(status="Open"))

    result = complete_task(created.task_id)
    assert result.success

    assert any(t.id == created.task_id for t in crud.list_tasks(status="Completed"))
    assert not any(t.id == created.task_id for t in crud.list_tasks(status="Open"))


def test_complete_task_unknown_id_fails_gracefully():
    result = complete_task(999999)
    assert not result.success


def test_list_tasks_filters_by_status_and_client():
    created = create_followup_task(description="Client-linked task", client_id="C1001")
    open_for_client = crud.list_tasks(status="Open", client_id="C1001")
    assert any(t.id == created.task_id for t in open_for_client)

    open_for_other_client = crud.list_tasks(status="Open", client_id="C1002")
    assert not any(t.id == created.task_id for t in open_for_other_client)
