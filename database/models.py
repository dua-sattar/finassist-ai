"""SQLAlchemy models for the FinAssist AI mock CRM.

10 tables: the 7 from spec section 14 (clients, leads, documents,
document_extractions, tasks, followups, conversations) plus ai_action_log
(spec section 17's AI Actions view), and contact_submissions (Phase 19's
Contact Us intake).
"""

from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    service: Mapped[str]
    account_status: Mapped[str]
    onboarding_status: Mapped[str]
    assigned_advisor: Mapped[str]
    last_contact: Mapped[date]
    created_date: Mapped[date]


class Lead(Base):
    __tablename__ = "leads"

    lead_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    company: Mapped[str]
    service_interest: Mapped[str]
    engagement_level: Mapped[str]
    information_complete: Mapped[bool]
    source: Mapped[str]
    status: Mapped[str]
    created_date: Mapped[date]
    last_contact: Mapped[date]


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.client_id"), nullable=True)
    filename: Mapped[str]
    document_type: Mapped[str]
    status: Mapped[str]  # "Received" | "Invalid"
    uploaded_at: Mapped[datetime] = mapped_column(default=_utcnow)


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    extracted_json: Mapped[str] = mapped_column(Text)
    missing_fields_json: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.client_id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.lead_id"), nullable=True)
    task_type: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="Open")
    priority: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    due_date: Mapped[date | None] = mapped_column(nullable=True)


class Followup(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.client_id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.lead_id"), nullable=True)
    # For a recipient with no client/lead record yet (e.g. a contact-form
    # submitter who wasn't classified as a lead).
    to_email: Mapped[str | None] = mapped_column(nullable=True)
    channel: Mapped[str] = mapped_column(default="email")
    subject: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="Draft")  # Draft | Approved | Sent-simulated
    source: Mapped[str] = mapped_column(default="manual")  # manual | template | ai_generated
    # Only set for source="ai_generated" -- lets "Regenerate" redo the draft
    # with the same inputs without the user re-entering them.
    reason: Mapped[str | None] = mapped_column(nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(nullable=True)
    context: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(index=True)
    role: Mapped[str]  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class AIActionLog(Base):
    __tablename__ = "ai_action_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tool_name: Mapped[str]
    input_summary: Mapped[str] = mapped_column(Text)
    result_summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="success")  # success | error
    human_approval_status: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class PendingChange(Base):
    """A proposed client/lead field update awaiting human approval before
    it's applied (Phase 30's broader human-approval gate, extending the
    Followup Draft/Approved/Sent-simulated pattern from email drafts to CRM
    record updates). Only the chat agent's propose_client_update /
    propose_lead_update tools create these -- the deterministic workflows
    (document review, lead qualification), which are already triggered by
    an explicit human clicking a dedicated UI button, keep updating records
    immediately since that click *is* the human-in-the-loop step for those
    flows."""

    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str]  # "client" | "lead"
    entity_id: Mapped[str]
    field_changes_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="Pending")  # Pending | Approved | Rejected
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)


class MeetingSummary(Base):
    """A structured AI summary of a client/lead meeting or call (spec section
    25): raw notes an advisor pastes in, plus the AI-extracted key points,
    decisions, action items, and next steps (Phase 28)."""

    __tablename__ = "meeting_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.client_id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.lead_id"), nullable=True)
    raw_notes: Mapped[str] = mapped_column(Text)
    key_points_json: Mapped[str] = mapped_column(Text)
    decisions_json: Mapped[str] = mapped_column(Text)
    action_items_json: Mapped[str] = mapped_column(Text)
    next_steps_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class ContactSubmission(Base):
    """A public Contact Us form submission -- doubles as the "ticket" record
    for every category; gains a lead_id once AI classification identifies it
    as a potential lead (spec sections 17/18)."""

    __tablename__ = "contact_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    phone: Mapped[str | None] = mapped_column(nullable=True)
    subject: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    # Set after AI classification runs.
    category: Mapped[str | None] = mapped_column(nullable=True)
    priority: Mapped[str | None] = mapped_column(nullable=True)  # High | Medium | Low
    ai_suggested_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set only if category == "Potential Lead" and a Lead record was created.
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.lead_id"), nullable=True)
    status: Mapped[str] = mapped_column(default="New")  # New | Reviewed
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
