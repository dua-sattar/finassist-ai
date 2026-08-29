"""LangGraph agent: a tool-calling loop over the Phase 7 tools, bound to a
Groq chat model. Entry point: run_agent(session_id, user_message) -> str.
"""

import logging
import os
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from agent import memory
from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState
from tools.anomaly_tools import detect_anomalies as _detect_anomalies
from tools.crm_tools import get_client as _get_client
from tools.crm_tools import get_lead as _get_lead
from tools.crm_tools import search_clients as _search_clients
from tools.crm_tools import search_leads as _search_leads
from tools.crm_tools import update_client as _update_client
from tools.crm_tools import update_lead as _update_lead
from tools.document_tools import analyze_document as _analyze_document
from tools.document_tools import check_required_documents as _check_required_documents
from tools.email_tools import generate_followup_email as _generate_followup_email
from tools.action_center_tools import get_action_center_summary as _get_action_center_summary
from tools.knowledge_tools import search_knowledge_base as _search_knowledge_base
from tools.search_tools import global_search as _global_search
from tools.summary_tools import generate_case_summary as _generate_case_summary
from tools.task_tools import complete_task as _complete_task
from tools.task_tools import create_followup_task as _create_followup_task

logger = logging.getLogger(__name__)

SYNTHETIC_DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"


# --- LangChain tool wrappers around the Phase 7 tools -----------------------
# Each wrapper exposes a plain-JSON-args signature for the model's function
# calling and returns the underlying typed result serialized to JSON, so the
# model can read fields like `success`/`found`/`missing_categories` back out.


@tool
def search_knowledge_base(query: str) -> str:
    """Search FinAssist AI's internal knowledge base (company policies: onboarding,
    required documents, payments, refunds, account closure, communication,
    escalation, privacy) for information relevant to the query. Always use this
    before answering any question about company policy -- never answer policy
    questions from memory."""
    return _search_knowledge_base(query).model_dump_json()


@tool
def get_client(client_id: str) -> str:
    """Look up a FinAssist AI client record by client_id (e.g. 'C1002'). Returns
    name, service, account_status, onboarding_status, assigned_advisor, and
    contact dates."""
    return _get_client(client_id).model_dump_json()


@tool
def get_lead(lead_id: str) -> str:
    """Look up a FinAssist AI lead record by lead_id (e.g. 'L1001'). Returns name,
    company, service_interest, engagement_level, information_complete, source,
    and status."""
    return _get_lead(lead_id).model_dump_json()


@tool
def search_clients(query: str) -> str:
    """Fuzzy-search FinAssist AI clients by name or email when you don't have
    an exact client_id (e.g. the user says 'find the client named Noah' or
    'look up noah.rhodes@example.com'). Returns up to 10 matches. Use
    get_client instead once you have the exact client_id."""
    return _search_clients(query).model_dump_json()


@tool
def search_leads(query: str) -> str:
    """Fuzzy-search FinAssist AI leads by name, company, or email when you
    don't have an exact lead_id. Returns up to 10 matches. Use get_lead
    instead once you have the exact lead_id."""
    return _search_leads(query).model_dump_json()


@tool
def global_search(query: str) -> str:
    """Broad search across clients, leads, documents, tasks, follow-up
    emails, the knowledge base, and AI-generated document summaries at once.
    Use this for vague or wide-scope requests (e.g. 'find anything about
    C1002' or 'search everything for proof of address') where you don't yet
    know which specific record type to look in. For a targeted lookup you
    already know the type of, prefer the more specific tool instead
    (get_client, search_clients, search_knowledge_base, etc.)."""
    return _global_search(query).model_dump_json()


@tool
def check_required_documents(client_id: str) -> str:
    """Check which of the 4 required onboarding documents (Government-issued ID,
    Proof of Address, Recent Financial Statement, Completed Application Form) a
    client has on file, and which are missing."""
    return _check_required_documents(client_id).model_dump_json()


@tool
def generate_case_summary(client_id: str) -> str:
    """Generate a full case summary for a client: service, onboarding status,
    required-documents checklist, recent activity (documents/tasks/follow-ups),
    an AI-narrated summary, and a recommended action. Read-only -- does not
    change anything. Use this when the user asks for an overview, status, or
    "what's going on with" a specific client, rather than calling several
    narrower tools yourself."""
    return _generate_case_summary(client_id).model_dump_json()


@tool
def get_action_center_summary() -> str:
    """Get a prioritized "what needs attention today" digest across the
    whole system: open follow-up tasks, clients with documents pending,
    draft emails awaiting approval, and new leads not yet qualified.
    Read-only. Use this when the user asks something broad like "what needs
    my attention", "what should I work on today", or "what's outstanding",
    rather than checking each area separately."""
    return _get_action_center_summary().model_dump_json()


