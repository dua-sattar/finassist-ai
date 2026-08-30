"""Manual verification for Phase 29 (Financial Calculator): confirms the
three deterministic calculators against hand-checkable figures, plus input
validation. No Groq/LLM involved -- pure math, so this is fast and doesn't
touch the database at all. Not a pytest suite (that's
tests/test_calculator_tools.py)."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.calculator_tools import calculate_loan_payment, calculate_net_worth, calculate_savings_growth


def main() -> None:
    print("=== Savings growth: zero rate is simple addition ===")
    result = calculate_savings_growth(initial_amount=1000, monthly_contribution=100, annual_rate_percent=0, years=2)
    assert result.success
    # 1000 + 100*24 = 3400, no growth since rate is 0.
    assert result.future_value == 3400.0, result.future_value
    assert result.total_contributions == 3400.0
    assert result.total_growth == 0.0
    assert len(result.yearly_balances) == 2
    assert result.yearly_balances[0].balance == 2200.0  # 1000 + 100*12
    assert result.yearly_balances[1].balance == 3400.0
    print(f"future_value={result.future_value}")
    print("OK\n")

    print("=== Savings growth: positive rate produces real growth ===")
    result = calculate_savings_growth(initial_amount=10000, monthly_contribution=200, annual_rate_percent=6, years=10)
    assert result.success
    assert result.future_value > result.total_contributions
    assert result.total_growth > 0
    assert len(result.yearly_balances) == 10
    assert result.yearly_balances[-1].balance == result.future_value
    print(f"future_value={result.future_value} total_growth={result.total_growth}")
    print("OK\n")

    print("=== Savings growth: invalid years fails gracefully ===")
    result = calculate_savings_growth(1000, 100, 5, 0)
    assert not result.success
    assert "years" in result.error.lower()
    print("OK\n")

    print("=== Loan payment: zero-interest loan is simple division ===")
    result = calculate_loan_payment(loan_amount=12000, annual_rate_percent=0, term_years=1)
    assert result.success
    assert result.monthly_payment == 1000.0, result.monthly_payment
    assert result.total_paid == 12000.0
    assert result.total_interest == 0.0
    print(f"monthly_payment={result.monthly_payment}")
    print("OK\n")

    print("=== Loan payment: standard mortgage-style loan ===")
    result = calculate_loan_payment(loan_amount=250000, annual_rate_percent=6.5, term_years=30)
    assert result.success
    # Hand-verified against the standard amortization formula: ~$1580/mo.
    assert 1570 < result.monthly_payment < 1590, result.monthly_payment
    assert result.total_interest > 0
    assert len(result.yearly_remaining_balance) == 30
    assert result.yearly_remaining_balance[-1].balance == 0.0
    assert result.yearly_remaining_balance[0].balance < 250000
    # Balance should decrease monotonically year over year.
    balances = [b.balance for b in result.yearly_remaining_balance]
    assert balances == sorted(balances, reverse=True)
    print(f"monthly_payment={result.monthly_payment} total_interest={result.total_interest}")
    print("OK\n")

    print("=== Loan payment: invalid loan amount fails gracefully ===")
    result = calculate_loan_payment(0, 5, 10)
    assert not result.success
    print("OK\n")

    print("=== Net worth: positive, negative, break-even ===")
    positive = calculate_net_worth(100000, 40000)
    assert positive.success and positive.net_worth == 60000.0 and positive.status == "Positive"
    negative = calculate_net_worth(40000, 100000)
    assert negative.success and negative.net_worth == -60000.0 and negative.status == "Negative"
    even = calculate_net_worth(50000, 50000)
    assert even.success and even.net_worth == 0.0 and even.status == "Break-even"
    print(f"positive={positive.net_worth} negative={negative.net_worth} even={even.net_worth}")
    print("OK\n")

    print("=== Every result carries the illustrative-estimate disclaimer ===")
    assert "illustrative estimate" in positive.disclaimer.lower()
    print("OK\n")

    print("All Financial Calculator checks passed.")


if __name__ == "__main__":
    main()
