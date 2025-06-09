"""create scoring batch sequence

Revision ID: d5a2a40dd73f
Revises: 52b3b3a5b71d
Create Date: 2025-06-09 10:31:53.578556

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5a2a40dd73f'
down_revision: Union[str, None] = '52b3b3a5b71d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.schema.CreateSequence(sa.Sequence("scoring_batch")))
    op.add_column("miner_score", sa.Column("scoring_batch", sa.BigInteger, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.schema.DropSequence(sa.Sequence("scoring_batch")))
    op.drop_column("miner_score", "scoring_batch")

