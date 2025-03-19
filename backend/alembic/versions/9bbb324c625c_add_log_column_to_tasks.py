"""add_log_column_to_tasks

Revision ID: 9bbb324c625c
Revises: c5dd3851e28a
Create Date: 2025-03-19 20:24:13.584063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bbb324c625c'
down_revision: Union[str, None] = 'c5dd3851e28a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('log', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'log')
