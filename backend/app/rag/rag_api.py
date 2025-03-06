import os
import requests
import json
from typing import List, Optional, Dict, Any, Union, Iterator
from app.config import settings
import logging

logger = logging.getLogger("app.rag_api")

class RagAPI:
    """QAnything API封装类"""
    
    def __init__(self, base_url: str = settings.RAG_KB_API_BASE):
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

    def _make_streaming_request(self, method: str, endpoint: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """发送HTTP流式请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        try:
            with requests.request(method, url, stream=True, **kwargs) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    # 先解码为字符串
                    line_str = line.decode('utf-8').strip()
                    
                    # 处理SSE格式
                    if line_str.startswith("data: "):
                        json_str = line_str[6:].strip()  # 去掉 "data: " 前缀
                        if json_str == "[DONE]":
                            break
                        try:
                            data = json.loads(json_str)
                            yield data
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON解析错误: {json_str}, 错误: {str(e)}")
                            continue
                    else:
                        # 尝试直接解析JSON
                        try:
                            data = json.loads(line_str)
                            yield data
                        except json.JSONDecodeError:
                            logger.debug(f"非JSON格式数据: {line_str}")
                            continue
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"RAG API流式请求失败: {str(e)}")
            raise Exception(f"RAG API流式请求失败: {str(e)}")

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
                file_name = os.path.basename(file_path)
                files_list.append(("files", (file_name, f, 'text/plain'))) 
                
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
    
    def delete_files(
        self,
        kb_id: str,
        file_ids: List[str],
        user_id: str = "zzp"
    ) -> Dict[str, Any]:
        """
        从知识库中删除文件
        
        Args:
            kb_id: 知识库ID
            file_ids: 要删除的文件ID列表
            user_id: 用户ID，默认为"zzp"
            
        Returns:
            Dict: 删除操作的响应结果
        """
        endpoint = "/local_doc_qa/delete_files"
        data = {
            "kb_id": kb_id,
            "user_id": user_id,
            "file_ids": file_ids
        }
        return self._make_request("POST", endpoint, json=data)    

    def chat(
        self,
        kb_ids: List[str],
        question: str,
        custom_prompt: Optional[str] = None,
        history: Optional[List[List[str]]] = None,
        streaming: bool = True,  # 默认开启流式返回
        networking: bool = False,
        product_source: str = "saas",
        rerank: bool = False,
        only_need_search_results: bool = False,
        hybrid_search: bool = False,
        max_token: int = 512,
        api_base: str = settings.RAG_KB_API_BASE, 
        api_key: str = settings.RAG_SUMMARY_API_KEY,
        model: str = settings.RAG_SUMMARY_MODEL,
        api_context_length: int = 4096,
        chunk_size: int = 800,
        top_p: float = 1.0,
        top_k: int = 30,
        temperature: float = 0.5,
        user_id: str = "zzp"
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """
        知识库问答接口
        
        Args:
            kb_ids: 知识库ID列表
            question: 问题内容
            history: 历史对话记录，格式为[[question1, answer1], [question2, answer2], ...]
            streaming: 是否使用流式返回
            networking: 是否使用联网功能
            product_source: 产品来源
            rerank: 是否重新排序
            only_need_search_results: 是否只需要搜索结果
            hybrid_search: 是否使用混合搜索
            max_token: 最大生成token数
            api_base: API基础URL
            api_key: API密钥
            model: 模型名称
            api_context_length: API上下文长度
            chunk_size: 分块大小
            top_p: 核采样参数
            top_k: 保留最高概率的k个token
            temperature: 温度参数
            user_id: 用户ID
            
        Returns:
            Union[Dict[str, Any], Iterator[Dict[str, Any]]]: 如果streaming=True，返回迭代器；否则返回字典
        """
        endpoint = "/local_doc_qa/local_doc_chat"
        data = {
            "user_id": user_id,
            "kb_ids": kb_ids,
            "history": history or [],
            "question": question,
            "streaming": streaming,  # 添加streaming参数
            "networking": networking,
            "product_source": product_source,
            "rerank": rerank,
            "only_need_search_results": only_need_search_results,
            "hybrid_search": hybrid_search,
            "max_token": max_token,
            "api_base": api_base,
            "api_key": api_key,
            "model": model,
            "api_context_length": api_context_length,
            "chunk_size": chunk_size,
            "top_p": top_p,
            "top_k": top_k,
            "temperature": temperature
        }
        
        if streaming:
            return self._make_streaming_request("POST", endpoint, json=data)
        else:
            return self._make_request("POST", endpoint, json=data)

# 创建全局实例
rag_api = RagAPI()
