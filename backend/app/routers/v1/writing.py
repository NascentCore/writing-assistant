from enum import Enum
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.response import APIResponse
from app.database import get_db
from app.services import OutlineGenerator
from app.models.upload_file import UploadFile
from app.models.outline import (
    Outline, 
    SubParagraph, 
    CountStyle, 
    WritingTemplate, 
    WritingTemplateType, 
    Reference, 
    WebLink,
    ReferenceType as ModelReferenceType
)
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


class WebLinkUpdate(BaseModel):
    id: Optional[int] = Field(None, description="WebLink ID，如果为空则创建新的")
    url: str = Field(..., description="网页URL")
    title: Optional[str] = Field(None, description="网页标题")
    summary: Optional[str] = Field(None, description="网页摘要")
    icon_url: Optional[str] = Field(None, description="网页图标")
    content_count: Optional[int] = Field(None, description="内容字数")
    content: Optional[str] = Field(None, description="网页正文")

class ReferenceUpdate(BaseModel):
    id: Optional[str] = Field(None, description="引用ID，如果为空则创建新的")
    type: ReferenceType = Field(..., description="引用类型")
    is_selected: bool = Field(False, description="是否被选中")
    web_link: Optional[WebLinkUpdate] = Field(None, description="网页链接，仅当type为WEB_LINK时有效")

class UpdateOutlineContent(BaseModel):
    id: Optional[int] = Field(None, description="段落ID，如果为空则创建新段落")
    title: str = Field(..., description="标题")
    description: Optional[str] = Field(None, description="描述")
    level: int = Field(..., description="段落级别")
    parent_id: Optional[int] = Field(None, description="父段落ID")
    count_style: Optional[str] = Field(None, description="段落设置，仅1级段落有效")
    reference_status: int = Field(0, description="引用状态")
    references: Optional[List[ReferenceUpdate]] = Field([], description="引用列表，仅1级段落有效")
    children: Optional[List["UpdateOutlineContent"]] = Field([], description="子段落列表")

# 解决循环引用问题
UpdateOutlineContent.update_forward_refs()

class UpdateOutlineMetaRequest(BaseModel):
    outline_id: str = Field(..., description="大纲ID")
    title: str = Field(..., description="大纲标题")
    sub_paragraphs: List[UpdateOutlineContent] = Field([], description="段落列表")


class GetOutlineRequest(BaseModel):
    outline_id: str = Field(..., description="大纲ID")


