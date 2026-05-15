"""digests

Revision ID: 20260425_03_digests
Revises: 20260425_02_posts_and_feedback
Create Date: 2026-04-26 09:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260425_03_digests"
down_revision = "20260425_02_posts_and_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("digest_type", sa.String(length=64), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("recipient_email", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "digest_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("digest_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"], name="fk_digest_items_digest_id"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], name="fk_digest_items_post_id"),
    )


def downgrade() -> None:
    op.drop_table("digest_items")
    op.drop_table("digests")
