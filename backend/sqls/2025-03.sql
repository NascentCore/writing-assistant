# 2025-03-04 会话表增加会话类型
ALTER TABLE chat_sessions
ADD COLUMN session_type TINYINT NOT NULL DEFAULT 1 COMMENT '会话类型 1: 写作会话, 2: 知识库会话'
AFTER session_id;

# 2025-03-06 消息表增加内容类型和大纲ID
ALTER TABLE chat_messages
ADD COLUMN content_type VARCHAR(20) DEFAULT 'text' COMMENT '内容类型' after full_content,
ADD COLUMN outline_id VARCHAR(100) DEFAULT '' COMMENT '大纲ID' after content_type;

# 2025-03-07 消息表增加文档ID
ALTER TABLE chat_messages
ADD COLUMN document_id VARCHAR(100) DEFAULT '' COMMENT '文档ID' after outline_id;
