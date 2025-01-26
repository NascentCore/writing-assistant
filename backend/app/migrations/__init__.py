from app.migrations.add_user_id import run_migration as add_user_id
from app.migrations.recreate_version_table import run_migration as recreate_version_table

def run_all_migrations():
    """运行所有迁移"""
    migrations = [
        add_user_id,
        recreate_version_table,
    ]
    
    for migration in migrations:
        try:
            migration()
            print(f"Migration {migration.__name__} completed successfully")
        except Exception as e:
            print(f"Migration {migration.__name__} failed: {str(e)}")
            # 不抛出异常，允许应用继续启动
            print("Continuing despite migration failure...") 