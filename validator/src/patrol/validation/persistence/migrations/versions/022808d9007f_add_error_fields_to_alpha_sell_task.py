"""Add error fields to AlphaSellChallengeTask

Revision ID: 022808d9007f
Revises: 50d1fdcf0d19
Create Date: 2025-05-30 09:32:49.936247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '022808d9007f'
down_revision: Union[str, None] = '50d1fdcf0d19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("alpha_sell_challenge_task", sa.Column("has_error", sa.Boolean, nullable=False))
    op.add_column("alpha_sell_challenge_task", sa.Column("error_message", sa.String, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("alpha_sell_challenge_task", "has_error")
    op.drop_column("alpha_sell_challenge_task", "error_message")
