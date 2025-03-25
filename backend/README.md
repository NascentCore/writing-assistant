# AI Editor Backend

## 技术方案
- Python 3.8+
- Web框架：FastAPI
- 数据库：MySQL (通过SQLAlchemy ORM进行交互)
- 服务器：Uvicorn (ASGI服务器)
- 认证：JWT (JSON Web Token)
- 部署：Docker容器化

## 部署
- 在backend目录下`cp .env.example .env`并修改为合适配置
- virtualenv
    - `python -m venv .venv`
    - `pip install -r requirements.txt`
    - `source .venv/bin/activate`
- 在backend目录下`export PYTHONPATH=$PYTHONPATH:$(pwd)`    
- 在backend/app/目录下执行`uvicorn main:app --reload`

## swagger
- http://localhost:8000/docs 
- http://localhost:8000/redoc


## 目录结构
```
backend/
├── app/                  # 主应用代码
│   ├── models/           # 数据库模型
│   ├── routers/          # API路由
│   ├── services/         # 业务逻辑服务
│   ├── rag/              # 检索增强生成相关功能
│   ├── config.py         # 配置文件
│   ├── database.py       # 数据库连接设置
│   ├── main.py           # 应用入口
│   └── parser.py         # 文档解析器
├── alembic/              # 数据库迁移管理
├── sqls/                 # SQL脚本
├── tests/                # 测试代码
└── requirements.txt      # 依赖项
```

## 主要功能模块

### 1. 用户认证与管理
- 用户注册、登录
- JWT令牌认证
- 用户角色管理(普通用户、部门管理员、系统管理员)
- 部门组织管理

### 2. 文档管理
- 支持上传和解析多种格式文档(PDF、Word)
- 文档版本控制
- 文档内容提取和存储

### 3. AI写作辅助
- 大纲生成 (OutlineGenerator)
- 内容生成
- AI对话支持
- 写作模板系统

### 4. 知识库与RAG(检索增强生成)
- 知识库管理(系统、用户、行业、公司、部门级别)
- 文件解析和内容提取
- 文档摘要生成
- 基于知识库的内容检索
- RAG增强的内容生成
- 基于WEB的内容搜索

### 5. 写作工作流程
- 任务队列管理
- 进度跟踪
- 异步处理

## 数据模型设计

主要数据模型包括：
- **User**：用户信息
- **Department**：部门信息
- **Document/DocumentVersion**：文档及版本控制
- **Outline/SubParagraph**：大纲结构
- **Task**：异步任务
- **ChatSession/ChatMessage**：聊天会话
- **RagFile/RagKnowledgeBase**：知识库和文件

## API接口设计

API采用RESTful设计，主要路由包括：
- `/api/v1/auth`：认证相关
- `/api/v1/users`：用户管理
- `/api/v1/document`：文档管理
- `/api/v1/rag`：知识库操作
- `/api/v1/writing`：写作相关功能

## 特色功能

1. **智能大纲生成**：系统能够根据用户提示自动生成结构化大纲，并支持验证与优化
2. **基于知识库的内容生成**：利用RAG技术增强生成内容的相关性和准确性
3. **多级知识库**：支持从个人到组织不同层次的知识管理
4. **文档解析与结构提取**：能从多种格式文档中提取结构化内容
5. **异步任务处理**：长时间运行的任务(如大纲生成、内容生成)通过异步任务处理
