"""Request and response bodies. Amounts are strict integers (micro units): no floats, no bools."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class CreateCampaignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_micro: StrictInt = Field(description="Campaign budget in micro units.")
    ends_at: datetime = Field(description="Campaign end, ISO 8601 with a timezone.")


class CampaignOut(BaseModel):
    id: str
    total_micro: int
    ends_at: datetime


class CreateCouponIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_value_micro: StrictInt = Field(description="Coupon face value in micro units.")


class CouponOut(BaseModel):
    id: str
    campaign_id: str
    face_value_micro: int


class RedeemOut(BaseModel):
    coupon_id: str
    campaign_id: str
    face_value_micro: int
    redeemed: bool


class BudgetOut(BaseModel):
    campaign_id: str
    allocated_micro: int
    spent_micro: int
    remaining_micro: int


class ErrorOut(BaseModel):
    error: str = Field(description="Stable machine-readable code.")
    message: str
