"""Reporting tools (spec section 24): five generated, downloadable reports
built entirely from data the app already tracks -- no new data model, just
aggregation over the existing CRM/document/task tables. Each report is
deterministic tabular data (a CSV export) plus a short AI-narrated overview
(with a templated fallback), read-only throughout.

The anomaly summary report reuses the Phase 26 check functions directly
rather than calling tools.anomaly_tools.detect_anomalies per client, which
would fire one Groq call per client with documents on file -- slow and
wasteful when one Groq call narrating the aggregated findings does the job.
"""

import csv
import io
import json
import logging
import os
from datetime import date, datetime

from pydantic import BaseModel

from database import crud
from tools.anomaly_tools import (
    _check_balance_math,
    _check_expired_id,
    _check_identity_consistency,
    _check_negative_balance,
)
from tools.common import log_action
from tools.document_tools import check_required_documents

logger = logging.getLogger(__name__)


class ReportResult(BaseModel):
    success: bool
    report_type: str
    title: str
    generated_at: str
    row_count: int = 0
    rows: list[dict] = []
    ai_summary: str = ""
    csv_text: str = ""
    error: str | None = None


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _generate_narration(system_prompt: str, fallback: str, user_content: str, report_type: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=200,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or fallback
    except Exception as exc:
        logger.warning("Groq narration call failed for %s report: %s", report_type, exc)
        return fallback


_PORTFOLIO_SYSTEM_PROMPT = (
    "You are FinAssist AI's reporting assistant. Given aggregate client portfolio "
    "statistics, write a brief, neutral 2-3 sentence overview for an internal "
    "report. Only state the numbers given -- do not invent figures."
)


def generate_client_portfolio_report() -> ReportResult:
    """All clients with service, account/onboarding status, and advisor,
    plus an AI-narrated portfolio overview."""
    try:
        clients = crud.list_clients()
        rows = [
            {
                "Client ID": c.client_id,
                "Name": c.name,
                "Service": c.service,
                "Account Status": c.account_status,
                "Onboarding Status": c.onboarding_status,
                "Advisor": c.assigned_advisor,
                "Last Contact": str(c.last_contact),
            }
            for c in clients
        ]

        by_account_status: dict[str, int] = {}
        by_onboarding_status: dict[str, int] = {}
        for c in clients:
            by_account_status[c.account_status] = by_account_status.get(c.account_status, 0) + 1
            by_onboarding_status[c.onboarding_status] = by_onboarding_status.get(c.onboarding_status, 0) + 1

        stats_text = (
            f"Total clients: {len(clients)}\n"
            f"By account status: {by_account_status}\n"
            f"By onboarding status: {by_onboarding_status}"
        )
        fallback = (
            f"{len(clients)} clients total. Account status: "
            f"{', '.join(f'{k} {v}' for k, v in by_account_status.items())}. Onboarding status: "
            f"{', '.join(f'{k} {v}' for k, v in by_onboarding_status.items())}."
        )
        ai_summary = _generate_narration(_PORTFOLIO_SYSTEM_PROMPT, fallback, stats_text, "client_portfolio")

        log_action("generate_client_portfolio_report", "", f"{len(rows)} clients")
        return ReportResult(
            success=True,
            report_type="client_portfolio",
            title="Client Portfolio Report",
            generated_at=_timestamp(),
            row_count=len(rows),
            rows=rows,
            ai_summary=ai_summary,
            csv_text=_rows_to_csv(rows),
        )
    except Exception as exc:
        logger.warning("generate_client_portfolio_report failed: %s", exc)
        log_action("generate_client_portfolio_report", "", str(exc), status="error")
        return ReportResult(
            success=False, report_type="client_portfolio", title="Client Portfolio Report",
            generated_at=_timestamp(), error=str(exc),
        )


_PIPELINE_SYSTEM_PROMPT = (
    "You are FinAssist AI's reporting assistant. Given aggregate lead pipeline "
    "statistics, write a brief, neutral 2-3 sentence overview for an internal "
    "report. Only state the numbers given -- do not invent figures."
)


def generate_lead_pipeline_report() -> ReportResult:
    """All leads with company, service interest, engagement level, and
    status, plus an AI-narrated pipeline overview."""
    try:
        leads = crud.list_leads()
        rows = [
            {
                "Lead ID": lead.lead_id,
                "Name": lead.name,
                "Company": lead.company,
                "Service Interest": lead.service_interest,
                "Engagement Level": lead.engagement_level,
                "Status": lead.status,
                "Source": lead.source,
                "Last Contact": str(lead.last_contact),
            }
            for lead in leads
        ]

        by_status: dict[str, int] = {}
        by_engagement: dict[str, int] = {}
        for lead in leads:
            by_status[lead.status] = by_status.get(lead.status, 0) + 1
            by_engagement[lead.engagement_level] = by_engagement.get(lead.engagement_level, 0) + 1

        stats_text = (
            f"Total leads: {len(leads)}\nBy status: {by_status}\nBy engagement level: {by_engagement}"
        )
        fallback = (
            f"{len(leads)} leads total. Status: {', '.join(f'{k} {v}' for k, v in by_status.items())}. "
            f"Engagement: {', '.join(f'{k} {v}' for k, v in by_engagement.items())}."
        )
        ai_summary = _generate_narration(_PIPELINE_SYSTEM_PROMPT, fallback, stats_text, "lead_pipeline")

        log_action("generate_lead_pipeline_report", "", f"{len(rows)} leads")
        return ReportResult(
            success=True,
            report_type="lead_pipeline",
            title="Lead Pipeline Report",
            generated_at=_timestamp(),
            row_count=len(rows),
            rows=rows,
            ai_summary=ai_summary,
            csv_text=_rows_to_csv(rows),
        )
    except Exception as exc:
        logger.warning("generate_lead_pipeline_report failed: %s", exc)
        log_action("generate_lead_pipeline_report", "", str(exc), status="error")
        return ReportResult(
            success=False, report_type="lead_pipeline", title="Lead Pipeline Report",
            generated_at=_timestamp(), error=str(exc),
        )


_COMPLIANCE_SYSTEM_PROMPT = (
    "You are FinAssist AI's reporting assistant. Given aggregate onboarding "
    "document compliance statistics across all clients, write a brief, neutral "
    "2-3 sentence overview for an internal report. Only state the numbers "
    "given -- do not invent figures."
)


def generate_document_compliance_report() -> ReportResult:
    """Every client's onboarding required-documents checklist status, plus
    an AI-narrated compliance overview."""
    try:
        clients = crud.list_clients()
        rows = []
        missing_category_counts: dict[str, int] = {}
        compliant_count = 0

        for c in clients:
            check = check_required_documents(c.client_id)
            if not check.success:
                continue
            if check.all_satisfied:
                compliant_count += 1
            for category in check.missing_categories:
                missing_category_counts[category] = missing_category_counts.get(category, 0) + 1
            rows.append(
                {
                    "Client ID": c.client_id,
                    "Name": c.name,
                    "Onboarding Status": c.onboarding_status,
                    "Fully Compliant": "Yes" if check.all_satisfied else "No",
                    "Missing Categories": ", ".join(check.missing_categories) or "None",
                }
            )

        stats_text = (
            f"Total clients checked: {len(rows)}\nFully compliant: {compliant_count}\n"
            f"Not compliant: {len(rows) - compliant_count}\n"
            f"Missing category frequency: {missing_category_counts}"
        )
        fallback = (
            f"{compliant_count} of {len(rows)} clients have all required onboarding documents on file. "
            f"Most commonly missing: {', '.join(f'{k} ({v})' for k, v in missing_category_counts.items()) or 'none'}."
        )
        ai_summary = _generate_narration(_COMPLIANCE_SYSTEM_PROMPT, fallback, stats_text, "document_compliance")

        log_action("generate_document_compliance_report", "", f"{len(rows)} clients checked")
        return ReportResult(
            success=True,
            report_type="document_compliance",
            title="Document Compliance Report",
            generated_at=_timestamp(),
            row_count=len(rows),
            rows=rows,
            ai_summary=ai_summary,
            csv_text=_rows_to_csv(rows),
        )
    except Exception as exc:
        logger.warning("generate_document_compliance_report failed: %s", exc)
        log_action("generate_document_compliance_report", "", str(exc), status="error")
        return ReportResult(
            success=False, report_type="document_compliance", title="Document Compliance Report",
            generated_at=_timestamp(), error=str(exc),
        )


_TASK_SYSTEM_PROMPT = (
    "You are FinAssist AI's reporting assistant. Given aggregate open-task "
    "statistics (by due-date grouping and priority), write a brief, neutral "
    "2-3 sentence overview for an internal report. Only state the numbers "
    "given -- do not invent figures."
)


def generate_task_report() -> ReportResult:
    """Every open task with due-date grouping (Overdue / Due Today /
    Upcoming / No Due Date), plus an AI-narrated overview."""
    try:
        all_tasks = crud.list_tasks()
        open_tasks = [t for t in all_tasks if t.status == "Open"]
        today = date.today()

        def _group(t) -> str:
            if not t.due_date:
                return "No Due Date"
            if t.due_date < today:
                return "Overdue"
            if t.due_date == today:
                return "Due Today"
            return "Upcoming"

        rows = [
            {
                "Task ID": t.id,
                "Type": t.task_type,
                "Client": t.client_id or "",
                "Lead": t.lead_id or "",
                "Description": t.description,
                "Priority": t.priority or "",
                "Due Date": str(t.due_date) if t.due_date else "",
                "Group": _group(t),
            }
            for t in open_tasks
        ]

        by_group: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for t in open_tasks:
            by_group[_group(t)] = by_group.get(_group(t), 0) + 1
            by_priority[t.priority or "None"] = by_priority.get(t.priority or "None", 0) + 1

        stats_text = (
            f"Open tasks: {len(open_tasks)}\nCompleted tasks: {len(all_tasks) - len(open_tasks)}\n"
            f"By due-date group: {by_group}\nBy priority: {by_priority}"
        )
        fallback = (
            f"{len(open_tasks)} open task(s). Due-date breakdown: "
            f"{', '.join(f'{k} {v}' for k, v in by_group.items()) or 'none'}. "
            f"Priority breakdown: {', '.join(f'{k} {v}' for k, v in by_priority.items()) or 'none'}."
        )
        ai_summary = _generate_narration(_TASK_SYSTEM_PROMPT, fallback, stats_text, "task_report")

        log_action("generate_task_report", "", f"{len(rows)} open tasks")
        return ReportResult(
            success=True,
            report_type="task_report",
            title="Task & Follow-up Report",
            generated_at=_timestamp(),
            row_count=len(rows),
            rows=rows,
            ai_summary=ai_summary,
            csv_text=_rows_to_csv(rows),
        )
    except Exception as exc:
        logger.warning("generate_task_report failed: %s", exc)
        log_action("generate_task_report", "", str(exc), status="error")
        return ReportResult(
            success=False, report_type="task_report", title="Task & Follow-up Report",
            generated_at=_timestamp(), error=str(exc),
        )


_ANOMALY_SUMMARY_SYSTEM_PROMPT = (
    "You are FinAssist AI's reporting assistant. Given aggregate data-quality "
    "anomaly statistics across all clients' documents, write a brief, neutral "
    "2-3 sentence overview for an internal report. Do NOT make any approval, "
    "risk, or fraud determination -- only describe what was found, using only "
    "the numbers given."
)


def generate_anomaly_summary_report() -> ReportResult:
    """Company-wide anomaly scan: runs the Phase 26 deterministic checks
    (balance math, negative balance, expired ID, identity consistency)
    against every client's documents on file, and narrates the aggregated
    findings in a single AI call rather than one per client."""
    try:
        clients = crud.list_clients()
        rows = []
        by_severity: dict[str, int] = {}
        clients_affected: set[str] = set()

        for c in clients:
            doc_rows = crud.list_documents_with_extractions_for_client(c.client_id)
            identity_records: list[tuple[str, dict]] = []
            client_anomalies = []

            for doc, extraction in doc_rows:
                if extraction is None:
                    continue
                fields = json.loads(extraction.extracted_json)
                identity_records.append((doc.filename, fields))
                for check in (_check_balance_math, _check_negative_balance, _check_expired_id):
                    found = check(doc.filename, fields)
                    if found is not None:
                        client_anomalies.append(found)

            client_anomalies.extend(_check_identity_consistency(identity_records))

            for a in client_anomalies:
                rows.append(
                    {
                        "Client ID": c.client_id,
                        "Client Name": c.name,
                        "Category": a.category,
                        "Severity": a.severity,
                        "Filename": a.filename,
                        "Description": a.description,
                    }
                )
                by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
                clients_affected.add(c.client_id)

        stats_text = (
            f"Total anomalies: {len(rows)}\nClients affected: {len(clients_affected)} of {len(clients)}\n"
            f"By severity: {by_severity}"
        )
        fallback = (
            f"{len(rows)} anomaly(ies) found across {len(clients_affected)} of {len(clients)} clients. "
            f"Severity breakdown: {', '.join(f'{k} {v}' for k, v in by_severity.items()) or 'none'}."
        )
        ai_summary = _generate_narration(_ANOMALY_SUMMARY_SYSTEM_PROMPT, fallback, stats_text, "anomaly_summary")

        log_action("generate_anomaly_summary_report", "", f"{len(rows)} anomalies across {len(clients_affected)} clients")
        return ReportResult(
            success=True,
            report_type="anomaly_summary",
            title="Anomaly Summary Report",
            generated_at=_timestamp(),
            row_count=len(rows),
            rows=rows,
            ai_summary=ai_summary,
            csv_text=_rows_to_csv(rows),
        )
    except Exception as exc:
        logger.warning("generate_anomaly_summary_report failed: %s", exc)
        log_action("generate_anomaly_summary_report", "", str(exc), status="error")
        return ReportResult(
            success=False, report_type="anomaly_summary", title="Anomaly Summary Report",
            generated_at=_timestamp(), error=str(exc),
        )
