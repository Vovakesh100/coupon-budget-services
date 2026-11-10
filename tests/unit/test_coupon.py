import inspect
from datetime import UTC, datetime, timedelta

import pytest

from coupon_budget.domain.budget import Budget, BudgetExceededError, Campaign
from coupon_budget.domain.coupon import (
    CampaignExpiredError,
    Coupon,
    CouponAlreadyRedeemedError,
    issue_coupon,
    redeem,
)
from coupon_budget.domain.money import Money

ENDS = datetime(2026, 12, 31, tzinfo=UTC)
BEFORE = ENDS - timedelta(seconds=1)


def _campaign(total: int = 100, spent: int = 0) -> Campaign:
    return Campaign(id="c1", budget=Budget(Money(total), Money(spent)), ends_at=ENDS)


def _coupon(face: int = 10) -> Coupon:
    return Coupon(id="k1", campaign_id="c1", face_value=Money(face))


def test_redeem_charges_full_face_value_and_marks_coupon() -> None:
    campaign, coupon = redeem(_campaign(), _coupon(10), BEFORE)
    assert campaign.budget.spent == Money(10)
    assert coupon.redeemed is True


def test_redeem_refused_at_or_after_expiry() -> None:
    with pytest.raises(CampaignExpiredError):
        redeem(_campaign(), _coupon(), ENDS)


def test_redeem_twice_refused() -> None:
    campaign, coupon = redeem(_campaign(), _coupon(), BEFORE)
    with pytest.raises(CouponAlreadyRedeemedError):
        redeem(campaign, coupon, BEFORE)


def test_redeem_over_budget_refused_and_inputs_unchanged() -> None:
    campaign = _campaign(total=5)
    coupon = _coupon(10)
    with pytest.raises(BudgetExceededError):
        redeem(campaign, coupon, BEFORE)
    assert campaign.budget.spent == Money(0)
    assert coupon.redeemed is False


def test_redeem_rejects_coupon_of_another_campaign() -> None:
    other = Coupon(id="k2", campaign_id="other", face_value=Money(1))
    with pytest.raises(ValueError):
        redeem(_campaign(), other, BEFORE)


def test_issue_refused_after_expiry() -> None:
    with pytest.raises(CampaignExpiredError):
        issue_coupon(_campaign(), "k1", Money(1), ENDS)


def test_zero_face_value_is_invalid() -> None:
    with pytest.raises(ValueError):
        Coupon(id="k", campaign_id="c1", face_value=Money(0))


def test_redeem_has_no_amount_parameter() -> None:
    assert "amount" not in inspect.signature(redeem).parameters
