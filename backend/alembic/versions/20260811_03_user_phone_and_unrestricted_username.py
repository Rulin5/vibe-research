"""Add registration phone and allow Unicode usernames.

Revision ID: 20260811_03
Revises: 20260811_02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_03"
down_revision = "20260811_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "username", existing_type=sa.String(length=32), type_=sa.Text(), postgresql_using="username::text")
    op.add_column("users", sa.Column("phone", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
    op.alter_column("users", "username", existing_type=sa.Text(), type_=sa.String(length=32), postgresql_using="left(username, 32)")
