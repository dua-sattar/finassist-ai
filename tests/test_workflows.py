"""Tests for the Phase 10/11 workflows against the seeded temp DB (conftest)."""

from agent.workflows import qualify_lead, review_client_documents


def test_review_client_documents_c1002_reports_missing_government_id():
    result = review_client_documents("C1002")

    assert result.success and result.found
    assert result.missing_categories == ["Government-issued ID"]
    assert result.onboarding_status == "Documents Pending"
    assert result.task_id is not None
    assert result.followup_id is not None
    assert "✗ Government-issued ID" in result.report
    assert "Recommended Next Action:" in result.report


def test_review_client_documents_unknown_client():
    result = review_client_documents("C9999")

    assert result.success and not result.found


def test_qualify_lead_high_priority():
    result = qualify_lead("L1001")

    assert result.success and result.found
    assert result.priority == "High"
    assert result.task_id is not None
    assert result.followup_id is not None
    assert "Lead Priority: HIGH" in result.report


def test_qualify_lead_low_priority():
    result = qualify_lead("L1002")

    assert result.success
    assert result.priority == "Low"


def test_qualify_lead_unknown_lead():
    result = qualify_lead("L9999")

    assert result.success and not result.found
