"""unique digest run slots

Revision ID: 20260725_01_digest_slots
Revises: 20260514_01_read_later
Create Date: 2026-07-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260725_01_digest_slots"
down_revision = "20260514_01_read_later"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("digests", sa.Column("delivery_slot_key", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_digests_delivery_slot_key",
        "digests",
        ["delivery_slot_key"],
        unique=True,
        postgresql_where=sa.text("delivery_slot_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_digests_delivery_slot_key", table_name="digests")
    op.drop_column("digests", "delivery_slot_key")
