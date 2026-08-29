"""Static, non-AI email templates for the Email Center's Templates tab.

Templates are plain Python string.format() strings -- deterministic, no LLM
call, distinct from the AI Generate tab. Fill placeholders: {recipient_name},
{service}, {details}.
"""

EMAIL_TEMPLATES: dict[str, dict[str, str]] = {
    "Missing Document Request": {
        "subject": "Action Required: Missing Document for Your FinAssist AI Application",
        "body": (
            "Dear {recipient_name},\n\n"
            "As part of your onboarding with FinAssist AI, we still need the following "
            "from you: {details}.\n\n"
            "Please submit this at your earliest convenience so we can continue "
            "processing your application.\n\n"
            "Best regards,\nThe FinAssist AI Team"
        ),
    },
    "Welcome / Onboarding Started": {
        "subject": "Welcome to FinAssist AI",
        "body": (
            "Dear {recipient_name},\n\n"
            "Thank you for choosing FinAssist AI for your {service} needs. We're excited "
            "to get started. {details}\n\n"
            "Best regards,\nThe FinAssist AI Team"
        ),
    },
    "Lead Follow-up": {
        "subject": "Following Up on Your Interest in FinAssist AI",
        "body": (
            "Dear {recipient_name},\n\n"
            "Thank you for your interest in {service}. {details}\n\n"
            "We'd love to schedule a quick call to discuss your needs further.\n\n"
            "Best regards,\nThe FinAssist AI Team"
        ),
    },
    "Account Closure Confirmation": {
        "subject": "Your FinAssist AI Account Closure",
        "body": (
            "Dear {recipient_name},\n\n"
            "This confirms that your FinAssist AI account has been closed as requested. "
            "{details}\n\n"
            "Thank you for being a client. Please reach out if you have any questions.\n\n"
            "Best regards,\nThe FinAssist AI Team"
        ),
    },
    "General Check-in": {
        "subject": "Checking In",
        "body": (
            "Dear {recipient_name},\n\n"
            "We wanted to check in regarding {details}. Please let us know if there's "
            "anything we can help with.\n\n"
            "Best regards,\nThe FinAssist AI Team"
        ),
    },
}


def render_template(name: str, recipient_name: str, service: str = "", details: str = "") -> tuple[str, str]:
    """Fill a template's placeholders. Returns (subject, body)."""
    template = EMAIL_TEMPLATES[name]
    subject = template["subject"].format(recipient_name=recipient_name, service=service, details=details)
    body = template["body"].format(recipient_name=recipient_name, service=service, details=details)
    return subject, body
