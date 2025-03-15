from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    department_id = Column(String(100), unique=True, index=True, comment='部门ID')
    name = Column(String(100), nullable=False, comment='部门名称')
    description = Column(String(200), comment='部门描述')
    parent_id = Column(String(100), nullable=True, index=True, comment='父部门ID')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment='更新时间')


class UserDepartment(Base):
    __tablename__ = "user_departments"
    
    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    user_id = Column(String(100), nullable=False, comment='用户ID')
    department_id = Column(String(100), nullable=False, comment='部门ID')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间') 