import os
import requests
import json
from typing import List, Optional, Dict, Any, Union, Iterator, AsyncIterator
from app.config import settings
import logging
import aiohttp
import asyncio

logger = logging.getLogger("app.rag_api")

class RagAPI:
    """QAnything API异步封装类"""
    
    def __init__(self, base_url: str = settings.RAG_KB_API_BASE):
        self.base_url = base_url.rstrip('/')
        self._session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送异步HTTP请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        try:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"RAG API请求失败: {str(e)}")

    async def _make_streaming_request(self, method: str, endpoint: str, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """发送异步HTTP流式请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        
        # 设置较大的读取限制
        timeout = aiohttp.ClientTimeout(total=3600)  # 设置1小时超时
        kwargs['timeout'] = timeout
        
        try:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                # 使用 aiohttp.StreamReader 的 read 方法替代按行读取
                buffer = b""
                async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line_str = line.decode('utf-8').strip()
                        if not line_str:
                            continue
                        
                        if line_str.startswith("data: "):
                            json_str = line_str[6:].strip()
                            if json_str == "[DONE]":
                                return
                            try:
                                data = json.loads(json_str)
                                yield data
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON解析错误: {json_str}, 错误: {str(e)}")
                                continue
                        else:
                            try:
                                data = json.loads(line_str)
                                yield data
                            except json.JSONDecodeError:
                                logger.debug(f"非JSON格式数据: {line_str}")
                                continue
                            
        except aiohttp.ClientError as e:
            logger.error(f"RAG API流式请求失败: {str(e)}")
            raise Exception(f"RAG API流式请求失败: {str(e)}")

    async def create_knowledge_base(self, kb_name: str) -> Dict[str, Any]:
        """创建新的知识库（异步）"""
        endpoint = "/local_doc_qa/new_knowledge_base"
        data = {"user_id": "zzp", "kb_name": kb_name}
        return await self._make_request("POST", endpoint, json=data)

    async def upload_files(
        self, 
        kb_id: str, 
        files: List[str],
        chunk_size: int = 800,
        user_id: str = "zzp",
        mode: str = "soft"
    ) -> Dict[str, Any]:
        """上传文件到知识库（异步）"""
        endpoint = "/local_doc_qa/upload_files"
        data = {
            "kb_id": kb_id,
            "user_id": user_id,
            "chunk_size": str(chunk_size),
            "mode": mode
        }
        
        files_list = []
        file_objects = []
        try:
            for file_path in files:
                f = open(file_path, 'rb')
                file_objects.append(f)
                file_name = os.path.basename(file_path)
                files_list.append(("files", (file_name, f, 'text/plain')))

            return await self._make_request("POST", endpoint, data=data, files=files_list)
        finally:
            for f in file_objects:
                f.close()

    async def list_files(
        self,
        kb_id: str,
        page_id: int = 1,
        page_limit: int = 10,
        user_id: str = "zzp",
        file_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取知识库中的文件列表（异步）"""
        endpoint = "/local_doc_qa/list_files"
        data = {
            "kb_id": kb_id,
            "user_id": user_id,
            "page_id": page_id,
            "page_limit": page_limit
        }
        if file_id:
            data["file_id"] = file_id
        return await self._make_request("POST", endpoint, json=data)
    
    async def delete_files(
        self,
        kb_id: str,
        file_ids: List[str],
        user_id: str = "zzp"
    ) -> Dict[str, Any]:
        """从知识库中删除文件（异步）"""
        endpoint = "/local_doc_qa/delete_files"
        data = {
            "kb_id": kb_id,
            "user_id": user_id,
            "file_ids": file_ids
        }
        return await self._make_request("POST", endpoint, json=data)

    async def chat(
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
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """知识库问答接口（异步）"""
        endpoint = "/local_doc_qa/local_doc_chat"
        data = {
            "user_id": user_id,
            "kb_ids": kb_ids,
            "history": history or [],
            "question": question,
            "custom_prompt": custom_prompt,
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
            return await self._make_request("POST", endpoint, json=data)

    async def close(self):
        """关闭aiohttp会话"""
        if self._session and not self._session.closed:
            await self._session.close()

# 创建全局实例
rag_api = RagAPI()
