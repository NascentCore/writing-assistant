"""add sort_index colume of sub_paragraphs

Revision ID: 54433c89c062
Revises: 
Create Date: 2025-03-17 11:31:34.969327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '54433c89c062'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    # 添加 sort_index 列
    op.add_column('sub_paragraphs', sa.Column('sort_index', sa.Integer(), nullable=True, comment="排序索引"))
    
    # 获取数据库连接
    connection = op.get_bind()
    session = Session(bind=connection)
    
    try:
        # 更新现有数据
        # 1. 获取所有大纲
        outlines = connection.execute(
            text("SELECT id FROM outlines")
        ).fetchall()
        
        for outline in outlines:
            outline_id = outline[0]
            
            # 2. 对每个大纲，按层级处理其段落
            # 首先处理顶级段落（level = 1）
            top_level_paragraphs = connection.execute(
                text("""
                    SELECT id FROM sub_paragraphs 
                    WHERE outline_id = :outline_id 
                    AND parent_id IS NULL 
                    ORDER BY id
                """),
                {"outline_id": outline_id}
            ).fetchall()
            
            # 更新顶级段落的排序
            for index, para in enumerate(top_level_paragraphs):
                connection.execute(
                    text("""
                        UPDATE sub_paragraphs 
                        SET sort_index = :sort_index 
                        WHERE id = :id
                    """),
                    {"sort_index": index, "id": para[0]}
                )
                
                # 处理该段落的子段落
                process_children(connection, para[0])
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def process_children(connection, parent_id):
    """递归处理子段落的排序"""
    # 获取所有子段落
    children = connection.execute(
        text("""
            SELECT id FROM sub_paragraphs 
            WHERE parent_id = :parent_id 
            ORDER BY id
        """),
        {"parent_id": parent_id}
    ).fetchall()
    
    # 更新子段落的排序
    for index, child in enumerate(children):
        connection.execute(
            text("""
                UPDATE sub_paragraphs 
                SET sort_index = :sort_index 
                WHERE id = :id
            """),
            {"sort_index": index, "id": child[0]}
        )
        
        # 递归处理下一层子段落
        process_children(connection, child[0])


def downgrade():
    # 删除 sort_index 列
    op.drop_column('sub_paragraphs', 'sort_index')