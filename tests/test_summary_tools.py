"""Tests for the Phase 21 Client Case Summary tool (tools/summary_tools.py),
against the seeded temp DB (conftest)."""

from agent.workflows import review_client_documents
from tools.summary_tools import generate_case_summary


def test_generate_case_summary_c1002_matches_spec_shape():
    result = generate_case_summary("C1002")

    assert result.success and result.found
    assert result.client_name == "Noah Rhodes"
    assert result.service == "Retirement Planning"
    assert "CLIENT CASE SUMMARY" in result.report
    assert "Documents:" in result.report
    assert "Recent Activity:" in result.report
    assert "AI Summary:" in result.report
    assert "Recommended Action:" in result.report
    assert "Human Review Required" in result.report
    assert result.ai_summary
    assert not result.all_satisfied
    assert "Government-issued ID" in result.recommended_action


def test_generate_case_summary_reflects_real_recent_activity():
    review_client_documents("C1003")
    result = generate_case_summary("C1003")

    assert result.success and result.found
    assert len(result.recent_activity) > 0
    assert any("Task created" in a for a in result.recent_activity)


def test_generate_case_summary_activity_is_chronological_most_recent_first():
    review_client_documents("C1004")
    result = generate_case_summary("C1004")

    # The task + followup created by review_client_documents should sort
    # ahead of the client's pre-existing document uploads.
    assert result.recent_activity
    assert result.recent_activity[0].startswith("Follow-up email") or result.recent_activity[0].startswith("Task created")


def test_generate_case_summary_unknown_client():
    result = generate_case_summary("C9999")
    assert result.success and not result.found
