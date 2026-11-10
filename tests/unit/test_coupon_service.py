"""Service tests with in-memory fakes only. No Redis or PostgreSQL."""

import asyncio
import functools
import itertools
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from coupon_budget.config.rules import Rules
from coupon_budget.domain.budget import BudgetExceededError
from coupon_budget.domain.coupon import CampaignExpiredError, CouponAlreadyRedeemedError
from coupon_budget.ports.budget_store import CampaignNotFoundError, CouponNotFoundError
from coupon_budget.services.coupons import (
    CouponService,
    InvalidRequestError,
    LimitExceededError,
)
from tests.fakes.memory_budget_store import MemoryBudgetStore
from tests.fakes.memory_repository import MemoryCampaignRepository


def _async[**P](fn: Callable[P, Coroutine[Any, Any, None]]) -> Callable[P, None]:
    """pytest-asyncio is not installed; run each async test with asyncio.run (same as T6)."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        asyncio.run(fn(*args, **kwargs))

    return wrapper


NOW = datetime(2026, 6, 1, tzinfo=UTC)
ENDS = NOW + timedelta(days=30)
RULES = Rules(
    version=1,
    idempotency_key_ttl_seconds=86400,
    max_campaign_budget_micro=1_000_000,
    max_coupon_face_value_micro=200_000,
)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _service(clock: Clock | None = None, rules: Rules = RULES) -> tuple[CouponService, Clock]:
    ids = (f"id-{n}" for n in itertools.count(1))
    clk = clock or Clock(NOW)
    svc = CouponService(
        records=MemoryCampaignRepository(),
        budget=MemoryBudgetStore(rules.idempotency_key_ttl_seconds),
        rules=rules,
        clock=clk,
        new_id=lambda: next(ids),
    )
    return svc, clk


@_async
async def test_create_campaign_then_read_budget() -> None:
    svc, _ = _service()
    campaign = await svc.create_campaign(total_micro=500_000, ends_at=ENDS)
    view = await svc.get_budget(campaign.id)
    assert int(view.allocated.micro) == 500_000
    assert int(view.spent.micro) == 0
    assert int(view.remaining.micro) == 500_000


@_async
async def test_issue_and_redeem_charges_budget() -> None:
    svc, _ = _service()
    campaign = await svc.create_campaign(total_micro=500_000, ends_at=ENDS)
    coupon = await svc.issue_coupon(campaign.id, face_value_micro=120_000)
    redeemed = await svc.redeem(coupon.id, "key-1")
    assert redeemed.redeemed
    view = await svc.get_budget(campaign.id)
    assert int(view.spent.micro) == 120_000
    assert int(view.remaining.micro) == 380_000


@_async
async def test_repeated_idempotency_key_does_not_charge_twice() -> None:
    svc, _ = _service()
    campaign = await svc.create_campaign(total_micro=500_000, ends_at=ENDS)
    coupon = await svc.issue_coupon(campaign.id, face_value_micro=120_000)
    await svc.redeem(coupon.id, "key-1")
    await svc.redeem(coupon.id, "key-1")
    view = await svc.get_budget(campaign.id)
    assert int(view.spent.micro) == 120_000


@_async
async def test_redeem_after_campaign_end_is_refused() -> None:
    svc, clock = _service()
    campaign = await svc.create_campaign(total_micro=500_000, ends_at=ENDS)
    coupon = await svc.issue_coupon(campaign.id, face_value_micro=1)
    clock.now = ENDS + timedelta(seconds=1)
    with pytest.raises(CampaignExpiredError):
        await svc.redeem(coupon.id, "key-late")
    view = await svc.get_budget(campaign.id)
    assert int(view.spent.micro) == 0


@_async
async def test_redeem_beyond_budget_is_refused() -> None:
    svc, _ = _service()
    campaign = await svc.create_campaign(total_micro=100_000, ends_at=ENDS)
    first = await svc.issue_coupon(campaign.id, face_value_micro=100_000)
    await svc.redeem(first.id, "key-1")
    second = await svc.issue_coupon(campaign.id, face_value_micro=1)
    with pytest.raises(BudgetExceededError):
        await svc.redeem(second.id, "key-2")


@_async
async def test_second_redemption_with_new_key_is_refused() -> None:
    svc, _ = _service()
    campaign = await svc.create_campaign(total_micro=500_000, ends_at=ENDS)
    coupon = await svc.issue_coupon(campaign.id, face_value_micro=1)
    await svc.redeem(coupon.id, "key-1")
    with pytest.raises(CouponAlreadyRedeemedError):
        await svc.redeem(coupon.id, "key-2")


@_async
async def test_issue_for_unknown_campaign_is_refused() -> None:
    svc, _ = _service()
    with pytest.raises(CampaignNotFoundError):
        await svc.issue_coupon("ghost", face_value_micro=1)


@_async
async def test_redeem_unknown_coupon_is_refused() -> None:
    svc, _ = _service()
    with pytest.raises(CouponNotFoundError):
        await svc.redeem("ghost", "key-1")


@_async
async def test_budget_for_unknown_campaign_is_refused() -> None:
    svc, _ = _service()
    with pytest.raises(CampaignNotFoundError):
        await svc.get_budget("ghost")


@_async
async def test_campaign_budget_above_limit_is_refused() -> None:
    svc, _ = _service()
    with pytest.raises(LimitExceededError):
        await svc.create_campaign(total_micro=RULES.max_campaign_budget_micro + 1, ends_at=ENDS)


@_async
async def test_coupon_face_value_above_limit_is_refused() -> None:
    svc, _ = _service()
    campaign = await svc.create_campaign(total_micro=500_000, ends_at=ENDS)
    with pytest.raises(LimitExceededError):
        await svc.issue_coupon(campaign.id, RULES.max_coupon_face_value_micro + 1)


@pytest.mark.parametrize("bad", [0, -1])
@_async
async def test_non_positive_campaign_budget_is_refused(bad: int) -> None:
    svc, _ = _service()
    with pytest.raises(InvalidRequestError):
        await svc.create_campaign(total_micro=bad, ends_at=ENDS)


@_async
async def test_campaign_end_in_the_past_is_refused() -> None:
    svc, _ = _service()
    with pytest.raises(InvalidRequestError, match="future"):
        await svc.create_campaign(total_micro=1, ends_at=NOW - timedelta(seconds=1))


@_async
async def test_naive_campaign_end_is_refused() -> None:
    svc, _ = _service()
    with pytest.raises(InvalidRequestError, match="timezone"):
        await svc.create_campaign(total_micro=1, ends_at=datetime(2027, 1, 1))  # noqa: DTZ001


@_async
async def test_new_settings_version_changes_limits() -> None:
    # TZ criterion 5: a new limit from a new settings version applies without code changes.
    stricter = Rules(
        version=2,
        idempotency_key_ttl_seconds=60,
        max_campaign_budget_micro=10,
        max_coupon_face_value_micro=5,
    )
    svc, _ = _service(rules=stricter)
    with pytest.raises(LimitExceededError):
        await svc.create_campaign(total_micro=11, ends_at=ENDS)
