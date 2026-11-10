"""Campaign budget and its invariant: spent never exceeds total."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from coupon_budget.domain.money import Money


class BudgetExceededError(Exception):
    """A charge would push spent above the total budget."""


@dataclass(frozen=True, slots=True)
class Budget:
    total: Money
    spent: Money = Money(0)

    def __post_init__(self) -> None:
        if self.spent.micro > self.total.micro:
            raise ValueError("spent cannot exceed total")

    @property
    def remaining(self) -> Money:
        return self.total - self.spent

    def charge(self, amount: Money) -> Budget:
        if amount.micro > self.remaining.micro:
            raise BudgetExceededError(
                f"charge {amount.micro} exceeds remaining {self.remaining.micro}"
            )
        return replace(self, spent=self.spent + amount)


@dataclass(frozen=True, slots=True)
class Campaign:
    id: str
    budget: Budget
    ends_at: datetime

    def __post_init__(self) -> None:
        if self.ends_at.tzinfo is None:
            raise ValueError("ends_at must be timezone-aware")

    def is_active(self, now: datetime) -> bool:
        return now < self.ends_at
