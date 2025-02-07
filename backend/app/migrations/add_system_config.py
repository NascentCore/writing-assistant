from sqlalchemy import create_engine, text
from app.config import settings

def run_migration():
    """创建系统配置表并添加默认提示词模板"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # 创建系统配置表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    `key` VARCHAR(100) UNIQUE,
                    value TEXT,
                    description VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_key (`key`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
            
            # 插入默认提示词模板
            default_prompts = {
                "completion_prompt": {
                    "key": "prompt.autocompletion",
                    "value": "请根据下面的文本，自动为其补全内容",
                    "description": "completion prompt"
                },
            }
            
            for prompt in default_prompts.values():
                conn.execute(text("""
                    INSERT INTO system_configs (`key`, value, description)
                    VALUES (:key, :value, :description)
                    ON DUPLICATE KEY UPDATE
                    value = :value,
                    description = :description
                """), prompt)
            
            conn.commit()
            print("系统配置表创建成功并添加了默认提示词模板")
            
        except Exception as e:
            print(f"迁移失败: {str(e)}")
            conn.rollback()
            raise 