from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import datetime
from app.database import Base  # 使用同一个 Base

class UploadFile(Base):
    """文件上传记录表"""
    __tablename__ = "upload_files"
    
    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    file_id = Column(String(50), unique=True, index=True, comment="文件ID")
    file_name = Column(String(255), comment="文件名")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_type = Column(String(50), comment="文件格式")
    file_path = Column(String(255), comment="文件存储路径")
    status = Column(Integer, default=0, comment="状态: 0未解析, 1解析中, 2解析成功, 3解析失败")
    content = Column(Text, comment="解析出的文本内容")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="upload_files")
    
    # 添加索引
    __table_args__ = (
        Index('idx_file_id', 'file_id', unique=True),
    ) 