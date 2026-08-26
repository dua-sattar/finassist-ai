"""Phase 12 verification: the followup Draft -> Approved -> Sent-simulated
gate. Generates a real draft via Phase 10's document-review workflow, then
confirms simulate_send refuses it while still Draft and only succeeds after
approve_followup. Not a pytest suite (that's Phase 15)."""

import sys

from database import crud
from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import review_client_documents  # noqa: E402


def main() -> None:
    seed_main()

    print("=== Generate a real draft via the Phase 10 workflow (C1002) ===")
    review = review_client_documents("C1002")
    assert review.followup_id is not None, "expected review_client_documents to draft a followup"
    followup_id = review.followup_id
    print(f"followup_id={followup_id}\n")

    print("=== Attempt simulate_send while still Draft ===")
    result = crud.simulate_send(followup_id)
    assert result is None, "simulate_send must refuse a Draft followup"
    print("OK: simulate_send correctly refused (returned None).\n")

    print("=== Approve, then simulate_send ===")
    approved = crud.approve_followup(followup_id)
    assert approved is not None and approved.status == "Approved"
    print(f"status after approve_followup: {approved.status}")

    sent = crud.simulate_send(followup_id)
    assert sent is not None and sent.status == "Sent-simulated"
    print(f"status after simulate_send: {sent.status}\n")
    print("OK: simulate_send succeeded only after approval.\n")

    print("=== Unknown followup_id ===")
    missing = crud.simulate_send(999999)
    assert missing is None
    print("OK: unknown followup handled gracefully, no crash.")


if __name__ == "__main__":
    main()
