"""Typed CRUD functions for the FinAssist AI mock CRM.

This is the only module other code (tools/, agent/, app/) should use to
touch the database -- no other module should open a SQLAlchemy session
directly.
"""

import json
import logging
from contextlib import contextmanager
from datetime import date, datetime, timezone

from sqlalchemy import func, or_

from database.database import SessionLocal
from database.models import (
    AIActionLog,
    Client,
    ContactSubmission,
    Conversation,
    Document,
    DocumentExtraction,
    Followup,
    Lead,
    Task,
)

logger = logging.getLogger(__name__)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- Clients ---------------------------------------------------------------


def get_client(client_id: str) -> Client | None:
    with session_scope() as session:
        return session.get(Client, client_id)


def list_clients(account_status: str | None = None) -> list[Client]:
    with session_scope() as session:
        query = session.query(Client)
        if account_status:
            query = query.filter(Client.account_status == account_status)
        return query.all()


def search_clients(query: str, limit: int = 10) -> list[Client]:
    """Case-insensitive substring match across client_id, name, and email."""
    needle = f"%{query.strip().lower()}%"
    with session_scope() as session:
        return (
            session.query(Client)
            .filter(
                or_(
                    func.lower(Client.client_id).like(needle),
                    func.lower(Client.name).like(needle),
                    func.lower(Client.email).like(needle),
                )
            )
            .limit(limit)
            .all()
        )


def update_client(client_id: str, **fields) -> Client | None:
    with session_scope() as session:
        client = session.get(Client, client_id)
        if client is None:
            logger.warning("update_client: client %s not found", client_id)
            return None
        for key, value in fields.items():
            setattr(client, key, value)
        return client


# --- Leads -------------------------------------------------------------


def next_lead_id() -> str:
    """Generate the next unused lead_id (e.g. "L1041"), continuing the
    seeded L1001... numbering."""
    with session_scope() as session:
        existing = [lead_id for (lead_id,) in session.query(Lead.lead_id).all()]
    numbers = [int(lid[1:]) for lid in existing if lid.startswith("L") and lid[1:].isdigit()]
    next_number = (max(numbers) + 1) if numbers else 1001
    return f"L{next_number}"


def create_lead(
    lead_id: str,
    name: str,
    email: str,
    company: str,
    service_interest: str,
    engagement_level: str,
    information_complete: bool,
    source: str,
    status: str = "New",
) -> Lead:
    with session_scope() as session:
        lead = Lead(
            lead_id=lead_id,
            name=name,
            email=email,
            company=company,
            service_interest=service_interest,
            engagement_level=engagement_level,
            information_complete=information_complete,
            source=source,
            status=status,
            created_date=date.today(),
            last_contact=date.today(),
        )
        session.add(lead)
        session.flush()
        return lead


def get_lead(lead_id: str) -> Lead | None:
    with session_scope() as session:
        return session.get(Lead, lead_id)


def list_leads(status: str | None = None) -> list[Lead]:
    with session_scope() as session:
        query = session.query(Lead)
        if status:
            query = query.filter(Lead.status == status)
        return query.all()


def search_leads(query: str, limit: int = 10) -> list[Lead]:
    """Case-insensitive substring match across lead_id, name, company, and email."""
    needle = f"%{query.strip().lower()}%"
    with session_scope() as session:
        return (
            session.query(Lead)
            .filter(
                or_(
                    func.lower(Lead.lead_id).like(needle),
                    func.lower(Lead.name).like(needle),
                    func.lower(Lead.company).like(needle),
                    func.lower(Lead.email).like(needle),
                )
            )
            .limit(limit)
            .all()
        )


def update_lead(lead_id: str, **fields) -> Lead | None:
    with session_scope() as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            logger.warning("update_lead: lead %s not found", lead_id)
            return None
        for key, value in fields.items():
            setattr(lead, key, value)
        return lead


# --- Documents ---------------------------------------------------------


def add_document(client_id: str | None, filename: str, document_type: str, status: str) -> Document:
    with session_scope() as session:
        doc = Document(client_id=client_id, filename=filename, document_type=document_type, status=status)
        session.add(doc)
        session.flush()
        return doc


def list_documents_for_client(client_id: str) -> list[Document]:
    with session_scope() as session:
        return session.query(Document).filter(Document.client_id == client_id).all()


def list_documents_with_extractions_for_client(client_id: str) -> list[tuple[Document, DocumentExtraction | None]]:
    """Every document on file for a client, paired with its most recent
    extraction (None if extraction failed or hasn't run). Used by anomaly
    detection to inspect documents already stored, not just a fresh upload
    batch."""
    with session_scope() as session:
        docs = (
            session.query(Document)
            .filter(Document.client_id == client_id)
            .order_by(Document.uploaded_at)
            .all()
        )
        results = []
        for doc in docs:
            extraction = (
                session.query(DocumentExtraction)
                .filter(DocumentExtraction.document_id == doc.id)
                .order_by(DocumentExtraction.id.desc())
                .first()
            )
            results.append((doc, extraction))
        return results


