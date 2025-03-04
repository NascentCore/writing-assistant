# 2025-03-04 会话表增加会话类型
ALTER TABLE chat_sessions
ADD COLUMN session_type TINYINT NOT NULL DEFAULT 1 COMMENT '会话类型 1: 写作会话, 2: 知识库会话'
AFTER session_id;