@router.post("/outlines/generate")
async def generate_outline(
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


@router.put("/outlines/{outline_id}")
async def update_outline(
    outline_id: str,
    request: UpdateOutlineMetaRequest,
    db: Session = Depends(get_db)
):
    """
    全量更新大纲结构
    
    Args:
        outline_id: 大纲ID
        title: 大纲标题
        sub_paragraphs: 段落列表
        
    Returns:
        success: 成功状态
        data: 更新后的大纲ID
    """
    # 确保路径参数和请求体中的ID一致
    if outline_id != request.outline_id:
        return APIResponse.error(message="路径参数与请求体中的大纲ID不一致")
    
    # 查找大纲
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return APIResponse.error(message=f"未找到ID为{outline_id}的大纲")
    
    # 更新大纲标题
    outline.title = request.title
    
    # 注意：markdown_content 是一个只读属性，由系统根据段落结构自动生成
    # 这里不需要手动更新 markdown_content
    
    # 删除所有现有段落（级联删除引用）
    db.query(SubParagraph).filter(SubParagraph.outline_id == outline_id).delete()
    db.commit()
    
    # 递归创建段落和引用
    def create_paragraphs(paragraphs, parent_id=None):
        for para_data in paragraphs:
            # 创建段落
            paragraph = SubParagraph(
                outline_id=outline_id,
                title=para_data.title,
                description=para_data.description,
                reference_status=para_data.reference_status,
                level=para_data.level,
                parent_id=parent_id
            )
            
            # 只有1级段落才能设置count_style
            if para_data.level == 1 and para_data.count_style:
                count_style_value = para_data.count_style.lower()
                # 确保count_style是有效的枚举值
                if count_style_value not in [e.value for e in CountStyle]:
                    count_style_value = "medium"  # 默认值
                paragraph.count_style = count_style_value
            
            db.add(paragraph)
            db.flush()  # 获取ID
            
            # 只有1级段落才能有引用
            if para_data.level == 1 and para_data.references:
                for ref_data in para_data.references:
                    # 创建引用
                    ref_id = ref_data.id if ref_data.id else str(uuid.uuid4())
                    reference = Reference(
                        id=ref_id,
                        sub_paragraph_id=paragraph.id,
                        type=ref_data.type.value,
                        is_selected=ref_data.is_selected
                    )
                    db.add(reference)
                    db.flush()  # 获取ID
                    
                    # 如果是网页链接类型，创建或更新WebLink
                    if ref_data.type == ReferenceType.WEB_LINK and ref_data.web_link:
                        web_link = WebLink(
                            reference_id=reference.id,
                            url=ref_data.web_link.url,
                            title=ref_data.web_link.title,
                            summary=ref_data.web_link.summary,
                            icon_url=ref_data.web_link.icon_url,
                            content_count=ref_data.web_link.content_count,
                            content=ref_data.web_link.content
                        )
                        db.add(web_link)
            
            # 递归处理子段落
            if para_data.children:
                create_paragraphs(para_data.children, paragraph.id)
    
    # 创建所有段落
    create_paragraphs(request.sub_paragraphs)
    
    # 提交更改
    db.commit()
    
    return APIResponse.success(message="大纲更新成功", data={"id": outline.id})


@router.get("/outlines/{outline_id}")
async def get_outline(
    outline_id: str,
    db: Session = Depends(get_db)
):
    """
    获取大纲详情
    
    Args:
        outline_id: 大纲ID
        
    Returns:
        id: 大纲ID
        title: 大纲标题
        markdown_content: 大纲的Markdown内容
        sub_paragraphs: 段落列表，包含层级结构和引用信息
    """
    # 查找大纲
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        return APIResponse.error(message=f"未找到ID为{outline_id}的大纲")
    
    # 递归构建段落数据
    def build_paragraph_data(paragraph):
        data = {
            "id": paragraph.id,
            "title": paragraph.title,
            "description": paragraph.description,
            "level": paragraph.level,
            "reference_status": paragraph.reference_status
        }
        
        # 只有1级段落才有count_style
        if paragraph.level == 1 and paragraph.count_style:
            data["count_style"] = paragraph.count_style.value
        
        # 只有1级段落才有引用
        if paragraph.level == 1:
            # 获取引用
            references = db.query(Reference).filter(
                Reference.sub_paragraph_id == paragraph.id
            ).all()
            
            if references:
                data["references"] = []
                for ref in references:
                    ref_data = {
                        "id": ref.id,
                        "type": ref.type,
                        "is_selected": ref.is_selected
                    }
                    
                    # 如果是网页链接类型，获取WebLink信息
                    if ref.type == ModelReferenceType.WEB_LINK.value:
                        web_link = db.query(WebLink).filter(
                            WebLink.reference_id == ref.id
                        ).first()
                        
                        if web_link:
                            ref_data["web_link"] = {
                                "id": web_link.id,
                                "url": web_link.url,
                                "title": web_link.title,
                                "summary": web_link.summary,
                                "icon_url": web_link.icon_url,
                                "content_count": web_link.content_count,
                                "content": web_link.content
                            }
                    
                    data["references"].append(ref_data)
            else:
                data["references"] = []
        
        # 获取子段落
        children = db.query(SubParagraph).filter(
            SubParagraph.parent_id == paragraph.id
        ).all()
        
        if children:
            data["children"] = [build_paragraph_data(child) for child in children]
        else:
            data["children"] = []
        
        return data
    
    # 构建响应数据
    response_data = {
        "id": outline.id,
        "title": outline.title,
        "markdown_content": outline.markdown_content,
        "sub_paragraphs": [
            build_paragraph_data(para) for para in db.query(SubParagraph).filter(
                SubParagraph.outline_id == outline.id,
                SubParagraph.parent_id == None
            ).all()
        ]
    }
    
    return APIResponse.success(message="获取大纲详情成功", data=response_data)


class GenerateFullContentRequest(BaseModel):
    outline_id: str = Field(..., description="大纲ID")


@router.post("/outlines/{outline_id}/content")
async def generate_content(
    outline_id: str,
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
        full_content = outline_generator.generate_full_content(outline_id, db)
        
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


@router.get("/templates")
async def get_templates(
    template_type: Optional[WritingTemplateType] = None,
    page: int = 1,
    page_size: int = 10,
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
        if template_type:
            query = query.filter(WritingTemplate.template_type == template_type)
        
        # 计算总数
        total = query.count()
        
        # 分页
        templates = query.offset((page - 1) * page_size) \
                        .limit(page_size) \
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
            "page": page,
            "page_size": page_size
        }
        
        return APIResponse.success(message="获取模板列表成功", data=response_data)
    except Exception as e:
        # 捕获所有异常，返回空列表
        print(f"Error getting templates: {str(e)}")
        return APIResponse.success(message="获取模板列表成功", data={
            "templates": [],
            "total": 0,
            "page": page,
            "page_size": page_size
        })


@router.post("/templates")
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

