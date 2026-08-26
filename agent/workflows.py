"""Deterministic multi-step business workflows (spec sections 12-13), built
by orchestrating the Phase 7 tools directly -- distinct from the free-form
LangGraph chat agent (Phase 8/9), which decides its own tool sequence. A
dedicated UI action (Phase 14's Document Analysis page) calls these
directly so the process runs the same way every time.
"""

import logging
from pathlib import Path

from pydantic import BaseModel

from tools.crm_tools import get_client, update_client
from tools.document_tools import RequiredDocumentStatus, analyze_document, check_required_documents
from tools.email_tools import generate_followup_email
from tools.task_tools import create_followup_task

logger = logging.getLogger(__name__)


class DocumentReviewResult(BaseModel):
    success: bool
    client_id: str
    found: bool = False
    checklist: list[RequiredDocumentStatus] = []
    all_satisfied: bool = False
    missing_categories: list[str] = []
    onboarding_status: str | None = None
    task_id: int | None = None
    followup_id: int | None = None
    report: str = ""
    error: str | None = None


def _format_report(
    client_id: str,
    client_name: str,
    checklist: list[RequiredDocumentStatus],
    all_satisfied: bool,
    missing: list[str],
) -> str:
    lines = [f"Client: {client_id} ({client_name})", "", "Document Review", ""]
    for item in checklist:
        mark = "✓" if item.satisfied else "✗"
        lines.append(f"{mark} {item.category}")

    status = "Complete" if all_satisfied else "Documents Pending"
    lines += ["", f"Status: {status}", "", "Recommended Next Action:"]

    if all_satisfied:
        lines.append("None -- onboarding requirements are fully satisfied. Confirm with the client if appropriate.")
    else:
        lines.append(f"Request the following from the client: {', '.join(missing)}.")

    lines += ["", "Human review required before sending any communication or finalizing this status."]
    return "\n".join(lines)


def review_client_documents(
    client_id: str,
    new_document_source: str | Path | bytes | None = None,
    new_document_filename: str | None = None,
) -> DocumentReviewResult:
    """Run the full client document-review workflow:
    identify client -> (optionally analyze a newly uploaded document) ->
    check required documents -> update onboarding status -> create a
    follow-up task and draft a request email if anything is missing.
    """
    client_result = get_client(client_id)
    if not client_result.success:
        return DocumentReviewResult(success=False, client_id=client_id, error=client_result.error)
    if not client_result.found:
        logger.info("review_client_documents: client %s not found", client_id)
        return DocumentReviewResult(success=True, client_id=client_id, found=False)

    if new_document_source is not None:
        analysis = analyze_document(new_document_source, client_id=client_id, filename=new_document_filename)
        if not analysis.success:
            logger.warning("New document analysis failed for %s: %s", client_id, analysis.error)

    check = check_required_documents(client_id)
    if not check.success:
        return DocumentReviewResult(success=False, client_id=client_id, found=True, error=check.error)

    new_status = "Complete" if check.all_satisfied else "Documents Pending"
    update_client(client_id, onboarding_status=new_status)

    task_id: int | None = None
    followup_id: int | None = None
    if not check.all_satisfied:
        missing_str = ", ".join(check.missing_categories)

        task = create_followup_task(
            description=f"Request missing onboarding documents from {client_id}: {missing_str}",
            task_type="document_follow_up",
            client_id=client_id,
            priority="High",
        )
        task_id = task.task_id

        email = generate_followup_email(
            reason="Missing onboarding documents",
            recipient_name=client_result.name or client_id,
            context=f"The following documents are still needed: {missing_str}.",
            client_id=client_id,
        )
        followup_id = email.followup_id

    report = _format_report(
        client_id, client_result.name or client_id, check.checklist, check.all_satisfied, check.missing_categories
    )

    return DocumentReviewResult(
        success=True,
        client_id=client_id,
        found=True,
        checklist=check.checklist,
        all_satisfied=check.all_satisfied,
        missing_categories=check.missing_categories,
        onboarding_status=new_status,
        task_id=task_id,
        followup_id=followup_id,
        report=report,
    )
