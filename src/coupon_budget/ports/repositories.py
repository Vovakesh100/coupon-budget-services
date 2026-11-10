"""Interface for campaign and coupon records (definitions, not budget state).

Budget spend and the redeemed flag used by the atomic redemption live in the budget store.
These records are the durable copy of what was issued. Adapters and test fakes implement it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from coupon_budget.ports.budget_store import CampaignNotFoundError

MAX_ID_LENGTH = 64


class RecordAlreadyExistsError(Exception):
    """A campaign or coupon with this id is already stored."""


def _check_id(value: str) -> None:
    if not value or len(value) > MAX_ID_LENGTH:
        raise ValueError(f"id must be 1..{MAX_ID_LENGTH} characters")


def _check_micro(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("amounts must be non-negative integers in micro units")


@dataclass(frozen=True, slots=True)
class CampaignRecord:
    id: str
    total_micro: int
    ends_at: datetime

    def __post_init__(self) -> None:
        _check_id(self.id)
        _check_micro(self.total_micro)
        if self.ends_at.tzinfo is None:
            raise ValueError("ends_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CouponRecord:
    id: str
    campaign_id: str
    face_value_micro: int
    redeemed: bool = False
    redeemed_at: datetime | None = None

    def __post_init__(self) -> None:
        _check_id(self.id)
        _check_id(self.campaign_id)
        _check_micro(self.face_value_micro)
        if self.redeemed != (self.redeemed_at is not None):
            raise ValueError("redeemed_at must be set exactly when redeemed is true")
        if self.redeemed_at is not None and self.redeemed_at.tzinfo is None:
            raise ValueError("redeemed_at must be timezone-aware")


class CampaignRepository(Protocol):
    async def add_campaign(self, record: CampaignRecord) -> None:
        """Raises RecordAlreadyExistsError if the id is taken."""
        ...

    async def get_campaign(self, campaign_id: str) -> CampaignRecord | None: ...

    async def add_coupon(self, record: CouponRecord) -> None:
        """Raises CampaignNotFoundError if the campaign is missing and
        RecordAlreadyExistsError if the coupon id is taken."""
        ...

    async def get_coupon(self, coupon_id: str) -> CouponRecord | None: ...


__all__ = [
    "MAX_ID_LENGTH",
    "CampaignNotFoundError",
    "CampaignRecord",
    "CampaignRepository",
    "CouponRecord",
    "RecordAlreadyExistsError",
]
