"""add_expected_word_count_to_sub_paragraphs

Revision ID: d860c8a60136
Revises: 9bbb324c625c
Create Date: 2025-03-26 22:29:42.172178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'd860c8a60136'
down_revision: Union[str, None] = '9bbb324c625c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 获取数据库连接和元数据信息
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [column['name'] for column in inspector.get_columns('sub_paragraphs')]
    
    # 只有当 expected_word_count 列不存在时才添加
    if 'expected_word_count' not in columns:
        op.add_column('sub_paragraphs', sa.Column('expected_word_count', sa.Integer(), nullable=True, comment="预期字数"))


def downgrade() -> None:
    """Downgrade schema."""
    # 删除 expected_word_count 列
    op.drop_column('sub_paragraphs', 'expected_word_count')
