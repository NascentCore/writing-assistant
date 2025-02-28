import os
import requests
from typing import List, Optional, Dict, Any
from app.config import settings

class RagAPI:
    """QAnything API封装类"""
    
    def __init__(self, base_url: str = settings.RAG_API_BASE):
        self.base_url = base_url.rstrip('/')
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"RAG API请求失败: {str(e)}")

    def create_knowledge_base(self, kb_name: str) -> Dict[str, Any]:
        """
        创建新的知识库
        
        Args:
            kb_name: 知识库名称
            
        Returns:
            Dict: 包含knowledge_base_id的响应
        """
        endpoint = "/local_doc_qa/new_knowledge_base"
        data = {"user_id": "zzp", "kb_name": kb_name}
        return self._make_request("POST", endpoint, json=data)

    def upload_files(
        self, 
        kb_id: str, 
        files: List[str],
        chunk_size: int = 800,
        user_id: str = "zzp",
        mode: str = "soft"
    ) -> Dict[str, Any]:
        """
        上传文件到知识库
        
        Args:
            kb_id: 知识库ID
            files: 文件路径列表
            chunk_size: 分块大小
            user_id: 用户ID
            mode: 上传模式，可选soft或其他
            
        Returns:
            Dict: 上传结果
        """
        endpoint = "/local_doc_qa/upload_files"
        
        # 普通表单字段
        data = {
            "kb_id": kb_id,
            "user_id": user_id,
            "chunk_size": str(chunk_size),
            "mode": mode
        }
        
        # 文件列表
        files_list = []
        file_objects = []
        
        try:
            for file_path in files:
                f = open(file_path, 'rb')
                file_objects.append(f)
                filename = os.path.basename(file_path)
                files_list.append(("files", (filename, f, 'text/plain'))) 
                
            return self._make_request("POST", endpoint, data=data, files=files_list)
        finally:
            for f in file_objects:
                f.close()

    def list_files(
        self,
        kb_id: str,
        page_id: int = 1,
        page_limit: int = 10,
        user_id: str = "zzp",
        file_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取知识库中的文件列表
        
        Args:
            kb_id: 知识库ID
            page_id: 页码，从1开始
            page_limit: 每页显示的数量
            user_id: 用户ID
            file_id: 文件ID
            
        Returns:
            Dict: 文件列表信息
        """
        endpoint = "/local_doc_qa/list_files"
        data = {
            "kb_id": kb_id,
            "user_id": user_id,
            "page_id": page_id,
            "page_limit": page_limit
        }
        if file_id:
            data["file_id"] = file_id
        return self._make_request("POST", endpoint, json=data)

    def get_doc_completed(self, kb_id: str, doc_id: str) -> Dict[str, Any]:
        """
        获取文档的完整解析内容
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            
        Returns:
            Dict: 文档解析内容
        """
        endpoint = "/local_doc_qa/get_doc_completed"
        params = {
            "knowledge_base_id": kb_id,
            "doc_id": doc_id
        }
        return self._make_request("GET", endpoint, params=params)

    def get_doc_detail(self, kb_id: str, doc_id: str) -> Dict[str, Any]:
        """
        获取文档的详细信息
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            
        Returns:
            Dict: 文档详细信息
        """
        endpoint = "/local_doc_qa/get_doc"
        params = {
            "knowledge_base_id": kb_id,
            "doc_id": doc_id
        }
        return self._make_request("GET", endpoint, params=params)

    def chat(
        self,
        kb_id: str,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False,
        temperature: float = 0.7,
        top_p: float = 0.7,
        max_tokens: int = 2048,
        doc_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        知识库问答接口
        
        Args:
            kb_id: 知识库ID
            question: 问题内容
            history: 历史对话记录
            stream: 是否使用流式响应
            temperature: 温度参数
            top_p: 核采样参数
            max_tokens: 最大生成token数
            doc_ids: 指定的文档ID列表
            
        Returns:
            Dict: 问答结果
        """
        endpoint = "/local_doc_qa/local_doc_chat"
        data = {
            "knowledge_base_id": kb_id,
            "question": question,
            "history": history or [],
            "stream": stream,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens
        }
        if doc_ids:
            data["doc_ids"] = doc_ids
            
        return self._make_request("POST", endpoint, json=data)

# 创建全局实例
rag_api = RagAPI()
