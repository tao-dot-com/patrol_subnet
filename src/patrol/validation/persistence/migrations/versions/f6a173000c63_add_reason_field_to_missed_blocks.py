"""add_reason_field_to_missed_blocks_table

Revision ID: f6a173000c63
Revises: 1bd98dce73f4
Create Date: 2025-05-02 11:38:19.531224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a173000c63'
down_revision: Union[str, None] = '1bd98dce73f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the new reason column
    op.add_column(
        'missed_blocks',
        sa.Column('reason', sa.String(), nullable=True)
    )

    op.create_index("idx_missed_blocks_reason", "missed_blocks", columns=["reason"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_missed_blocks_reason", "missed_blocks")
    op.drop_column("missed_blocks", "reason")