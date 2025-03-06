from app.migrations.add_user_id import run_migration as add_user_id
from app.migrations.recreate_version_table import run_migration as recreate_version_table
from app.migrations.add_system_config import run_migration as add_system_config
from app.migrations.add_content_type_and_outline import run_migration as add_content_type_and_outline
from app.migrations.add_template_variables import run_migration as add_template_variables

def run_all_migrations():
    """运行所有迁移"""
    migrations = [
        add_user_id,
        recreate_version_table,
        add_system_config,
        add_content_type_and_outline,
        add_template_variables,
    ]
    
    for migration in migrations:
        try:
            migration()
            print(f"Migration {migration.__name__} completed successfully")
        except Exception as e:
            print(f"Migration {migration.__name__} failed: {str(e)}")
            # 不抛出异常，允许应用继续启动
            print("Continuing despite migration failure...") 