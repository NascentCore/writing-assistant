-- 2025-02-18 添加doc_id
ALTER TABLE chat_sessions 
ADD COLUMN doc_id VARCHAR(100) DEFAULT '' NOT NULL comment '文档ID' after user_id,
ADD INDEX idx_doc_id (doc_id);

-- 2025-02-25 添加用户表的管理员字段
ALTER TABLE users
ADD COLUMN admin TINYINT DEFAULT 0 NOT NULL COMMENT '管理员标识 0 普通用户 1 管理员' after hashed_password; 

-- 2025-02-28 添加RAG文件表
CREATE TABLE rag_files (
    id INT AUTO_INCREMENT COMMENT '主键ID',
    file_id VARCHAR(100) NOT NULL COMMENT '文件ID',
    kb_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '知识库ID',
    kb_type TINYINT NOT NULL DEFAULT 1 COMMENT '知识库类型 1: 系统, 2: 用户',
    kb_file_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '在RAG知识库中的文件ID',
    user_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '用户ID',
    file_name VARCHAR(150) NOT NULL DEFAULT '' COMMENT '文件名',
    file_size INT NOT NULL DEFAULT 0 COMMENT '文件大小(字节)',
    file_words INT NOT NULL DEFAULT 0 COMMENT '文件字数',
    file_ext VARCHAR(50) NOT NULL DEFAULT '' COMMENT '文件格式',
    file_path VARCHAR(255) NOT NULL DEFAULT '' COMMENT '文件存储路径',
    hash VARCHAR(100) NOT NULL DEFAULT '' COMMENT '文件hash',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0解析失败, 1未解析, 2本地解析中, 3本地解析成功, 4知识库解析中, 5知识库解析成功',
    error_message VARCHAR(255) NOT NULL DEFAULT '' COMMENT '错误信息',
    summary_small TEXT NOT NULL COMMENT '小摘要',
    summary_medium TEXT NOT NULL COMMENT '中摘要',
    summary_large TEXT NOT NULL COMMENT '大摘要',
    content LONGTEXT NOT NULL  COMMENT '解析出的文本内容',
    meta TEXT NOT NULL COMMENT '元数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    is_deleted BOOLEAN DEFAULT FALSE COMMENT '是否删除',
    PRIMARY KEY (id),
    UNIQUE INDEX idx_file_id (file_id),
    INDEX idx_kb_id (kb_id),
    INDEX idx_user_id (user_id),
    INDEX idx_hash (hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE rag_knowledge_bases (
    id INT AUTO_INCREMENT COMMENT '主键ID',
    kb_id VARCHAR(100) NOT NULL COMMENT '知识库ID',
    kb_type TINYINT NOT NULL DEFAULT 1 COMMENT '知识库类型 1: 系统, 2: 用户',
    user_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '用户ID',
    kb_name VARCHAR(150) NOT NULL DEFAULT '' COMMENT '知识库名称',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    is_deleted BOOLEAN DEFAULT FALSE COMMENT '是否删除',
    PRIMARY KEY (id),
    UNIQUE INDEX idx_kb_id (kb_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

