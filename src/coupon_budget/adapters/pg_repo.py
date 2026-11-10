"""PostgreSQL implementation of CampaignRepository (SQLAlchemy 2 async over asyncpg)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from coupon_budget.adapters.pg_models import CampaignRow, CouponRow
from coupon_budget.ports.budget_store import CampaignNotFoundError
from coupon_budget.ports.repositories import (
    CampaignRecord,
    CouponRecord,
    RecordAlreadyExistsError,
)

# PostgreSQL error codes: https://www.postgresql.org/docs/16/errcodes-appendix.html
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"

SessionFactory = async_sessionmaker[AsyncSession]


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(engine, expire_on_commit=False)


def _sqlstate(exc: IntegrityError) -> str | None:
    """asyncpg puts the PostgreSQL error code on the driver exception, which SQLAlchemy wraps."""
    cause: BaseException | None = exc.orig
    while cause is not None:
        state = getattr(cause, "sqlstate", None)
        if isinstance(state, str):
            return state
        cause = cause.__cause__
    return None


class PgCampaignRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    async def add_campaign(self, record: CampaignRecord) -> None:
        row = CampaignRow(id=record.id, total_micro=record.total_micro, ends_at=record.ends_at)
        async with self._sessions() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if _sqlstate(exc) == UNIQUE_VIOLATION:
                    raise RecordAlreadyExistsError(record.id) from exc
                raise

    async def get_campaign(self, campaign_id: str) -> CampaignRecord | None:
        async with self._sessions() as session:
            row = await session.get(CampaignRow, campaign_id)
        if row is None:
            return None
        return CampaignRecord(id=row.id, total_micro=row.total_micro, ends_at=row.ends_at)

    async def add_coupon(self, record: CouponRecord) -> None:
        row = CouponRow(
            id=record.id,
            campaign_id=record.campaign_id,
            face_value_micro=record.face_value_micro,
        )
        async with self._sessions() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                state = _sqlstate(exc)
                if state == FOREIGN_KEY_VIOLATION:
                    raise CampaignNotFoundError(record.campaign_id) from exc
                if state == UNIQUE_VIOLATION:
                    raise RecordAlreadyExistsError(record.id) from exc
                raise

    async def get_coupon(self, coupon_id: str) -> CouponRecord | None:
        async with self._sessions() as session:
            row = await session.get(CouponRow, coupon_id)
        if row is None:
            return None
        return CouponRecord(
            id=row.id,
            campaign_id=row.campaign_id,
            face_value_micro=row.face_value_micro,
        )
