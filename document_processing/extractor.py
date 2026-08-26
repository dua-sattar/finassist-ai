"""Structured field extraction and summarization for FinAssist AI documents.

Classification and field extraction are deterministic (regex over the
`Label: value` line format every synthetic document uses) rather than
LLM-based -- cheap, offline-testable, and realistic for a fixed document
template. Only the free-text summary calls the Groq API (free tier), with a
graceful templated fallback if no API key is configured or the call fails.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from document_processing.parser import extract_text
from document_processing.schemas import DOCUMENT_TYPE_SCHEMAS

load_dotenv()

logger = logging.getLogger(__name__)

TITLE_TO_TYPE = {
    "bank statement": "bank_statement",
    "financial summary": "financial_summary",
    "transaction report": "transaction_report",
    "client application form": "client_application_form",
    "account summary": "account_summary",
    "government-issued id": "government_id",
    "proof of address": "proof_of_address",
}

_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z \-]*):\s*(.+)$")
_MONEY_RE = re.compile(r"^\$-?[\d,]+\.\d{2}$")


def classify_document(text: str) -> str:
    """Identify the document type from its title line, with a keyword fallback."""
    first_line = text.splitlines()[0].strip().lower() if text.strip() else ""
    if first_line in TITLE_TO_TYPE:
        return TITLE_TO_TYPE[first_line]

    for title, doc_type in TITLE_TO_TYPE.items():
        if title in text.lower():
            return doc_type

    return "unknown"


def _normalize_label(label: str) -> str:
    return label.strip().lower().replace(" ", "_").replace("-", "_")


def _coerce_value(value: str) -> Optional[str] | float:
    value = value.strip()
    if value == "(not provided)":
        return None
    if _MONEY_RE.match(value):
        return float(value.replace("$", "").replace(",", ""))
    return value


def extract_fields(text: str, document_type: str) -> dict:
    """Parse every `Label: value` line in the document into a flat dict."""
    fields: dict = {}
    for line in text.splitlines():
        match = _LINE_RE.match(line.strip())
        if not match:
            continue
        key = _normalize_label(match.group(1))
        fields[key] = _coerce_value(match.group(2))

    if document_type == "transaction_report":
        marker = "Recent Transactions:"
        if marker in text:
            fields["transactions_raw"] = text.split(marker, 1)[1].strip()

    return fields


def summarize_document(document_type: str, extracted: dict) -> str:
    """One-sentence-or-two AI summary of the extracted document, with a
    templated fallback if Groq is unavailable or the call fails."""
    client_id = extracted.get("client_id", "unknown client")
    label = document_type.replace("_", " ")
    field_str = ", ".join(f"{k}={v}" for k, v in extracted.items() if v is not None and k != "client_id")
    fallback = f"{label.title()} for {client_id}. Extracted fields: {field_str or 'none'}."

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.info("No GROQ_API_KEY configured; using templated summary for %s", client_id)
        return fallback

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the following extracted financial document data in "
                        "2-3 plain sentences for an internal advisor review. Do not "
                        "invent any values not present in the data."
                    ),
                },
                {"role": "user", "content": f"Document type: {label}\nFields: {extracted}"},
            ],
            max_tokens=150,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            logger.warning("Groq returned an empty summary for %s; using template", client_id)
            return fallback
        return content
    except Exception as exc:
        logger.warning("Groq summary call failed for %s: %s", client_id, exc)
        return fallback


@dataclass
class DocumentExtractionResult:
    filename: str
    success: bool
    document_type: str
    extracted_fields: dict = field(default_factory=dict)
    validated: Optional[BaseModel] = None
    missing_fields: list[str] = field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None


def process_document(source: str | Path | bytes, filename: Optional[str] = None) -> DocumentExtractionResult:
    """Full pipeline: extract text -> classify -> extract fields -> validate -> summarize."""
    display_name = filename or (str(source) if isinstance(source, (str, Path)) else "uploaded_document")

    parsed = extract_text(source)
    if not parsed.success:
        return DocumentExtractionResult(
            filename=display_name, success=False, document_type="unknown", error=parsed.error
        )

    document_type = classify_document(parsed.text)
    raw_fields = extract_fields(parsed.text, document_type)

    schema_cls = DOCUMENT_TYPE_SCHEMAS.get(document_type)
    validated = None
    missing_fields: list[str] = []
    if schema_cls is not None:
        try:
            known_fields = {k: v for k, v in raw_fields.items() if k in schema_cls.model_fields}
            validated = schema_cls(**known_fields)
            missing_fields = [k for k, v in validated.model_dump().items() if v is None]
        except ValidationError as exc:
            logger.warning("Validation failed for %s: %s", display_name, exc)
            return DocumentExtractionResult(
                filename=display_name,
                success=False,
                document_type=document_type,
                extracted_fields=raw_fields,
                error=str(exc),
            )

    summary = summarize_document(document_type, raw_fields)

    return DocumentExtractionResult(
        filename=display_name,
        success=True,
        document_type=document_type,
        extracted_fields=raw_fields,
        validated=validated,
        missing_fields=missing_fields,
        summary=summary,
    )
