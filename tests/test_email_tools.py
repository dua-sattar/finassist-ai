"""Tests for the Phase 18 Email Center tools (tools/email_tools.py,
tools/email_templates.py), against the seeded temp DB (conftest)."""

from database import crud
from tools.email_templates import render_template
from tools.email_tools import compose_email, edit_email_draft, generate_followup_email, regenerate_email_draft


def test_compose_email_creates_a_draft():
    result = compose_email(subject="Manual subject", body="Manual body.", client_id="C1001", source="manual")
    assert result.success and result.followup_id is not None

    row = crud.list_followups(status="Draft")
    assert any(f.id == result.followup_id and f.source == "manual" for f in row)


def test_edit_email_draft_updates_subject_and_body():
    created = compose_email(subject="Original", body="Original body.", client_id="C1001")
    result = edit_email_draft(created.followup_id, subject="Updated", body="Updated body.")
    assert result.success

    row = next(f for f in crud.list_followups(status="Draft") if f.id == created.followup_id)
    assert row.subject == "Updated"
    assert row.body == "Updated body."


def test_edit_email_draft_refuses_once_approved():
    created = compose_email(subject="Original", body="Original body.", client_id="C1001")
    crud.approve_followup(created.followup_id)

    result = edit_email_draft(created.followup_id, subject="Should fail", body="Should fail")
    assert not result.success


def test_edit_email_draft_unknown_id():
    result = edit_email_draft(999999, subject="x", body="y")
    assert not result.success


def test_render_template_fills_placeholders():
    subject, body = render_template(
        "Missing Document Request", recipient_name="Allison Hill", service="Investment Advisory", details="Proof of Address"
    )
    assert "Allison Hill" in body
    assert "Proof of Address" in body


def test_generate_followup_email_persists_regeneration_inputs():
    result = generate_followup_email(reason="Missing ID", recipient_name="Noah Rhodes", context="test context", client_id="C1002")
    assert result.success

    row = next(f for f in crud.list_followups(status="Draft") if f.id == result.followup_id)
    assert row.source == "ai_generated"
    assert row.reason == "Missing ID"
    assert row.recipient_name == "Noah Rhodes"


def test_regenerate_email_draft_changes_content_and_stays_draft():
    generated = generate_followup_email(reason="Missing ID", recipient_name="Noah Rhodes", client_id="C1002")

    result = regenerate_email_draft(generated.followup_id, reason="Missing ID, second reminder", recipient_name="Noah Rhodes")
    assert result.success
    assert result.subject

    row = next(f for f in crud.list_followups(status="Draft") if f.id == generated.followup_id)
    assert row.status == "Draft"


def test_regenerate_email_draft_refuses_once_approved():
    generated = generate_followup_email(reason="Missing ID", recipient_name="Noah Rhodes", client_id="C1002")
    crud.approve_followup(generated.followup_id)

    result = regenerate_email_draft(generated.followup_id, reason="x", recipient_name="y")
    assert not result.success