@tool
def detect_anomalies(client_id: str) -> str:
    """Scan every document already on file for a client for data-quality
    anomalies: bank-statement math that doesn't reconcile, negative
    balances, expired government IDs, and client identity mismatches across
    documents. Read-only, runs against what's already stored -- no new
    upload needed. Use this when the user asks to check a client for
    inconsistencies, red flags, or data-quality issues."""
    return _detect_anomalies(client_id).model_dump_json()


@tool
def analyze_document(filename: str, client_id: str | None = None) -> str:
    """Analyze a document already present in the synthetic documents folder by
    filename, extracting its type, structured fields, missing fields, and an AI
    summary, and recording it in the CRM."""
    path = SYNTHETIC_DOCUMENTS_DIR / filename
    return _analyze_document(path, client_id=client_id, filename=filename).model_dump_json()


@tool
def update_client(
    client_id: str,
    account_status: str | None = None,
    onboarding_status: str | None = None,
    assigned_advisor: str | None = None,
) -> str:
    """Update a client's account_status, onboarding_status, and/or
    assigned_advisor. Only pass the fields that should change."""
    return _update_client(
        client_id,
        account_status=account_status,
        onboarding_status=onboarding_status,
        assigned_advisor=assigned_advisor,
    ).model_dump_json()


@tool
def update_lead(
    lead_id: str,
    status: str | None = None,
    engagement_level: str | None = None,
    information_complete: bool | None = None,
) -> str:
    """Update a lead's status, engagement_level, and/or information_complete.
    Only pass the fields that should change."""
    return _update_lead(
        lead_id,
        status=status,
        engagement_level=engagement_level,
        information_complete=information_complete,
    ).model_dump_json()


@tool
def create_followup_task(
    description: str,
    task_type: str = "follow_up",
    client_id: str | None = None,
    lead_id: str | None = None,
    priority: str | None = None,
) -> str:
    """Create a follow-up task for a human advisor, tied to a client and/or lead.
    Use this whenever a document is missing, a lead needs advisor attention, or
    any other action requires human follow-up."""
    return _create_followup_task(
        description=description, task_type=task_type, client_id=client_id, lead_id=lead_id, priority=priority
    ).model_dump_json()


@tool
def complete_task(task_id: int) -> str:
    """Mark a follow-up task as completed. Only use this when the user
    explicitly confirms the underlying work is done."""
    return _complete_task(task_id).model_dump_json()


@tool
def generate_followup_email(
    reason: str,
    recipient_name: str,
    context: str = "",
    client_id: str | None = None,
    lead_id: str | None = None,
) -> str:
    """Draft a follow-up email to a client or lead. The email is ALWAYS saved as
    a draft pending human approval -- it is never sent automatically. Use this
    when a client needs to be asked for missing information/documents, or a
    lead needs follow-up outreach."""
    return _generate_followup_email(
        reason=reason, recipient_name=recipient_name, context=context, client_id=client_id, lead_id=lead_id
    ).model_dump_json()


TOOLS = [
    search_knowledge_base,
    get_client,
    get_lead,
    search_clients,
    search_leads,
    global_search,
    check_required_documents,
    generate_case_summary,
    get_action_center_summary,
    detect_anomalies,
    analyze_document,
    update_client,
    update_lead,
    create_followup_task,
    complete_task,
    generate_followup_email,
]


def _build_model():
    api_key = os.getenv("GROQ_API_KEY")
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    llm = ChatGroq(api_key=api_key, model=model_name, temperature=0.2)
    return llm.bind_tools(TOOLS)


def _agent_node(state: AgentState) -> dict:
    model = _build_model()
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    response = model.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


# Explicit rather than relying on ToolNode's default error handler: any
# exception during tool invocation -- including malformed/invalid arguments
# the model generates, which surface as a schema ValidationError -- becomes
# an error ToolMessage fed back to the model instead of crashing the run.
TOOL_NODE = ToolNode(TOOLS, handle_tool_errors=True)


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", TOOL_NODE)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_agent(session_id: str, user_message: str) -> str:
    """Run one turn of the agent: load history, invoke the graph (looping
    through any tool calls), persist the new turns, and return the final
    assistant text."""
    graph = get_graph()
    history = memory.load_history(session_id)
    messages = [*history, HumanMessage(content=user_message)]

    try:
        result = graph.invoke({"messages": messages, "session_id": session_id})
        response_text = result["messages"][-1].content
    except Exception as exc:
        logger.warning("Agent run failed for session %s: %s", session_id, exc)
        response_text = (
            "Sorry, something went wrong while processing that request. "
            "Please try again or contact a human advisor if the issue persists."
        )

    memory.persist_turn(session_id, "user", user_message)
    memory.persist_turn(session_id, "assistant", response_text)

    return response_text
