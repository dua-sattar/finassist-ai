"""Global disclaimer banner shown at the top of every page (spec section 18)."""

import streamlit as st


def render_disclaimer_banner() -> None:
    st.markdown(
        """
        <div style="
            background-color:#fff8e1;
            border:1px solid #f0c14b;
            border-radius:6px;
            padding:10px 16px;
            margin-bottom:16px;
            font-size:0.88rem;
            color:#5c4813;
        ">
            <strong>Portfolio Demonstration — Synthetic Data Only — Human Review Required.</strong>
            FinAssist AI is a fictional company. This application is not a production financial
            system and does not provide real financial, tax, or legal advice. All AI-generated
            recommendations require human review before acting on them.
        </div>
        """,
        unsafe_allow_html=True,
    )
