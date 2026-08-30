"""Financial calculator tools (spec section 26): three small, fully
deterministic calculators -- no LLM involved, no fabricated figures, just
standard finance formulas. Every result carries an explicit "illustrative
estimate only" disclaimer, consistent with the rest of the app's human
review framing.
"""

import logging

from pydantic import BaseModel

from tools.common import log_action

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "This is an illustrative estimate only, based on the inputs provided and standard "
    "financial formulas. It is not financial, tax, or legal advice. Human review required "
    "before acting on it."
)


class YearlyBalance(BaseModel):
    year: int
    balance: float


class SavingsGrowthResult(BaseModel):
    success: bool
    future_value: float = 0.0
    total_contributions: float = 0.0
    total_growth: float = 0.0
    yearly_balances: list[YearlyBalance] = []
    disclaimer: str = DISCLAIMER
    error: str | None = None


def calculate_savings_growth(
    initial_amount: float, monthly_contribution: float, annual_rate_percent: float, years: int
) -> SavingsGrowthResult:
    """Project the future value of an initial amount plus regular monthly
    contributions, compounded monthly at a fixed annual rate -- e.g. a
    retirement or investment savings projection."""
    try:
        if years <= 0:
            raise ValueError("years must be greater than 0")
        if initial_amount < 0 or monthly_contribution < 0:
            raise ValueError("initial_amount and monthly_contribution must not be negative")

        monthly_rate = annual_rate_percent / 100 / 12
        yearly_balances: list[YearlyBalance] = []
        balance = initial_amount

        for year in range(1, years + 1):
            for _ in range(12):
                balance = balance * (1 + monthly_rate) + monthly_contribution
            yearly_balances.append(YearlyBalance(year=year, balance=round(balance, 2)))

        future_value = balance
        total_contributions = initial_amount + monthly_contribution * years * 12
        total_growth = future_value - total_contributions

        log_action(
            "calculate_savings_growth",
            f"initial={initial_amount} monthly={monthly_contribution} rate={annual_rate_percent}% years={years}",
            f"future_value={future_value:.2f}",
        )
        return SavingsGrowthResult(
            success=True,
            future_value=round(future_value, 2),
            total_contributions=round(total_contributions, 2),
            total_growth=round(total_growth, 2),
            yearly_balances=yearly_balances,
        )
    except Exception as exc:
        logger.warning("calculate_savings_growth failed: %s", exc)
        log_action("calculate_savings_growth", f"years={years}", str(exc), status="error")
        return SavingsGrowthResult(success=False, error=str(exc))


class LoanPaymentResult(BaseModel):
    success: bool
    monthly_payment: float = 0.0
    total_paid: float = 0.0
    total_interest: float = 0.0
    yearly_remaining_balance: list[YearlyBalance] = []
    disclaimer: str = DISCLAIMER
    error: str | None = None


def calculate_loan_payment(loan_amount: float, annual_rate_percent: float, term_years: int) -> LoanPaymentResult:
    """Compute the fixed monthly payment for a standard amortizing loan
    (e.g. a mortgage or business loan), plus total interest paid and a
    year-by-year remaining-balance schedule."""
    try:
        if loan_amount <= 0:
            raise ValueError("loan_amount must be greater than 0")
        if term_years <= 0:
            raise ValueError("term_years must be greater than 0")
        if annual_rate_percent < 0:
            raise ValueError("annual_rate_percent must not be negative")

        monthly_rate = annual_rate_percent / 100 / 12
        n_payments = term_years * 12

        if monthly_rate == 0:
            monthly_payment = loan_amount / n_payments
        else:
            factor = (1 + monthly_rate) ** n_payments
            monthly_payment = loan_amount * monthly_rate * factor / (factor - 1)

        yearly_remaining: list[YearlyBalance] = []
        balance = loan_amount
        for year in range(1, term_years + 1):
            for _ in range(12):
                interest_portion = balance * monthly_rate
                balance = balance - (monthly_payment - interest_portion)
            yearly_remaining.append(YearlyBalance(year=year, balance=round(max(balance, 0.0), 2)))

        total_paid = monthly_payment * n_payments
        total_interest = total_paid - loan_amount

        log_action(
            "calculate_loan_payment",
            f"loan_amount={loan_amount} rate={annual_rate_percent}% term_years={term_years}",
            f"monthly_payment={monthly_payment:.2f}",
        )
        return LoanPaymentResult(
            success=True,
            monthly_payment=round(monthly_payment, 2),
            total_paid=round(total_paid, 2),
            total_interest=round(total_interest, 2),
            yearly_remaining_balance=yearly_remaining,
        )
    except Exception as exc:
        logger.warning("calculate_loan_payment failed: %s", exc)
        log_action("calculate_loan_payment", f"term_years={term_years}", str(exc), status="error")
        return LoanPaymentResult(success=False, error=str(exc))


class NetWorthResult(BaseModel):
    success: bool
    net_worth: float = 0.0
    status: str = ""  # "Positive" | "Negative" | "Break-even"
    disclaimer: str = DISCLAIMER
    error: str | None = None


def calculate_net_worth(total_assets: float, total_liabilities: float) -> NetWorthResult:
    """Compute net worth (assets minus liabilities) from figures the user
    provides directly."""
    try:
        if total_assets < 0 or total_liabilities < 0:
            raise ValueError("total_assets and total_liabilities must not be negative")

        net_worth = total_assets - total_liabilities
        if net_worth > 0:
            status = "Positive"
        elif net_worth < 0:
            status = "Negative"
        else:
            status = "Break-even"

        log_action(
            "calculate_net_worth", f"assets={total_assets} liabilities={total_liabilities}", f"net_worth={net_worth:.2f}"
        )
        return NetWorthResult(success=True, net_worth=round(net_worth, 2), status=status)
    except Exception as exc:
        logger.warning("calculate_net_worth failed: %s", exc)
        log_action("calculate_net_worth", "", str(exc), status="error")
        return NetWorthResult(success=False, error=str(exc))
