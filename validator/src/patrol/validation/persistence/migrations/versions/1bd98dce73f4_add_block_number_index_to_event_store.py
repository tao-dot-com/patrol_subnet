"""add_block_number_index_to_event_store

Revision ID: 1bd98dce73f4
Revises: ac9b2755bbdd
Create Date: 2025-04-28 13:48:15.252310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bd98dce73f4'
down_revision: Union[str, None] = 'ac9b2755bbdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("idx_event_store_block_number", "event_store", ["block_number"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_event_store_block_number", "event_store")
