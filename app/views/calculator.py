"""Financial Calculator page (spec section 26): three small, deterministic
calculators -- savings growth projection, loan payment, and net worth. No
AI/LLM involved; every result is an illustrative estimate only."""

import pandas as pd
import streamlit as st

from tools.calculator_tools import calculate_loan_payment, calculate_net_worth, calculate_savings_growth


def _render_savings_growth() -> None:
    st.caption("Project the future value of an initial amount plus regular monthly contributions.")
    col1, col2 = st.columns(2)
    with col1:
        initial_amount = st.number_input("Initial amount ($)", min_value=0.0, value=1000.0, step=100.0, key="sg-initial")
        annual_rate = st.number_input("Annual interest rate (%)", min_value=0.0, value=6.0, step=0.5, key="sg-rate")
    with col2:
        monthly_contribution = st.number_input(
            "Monthly contribution ($)", min_value=0.0, value=200.0, step=50.0, key="sg-monthly"
        )
        years = st.number_input("Years", min_value=1, value=20, step=1, key="sg-years")

    if st.button("Calculate", type="primary", key="sg-calculate"):
        result = calculate_savings_growth(initial_amount, monthly_contribution, annual_rate, int(years))
        st.session_state["sg-result"] = result

    result = st.session_state.get("sg-result")
    if result is None:
        return
    if not result.success:
        st.error(f"Could not calculate: {result.error}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Future Value", f"${result.future_value:,.2f}")
    col2.metric("Total Contributions", f"${result.total_contributions:,.2f}")
    col3.metric("Total Growth", f"${result.total_growth:,.2f}")

    with st.expander("Year-by-year balance"):
        rows = [{"Year": b.year, "Balance": f"${b.balance:,.2f}"} for b in result.yearly_balances]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption(result.disclaimer)


def _render_loan_payment() -> None:
    st.caption("Compute the fixed monthly payment for a standard amortizing loan.")
    col1, col2 = st.columns(2)
    with col1:
        loan_amount = st.number_input("Loan amount ($)", min_value=0.0, value=250000.0, step=1000.0, key="lp-amount")
    with col2:
        annual_rate = st.number_input("Annual interest rate (%)", min_value=0.0, value=6.5, step=0.1, key="lp-rate")
    term_years = st.number_input("Term (years)", min_value=1, value=30, step=1, key="lp-term")

    if st.button("Calculate", type="primary", key="lp-calculate"):
        result = calculate_loan_payment(loan_amount, annual_rate, int(term_years))
        st.session_state["lp-result"] = result

    result = st.session_state.get("lp-result")
    if result is None:
        return
    if not result.success:
        st.error(f"Could not calculate: {result.error}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Monthly Payment", f"${result.monthly_payment:,.2f}")
    col2.metric("Total Paid", f"${result.total_paid:,.2f}")
    col3.metric("Total Interest", f"${result.total_interest:,.2f}")

    with st.expander("Year-by-year remaining balance"):
        rows = [{"Year": b.year, "Remaining Balance": f"${b.balance:,.2f}"} for b in result.yearly_remaining_balance]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption(result.disclaimer)


def _render_net_worth() -> None:
    st.caption("Compute net worth from total assets and total liabilities.")
    col1, col2 = st.columns(2)
    with col1:
        total_assets = st.number_input("Total assets ($)", min_value=0.0, value=0.0, step=1000.0, key="nw-assets")
    with col2:
        total_liabilities = st.number_input(
            "Total liabilities ($)", min_value=0.0, value=0.0, step=1000.0, key="nw-liabilities"
        )

    if st.button("Calculate", type="primary", key="nw-calculate"):
        result = calculate_net_worth(total_assets, total_liabilities)
        st.session_state["nw-result"] = result

    result = st.session_state.get("nw-result")
    if result is None:
        return
    if not result.success:
        st.error(f"Could not calculate: {result.error}")
        return

    st.metric("Net Worth", f"${result.net_worth:,.2f}", delta=result.status)
    st.caption(result.disclaimer)


def render() -> None:
    st.header("Financial Calculator")
    st.caption("Deterministic calculators -- no AI involved. Every result is an illustrative estimate only.")

    tab1, tab2, tab3 = st.tabs(["Savings Growth", "Loan Payment", "Net Worth"])
    with tab1:
        _render_savings_growth()
    with tab2:
        _render_loan_payment()
    with tab3:
        _render_net_worth()
