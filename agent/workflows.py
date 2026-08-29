"""Deterministic multi-step business workflows (spec sections 12-13), built
by orchestrating the Phase 7 tools directly -- distinct from the free-form
LangGraph chat agent (Phase 8/9), which decides its own tool sequence. A
dedicated UI action (Phase 14's Document Analysis / Lead Management pages)
calls these directly so each process runs the same way every time.
"""

import logging
import os
from pathlib import Path

from pydantic import BaseModel

from document_processing.schemas import REQUIRED_DOCUMENT_CATEGORIES
from tools.contact_tools import classify_contact_submission, create_contact_submission, update_contact_submission
from tools.crm_tools import create_lead, get_client, get_lead, update_client, update_lead
from tools.document_tools import (
    AnalyzeDocumentResult,
    RequiredDocumentStatus,
    analyze_document,
    check_required_documents,
)
from tools.email_tools import generate_followup_email
from tools.task_tools import create_followup_task

logger = logging.getLogger(__name__)


class DocumentReviewResult(BaseModel):
    success: bool
    client_id: str
    found: bool = False
    analysis: AnalyzeDocumentResult | None = None  # set only if a new document was analyzed this call
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

    analysis: AnalyzeDocumentResult | None = None
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
        analysis=analysis,
        checklist=check.checklist,
        all_satisfied=check.all_satisfied,
        missing_categories=check.missing_categories,
        onboarding_status=new_status,
        task_id=task_id,
        followup_id=followup_id,
        report=report,
    )


# --- Lead qualification (spec section 13) -----------------------------------

KNOWN_SERVICES = {
    "Retirement Planning",
    "Investment Advisory Consultation",
    "Tax Planning Consultation",
    "Estate Planning Guidance",
    "Business Financial Consulting",
}

# Transparent, documented point system -- NOT a real risk/suitability
# assessment (spec sections 13/26). engagement_level contributes 0-2,
# information_complete contributes 0-1, a recognized service_interest
# contributes 0-1. Total 0-4: >=3 High, ==2 Medium, <=1 Low.
ENGAGEMENT_POINTS = {"High": 2, "Medium": 1, "Low": 0}


class LeadQualificationResult(BaseModel):
    success: bool
    lead_id: str
    found: bool = False
    priority: str | None = None  # High | Medium | Low
    score: int | None = None
    reasons: list[str] = []
    new_status: str | None = None
    task_id: int | None = None
    followup_id: int | None = None
    report: str = ""
    error: str | None = None


def _priority_from_score(score: int) -> str:
    if score >= 3:
        return "High"
    if score == 2:
        return "Medium"
    return "Low"


def _recommended_action_for(priority: str) -> str:
    if priority == "High":
        return "Schedule advisor follow-up."
    if priority == "Medium":
        return "Advisor to follow up within the standard timeframe; request any missing information."
    return "Add to the nurture sequence; low-touch follow-up only."


def _format_lead_report(priority: str, reasons: list[str], recommended_action: str) -> str:
    lines = [f"Lead Priority: {priority.upper()}", "", "Reason:"]
    lines += [f"- {r}" for r in reasons]
    lines += [
        "",
        "Recommended Action:",
        recommended_action,
        "",
        "Human review required before finalizing lead priority or sending any communication.",
    ]
    return "\n".join(lines)


