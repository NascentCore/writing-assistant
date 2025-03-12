from sqlalchemy import Column, Enum, Integer, String, Text, DateTime, Boolean, SmallInteger
from sqlalchemy.sql import func
from app.database import Base

class RagKnowledgeBaseType(Enum):
    NONE = 0
    SYSTEM = 1
    USER = 2

class RagFileStatus(Enum):
    FAILED = 0
    LOCAL_SAVED= 1
    LOCAL_PARSING = 2
    LOCAL_PARSED = 3
    LLM_SUMMARIZING = 4
    LLM_SUMMARYED = 5
    RAG_UPLOADING = 6
    RAG_UPLOADED = 7
    RAG_PARSING = 8
    DONE = 99

    @classmethod
    def get_status_map(cls):
        return {
            cls.FAILED: "Failed",
            cls.LOCAL_SAVED: "LocalSaved",
            cls.LOCAL_PARSING: "LocalParsing",
            cls.LOCAL_PARSED: "LocalParsed",
            cls.LLM_SUMMARIZING: "LLMSummarizing",
            cls.LLM_SUMMARYED: "LLMSummarized",
            cls.RAG_UPLOADING: "RAGUploading",
            cls.RAG_UPLOADED: "RAGUploaded",
            cls.RAG_PARSING: "RAGParsing",
            cls.DONE: "Done"
        }

class RagFile(Base):
    """RAG文件表"""
    __tablename__ = "rag_files"
    
    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    file_id = Column(String(100), unique=True, index=True, comment="文件ID")
    kb_id = Column(String(100), index=True, default="", comment="知识库ID")
    kb_type = Column(SmallInteger, default=1, nullable=False, comment="知识库类型 1: 系统, 2: 用户")
    kb_file_id = Column(String(100), index=True, default="", comment="知识库文件ID")
    user_id = Column(String(100), index=True, default="", comment="用户ID")
    file_name = Column(String(150), default="", comment="文件名")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    file_words = Column(Integer, default=0, comment="文件字数")
    file_ext = Column(String(50), default="", comment="文件格式")
    file_path = Column(String(255), default="", comment="文件存储路径")
    hash = Column(String(100), default="", comment="文件hash")
    status = Column(SmallInteger, default=1, nullable=False, comment="状态: 0解析失败, 1未解析, 2本地解析中, 3本地解析成功, 4知识库解析中, 5知识库解析成功")
    error_message = Column(String(255), default="", comment="错误信息")
    summary_small = Column(Text, comment="小摘要")
    summary_medium = Column(Text, comment="中摘要")
    summary_large = Column(Text, comment="大摘要")
    content = Column(Text(length=4294967295), comment="解析出的文本内容")
    meta = Column(Text, comment="元数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")

class RagKnowledgeBase(Base):
    """RAG知识库表"""
    __tablename__ = "rag_knowledge_bases"
    
    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    kb_id = Column(String(100), unique=True, index=True, comment="知识库ID")
    kb_type = Column(SmallInteger, default=1, nullable=False, comment="知识库类型 1: 系统, 2: 用户")
    user_id = Column(String(100), index=True, default="", comment="用户ID")
    kb_name = Column(String(150), default="", comment="知识库名称")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除") 