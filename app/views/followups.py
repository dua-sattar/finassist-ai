"""Tasks & Follow-ups page (spec sections 20-21): create tasks manually
(the AI creates them automatically too), complete them, and see them
grouped by Overdue / Due Today / Upcoming / Completed. Email drafts live on
the dedicated Email Center page (Phase 18), not here.

No background scheduler/reminder job is implemented -- Streamlit Community
Cloud has no persistent runtime to host one, and the spec only asks for
that "if true scheduled automation is implemented". Due/overdue status is
instead computed live from due_date every time the page loads, which is the
honest scope for this deployment model.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.components.status_badge import render_status_badge
from database import crud
from tools.task_tools import complete_task, create_followup_task


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


def _render_create_task_form() -> None:
    with st.expander("➕ Create a new task"):
        description = st.text_input("Description", key="newtask-description")
        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1, key="newtask-priority")
        with col2:
            due = st.date_input("Due date", value=date.today() + timedelta(days=3), key="newtask-due")

        client_id, lead_id = _client_lead_picker("newtask")

        if st.button("Create Task", type="primary", disabled=not description, key="newtask-submit"):
            result = create_followup_task(
                description=description,
                task_type="manual",
                client_id=client_id,
                lead_id=lead_id,
                priority=priority,
                due_date=due,
            )
            if result.success:
                st.success(f"Task #{result.task_id} created.")
                st.rerun()
            else:
                st.error(f"Could not create task: {result.error}")


def _render_open_task_row(t) -> None:
    col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
    with col1:
        who = t.client_id or t.lead_id or ""
        label = f"**#{t.id}** {t.description}"
        st.markdown(label + (f"  \n*{who} · {t.task_type}*" if who else f"  \n*{t.task_type}*"))
    with col2:
        render_status_badge(t.priority)
    with col3:
        st.caption(f"Due: {t.due_date}" if t.due_date else "No due date")
    with col4:
        if st.button("Complete", key=f"complete-{t.id}"):
            result = complete_task(t.id)
            if not result.success:
                st.error(result.error)
            st.rerun()


def _render_open_task_group(title: str, tasks: list, empty_caption: str = "None.") -> None:
    st.subheader(f"{title} ({len(tasks)})")
    if not tasks:
        st.caption(empty_caption)
        return
    for t in tasks:
        _render_open_task_row(t)
    st.divider()


def render() -> None:
    st.header("Tasks & Follow-ups")
    st.caption("Tasks created by the AI agent or manually. Email drafts live in the Email Center.")

    _render_create_task_form()
    st.divider()

    try:
        all_tasks = crud.list_tasks()
    except Exception as exc:
        st.error(f"Could not load tasks: {exc}")
        return

    today = date.today()
    open_tasks = [t for t in all_tasks if t.status == "Open"]
    completed_tasks = [t for t in all_tasks if t.status == "Completed"]

    overdue = [t for t in open_tasks if t.due_date and t.due_date < today]
    due_today = [t for t in open_tasks if t.due_date and t.due_date == today]
    upcoming = [t for t in open_tasks if t.due_date and t.due_date > today]
    no_due_date = [t for t in open_tasks if not t.due_date]

    if overdue:
        st.error(f"🔴 {len(overdue)} task(s) overdue -- see below.")

    _render_open_task_group("Overdue", overdue)
    _render_open_task_group("Due Today", due_today)
    _render_open_task_group("Upcoming", upcoming)
    if no_due_date:
        _render_open_task_group(
            "No Due Date", no_due_date, empty_caption="None."
        )

    st.subheader(f"Completed ({len(completed_tasks)})")
    if not completed_tasks:
        st.caption("None yet.")
        return
    rows = [
        {
            "Task ID": t.id,
            "Type": t.task_type,
            "Client": t.client_id or "",
            "Lead": t.lead_id or "",
            "Description": t.description,
            "Created": t.created_at,
        }
        for t in completed_tasks
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
