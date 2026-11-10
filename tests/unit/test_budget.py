import pytest

from coupon_budget.domain.budget import Budget, BudgetExceededError
from coupon_budget.domain.money import Money


def test_remaining_is_total_minus_spent() -> None:
    assert Budget(total=Money(10), spent=Money(4)).remaining == Money(6)


def test_charge_within_budget() -> None:
    assert Budget(total=Money(10)).charge(Money(10)).remaining == Money(0)


def test_charge_over_budget_raises_and_keeps_state() -> None:
    budget = Budget(total=Money(10), spent=Money(8))
    with pytest.raises(BudgetExceededError):
        budget.charge(Money(3))
    assert budget.spent == Money(8)


def test_spent_above_total_is_invalid() -> None:
    with pytest.raises(ValueError):
        Budget(total=Money(5), spent=Money(6))
