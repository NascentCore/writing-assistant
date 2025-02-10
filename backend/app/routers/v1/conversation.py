from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator
from openai import OpenAI
import json
from redis import Redis
from uuid import uuid4
from datetime import datetime
from app.config import settings  # 假设配置文件中存储了 OPENAI_API_KEY


router = APIRouter()

class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None  # 如果为空则创建新对话
    message: str
    # model: str = "gpt-3.5-turbo"

async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis(
        host='localhost', 
        port=6379, 
        db=0, 
        # password='your_password',  # 使用在docker-compose中设置的密码
        decode_responses=True
    )
    try:
        yield redis
    finally:
        redis.close()

@router.post("/chat")
async def chat(request: ChatRequest, redis: Redis = Depends(get_redis)):
    try:
        if not request.conversation_id:
            # 创建新对话
            request.conversation_id = str(uuid4())
            messages = [{
                "role": "system",
                "content": settings.LLM_SYSTEM_PROMPT
            }]
        else:
            # 获取历史消息
            messages_str = redis.get(f"chat:{request.conversation_id}")
            messages = json.loads(messages_str) if messages_str else [{
                "role": "system", 
                "content": settings.LLM_SYSTEM_PROMPT
            }]

        # 添加用户新消息
        current_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        }
        messages.append(current_message)

        client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL
        )

        # 调用 OpenAI API
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": msg["role"], "content": msg["content"]} for msg in messages],
            temperature=0.7,
        )

        # 保存 AI 回复
        ai_message = {
            "role": "assistant",
            "content": response.choices[0].message.content,
            "timestamp": datetime.now().isoformat()
        }
        messages.append(ai_message)

        # 保存到 Redis（设置 24 小时过期）
        redis.setex(
            f"chat:{request.conversation_id}",
            24 * 3600,  # 24小时过期
            json.dumps(messages)
        )

        return {
            "conversation_id": request.conversation_id,
            "message": ai_message["content"],
            "total_tokens": response.usage.total_tokens,
            "history": messages
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/conversation/{conversation_id}")
async def get_conversation_history(conversation_id: str, redis: Redis = Depends(get_redis)):
    try:
        messages_str = redis.get(f"chat:{conversation_id}")
        if not messages_str:
            raise HTTPException(status_code=404, detail="对话不存在或已过期")
        
        messages = json.loads(messages_str)
        return {"conversation_id": conversation_id, "history": messages}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
