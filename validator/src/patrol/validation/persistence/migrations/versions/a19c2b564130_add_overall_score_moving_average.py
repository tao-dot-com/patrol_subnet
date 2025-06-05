"""add overall score moving average

Revision ID: a19c2b564130
Revises: cf1cc0b57040
Create Date: 2025-04-07 11:53:55.890155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a19c2b564130'
down_revision: Union[str, None] = 'cf1cc0b57040'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("miner_score", sa.Column("overall_score_moving_average", sa.Float, nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("miner_score", "overall_score_moving_average")
