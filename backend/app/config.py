from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from typing import Optional

# 加载.env文件
load_dotenv()

class Settings(BaseSettings):
    # 基础配置
    PROJECT_NAME: str = "AI Editor Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 上传文件配置
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # 数据库配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "aieditor")
    
    # 大模型配置
    LLM_API_KEY: str = os.getenv("LLM_API_KEY")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL")
    LLM_MODEL: str = os.getenv("LLM_MODEL")
    
    # 数据库配置
    DATABASE_URL: str = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    
    # API文档配置
    API_DOCS_TITLE: str = "AI Editor API Documentation"
    API_DOCS_DESCRIPTION: str = """
    AI Editor 后端API文档。
    
    ## 功能特性
    * 文件上传与解析
    * AI对话支持
    * 文件管理

    """
    
    class Config:
        case_sensitive = True
        env_file = ".env"

# 创建全局配置实例
settings = Settings() 