def add_document_extraction(
    document_id: int, extracted_fields: dict, missing_fields: list[str], summary: str
) -> DocumentExtraction:
    with session_scope() as session:
        extraction = DocumentExtraction(
            document_id=document_id,
            extracted_json=json.dumps(extracted_fields, default=str),
            missing_fields_json=json.dumps(missing_fields),
            summary=summary,
        )
        session.add(extraction)
        session.flush()
        return extraction


def search_documents(query: str, limit: int = 10) -> list[Document]:
    """Case-insensitive substring match across filename and document_type."""
    needle = f"%{query.strip().lower()}%"
    with session_scope() as session:
        return (
            session.query(Document)
            .filter(or_(func.lower(Document.filename).like(needle), func.lower(Document.document_type).like(needle)))
            .order_by(Document.id.desc())
            .limit(limit)
            .all()
        )


def search_document_extractions(query: str, limit: int = 10) -> list[tuple[DocumentExtraction, Document]]:
    """Case-insensitive substring match over AI-generated document summaries,
    joined with the owning Document for display context."""
    needle = f"%{query.strip().lower()}%"
    with session_scope() as session:
        return (
            session.query(DocumentExtraction, Document)
            .join(Document, DocumentExtraction.document_id == Document.id)
            .filter(func.lower(DocumentExtraction.summary).like(needle))
            .order_by(DocumentExtraction.id.desc())
            .limit(limit)
            .all()
        )


# --- Tasks ---------------------------------------------------------------


def create_task(
    task_type: str,
    description: str,
    client_id: str | None = None,
    lead_id: str | None = None,
    priority: str | None = None,
    due_date: date | None = None,
) -> Task:
    with session_scope() as session:
        task = Task(
            task_type=task_type,
            description=description,
            client_id=client_id,
            lead_id=lead_id,
            priority=priority,
            due_date=due_date,
        )
        session.add(task)
        session.flush()
        return task


def list_open_tasks(client_id: str | None = None, lead_id: str | None = None) -> list[Task]:
    with session_scope() as session:
        query = session.query(Task).filter(Task.status == "Open")
        if client_id:
            query = query.filter(Task.client_id == client_id)
        if lead_id:
            query = query.filter(Task.lead_id == lead_id)
        return query.all()


def list_tasks(status: str | None = None, client_id: str | None = None, lead_id: str | None = None) -> list[Task]:
    """List tasks regardless of status (unlike list_open_tasks) -- needed
    for the Completed / overdue / due-today / upcoming groupings."""
    with session_scope() as session:
        query = session.query(Task).order_by(Task.id.desc())
        if status:
            query = query.filter(Task.status == status)
        if client_id:
            query = query.filter(Task.client_id == client_id)
        if lead_id:
            query = query.filter(Task.lead_id == lead_id)
        return query.all()


def complete_task(task_id: int) -> Task | None:
    with session_scope() as session:
        task = session.get(Task, task_id)
        if task is None:
            logger.warning("complete_task: task %s not found", task_id)
            return None
        task.status = "Completed"
        return task


def search_tasks(query: str, limit: int = 10) -> list[Task]:
    """Case-insensitive substring match across description and task_type,
    regardless of status (Global Search should surface historical tasks too)."""
    needle = f"%{query.strip().lower()}%"
    with session_scope() as session:
        return (
            session.query(Task)
            .filter(or_(func.lower(Task.description).like(needle), func.lower(Task.task_type).like(needle)))
            .order_by(Task.id.desc())
            .limit(limit)
            .all()
        )


# --- Followups -----------------------------------------------------------


def create_followup(
    subject: str,
    body: str,
    client_id: str | None = None,
    lead_id: str | None = None,
    to_email: str | None = None,
    channel: str = "email",
    source: str = "manual",
    reason: str | None = None,
    recipient_name: str | None = None,
    context: str | None = None,
) -> Followup:
    with session_scope() as session:
        followup = Followup(
            client_id=client_id,
            lead_id=lead_id,
            to_email=to_email,
            channel=channel,
            subject=subject,
            body=body,
            status="Draft",
            source=source,
            reason=reason,
            recipient_name=recipient_name,
            context=context,
        )
        session.add(followup)
        session.flush()
        return followup


def list_followups(status: str | None = None) -> list[Followup]:
    with session_scope() as session:
        query = session.query(Followup).order_by(Followup.id.desc())
        if status:
            query = query.filter(Followup.status == status)
        return query.all()


