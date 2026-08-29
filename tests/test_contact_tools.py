"""Tests for the Phase 19 Contact Us tools (tools/contact_tools.py) and the
process_contact_submission workflow, against the seeded temp DB (conftest).

Classification-dependent tests monkeypatch classify_contact_submission to a
fixed result rather than relying on real (non-deterministic) LLM output --
the real Groq path is separately exercised by agent/verify_contact.py.
"""

import agent.workflows as workflows
from database import crud
from tools.contact_tools import ClassificationResult, create_contact_submission, update_contact_submission
from tools.crm_tools import create_lead


def test_create_contact_submission_creates_a_ticket():
    result = create_contact_submission(
        name="Sam Rivera", email="sam.rivera@example.com", subject="Test subject", message="Test message."
    )
    assert result.success and result.submission_id is not None

    submission = crud.get_contact_submission(result.submission_id)
    assert submission is not None
    assert submission.name == "Sam Rivera"
    assert submission.status == "New"


def test_update_contact_submission_applies_classification():
    created = create_contact_submission(name="Sam Rivera", email="sam.rivera@example.com", subject="s", message="m")
    result = update_contact_submission(created.submission_id, category="Billing", priority="High")
    assert result.success

    submission = crud.get_contact_submission(created.submission_id)
    assert submission.category == "Billing"
    assert submission.priority == "High"


def test_update_contact_submission_unknown_id():
    result = update_contact_submission(999999, category="Billing")
    assert not result.success


def test_create_lead_generates_sequential_ids():
    first = create_lead(name="Test Lead One", email="lead1@example.com", service_interest="Retirement Planning")
    second = create_lead(name="Test Lead Two", email="lead2@example.com", service_interest="Retirement Planning")
    assert first.success and second.success
    assert first.lead_id != second.lead_id

    lead = crud.get_lead(first.lead_id)
    assert lead.name == "Test Lead One"
    assert lead.source == "Contact Form"


def test_process_contact_submission_non_lead_creates_task_not_lead(monkeypatch):
    monkeypatch.setattr(
        workflows,
        "classify_contact_submission",
        lambda subject, message: ClassificationResult(
            success=True, category="Technical Issue", priority="Medium", suggested_response="We're looking into it."
        ),
    )

    result = workflows.process_contact_submission(
        name="Taylor Kim", email="taylor.kim@example.com", subject="Site error", message="I got an error message."
    )

    assert result.success
    assert result.category == "Technical Issue"
    assert result.created_lead_id is None
    assert result.task_id is not None

    submission = crud.get_contact_submission(result.submission_id)
    assert submission.category == "Technical Issue"
    assert submission.ai_suggested_response == "We're looking into it."


def test_process_contact_submission_potential_lead_runs_full_automation(monkeypatch):
    monkeypatch.setattr(
        workflows,
        "classify_contact_submission",
        lambda subject, message: ClassificationResult(
            success=True,
            category="Potential Lead",
            priority="High",
            service_interest="Business Financial Consulting",
            suggested_response="We'd love to help your business.",
        ),
    )

    result = workflows.process_contact_submission(
        name="Morgan Blake",
        email="morgan.blake@example.com",
        subject="Interested in your business services",
        message="I run a small business and need financial consulting.",
        phone="555-0199",
    )

    assert result.success
    assert result.category == "Potential Lead"
    assert result.created_lead_id is not None
    assert result.task_id is None  # qualify_lead creates its own task, no duplicate

    lead = crud.get_lead(result.created_lead_id)
    assert lead is not None
    assert lead.service_interest == "Business Financial Consulting"
    assert lead.source == "Contact Form"

    assert result.lead_qualification is not None
    assert result.lead_qualification.success
    assert result.lead_qualification.task_id is not None
    assert result.lead_qualification.followup_id is not None

    submission = crud.get_contact_submission(result.submission_id)
    assert submission.lead_id == result.created_lead_id
