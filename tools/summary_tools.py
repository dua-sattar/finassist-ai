"""generate_case_summary tool -- an AI-generated per-client case summary
(spec section 12), combining real CRM/document data with a narrated
paragraph. Read-only: unlike the Phase 10/11 workflows, it never mutates
CRM state (no status changes, no tasks, no drafts), so it's safe to expose
directly to the chat agent rather than only a dedicated UI button.
"""

import logging
import os

from pydantic import BaseModel

from database import crud
from tools.common import log_action
from tools.document_tools import RequiredDocumentStatus, check_required_documents

logger = logging.getLogger(__name__)

MAX_ACTIVITY_ITEMS = 8

CASE_SUMMARY_SYSTEM_PROMPT = (
    "You are FinAssist AI's internal case-summary assistant. Given a client's service, "
    "onboarding status, document checklist, and recent activity, write a concise 2-3 "
    "sentence summary for an advisor's quick review. Only state facts present in the "
    "provided data -- do not invent details, dates, or outcomes not given to you."
)


class ClientCaseSummaryResult(BaseModel):
    success: bool
    client_id: str
    found: bool = False
    client_name: str | None = None
    service: str | None = None
    status: str | None = None
    checklist: list[RequiredDocumentStatus] = []
    all_satisfied: bool = False
    recent_activity: list[str] = []
    ai_summary: str = ""
    recommended_action: str = ""
    report: str = ""
    error: str | None = None


def _gather_recent_activity(client_id: str) -> list[str]:
    """Merge document uploads, task creations, and follow-up emails into one
    chronological (most-recent-first) activity feed. Uses the same
    relational client_id FKs as everything else in the app -- no fragile
    text-matching against ai_action_log."""
    events: list[tuple[object, str]] = []

    for d in crud.list_documents_for_client(client_id):
        events.append((d.uploaded_at, f"Document uploaded: {d.filename} ({d.document_type})"))

    for t in crud.list_open_tasks(client_id=client_id):
        events.append((t.created_at, f"Task created: {t.description}"))

    for f in crud.list_followups():
        if f.client_id == client_id:
            events.append((f.created_at, f"Follow-up email {f.status.lower()}: {f.subject}"))

    events.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _ts, text in events[:MAX_ACTIVITY_ITEMS]]


def _fallback_ai_summary(client_name: str, service: str, status: str, all_satisfied: bool, missing: list[str]) -> str:
    doc_note = (
        "All required onboarding documents are on file."
        if all_satisfied
        else f"Still missing: {', '.join(missing)}."
    )
    return f"{client_name} is engaged for {service} and is currently {status}. {doc_note}"


def _generate_ai_summary(
    client_id: str,
    client_name: str,
    service: str,
    status: str,
    checklist_text: str,
    activity_text: str,
    all_satisfied: bool,
    missing: list[str],
) -> str:
    fallback = _fallback_ai_summary(client_name, service, status, all_satisfied, missing)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CASE_SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Client: {client_name} ({client_id})\nService: {service}\nStatus: {status}\n"
                        f"Documents:\n{checklist_text}\nRecent Activity:\n{activity_text}"
                    ),
                },
            ],
            max_tokens=200,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            logger.warning("Groq returned an empty case summary for %s; using template", client_id)
            return fallback
        return text
    except Exception as exc:
        logger.warning("Groq case summary call failed for %s: %s", client_id, exc)
        return fallback


def _format_report(
    client_id: str,
    client_name: str,
    service: str,
    status: str,
    checklist: list[RequiredDocumentStatus],
    recent_activity: list[str],
    ai_summary: str,
    recommended_action: str,
) -> str:
    lines = [
        "CLIENT CASE SUMMARY",
        "",
        f"Client: {client_id} ({client_name})",
        f"Service: {service}",
        f"Status: {status}",
        "",
        "Documents:",
    ]
    for item in checklist:
        mark = "✓" if item.satisfied else "✗"
        lines.append(f"{mark} {item.category}")

    lines += ["", "Recent Activity:"]
    if recent_activity:
        lines += [f"• {a}" for a in recent_activity]
    else:
        lines.append("• No recent activity recorded.")

    lines += ["", "AI Summary:", ai_summary, "", "Recommended Action:", recommended_action, "", "Human Review Required"]
    return "\n".join(lines)


def generate_case_summary(client_id: str) -> ClientCaseSummaryResult:
    """Generate an AI case summary for a client: service, onboarding status,
    required-documents checklist, recent activity, and a narrated AI summary
    + recommended action. Read-only -- never updates CRM records, creates
    tasks, or drafts emails."""
    try:
        client = crud.get_client(client_id)
        if client is None:
            log_action("generate_case_summary", f"client_id={client_id}", "not found")
            return ClientCaseSummaryResult(success=True, client_id=client_id, found=False)

        doc_check = check_required_documents(client_id)
        recent_activity = _gather_recent_activity(client_id)

        checklist_text = "\n".join(
            f"{'OK' if item.satisfied else 'MISSING'}: {item.category}" for item in doc_check.checklist
        )
        activity_text = "\n".join(recent_activity) or "None recorded."

        ai_summary = _generate_ai_summary(
            client_id,
            client.name,
            client.service,
            client.onboarding_status,
            checklist_text,
            activity_text,
            doc_check.all_satisfied,
            doc_check.missing_categories,
        )

        if doc_check.all_satisfied:
            recommended_action = "No further documents needed. Confirm final onboarding steps with the client."
        else:
            recommended_action = f"Request the following missing document(s): {', '.join(doc_check.missing_categories)}."

        report = _format_report(
            client_id,
            client.name,
            client.service,
            client.onboarding_status,
            doc_check.checklist,
            recent_activity,
            ai_summary,
            recommended_action,
        )

        log_action("generate_case_summary", f"client_id={client_id}", "summary generated")
        return ClientCaseSummaryResult(
            success=True,
            client_id=client_id,
            found=True,
            client_name=client.name,
            service=client.service,
            status=client.onboarding_status,
            checklist=doc_check.checklist,
            all_satisfied=doc_check.all_satisfied,
            recent_activity=recent_activity,
            ai_summary=ai_summary,
            recommended_action=recommended_action,
            report=report,
        )
    except Exception as exc:
        logger.warning("generate_case_summary failed for %s: %s", client_id, exc)
        log_action("generate_case_summary", f"client_id={client_id}", str(exc), status="error")
        return ClientCaseSummaryResult(success=False, client_id=client_id, error=str(exc))
