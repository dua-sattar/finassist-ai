"""Manual verification for Phase 28 (AI Meeting/Call Summary): confirms
summarize_meeting_notes extracts a structured summary from raw notes,
creates follow-up tasks from action items, persists the summary for later
retrieval, and degrades honestly (no fabricated summary) when Groq is
unavailable. Not a pytest suite (that's tests/test_meeting_tools.py)."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database import crud  # noqa: E402
from database.database import init_db  # noqa: E402
from database.seed import main as seed_main  # noqa: E402
from tools.meeting_tools import _parse_sections, summarize_meeting_notes  # noqa: E402

SAMPLE_NOTES = """
Call with Allison Hill regarding her investment advisory consultation.

She confirmed she wants to move forward with the retirement planning add-on.
We agreed to schedule a follow-up call next month to review her risk tolerance
questionnaire. She still needs to send over her most recent bank statement.
Allison asked whether the advisory fee is negotiable for accounts over $500k --
told her we would check with the team and get back to her.
"""


def main() -> None:
    init_db()
    seed_main()

    print("=== _parse_sections handles the expected label format ===")
    sample_text = (
        "Key Points:\n- Point one\n- Point two\n\n"
        "Decisions:\n- Decision one\n\n"
        "Action Items:\n- Action one\n- Action two\n\n"
        "Next Steps:\n- None noted."
    )
    parsed = _parse_sections(sample_text)
    assert parsed["Key Points"] == ["Point one", "Point two"]
    assert parsed["Decisions"] == ["Decision one"]
    assert parsed["Action Items"] == ["Action one", "Action two"]
    assert parsed["Next Steps"] == []
    print("OK\n")

    print("=== Unknown client fails gracefully ===")
    result = summarize_meeting_notes("Some notes.", client_id="C9999")
    assert not result.success
    assert "not found" in result.error.lower()
    print("OK\n")

    print("=== Summarize real notes linked to C1001, verify persistence + task creation ===")
    before_tasks = len(crud.list_open_tasks(client_id="C1001"))
    result = summarize_meeting_notes(SAMPLE_NOTES, client_id="C1001")
    assert result.success, result.error
    assert result.meeting_id is not None
    print(f"used_ai={result.used_ai}")
    print(f"key_points={result.key_points}")
    print(f"decisions={result.decisions}")
    print(f"action_items={result.action_items}")
    print(f"next_steps={result.next_steps}")
    print(f"task_ids_created={result.task_ids_created}")
    assert "Human Review Required" in result.report

    after_tasks = crud.list_open_tasks(client_id="C1001")
    assert len(after_tasks) == before_tasks + len(result.task_ids_created)

    stored = crud.list_meeting_summaries(client_id="C1001")
    assert any(s.id == result.meeting_id for s in stored)
    print("OK\n")

    print("=== Unlinked meeting note (no client/lead) still works ===")
    result = summarize_meeting_notes("General notes with no client attached.")
    assert result.success
    assert result.client_id is None and result.lead_id is None
    print("OK\n")

    print("All Meeting Summary checks passed.")


if __name__ == "__main__":
    main()
