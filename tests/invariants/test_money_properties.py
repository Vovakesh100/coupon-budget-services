from hypothesis import given
from hypothesis import strategies as st

from coupon_budget.domain.money import Money

amounts = st.integers(min_value=0, max_value=10**15)


def _as_decimal_string(micro: int, extra_digit: int) -> str:
    units, rest = divmod(micro, 1_000_000)
    return f"{units}.{rest:06d}{extra_digit}"


@given(amounts, amounts)
def test_addition_is_commutative(a: int, b: int) -> None:
    assert Money(a) + Money(b) == Money(b) + Money(a)


@given(amounts, amounts, amounts)
def test_addition_is_associative(a: int, b: int, c: int) -> None:
    assert (Money(a) + Money(b)) + Money(c) == Money(a) + (Money(b) + Money(c))


@given(amounts, amounts)
def test_subtraction_never_goes_negative(a: int, b: int) -> None:
    if a >= b:
        assert (Money(a) - Money(b)).micro == a - b
    else:
        try:
            Money(a) - Money(b)
        except ValueError:
            pass
        else:
            raise AssertionError("expected NegativeMoneyError")


@given(amounts, st.integers(min_value=0, max_value=9))
def test_from_units_round_trip_rounds_down(micro: int, extra: int) -> None:
    assert Money.from_units(_as_decimal_string(micro, extra)) == Money(micro)
