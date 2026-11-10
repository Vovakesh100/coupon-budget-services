"""Money as an integer number of micro units.

Rules (see docs/TZ.md, criterion 4): no float anywhere, conversions round down.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, InvalidOperation, localcontext

MICRO_PER_UNIT = 1_000_000


class NegativeMoneyError(ValueError):
    """Raised when an amount would become negative."""


@dataclass(frozen=True, slots=True, order=True)
class Money:
    micro: int

    def __post_init__(self) -> None:
        # type() check, not isinstance: bool is a subclass of int and must be rejected.
        if type(self.micro) is not int:
            raise TypeError(f"micro must be int, got {type(self.micro).__name__}")
        if self.micro < 0:
            raise NegativeMoneyError(f"amount cannot be negative: {self.micro}")

    @classmethod
    def from_units(cls, value: str) -> Money:
        """Parse a decimal string such as "12.5". Digits beyond 6 places are rounded down."""
        if not isinstance(value, str):
            raise TypeError("from_units takes a str, so no float can sneak in")
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal number: {value!r}") from exc
        if not amount.is_finite():
            raise ValueError(f"not a finite number: {value!r}")
        if amount < 0:
            raise NegativeMoneyError(f"amount cannot be negative: {value!r}")
        with localcontext() as ctx:
            ctx.prec = 200
            scaled = (amount * MICRO_PER_UNIT).to_integral_value(rounding=ROUND_DOWN)
        return cls(int(scaled))

    def __add__(self, other: Money) -> Money:
        return Money(self.micro + other.micro)

    def __sub__(self, other: Money) -> Money:
        return Money(self.micro - other.micro)

    def __mul__(self, factor: int) -> Money:
        if type(factor) is not int:
            raise TypeError("money can only be multiplied by an int")
        return Money(self.micro * factor)
