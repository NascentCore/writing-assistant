from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.v1.api import router as api_router
from app.config import settings  # 导入配置

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI编辑器后端服务",
    version=settings.VERSION
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
