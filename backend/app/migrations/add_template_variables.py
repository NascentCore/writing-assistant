from typing import Tuple
from sqlalchemy import text
from app.database import sync_engine

def column_exists(connection, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    result = connection.execute(text(f"""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}' 
        AND column_name = '{column_name}'
        AND table_schema = DATABASE();
    """))
    return result.scalar() > 0

def upgrade() -> Tuple[bool, str]:
    """
    升级数据库：添加 description 字段到 writing_templates 表
    """
    try:
        with sync_engine.connect() as connection:
            # 添加 description 字段
            if not column_exists(connection, 'writing_templates', 'description'):
                connection.execute(text("""
                    ALTER TABLE writing_templates 
                    ADD COLUMN description TEXT NULL COMMENT '大纲描述';
                """))
            
            connection.commit()
        
        return True, "成功添加 description 字段到 writing_templates 表"
    except Exception as e:
        return False, f"添加字段失败: {str(e)}"

def downgrade() -> Tuple[bool, str]:
    """
    回滚数据库
    """
    try:
        with sync_engine.connect() as connection:
            # 删除新添加的字段
            if column_exists(connection, 'writing_templates', 'description'):
                connection.execute(text("""
                    ALTER TABLE writing_templates 
                    DROP COLUMN description;
                """))
            
            connection.commit()
            
        return True, "成功删除 description 字段"
    except Exception as e:
        return False, f"删除字段失败: {str(e)}"

def run_migration():
    """执行迁移"""
    success, message = upgrade()
    if not success:
        raise Exception(message)
    return message 