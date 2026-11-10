import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from coupon_budget.domain.budget import Budget, BudgetExceededError, Campaign
from coupon_budget.domain.coupon import Coupon, CouponAlreadyRedeemedError
from coupon_budget.domain.money import Money
from coupon_budget.ports.budget_store import CouponNotFoundError, IdempotencyKeyReusedError
from tests.fakes.memory_budget_store import MemoryBudgetStore

ENDS = datetime(2027, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _store(total: int = 100, ttl: int = 3600) -> MemoryBudgetStore:
    store = MemoryBudgetStore(idempotency_ttl_seconds=ttl)
    await store.add_campaign(Campaign(id="c", budget=Budget(Money(total)), ends_at=ENDS))
    return store


async def _coupon(store: MemoryBudgetStore, coupon_id: str, face: int) -> None:
    await store.add_coupon(Coupon(id=coupon_id, campaign_id="c", face_value=Money(face)))


def test_repeated_key_does_not_charge_twice() -> None:
    async def scenario() -> None:
        store = await _store()
        await _coupon(store, "k1", 10)
        await store.redeem("k1", "key-A", NOW)
        await store.redeem("k1", "key-A", NOW)
        campaign = await store.get_campaign("c")
        assert campaign is not None
        assert campaign.budget.spent == Money(10)

    asyncio.run(scenario())


def test_same_key_for_another_coupon_is_refused() -> None:
    async def scenario() -> None:
        store = await _store()
        await _coupon(store, "k1", 10)
        await _coupon(store, "k2", 10)
        await store.redeem("k1", "key-A", NOW)
        with pytest.raises(IdempotencyKeyReusedError):
            await store.redeem("k2", "key-A", NOW)

    asyncio.run(scenario())


def test_key_is_forgotten_after_ttl() -> None:
    async def scenario() -> None:
        store = await _store(ttl=60)
        await _coupon(store, "k1", 10)
        await store.redeem("k1", "key-A", NOW)
        with pytest.raises(CouponAlreadyRedeemedError):
            await store.redeem("k1", "key-A", NOW + timedelta(seconds=60))

    asyncio.run(scenario())


def test_budget_refusal_stores_no_key() -> None:
    async def scenario() -> None:
        store = await _store(total=5)
        await _coupon(store, "k1", 10)
        with pytest.raises(BudgetExceededError):
            await store.redeem("k1", "key-A", NOW)
        campaign = await store.get_campaign("c")
        assert campaign is not None
        assert campaign.budget.spent == Money(0)

    asyncio.run(scenario())


def test_unknown_coupon_raises() -> None:
    async def scenario() -> None:
        store = await _store()
        with pytest.raises(CouponNotFoundError):
            await store.redeem("missing", "key-A", NOW)

    asyncio.run(scenario())


def test_parallel_redemptions_do_not_overspend() -> None:
    async def scenario() -> None:
        store = await _store(total=100)
        for i in range(20):
            await _coupon(store, f"k{i}", 10)
        results = await asyncio.gather(
            *(store.redeem(f"k{i}", f"key-{i}", NOW) for i in range(20)),
            return_exceptions=True,
        )
        successes = [r for r in results if isinstance(r, Coupon)]
        campaign = await store.get_campaign("c")
        assert campaign is not None
        assert len(successes) == 10
        assert campaign.budget.spent == Money(100)

    asyncio.run(scenario())
