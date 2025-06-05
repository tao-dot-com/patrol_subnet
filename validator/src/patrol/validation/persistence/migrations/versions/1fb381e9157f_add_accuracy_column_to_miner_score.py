"""Add accuracy column to miner_score

Revision ID: 1fb381e9157f
Revises: 616f4febd39c
Create Date: 2025-05-27 16:22:18.074607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fb381e9157f'
down_revision: Union[str, None] = '616f4febd39c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("miner_score", sa.Column("accuracy_score", sa.Float, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("miner_score", "accuracy_score")
