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

# 2025-03-10 消息表增加任务相关字段
ALTER TABLE chat_messages
ADD COLUMN task_id VARCHAR(100) DEFAULT '' COMMENT '任务ID' after document_id,
ADD COLUMN task_status VARCHAR(20) DEFAULT '' COMMENT '任务状态' after task_id,
ADD COLUMN task_result TEXT COMMENT '任务结果' after task_status;

# 2025-03-10 修改documents表content列类型为longtext
ALTER TABLE `documents` 
CHANGE `content` `content` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '文档内容';

# 2025-03-12 部门表和用户部门关联表
CREATE TABLE departments (
    id INT AUTO_INCREMENT COMMENT '主键ID',
    department_id VARCHAR(100) COMMENT '部门ID',
    name VARCHAR(100) NOT NULL COMMENT '部门名称',
    description VARCHAR(200) COMMENT '部门描述',
    parent_id VARCHAR(100) COMMENT '父部门ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY idx_department_id (department_id),
    KEY idx_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';

CREATE TABLE user_departments (
    id INT AUTO_INCREMENT COMMENT '主键ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    department_id VARCHAR(100) NOT NULL COMMENT '部门ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_user_id (user_id),
    KEY idx_department_id (department_id),
    KEY idx_user_dept (user_id, department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户部门关联表';


ALTER TABLE rag_knowledge_bases ADD COLUMN owner_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '所有者ID' AFTER kb_type;
UPDATE rag_knowledge_bases SET owner_id = user_id;


# 2025-03-19 删除用户表的email索引
ALTER TABLE users
DROP INDEX ix_users_email;