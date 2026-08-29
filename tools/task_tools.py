"""create_followup_task / complete_task tools -- task lifecycle for a human
advisor (spec sections 20-21)."""

import logging
from datetime import date, timedelta

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)

# Default due date, by priority, when the caller doesn't set one explicitly
# -- keeps "Overdue"/"Due Today"/"Upcoming" grouping meaningful for
# AI-created tasks rather than leaving due_date perpetually null.
_DEFAULT_DUE_DAYS = {"High": 1, "Medium": 3, "Low": 7}
_DEFAULT_DUE_DAYS_FALLBACK = 5


class CreateFollowupTaskResult(BaseModel):
    success: bool
    task_id: int | None = None
    task_type: str
    description: str
    priority: str | None = None
    due_date: date | None = None
    error: str | None = None


def create_followup_task(
    description: str,
    task_type: str = "follow_up",
    client_id: str | None = None,
    lead_id: str | None = None,
    priority: str | None = None,
    due_date: date | None = None,
) -> CreateFollowupTaskResult:
    """Create a follow-up task for a human advisor, tied to a client and/or
    lead. If due_date isn't given, one is assigned based on priority (High
    +1 day, Medium +3 days, Low +7 days, otherwise +5 days)."""
    if due_date is None:
        due_date = date.today() + timedelta(days=_DEFAULT_DUE_DAYS.get(priority, _DEFAULT_DUE_DAYS_FALLBACK))
    try:
        task = crud.create_task(
            task_type=task_type,
            description=description,
            client_id=client_id,
            lead_id=lead_id,
            priority=priority,
            due_date=due_date,
        )
        log_action(
            "create_followup_task",
            f"client_id={client_id} lead_id={lead_id} type={task_type} priority={priority} due_date={due_date}",
            f"task_id={task.id}",
        )
        return CreateFollowupTaskResult(
            success=True,
            task_id=task.id,
            task_type=task_type,
            description=description,
            priority=priority,
            due_date=due_date,
        )
    except Exception as exc:
        logger.warning("create_followup_task failed: %s", exc)
        log_action("create_followup_task", f"client_id={client_id} lead_id={lead_id}", str(exc), status="error")
        return CreateFollowupTaskResult(
            success=False, task_type=task_type, description=description, priority=priority, error=str(exc)
        )


class CompleteTaskResult(BaseModel):
    success: bool
    task_id: int
    error: str | None = None


def complete_task(task_id: int) -> CompleteTaskResult:
    """Mark a task as completed."""
    try:
        updated = crud.complete_task(task_id)
        if updated is None:
            log_action("complete_task", f"task_id={task_id}", "not found", status="error")
            return CompleteTaskResult(success=False, task_id=task_id, error="Task not found.")
        log_action("complete_task", f"task_id={task_id}", "completed", human_approval_status="N/A")
        return CompleteTaskResult(success=True, task_id=task_id)
    except Exception as exc:
        logger.warning("complete_task failed for %s: %s", task_id, exc)
        log_action("complete_task", f"task_id={task_id}", str(exc), status="error")
        return CompleteTaskResult(success=False, task_id=task_id, error=str(exc))
