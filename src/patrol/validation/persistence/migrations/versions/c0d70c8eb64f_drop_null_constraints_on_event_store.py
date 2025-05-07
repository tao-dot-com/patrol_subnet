"""drop null constraints on event_store

Revision ID: c0d70c8eb64f
Revises: 1bd98dce73f4
Create Date: 2025-05-07 18:24:39.605157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0d70c8eb64f'
down_revision: Union[str, None] = '1bd98dce73f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("event_store", "coldkey_source", existing_type=sa.String, nullable=True)
    op.alter_column("event_store", "coldkey_owner", existing_type=sa.String, nullable=True)
    op.alter_column("event_store", "rao_amount", existing_type=sa.String, nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    pass
