"""SQLAlchemy models for campaign and coupon records.

Budget spend is not stored here; it lives in Redis (see docs/adr/0001-atomicity-strategy.md).
The schema is created by the Alembic migration in migrations/versions/. Keep both in sync:
tests/integration/test_pg_repo.py fails if the models and the migrated schema differ.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CampaignRow(Base):
    __tablename__ = "campaigns"
    __table_args__ = (CheckConstraint("total_micro >= 0", name="campaigns_total_nonneg"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CouponRow(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("face_value_micro >= 0", name="coupons_face_value_nonneg"),
        CheckConstraint("redeemed = (redeemed_at IS NOT NULL)", name="coupons_redeemed_consistent"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="RESTRICT", name="coupons_campaign_id_fkey"),
        index=True,
    )
    face_value_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
