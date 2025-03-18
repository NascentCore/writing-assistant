import enum
import json
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class TaskType(enum.Enum):
    GENERATE_OUTLINE = "generate_outline"
    GENERATE_CONTENT = "generate_content"
    # 可以添加其他任务类型


class TaskStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(22), primary_key=True, index=True)
    type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    process = Column(Integer, nullable=True, default=0)
    process_detail_info = Column(Text, nullable=True)
    session_id = Column(String(22), ForeignKey("chat_sessions.session_id"), nullable=True)
    
    # 存储任务参数，如prompt、file_ids等
    _params = Column("params", Text, nullable=True)
    
    # 存储任务结果，如outline_id等
    _result = Column("result", Text, nullable=True)
    
    # 存储错误信息
    error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    session = relationship("ChatSession", back_populates="tasks", foreign_keys=[session_id])
    
    @property
    def params(self):
        if self._params:
            return json.loads(self._params)
        return {}
    
    @params.setter
    def params(self, value):
        self._params = json.dumps(value)
    
    @property
    def result(self):
        if self._result:
            return json.loads(self._result)
        return {}
    
    @result.setter
    def result(self, value):
        self._result = json.dumps(value) 