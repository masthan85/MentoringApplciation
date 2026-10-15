"""regions: the user's country and time zone

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("country", sa.String(2)))
    op.add_column("profiles", sa.Column("timezone", sa.String(64)))
    op.alter_column("profiles", "english_variant", type_=sa.String(5))


def downgrade() -> None:
    op.drop_column("profiles", "timezone")
    op.drop_column("profiles", "country")
