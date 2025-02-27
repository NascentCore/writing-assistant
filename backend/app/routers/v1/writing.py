from enum import Enum
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.response import APIResponse
from app.database import get_db
from app.services import OutlineGenerator
from app.models.upload_file import UploadFile
from app.models.outline import Outline, SubParagraph, CountStyle, WritingTemplate, WritingTemplateType
from app.config import Settings


router = APIRouter()

# 枚举类型
class CountStyle(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

class ReferenceType(int, Enum):
    WEB_LINK = 1
    BOOK = 2
    PAPER = 3

# WebLink模型
class WebLinkBase(BaseModel):
    url: str
    title: Optional[str] = None
    summary: Optional[str] = None
    icon_url: Optional[str] = None
    content_count: Optional[int] = None
    content: Optional[str] = None


class WritingRequest(BaseModel):
    prompt: str = Field(..., description="写作提示")
    file_ids: Optional[List[str]] = Field(None, description="文件ID列表")
    tpl_id: Optional[str] = Field(None, description="模板ID")
    outline_id: Optional[str] = Field(None, description="大纲ID")


class UpdateOutlineContent(BaseModel):
    count_style: str = Field(..., description="段落设置")
    level: int = Field(..., description="层级")
    reference_status: int = Field(..., description="引用状态")
    title: str = Field(..., description="标题")

class UpdateOutlineMetaRequest(BaseModel):
    outline_id: str = Field(..., description="大纲ID")
    markdown_content: str = Field(..., description="markdown内容")
    content: UpdateOutlineContent = Field(..., description="内容")


class OutlineMetaResponse(BaseModel):
    id: int = Field(..., description="大纲ID")
    title: str = Field(..., description="大纲标题")
    sub_paragraphs: List[dict] = Field(..., description="子段落列表")


class GetOutlineRequest(BaseModel):
    outline_id: str = Field(..., description="大纲ID")


@router.post("/get_outline_meta")
async def get_generate_outline(
    request: WritingRequest,
    db: Session = Depends(get_db)
):
    """
    获取生成大纲

    Args:
        prompt: 写作提示
        file_ids: 文件ID列表
        tpl_id: 模板ID
        outline_id: 大纲ID

    Returns:
        id: 大纲ID
        title: 大纲标题
        sub_paragraphs: 子段落列表
    """
    
    # 获取文件内容
    file_contents = []
    if request.file_ids:
        for file_id in request.file_ids:
            file = db.query(UploadFile).filter(UploadFile.id == file_id).first()
            if file and file.content:
                file_contents.append(file.content)
    
    # 初始化大纲生成器
    # TODO(dg): 需要可以配置模型
    outline_generator = OutlineGenerator()
    
    # 调用大模型生成结构化大纲
    outline_data = outline_generator.generate_outline(request.prompt, file_contents)
    
    # 保存到数据库
    saved_outline = outline_generator.save_outline_to_db(
        outline_data=outline_data,
        db_session=db,
        outline_id=request.outline_id if request.outline_id != "0" else None
    )
    
    return APIResponse.success(message="大纲生成成功", data=saved_outline)


@router.post("/update_outline_meta")
async def update_outline_meta(
    request: UpdateOutlineMetaRequest,
    db: Session = Depends(get_db)
):
    """
    更新大纲元数据

    Args:
        outline_id: 大纲ID
        markdown_content: markdown内容
        content: 内容对象
        
    Returns:
        success: 成功状态
    """
    
    # 查找大纲
    outline = db.query(Outline).filter(Outline.id == request.outline_id).first()
    if not outline:
        return APIResponse.error(message=f"未找到ID为{request.outline_id}的大纲")
    
    # 更新大纲标题
    outline.title = request.content.title
    
    # 查找对应的子段落
    sub_paragraph = db.query(SubParagraph).filter(
        SubParagraph.outline_id == request.outline_id,
        SubParagraph.title == request.content.title
    ).first()
    
    if sub_paragraph:
        # 更新子段落
        count_style_value = request.content.count_style.lower()
        # 确保count_style是有效的枚举值
        if count_style_value not in [e.value for e in CountStyle]:
            count_style_value = "medium"  # 默认值
            
        sub_paragraph.count_style = count_style_value
        sub_paragraph.reference_status = request.content.reference_status
    
    # 提交更改
    db.commit()
    
    return APIResponse.success(message="大纲更新成功")


@router.post("/get_outline_detail")
async def get_outline_detail(
    request: GetOutlineRequest,
    db: Session = Depends(get_db)
):
    """
    获取大纲详情
    
    Args:
        outline_id: 大纲ID
        
    Returns:
        id: 大纲ID
        title: 大纲标题
        sub_paragraphs: 子段落列表
    """
    from app.models.outline import Outline
    
    # 查找大纲
    outline = db.query(Outline).filter(Outline.id == request.outline_id).first()
    if not outline:
        return APIResponse.error(message=f"未找到ID为{request.outline_id}的大纲")
    
    # 构建响应数据
    response_data = {
        "id": outline.id,
        "title": outline.title,
        "sub_paragraphs": [
            {
                "id": sub_para.id,
                "title": sub_para.title,
                "description": sub_para.description,
                "count_style": sub_para.count_style.value,
                "reference_status": sub_para.reference_status
            }
            for sub_para in outline.sub_paragraphs
        ]
    }
    
    return APIResponse.success(message="获取大纲详情成功", data=response_data)


class GenerateFullContentRequest(BaseModel):
    outline_id: str = Field(..., description="大纲ID")


@router.post("/generate_full_content")
async def generate_full_content(
    request: GenerateFullContentRequest,
    db: Session = Depends(get_db)
):
    """
    根据大纲生成全文
    
    Args:
        outline_id: 大纲ID
        
    Returns:
        title: 文章标题
        content: 文章内容列表，每个元素包含标题和内容
        markdown: Markdown格式的完整文章
    """
    # 初始化大纲生成器
    outline_generator = OutlineGenerator()
    
    try:
        # 调用生成全文的方法
        full_content = outline_generator.generate_full_content(request.outline_id, db)
        
        return APIResponse.success(message="全文生成成功", data=full_content)
    except ValueError as e:
        return APIResponse.error(message=str(e))
    except Exception as e:
        return APIResponse.error(message=f"生成全文时出错: {str(e)}")



class TemplateBase(BaseModel):
    show_name: str = Field(..., description="模板显示名称")
    value: str = Field(..., description="模板内容")
    is_default: bool = Field(False, description="是否默认模板")
    background_url: Optional[str] = Field(None, description="背景图片URL")
    template_type: WritingTemplateType = Field(WritingTemplateType.OTHER, description="模板类型")
    variables: Optional[List[str]] = Field(None, description="模板变量列表")

class TemplateCreate(TemplateBase):
    pass

class TemplateResponse(TemplateBase):
    id: str = Field(..., description="模板ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

class TemplateListRequest(BaseModel):
    template_type: Optional[WritingTemplateType] = Field(None, description="模板类型")
    page: int = Field(1, description="页码")
    page_size: int = Field(10, description="每页数量")


@router.post("/templates/list")
async def get_templates(
    request: TemplateListRequest = TemplateListRequest(),
    db: Session = Depends(get_db)
):
    """
    获取写作模板列表 
    
    Args:
        template_type: 模板类型
        page: 页码
        page_size: 每页数量
        
    Returns:
        templates: 模板列表
        total: 总数
        page: 当前页码
        page_size: 每页数量
    """
    try:
        # 构建查询
        query = db.query(WritingTemplate)
        
        # 根据类型筛选
        if request.template_type:
            query = query.filter(WritingTemplate.template_type == request.template_type)
        
        # 计算总数
        total = query.count()
        
        # 分页
        templates = query.offset((request.page - 1) * request.page_size) \
                        .limit(request.page_size) \
                        .all()
        
        # 构建响应数据
        response_data = {
            "templates": [
                {
                    "id": template.id,
                    "show_name": template.show_name,
                    "value": template.value,
                    "is_default": template.is_default,
                    "background_url": template.background_url,
                    "template_type": template.template_type,
                    "variables": template.variables,
                    "created_at": template.created_at.isoformat(),
                    "updated_at": template.updated_at.isoformat()
                }
                for template in templates
            ],
            "total": total,
            "page": request.page,
            "page_size": request.page_size
        }
        
        return APIResponse.success(message="获取模板列表成功", data=response_data)
    except Exception as e:
        # 捕获所有异常，返回空列表
        print(f"Error getting templates: {str(e)}")
        return APIResponse.success(message="获取模板列表成功", data={
            "templates": [],
            "total": 0,
            "page": request.page,
            "page_size": request.page_size
        })


@router.post("/templates/create")
async def create_template(
    template: TemplateCreate,
    db: Session = Depends(get_db)
):
    """
    创建模板
    
    Args:
        template: 模板信息
        
    Returns:
        id: 模板ID
    """
    try:
        # 创建模板
        new_template = WritingTemplate(
            show_name=template.show_name,
            value=template.value,
            is_default=template.is_default,
            background_url=template.background_url,
            template_type=template.template_type,
            variables=template.variables
        )
        
        # 保存到数据库
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        
        return APIResponse.success(message="创建模板成功", data={"id": new_template.id})
    except Exception as e:
        db.rollback()
        print(f"Error creating template: {str(e)}")
        return APIResponse.error(message=f"创建模板失败: {str(e)}")

