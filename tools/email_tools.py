"""generate_followup_email tool -- drafts a follow-up email via Groq (with a
templated fallback), and saves it as a Draft followup. Never sends anything:
the followup only leaves Draft status via database.crud.approve_followup,
which is a separate, explicit human action (see Phase 12)."""

import logging
import os

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)

EMAIL_SYSTEM_PROMPT = (
    "You are drafting a professional follow-up email on behalf of a FinAssist AI "
    "advisor. Be concise, warm, and clear about what the client or lead needs to "
    "do next. Do not make promises about financial outcomes, investment returns, "
    "or approval decisions. Sign off as 'The FinAssist AI Team'. Respond with a "
    "first line starting with 'Subject:' followed by the email body."
)


class GenerateFollowupEmailResult(BaseModel):
    success: bool
    followup_id: int | None = None
    subject: str = ""
    body: str = ""
    status: str = "Draft"
    error: str | None = None


def _draft_email(reason: str, recipient_name: str, context: str) -> tuple[str, str]:
    fallback_subject = f"Follow-up: {reason}"
    fallback_body = (
        f"Dear {recipient_name},\n\n"
        f"We're following up regarding: {reason}. {context}\n\n"
        "Please let us know if you have any questions.\n\n"
        "Best regards,\nThe FinAssist AI Team"
    )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback_subject, fallback_body

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EMAIL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Recipient: {recipient_name}\nReason: {reason}\nContext: {context}",
                },
            ],
            max_tokens=300,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            logger.warning("Groq returned an empty email draft for %s; using template", recipient_name)
            return fallback_subject, fallback_body
        if text.lower().startswith("subject:"):
            subject_line, _, body = text.partition("\n")
            subject = subject_line.split(":", 1)[1].strip()
            return subject, body.strip()
        return fallback_subject, text
    except Exception as exc:
        logger.warning("Groq email draft failed, using template: %s", exc)
        return fallback_subject, fallback_body


def generate_followup_email(
    reason: str,
    recipient_name: str,
    context: str = "",
    client_id: str | None = None,
    lead_id: str | None = None,
) -> GenerateFollowupEmailResult:
    """Draft a follow-up email. Always saved as Draft, pending human approval
    -- never sent automatically."""
    try:
        subject, body = _draft_email(reason, recipient_name, context)
        followup = crud.create_followup(subject=subject, body=body, client_id=client_id, lead_id=lead_id)

        log_action(
            "generate_followup_email",
            f"client_id={client_id} lead_id={lead_id} reason={reason!r}",
            f"followup_id={followup.id}",
            human_approval_status="Pending",
        )
        return GenerateFollowupEmailResult(
            success=True, followup_id=followup.id, subject=subject, body=body, status=followup.status
        )
    except Exception as exc:
        logger.warning("generate_followup_email failed: %s", exc)
        log_action("generate_followup_email", f"client_id={client_id} lead_id={lead_id}", str(exc), status="error")
        return GenerateFollowupEmailResult(success=False, error=str(exc))