def qualify_lead(lead_id: str) -> LeadQualificationResult:
    """Assign a transparent, rule-based priority (High/Medium/Low) to a lead,
    explain the reasoning, update the CRM, and prepare a follow-up task and
    draft email. Not a real financial risk or suitability assessment."""
    lead_result = get_lead(lead_id)
    if not lead_result.success:
        return LeadQualificationResult(success=False, lead_id=lead_id, error=lead_result.error)
    if not lead_result.found:
        logger.info("qualify_lead: lead %s not found", lead_id)
        return LeadQualificationResult(success=True, lead_id=lead_id, found=False)

    reasons: list[str] = []
    score = 0

    service_relevant = lead_result.service_interest in KNOWN_SERVICES
    if service_relevant:
        reasons.append(f"Relevant service interest ({lead_result.service_interest})")
        score += 1
    else:
        reasons.append(f"Service interest ({lead_result.service_interest}) is outside our standard offerings")

    if lead_result.information_complete:
        reasons.append("Complete information provided")
        score += 1
    else:
        reasons.append("Missing required lead information")

    engagement = lead_result.engagement_level or "Low"
    score += ENGAGEMENT_POINTS.get(engagement, 0)
    reasons.append(f"{engagement} engagement level")

    priority = _priority_from_score(score)
    recommended_action = _recommended_action_for(priority)

    new_status = "Qualified" if priority in ("High", "Medium") else "Unqualified"
    update_lead(lead_id, status=new_status)

    task = create_followup_task(
        description=f"Follow up with lead {lead_id} ({priority} priority): {recommended_action}",
        task_type="lead_follow_up",
        lead_id=lead_id,
        priority=priority,
    )

    email = generate_followup_email(
        reason=f"{priority}-priority lead follow-up",
        recipient_name=lead_result.name or lead_id,
        context=f"Interested in {lead_result.service_interest}. {recommended_action}",
        lead_id=lead_id,
    )

    report = _format_lead_report(priority, reasons, recommended_action)

    return LeadQualificationResult(
        success=True,
        lead_id=lead_id,
        found=True,
        priority=priority,
        score=score,
        reasons=reasons,
        new_status=new_status,
        task_id=task.task_id,
        followup_id=email.followup_id,
        report=report,
    )


# --- Contact Us intake (spec sections 17-18) ---------------------------------


class ContactSubmissionResult(BaseModel):
    success: bool
    submission_id: int | None = None
    category: str | None = None
    priority: str | None = None
    suggested_response: str | None = None
    created_lead_id: str | None = None
    lead_qualification: LeadQualificationResult | None = None
    task_id: int | None = None
    error: str | None = None


def process_contact_submission(
    name: str, email: str, subject: str, message: str, phone: str | None = None
) -> ContactSubmissionResult:
    """Full contact-intake workflow (spec sections 17/18): record the
    submission (it doubles as the ticket), classify it via AI, and -- only
    if it looks like a genuine new-business inquiry -- create a real Lead
    record and run it straight through Phase 11's qualify_lead, so a
    Contact Us submission gets the exact same CRM update + follow-up task +
    draft email a manually-added lead would."""
    created = create_contact_submission(name=name, email=email, subject=subject, message=message, phone=phone)
    if not created.success:
        return ContactSubmissionResult(success=False, error=created.error)

    submission_id = created.submission_id
    classification = classify_contact_submission(subject, message)

    update_contact_submission(
        submission_id,
        category=classification.category,
        priority=classification.priority,
        ai_suggested_response=classification.suggested_response,
    )

    result = ContactSubmissionResult(
        success=True,
        submission_id=submission_id,
        category=classification.category,
        priority=classification.priority,
        suggested_response=classification.suggested_response,
    )

    if classification.category == "Potential Lead":
        lead = create_lead(
            name=name,
            email=email,
            service_interest=classification.service_interest or "Retirement Planning",
            engagement_level="Medium",
            information_complete=bool(phone) and bool(classification.service_interest),
            source="Contact Form",
        )
        if lead.success:
            update_contact_submission(submission_id, lead_id=lead.lead_id)
            result.created_lead_id = lead.lead_id
            result.lead_qualification = qualify_lead(lead.lead_id)
        else:
            logger.warning("process_contact_submission: lead creation failed: %s", lead.error)
    else:
        task = create_followup_task(
            description=f"Review contact form ticket #{submission_id} ({classification.category}): {subject}",
            task_type="contact_ticket",
            priority=classification.priority,
        )
        if task.success:
            result.task_id = task.task_id

    return result


# --- Multi-Document Analysis (spec section 8) --------------------------------

_NAME_FIELD_KEYS = ("client_name", "full_name", "recipient_name")

