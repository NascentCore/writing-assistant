from sqlalchemy import create_engine, text, inspect
from app.config import settings

def run_migration():
    """添加用户ID列到相关表"""
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    # 执行迁移
    with engine.connect() as conn:
        try:
            # 检查 documents 表的 user_id 列是否存在
            if 'user_id' not in [c['name'] for c in inspector.get_columns('documents')]:
                # 先删除可能存在的外键约束
                try:
                    conn.execute(text("ALTER TABLE documents DROP FOREIGN KEY fk_user_id;"))
                except:
                    pass
                
                # 添加 user_id 列
                conn.execute(text("ALTER TABLE documents ADD COLUMN user_id INT;"))
                
                # 添加外键约束
                conn.execute(text("""
                    ALTER TABLE documents 
                    ADD CONSTRAINT fk_user_id 
                    FOREIGN KEY (user_id) 
                    REFERENCES users(id);
                """))
                print("Added user_id to documents table")
            
            # 检查 upload_files 表的 user_id 列是否存在
            if 'user_id' not in [c['name'] for c in inspector.get_columns('upload_files')]:
                # 先删除可能存在的外键约束
                try:
                    conn.execute(text("ALTER TABLE upload_files DROP FOREIGN KEY fk_upload_user_id;"))
                except:
                    pass
                
                # 添加 user_id 列
                conn.execute(text("ALTER TABLE upload_files ADD COLUMN user_id INT;"))
                
                # 添加外键约束
                conn.execute(text("""
                    ALTER TABLE upload_files 
                    ADD CONSTRAINT fk_upload_user_id 
                    FOREIGN KEY (user_id) 
                    REFERENCES users(id);
                """))
                print("Added user_id to upload_files table")
            
            # 提交事务
            conn.commit()
            print("Migration completed successfully")
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            conn.rollback()
            raise

if __name__ == "__main__":
    run_migration() 