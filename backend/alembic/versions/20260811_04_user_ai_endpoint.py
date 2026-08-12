"""Store the encrypted credential's non-secret endpoint metadata.

Revision ID: 20260811_04
Revises: 20260811_03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_04"
down_revision = "20260811_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_ai_credentials", sa.Column("base_url", sa.Text(), nullable=True))
    op.add_column("user_ai_credentials", sa.Column("model_id", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("user_ai_credentials", "model_id")
    op.drop_column("user_ai_credentials", "base_url")
