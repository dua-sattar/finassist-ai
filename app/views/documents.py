"""Document Analysis page: upload a PDF, identify the client, run the full
Phase 3/10 extraction + document-review pipeline, and show the results.
Phase 24 adds a Multi-Document Analysis tab for uploading several documents
for one client at once and checking cross-document consistency. Phase 25
adds a Document Comparison tab for diffing two documents field-by-field."""

import streamlit as st

from agent.workflows import analyze_multiple_documents, compare_documents, review_client_documents
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
        "Upload synthetic financial documents (PDF) to extract structured fields, generate an "
        "AI summary, and check them against the client's onboarding requirements."
    )

    single_tab, multi_tab, compare_tab = st.tabs(["Single Document", "Multi-Document Analysis", "Document Comparison"])

    with single_tab:
        _render_single_document()

    with multi_tab:
        _render_multi_document()

    with compare_tab:
        _render_comparison()


def _render_single_document() -> None:
    uploaded = st.file_uploader("Upload a PDF document", type=["pdf"], key="single-doc-uploader")

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

    selected_label = st.selectbox("Client", list(options.keys()), index=default_index, key="single-doc-client")
    client_id = options[selected_label]

    if uploaded is None:
        st.caption("Upload a document above, then click Analyze.")

    analyze_clicked = st.button("Analyze Document", type="primary", disabled=uploaded is None, key="single-doc-analyze")

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


def _render_multi_document() -> None:
    st.caption(
        "Upload several documents for the same client at once to check category coverage and "
        "consistency (client ID / name) across the whole batch."
    )

    try:
        options = _client_options()
    except Exception as exc:
        st.error(f"Could not load clients: {exc}")
        return

    if not options:
        st.warning("No clients found in the CRM yet.")
        return

    selected_label = st.selectbox("Client", list(options.keys()), key="multi-doc-client")
    client_id = options[selected_label]

    uploaded_files = st.file_uploader(
        "Upload PDF documents", type=["pdf"], accept_multiple_files=True, key="multi-doc-uploader"
    )

    analyze_clicked = st.button(
        "Analyze Documents", type="primary", disabled=not uploaded_files, key="multi-doc-analyze"
    )

    if not analyze_clicked:
        return

    files = [(f.getvalue(), f.name) for f in uploaded_files]

    with st.spinner(f"Analyzing {len(files)} document(s)..."):
        try:
            result = analyze_multiple_documents(client_id, files)
        except Exception as exc:
            st.error(f"Multi-document analysis failed: {exc}")
            return

    if not result.success:
        st.error(f"Could not complete multi-document analysis: {result.error}")
        return
    if not result.found:
        st.error(f"Client {client_id} not found.")
        return

    st.subheader("Documents in This Batch")
    for item in result.batch_items:
        with st.expander(f"{'✅' if item.success else '❌'} {item.filename} ({item.document_type})"):
            if item.success:
                st.json(item.extracted_fields)
                if item.missing_fields:
                    st.caption(f"Missing fields: {', '.join(item.missing_fields)}")
            else:
                st.warning(item.error or "Extraction failed.")

    st.subheader("Category Coverage")
    if result.missing_categories:
        st.warning(f"Missing categories: {', '.join(result.missing_categories)}")
    else:
        st.success("All required categories are represented in this batch.")

    st.subheader("Consistency Check")
    if result.client_id_mismatch:
        st.error(f"Client ID mismatch across documents: {', '.join(result.client_ids_seen)}")
    else:
        st.success("Client ID is consistent across the batch.")
    if result.name_mismatch:
        st.error(f"Client name mismatch across documents: {', '.join(result.names_seen)}")
    else:
        st.success("Client name is consistent across the batch.")

    render_status_badge(result.overall_status)

    st.markdown("**AI Observation**")
    st.info(result.ai_observation)

    st.markdown("**Recommended Action**")
    st.warning(result.recommended_action)

    with st.expander("Full report"):
        st.text(result.report)


def _render_comparison() -> None:
    st.caption(
        "Upload two documents for the same client -- e.g. two bank statements from different "
        "periods -- to see what changed between them, field by field."
    )

    try:
        options = _client_options()
    except Exception as exc:
        st.error(f"Could not load clients: {exc}")
        return

    if not options:
        st.warning("No clients found in the CRM yet.")
        return

    selected_label = st.selectbox("Client", list(options.keys()), key="compare-doc-client")
    client_id = options[selected_label]

    col1, col2 = st.columns(2)
    with col1:
        file_a = st.file_uploader("Document A", type=["pdf"], key="compare-doc-a")
    with col2:
        file_b = st.file_uploader("Document B", type=["pdf"], key="compare-doc-b")

    compare_clicked = st.button(
        "Compare Documents", type="primary", disabled=(file_a is None or file_b is None), key="compare-doc-analyze"
    )

    if not compare_clicked:
        return

    with st.spinner("Extracting and comparing..."):
        try:
            result = compare_documents(
                client_id, (file_a.getvalue(), file_a.name), (file_b.getvalue(), file_b.name)
            )
        except Exception as exc:
            st.error(f"Document comparison failed: {exc}")
            return

    if not result.success:
        st.error(f"Could not complete document comparison: {result.error}")
        return
    if not result.found:
        st.error(f"Client {client_id} not found.")
        return

    if not (result.document_a.success and result.document_b.success):
        if not result.document_a.success:
            st.error(f"Document A ({result.document_a.filename}) failed to extract: {result.document_a.error}")
        if not result.document_b.success:
            st.error(f"Document B ({result.document_b.filename}) failed to extract: {result.document_b.error}")
        st.info(result.ai_observation)
        return

    if result.document_type_mismatch:
        st.warning(
            f"Document types differ: **{result.document_a.document_type}** vs "
            f"**{result.document_b.document_type}** -- comparison may not be meaningful."
        )

    st.subheader("Field-by-Field Comparison")
    rows = [
        {
            "Field": c.field,
            "Document A": c.value_a if c.value_a is not None else "(not provided)",
            "Document B": c.value_b if c.value_b is not None else "(not provided)",
            "Changed": "Yes" if c.changed else "No",
            "Delta": c.delta if c.delta is not None else "",
        }
        for c in result.field_comparisons
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if result.changed_fields:
        st.warning(f"{len(result.changed_fields)} field(s) changed: {', '.join(result.changed_fields)}")
    else:
        st.success("No differences detected between the two documents.")

    st.markdown("**AI Observation**")
    st.info(result.ai_observation)

    st.markdown("**Recommended Action**")
    st.warning(result.recommended_action)

    with st.expander("Full report"):
        st.text(result.report)
