"""Add alpha_sell_prediction index

Revision ID: b7d66bdfa9c2
Revises: d544c99ec19c
Create Date: 2025-05-21 15:08:14.356079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d66bdfa9c2'
down_revision: Union[str, None] = 'd544c99ec19c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("idx_alpha_sell_prediction_task_id", "alpha_sell_prediction", ["task_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_alpha_sell_prediction_task_id", "alpha_sell_prediction")
