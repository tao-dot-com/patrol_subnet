"""Index alpha-sell table

Revision ID: e0fa93e1d673
Revises: d5a2a40dd73f
Create Date: 2025-06-16 09:40:54.299289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0fa93e1d673'
down_revision: Union[str, None] = 'd5a2a40dd73f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("idx_alpha_sell_event_block", "alpha_sell_event", ["block_number"])
    op.create_index("idx_alpha_sell_event_type", "alpha_sell_event", ["event_type"])
    op.create_index("idx_alpha_sell_event_from_net_uid", "alpha_sell_event", ["from_net_uid"])
    op.create_index("idx_alpha_sell_event_to_net_uid", "alpha_sell_event", ["to_net_uid"])
    op.create_index("idx_alpha_sell_event_from_wallet", "alpha_sell_event", ["coldkey", "from_hotkey"])
    op.create_index("idx_alpha_sell_event_to_wallet", "alpha_sell_event", ["coldkey", "to_hotkey"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_alpha_sell_event_block", "alpha_sell_event")
    op.drop_index("idx_alpha_sell_event_type", "alpha_sell_event")
    op.drop_index("idx_alpha_sell_event_from_net_uid", "alpha_sell_event")
    op.drop_index("idx_alpha_sell_event_to_net_uid", "alpha_sell_event")
    op.drop_index("idx_alpha_sell_event_from_wallet", "alpha_sell_event")
    op.drop_index("idx_alpha_sell_event_to_wallet", "alpha_sell_event")
