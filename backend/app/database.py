from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from fastapi import Depends
from sqlalchemy.orm import Session

# 创建数据库引擎
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 创建依赖
def get_db_dependency():
    return Depends(get_db) 