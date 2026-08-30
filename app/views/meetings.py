"""Meeting Summaries page (spec section 25): paste raw meeting/call notes
and get a structured AI summary -- key points, decisions, action items
(auto-created as follow-up tasks), and next steps. Past summaries for a
selected client/lead stay retrievable below."""

import json

import streamlit as st

from database import crud
from tools.meeting_tools import summarize_meeting_notes


def _client_lead_picker(key_prefix: str) -> tuple[str | None, str | None]:
    link_type = st.radio("Link to (optional)", ["None", "Client", "Lead"], key=f"{key_prefix}-linktype", horizontal=True)

    if link_type == "Client":
        clients = crud.list_clients()
        options = {f"{c.client_id} -- {c.name}": c.client_id for c in clients}
        if not options:
            st.warning("No clients found.")
            return None, None
        label = st.selectbox("Client", list(options.keys()), key=f"{key_prefix}-client")
        return options[label], None

    if link_type == "Lead":
        leads = crud.list_leads()
        options = {f"{lead.lead_id} -- {lead.name}": lead.lead_id for lead in leads}
        if not options:
            st.warning("No leads found.")
            return None, None
        label = st.selectbox("Lead", list(options.keys()), key=f"{key_prefix}-lead")
        return None, options[label]

    return None, None


def _render_new_summary_form() -> None:
    raw_notes = st.text_area(
        "Meeting / call notes",
        height=200,
        placeholder="Paste raw notes from a client or lead meeting or call here...",
        key="meeting-notes-input",
    )
    client_id, lead_id = _client_lead_picker("meeting")

    if st.button("Summarize Meeting", type="primary", disabled=not raw_notes.strip()):
        with st.spinner("Extracting key points, decisions, action items, and next steps..."):
            result = summarize_meeting_notes(raw_notes, client_id=client_id, lead_id=lead_id)
        st.session_state["last_meeting_summary"] = result
        st.rerun()

    result = st.session_state.get("last_meeting_summary")
    if result is None:
        return

    if not result.success:
        st.error(f"Could not summarize meeting: {result.error}")
        return

    if not result.used_ai:
        st.warning(
            "AI summarization was unavailable for this note (no API key configured, or the call "
            "failed) -- the raw notes were still saved. Please review them manually below."
        )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Key Points**")
        st.markdown("\n".join(f"- {p}" for p in result.key_points) or "_None noted._")
        st.markdown("**Decisions**")
        st.markdown("\n".join(f"- {d}" for d in result.decisions) or "_None noted._")
    with col2:
        st.markdown("**Action Items**")
        st.markdown("\n".join(f"- {a}" for a in result.action_items) or "_None noted._")
        st.markdown("**Next Steps**")
        st.markdown("\n".join(f"- {n}" for n in result.next_steps) or "_None noted._")

    if result.task_ids_created:
        st.success(
            f"{len(result.task_ids_created)} follow-up task(s) created from action items: "
            f"{', '.join(f'#{t}' for t in result.task_ids_created)}. See the Follow-ups page."
        )

    with st.expander("Full report"):
        st.text(result.report)


def _render_past_summaries() -> None:
    st.divider()
    st.subheader("Past Meeting Summaries")

    client_id, lead_id = _client_lead_picker("meeting-history")
    if not client_id and not lead_id:
        st.caption("Select a client or lead above to see their past meeting summaries.")
        return

    try:
        summaries = crud.list_meeting_summaries(client_id=client_id, lead_id=lead_id)
    except Exception as exc:
        st.error(f"Could not load past summaries: {exc}")
        return

    if not summaries:
        st.caption("No meeting summaries recorded yet.")
        return

    for s in summaries:
        key_points = json.loads(s.key_points_json)
        action_items = json.loads(s.action_items_json)
        with st.expander(f"{s.created_at:%Y-%m-%d %H:%M} -- {len(action_items)} action item(s)"):
            st.markdown("**Key Points**")
            st.markdown("\n".join(f"- {p}" for p in key_points) or "_None noted._")
            st.markdown("**Action Items**")
            st.markdown("\n".join(f"- {a}" for a in action_items) or "_None noted._")
            st.markdown("**Raw Notes**")
            st.text(s.raw_notes)


def render() -> None:
    st.header("Meeting Summaries")
    st.caption(
        "Paste raw meeting or call notes to get a structured AI summary. Action items become "
        "follow-up tasks automatically."
    )

    _render_new_summary_form()
    _render_past_summaries()
