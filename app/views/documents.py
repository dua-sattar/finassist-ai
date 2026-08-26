"""Document Analysis page: upload a PDF, identify the client, run the full
Phase 3/10 extraction + document-review pipeline, and show the results."""

import streamlit as st

from agent.workflows import review_client_documents
from app.components.status_badge import render_status_badge
from database import crud
from document_processing.extractor import extract_fields
from document_processing.parser import extract_text


def _client_options() -> dict[str, str]:
    clients = crud.list_clients()
    return {f"{c.client_id} -- {c.name}": c.client_id for c in clients}


def render() -> None:
    st.header("Document Analysis")
    st.caption(
        "Upload a synthetic financial document (PDF) to extract structured fields, generate an "
        "AI summary, and check it against the client's onboarding requirements."
    )

    uploaded = st.file_uploader("Upload a PDF document", type=["pdf"])

    try:
        options = _client_options()
    except Exception as exc:
        st.error(f"Could not load clients: {exc}")
        return

    default_index = 0
    detected_client_id = None

    if uploaded is not None:
        try:
            file_bytes = uploaded.getvalue()
            parsed = extract_text(file_bytes)
            if parsed.success:
                fields = extract_fields(parsed.text, document_type="")
                detected_client_id = fields.get("client_id")
        except Exception:
            detected_client_id = None

        if detected_client_id:
            for i, (_label, cid) in enumerate(options.items()):
                if cid == detected_client_id:
                    default_index = i
                    break
            st.info(f"Detected Client ID in document: **{detected_client_id}**")

    if not options:
        st.warning("No clients found in the CRM yet.")
        return

    selected_label = st.selectbox("Client", list(options.keys()), index=default_index)
    client_id = options[selected_label]

    if uploaded is None:
        st.caption("Upload a document above, then click Analyze.")

    analyze_clicked = st.button("Analyze Document", type="primary", disabled=uploaded is None)

    if not analyze_clicked:
        return

    with st.spinner("Extracting, validating, and summarizing..."):
        try:
            result = review_client_documents(
                client_id, new_document_source=uploaded.getvalue(), new_document_filename=uploaded.name
            )
        except Exception as exc:
            st.error(f"Document analysis failed: {exc}")
            return

    if not result.success:
        st.error(f"Could not complete document review: {result.error}")
        return

    if result.analysis is not None:
        st.subheader("Extracted Document")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Document Type:** {result.analysis.document_type}")
            render_status_badge("Received" if result.analysis.success else "Invalid")
        with col2:
            if result.analysis.missing_fields:
                st.markdown(f"**Missing Fields:** {', '.join(result.analysis.missing_fields)}")
            else:
                st.markdown("**Missing Fields:** none")

        st.markdown("**AI Summary**")
        st.info(result.analysis.summary or "(no summary available)")

        with st.expander("Extracted fields (raw)"):
            st.json(result.analysis.extracted_fields)

        if not result.analysis.success:
            st.warning(f"Extraction issue: {result.analysis.error}")

    st.subheader("Onboarding Document Review")
    cols = st.columns(len(result.checklist) or 1)
    for col, item in zip(cols, result.checklist):
        with col:
            st.markdown(("✅ " if item.satisfied else "❌ ") + item.category)

    status_col, _ = st.columns([1, 3])
    with status_col:
        render_status_badge(result.onboarding_status)

    st.text(result.report)

    if not result.all_satisfied:
        st.success(
            f"Follow-up task #{result.task_id} created and a draft email (#{result.followup_id}) "
            "is ready for approval on the Follow-ups page."
        )
