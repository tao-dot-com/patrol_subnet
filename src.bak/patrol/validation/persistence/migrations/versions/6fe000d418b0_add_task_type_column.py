"""Add task_type column

Revision ID: 6fe000d418b0
Revises: c5fe79c367da
Create Date: 2025-05-12 12:28:46.617826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fe000d418b0'
down_revision: Union[str, None] = 'c5fe79c367da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("miner_score", sa.Column("task_type", sa.String))
    op.create_index("idx_miner_score_task_type", "miner_score", ["task_type"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_miner_score_task_type", "miner_score", if_exists=True)
    op.drop_column("miner_score", "task_type")
