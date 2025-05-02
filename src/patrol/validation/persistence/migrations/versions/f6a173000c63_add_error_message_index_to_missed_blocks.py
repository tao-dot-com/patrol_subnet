"""add_error_message_index_to_missed_blocks_table

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
    op.create_index("idx_missed_blocks_error_message", "missed_blocks", 
                   columns=["error_message"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_missed_blocks_error_message", "missed_blocks")