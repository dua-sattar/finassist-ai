"""detect_anomalies tool -- scans a client's already-stored documents for
data-quality anomalies (spec section 10): bank-statement math that doesn't
reconcile, negative balances, expired government IDs, and cross-document
client identity mismatches. Builds on the same consistency-checking
approach as Phase 24 (multi-document) and Phase 25 (comparison), but runs
against everything already on file for a client rather than requiring a
fresh upload batch. Read-only -- never mutates CRM state, so it's safe to
expose directly to the chat agent.
"""

import json
import logging
import os
from datetime import date, datetime

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)

_BALANCE_TOLERANCE = 0.01
_NAME_FIELD_KEYS = ("client_name", "full_name")

ANOMALY_SYSTEM_PROMPT = (
    "You are FinAssist AI's document-review assistant. You are given a list of "
    "data-quality anomalies found across a client's documents on file. Write a "
    "brief, neutral 2-3 sentence observation describing what was found, using "
    "only the details given. Do not invent facts. Do NOT make any approval, "
    "risk, or fraud determination -- only describe the anomalies."
)


class Anomaly(BaseModel):
    category: str
    severity: str  # "High" | "Medium"
    filename: str
    description: str


class AnomalyDetectionResult(BaseModel):
    success: bool
    client_id: str
    found: bool = False
    documents_checked: int = 0
    anomalies: list[Anomaly] = []
    ai_observation: str = ""
    recommended_action: str = ""
    report: str = ""
    error: str | None = None


def _check_balance_math(filename: str, fields: dict) -> Anomaly | None:
    opening = fields.get("opening_balance")
    deposits = fields.get("total_deposits")
    withdrawals = fields.get("total_withdrawals")
    closing = fields.get("closing_balance")
    if not all(isinstance(v, (int, float)) for v in (opening, deposits, withdrawals, closing)):
        return None
    expected = opening + deposits - withdrawals
    if abs(expected - closing) > _BALANCE_TOLERANCE:
        return Anomaly(
            category="Balance Mismatch",
            severity="High",
            filename=filename,
            description=(
                f"Opening balance + deposits - withdrawals = {expected:,.2f}, but closing balance "
                f"is {closing:,.2f} (difference {closing - expected:+,.2f})."
            ),
        )
    return None


def _check_negative_balance(filename: str, fields: dict) -> Anomaly | None:
    for key in ("closing_balance", "current_balance"):
        value = fields.get(key)
        if isinstance(value, (int, float)) and value < 0:
            return Anomaly(
                category="Negative Balance",
                severity="Medium",
                filename=filename,
                description=f"{key.replace('_', ' ')} is negative: {value:,.2f}.",
            )
    return None


def _check_expired_id(filename: str, fields: dict) -> Anomaly | None:
    expiration = fields.get("expiration_date")
    if not isinstance(expiration, str):
        return None
    try:
        expiration_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    except ValueError:
        return None
    if expiration_date < date.today():
        return Anomaly(
            category="Expired ID",
            severity="Medium",
            filename=filename,
            description=f"Government ID expired on {expiration_date.isoformat()}.",
        )
    return None


def _check_identity_consistency(records: list[tuple[str, dict]]) -> list[Anomaly]:
    client_ids_seen: dict[str, list[str]] = {}
    names_seen: dict[str, list[str]] = {}
    for filename, fields in records:
        cid = fields.get("client_id")
        if cid:
            client_ids_seen.setdefault(cid, []).append(filename)
        for key in _NAME_FIELD_KEYS:
            name = fields.get(key)
            if name:
                names_seen.setdefault(name, []).append(filename)
                break

    anomalies: list[Anomaly] = []
    if len(client_ids_seen) > 1:
        all_files = sorted({f for files in client_ids_seen.values() for f in files})
        anomalies.append(
            Anomaly(
                category="Identity Mismatch",
                severity="High",
                filename=", ".join(all_files),
                description=f"Documents reference different client IDs: {', '.join(sorted(client_ids_seen))}.",
            )
        )
    if len(names_seen) > 1:
        all_files = sorted({f for files in names_seen.values() for f in files})
        anomalies.append(
            Anomaly(
                category="Identity Mismatch",
                severity="High",
                filename=", ".join(all_files),
                description=f"Documents reference different client names: {', '.join(sorted(names_seen))}.",
            )
        )
    return anomalies


