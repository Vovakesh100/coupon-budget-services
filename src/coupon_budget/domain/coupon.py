"""Coupon rules: issue while the campaign runs, redeem once, for the full face value."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from coupon_budget.domain.budget import Campaign
from coupon_budget.domain.money import Money


class CampaignExpiredError(Exception):
    """The campaign has ended; no coupon can be issued or redeemed."""


class CouponAlreadyRedeemedError(Exception):
    """This coupon was already redeemed once."""


@dataclass(frozen=True, slots=True)
class Coupon:
    id: str
    campaign_id: str
    face_value: Money
    redeemed: bool = False

    def __post_init__(self) -> None:
        if self.face_value.micro == 0:
            raise ValueError("face value must be positive")


def issue_coupon(campaign: Campaign, coupon_id: str, face_value: Money, now: datetime) -> Coupon:
    if not campaign.is_active(now):
        raise CampaignExpiredError(campaign.id)
    return Coupon(id=coupon_id, campaign_id=campaign.id, face_value=face_value)


def redeem(campaign: Campaign, coupon: Coupon, now: datetime) -> tuple[Campaign, Coupon]:
    """Redeem the whole face value. No amount parameter, so partial redemption is impossible."""
    if coupon.campaign_id != campaign.id:
        raise ValueError("coupon belongs to another campaign")
    if coupon.redeemed:
        raise CouponAlreadyRedeemedError(coupon.id)
    if not campaign.is_active(now):
        raise CampaignExpiredError(campaign.id)
    new_budget = campaign.budget.charge(coupon.face_value)
    return replace(campaign, budget=new_budget), replace(coupon, redeemed=True)
