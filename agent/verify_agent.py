"""Manual verification for Phase 8: run the LangGraph agent through 3
scripted prompts and confirm the right tool(s) fire and the answer is
sensible. Not a pytest suite (that's Phase 15)."""

import sys

from database import crud
from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.graph import run_agent  # noqa: E402 (after stdout reconfigure)

SESSION_ID = "verify-agent-session"

PROMPTS = [
    "What documents are required for client onboarding?",
    "Can you check on client C1002 for me?",
    "Please create a follow-up task for C1002 to request their missing government ID.",
]


def main() -> None:
    seed_main()

    for prompt in PROMPTS:
        before_ids = {a.id for a in crud.list_ai_actions(limit=200)}

        print(f"USER: {prompt}")
        response = run_agent(SESSION_ID, prompt)
        print(f"ASSISTANT: {response}\n")

        after = crud.list_ai_actions(limit=200)
        new_actions = [a for a in after if a.id not in before_ids]
        tool_names = [a.tool_name for a in reversed(new_actions)]
        print(f"tools invoked: {tool_names}")
        print("-" * 70)


if __name__ == "__main__":
    main()
