"""read_later

Revision ID: 20260514_01_read_later
Revises: 20260425_03_digests
Create Date: 2026-05-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260514_01_read_later"
down_revision = "20260425_03_digests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "read_later",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], name="fk_read_later_post_id"),
        sa.UniqueConstraint("post_id", name="uq_read_later_post_id"),
    )


def downgrade() -> None:
    op.drop_table("read_later")