_MULTI_DOC_SYSTEM_PROMPT = (
    "You are FinAssist AI's document-review assistant. You are given the extracted "
    "fields from multiple documents uploaded together for one client. Write a brief, "
    "neutral 'AI Observation' (2-4 sentences) noting only what is actually present in "
    "the data: relevant extracted values, and any conflicting information or "
    "inconsistent dates/client details visible across the documents. Do not invent "
    "facts. Do NOT make any approval, rejection, or fraud determination -- only "
    "describe what you observe. If nothing looks inconsistent, say so plainly."
)


class DocumentBatchItem(BaseModel):
    filename: str
    success: bool
    document_type: str
    extracted_fields: dict = {}
    missing_fields: list[str] = []
    error: str | None = None


class MultiDocumentAnalysisResult(BaseModel):
    success: bool
    client_id: str
    found: bool = False
    batch_items: list[DocumentBatchItem] = []
    missing_categories: list[str] = []
    client_id_mismatch: bool = False
    client_ids_seen: list[str] = []
    name_mismatch: bool = False
    names_seen: list[str] = []
    overall_status: str = ""
    ai_observation: str = ""
    recommended_action: str = ""
    report: str = ""
    error: str | None = None


def _fallback_multi_doc_observation(
    batch_items: list[DocumentBatchItem],
    missing_categories: list[str],
    client_id_mismatch: bool,
    client_ids_seen: list[str],
    name_mismatch: bool,
    names_seen: list[str],
) -> str:
    parts = [f"{len(batch_items)} document(s) analyzed."]
    if client_id_mismatch:
        parts.append(f"Client ID mismatch across documents: {', '.join(client_ids_seen)}.")
    if name_mismatch:
        parts.append(f"Client name mismatch across documents: {', '.join(names_seen)}.")
    if missing_categories:
        parts.append(f"Missing categories in this batch: {', '.join(missing_categories)}.")
    else:
        parts.append("All required categories are represented in this batch.")
    return " ".join(parts)


def _generate_multi_doc_observation(
    client_id: str,
    batch_items: list[DocumentBatchItem],
    missing_categories: list[str],
    client_id_mismatch: bool,
    client_ids_seen: list[str],
    name_mismatch: bool,
    names_seen: list[str],
) -> str:
    fallback = _fallback_multi_doc_observation(
        batch_items, missing_categories, client_id_mismatch, client_ids_seen, name_mismatch, names_seen
    )
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        doc_summaries = "\n".join(
            f"- {item.filename} ({item.document_type}): {item.extracted_fields}"
            for item in batch_items
            if item.success
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _MULTI_DOC_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Client: {client_id}\nDocuments:\n{doc_summaries}\n\n"
                        f"Missing categories in this batch: {missing_categories or 'none'}\n"
                        f"Client ID values seen: {client_ids_seen}\n"
                        f"Client name values seen: {names_seen}"
                    ),
                },
            ],
            max_tokens=250,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or fallback
    except Exception as exc:
        logger.warning("Groq multi-document observation call failed for %s: %s", client_id, exc)
        return fallback


def _format_multi_doc_report(
    client_id: str,
    client_name: str,
    batch_items: list[DocumentBatchItem],
    missing_categories: list[str],
    client_id_mismatch: bool,
    client_ids_seen: list[str],
    name_mismatch: bool,
    names_seen: list[str],
    overall_status: str,
    ai_observation: str,
    recommended_action: str,
) -> str:
    lines = [
        "MULTI-DOCUMENT ANALYSIS",
        "",
        f"Client: {client_id} ({client_name})",
        f"Documents Analyzed: {len(batch_items)}",
        "",
    ]
    for item in batch_items:
        mark = "✓" if item.success else "✗"
        detail = item.document_type if item.success else f"failed: {item.error}"
        lines.append(f"{mark} {item.filename} ({detail})")

    lines += ["", "Category Coverage:"]
    for category in REQUIRED_DOCUMENT_CATEGORIES:
        mark = "✗" if category in missing_categories else "✓"
        lines.append(f"{mark} {category}")

    lines += ["", "Consistency Check:"]
    if client_id_mismatch:
        lines.append(f"✗ Client ID mismatch: {', '.join(client_ids_seen)}")
    else:
        lines.append(f"✓ Client ID consistent ({client_ids_seen[0] if client_ids_seen else 'n/a'})")
    if name_mismatch:
        lines.append(f"✗ Client name mismatch: {', '.join(names_seen)}")
    else:
        lines.append(f"✓ Client name consistent ({names_seen[0] if names_seen else 'n/a'})")

    lines += [
        "",
        f"Overall Status: {overall_status}",
        "",
        "AI Observation:",
        ai_observation,
        "",
        "Recommended Action:",
        recommended_action,
        "",
        "Human Review Required",
    ]
    return "\n".join(lines)


