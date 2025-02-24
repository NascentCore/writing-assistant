import asyncio
import json
from typing import Dict
from fastapi import WebSocket, APIRouter
import openai
from app.config import settings

router = APIRouter()

active_connections: Dict[str, WebSocket] = {}

class ConnectionManager:
    def __init__(self):
        self.last_completion_time = {}
        self.completion_cooldown = 0.5  # 冷却时间,单位秒
        # 初始化 OpenAI 客户端
        self.openai_client = openai.AsyncOpenAI(
            api_key=settings.LLM_MODELS[0]["api_key"],
            base_url=settings.LLM_MODELS[0]["base_url"]
        )

    async def get_completion(self, text: str, cursor: int) -> str:
        """获取文本补全结果"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.LLM_MODELS[0]["model"],
                messages=[{
                    "role": "user",
                    "content": text[:cursor]
                }],
                stream=True,
                max_tokens=50,
                temperature=0.1  # 降低随机性,使补全更确定性
            )
            return response
        except Exception as e:
            print(f"获取补全结果失败: {str(e)}")
            return None

completion_manager = ConnectionManager()

@router.websocket("/complete")
async def websocket_endpoint(websocket: WebSocket):
    """处理WebSocket连接的补全请求"""
    await websocket.accept()
    client_id = id(websocket)
    active_connections[client_id] = websocket
    
    try:
        last_text = ""
        last_cursor = -1
        
        while True:
            data = await websocket.receive_text()
            content = json.loads(data)
            
            # 如果文本或光标位置改变,跳过本次补全
            if content["text"] != last_text or content["cursor"] != last_cursor:
                last_text = content["text"]
                last_cursor = content["cursor"]
                continue

            # 检查补全冷却时间
            current_time = asyncio.get_event_loop().time()
            last_time = completion_manager.last_completion_time.get(client_id, 0)
            
            if current_time - last_time >= completion_manager.completion_cooldown:
                completion_manager.last_completion_time[client_id] = current_time
                
                stream = await completion_manager.get_completion(
                    content["text"],
                    content["cursor"]
                )

                if stream:
                    suggestion = ""
                    async for chunk in stream:
                        # 再次检查文本和光标是否改变
                        if content["text"] != last_text or content["cursor"] != last_cursor:
                            break
                            
                        if chunk.choices[0].delta.content:
                            suggestion += chunk.choices[0].delta.content
                            # 每收到新的内容就发送
                            await websocket.send_json({
                                "timestamp": content["timestamp"],
                                "suggestion": suggestion
                            })

    except Exception as e:
        print(f"WebSocket连接错误: {str(e)}")
    finally:
        if client_id in active_connections:
            del active_connections[client_id]