def _fallback_observation(anomalies: list[Anomaly]) -> str:
    if not anomalies:
        return "No anomalies detected across the documents on file."
    parts = [f"{len(anomalies)} anomaly(ies) found:"]
    for a in anomalies[:5]:
        parts.append(f"[{a.severity}] {a.category} ({a.filename}): {a.description}")
    return " ".join(parts)


def _generate_observation(client_id: str, anomalies: list[Anomaly]) -> str:
    fallback = _fallback_observation(anomalies)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        anomaly_text = (
            "\n".join(f"- [{a.severity}] {a.category} ({a.filename}): {a.description}" for a in anomalies)
            or "none"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ANOMALY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Client: {client_id}\nAnomalies:\n{anomaly_text}"},
            ],
            max_tokens=200,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or fallback
    except Exception as exc:
        logger.warning("Groq anomaly observation call failed for %s: %s", client_id, exc)
        return fallback


def _format_report(
    client_id: str,
    client_name: str,
    documents_checked: int,
    anomalies: list[Anomaly],
    ai_observation: str,
    recommended_action: str,
) -> str:
    lines = [
        "ANOMALY DETECTION REPORT",
        "",
        f"Client: {client_id} ({client_name})",
        f"Documents Checked: {documents_checked}",
        "",
    ]
    if anomalies:
        lines.append("Anomalies Found:")
        for a in anomalies:
            lines.append(f"[{a.severity}] {a.category} -- {a.filename}: {a.description}")
    else:
        lines.append("No anomalies found.")

    lines += [
        "",
        "AI Observation:",
        ai_observation,
        "",
        "Recommended Action:",
        recommended_action,
        "",
        "Human Review Required",
    ]
    return "\n".join(lines)


def detect_anomalies(client_id: str) -> AnomalyDetectionResult:
    """Scan every document already on file for a client for data-quality
    anomalies: bank-statement math that doesn't reconcile, negative
    balances, expired government IDs, and client identity mismatches across
    documents. Read-only -- runs against what's already stored, no new
    upload needed. Never makes an approval, risk, or fraud determination --
    always ends with a human-review notice."""
    try:
        client = crud.get_client(client_id)
        if client is None:
            log_action("detect_anomalies", f"client_id={client_id}", "not found")
            return AnomalyDetectionResult(success=True, client_id=client_id, found=False)

        rows = crud.list_documents_with_extractions_for_client(client_id)
        anomalies: list[Anomaly] = []
        identity_records: list[tuple[str, dict]] = []

        for doc, extraction in rows:
            if extraction is None:
                continue
            fields = json.loads(extraction.extracted_json)
            identity_records.append((doc.filename, fields))

            for check in (_check_balance_math, _check_negative_balance, _check_expired_id):
                found_anomaly = check(doc.filename, fields)
                if found_anomaly is not None:
                    anomalies.append(found_anomaly)

        anomalies.extend(_check_identity_consistency(identity_records))

        ai_observation = _generate_observation(client_id, anomalies)

        high_severity = [a for a in anomalies if a.severity == "High"]
        if high_severity:
            recommended_action = "Escalate to a human advisor for review before taking any further action on this client."
        elif anomalies:
            recommended_action = "Flag for advisor review at the next client contact."
        else:
            recommended_action = "No anomalies detected. No action needed."

        report = _format_report(client_id, client.name, len(rows), anomalies, ai_observation, recommended_action)

        log_action("detect_anomalies", f"client_id={client_id}", f"{len(anomalies)} anomalies found")
        return AnomalyDetectionResult(
            success=True,
            client_id=client_id,
            found=True,
            documents_checked=len(rows),
            anomalies=anomalies,
            ai_observation=ai_observation,
            recommended_action=recommended_action,
            report=report,
        )
    except Exception as exc:
        logger.warning("detect_anomalies failed for %s: %s", client_id, exc)
        log_action("detect_anomalies", f"client_id={client_id}", str(exc), status="error")
        return AnomalyDetectionResult(success=False, client_id=client_id, error=str(exc))
