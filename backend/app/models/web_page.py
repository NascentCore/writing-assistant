import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.database import Base

class WebPage(Base):
    __tablename__ = "web_pages"

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    webpage_id = Column(String(100), unique=True, index=True, comment="网页ID")
    url = Column(String(1024), comment="URL")
    user_id = Column(String(100), index=True, comment="用户ID")
    status = Column(Integer, default=0, comment="状态: 0未解析, 1解析中, 2解析成功, 3解析失败")
    title = Column(String(512), comment="标题")
    text_content = Column(Text(length=4294967295), comment="文本内容")
    html_content = Column(Text(length=4294967295), comment="HTML内容")
    summary = Column(Text, comment="摘要")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
