from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base

class UserRole(Enum):
    USER = 0
    DEPT_ADMIN = 1
    SYS_ADMIN = 2

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, comment='用户ID')
    username = Column(String(50), unique=True, index=True, comment='用户名')
    user_id = Column(String(100), unique=True, index=True, comment='用户唯一标识')
    email = Column(String(100), comment='电子邮件')
    hashed_password = Column(String(100), comment='加密密码')
    admin = Column(Integer, default=0, nullable=False, comment='管理员标识，0为普通用户 1为部门管理员 2为系统管理员')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment='更新时间')
    