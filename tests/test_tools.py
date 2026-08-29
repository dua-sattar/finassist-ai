"""Tests for the Phase 7 agent tools, against the seeded temp DB (conftest)."""

from tools.crm_tools import get_client, get_lead, search_clients, search_leads, update_client, update_lead
from tools.document_tools import analyze_document, check_required_documents
from tools.email_tools import generate_followup_email
from tools.task_tools import create_followup_task
from tests.conftest import DOCUMENTS_DIR


def test_get_client_found():
    result = get_client("C1002")
    assert result.success and result.found
    assert result.name == "Noah Rhodes"


def test_get_client_not_found():
    result = get_client("C9999")
    assert result.success and not result.found


def test_get_lead_found():
    result = get_lead("L1001")
    assert result.success and result.found


def test_search_clients_fuzzy_match_by_name():
    result = search_clients("Noah")
    assert result.success
    assert any(c.client_id == "C1002" for c in result.results)


def test_search_clients_no_match_returns_empty_not_error():
    result = search_clients("zzz-nonexistent-zzz")
    assert result.success
    assert result.results == []


def test_search_clients_is_case_insensitive():
    result = search_clients("NOAH")
    assert result.success
    assert any(c.client_id == "C1002" for c in result.results)


def test_search_leads_fuzzy_match_by_company():
    result = search_leads("George")
    assert result.success
    assert any(lead.lead_id == "L1001" for lead in result.results)


def test_check_required_documents_c1002_missing_government_id():
    result = check_required_documents("C1002")

    assert result.success
    assert result.missing_categories == ["Government-issued ID"]
    assert not result.all_satisfied


def test_update_client_round_trips():
    updated = update_client("C1002", assigned_advisor="Test Advisor")
    assert updated.success and updated.found

    fetched = get_client("C1002")
    assert fetched.assigned_advisor == "Test Advisor"


def test_update_lead_round_trips():
    updated = update_lead("L1001", status="Contacted")
    assert updated.success and updated.found

    fetched = get_lead("L1001")
    assert fetched.status == "Contacted"


def test_analyze_document_valid_pdf():
    result = analyze_document(
        DOCUMENTS_DIR / "C1004_bank_statement.pdf", client_id="C1004", filename="C1004_bank_statement.pdf"
    )

    assert result.success
    assert result.document_id is not None
    assert result.document_type == "bank_statement"


def test_analyze_document_corrupted_pdf_reports_failure_not_exception():
    result = analyze_document(DOCUMENTS_DIR / "invalid_corrupted.pdf", filename="invalid_corrupted.pdf")

    assert not result.success
    assert result.error


def test_create_followup_task():
    result = create_followup_task(description="Test task", client_id="C1002", priority="High")

    assert result.success
    assert result.task_id is not None


def test_generate_followup_email_is_always_draft():
    result = generate_followup_email(
        reason="Test reason", recipient_name="Noah Rhodes", client_id="C1002"
    )

    assert result.success
    assert result.status == "Draft"
    assert result.subject
