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
    升级数据库
    """
    try:
        with sync_engine.connect() as connection:
            # 添加 content_type 字段
            if not column_exists(connection, 'chat_messages', 'content_type'):
                connection.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN content_type VARCHAR(20) DEFAULT 'text' COMMENT '内容类型';
                """))
            
            # 添加 outline_id 字段
            if not column_exists(connection, 'chat_messages', 'outline_id'):
                connection.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN outline_id VARCHAR(100) DEFAULT '' COMMENT '大纲ID';
                """))
            
            connection.commit()
        
        return True, "成功添加content_type和outline_id字段"
    except Exception as e:
        return False, f"添加字段失败: {str(e)}"

def downgrade() -> Tuple[bool, str]:
    """
    回滚数据库
    """
    try:
        with sync_engine.connect() as connection:
            # 删除新添加的字段
            for column in ['content_type', 'outline_id']:
                if column_exists(connection, 'chat_messages', column):
                    connection.execute(text(f"""
                        ALTER TABLE chat_messages 
                        DROP COLUMN {column};
                    """))
            
            connection.commit()
            
        return True, "成功删除content_type和outline_id字段"
    except Exception as e:
        return False, f"删除字段失败: {str(e)}"

def run_migration():
    """执行迁移"""
    success, message = upgrade()
    if not success:
        raise Exception(message)
    return message 