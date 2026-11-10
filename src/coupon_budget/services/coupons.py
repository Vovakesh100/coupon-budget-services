"""Orchestration for the four TZ operations.

Write order when a record and the budget both change: the PostgreSQL record first, then the
Redis budget state. If the second write fails, the record exists without budget state, so a
redemption returns "not found" and no money moves. The reverse order could leave budget state
without a record, which reports would show as missing. Failures between the two writes are not
repaired automatically yet (see docs/adr/0002-storage-split.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from coupon_budget.config.rules import Rules
from coupon_budget.domain.budget import Budget, Campaign
from coupon_budget.domain.coupon import Coupon
from coupon_budget.domain.money import Money
from coupon_budget.ports.budget_store import BudgetStore, CampaignNotFoundError
from coupon_budget.ports.repositories import (
    CampaignRecord,
    CampaignRepository,
    CouponRecord,
)


class LimitExceededError(ValueError):
    """A value is above a limit from the settings file."""


class InvalidRequestError(ValueError):
    """A value is well-typed but breaks a business rule (for example, a past end date)."""


@dataclass(frozen=True, slots=True)
class BudgetView:
    campaign_id: str
    allocated: Money
    spent: Money
    remaining: Money


def _new_id() -> str:
    return uuid.uuid4().hex


class CouponService:
    def __init__(
        self,
        records: CampaignRepository,
        budget: BudgetStore,
        rules: Rules,
        clock: Callable[[], datetime],
        new_id: Callable[[], str] = _new_id,
    ) -> None:
        self._records = records
        self._budget = budget
        self._rules = rules
        self._clock = clock
        self._new_id = new_id

    async def create_campaign(self, total_micro: int, ends_at: datetime) -> CampaignRecord:
        if ends_at.tzinfo is None:
            raise InvalidRequestError("ends_at must include a timezone")
        if ends_at <= self._clock():
            raise InvalidRequestError("ends_at must be in the future")
        if total_micro <= 0:
            raise InvalidRequestError("total_micro must be positive")
        if total_micro > self._rules.max_campaign_budget_micro:
            raise LimitExceededError("total_micro is above the campaign limit")
        record = CampaignRecord(id=self._new_id(), total_micro=total_micro, ends_at=ends_at)
        await self._records.add_campaign(record)
        await self._budget.add_campaign(
            Campaign(id=record.id, budget=Budget(Money(total_micro)), ends_at=ends_at)
        )
        return record

    async def issue_coupon(self, campaign_id: str, face_value_micro: int) -> CouponRecord:
        if face_value_micro <= 0:
            raise InvalidRequestError("face_value_micro must be positive")
        if face_value_micro > self._rules.max_coupon_face_value_micro:
            raise LimitExceededError("face_value_micro is above the coupon limit")
        if await self._records.get_campaign(campaign_id) is None:
            raise CampaignNotFoundError(campaign_id)
        record = CouponRecord(
            id=self._new_id(), campaign_id=campaign_id, face_value_micro=face_value_micro
        )
        await self._records.add_coupon(record)
        await self._budget.add_coupon(
            Coupon(id=record.id, campaign_id=campaign_id, face_value=Money(face_value_micro))
        )
        return record

    async def redeem(self, coupon_id: str, idempotency_key: str) -> Coupon:
        return await self._budget.redeem(coupon_id, idempotency_key, self._clock())

    async def get_budget(self, campaign_id: str) -> BudgetView:
        campaign = await self._budget.get_campaign(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(campaign_id)
        budget = campaign.budget
        return BudgetView(
            campaign_id=campaign_id,
            allocated=budget.total,
            spent=budget.spent,
            remaining=budget.remaining,
        )
