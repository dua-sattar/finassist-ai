"""Global Search page: one query, searched across clients, leads,
documents, tasks, follow-ups, the knowledge base, and AI-generated document
summaries at once (spec section 22)."""

import streamlit as st

from tools.search_tools import ALL_CATEGORIES, global_search

_CATEGORY_ICON = {
    "Clients": "🧑‍💼",
    "Leads": "🎯",
    "Documents": "📄",
    "Tasks": "✅",
    "Follow-ups": "📧",
    "Knowledge Base": "📚",
    "AI Summaries": "🤖",
}


def render() -> None:
    st.header("Global Search")
    st.caption("Search across clients, leads, documents, tasks, follow-ups, the knowledge base, and AI summaries.")

    query = st.text_input("Search", placeholder="e.g. C1002, proof of address, refund policy...")
    categories = st.multiselect("Filter by record type", ALL_CATEGORIES, default=ALL_CATEGORIES)

    if not query:
        st.caption("Enter a search term above.")
        return

    with st.spinner("Searching..."):
        result = global_search(query, categories=categories or None)

    if not result.success:
        st.error(f"Search failed: {result.error}")
        return

    if not result.results:
        st.info(f"No results found for {query!r}.")
        return

    total = len(result.results)
    nonzero_categories = sum(1 for count in result.counts_by_category.values() if count > 0)
    st.caption(
        f"{total} result{'s' if total != 1 else ''} across "
        f"{nonzero_categories} categor{'ies' if nonzero_categories != 1 else 'y'}."
    )

    for category in ALL_CATEGORIES:
        items = [r for r in result.results if r.category == category]
        if not items:
            continue

        icon = _CATEGORY_ICON.get(category, "")
        st.subheader(f"{icon} {category} ({len(items)})")
        for item in items:
            st.markdown(f"**{item.title}**")
            st.caption(item.snippet)
        st.divider()
