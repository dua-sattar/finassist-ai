"""Small colored status badge, reused across the clients, leads, followups,
documents, and AI actions pages."""

import streamlit as st

_COLORS = {
    # generic
    "active": ("#e6f4ea", "#1e7e34"),
    "complete": ("#e6f4ea", "#1e7e34"),
    "approved": ("#e6f4ea", "#1e7e34"),
    "sent-simulated": ("#e6f4ea", "#1e7e34"),
    "qualified": ("#e6f4ea", "#1e7e34"),
    "received": ("#e6f4ea", "#1e7e34"),
    "success": ("#e6f4ea", "#1e7e34"),
    "high": ("#fdecea", "#c0392b"),
    "pending": ("#fff4e0", "#a86400"),
    "documents pending": ("#fff4e0", "#a86400"),
    "draft": ("#fff4e0", "#a86400"),
    "in review": ("#fff4e0", "#a86400"),
    "medium": ("#fff4e0", "#a86400"),
    "new": ("#e8eefc", "#2955a3"),
    "contacted": ("#e8eefc", "#2955a3"),
    "open": ("#e8eefc", "#2955a3"),
    "low": ("#eceff1", "#546e7a"),
    "closed": ("#eceff1", "#546e7a"),
    "unqualified": ("#eceff1", "#546e7a"),
    "invalid": ("#fdecea", "#c0392b"),
    "error": ("#fdecea", "#c0392b"),
    "n/a": ("#eceff1", "#546e7a"),
}
_DEFAULT_COLOR = ("#eceff1", "#37474f")


def badge_html(label: str | None) -> str:
    text = label if label else "N/A"
    bg, fg = _COLORS.get(text.strip().lower(), _DEFAULT_COLOR)
    return (
        f'<span style="background-color:{bg};color:{fg};padding:2px 10px;'
        f'border-radius:12px;font-size:0.82rem;font-weight:600;white-space:nowrap;">{text}</span>'
    )


def render_status_badge(label: str | None) -> None:
    st.markdown(badge_html(label), unsafe_allow_html=True)
