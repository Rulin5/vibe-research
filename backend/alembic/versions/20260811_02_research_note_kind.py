"""Add durable display classification to user research notes.

Revision ID: 20260811_02
Revises: 20260811_01
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_02"
down_revision = "20260811_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_notes",
        sa.Column("kind", sa.String(length=64), nullable=False, server_default="general"),
    )
    op.alter_column("research_notes", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("research_notes", "kind")
