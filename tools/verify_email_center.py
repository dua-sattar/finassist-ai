"""Manual verification for Phase 18 (Email Center): compose, template,
AI-generate, edit, regenerate, and the Draft -> Approved -> Sent-simulated
lifecycle, all through the tools/ layer (no UI). Not a pytest suite (that's
covered separately in tests/test_email_tools.py)."""

import sys

from database.seed import main as seed_main
from tools.email_templates import render_template
from tools.email_tools import (
    compose_email,
    edit_email_draft,
    generate_followup_email,
    regenerate_email_draft,
)
from database import crud

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    seed_main()

    print("--- Compose (manual) ---")
    r = compose_email(subject="Test manual subject", body="Test manual body.", client_id="C1001", source="manual")
    assert r.success and r.followup_id is not None
    manual_id = r.followup_id
    print(f"OK: draft #{manual_id} created (manual)\n")

    print("--- Edit the manual draft ---")
    r = edit_email_draft(manual_id, subject="Edited subject", body="Edited body.")
    assert r.success
    edited = crud.list_followups(status="Draft")
    edited_row = next(f for f in edited if f.id == manual_id)
    assert edited_row.subject == "Edited subject"
    print(f"OK: draft #{manual_id} edited\n")

    print("--- Templates ---")
    subject, body = render_template(
        "Missing Document Request", recipient_name="Allison Hill", service="Investment Advisory", details="Proof of Address"
    )
    print(f"subject={subject!r}")
    assert "Allison Hill" in subject or "Allison Hill" in body
    r = compose_email(subject=subject, body=body, client_id="C1001", source="template")
    assert r.success
    print(f"OK: draft #{r.followup_id} created (template)\n")

    print("--- AI Generate ---")
    r = generate_followup_email(
        reason="Missing government ID", recipient_name="Noah Rhodes", context="Onboarding blocked.", client_id="C1002"
    )
    assert r.success and r.status == "Draft"
    ai_id = r.followup_id
    print(f"OK: draft #{ai_id} generated, subject={r.subject!r}\n")

    print("--- Regenerate the AI draft ---")
    before_subject = r.subject
    r2 = regenerate_email_draft(ai_id, reason="Missing government ID", recipient_name="Noah Rhodes", context="Onboarding blocked, second attempt.")
    assert r2.success
    print(f"OK: draft #{ai_id} regenerated, new subject={r2.subject!r}\n")

    print("--- Edit/regenerate refuse once no longer Draft ---")
    crud.approve_followup(ai_id)
    r3 = edit_email_draft(ai_id, subject="Should not work", body="Should not work")
    assert not r3.success, "editing an Approved followup should be refused"
    r4 = regenerate_email_draft(ai_id, reason="x", recipient_name="y")
    assert not r4.success, "regenerating an Approved followup should be refused"
    print("OK: edit/regenerate correctly refused once Approved\n")

    print("--- Full lifecycle: Draft -> Approved -> Sent-simulated ---")
    sent = crud.simulate_send(ai_id)
    assert sent is not None and sent.status == "Sent-simulated"
    print(f"OK: followup #{ai_id} is now Sent-simulated\n")

    print("--- Tab counts ---")
    print(f"Drafts: {len(crud.list_followups(status='Draft'))}")
    print(f"Approved (Follow-ups tab): {len(crud.list_followups(status='Approved'))}")
    print(f"Sent-simulated: {len(crud.list_followups(status='Sent-simulated'))}")

    print("\nAll Email Center checks passed.")


if __name__ == "__main__":
    main()
