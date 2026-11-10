"""Interface for campaign and coupon storage. Adapters and test fakes implement it."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from coupon_budget.domain.budget import Campaign
from coupon_budget.domain.coupon import Coupon


class CampaignNotFoundError(Exception):
    """No campaign with this id."""


class CouponNotFoundError(Exception):
    """No coupon with this id."""


class IdempotencyKeyReusedError(Exception):
    """The same Idempotency-Key was used for a different coupon."""


class BudgetStore(Protocol):
    """Redemption is one operation on purpose: the check and the charge must be atomic together."""

    async def add_campaign(self, campaign: Campaign) -> None: ...

    async def add_coupon(self, coupon: Coupon) -> None: ...

    async def get_campaign(self, campaign_id: str) -> Campaign | None: ...

    async def get_coupon(self, coupon_id: str) -> Coupon | None: ...

    async def redeem(self, coupon_id: str, idempotency_key: str, now: datetime) -> Coupon:
        """Redeem atomically. A repeated key for the same coupon returns the stored result
        without charging again. Domain errors (budget, expiry, already redeemed) propagate."""
        ...
