"""Idempotent seed script for the FinAssist AI mock CRM.

Loads clients.csv / leads.csv into their tables, and the Phase 2/3 synthetic
documents (re-run through the Phase 3 extractor) into documents /
document_extractions -- but only for tables that are still empty, so running
this repeatedly is always safe.
"""

import csv
import json
from datetime import date
from pathlib import Path

from database.database import SessionLocal, init_db
from database.models import Client, Document, DocumentExtraction, Lead
from document_processing.extractor import process_document

BASE_DIR = Path(__file__).parent.parent
CLIENTS_CSV = BASE_DIR / "data" / "synthetic" / "clients.csv"
LEADS_CSV = BASE_DIR / "data" / "synthetic" / "leads.csv"
DOCUMENTS_DIR = BASE_DIR / "data" / "synthetic" / "documents"
MANIFEST_CSV = DOCUMENTS_DIR / "manifest.csv"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def seed_clients(session) -> int:
    if session.query(Client).count() > 0:
        return 0
    count = 0
    with CLIENTS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            session.add(
                Client(
                    client_id=row["client_id"],
                    name=row["name"],
                    email=row["email"],
                    service=row["service"],
                    account_status=row["account_status"],
                    onboarding_status=row["onboarding_status"],
                    assigned_advisor=row["assigned_advisor"],
                    last_contact=_parse_date(row["last_contact"]),
                    created_date=_parse_date(row["created_date"]),
                )
            )
            count += 1
    return count


def seed_leads(session) -> int:
    if session.query(Lead).count() > 0:
        return 0
    count = 0
    with LEADS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            session.add(
                Lead(
                    lead_id=row["lead_id"],
                    name=row["name"],
                    email=row["email"],
                    company=row["company"],
                    service_interest=row["service_interest"],
                    engagement_level=row["engagement_level"],
                    information_complete=(row["information_complete"] == "Yes"),
                    source=row["source"],
                    status=row["status"],
                    created_date=_parse_date(row["created_date"]),
                    last_contact=_parse_date(row["last_contact"]),
                )
            )
            count += 1
    return count


def seed_documents(session) -> int:
    if session.query(Document).count() > 0:
        return 0
    count = 0
    with MANIFEST_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            client_id = row["client_id"] or None
            path = DOCUMENTS_DIR / row["filename"]
            result = process_document(path, filename=row["filename"])

            doc = Document(
                client_id=client_id,
                filename=row["filename"],
                document_type=result.document_type,
                status="Received" if result.success else "Invalid",
            )
            session.add(doc)
            session.flush()  # populate doc.id for the extraction FK below

            if result.success:
                session.add(
                    DocumentExtraction(
                        document_id=doc.id,
                        extracted_json=json.dumps(result.extracted_fields, default=str),
                        missing_fields_json=json.dumps(result.missing_fields),
                        summary=result.summary,
                    )
                )
            count += 1
    return count


def main() -> None:
    init_db()
    session = SessionLocal()
    try:
        n_clients = seed_clients(session)
        n_leads = seed_leads(session)
        n_docs = seed_documents(session)
        session.commit()
        print(
            f"Seeded {n_clients} clients, {n_leads} leads, {n_docs} documents "
            "(0 for a table means it was already seeded)."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
