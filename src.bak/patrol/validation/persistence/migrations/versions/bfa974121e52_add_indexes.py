"""add indexes

Revision ID: bfa974121e52
Revises: a19c2b564130
Create Date: 2025-04-07 15:35:30.435290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfa974121e52'
down_revision: Union[str, None] = 'a19c2b564130'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("idx_miner_id", "miner_score", columns=["uid", "hotkey"])
    op.create_index("idx_miner_score_created_at", "miner_score", columns=["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_miner_id", "miner_score")
    op.drop_index("idx_miner_score_created_at", "miner_score")
