"""In-memory CampaignRepository for service tests. Mirrors the PostgreSQL adapter's errors."""

from __future__ import annotations

from coupon_budget.ports.budget_store import CampaignNotFoundError
from coupon_budget.ports.repositories import (
    CampaignRecord,
    CouponRecord,
    RecordAlreadyExistsError,
)


class MemoryCampaignRepository:
    def __init__(self) -> None:
        self._campaigns: dict[str, CampaignRecord] = {}
        self._coupons: dict[str, CouponRecord] = {}

    async def add_campaign(self, record: CampaignRecord) -> None:
        if record.id in self._campaigns:
            raise RecordAlreadyExistsError(record.id)
        self._campaigns[record.id] = record

    async def get_campaign(self, campaign_id: str) -> CampaignRecord | None:
        return self._campaigns.get(campaign_id)

    async def add_coupon(self, record: CouponRecord) -> None:
        if record.campaign_id not in self._campaigns:
            raise CampaignNotFoundError(record.campaign_id)
        if record.id in self._coupons:
            raise RecordAlreadyExistsError(record.id)
        self._coupons[record.id] = record

    async def get_coupon(self, coupon_id: str) -> CouponRecord | None:
        return self._coupons.get(coupon_id)
