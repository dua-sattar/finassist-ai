"""Tests for the Phase 27 reporting tools (tools/report_tools.py), against
the seeded temp DB (conftest)."""

import csv
import io

from tools.report_tools import (
    generate_anomaly_summary_report,
    generate_client_portfolio_report,
    generate_document_compliance_report,
    generate_lead_pipeline_report,
    generate_task_report,
)


def _csv_row_count(csv_text: str) -> int:
    return len(list(csv.DictReader(io.StringIO(csv_text))))


def test_client_portfolio_report_covers_every_seeded_client():
    result = generate_client_portfolio_report()
    assert result.success
    assert result.report_type == "client_portfolio"
    assert result.row_count == 40
    assert len(result.rows) == 40
    assert _csv_row_count(result.csv_text) == 40
    assert result.ai_summary
    assert {"Client ID", "Name", "Account Status", "Onboarding Status"} <= result.rows[0].keys()


def test_lead_pipeline_report_covers_every_seeded_lead():
    # >= rather than == 40: other test modules (e.g. contact-submission
    # tests) call create_lead against this same session-scoped DB, so more
    # leads may exist by the time this test runs depending on collection
    # order -- the seeded 40 are always a subset.
    result = generate_lead_pipeline_report()
    assert result.success
    assert result.row_count >= 40
    assert _csv_row_count(result.csv_text) == result.row_count
    assert result.ai_summary
    assert {"Lead ID", "Status", "Engagement Level"} <= result.rows[0].keys()
    assert any(r["Lead ID"] == "L1001" for r in result.rows)


def test_document_compliance_report_flags_missing_categories():
    result = generate_document_compliance_report()
    assert result.success
    assert result.row_count == 40
    assert _csv_row_count(result.csv_text) == 40
    by_client = {r["Client ID"]: r for r in result.rows}
    assert by_client["C1001"]["Fully Compliant"] == "No"
    assert "Completed Application Form" in by_client["C1001"]["Missing Categories"]


def test_task_report_groups_by_due_date():
    result = generate_task_report()
    assert result.success
    assert _csv_row_count(result.csv_text) == result.row_count
    if result.rows:
        assert all(r["Group"] in {"Overdue", "Due Today", "Upcoming", "No Due Date"} for r in result.rows)
    assert result.ai_summary


def test_anomaly_summary_report_finds_c1001_expired_id():
    result = generate_anomaly_summary_report()
    assert result.success
    assert _csv_row_count(result.csv_text) == result.row_count
    expired = [r for r in result.rows if r["Client ID"] == "C1001" and r["Category"] == "Expired ID"]
    assert expired
    assert result.ai_summary


def test_reports_are_downloadable_as_valid_csv_with_matching_headers():
    result = generate_client_portfolio_report()
    reader = csv.DictReader(io.StringIO(result.csv_text))
    assert reader.fieldnames == list(result.rows[0].keys())
