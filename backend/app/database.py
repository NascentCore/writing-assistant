from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
from contextlib import asynccontextmanager
import logging

# 设置 SQLAlchemy 日志级别
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)

# 创建同步引擎
sync_engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建同步会话
sync_session = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

def get_db():
    db = sync_session()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()

# 创建异步引擎
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建异步会话
async_session = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 获取数据库会话的依赖函数
@asynccontextmanager
async def get_async_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
