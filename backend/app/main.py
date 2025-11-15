import logging
import sys
import threading
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.v1 import api, auth, users, prompt, document, rag, writing
from fastapi.openapi.utils import get_openapi
from app.config import settings
from app.database import get_db, sync_engine, Base
from app.rag.process import rag_worker
from app.rag.kb import ensure_knowledge_bases
from app.routers.v1.writing import refresh_writing_tasks_status
from fastapi.logger import logger as fastapi_logger

# Architectural hinge:
# This entrypoint stitches together configuration, API routers, and background workers:
#   - `lifespan` initializes DB state, knowledge bases, and the `rag_worker`, so writing endpoints can assume KB metadata exists.
#   - Router wiring here mirrors the separation documented in ARCHITECTURE.md (auth/users/document/writing/rag) and keeps their cross-calls explicit.
#   - `refresh_writing_tasks_status` bridges persisted `Task` rows with the thread-pool used in `app/routers/v1/writing.py`, ensuring restarts do not orphan UI-visible jobs.

logger = logging.getLogger("app")

def setup_logging():
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # 文件处理器
    file_handler = logging.FileHandler('app.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 清除已有的处理器
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 配置FastAPI日志器
    fastapi_logger.setLevel(logging.INFO)
    # 清除已有的处理器
    fastapi_logger.handlers.clear()
    fastapi_logger.addHandler(console_handler)
    fastapi_logger.addHandler(file_handler)
    
    # 配置应用日志器
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    # 防止日志传递到父日志器
    app_logger.propagate = False
    # 清除已有的处理器
    app_logger.handlers.clear()
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件处理"""
    # 在应用启动时配置日志
    setup_logging()
    logger.info("应用正在启动...")
    
    # 创建数据库表
    create_tables()

    # 确保系统基础知识库已创建
    db = next(get_db())
    try:
        await ensure_knowledge_bases(db)
    except Exception as e:
        logger.error(f"系统知识库初始化失败: {str(e)}")
    
    # 启动知识库文件处理线程
    thread = threading.Thread(target=rag_worker, name="rag_worker")
    thread.daemon = True
    thread.start()
    logger.info("知识库文件处理线程已启动")
    
    # 恢复未完成的写作任务
    try:
        refresh_writing_tasks_status()
        logger.info("未完成的写作任务恢复检查完成")
    except Exception as e:
        logger.error(f"恢复写作任务失败: {str(e)}")
    
    yield
    
    logger.info("应用正在关闭...")

# 创建所有表
def create_tables():
    try:
        Base.metadata.create_all(bind=sync_engine)
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"创建数据库表时出错: {str(e)}")
        logger.exception("详细错误信息:")

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    AI编辑器后端服务
    
    ## 认证
    所有需要认证的接口都需要在请求头中携带 JWT Token:
    - 先调用token接口获取your_token
    - 在 Swagger UI 右上角点击 "Authorize" 按钮
    - 输入第一步获取的your_token
    """,
    version=settings.VERSION,
    lifespan=lifespan,
    # OpenAPI/Swagger配置
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        # 添加以下配置
        "syntaxHighlight.theme": "obsidian",
        "tryItOutEnabled": True,  # 默认展开 "Try it out" 按钮
        "requestSnippetsEnabled": True,  # 显示请求示例
        "defaultModelsExpandDepth": 3,
        "defaultModelExpandDepth": 3,
    }
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=604800  # 设置预检请求的缓存时间为一周
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(api.router, prefix="/api/v1", tags=["api"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])  # 修改用户路由前缀
app.include_router(prompt.router, prefix="/api/v1", tags=["prompt"])
app.include_router(document.router, prefix="/api/v1", tags=["document"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])
app.include_router(writing.router, prefix="/api/v1/writing", tags=["writing"])

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "API is running",
        "version": settings.VERSION
    }

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=app.description,
        routes=app.routes,
    )
    
    # 添加安全定义
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": """
            输入格式为: your_token
            注意: 不需要Bearer前缀
            """
        }
    }
    
    # 为所有路由添加安全要求，除了 /token 和 /register
    if "paths" in openapi_schema:
        for path in openapi_schema["paths"]:
            # 跳过认证相关的路由
            if path.endswith("/token") or path.endswith("/register"):
                continue
                
            # 为路径下的所有操作添加安全要求
            for method in openapi_schema["paths"][path]:
                if method.lower() in ("get", "post", "put", "delete", "patch"):
                    openapi_schema["paths"][path][method]["security"] = [{"Bearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# 启动服务器的入口点
if __name__ == "__main__":
    # 启动FastAPI应用
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True
    )
