from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.config import settings
import openai
import json

router = APIRouter()

@router.get("/config")
async def get_config():
    """获取大模型配置信息"""
    return {
        "message": "success",
        "data": {
            "llm": {
                "base_url": settings.LLM_BASE_URL,
                "model": settings.LLM_MODEL
            }
        }
    }

@router.post("/completions")
async def completions(request: Request):
    """OpenAI 兼容的 completions 接口"""
    body = await request.json()
    stream = body.get("stream", False)
    
    # 检查必需参数
    if "messages" not in body:
        raise ValueError("Missing required parameter: messages")
    
    # model
    body["model"] = settings.LLM_MODEL
    
    # 配置 OpenAI 客户端
    client = openai.AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY
    )
    
    if stream:
        # 流式响应
        async def generate_stream():
            completion = await client.chat.completions.create(
                **body
            )
            async for chunk in completion:
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream"
        )
    else:
        # 非流式响应
        completion = await client.chat.completions.create(
            **body
        )
        return completion.model_dump()

