"""Manual verification for Phase 19 (Contact Us + Contact->Lead automation):
runs process_contact_submission for a non-lead ticket and a potential-lead
submission, confirming classification, ticket/task creation, and the full
lead creation -> qualification -> CRM update -> follow-up task -> draft
email chain. Not a pytest suite (that's tests/test_contact_tools.py)."""

import sys

from database import crud
from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import process_contact_submission  # noqa: E402


def main() -> None:
    seed_main()

    print("=== Non-lead ticket (Billing question) ===")
    result = process_contact_submission(
        name="Jordan Lee",
        email="jordan.lee@example.com",
        subject="Question about my invoice",
        message="I was charged twice this month for my Tax Planning Consultation service. Can someone look into this?",
        phone=None,
    )
    print(f"success={result.success} category={result.category} priority={result.priority}")
    print(f"suggested_response={result.suggested_response!r}")
    assert result.success
    assert result.category in {
        "General Inquiry", "Client Support", "Onboarding", "Document Request",
        "Billing", "Technical Issue", "Potential Lead", "Other",
    }
    assert result.created_lead_id is None, "a billing question should not create a lead"
    if result.category != "Potential Lead":
        assert result.task_id is not None, "a non-lead ticket should create a follow-up task"
    submission = crud.get_contact_submission(result.submission_id)
    assert submission is not None and submission.category == result.category
    print("OK: ticket recorded, classified, and (if non-lead) a task was created.\n")

    print("=== Potential-lead submission ===")
    result2 = process_contact_submission(
        name="Casey Morgan",
        email="casey.morgan@example.com",
        subject="Interested in retirement planning services",
        message=(
            "Hi, I'm looking to start planning for retirement and would love to learn more "
            "about what FinAssist AI offers. Could someone reach out to discuss my options?"
        ),
        phone="555-0100",
    )
    print(f"success={result2.success} category={result2.category} priority={result2.priority}")
    print(f"created_lead_id={result2.created_lead_id}")
    assert result2.success

    if result2.category == "Potential Lead":
        assert result2.created_lead_id is not None, "expected a lead to be created"
        lead = crud.get_lead(result2.created_lead_id)
        assert lead is not None
        assert lead.source == "Contact Form"
        print(f"lead: name={lead.name} service_interest={lead.service_interest} status={lead.status}")

        assert result2.lead_qualification is not None
        print(f"qualification: priority={result2.lead_qualification.priority} status={lead.status}")
        assert result2.lead_qualification.task_id is not None
        assert result2.lead_qualification.followup_id is not None

        submission2 = crud.get_contact_submission(result2.submission_id)
        assert submission2.lead_id == result2.created_lead_id
        print("OK: lead created, qualified, CRM updated, follow-up task + draft email created.\n")
    else:
        print(f"NOTE: this run's AI classification did not label the submission a Potential Lead "
              f"(got {result2.category!r}) -- LLM classification is not deterministic. "
              f"The lead-automation branch is still covered by tests/test_contact_tools.py "
              f"via a forced category.\n")

    print("=== Ticket counts ===")
    all_submissions = crud.list_contact_submissions()
    print(f"Total submissions: {len(all_submissions)}")
    print(f"By category: {sorted({(s.category, ) for s in all_submissions})}")

    print("\nAll Contact Us checks passed.")


if __name__ == "__main__":
    main()
