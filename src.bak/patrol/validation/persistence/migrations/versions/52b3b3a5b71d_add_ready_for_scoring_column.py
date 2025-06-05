"""add ready for scoring column

Revision ID: 52b3b3a5b71d
Revises: 022808d9007f
Create Date: 2025-06-02 17:28:35.493929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52b3b3a5b71d'
down_revision: Union[str, None] = '022808d9007f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("alpha_sell_challenge_batch", sa.Column("is_ready_for_scoring", sa.Boolean, nullable=False))
    op.create_index("idx_is_ready_for_scoring", "alpha_sell_challenge_batch", ["is_ready_for_scoring"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_is_ready_for_scoring", table_name="alpha_sell_challenge_batch")
    op.drop_column("alpha_sell_challenge_batch", "is_ready_for_scoring")
