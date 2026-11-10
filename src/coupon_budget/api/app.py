"""FastAPI application factory.

create_app(service=...) takes a ready service (used by tests). create_app() with no argument
builds the real service from environment variables on startup: DATABASE_URL, REDIS_URL and
SETTINGS_FILE. Nothing is read at import time.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from redis.asyncio import Redis

from coupon_budget.adapters.pg_repo import PgCampaignRepository, create_engine, make_session_factory
from coupon_budget.adapters.redis_budget import RedisBudgetStore
from coupon_budget.api.errors import install_error_handlers
from coupon_budget.api.routes import router
from coupon_budget.config.database import database_url_from_env, redis_url_from_env
from coupon_budget.config.rules import load_rules_from_env
from coupon_budget.services.coupons import CouponService


def _clock() -> datetime:
    return datetime.now(UTC)


def _build_service_from_env(app: FastAPI) -> CouponService:
    environ = os.environ
    rules = load_rules_from_env(environ)
    engine = create_engine(database_url_from_env(environ))
    redis = Redis.from_url(redis_url_from_env(environ))
    app.state.engine = engine
    app.state.redis = redis
    return CouponService(
        records=PgCampaignRepository(make_session_factory(engine)),
        budget=RedisBudgetStore(redis, rules.idempotency_key_ttl_seconds),
        rules=rules,
        clock=_clock,
    )


def create_app(service: CouponService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if service is None:
            app.state.service = _build_service_from_env(app)
        yield
        if service is None:
            await app.state.redis.aclose()
            await app.state.engine.dispose()

    app = FastAPI(
        title="coupon-budget-service",
        version="0.1.0",
        description="Issues coupons against campaign budgets. Amounts are integer micro units.",
        lifespan=lifespan,
    )
    if service is not None:
        app.state.service = service
    app.include_router(router)
    install_error_handlers(app)
    return app
