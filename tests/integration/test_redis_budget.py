"""Integration tests against a real Redis. Skipped unless REDIS_URL is set."""

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from coupon_budget.adapters.redis_budget import RedisBudgetStore
from coupon_budget.domain.budget import Budget, BudgetExceededError, Campaign
from coupon_budget.domain.coupon import (
    CampaignExpiredError,
    Coupon,
    CouponAlreadyRedeemedError,
)
from coupon_budget.domain.money import Money
from coupon_budget.ports.budget_store import IdempotencyKeyReusedError

REDIS_URL = os.environ.get("REDIS_URL", "")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL is not set")

NOW = datetime(2026, 6, 1, tzinfo=UTC)
ENDS = datetime(2027, 1, 1, tzinfo=UTC)


def _run[T](scenario: Callable[[Redis], Awaitable[T]]) -> T:
    async def wrapper() -> T:
        client = Redis.from_url(REDIS_URL)
        try:
            return await scenario(client)
        finally:
            await client.aclose()

    return asyncio.run(wrapper())


async def _setup(redis: Redis, total: int, ttl: int = 3600) -> tuple[RedisBudgetStore, str]:
    cid = f"c-{uuid.uuid4().hex}"
    store = RedisBudgetStore(redis, idempotency_ttl_seconds=ttl)
    await store.add_campaign(Campaign(id=cid, budget=Budget(Money(total)), ends_at=ENDS))
    return store, cid


async def _coupon(store: RedisBudgetStore, cid: str, face: int) -> str:
    coupon_id = f"k-{uuid.uuid4().hex}"
    await store.add_coupon(Coupon(id=coupon_id, campaign_id=cid, face_value=Money(face)))
    return coupon_id


def test_repeated_key_charges_once() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=100)
        coupon = await _coupon(store, cid, 10)
        await store.redeem(coupon, "key-1", NOW)
        await store.redeem(coupon, "key-1", NOW)
        campaign = await store.get_campaign(cid)
        assert campaign is not None
        assert campaign.budget.spent == Money(10)

    _run(scenario)


def test_same_key_other_coupon_refused() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=100)
        first = await _coupon(store, cid, 10)
        second = await _coupon(store, cid, 10)
        await store.redeem(first, "key-2", NOW)
        with pytest.raises(IdempotencyKeyReusedError):
            await store.redeem(second, "key-2", NOW)

    _run(scenario)


def test_expired_campaign_refused() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=100)
        coupon = await _coupon(store, cid, 10)
        with pytest.raises(CampaignExpiredError):
            await store.redeem(coupon, "key-3", ENDS)

    _run(scenario)


def test_budget_refusal_leaves_state() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=5)
        coupon = await _coupon(store, cid, 10)
        with pytest.raises(BudgetExceededError):
            await store.redeem(coupon, "key-4", NOW)
        campaign = await store.get_campaign(cid)
        assert campaign is not None
        assert campaign.budget.spent == Money(0)

    _run(scenario)


def test_second_redemption_with_new_key_refused() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=100)
        coupon = await _coupon(store, cid, 10)
        await store.redeem(coupon, "key-5", NOW)
        with pytest.raises(CouponAlreadyRedeemedError):
            await store.redeem(coupon, "key-6", NOW)

    _run(scenario)


def test_parallel_redemptions_never_overspend() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=100)
        coupons = [await _coupon(store, cid, 10) for _ in range(50)]
        results = await asyncio.gather(
            *(store.redeem(c, f"par-{i}", NOW) for i, c in enumerate(coupons)),
            return_exceptions=True,
        )
        successes = [r for r in results if isinstance(r, Coupon)]
        campaign = await store.get_campaign(cid)
        assert campaign is not None
        assert len(successes) == 10
        assert campaign.budget.spent == Money(100)

    _run(scenario)


def test_idempotency_key_expires() -> None:
    async def scenario(redis: Redis) -> None:
        store, cid = await _setup(redis, total=100, ttl=1)
        coupon = await _coupon(store, cid, 10)
        await store.redeem(coupon, "key-7", NOW)
        await asyncio.sleep(1.2)
        with pytest.raises(CouponAlreadyRedeemedError):
            await store.redeem(coupon, "key-7", NOW + timedelta(seconds=1))

    _run(scenario)
