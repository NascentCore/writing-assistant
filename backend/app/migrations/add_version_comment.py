from sqlalchemy import create_engine, text, inspect
from app.config import settings

def run_migration():
    """添加版本注释字段"""
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        try:
            # 检查 comment 列是否存在
            if 'comment' not in [c['name'] for c in inspector.get_columns('document_versions')]:
                conn.execute(text("""
                    ALTER TABLE document_versions 
                    ADD COLUMN comment VARCHAR(200);
                """))
                print("Added comment column to document_versions table")
            
            conn.commit()
            print("Migration completed successfully")
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            conn.rollback()
            raise 