import pytest

from coupon_budget.domain.money import MICRO_PER_UNIT, Money, NegativeMoneyError


def test_stores_integer_micro() -> None:
    assert Money(5).micro == 5


def test_rejects_float() -> None:
    with pytest.raises(TypeError):
        Money(1.0)  # type: ignore[arg-type]


def test_rejects_bool() -> None:
    with pytest.raises(TypeError):
        Money(True)


def test_rejects_negative() -> None:
    with pytest.raises(NegativeMoneyError):
        Money(-1)


def test_from_units_is_exact_for_six_places() -> None:
    assert Money.from_units("12.5") == Money(12_500_000)
    assert Money.from_units("0.000001") == Money(1)


def test_from_units_rounds_down_beyond_micro() -> None:
    assert Money.from_units("0.0000019") == Money(1)
    assert Money.from_units("1.23456789") == Money(1_234_567)


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity", "abc", ""])
def test_from_units_rejects_bad_input(bad: str) -> None:
    with pytest.raises(ValueError):
        Money.from_units(bad)


def test_from_units_rejects_non_str() -> None:
    with pytest.raises(TypeError):
        Money.from_units(1.5)  # type: ignore[arg-type]


def test_add_and_sub() -> None:
    assert Money(2) + Money(3) == Money(5)
    assert Money(5) - Money(3) == Money(2)


def test_sub_below_zero_raises() -> None:
    with pytest.raises(NegativeMoneyError):
        Money(1) - Money(2)


def test_mul_by_int_only() -> None:
    assert Money(4) * 3 == Money(12)
    with pytest.raises(TypeError):
        Money(4) * 1.5  # type: ignore[operator]


def test_one_unit_constant() -> None:
    assert Money.from_units("1") == Money(MICRO_PER_UNIT)
