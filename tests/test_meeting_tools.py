"""Tests for the Phase 28 meeting-summary tool (tools/meeting_tools.py),
against the seeded temp DB (conftest)."""

from database import crud
from tools.meeting_tools import _parse_sections, summarize_meeting_notes

SAMPLE_NOTES = (
    "Call with the client. She confirmed she wants to proceed with the "
    "retirement planning add-on and needs to send her latest bank statement. "
    "We agreed to schedule a follow-up call next month."
)


def test_parse_sections_extracts_bullets_under_each_header():
    text = (
        "Key Points:\n- Point one\n- Point two\n\n"
        "Decisions:\n- Decision one\n\n"
        "Action Items:\n- Action one\n\n"
        "Next Steps:\n- Step one"
    )
    parsed = _parse_sections(text)
    assert parsed["Key Points"] == ["Point one", "Point two"]
    assert parsed["Decisions"] == ["Decision one"]
    assert parsed["Action Items"] == ["Action one"]
    assert parsed["Next Steps"] == ["Step one"]


def test_parse_sections_treats_none_noted_as_empty():
    text = "Key Points:\n- None noted.\n\nDecisions:\n- Real decision."
    parsed = _parse_sections(text)
    assert parsed["Key Points"] == []
    assert parsed["Decisions"] == ["Real decision."]


def test_parse_sections_ignores_text_outside_any_section():
    text = "Some preamble that should be ignored.\n\nKey Points:\n- A real point."
    parsed = _parse_sections(text)
    assert parsed["Key Points"] == ["A real point."]


def test_unknown_client_fails_gracefully():
    result = summarize_meeting_notes("Notes.", client_id="C9999")
    assert not result.success
    assert "not found" in result.error.lower()


def test_unknown_lead_fails_gracefully():
    result = summarize_meeting_notes("Notes.", lead_id="L9999")
    assert not result.success
    assert "not found" in result.error.lower()


def test_summarize_meeting_notes_persists_and_links_to_client():
    result = summarize_meeting_notes(SAMPLE_NOTES, client_id="C1002")
    assert result.success, result.error
    assert result.meeting_id is not None
    assert result.client_id == "C1002"
    assert "Human Review Required" in result.report

    stored = crud.list_meeting_summaries(client_id="C1002")
    assert any(s.id == result.meeting_id for s in stored)


def test_action_items_become_open_tasks():
    before = len(crud.list_open_tasks(client_id="C1003"))
    result = summarize_meeting_notes(SAMPLE_NOTES, client_id="C1003")
    assert result.success, result.error
    after = crud.list_open_tasks(client_id="C1003")
    assert len(after) == before + len(result.task_ids_created)
    for task_id in result.task_ids_created:
        assert any(t.id == task_id for t in after)


def test_unlinked_note_has_no_client_or_lead():
    result = summarize_meeting_notes("Some general notes with no CRM link.")
    assert result.success
    assert result.client_id is None
    assert result.lead_id is None
    assert result.meeting_id is not None


def test_report_always_includes_human_review_notice():
    result = summarize_meeting_notes(SAMPLE_NOTES)
    assert result.success
    assert "Human Review Required" in result.report
