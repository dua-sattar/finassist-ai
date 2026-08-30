"""Pending Approvals page (Phase 30): review and approve/reject CRM field
changes the chat agent has proposed via propose_client_update /
propose_lead_update. Extends the same Draft -> Approved pattern already
used for email follow-ups (see Email Center) to client/lead record
updates -- nothing the chat agent proposes takes effect until a human
approves it here."""

import json

import streamlit as st

from database import crud


def _entity_label(change) -> str:
    if change.entity_type == "client":
        client = crud.get_client(change.entity_id)
        name = client.name if client else "unknown"
    else:
        lead = crud.get_lead(change.entity_id)
        name = lead.name if lead else "unknown"
    return f"{change.entity_id} -- {name}"


def _current_value(change, field: str):
    if change.entity_type == "client":
        entity = crud.get_client(change.entity_id)
    else:
        entity = crud.get_lead(change.entity_id)
    return getattr(entity, field, None) if entity else None


def _render_pending_change(change) -> None:
    fields = json.loads(change.field_changes_json)
    entity_kind = "Client" if change.entity_type == "client" else "Lead"

    with st.expander(f"{entity_kind}: {_entity_label(change)} -- proposed {change.created_at:%Y-%m-%d %H:%M}"):
        st.markdown(f"**Reason:** {change.reason}")
        st.markdown("**Proposed Changes:**")
        for field, new_value in fields.items():
            current_value = _current_value(change, field)
            st.markdown(f"- `{field}`: {current_value} → **{new_value}**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve", key=f"approve-change-{change.id}", type="primary"):
                try:
                    result = crud.approve_pending_change(change.id)
                except Exception as exc:
                    st.error(f"Could not approve: {exc}")
                else:
                    if result is None:
                        st.error("Could not approve -- the change may have already been decided.")
                    else:
                        st.rerun()
        with col2:
            if st.button("Reject", key=f"reject-change-{change.id}"):
                try:
                    result = crud.reject_pending_change(change.id)
                except Exception as exc:
                    st.error(f"Could not reject: {exc}")
                else:
                    if result is None:
                        st.error("Could not reject -- the change may have already been decided.")
                    else:
                        st.rerun()


def _render_decided_history() -> None:
    st.divider()
    st.subheader("Recently Decided")
    try:
        approved = crud.list_pending_changes(status="Approved")[:5]
        rejected = crud.list_pending_changes(status="Rejected")[:5]
    except Exception as exc:
        st.error(f"Could not load history: {exc}")
        return

    decided = sorted(approved + rejected, key=lambda c: c.decided_at or c.created_at, reverse=True)[:10]
    if not decided:
        st.caption("No changes decided yet.")
        return

    for change in decided:
        icon = "✅" if change.status == "Approved" else "❌"
        st.markdown(f"{icon} **{change.status}** -- {_entity_label(change)}: {change.reason}")


def render() -> None:
    st.header("Pending Approvals")
    st.caption(
        "CRM changes proposed by the AI assistant during chat never take effect immediately -- "
        "review and approve or reject them here."
    )

    try:
        pending = crud.list_pending_changes(status="Pending")
    except Exception as exc:
        st.error(f"Could not load pending changes: {exc}")
        return

    if not pending:
        st.info("No pending changes awaiting approval.")
    else:
        for change in pending:
            _render_pending_change(change)

    _render_decided_history()
