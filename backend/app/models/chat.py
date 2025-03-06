from sqlalchemy import Enum, Column, Integer, SmallInteger, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base

class ChatSessionType(Enum):
    WRITING = 1
    KNOWLEDGE_BASE = 2

class ContentType(str, Enum):
    TEXT = "text"
    OUTLINE = "outline"

class ChatSession(Base):
    """聊天会话记录表"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="自增主键")
    session_id = Column(String(100), unique=True, comment="会话ID")
    session_type = Column(SmallInteger, default=1, comment="会话类型 1: 写作会话, 2: 知识库会话")
    user_id = Column(String(100), index=True, comment="用户ID")
    doc_id = Column(String(100), index=True, default="", comment="文档ID")
    meta = Column(Text, default="", comment="额外元数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="最后更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")

    
class ChatMessage(Base):
    """聊天消息记录表"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="自增主键")
    message_id = Column(String(100), unique=True, index=True, comment="消息ID")
    session_id = Column(String(100), index=True, comment="会话ID")
    question_id = Column(String(100), default="", comment="问题ID(用于回答的message)")
    role = Column(String(20), default="user", comment="消息角色")
    content = Column(Text, default="", comment="消息内容")
    content_type = Column(String(20), default=ContentType.TEXT, comment="内容类型")
    outline_id = Column(String(100), default="", comment="大纲ID")
    full_content = Column(Text(length=4294967295), default="", comment="完整消息内容")
    tokens = Column(Integer, default=0, comment="消息token数量")
    meta = Column(Text, default="", comment="额外元数据(温度、top_p等参数)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间") 
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="最后更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")