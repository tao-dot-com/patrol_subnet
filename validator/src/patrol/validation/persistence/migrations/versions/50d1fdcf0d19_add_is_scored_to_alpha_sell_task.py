"""Add is_scored to alpha_sell_task

Revision ID: 50d1fdcf0d19
Revises: 1fb381e9157f
Create Date: 2025-05-28 16:59:02.470297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50d1fdcf0d19'
down_revision: Union[str, None] = '1fb381e9157f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("alpha_sell_challenge_task", sa.Column("is_scored", sa.Boolean, nullable=False, default=False))
    op.create_index("idx_alpha_sell_task_is_scored", "alpha_sell_challenge_task", ["is_scored"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_alpha_sell_task_is_scored", "alpha_sell_challenge_task")
    op.drop_column("alpha_sell_challenge_task", "is_scored")

