"""get_action_center_summary tool -- aggregates actionable items across the
system into one prioritized "what needs attention today" digest (spec
section 19). Distinct from the AI Actions page: that's a historical audit
log of every tool call; this is a forward-looking triage list. Read-only,
so (like Phase 21's case summary) it's safe to expose to the chat agent.

"Follow-up Overdue" isn't included as its own category yet: no task in this
codebase currently gets a real due_date (create_followup_task's due_date
param is always None in every caller today), so there's nothing genuine to
call "overdue" on. Phase 23 (due-date mechanics + overdue grouping) is
where that gets built for real, rather than faking it here.
"""

import logging

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)

_TASK_TYPE_LABELS = {
    "document_follow_up": "Missing Document",
    "lead_follow_up": "Lead Follow-up",
    "contact_ticket": "Contact Ticket",
}

_PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


class ActionItem(BaseModel):
    key: str
    record_id: str
    category: str
    priority: str
    recommended_action: str
    detail: str


class ActionCenterSummary(BaseModel):
    success: bool
    high_priority_count: int = 0
    followups_count: int = 0
    documents_pending_count: int = 0
    emails_awaiting_approval_count: int = 0
    new_leads_count: int = 0
    pending_changes_count: int = 0
    items: list[ActionItem] = []
    error: str | None = None


def get_action_center_summary() -> ActionCenterSummary:
    """Aggregate open tasks, documents-pending clients, draft emails
    awaiting approval, pending CRM changes awaiting approval, and
    unqualified new leads into one prioritized action-item list. Read-only
    -- never changes anything."""
    try:
        open_tasks = crud.list_open_tasks()
        clients = crud.list_clients()
        drafts = crud.list_followups(status="Draft")
        new_leads = crud.list_leads(status="New")
        pending_changes = crud.list_pending_changes(status="Pending")

        items: list[ActionItem] = []

        for t in open_tasks:
            category = _TASK_TYPE_LABELS.get(t.task_type, "Follow-up")
            # A contact-ticket task has no client/lead FK yet (the submitter
            # isn't a CRM record until/unless classified a lead) -- fall back
            # to a task reference rather than a bare "-".
            record_id = t.client_id or t.lead_id or f"Task #{t.id}"
            items.append(
                ActionItem(
                    key=f"task-{t.id}",
                    record_id=record_id,
                    category=category,
                    priority=t.priority or "Medium",
                    recommended_action=t.description,
                    detail=t.description,
                )
            )

        for lead in new_leads:
            items.append(
                ActionItem(
                    key=f"lead-{lead.lead_id}",
                    record_id=lead.lead_id,
                    category="New Lead",
                    priority="Medium",
                    recommended_action="Review Qualification",
                    detail=f"{lead.name} ({lead.company}) -- interested in {lead.service_interest}",
                )
            )

        for f in drafts:
            record_id = f.client_id or f.lead_id or f.to_email or "-"
            items.append(
                ActionItem(
                    key=f"followup-{f.id}",
                    record_id=record_id,
                    category="Email Awaiting Approval",
                    priority="Medium",
                    recommended_action=f"Review and approve draft: {f.subject}",
                    detail=f.subject,
                )
            )

        for change in pending_changes:
            entity_label = "Client" if change.entity_type == "client" else "Lead"
            items.append(
                ActionItem(
                    key=f"pending-change-{change.id}",
                    record_id=change.entity_id,
                    category="Pending Approval",
                    priority="High",
                    recommended_action=f"Review and approve {entity_label.lower()} update on the Pending Approvals page",
                    detail=change.reason,
                )
            )

        items.sort(key=lambda item: _PRIORITY_RANK.get(item.priority, 1))

        high_priority_count = sum(1 for item in items if item.priority == "High")
        documents_pending_count = sum(1 for c in clients if c.onboarding_status == "Documents Pending")

        log_action("get_action_center_summary", "", f"{len(items)} action items")
        return ActionCenterSummary(
            success=True,
            high_priority_count=high_priority_count,
            followups_count=len(open_tasks),
            documents_pending_count=documents_pending_count,
            emails_awaiting_approval_count=len(drafts),
            new_leads_count=len(new_leads),
            pending_changes_count=len(pending_changes),
            items=items,
        )
    except Exception as exc:
        logger.warning("get_action_center_summary failed: %s", exc)
        log_action("get_action_center_summary", "", str(exc), status="error")
        return ActionCenterSummary(success=False, error=str(exc))
