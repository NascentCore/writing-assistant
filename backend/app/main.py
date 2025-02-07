from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.v1 import api, auth, users
from app.config import settings
from app.database import engine, Base
from app.models import document, upload_file, user  # 添加 user 模型
from app.migrations import run_all_migrations
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os

# 创建所有表
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        # 不抛出异常，允许应用继续启动
        print("Continuing despite table creation failure...")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件处理"""
    # 启动时创建数据库表
    create_tables()
    try:
        # 运行迁移
        run_all_migrations()
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        print("Continuing despite migration failure...")
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

# 修改静态文件挂载
# app.mount("/static", StaticFiles(directory="build/static"), name="static")
# app.mount("/assets", StaticFiles(directory="build"), name="assets")
# templates = Jinja2Templates(directory="build")

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(api.router, prefix="/api/v1", tags=["api"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])  # 修改用户路由前缀

@app.get("/", response_class=HTMLResponse)
async def root():
    return templates.TemplateResponse("index.html", {"request": {}})


# 启动服务器的入口点
if __name__ == "__main__":
    # 确保在启动时创建表
    create_tables()
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
