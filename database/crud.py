"""Typed CRUD functions for the FinAssist AI mock CRM.

This is the only module other code (tools/, agent/, app/) should use to
touch the database -- no other module should open a SQLAlchemy session
directly.
"""

import json
import logging
from contextlib import contextmanager
from datetime import date, datetime, timezone

from database.database import SessionLocal
from database.models import (
    AIActionLog,
    Client,
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


def get_lead(lead_id: str) -> Lead | None:
    with session_scope() as session:
        return session.get(Lead, lead_id)


def list_leads(status: str | None = None) -> list[Lead]:
    with session_scope() as session:
        query = session.query(Lead)
        if status:
            query = query.filter(Lead.status == status)
        return query.all()


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


# --- Followups -----------------------------------------------------------


def create_followup(
    subject: str,
    body: str,
    client_id: str | None = None,
    lead_id: str | None = None,
    channel: str = "email",
) -> Followup:
    with session_scope() as session:
        followup = Followup(
            client_id=client_id,
            lead_id=lead_id,
            channel=channel,
            subject=subject,
            body=body,
            status="Draft",
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
