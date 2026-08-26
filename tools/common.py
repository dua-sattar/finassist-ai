"""Shared helper for agent tools: log every tool invocation to ai_action_log.

Used by every module in tools/ so the Phase 14 AI Actions dashboard view has
a real audit trail from the moment tools exist.
"""

import logging

from database import crud

logger = logging.getLogger(__name__)


def log_action(
    tool_name: str,
    input_summary: str,
    result_summary: str,
    status: str = "success",
    human_approval_status: str | None = None,
) -> None:
    """Record a tool call. Never raises -- a logging failure must not break
    the tool's actual result."""
    try:
        crud.log_ai_action(
            tool_name=tool_name,
            input_summary=input_summary,
            result_summary=result_summary,
            status=status,
            human_approval_status=human_approval_status,
        )
    except Exception as exc:
        logger.warning("Failed to log AI action for %s: %s", tool_name, exc)
