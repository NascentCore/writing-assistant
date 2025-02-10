from datetime import datetime
from openai import OpenAI
from config import settings

# 调用 OpenAI API
response = client.chat.completions.create(
    model=settings.LLM_MODEL,
    messages=[{"role": msg["role"], "content": msg["content"]} for msg in messages],
    temperature=0.7,
    stream=False
)

# 保存 AI 回复
ai_message = {
    "role": "assistant",
    "content": response.choices[0].message.content,
    "timestamp": datetime.now().isoformat()
} 