"""add_process_column_to_tasks

Revision ID: c5dd3851e28a
Revises: 54433c89c062
Create Date: 2025-03-18 20:00:11.517728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5dd3851e28a'
down_revision: Union[str, None] = '54433c89c062'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 process 列到 tasks 表
    op.add_column('tasks', sa.Column('process', sa.Integer(), nullable=True, default=0))
    # 添加 process_detail_info 列到 tasks 表
    op.add_column('tasks', sa.Column('process_detail_info', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # 删除 process_detail_info 列
    op.drop_column('tasks', 'process_detail_info')
    # 删除 process 列
    op.drop_column('tasks', 'process')
