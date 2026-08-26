"""Conversation memory: loads/persists agent turns via the SQLite-backed
conversations table (database/crud.py), not LangGraph's opaque checkpointer,
so history stays visible/queryable in the CRM dashboard.
"""

from langchain_core.messages import AIMessage, HumanMessage

from database import crud

# Cap replayed history to control token cost per agent turn (Phase 13 tunes this further).
DEFAULT_HISTORY_LIMIT = 20


def load_history(session_id: str, limit: int = DEFAULT_HISTORY_LIMIT) -> list:
    """Load a session's prior turns as LangChain messages, oldest first."""
    turns = crud.list_conversation_turns(session_id, limit=limit)
    messages = []
    for turn in turns:
        if turn.role == "user":
            messages.append(HumanMessage(content=turn.content))
        elif turn.role == "assistant":
            messages.append(AIMessage(content=turn.content))
    return messages


def persist_turn(session_id: str, role: str, content: str) -> None:
    crud.log_conversation_turn(session_id, role, content)
