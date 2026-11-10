"""Integration tests against a real PostgreSQL. Skipped unless DATABASE_URL is set.

DATABASE_URL must point to a disposable database: the module migrates it to a clean state
and every test truncates the tables.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from coupon_budget.adapters.pg_models import Base
from coupon_budget.adapters.pg_repo import (
    PgCampaignRepository,
    create_engine,
    make_session_factory,
)
from coupon_budget.ports.budget_store import CampaignNotFoundError
from coupon_budget.ports.repositories import (
    CampaignRecord,
    CouponRecord,
    RecordAlreadyExistsError,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is not set")

ROOT = Path(__file__).resolve().parents[2]
ENDS = datetime(2027, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _migrated_schema() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def _run[T](scenario: Callable[[AsyncEngine], Awaitable[T]]) -> T:
    async def wrapper() -> T:
        engine = create_engine(DATABASE_URL)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("TRUNCATE coupons, campaigns"))
            return await scenario(engine)
        finally:
            await engine.dispose()

    return asyncio.run(wrapper())


def test_campaign_round_trip() -> None:
    record = CampaignRecord(id="cmp-1", total_micro=5_000_000, ends_at=ENDS)

    async def scenario(engine: AsyncEngine) -> CampaignRecord | None:
        repo = PgCampaignRepository(make_session_factory(engine))
        await repo.add_campaign(record)
        return await repo.get_campaign("cmp-1")

    assert _run(scenario) == record


def test_missing_campaign_returns_none() -> None:
    async def scenario(engine: AsyncEngine) -> CampaignRecord | None:
        return await PgCampaignRepository(make_session_factory(engine)).get_campaign("nope")

    assert _run(scenario) is None


def test_duplicate_campaign_is_rejected() -> None:
    record = CampaignRecord(id="cmp-1", total_micro=1, ends_at=ENDS)

    async def scenario(engine: AsyncEngine) -> None:
        repo = PgCampaignRepository(make_session_factory(engine))
        await repo.add_campaign(record)
        await repo.add_campaign(record)

    with pytest.raises(RecordAlreadyExistsError):
        _run(scenario)


def test_coupon_round_trip() -> None:
    campaign = CampaignRecord(id="cmp-1", total_micro=1_000, ends_at=ENDS)
    coupon = CouponRecord(id="cpn-1", campaign_id="cmp-1", face_value_micro=250)

    async def scenario(engine: AsyncEngine) -> CouponRecord | None:
        repo = PgCampaignRepository(make_session_factory(engine))
        await repo.add_campaign(campaign)
        await repo.add_coupon(coupon)
        return await repo.get_coupon("cpn-1")

    assert _run(scenario) == coupon


def test_coupon_for_missing_campaign_is_rejected() -> None:
    coupon = CouponRecord(id="cpn-1", campaign_id="ghost", face_value_micro=1)

    async def scenario(engine: AsyncEngine) -> None:
        await PgCampaignRepository(make_session_factory(engine)).add_coupon(coupon)

    with pytest.raises(CampaignNotFoundError):
        _run(scenario)


def test_duplicate_coupon_is_rejected() -> None:
    campaign = CampaignRecord(id="cmp-1", total_micro=1_000, ends_at=ENDS)
    coupon = CouponRecord(id="cpn-1", campaign_id="cmp-1", face_value_micro=1)

    async def scenario(engine: AsyncEngine) -> None:
        repo = PgCampaignRepository(make_session_factory(engine))
        await repo.add_campaign(campaign)
        await repo.add_coupon(coupon)
        await repo.add_coupon(coupon)

    with pytest.raises(RecordAlreadyExistsError):
        _run(scenario)


def test_database_rejects_negative_total_even_without_the_domain() -> None:
    async def scenario(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO campaigns (id, total_micro, ends_at) VALUES ('x', -1, :e)"),
                {"e": ENDS},
            )

    with pytest.raises(IntegrityError):
        _run(scenario)


def test_coupons_table_has_no_redemption_state() -> None:
    async def scenario(engine: AsyncEngine) -> set[str]:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'coupons'"
                )
            )
            return {str(row[0]) for row in result}

    assert _run(scenario) == {"id", "campaign_id", "face_value_micro"}


def test_migrated_schema_matches_models() -> None:
    def diff(sync_conn: Connection) -> list[object]:
        ctx = MigrationContext.configure(sync_conn)
        differences: list[object] = list(compare_metadata(ctx, Base.metadata))
        return differences

    async def scenario(engine: AsyncEngine) -> list[object]:
        async with engine.connect() as conn:
            differences: list[object] = await conn.run_sync(lambda sync_conn: diff(sync_conn))
        return differences

    assert _run(scenario) == []
