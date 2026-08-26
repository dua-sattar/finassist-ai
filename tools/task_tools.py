"""create_followup_task tool -- creates a follow-up task for a human advisor."""

import logging
from datetime import date

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)


class CreateFollowupTaskResult(BaseModel):
    success: bool
    task_id: int | None = None
    task_type: str
    description: str
    priority: str | None = None
    error: str | None = None


def create_followup_task(
    description: str,
    task_type: str = "follow_up",
    client_id: str | None = None,
    lead_id: str | None = None,
    priority: str | None = None,
    due_date: date | None = None,
) -> CreateFollowupTaskResult:
    """Create a follow-up task for a human advisor, tied to a client and/or lead."""
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
            f"client_id={client_id} lead_id={lead_id} type={task_type} priority={priority}",
            f"task_id={task.id}",
        )
        return CreateFollowupTaskResult(
            success=True, task_id=task.id, task_type=task_type, description=description, priority=priority
        )
    except Exception as exc:
        logger.warning("create_followup_task failed: %s", exc)
        log_action("create_followup_task", f"client_id={client_id} lead_id={lead_id}", str(exc), status="error")
        return CreateFollowupTaskResult(
            success=False, task_type=task_type, description=description, priority=priority, error=str(exc)
        )
