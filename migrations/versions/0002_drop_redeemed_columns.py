"""Drop redeemed state from PostgreSQL. Redemption status lives only in Redis (ADR 0001, 0002).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("coupons_redeemed_consistent", "coupons", type_="check")
    op.drop_column("coupons", "redeemed_at")
    op.drop_column("coupons", "redeemed")


def downgrade() -> None:
    op.add_column(
        "coupons",
        sa.Column("redeemed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("coupons", sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "coupons_redeemed_consistent",
        "coupons",
        "redeemed = (redeemed_at IS NOT NULL)",
    )
