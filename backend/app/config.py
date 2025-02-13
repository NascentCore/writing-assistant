from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from typing import Optional
import yaml
from pathlib import Path

# 加载.env文件
load_dotenv()

# 加载yaml配置文件
def load_yaml_config():
    config_path = Path(os.getenv("CONFIG_PATH", "config.yaml"))
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

yaml_config = load_yaml_config()

class Settings(BaseSettings):
    # 基础配置
    PROJECT_NAME: str = yaml_config.get("project", {}).get("name", "AI编辑器")
    VERSION: str = yaml_config.get("project", {}).get("version", "0.1.0")
    API_V1_STR: str = yaml_config.get("api", {}).get("prefix", "/api/v1")
    
    # 上传文件配置
    UPLOAD_DIR: str = yaml_config.get("upload", {}).get("dir", os.getenv("UPLOAD_DIR", "uploads"))
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # MySQL数据库配置
    MYSQL_HOST: str = yaml_config.get("mysql", {}).get("host", os.getenv("MYSQL_HOST", "localhost"))
    MYSQL_PORT: int = int(yaml_config.get("mysql", {}).get("port", os.getenv("MYSQL_PORT", "3306")))
    MYSQL_USER: str = yaml_config.get("mysql", {}).get("user", os.getenv("MYSQL_USER", "root"))
    MYSQL_PASSWORD: str = yaml_config.get("mysql", {}).get("password", os.getenv("MYSQL_PASSWORD", ""))
    MYSQL_DATABASE: str = yaml_config.get("mysql", {}).get("database", os.getenv("MYSQL_DATABASE", "aieditor"))
    
    # 构建数据库URL
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    # 大模型配置
    LLM_MODELS: list = yaml_config.get("llm_models", []) or [{
        "base_url": os.getenv("LLM_BASE_URL", "http://localhost:8001/v1"),
        "model": os.getenv("LLM_MODEL", "chatglm3"),
        "api_key": os.getenv("LLM_API_KEY", "EMPTY"),
        "readable_model_name": os.getenv("LLM_READABLE_MODEL_NAME", "chatglm3-6b-8192"),
        "system_prompt": os.getenv("LLM_SYSTEM_PROMPT", "你是一个专业的写作助手,擅长帮助用户改进文章的结构、内容和表达。"),
    }]
    LLM_REQUEST_TIMEOUT: float = yaml_config.get("request_timeout", 300.0)
    # 向后兼容的默认模型配置
    LLM_BASE_URL: str = LLM_MODELS[0]["base_url"]
    LLM_MODEL: str = LLM_MODELS[0]["model"]
    LLM_API_KEY: str = LLM_MODELS[0]["api_key"]
    LLM_READABLE_MODEL_NAME: str = LLM_MODELS[0]["readable_model_name"]
    LLM_SYSTEM_PROMPT: str = LLM_MODELS[0]["system_prompt"]
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