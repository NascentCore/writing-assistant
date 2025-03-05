import sys
import requests
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class ChatConfig:
    """聊天配置类"""
    api_base: str = "https://api.openai-proxy.org/v1"
    api_key: str = "sk-xxx"
    model: str = "gpt-3.5-turbo"
    api_context_length: int = 16384
    chunk_size: int = 800
    top_p: float = 1.0
    temperature: float = 0.5
    max_token: int = 512

class ChatService:
    """本地文档问答服务类"""
    
    def __init__(self, host: str, port: int = 8777, config: Optional[ChatConfig] = None):
        """
        初始化聊天服务
        
        Args:
            host: 服务器主机地址
            port: 服务器端口号
            config: 聊天配置，如果为None则使用默认配置
        """
        self.base_url = f"http://{host}:{port}"
        self.config = config or ChatConfig()
        
    def chat(
        self,
        question: str,
        user_id: str,
        kb_ids: List[str],
        history: List[Dict] = None,
        streaming: bool = True,
        networking: bool = False,
        product_source: str = "saas",
        rerank: bool = False,
        only_need_search_results: bool = False,
        hybrid_search: bool = False,
    ) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            question: 用户问题
            user_id: 用户ID
            kb_ids: 知识库ID列表
            history: 聊天历史
            streaming: 是否使用流式响应
            networking: 是否使用联网搜索
            product_source: 产品来源
            rerank: 是否重新排序
            only_need_search_results: 是否只需要搜索结果
            hybrid_search: 是否使用混合搜索
            
        Returns:
            Dict: 接口响应结果
        """
        url = f"{self.base_url}/api/local_doc_qa/local_doc_chat"
        headers = {
            'content-type': 'application/json'
        }
        
        data = {
            "user_id": user_id,
            "kb_ids": kb_ids,
            "history": history or [],
            "question": question,
            "streaming": streaming,
            "networking": networking,
            "product_source": product_source,
            "rerank": rerank,
            "only_need_search_results": only_need_search_results,
            "hybrid_search": hybrid_search,
            "max_token": self.config.max_token,
            "api_base": self.config.api_base,
            "api_key": self.config.api_key,
            "model": self.config.model,
            "api_context_length": self.config.api_context_length,
            "chunk_size": self.config.chunk_size,
            "top_p": self.config.top_p,
            "temperature": self.config.temperature
        }
        
        try:
            start_time = time.time()
            response = requests.post(url=url, headers=headers, json=data, timeout=60)
            end_time = time.time()
            
            response.raise_for_status()  # 检查响应状态
            result = response.json()
            
            # 添加响应时间信息
            result['response_time'] = end_time - start_time
            result['status_code'] = response.status_code
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求发送失败: {str(e)}")
