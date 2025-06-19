"""add stake scores to miner score

Revision ID: d60e7dc289b1
Revises: e0fa93e1d673
Create Date: 2025-06-19 15:50:00.539931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd60e7dc289b1'
down_revision: Union[str, None] = 'e0fa93e1d673'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("miner_score", sa.Column("stake_removal_score", sa.Float, nullable=True))
    op.add_column("miner_score", sa.Column("stake_addition_score", sa.Float, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("miner_score", "stake_addition_score")
    op.drop_column("miner_score", "stake_removal_score")
