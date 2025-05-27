"""Create alpha_sell_challenge table

Revision ID: d544c99ec19c
Revises: 6fe000d418b0
Create Date: 2025-05-21 12:05:45.172863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import ForeignKeyConstraint, ForeignKey

# revision identifiers, used by Alembic.
revision: str = 'd544c99ec19c'
down_revision: Union[str, None] = '6fe000d418b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("alpha_sell_challenge_batch",
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('subnet_uid', sa.Integer, nullable=False),
        sa.Column('hotkeys_ss58_json', sa.JSON, nullable=False),
        sa.Column('prediction_interval_start', sa.Integer, nullable=False),
        sa.Column('prediction_interval_end', sa.Integer, nullable=False),
    )
    op.create_table("alpha_sell_challenge_task",
        sa.Column('id', sa.String, primary_key=True),
        sa.Column("batch_id", sa.String, ForeignKey("alpha_sell_challenge_batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('miner_hotkey', sa.String, nullable=False),
        sa.Column('miner_uid', sa.Integer, nullable=False),
        sa.Column('response_time', sa.Float, nullable=False),
    )
    op.create_table("alpha_sell_prediction",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String, ForeignKey("alpha_sell_challenge_task.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hotkey", sa.String, nullable=False),
        sa.Column("coldkey", sa.String, nullable=False),
        sa.Column("transaction_type", sa.String, nullable=False),
        sa.Column("amount", sa.Float, nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("alpha_sell_prediction")
    op.drop_table("alpha_sell_challenge_task")
    op.drop_table("alpha_sell_challenge_batch")
