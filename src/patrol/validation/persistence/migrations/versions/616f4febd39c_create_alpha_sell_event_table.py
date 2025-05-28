"""create alpha sell event table

Revision ID: 616f4febd39c
Revises: 30e446d6b9b8
Create Date: 2025-05-22 17:03:36.820567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '616f4febd39c'
down_revision: Union[str, None] = 'b7d66bdfa9c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("alpha_sell_event", 
                    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("created_at", sa.DateTime(timezone=True)), 
                    sa.Column("block_number", sa.Integer),
                    sa.Column("event_type", sa.String), 
                    sa.Column("coldkey", sa.String), 
                    sa.Column("from_hotkey", sa.String, nullable=True),
                    sa.Column("to_hotkey", sa.String, nullable=True),
                    sa.Column("rao_amount", sa.BigInteger),
                    sa.Column("from_net_uid", sa.Integer, nullable=True), 
                    sa.Column("to_net_uid", sa.Integer, nullable=True),
                    sa.Column("alpha_amount", sa.BigInteger, nullable=True))
    


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("alpha_sell_event")
