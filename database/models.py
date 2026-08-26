"""SQLAlchemy models for the FinAssist AI mock CRM.

8 tables: the 7 from spec section 14 (clients, leads, documents,
document_extractions, tasks, followups, conversations) plus ai_action_log,
which backs the "AI Actions" dashboard view from spec section 17.
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
    channel: Mapped[str] = mapped_column(default="email")
    subject: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="Draft")  # Draft | Approved | Sent-simulated
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
