"""add sort_order field to writing_templates

Revision ID: 9c45ea7d3c12
Revises: c5dd3851e28a
Create Date: 2025-04-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '9c45ea7d3c12'
down_revision: Union[str, None] = 'c5dd3851e28a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 获取数据库连接和元数据信息
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [column['name'] for column in inspector.get_columns('writing_templates')]
    
    # 只有当 sort_order 列不存在时才添加
    if 'sort_order' not in columns:
        op.add_column('writing_templates', sa.Column('sort_order', sa.Integer(), nullable=True, default=0, comment="排序顺序，值越小排序越靠前"))
    
    # 获取会话
    session = Session(bind=connection)
    
    try:
        # 获取所有模板并按创建时间倒序排序
        templates = connection.execute(
            text("SELECT id FROM writing_templates ORDER BY created_at DESC")
        ).fetchall()
        
        # 更新现有模板的排序字段，保持与创建时间相同的排序
        for index, template in enumerate(templates):
            connection.execute(
                text("""
                    UPDATE writing_templates 
                    SET sort_order = :sort_order 
                    WHERE id = :id
                """),
                {"sort_order": index, "id": template[0]}
            )
            
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def downgrade():
    # 删除 sort_order 列
    op.drop_column('writing_templates', 'sort_order') 