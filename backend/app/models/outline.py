from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
import enum
from datetime import datetime

# 引用状态枚举
class ReferenceStatus(enum.Enum):
    NOT_REFERENCED = 0  # 未引用
    PARTIALLY_REFERENCED = 1  # 部分引用
    FULLY_REFERENCED = 2  # 完全引用

# 引用类型枚举 
class ReferenceType(enum.Enum):
    WEB_LINK = 1  # 网页链接
    BOOK = 2  # 书籍
    PAPER = 3  # 论文

# 文章计数风格枚举
class CountStyle(enum.Enum):
    SHORT = "short"  # 短篇
    MEDIUM = "medium"  # 中篇  
    LONG = "long"  # 长篇

# 大纲主表
class Outline(Base):
    __tablename__ = "outlines"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, comment="大纲标题")
    reference_status = Column(Integer, nullable=False, default=0, comment="引用状态")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联子段落
    sub_paragraphs = relationship("SubParagraph", back_populates="outline", cascade="all, delete-orphan")

# 子段落表
class SubParagraph(Base):
    __tablename__ = "sub_paragraphs"
    
    id = Column(Integer, primary_key=True, index=True)
    outline_id = Column(Integer, ForeignKey("outlines.id"), nullable=False)
    title = Column(String(255), nullable=False, comment="子段落标题")
    description = Column(Text, nullable=True, comment="子段落描述")
    count_style = Column(Enum(CountStyle), nullable=False, comment="篇幅风格")
    reference_status = Column(Integer, nullable=False, default=0, comment="引用状态")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    outline = relationship("Outline", back_populates="sub_paragraphs")
    references = relationship("Reference", back_populates="sub_paragraph", cascade="all, delete-orphan")

# 引用资料表
class Reference(Base):
    __tablename__ = "references"
    
    id = Column(String(255), primary_key=True, comment="引用ID")
    sub_paragraph_id = Column(Integer, ForeignKey("sub_paragraphs.id"), nullable=False)
    type = Column(Integer, nullable=False, comment="引用类型")
    is_selected = Column(Boolean, default=False, comment="是否被选中")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    sub_paragraph = relationship("SubParagraph", back_populates="references")
    web_link = relationship("WebLink", back_populates="reference", uselist=False, cascade="all, delete-orphan")

# 网页链接表
class WebLink(Base):
    __tablename__ = "web_links"
    
    id = Column(Integer, primary_key=True)
    reference_id = Column(String(255), ForeignKey("references.id"), nullable=False)
    url = Column(String(1024), nullable=False, comment="网页URL")
    title = Column(String(255), nullable=True, comment="网页标题")
    summary = Column(Text, nullable=True, comment="网页摘要") 
    icon_url = Column(String(1024), nullable=True, comment="网页图标")
    content_count = Column(Integer, nullable=True, comment="内容字数")
    content = Column(Text, nullable=True, comment="网页正文")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    reference = relationship("Reference", back_populates="web_link")
    
