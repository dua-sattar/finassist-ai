"""Phase 13 verification: memory correctness.

1. History capping -- load_history returns only the most recent N turns,
   still in chronological order, when a session has more than the cap.
2. Reference resolution -- the spec's own two-turn example ("What documents
   do I need?" then "I already uploaded the statement.") run through the
   real agent in the same session_id: the second answer must correctly
   understand "the statement" refers to the financial statement requirement
   raised in the first turn, not ask the user to clarify from scratch.

Not a pytest suite (that's Phase 15)."""

import sys
import uuid

from database import crud
from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent import memory  # noqa: E402
from agent.graph import run_agent  # noqa: E402


def check_history_cap() -> None:
    print("--- History capping ---")
    session_id = f"verify-memory-cap-{uuid.uuid4().hex[:8]}"

    for i in range(25):
        role = "user" if i % 2 == 0 else "assistant"
        crud.log_conversation_turn(session_id, role, f"turn-{i}")

    loaded = memory.load_history(session_id, limit=20)
    contents = [m.content for m in loaded]

    assert len(loaded) == 20, f"expected 20 messages, got {len(loaded)}"
    assert contents[0] == "turn-5", f"expected oldest kept turn to be turn-5, got {contents[0]}"
    assert contents[-1] == "turn-24", f"expected newest turn to be turn-24, got {contents[-1]}"
    assert contents == sorted(contents, key=lambda c: int(c.split("-")[1])), "history is not chronological"
    print(f"OK: 25 turns logged, load_history(limit=20) returned {len(loaded)} turns, "
          f"chronological, oldest kept = {contents[0]!r}, newest = {contents[-1]!r}.\n")


def check_reference_resolution() -> None:
    print("--- Reference resolution (spec's own two-turn example) ---")
    session_id = f"verify-memory-refs-{uuid.uuid4().hex[:8]}"

    q1 = "What documents do I need?"
    a1 = run_agent(session_id, q1)
    print(f"USER: {q1}\nASSISTANT: {a1}\n")

    q2 = "I already uploaded the statement."
    a2 = run_agent(session_id, q2)
    print(f"USER: {q2}\nASSISTANT: {a2}\n")

    lower = a2.lower()
    understood = "statement" in lower and ("financial" in lower or "already" in lower or "noted" in lower)
    asks_for_clarification = "which statement" in lower or "what statement" in lower or "clarify" in lower

    print(f"mentions statement context appropriately: {understood}")
    print(f"asks for clarification (would indicate lost context): {asks_for_clarification}")
    assert understood and not asks_for_clarification, (
        "second answer does not appear to reference the prior turn's context"
    )
    print("OK: second answer correctly builds on the first turn's context.")


def main() -> None:
    seed_main()
    check_history_cap()
    check_reference_resolution()


if __name__ == "__main__":
    main()
