from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.system_config import SystemConfig
from app.schemas.response import APIResponse
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()

class PromptTemplateUpdate(BaseModel):
    prompt: str = Field(..., description="提示词模板内容")
    description: Optional[str] = Field(None, description="模板描述")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "请根据下面的文本，自动为其补全内容",
                "description": "自动补全模板"
            }
        }

@router.get("/prompts")
async def get_prompt_templates(db: Session = Depends(get_db)):
    """获取提示词模板列表"""
    templates = db.query(SystemConfig).filter(
        SystemConfig.key.like("prompt.%")
    ).all()
    
    return APIResponse.success(
        message="获取成功",
        data=[
            {
                "key": template.key,
                "prompt": template.value,
                "description": template.description
            }
            for template in templates
        ]
    )

@router.put("/prompts/{key}")
async def update_prompt_template(
    key: str,
    prompt: PromptTemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    更新提示词模板
    
    Args:\n
        key: 提示词模板的键名，如 prompt.completion\n
        prompt: 提示词模板内容, 支持的变量\n
        description: 模板描述
        
    Returns:\n
        prompt: 更新后的模板内容\n
        description: 更新后的模板描述\n
    """
    # 验证key格式
    if not key.startswith("prompt."):
        return APIResponse.error(message="无效的提示词键名，必须以 'prompt.' 开头")
    
    db_template = db.query(SystemConfig).filter(
        SystemConfig.key == key
    ).first()
    
    if not db_template:
        db_template = SystemConfig(
            key=key,
            value=prompt.prompt,
            description=prompt.description or "默认提示词模板"
        )
        db.add(db_template)
    else:
        db_template.value = prompt.prompt
        if prompt.description:
            db_template.description = prompt.description
    
    db.commit()
    db.refresh(db_template)
    
    return APIResponse.success(
        message="更新成功",
        data={
            "key": db_template.key,
            "prompt": db_template.value,
            "description": db_template.description
        }
    ) 