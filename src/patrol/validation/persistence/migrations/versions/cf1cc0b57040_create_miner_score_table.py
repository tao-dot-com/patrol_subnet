"""create miner score table

Revision ID: cf1cc0b57040
Revises: 
Create Date: 2025-04-03 14:02:39.330270

"""
from tokenize import String
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("miner_score",
            sa.Column('id', sa.String),# primary_key=True),
            sa.Column('batch_id', sa.String),# primary_key=True),
            sa.Column('uid', sa.Integer),#, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True)),#, nullable=False),
            sa.Column('coldkey', sa.String),#, nullable=False),#,
            sa.Column('hotkey', sa.String),#, nullable=False),#,
            sa.Column('overall_score', sa.Float),#, nullable=False),
            sa.Column('volume', sa.Integer),#, nullable=False),
            sa.Column('volume_score', sa.Float),#, nullable=False),
            sa.Column('responsiveness_score', sa.Float),#, nullable=False),
            sa.Column('response_time_seconds', sa.Float),#, nullable=False),
            sa.Column('novelty_score', sa.Float),#, nullable=True),
            sa.Column('validation_passed', sa.Boolean),#, nullable=False),
            sa.Column('error_msg', sa.String),# nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("miner_score")
