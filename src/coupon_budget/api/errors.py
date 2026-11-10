"""Maps domain and port errors to HTTP status codes and stable error codes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from coupon_budget.domain.budget import BudgetExceededError
from coupon_budget.domain.coupon import CampaignExpiredError, CouponAlreadyRedeemedError
from coupon_budget.ports.budget_store import (
    CampaignNotFoundError,
    CouponNotFoundError,
    IdempotencyKeyReusedError,
)
from coupon_budget.ports.repositories import RecordAlreadyExistsError
from coupon_budget.services.coupons import InvalidRequestError, LimitExceededError

ERROR_MAP: dict[type[Exception], tuple[int, str]] = {
    CampaignNotFoundError: (404, "campaign_not_found"),
    CouponNotFoundError: (404, "coupon_not_found"),
    CampaignExpiredError: (409, "campaign_expired"),
    CouponAlreadyRedeemedError: (409, "coupon_already_redeemed"),
    BudgetExceededError: (409, "budget_exceeded"),
    IdempotencyKeyReusedError: (409, "idempotency_key_reused"),
    RecordAlreadyExistsError: (409, "already_exists"),
    LimitExceededError: (422, "limit_exceeded"),
    InvalidRequestError: (422, "invalid_request"),
    RedisConnectionError: (503, "budget_store_unavailable"),
    RedisTimeoutError: (503, "budget_store_unavailable"),
}


def install_error_handlers(app: FastAPI) -> None:
    for exc_type, (status, code) in ERROR_MAP.items():

        app.add_exception_handler(exc_type, _make_handler(status, code))


def _make_handler(
    status: int, code: str
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": code, "message": str(exc)})

    return handler
