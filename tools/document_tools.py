"""analyze_document and check_required_documents tools -- wrap the Phase 3
extraction pipeline and the Phase 3 required-documents mapping."""

import logging
from pathlib import Path

from pydantic import BaseModel

from database import crud
from document_processing.extractor import process_document
from document_processing.schemas import REQUIRED_DOCUMENT_CATEGORIES
from tools.common import log_action

logger = logging.getLogger(__name__)


class AnalyzeDocumentResult(BaseModel):
    success: bool
    filename: str
    document_id: int | None = None
    document_type: str = "unknown"
    extracted_fields: dict = {}
    missing_fields: list[str] = []
    summary: str = ""
    error: str | None = None


def analyze_document(
    source: str | Path | bytes, client_id: str | None = None, filename: str | None = None
) -> AnalyzeDocumentResult:
    """Extract text/fields/summary from an uploaded document and record it in the CRM."""
    display_name = filename or (str(source) if isinstance(source, (str, Path)) else "uploaded_document")
    try:
        extraction = process_document(source, filename=display_name)

        doc = crud.add_document(
            client_id=client_id,
            filename=display_name,
            document_type=extraction.document_type,
            status="Received" if extraction.success else "Invalid",
        )

        if extraction.success:
            crud.add_document_extraction(
                document_id=doc.id,
                extracted_fields=extraction.extracted_fields,
                missing_fields=extraction.missing_fields,
                summary=extraction.summary,
            )

        log_action(
            "analyze_document",
            f"filename={display_name} client_id={client_id}",
            f"type={extraction.document_type} success={extraction.success}",
            status="success" if extraction.success else "error",
        )
        return AnalyzeDocumentResult(
            success=extraction.success,
            filename=display_name,
            document_id=doc.id,
            document_type=extraction.document_type,
            extracted_fields=extraction.extracted_fields,
            missing_fields=extraction.missing_fields,
            summary=extraction.summary,
            error=extraction.error,
        )
    except Exception as exc:
        logger.warning("analyze_document failed for %s: %s", display_name, exc)
        log_action("analyze_document", f"filename={display_name} client_id={client_id}", str(exc), status="error")
        return AnalyzeDocumentResult(success=False, filename=display_name, error=str(exc))


class RequiredDocumentStatus(BaseModel):
    category: str
    satisfied: bool
    matched_document_types: list[str] = []


class CheckRequiredDocumentsResult(BaseModel):
    success: bool
    client_id: str
    checklist: list[RequiredDocumentStatus] = []
    all_satisfied: bool = False
    missing_categories: list[str] = []
    error: str | None = None


def check_required_documents(client_id: str) -> CheckRequiredDocumentsResult:
    """Compare a client's received documents against the onboarding required-documents checklist."""
    try:
        docs = crud.list_documents_for_client(client_id)
        received_types = {d.document_type for d in docs if d.status == "Received"}

        checklist = []
        missing = []
        for category, doc_types in REQUIRED_DOCUMENT_CATEGORIES.items():
            matched = [t for t in doc_types if t in received_types]
            satisfied = len(matched) > 0
            checklist.append(
                RequiredDocumentStatus(category=category, satisfied=satisfied, matched_document_types=matched)
            )
            if not satisfied:
                missing.append(category)

        log_action(
            "check_required_documents",
            f"client_id={client_id}",
            f"missing={missing}" if missing else "all satisfied",
        )
        return CheckRequiredDocumentsResult(
            success=True,
            client_id=client_id,
            checklist=checklist,
            all_satisfied=(len(missing) == 0),
            missing_categories=missing,
        )
    except Exception as exc:
        logger.warning("check_required_documents failed for %s: %s", client_id, exc)
        log_action("check_required_documents", f"client_id={client_id}", str(exc), status="error")
        return CheckRequiredDocumentsResult(success=False, client_id=client_id, error=str(exc))
