"""Create campaigns and coupons tables (records only; budget spend stays in Redis).

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("total_micro", sa.BigInteger(), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total_micro >= 0", name="campaigns_total_nonneg"),
    )
    op.create_table(
        "coupons",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("face_value_micro", sa.BigInteger(), nullable=False),
        sa.Column("redeemed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="coupons_campaign_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("face_value_micro >= 0", name="coupons_face_value_nonneg"),
        sa.CheckConstraint(
            "redeemed = (redeemed_at IS NOT NULL)", name="coupons_redeemed_consistent"
        ),
    )
    op.create_index("ix_coupons_campaign_id", "coupons", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_coupons_campaign_id", table_name="coupons")
    op.drop_table("coupons")
    op.drop_table("campaigns")
