"""summarize_meeting_notes tool -- turns raw client/lead meeting or call
notes into a structured summary (spec section 25): key points, decisions,
action items, and next steps. Action items automatically become follow-up
tasks (via tools.task_tools.create_followup_task) so they show up on the
Follow-ups page and AI Action Center like any other task -- the summary
itself is stored (database.crud.create_meeting_summary) so past meetings
stay retrievable per client/lead.
"""

import logging
import os

from pydantic import BaseModel

from database import crud
from tools.common import log_action
from tools.crm_tools import get_client, get_lead
from tools.task_tools import create_followup_task

logger = logging.getLogger(__name__)

_SECTION_HEADERS = ["Key Points", "Decisions", "Action Items", "Next Steps"]
_MAX_ACTION_ITEM_TASKS = 10

MEETING_SYSTEM_PROMPT = (
    "You are FinAssist AI's meeting-notes assistant. Given raw notes from a client "
    "or lead meeting or call, extract a structured summary using ONLY information "
    "present in the notes -- never invent facts, commitments, figures, or dates not "
    "stated. Respond in EXACTLY this format, with each header on its own line "
    "followed by bullet points starting with '- ' (write '- None noted.' if a "
    "section has nothing):\n\n"
    "Key Points:\n- ...\n\nDecisions:\n- ...\n\nAction Items:\n- ...\n\nNext Steps:\n- ..."
)


class MeetingSummaryResult(BaseModel):
    success: bool
    meeting_id: int | None = None
    client_id: str | None = None
    lead_id: str | None = None
    key_points: list[str] = []
    decisions: list[str] = []
    action_items: list[str] = []
    next_steps: list[str] = []
    task_ids_created: list[int] = []
    report: str = ""
    used_ai: bool = False
    error: str | None = None


def _parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {header: [] for header in _SECTION_HEADERS}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        header_match = next(
            (h for h in _SECTION_HEADERS if stripped.lower().rstrip(":") == h.lower()), None
        )
        if header_match:
            current = header_match
            continue
        if current and stripped.startswith("-"):
            item = stripped.lstrip("-").strip()
            if item and item.lower() != "none noted.":
                sections[current].append(item)
    return sections


def _generate_structured_summary(raw_notes: str) -> tuple[dict[str, list[str]], bool]:
    """Returns (sections, used_ai). On any failure or missing API key, falls
    back to an honest empty structure rather than fabricating a summary of
    unstructured text without an LLM."""
    empty = {header: [] for header in _SECTION_HEADERS}
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return empty, False

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": MEETING_SYSTEM_PROMPT},
                {"role": "user", "content": raw_notes},
            ],
            max_tokens=500,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("empty response from Groq")
        return _parse_sections(text), True
    except Exception as exc:
        logger.warning("Groq meeting-summary call failed: %s", exc)
        return empty, False


def _format_report(
    client_id: str | None,
    lead_id: str | None,
    key_points: list[str],
    decisions: list[str],
    action_items: list[str],
    next_steps: list[str],
    used_ai: bool,
    task_ids_created: list[int],
) -> str:
    lines = ["MEETING SUMMARY", ""]
    if client_id:
        lines.append(f"Client: {client_id}")
    if lead_id:
        lines.append(f"Lead: {lead_id}")
    if not client_id and not lead_id:
        lines.append("Not linked to a client or lead record.")
    lines.append("")

    def _section(title: str, items: list[str]) -> None:
        lines.append(f"{title}:")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- None noted.")
        lines.append("")

    _section("Key Points", key_points)
    _section("Decisions", decisions)
    _section("Action Items", action_items)
    _section("Next Steps", next_steps)

    if not used_ai:
        lines.append(
            "AI summarization was unavailable for this note (no API key configured or the "
            "call failed) -- please review the raw notes manually below."
        )
        lines.append("")

    if task_ids_created:
        lines.append(f"Follow-up task(s) created from action items: {', '.join(f'#{t}' for t in task_ids_created)}")
        lines.append("")

    lines.append("Human Review Required")
    return "\n".join(lines)


def summarize_meeting_notes(
    raw_notes: str, client_id: str | None = None, lead_id: str | None = None
) -> MeetingSummaryResult:
    """Summarize raw client/lead meeting or call notes into key points,
    decisions, action items, and next steps via Groq (with an honest empty
    fallback if unavailable -- never a fabricated summary of unstructured
    text). Action items become follow-up tasks automatically (capped at 10
    per meeting). Stores the summary for later retrieval."""
    if client_id:
        client_result = get_client(client_id)
        if not client_result.success:
            return MeetingSummaryResult(success=False, error=client_result.error)
        if not client_result.found:
            return MeetingSummaryResult(success=False, error=f"Client {client_id} not found.")
    if lead_id:
        lead_result = get_lead(lead_id)
        if not lead_result.success:
            return MeetingSummaryResult(success=False, error=lead_result.error)
        if not lead_result.found:
            return MeetingSummaryResult(success=False, error=f"Lead {lead_id} not found.")

    try:
        sections, used_ai = _generate_structured_summary(raw_notes)
        key_points = sections["Key Points"]
        decisions = sections["Decisions"]
        action_items = sections["Action Items"]
        next_steps = sections["Next Steps"]

        task_ids_created: list[int] = []
        for item in action_items[:_MAX_ACTION_ITEM_TASKS]:
            task = create_followup_task(
                description=item, task_type="meeting_action_item", client_id=client_id, lead_id=lead_id,
                priority="Medium",
            )
            if task.success and task.task_id is not None:
                task_ids_created.append(task.task_id)

        meeting = crud.create_meeting_summary(
            client_id=client_id, lead_id=lead_id, raw_notes=raw_notes, key_points=key_points,
            decisions=decisions, action_items=action_items, next_steps=next_steps,
        )

        report = _format_report(
            client_id, lead_id, key_points, decisions, action_items, next_steps, used_ai, task_ids_created
        )

        log_action(
            "summarize_meeting_notes",
            f"client_id={client_id} lead_id={lead_id}",
            f"meeting_id={meeting.id} action_items={len(action_items)} tasks_created={len(task_ids_created)}",
        )
        return MeetingSummaryResult(
            success=True,
            meeting_id=meeting.id,
            client_id=client_id,
            lead_id=lead_id,
            key_points=key_points,
            decisions=decisions,
            action_items=action_items,
            next_steps=next_steps,
            task_ids_created=task_ids_created,
            report=report,
            used_ai=used_ai,
        )
    except Exception as exc:
        logger.warning("summarize_meeting_notes failed: %s", exc)
        log_action("summarize_meeting_notes", f"client_id={client_id} lead_id={lead_id}", str(exc), status="error")
        return MeetingSummaryResult(success=False, client_id=client_id, lead_id=lead_id, error=str(exc))
