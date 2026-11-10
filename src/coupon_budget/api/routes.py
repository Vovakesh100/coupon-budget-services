"""The four routes from docs/TZ.md. Paths and bodies must not change without an owner decision."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status

from coupon_budget.api.schemas import (
    BudgetOut,
    CampaignOut,
    CouponOut,
    CreateCampaignIn,
    CreateCouponIn,
    RedeemOut,
)
from coupon_budget.services.coupons import CouponService

router = APIRouter()

IDEMPOTENCY_KEY_MAX_LENGTH = 255


def get_service(request: Request) -> CouponService:
    service: CouponService = request.app.state.service
    return service


ServiceDep = Annotated[CouponService, Depends(get_service)]
IdempotencyKeyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=IDEMPOTENCY_KEY_MAX_LENGTH),
]


@router.post("/campaigns", status_code=status.HTTP_201_CREATED, response_model=CampaignOut)
async def create_campaign(body: CreateCampaignIn, service: ServiceDep) -> CampaignOut:
    record = await service.create_campaign(body.total_micro, body.ends_at)
    return CampaignOut(id=record.id, total_micro=record.total_micro, ends_at=record.ends_at)


@router.post(
    "/campaigns/{campaign_id}/coupons",
    status_code=status.HTTP_201_CREATED,
    response_model=CouponOut,
)
async def issue_coupon(campaign_id: str, body: CreateCouponIn, service: ServiceDep) -> CouponOut:
    record = await service.issue_coupon(campaign_id, body.face_value_micro)
    return CouponOut(
        id=record.id,
        campaign_id=record.campaign_id,
        face_value_micro=record.face_value_micro,
    )


@router.post("/coupons/{coupon_id}/redeem", response_model=RedeemOut)
async def redeem_coupon(
    coupon_id: str,
    service: ServiceDep,
    idempotency_key: IdempotencyKeyHeader,
) -> RedeemOut:
    coupon = await service.redeem(coupon_id, idempotency_key)
    return RedeemOut(
        coupon_id=coupon.id,
        campaign_id=coupon.campaign_id,
        face_value_micro=int(coupon.face_value.micro),
        redeemed=coupon.redeemed,
    )


@router.get("/campaigns/{campaign_id}/budget", response_model=BudgetOut)
async def get_budget(campaign_id: str, service: ServiceDep) -> BudgetOut:
    view = await service.get_budget(campaign_id)
    return BudgetOut(
        campaign_id=view.campaign_id,
        allocated_micro=int(view.allocated.micro),
        spent_micro=int(view.spent.micro),
        remaining_micro=int(view.remaining.micro),
    )
