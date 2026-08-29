"""classify_contact_submission tool -- AI classification for the Contact Us
form (spec sections 17/18): category, priority, a guessed service interest
(used only if the submission looks like a potential lead), and a suggested
reply for a human advisor to review before sending."""

import logging
import os

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)

CATEGORIES = [
    "General Inquiry",
    "Client Support",
    "Onboarding",
    "Document Request",
    "Billing",
    "Technical Issue",
    "Potential Lead",
    "Other",
]
PRIORITIES = ["High", "Medium", "Low"]
KNOWN_SERVICES = [
    "Retirement Planning",
    "Investment Advisory Consultation",
    "Tax Planning Consultation",
    "Estate Planning Guidance",
    "Business Financial Consulting",
]

CLASSIFY_SYSTEM_PROMPT = (
    "You are FinAssist AI's contact-intake classifier. Given a contact form submission, "
    "respond in EXACTLY this format (no extra commentary before or after):\n"
    "Category: <one of General Inquiry, Client Support, Onboarding, Document Request, "
    "Billing, Technical Issue, Potential Lead, Other>\n"
    "Priority: <High, Medium, or Low>\n"
    "ServiceInterest: <one of Retirement Planning, Investment Advisory Consultation, "
    "Tax Planning Consultation, Estate Planning Guidance, Business Financial Consulting, "
    "or None>\n"
    "Response: <a brief, professional 2-4 sentence suggested reply to the submitter, for a "
    "human advisor to review before sending -- do not invent company policy or make "
    "financial promises>\n\n"
    "Use 'Potential Lead' only when the message expresses genuine interest in becoming a "
    "new client for one of FinAssist AI's services, not for support/billing/general questions."
)

_SERVICE_KEYWORDS: dict[str, list[str]] = {
    "Tax Planning Consultation": ["tax"],
    "Retirement Planning": ["retire", "retirement", "401k", "pension"],
    "Estate Planning Guidance": ["estate", "will", "trust", "inheritance"],
    "Business Financial Consulting": ["business", "small business", "llc", "payroll"],
    "Investment Advisory Consultation": ["invest", "portfolio", "stocks", "advisory"],
}

FALLBACK_RESPONSE = (
    "Thank you for contacting FinAssist AI. A member of our team has received your message "
    "and will follow up with you shortly."
)


class ClassificationResult(BaseModel):
    success: bool
    category: str
    priority: str
    service_interest: str | None = None
    suggested_response: str = ""
    error: str | None = None


class CreateContactSubmissionResult(BaseModel):
    success: bool
    submission_id: int | None = None
    error: str | None = None


def create_contact_submission(
    name: str, email: str, subject: str, message: str, phone: str | None = None
) -> CreateContactSubmissionResult:
    """Save a raw Contact Us form submission. This doubles as the "ticket"
    record for every category, before AI classification runs."""
    try:
        submission = crud.create_contact_submission(name=name, email=email, phone=phone, subject=subject, message=message)
        log_action("create_contact_submission", f"name={name!r} subject={subject!r}", f"submission_id={submission.id}")
        return CreateContactSubmissionResult(success=True, submission_id=submission.id)
    except Exception as exc:
        logger.warning("create_contact_submission failed for %r: %s", name, exc)
        log_action("create_contact_submission", f"name={name!r}", str(exc), status="error")
        return CreateContactSubmissionResult(success=False, error=str(exc))


class UpdateContactSubmissionResult(BaseModel):
    success: bool
    submission_id: int
    error: str | None = None


def update_contact_submission(submission_id: int, **fields) -> UpdateContactSubmissionResult:
    """Apply classification results (or a linked lead_id) to a submission."""
    try:
        updated = crud.update_contact_submission(submission_id, **fields)
        if updated is None:
            return UpdateContactSubmissionResult(success=False, submission_id=submission_id, error="Submission not found.")
        log_action("update_contact_submission", f"submission_id={submission_id} fields={fields}", "updated")
        return UpdateContactSubmissionResult(success=True, submission_id=submission_id)
    except Exception as exc:
        logger.warning("update_contact_submission failed for %s: %s", submission_id, exc)
        log_action("update_contact_submission", f"submission_id={submission_id}", str(exc), status="error")
        return UpdateContactSubmissionResult(success=False, submission_id=submission_id, error=str(exc))


def _guess_service_interest(text: str) -> str | None:
    lowered = text.lower()
    for service, keywords in _SERVICE_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return service
    return None


def _fallback_classification(subject: str, message: str) -> ClassificationResult:
    return ClassificationResult(
        success=True,
        category="General Inquiry",
        priority="Medium",
        service_interest=_guess_service_interest(f"{subject} {message}"),
        suggested_response=FALLBACK_RESPONSE,
    )


def _parse_classification(text: str) -> dict[str, str]:
    """Parse the 'Category: ...\\nPriority: ...\\nServiceInterest: ...\\nResponse: ...'
    format. Response may span multiple lines, so it's accumulated until the
    next known key or end of text."""
    fields: dict[str, str] = {}
    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_key:
            fields[current_key] = "\n".join(buffer).strip()

    for line in text.splitlines():
        matched = False
        for key in ("category", "priority", "serviceinterest", "response"):
            if line.strip().lower().startswith(f"{key}:"):
                flush()
                current_key = key
                buffer = [line.split(":", 1)[1].strip()]
                matched = True
                break
        if not matched and current_key:
            buffer.append(line)
    flush()
    return fields


def classify_contact_submission(subject: str, message: str) -> ClassificationResult:
    """Classify a contact-form submission into a category + priority, guess a
    likely service interest, and draft a suggested reply -- via Groq, with a
    deterministic fallback if no API key or the call fails."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        result = _fallback_classification(subject, message)
        log_action("classify_contact_submission", f"subject={subject!r}", "no API key, used fallback")
        return result

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Subject: {subject}\nMessage: {message}"},
            ],
            max_tokens=300,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("empty response from Groq")

        parsed = _parse_classification(text)
        category = parsed.get("category", "")
        if category not in CATEGORIES:
            category = "Other"
        priority = parsed.get("priority", "")
        if priority not in PRIORITIES:
            priority = "Medium"
        service_interest = parsed.get("serviceinterest")
        if service_interest not in KNOWN_SERVICES:
            service_interest = _guess_service_interest(f"{subject} {message}")
        suggested_response = parsed.get("response") or FALLBACK_RESPONSE

        log_action("classify_contact_submission", f"subject={subject!r}", f"category={category} priority={priority}")
        return ClassificationResult(
            success=True,
            category=category,
            priority=priority,
            service_interest=service_interest,
            suggested_response=suggested_response,
        )
    except Exception as exc:
        logger.warning("classify_contact_submission failed, using fallback: %s", exc)
        result = _fallback_classification(subject, message)
        log_action(
            "classify_contact_submission", f"subject={subject!r}", f"error, used fallback: {exc}", status="error"
        )
        return result
