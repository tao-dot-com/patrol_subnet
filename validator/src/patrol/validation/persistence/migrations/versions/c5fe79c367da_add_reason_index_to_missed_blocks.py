"""add_reason_index_to_missed_blocks

Revision ID: c5fe79c367da
Revises: f6a173000c63
Create Date: 2025-05-06 13:03:37.793939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5fe79c367da'
down_revision: Union[str, None] = 'f6a173000c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add index for the reason column
    op.create_index("idx_missed_blocks_reason", "missed_blocks", columns=["reason"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_missed_blocks_reason", "missed_blocks")