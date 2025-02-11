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
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

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
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(api.router, prefix="/api/v1", tags=["api"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])  # 修改用户路由前缀

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
    # 确保在启动时创建表
    create_tables()
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
