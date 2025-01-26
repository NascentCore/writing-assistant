from sqlalchemy import create_engine, text
from app.config import settings

def run_migration():
    """重建文档版本表"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # 删除旧表
            conn.execute(text("DROP TABLE IF EXISTS document_versions;"))
            
            # 创建新表 (使用 MySQL 语法)
            conn.execute(text("""
                CREATE TABLE document_versions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    document_id INT,
                    content TEXT,
                    version INT,
                    comment VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
            
            print("Recreated document_versions table")
            conn.commit()
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            conn.rollback()
            raise 