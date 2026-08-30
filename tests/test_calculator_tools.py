"""Tests for the Phase 29 financial calculator tools
(tools/calculator_tools.py). Pure math, no database or Groq involved."""

from tools.calculator_tools import calculate_loan_payment, calculate_net_worth, calculate_savings_growth


def test_savings_growth_zero_rate_is_simple_addition():
    result = calculate_savings_growth(initial_amount=1000, monthly_contribution=100, annual_rate_percent=0, years=2)
    assert result.success
    assert result.future_value == 3400.0
    assert result.total_growth == 0.0
    assert len(result.yearly_balances) == 2


def test_savings_growth_positive_rate_produces_growth():
    result = calculate_savings_growth(initial_amount=10000, monthly_contribution=200, annual_rate_percent=6, years=10)
    assert result.success
    assert result.future_value > result.total_contributions
    assert result.total_growth > 0
    assert result.yearly_balances[-1].balance == result.future_value


def test_savings_growth_rejects_non_positive_years():
    result = calculate_savings_growth(1000, 100, 5, 0)
    assert not result.success
    assert "years" in result.error.lower()


def test_savings_growth_rejects_negative_amounts():
    result = calculate_savings_growth(-100, 100, 5, 10)
    assert not result.success


def test_loan_payment_zero_interest_is_simple_division():
    result = calculate_loan_payment(loan_amount=12000, annual_rate_percent=0, term_years=1)
    assert result.success
    assert result.monthly_payment == 1000.0
    assert result.total_interest == 0.0


def test_loan_payment_standard_mortgage():
    result = calculate_loan_payment(loan_amount=250000, annual_rate_percent=6.5, term_years=30)
    assert result.success
    assert 1570 < result.monthly_payment < 1590
    assert result.total_interest > 0
    assert len(result.yearly_remaining_balance) == 30
    assert result.yearly_remaining_balance[-1].balance == 0.0


def test_loan_payment_balance_decreases_monotonically():
    result = calculate_loan_payment(loan_amount=50000, annual_rate_percent=4, term_years=5)
    balances = [b.balance for b in result.yearly_remaining_balance]
    assert balances == sorted(balances, reverse=True)


def test_loan_payment_rejects_non_positive_loan_amount():
    result = calculate_loan_payment(0, 5, 10)
    assert not result.success


def test_net_worth_positive_negative_break_even():
    assert calculate_net_worth(100000, 40000).status == "Positive"
    assert calculate_net_worth(40000, 100000).status == "Negative"
    assert calculate_net_worth(50000, 50000).status == "Break-even"


def test_net_worth_rejects_negative_inputs():
    result = calculate_net_worth(-100, 50)
    assert not result.success


def test_every_successful_result_carries_disclaimer():
    for result in (
        calculate_savings_growth(1000, 100, 5, 5),
        calculate_loan_payment(10000, 5, 5),
        calculate_net_worth(100, 50),
    ):
        assert result.success
        assert "illustrative estimate" in result.disclaimer.lower()