def analyze_multiple_documents(client_id: str, files: list[tuple[bytes, str]]) -> MultiDocumentAnalysisResult:
    """Upload and analyze multiple documents together for one client: run
    each through the Phase 3 extraction pipeline, check category coverage
    and client ID/name consistency across the batch, and get an AI
    observation grounded only in what was actually extracted. Never makes
    an approval, rejection, or fraud determination -- always ends with a
    human-review notice."""
    client_result = get_client(client_id)
    if not client_result.success:
        return MultiDocumentAnalysisResult(success=False, client_id=client_id, error=client_result.error)
    if not client_result.found:
        return MultiDocumentAnalysisResult(success=True, client_id=client_id, found=False)

    batch_items: list[DocumentBatchItem] = []
    document_types_seen: set[str] = set()
    client_ids_seen: set[str] = set()
    names_seen: set[str] = set()

    for file_bytes, filename in files:
        analysis = analyze_document(file_bytes, client_id=client_id, filename=filename)
        batch_items.append(
            DocumentBatchItem(
                filename=filename,
                success=analysis.success,
                document_type=analysis.document_type,
                extracted_fields=analysis.extracted_fields,
                missing_fields=analysis.missing_fields,
                error=analysis.error,
            )
        )
        if analysis.success:
            document_types_seen.add(analysis.document_type)
            cid = analysis.extracted_fields.get("client_id")
            if cid:
                client_ids_seen.add(cid)
            for key in _NAME_FIELD_KEYS:
                name = analysis.extracted_fields.get(key)
                if name:
                    names_seen.add(name)
                    break

    missing_categories = [
        category
        for category, doc_types in REQUIRED_DOCUMENT_CATEGORIES.items()
        if not any(dt in document_types_seen for dt in doc_types)
    ]

    client_id_mismatch = len(client_ids_seen) > 1
    name_mismatch = len(names_seen) > 1
    overall_status = "Complete" if not missing_categories else "Partial"

    ai_observation = _generate_multi_doc_observation(
        client_id,
        batch_items,
        missing_categories,
        client_id_mismatch,
        sorted(client_ids_seen),
        name_mismatch,
        sorted(names_seen),
    )

    if client_id_mismatch or name_mismatch:
        recommended_action = "Documents reference different client identities -- verify with the client before proceeding."
    elif missing_categories:
        recommended_action = f"Request the following missing document(s): {', '.join(missing_categories)}."
    else:
        recommended_action = "All document categories are present in this batch. Confirm details with the client before finalizing."

    report = _format_multi_doc_report(
        client_id,
        client_result.name or client_id,
        batch_items,
        missing_categories,
        client_id_mismatch,
        sorted(client_ids_seen),
        name_mismatch,
        sorted(names_seen),
        overall_status,
        ai_observation,
        recommended_action,
    )

    return MultiDocumentAnalysisResult(
        success=True,
        client_id=client_id,
        found=True,
        batch_items=batch_items,
        missing_categories=missing_categories,
        client_id_mismatch=client_id_mismatch,
        client_ids_seen=sorted(client_ids_seen),
        name_mismatch=name_mismatch,
        names_seen=sorted(names_seen),
        overall_status=overall_status,
        ai_observation=ai_observation,
        recommended_action=recommended_action,
        report=report,
    )
