"""create event_store table

Revision ID: be6941ce7880
Revises: bfa974121e52
Create Date: 2025-04-23 17:49:08.202787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be6941ce7880'
down_revision: Union[str, None] = 'bfa974121e52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("event_store",
            sa.Column('edge_hash', sa.String, primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('coldkey_source', sa.String, nullable=False),
            sa.Column('coldkey_destination', sa.String, nullable=False),
            sa.Column('edge_category', sa.String, nullable=False),
            sa.Column('edge_type', sa.String, nullable=False),
            sa.Column('coldkey_owner', sa.String, nullable=True),
            sa.Column('block_number', sa.Integer, nullable=False),
            sa.Column('rao_amount', sa.BigInteger, nullable=False),
            sa.Column('destination_net_uid', sa.Integer, nullable=True),
            sa.Column('source_net_uid', sa.Integer, nullable=True),
            sa.Column('alpha_amount', sa.BigInteger, nullable=True),
            sa.Column('delegate_hotkey_source', sa.String, nullable=True),
            sa.Column('delegate_hotkey_destination', sa.String, nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("event_store")