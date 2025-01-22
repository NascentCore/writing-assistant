from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.v1.api import router as api_router
from app.config import settings
from app.database import engine
from app.models.upload_file import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件处理"""
    # 启动时创建数据库表
    Base.metadata.create_all(bind=engine)
    yield

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI编辑器后端服务",
    version=settings.VERSION,
    lifespan=lifespan,
    # 添加以下配置来启用和自定义 Swagger UI
    docs_url="/docs",  # Swagger UI 的访问路径 (默认就是 /docs)
    redoc_url="/redoc",  # ReDoc 文档的访问路径 (默认就是 /redoc)
    openapi_url="/openapi.json",  # OpenAPI schema 的访问路径
    swagger_ui_parameters={
        "persistAuthorization": True,  # 保持授权信息
        "displayRequestDuration": True,  # 显示请求持续时间
    }
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 启动服务器的入口点
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
