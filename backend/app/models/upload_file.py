from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class UploadFile(Base):
    """文件上传记录表"""
    __tablename__ = "upload_file"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    file_id = Column(String(255), nullable=False, comment="文件ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    file_type = Column(String(50), nullable=False, comment="文件格式")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    status = Column(Integer, default=0, comment="状态: 0未解析, 1解析中, 2解析成功, 3解析失败")
    content = Column(Text(length=4294967295), nullable=True, comment="解析出的文本内容")
    uploader_id = Column(String(50), nullable=True, comment="上传者ID")
    uploader_name = Column(String(100), nullable=True, comment="上传者姓名")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    
    # 添加索引
    __table_args__ = (
        Index('idx_file_id', 'file_id', unique=True),
    ) 