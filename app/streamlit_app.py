"""FinAssist AI -- Streamlit entrypoint: sidebar navigation, global
disclaimer banner, and page router.

Uses st.navigation/st.Page (not folder-based auto-discovery) for a custom
sidebar with a shared disclaimer banner wrapping every page. Page modules
live in app/views/ rather than app/pages/ -- Streamlit reserves a literal
`pages/` directory next to the entrypoint for its own automatic multipage
detection, which overrides any in-script st.navigation() call and hijacks
the sidebar regardless of what the entrypoint does.

Run with: streamlit run app/streamlit_app.py
"""

import logging
import sys
from pathlib import Path

import streamlit as st

# Allow `import app.x` / `from database import ...` etc. when launched
# directly by `streamlit run` from the project root.
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app.components.disclaimer import render_disclaimer_banner  # noqa: E402
from app.views import (  # noqa: E402
    ai_actions,
    assistant,
    clients,
    dashboard,
    documents,
    followups,
    knowledge_base,
    leads,
)
from database.database import init_db  # noqa: E402
from database.seed import main as seed_database  # noqa: E402

st.set_page_config(page_title="FinAssist AI", page_icon="💼", layout="wide")


@st.cache_resource
def _ensure_database_ready() -> None:
    init_db()
    seed_database()


def _with_banner(render_fn):
    def wrapped() -> None:
        render_disclaimer_banner()
        render_fn()

    return wrapped


def main() -> None:
    try:
        _ensure_database_ready()
    except Exception as exc:
        st.error(
            "FinAssist AI could not start because the database could not be initialized. "
            "Please check the server logs and try again."
        )
        logging.getLogger(__name__).error("Database initialization failed: %s", exc, exc_info=True)
        st.stop()

    with st.sidebar:
        st.markdown("## 💼 FinAssist AI")
        st.caption("AI Financial Operations Agent -- Portfolio Demo")

    # Every wrapped page function is named `wrapped` (same closure), so
    # st.Page's callable-name-based URL inference collides across all 8 --
    # url_path is passed explicitly to avoid that.
    pages = [
        st.Page(_with_banner(dashboard.render), title="Dashboard", icon="📊", url_path="dashboard", default=True),
        st.Page(_with_banner(assistant.render), title="AI Assistant", icon="💬", url_path="assistant"),
        st.Page(_with_banner(documents.render), title="Document Analysis", icon="📄", url_path="documents"),
        st.Page(_with_banner(knowledge_base.render), title="Knowledge Base", icon="📚", url_path="knowledge-base"),
        st.Page(_with_banner(clients.render), title="Client Management", icon="🧑‍💼", url_path="clients"),
        st.Page(_with_banner(leads.render), title="Lead Management", icon="🎯", url_path="leads"),
        st.Page(_with_banner(followups.render), title="Follow-ups", icon="✅", url_path="followups"),
        st.Page(_with_banner(ai_actions.render), title="AI Actions", icon="🪵", url_path="ai-actions"),
    ]
    nav = st.navigation(pages)

    with st.sidebar:
        st.divider()
        st.caption("Synthetic data only. Not a real financial institution.")

    nav.run()


if __name__ == "__main__":
    main()
