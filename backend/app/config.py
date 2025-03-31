from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from typing import Optional, List
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

# 全局数据库配置 - 只从yaml文件读取
MYSQL_HOST = yaml_config.get("mysql", {}).get("host", "localhost")
MYSQL_PORT = int(yaml_config.get("mysql", {}).get("port", 3306))
MYSQL_USER = yaml_config.get("mysql", {}).get("user", "root")
MYSQL_PASSWORD = yaml_config.get("mysql", {}).get("password", "")
MYSQL_DATABASE = yaml_config.get("mysql", {}).get("database", "aieditor")
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
ASYNC_DATABASE_URL = f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

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
    MYSQL_HOST: str = MYSQL_HOST
    MYSQL_PORT: int = MYSQL_PORT
    MYSQL_USER: str = MYSQL_USER
    MYSQL_PASSWORD: str = MYSQL_PASSWORD
    MYSQL_DATABASE: str = MYSQL_DATABASE
    
    # 数据库URL
    DATABASE_URL: str = DATABASE_URL
    ASYNC_DATABASE_URL: str = ASYNC_DATABASE_URL
    
    # 大模型配置
    LLM_MODELS: list = yaml_config.get("llm_models", []) or [{
        "base_url": os.getenv("LLM_BASE_URL", "http://localhost:8001/v1"),
        "model": os.getenv("LLM_MODEL", "chatglm3"),
        "api_key": os.getenv("LLM_API_KEY", "EMPTY"),
        "readable_model_name": os.getenv("LLM_READABLE_MODEL_NAME", "chatglm3-6b-8192"),
        "system_prompt": os.getenv("LLM_SYSTEM_PROMPT", "你是一个专业的写作助手,擅长帮助用户改进文章的结构、内容和表达。"),
        "max_tokens": os.getenv("LLM_MAX_TOKENS", 4096),
    }]
    LLM_REQUEST_TIMEOUT: float = yaml_config.get("request_timeout", 300.0)
    LLM_CHAT_MAX_TOKENS: int = yaml_config.get("chat_max_tokens", 200)
    LLM_COMPLETION_DOC_MAX_LENGTH: int = yaml_config.get("completion_doc_max_length", 10000)
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
    
    # 知识库配置
    RAG_KB_API_BASE: str = yaml_config.get("rag", {}).get("kb_api_base", "http://rag.llm.sxwl.ai:30003/api/")
    RAG_SUMMARY_MODEL: str = yaml_config.get("rag", {}).get("summary_model")
    RAG_SUMMARY_BASE_URL: str = yaml_config.get("rag", {}).get("summary_base_url")
    RAG_SUMMARY_API_KEY: str = yaml_config.get("rag", {}).get("summary_api_key")
    RAG_SUMMARY_TEMPERATURE: float = yaml_config.get("rag", {}).get("summary_temperature", 0.4)
    RAG_SUMMARY_TOP_P: float = yaml_config.get("rag", {}).get("summary_top_p", 0.6)
    RAG_SUMMARY_MAX_TOKENS: int = yaml_config.get("rag", {}).get("summary_max_tokens", 1500)
    RAG_SUMMARY_REQUEST_TIMEOUT: float = yaml_config.get("rag", {}).get("summary_request_timeout", 300.0)
    RAG_FILE_PROCESSOR_INTERVAL: int = yaml_config.get("rag", {}).get("file_processor_interval", 5)
    RAG_CHAT_TEMPERATURE: float = yaml_config.get("rag", {}).get("chat_temperature", 0.5)
    RAG_CHAT_TOP_P: float = yaml_config.get("rag", {}).get("chat_top_p", 1.0)
    RAG_CHAT_TOP_K: int = yaml_config.get("rag", {}).get("chat_top_k", 30)
    RAG_CHAT_MAX_TOKENS: int = yaml_config.get("rag", {}).get("chat_max_tokens", 512)
    RAG_CHAT_NETWORKING: bool = yaml_config.get("rag", {}).get("chat_networking", False)
    RAG_CHAT_PRODUCT_SOURCE: str = yaml_config.get("rag", {}).get("chat_product_source", "saas")
    RAG_CHAT_RERANK: bool = yaml_config.get("rag", {}).get("chat_rerank", False)
    RAG_CHAT_ONLY_NEED_SEARCH_RESULTS: bool = yaml_config.get("rag", {}).get("chat_only_need_search_results", False)
    RAG_CHAT_HYBRID_SEARCH: bool = yaml_config.get("rag", {}).get("chat_hybrid_search", False)
    RAG_CHAT_API_CONTEXT_LENGTH: int = yaml_config.get("rag", {}).get("chat_api_context_length", 4096)
    RAG_CHAT_CHUNK_SIZE: int = yaml_config.get("rag", {}).get("chat_chunk_size", 800)
    RAG_CHAT_PER_FILE_MAX_LENGTH: int = yaml_config.get("rag", {}).get("chat_per_file_max_length", 2000)
    RAG_CHAT_TOTAL_FILE_MAX_LENGTH: int = yaml_config.get("rag", {}).get("chat_total_file_max_length", 10000)
    RAG_CHAT_HISTORY_SIZE: int = yaml_config.get("rag", {}).get("chat_history_size", 20)
    RAG_CHAT_HISTORY_MAX_LENGTH: int = yaml_config.get("rag", {}).get("chat_history_max_length", 10000)

    # 写作助手配置
    WRITING_PER_PAGE_WORD_COUNT: int = yaml_config.get("writing", {}).get("per_page_word_count", 800)
    # 大模型每次生成字数限制
    WRITING_MAX_WORD_COUNT_PER_GENERATION: int = yaml_config.get("writing", {}).get("max_word_count_per_generation", 5000)
    class Config:
        case_sensitive = True
        env_file = ".env"

# 创建全局配置实例
settings = Settings()