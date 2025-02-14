from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
from fastapi import Depends
from sqlalchemy.orm import Session
import logging

logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    # echo=False,  # 添加这个参数
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_recycle=3600,   # 一小时后回收连接
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建声明性基类
Base = declarative_base()

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