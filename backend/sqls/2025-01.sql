-- 2025-02-18 添加doc_id
ALTER TABLE chat_sessions 
ADD COLUMN doc_id VARCHAR(100) DEFAULT '' NOT NULL comment '文档ID' after user_id,
ADD INDEX idx_doc_id (doc_id);
