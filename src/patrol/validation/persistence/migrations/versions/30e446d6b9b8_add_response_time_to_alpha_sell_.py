"""Add response_time to alpha_sell_challenge table

Revision ID: 30e446d6b9b8
Revises: b7d66bdfa9c2
Create Date: 2025-05-21 18:24:03.768743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30e446d6b9b8'
down_revision: Union[str, None] = 'b7d66bdfa9c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("alpha_sell_challenge", sa.Column("response_time", sa.Float))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("alpha_sell_challenge", "response_time")
