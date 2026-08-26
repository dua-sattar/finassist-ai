"""Manual verification for Phase 7: call each of the 9 agent tools directly
against the seeded DB (no agent yet) and confirm typed outputs plus
ai_action_log rows. Not a pytest suite (that's Phase 15)."""

import sys

from database import crud
from database.seed import main as seed_main
from tools.crm_tools import get_client, get_lead, update_client, update_lead
from tools.document_tools import analyze_document, check_required_documents
from tools.email_tools import generate_followup_email
from tools.knowledge_tools import search_knowledge_base
from tools.task_tools import create_followup_task

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    seed_main()
    before_count = len(crud.list_ai_actions(limit=1000))

    print("--- search_knowledge_base ---")
    r = search_knowledge_base("What documents are required for client onboarding?")
    print(f"success={r.success} chunks={len(r.chunks)} top_source={r.chunks[0].source if r.chunks else None}")
    assert r.success and r.chunks

    print("\n--- get_client ---")
    r = get_client("C1002")
    print(f"success={r.success} found={r.found} name={r.name} onboarding_status={r.onboarding_status}")
    assert r.success and r.found

    print("\n--- get_client (missing) ---")
    r = get_client("C9999")
    print(f"success={r.success} found={r.found}")
    assert r.success and not r.found

    print("\n--- get_lead ---")
    r = get_lead("L1001")
    print(f"success={r.success} found={r.found} name={r.name} status={r.status}")
    assert r.success and r.found

    print("\n--- check_required_documents (C1002, expect missing Government-issued ID) ---")
    r = check_required_documents("C1002")
    print(f"success={r.success} all_satisfied={r.all_satisfied} missing={r.missing_categories}")
    for item in r.checklist:
        print(f"  [{'x' if item.satisfied else ' '}] {item.category} -> {item.matched_document_types}")
    assert r.success and r.missing_categories == ["Government-issued ID"]

    print("\n--- analyze_document (new upload simulation) ---")
    r = analyze_document(
        "data/synthetic/documents/C1003_bank_statement.pdf", client_id="C1003", filename="C1003_bank_statement.pdf"
    )
    print(f"success={r.success} document_id={r.document_id} type={r.document_type} missing={r.missing_fields}")
    assert r.success and r.document_id is not None

    print("\n--- update_client (harmless field) ---")
    r = update_client("C1002", assigned_advisor="Morgan Ellis")
    print(f"success={r.success} found={r.found} updated_fields={r.updated_fields}")
    assert r.success and r.found

    print("\n--- update_lead ---")
    r = update_lead("L1001", status="Contacted")
    print(f"success={r.success} found={r.found} updated_fields={r.updated_fields}")
    assert r.success and r.found

    print("\n--- create_followup_task ---")
    r = create_followup_task(
        description="Request Government ID from C1002", client_id="C1002", priority="High"
    )
    print(f"success={r.success} task_id={r.task_id} priority={r.priority}")
    assert r.success and r.task_id is not None

    print("\n--- generate_followup_email ---")
    r = generate_followup_email(
        reason="Missing government ID",
        recipient_name="Noah Rhodes",
        context="Onboarding cannot complete until this is received.",
        client_id="C1002",
    )
    print(f"success={r.success} followup_id={r.followup_id} status={r.status}")
    print(f"subject={r.subject!r}")
    assert r.success and r.status == "Draft"

    after_count = len(crud.list_ai_actions(limit=1000))
    new_actions = after_count - before_count
    print(f"\nai_action_log rows created this run: {new_actions}")
    recent = crud.list_ai_actions(limit=new_actions)
    tool_names = {a.tool_name for a in recent}
    print(f"tools represented in ai_action_log: {sorted(tool_names)}")

    expected_tools = {
        "search_knowledge_base",
        "get_client",
        "get_lead",
        "check_required_documents",
        "analyze_document",
        "update_client",
        "update_lead",
        "create_followup_task",
        "generate_followup_email",
    }
    missing_from_log = expected_tools - tool_names
    if missing_from_log:
        print(f"MISSING FROM LOG: {missing_from_log}")
    else:
        print("OK: all 9 tools logged an ai_action_log entry.")


if __name__ == "__main__":
    main()
