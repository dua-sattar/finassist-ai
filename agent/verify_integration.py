"""Phase 9 integration/hardening verification: re-run the Phase 5 canonical
RAG questions and Phase 8 scripted prompts through the FULL agent graph
end-to-end, confirm citations surface in the agent's own answers, and
directly test the malformed-tool-call-arguments guard. Not a pytest suite
(that's Phase 15)."""

import sys

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph

from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.graph import TOOL_NODE, TOOLS, run_agent  # noqa: E402
from agent.state import AgentState  # noqa: E402

SESSION_ID = "verify-integration-session"

# (question, expected source filename or None for out-of-scope)
CANONICAL_QUESTIONS = [
    ("What documents are required for client onboarding?", "required_documents.md"),
    ("What is FinAssist AI's refund policy?", "refund_policy.md"),
    ("How do I close my FinAssist AI account?", "account_closure.md"),
    ("What services does FinAssist AI offer?", "services.md"),
    ("What happens if I miss a payment?", "payment_policy.md"),
    ("What's the weather like in Paris today?", None),
]

SCRIPTED_PROMPTS = [
    "What documents are required for client onboarding?",
    "Can you check on client C1002 for me?",
    "Please create a follow-up task for C1002 to request their missing government ID.",
]


def check_tool_registration() -> None:
    print("--- Tool registration ---")
    names = sorted(t.name for t in TOOLS)
    print(f"{len(names)} tools registered: {names}")
    expected = {
        "search_knowledge_base",
        "get_client",
        "get_lead",
        "check_required_documents",
        "analyze_document",
        "propose_client_update",
        "propose_lead_update",
        "create_followup_task",
        "generate_followup_email",
    }
    missing = expected - set(names)
    assert not missing, f"missing tools: {missing}"
    print(f"OK: all {len(expected)} originally-checked tools still registered (now {len(names)} total).\n")


def check_malformed_tool_call_guard() -> None:
    print("--- Malformed tool-call arguments guard ---")
    # Fabricate a tool call with a wrong argument name (missing the required
    # client_id) to force a schema ValidationError inside ToolNode, without
    # depending on the model spontaneously generating bad arguments. Wrapped
    # in its own tiny compiled graph so ToolNode gets the runtime context it
    # needs (calling ToolNode.invoke() bare, outside a compiled graph, raises
    # an unrelated "missing config key" error from LangGraph's Pregel layer).
    bad_call = AIMessage(
        content="",
        tool_calls=[{"name": "get_client", "args": {"wrong_arg": 123}, "id": "test-call-1"}],
    )
    probe = StateGraph(AgentState)
    probe.add_node("tools", TOOL_NODE)
    probe.set_entry_point("tools")
    probe.set_finish_point("tools")
    compiled_probe = probe.compile()

    try:
        result = compiled_probe.invoke({"messages": [bad_call], "session_id": "guard-test"})
        tool_message = result["messages"][-1]
        print(f"OK: ToolNode did not raise. Returned error content: {tool_message.content[:200]!r}")
    except Exception as exc:
        print(f"FAIL: ToolNode raised instead of returning an error message: {exc}")
        raise
    print()


def check_rag_citations() -> None:
    print("--- Full-graph RAG citation check ---")
    correct = 0
    for question, expected_source in CANONICAL_QUESTIONS:
        answer = run_agent(SESSION_ID, question)
        cited = expected_source is not None and expected_source in answer
        if expected_source is not None:
            correct += int(cited)
            status = "OK" if cited else "MISS"
            print(f"[{status}] {question!r} -> expected citation of {expected_source!r} present={cited}")
        else:
            print(f"[out-of-scope] {question!r} -> answer: {answer[:150]!r}")
    in_scope_total = sum(1 for _, s in CANONICAL_QUESTIONS if s is not None)
    print(f"\nCitation accuracy: {correct}/{in_scope_total} in-scope answers cited their expected source.\n")


def check_scripted_prompts() -> None:
    print("--- Scripted prompts through full graph ---")
    for prompt in SCRIPTED_PROMPTS:
        answer = run_agent(SESSION_ID, prompt)
        print(f"USER: {prompt}\nASSISTANT: {answer[:300]}\n{'-' * 60}")


def main() -> None:
    seed_main()
    check_tool_registration()
    check_malformed_tool_call_guard()
    check_rag_citations()
    check_scripted_prompts()


if __name__ == "__main__":
    main()
