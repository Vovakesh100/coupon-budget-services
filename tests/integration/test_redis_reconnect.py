"""Integration test: a dropped Redis connection does not fail the next operation.

Reproduces the failure seen after `docker compose restart redis`: the pool holds a connection
the server has closed. CLIENT KILL closes every client connection except the caller's own.
Skipped unless REDIS_URL is set.
"""

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis

from coupon_budget.adapters.redis_budget import RedisBudgetStore
from coupon_budget.adapters.redis_client import build_redis_client
from coupon_budget.domain.budget import Budget, Campaign
from coupon_budget.domain.coupon import Coupon
from coupon_budget.domain.money import Money

REDIS_URL = os.environ.get("REDIS_URL", "")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL is not set")

NOW = datetime(2026, 6, 1, tzinfo=UTC)
ENDS = datetime(2027, 1, 1, tzinfo=UTC)


def _run[T](scenario: Callable[[Redis], Awaitable[T]]) -> T:
    async def wrapper() -> T:
        client = build_redis_client(REDIS_URL)
        try:
            return await scenario(client)
        finally:
            await client.aclose()

    return asyncio.run(wrapper())


async def _kill_client_connections() -> None:
    admin = Redis.from_url(REDIS_URL)
    try:
        await admin.client_kill_filter(_type="normal", skipme=True)
    finally:
        await admin.aclose()


def _scenario_factory(
    campaign_id: str, first_coupon: str, second_coupon: str
) -> Callable[[Redis], Awaitable[tuple[str, str, str]]]:
    async def scenario(client: Redis) -> tuple[str, str, str]:
        store = RedisBudgetStore(client, idempotency_ttl_seconds=3600)
        await store.add_campaign(
            Campaign(id=campaign_id, budget=Budget(Money(500_000)), ends_at=ENDS)
        )
        for coupon_id in (first_coupon, second_coupon):
            await store.add_coupon(
                Coupon(id=coupon_id, campaign_id=campaign_id, face_value=Money(120_000))
            )
        await store.redeem(first_coupon, f"key-{uuid.uuid4().hex}", NOW)
        # The pool now holds a live connection. Drop it on the server side.
        await _kill_client_connections()
        await asyncio.sleep(0.1)
        # First operation after the drop: this is the call that failed inside the app.
        campaign = await store.get_campaign(campaign_id)
        assert campaign is not None
        spent_after_drop = str(campaign.budget.spent.micro)
        redeemed = await store.redeem(second_coupon, f"key-{uuid.uuid4().hex}", NOW)
        final = await store.get_campaign(campaign_id)
        assert final is not None
        return spent_after_drop, str(redeemed.redeemed), str(final.budget.spent.micro)

    return scenario


def test_operations_survive_a_dropped_connection() -> None:
    suffix = uuid.uuid4().hex[:12]
    spent_after_drop, redeemed, final_spent = _run(
        _scenario_factory(f"rc-{suffix}", f"ra-{suffix}", f"rb-{suffix}")
    )
    assert spent_after_drop == "120000"
    assert redeemed == "True"
    assert final_spent == "240000"
