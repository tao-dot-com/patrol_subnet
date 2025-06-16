"""create missed_blocks table

Revision ID: ac9b2755bbdd
Revises: be6941ce7880
Create Date: 2025-04-28 10:11:13.511133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac9b2755bbdd'
down_revision: Union[str, None] = 'be6941ce7880'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("missed_blocks",
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('block_number', sa.BigInteger, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('error_message', sa.String, nullable=True),
    )
    
    op.create_index("idx_missed_blocks_block_number", "missed_blocks", 
                   columns=["block_number"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_missed_blocks_block_number", "missed_blocks")
    op.drop_table("missed_blocks")