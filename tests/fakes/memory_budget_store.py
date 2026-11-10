"""In-memory BudgetStore for service tests. A single asyncio lock makes redeem atomic."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from coupon_budget.domain.budget import Campaign
from coupon_budget.domain.coupon import Coupon
from coupon_budget.domain.coupon import redeem as redeem_coupon
from coupon_budget.ports.budget_store import (
    CampaignNotFoundError,
    CouponNotFoundError,
    IdempotencyKeyReusedError,
)


class MemoryBudgetStore:
    def __init__(self, idempotency_ttl_seconds: int) -> None:
        self._ttl = timedelta(seconds=idempotency_ttl_seconds)
        self._campaigns: dict[str, Campaign] = {}
        self._coupons: dict[str, Coupon] = {}
        self._keys: dict[str, tuple[str, datetime]] = {}  # key -> (coupon_id, expires_at)
        self._lock = asyncio.Lock()

    async def add_campaign(self, campaign: Campaign) -> None:
        async with self._lock:
            self._campaigns[campaign.id] = campaign

    async def add_coupon(self, coupon: Coupon) -> None:
        async with self._lock:
            self._coupons[coupon.id] = coupon

    async def get_campaign(self, campaign_id: str) -> Campaign | None:
        return self._campaigns.get(campaign_id)

    async def get_coupon(self, coupon_id: str) -> Coupon | None:
        return self._coupons.get(coupon_id)

    def _forget_expired_keys(self, now: datetime) -> None:
        expired = [key for key, (_, expires_at) in self._keys.items() if now >= expires_at]
        for key in expired:
            del self._keys[key]

    async def redeem(self, coupon_id: str, idempotency_key: str, now: datetime) -> Coupon:
        async with self._lock:
            self._forget_expired_keys(now)
            seen = self._keys.get(idempotency_key)
            if seen is not None:
                stored_coupon_id, _ = seen
                if stored_coupon_id != coupon_id:
                    raise IdempotencyKeyReusedError(idempotency_key)
                return self._coupons[stored_coupon_id]
            coupon = self._coupons.get(coupon_id)
            if coupon is None:
                raise CouponNotFoundError(coupon_id)
            campaign = self._campaigns.get(coupon.campaign_id)
            if campaign is None:
                raise CampaignNotFoundError(coupon.campaign_id)
            new_campaign, new_coupon = redeem_coupon(campaign, coupon, now)
            self._campaigns[campaign.id] = new_campaign
            self._coupons[coupon.id] = new_coupon
            self._keys[idempotency_key] = (coupon_id, now + self._ttl)
            return new_coupon