def search_followups(query: str, limit: int = 10) -> list[Followup]:
    """Case-insensitive substring match across subject and body."""
    needle = f"%{query.strip().lower()}%"
    with session_scope() as session:
        return (
            session.query(Followup)
            .filter(or_(func.lower(Followup.subject).like(needle), func.lower(Followup.body).like(needle)))
            .order_by(Followup.id.desc())
            .limit(limit)
            .all()
        )


def update_followup(followup_id: int, subject: str | None = None, body: str | None = None) -> Followup | None:
    """Edit a Draft followup's subject/body in place. Refuses (returns None)
    if not found or not still Draft -- an Approved/Sent email must not be
    silently altered after the fact."""
    with session_scope() as session:
        followup = session.get(Followup, followup_id)
        if followup is None:
            logger.warning("update_followup: followup %s not found", followup_id)
            return None
        if followup.status != "Draft":
            logger.warning(
                "update_followup: followup %s is %s, not Draft -- refusing edit",
                followup_id,
                followup.status,
            )
            return None
        if subject is not None:
            followup.subject = subject
        if body is not None:
            followup.body = body
        return followup


def approve_followup(followup_id: int) -> Followup | None:
    with session_scope() as session:
        followup = session.get(Followup, followup_id)
        if followup is None:
            logger.warning("approve_followup: followup %s not found", followup_id)
            return None
        followup.status = "Approved"
        followup.approved_at = datetime.now(timezone.utc)
        return followup


def simulate_send(followup_id: int) -> Followup | None:
    """Mark a followup as sent -- but this NEVER sends a real email; it only
    flips a status flag for the demo. Only succeeds if the followup is
    already Approved by a human; returns None (and changes nothing) if it's
    not found or still Draft, so a followup can never be "sent" without
    going through approve_followup first."""
    with session_scope() as session:
        followup = session.get(Followup, followup_id)
        if followup is None:
            logger.warning("simulate_send: followup %s not found", followup_id)
            return None
        if followup.status != "Approved":
            logger.warning(
                "simulate_send: followup %s is %s, not Approved -- refusing to send",
                followup_id,
                followup.status,
            )
            return None
        followup.status = "Sent-simulated"
        return followup


# --- Conversations -------------------------------------------------------


def log_conversation_turn(session_id: str, role: str, content: str) -> Conversation:
    with session_scope() as session:
        turn = Conversation(session_id=session_id, role=role, content=content)
        session.add(turn)
        session.flush()
        return turn


def list_conversation_turns(session_id: str, limit: int | None = None) -> list[Conversation]:
    """Return a session's turns oldest-first. With `limit`, returns only the
    most recent `limit` turns (still oldest-first) rather than the earliest ones."""
    with session_scope() as session:
        query = session.query(Conversation).filter(Conversation.session_id == session_id).order_by(
            Conversation.id.asc()
        )
        if limit:
            total = query.count()
            if total > limit:
                query = query.offset(total - limit)
        return query.all()


# --- AI action log ---------------------------------------------------------


def log_ai_action(
    tool_name: str,
    input_summary: str,
    result_summary: str,
    status: str = "success",
    human_approval_status: str | None = None,
) -> AIActionLog:
    with session_scope() as session:
        entry = AIActionLog(
            tool_name=tool_name,
            input_summary=input_summary,
            result_summary=result_summary,
            status=status,
            human_approval_status=human_approval_status,
        )
        session.add(entry)
        session.flush()
        return entry


def list_ai_actions(limit: int = 50) -> list[AIActionLog]:
    with session_scope() as session:
        return session.query(AIActionLog).order_by(AIActionLog.id.desc()).limit(limit).all()


# --- Contact submissions (Phase 19) -----------------------------------------


def create_contact_submission(
    name: str, email: str, subject: str, message: str, phone: str | None = None
) -> ContactSubmission:
    with session_scope() as session:
        submission = ContactSubmission(name=name, email=email, phone=phone, subject=subject, message=message)
        session.add(submission)
        session.flush()
        return submission


def get_contact_submission(submission_id: int) -> ContactSubmission | None:
    with session_scope() as session:
        return session.get(ContactSubmission, submission_id)


def update_contact_submission(submission_id: int, **fields) -> ContactSubmission | None:
    with session_scope() as session:
        submission = session.get(ContactSubmission, submission_id)
        if submission is None:
            logger.warning("update_contact_submission: submission %s not found", submission_id)
            return None
        for key, value in fields.items():
            setattr(submission, key, value)
        return submission


def list_contact_submissions(category: str | None = None, status: str | None = None) -> list[ContactSubmission]:
    with session_scope() as session:
        query = session.query(ContactSubmission).order_by(ContactSubmission.id.desc())
        if category:
            query = query.filter(ContactSubmission.category == category)
        if status:
            query = query.filter(ContactSubmission.status == status)
        return query.all()
