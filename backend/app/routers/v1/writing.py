from enum import Enum
import logging
import shortuuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, UploadFile as FastAPIUploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session
import os
import asyncio
import concurrent.futures
import json

from app.schemas.response import APIResponse, PaginationData
from app.database import get_db
from app.services import OutlineGenerator
from app.models.upload_file import UploadFile
from app.models.outline import (
    Outline,
    ReferenceStatus, 
    SubParagraph, 
    CountStyle, 
    WritingTemplate, 
    WritingTemplateType, 
    Reference,
    WebLink,
    ReferenceType as ModelReferenceType,
    generate_uuid
)
from app.models.chat import ChatSession, ChatMessage, ChatSessionType, ContentType
from app.config import Settings
from app.parser import DocxParser
from app.auth import get_current_user
from app.models.user import User
from app.utils.outline import build_paragraph_key
from app.models.task import Task, TaskStatus, TaskType
from app.models.document import Document, DocumentVersion

logger = logging.getLogger("app")

router = APIRouter()

# 创建线程池执行器
executor = concurrent.futures.ThreadPoolExecutor()

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


class GenerateOutlineRequest(BaseModel):
    outline_id: Optional[str] = Field(None, description="大纲ID，如果提供则直接返回对应大纲")
    prompt: Optional[str] = Field(None, description="写作提示")
    file_ids: Optional[List[str]] = Field(None, description="文件ID列表")
    model_name: Optional[str] = Field(None, description="模型")


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


def get_sibling_index(paragraph, outline_id, db):
    """获取段落在同级中的序号（从1开始）"""
    if not paragraph.parent_id:
        # 获取所有顶级段落
        siblings = db.query(SubParagraph).filter(
            SubParagraph.outline_id == outline_id,
            SubParagraph.parent_id == None
        ).order_by(SubParagraph.id).all()
    else:
        # 获取同一父段落下的所有子段落
        siblings = db.query(SubParagraph).filter(
            SubParagraph.parent_id == paragraph.parent_id
        ).order_by(SubParagraph.id).all()
    
    # 找到当前段落的索引
    for i, sibling in enumerate(siblings, 1):
        if sibling.id == paragraph.id:
            return i
    return 1

@router.post("/outlines/generate")
async def generate_outline(
    request: GenerateOutlineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    异步生成大纲

    Args:
        outline_id: 大纲ID，如果提供则直接返回对应大纲
        prompt: 写作提示
        file_ids: 文件ID列表
        readable_model_name: 模型

    Returns:
        task_id: 任务ID
        session_id: 会话ID
    """
    
    # 如果提供了outline_id，直接返回对应大纲
    if request.outline_id:
        outline = db.query(Outline).filter(Outline.id == request.outline_id).first()
        if not outline:
            return APIResponse.error(message=f"未找到ID为{request.outline_id}的大纲")
            
        # 校验权限：只能访问自己的大纲或系统预留的大纲
        if outline.user_id is not None and outline.user_id != current_user.user_id:
            return APIResponse.error(message="您没有权限访问该大纲")
            
        # 如果是系统预留大纲（user_id为空），创建一个副本
        if outline.user_id is None:
            # 创建新大纲
            new_outline = Outline(
                title=outline.title,
                user_id=current_user.user_id,
                reference_status=outline.reference_status
            )
            db.add(new_outline)
            db.flush()  # 获取新ID
            
            # 递归复制子段落
            def copy_paragraphs(paragraphs, parent_id=None):
                for para in paragraphs:
                    # 创建段落副本
                    new_para = SubParagraph(
                        outline_id=new_outline.id,
                        parent_id=parent_id,
                        level=para.level,
                        title=para.title,
                        description=para.description,
                        count_style=para.count_style,
                        reference_status=para.reference_status
                    )
                    db.add(new_para)
                    db.flush()  # 获取新ID
                    
                    # 复制引用
                    if para.level == 1:
                        for ref in para.references:
                            # 创建引用副本
                            new_ref = Reference(
                                id=shortuuid.uuid(),
                                sub_paragraph_id=new_para.id,
                                type=ref.type,
                                is_selected=ref.is_selected
                            )
                            db.add(new_ref)
                            db.flush()
                            
                            # 如果是网页链接，复制WebLink
                            if ref.type == ModelReferenceType.WEB_LINK.value and ref.web_link:
                                web_link = ref.web_link
                                new_web_link = WebLink(
                                    reference_id=new_ref.id,
                                    url=web_link.url,
                                    title=web_link.title,
                                    summary=web_link.summary,
                                    icon_url=web_link.icon_url,
                                    content_count=web_link.content_count,
                                    content=web_link.content
                                )
                                db.add(new_web_link)
                    
                    # 递归处理子段落
                    children = db.query(SubParagraph).filter(
                        SubParagraph.parent_id == para.id
                    ).all()
                    if children:
                        copy_paragraphs(children, new_para.id)
            
            # 开始复制顶级段落
            top_level_paragraphs = db.query(SubParagraph).filter(
                SubParagraph.outline_id == outline.id,
                SubParagraph.parent_id == None
            ).all()
            copy_paragraphs(top_level_paragraphs)
            
            # 提交事务
            db.commit()
            
            # 使用新创建的大纲
            outline = new_outline
            
        # 一次性获取所有段落
        all_paragraphs = db.query(SubParagraph).filter(
            SubParagraph.outline_id == outline.id
        ).all()
        
        # 构建段落字典和父子关系字典
        paragraphs_dict = {p.id: p for p in all_paragraphs}
        siblings_dict = {}  # parent_id -> [ordered_child_ids]
        for p in all_paragraphs:
            if p.parent_id not in siblings_dict:
                siblings_dict[p.parent_id] = []
            siblings_dict[p.parent_id].append(p.id)
        
        # 确保每个列表都是按ID排序的
        for parent_id in siblings_dict:
            siblings_dict[parent_id].sort()
            
        # 构建响应数据
        def build_paragraph_data(paragraph):
            data = {
                "id": str(paragraph.id),
                "key": build_paragraph_key(paragraph, siblings_dict, paragraphs_dict),
                "title": paragraph.title,
                "description": paragraph.description,
                "level": paragraph.level,
                "reference_status": ReferenceStatus(paragraph.reference_status).value
            }
            
            # 只有1级段落才有count_style
            if paragraph.level == 1 and paragraph.count_style:
                data["count_style"] = paragraph.count_style.value
            
            # 只有1级段落才有引用
            if paragraph.level == 1:
                data["references"] = []
                # 获取引用
                references = db.query(Reference).filter(
                    Reference.sub_paragraph_id == paragraph.id
                ).all()
                
                if references:
                    for ref in references:
                        ref_data = {
                            "id": str(ref.id),
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
                                    "id": str(web_link.id),
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
        
        
        # 创建聊天会话
        session_id = f"chat-{shortuuid.uuid()}"[:22]
        chat_session = ChatSession(
            session_id=session_id,
            session_type=ChatSessionType.WRITING,
            user_id=current_user.user_id,
        )
        db.add(chat_session)
        
        # 创建用户的提问消息
        user_message = ChatMessage(
            message_id=shortuuid.uuid(),
            session_id=session_id,
            role="user",
            content=request.prompt or f"获取大纲: {outline.title}",
            content_type=ContentType.TEXT,
        )
        db.add(user_message)
        
        # 创建助手的回答消息
        assistant_message_id = shortuuid.uuid()
        assistant_message = ChatMessage(
            message_id=assistant_message_id,
            session_id=session_id,
            role="assistant",
            content_type=ContentType.OUTLINE,
            outline_id=str(outline.id),
            task_status=TaskStatus.COMPLETED.value
        )
        db.add(assistant_message)
        
        # 创建任务记录
        task_id = f"task-{shortuuid.uuid()}"[:22]
        task = Task(
            id=task_id,
            type=TaskType.GENERATE_OUTLINE,
            status=TaskStatus.COMPLETED,
            session_id=session_id,
            params={
                "user_id": current_user.user_id,
                "outline_id": str(outline.id)
            },
            result={"outline_id": str(outline.id)}
        )
        db.add(task)
        
        # 提交事务
        db.commit()
        
        # 返回任务ID和会话ID
        return APIResponse.success(message="大纲获取成功", data={
            "task_id": task_id,
            "session_id": session_id
        })
    
    # 创建聊天会话
    session_id = f"chat-{shortuuid.uuid()}"[:22]
    chat_session = ChatSession(
        session_id=session_id,
        session_type=ChatSessionType.WRITING,
        user_id=current_user.user_id,
    )
    db.add(chat_session)
    
    # 创建用户的提问消息
    user_message = ChatMessage(
        message_id=shortuuid.uuid(),
        session_id=session_id,
        role="user",
        content=request.prompt,
        content_type=ContentType.TEXT,
    )
    db.add(user_message)

    # 创建助手的回答消息（任务进行中状态）
    assistant_message_id = shortuuid.uuid()
    assistant_message = ChatMessage(
        message_id=assistant_message_id,
        session_id=session_id,
        role="assistant",
        content="正在生成大纲，请稍候...",
        content_type=ContentType.TEXT,
        task_status=TaskStatus.PENDING.value
    )
    db.add(assistant_message)
    
    # 创建任务记录
    task_id = f"task-{shortuuid.uuid()}"[:22]
    task = Task(
        id=task_id,
        type=TaskType.GENERATE_OUTLINE,
        status=TaskStatus.PENDING,
        session_id=session_id,
        params={
            "user_id": current_user.user_id,
            "prompt": request.prompt,
            "file_ids": request.file_ids or []
        }
    )
    db.add(task)
    
    # 提交事务
    db.commit()
    
    # 使用线程池运行异步任务，避免阻塞当前事件循环
    def run_async_task():
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 在新的事件循环中运行异步任务
        loop.run_until_complete(process_outline_generation(
            task_id=task_id,
            prompt=request.prompt,
            file_ids=request.file_ids or [],
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            readable_model_name=request.model_name
        ))
        
        loop.close()
    
    # 在线程池中启动任务
    executor.submit(run_async_task)
    
    # 立即返回响应，不等待异步任务完成
    return APIResponse.success(message="大纲生成任务已创建", data={
        "task_id": task_id,
        "session_id": session_id
    })


async def process_outline_generation(task_id: str, prompt: str, file_ids: List[str], session_id: str, assistant_message_id: str, readable_model_name: Optional[str] = None):
    """异步处理大纲生成任务"""
    # 创建新的数据库会话
    db = next(get_db())
    
    try:
        # 更新任务状态为处理中
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"任务 {task_id} 不存在")
            return
        
        task.status = TaskStatus.PROCESSING
        
        # 更新助手消息状态为处理中
        assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
        if assistant_message:
            assistant_message.task_status = TaskStatus.PROCESSING.value
            assistant_message.task_id = task_id
            assistant_message.content = "正在生成大纲，请稍候..."
        
        db.commit()
        
        # 从task.params中获取user_id
        task_params = task.params
        user_id = task_params.get("user_id")
        
        # 获取文件内容
        file_contents = []
        for file_id in file_ids:
            file = db.query(UploadFile).filter(UploadFile.id == file_id).first()
            if file and file.content:
                file_contents.append(file.content)
        
        # 初始化大纲生成器
        outline_generator = OutlineGenerator(readable_model_name=readable_model_name)
        
        # 调用大模型生成结构化大纲
        outline_data = outline_generator.generate_outline(prompt, file_contents)
        
        # 保存到数据库
        saved_outline = outline_generator.save_outline_to_db(
            outline_data=outline_data,
            db_session=db,
            user_id=user_id
        )
        
        # 创建助手的回答消息
        if assistant_message:
            # 更新之前创建的助手消息
            assistant_message.content_type = ContentType.OUTLINE
            assistant_message.outline_id = saved_outline["id"]
            assistant_message.task_status = TaskStatus.COMPLETED.value
            assistant_message.task_result = json.dumps({"outline_id": saved_outline["id"]})
        else:
            # 如果之前的消息不存在，创建新消息
            assistant_message = ChatMessage(
                message_id=shortuuid.uuid(),
                session_id=session_id,
                role="assistant",
                content_type=ContentType.OUTLINE,
                outline_id=saved_outline["id"],
                task_status=TaskStatus.COMPLETED.value,
                task_id=task_id,
                task_result=json.dumps({"outline_id": saved_outline["id"]})
            )
            db.add(assistant_message)
        
        # 更新任务状态为完成
        task.status = TaskStatus.COMPLETED
        task.result = {"outline_id": saved_outline["id"]}
        db.commit()
        
    except Exception as e:
        # 更新任务状态为失败
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        # 更新助手消息状态为失败
        assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
        if assistant_message:
            assistant_message.task_status = TaskStatus.FAILED.value
            assistant_message.content = f"生成大纲失败: {str(e)}"
        
        db.commit()
        
    finally:
        db.close()


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        id: 任务ID
        type: 任务类型
        status: 任务状态 PENDING, PROCESSING, COMPLETED, FAILED
        created_at: 创建时间
        updated_at: 更新时间
        result: 任务结果
        error: 错误信息
    """
    task = db.query(Task).filter(
        Task.id == task_id,
    ).first()
    
    if not task:
        return APIResponse.error(message=f"未找到ID为{task_id}的任务")
    
    response_data = {
        "id": task.id,
        "type": task.type.value,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "result": task.result,
        "error": task.error
    }
    
    return APIResponse.success(message="获取任务状态成功", data=response_data)


@router.put("/outlines/{outline_id}")
async def update_outline(
    outline_id: str,
    request: UpdateOutlineMetaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    差异化更新大纲结构
    
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
    outline = db.query(Outline).filter(
        Outline.id == outline_id,
        Outline.user_id == current_user.user_id
    ).first()
    if not outline:
        return APIResponse.error(message=f"未找到ID为{outline_id}的大纲")
    
    # 更新大纲标题
    outline.title = request.title
    
    # 注意：markdown_content 是一个只读属性，由系统根据段落结构自动生成
    # 这里不需要手动更新 markdown_content
    
    try:
        # 获取所有现有段落
        existing_paragraphs = db.query(SubParagraph).filter(
            SubParagraph.outline_id == outline_id
        ).all()
        
        # 将现有段落转换为字典，以ID为键
        existing_dict = {p.id: p for p in existing_paragraphs}
        
        # 收集新结构中的所有段落ID
        new_paragraph_ids = set()
        
        # 递归更新段落
        def update_paragraphs_recursively(paragraphs, parent_id=None):
            result_ids = []
            
            for para_data in paragraphs:
                paragraph_id = para_data.id
                
                # 如果有ID且存在于现有段落中，则更新
                if paragraph_id is not None and paragraph_id in existing_dict:
                    paragraph = existing_dict[paragraph_id]
                    
                    # 更新基本信息
                    paragraph.title = para_data.title
                    paragraph.description = para_data.description
                    paragraph.reference_status = ReferenceStatus(para_data.reference_status)
                    paragraph.level = para_data.level
                    paragraph.parent_id = parent_id
                    
                    # 只有1级段落才能设置count_style
                    if para_data.level == 1 and para_data.count_style:
                        count_style_value = para_data.count_style.lower()
                        # 确保count_style是有效的枚举值
                        if count_style_value not in [e.value for e in CountStyle]:
                            count_style_value = "medium"  # 默认值
                        paragraph.count_style = count_style_value
                    
                    # 记录此段落已处理
                    new_paragraph_ids.add(paragraph_id)
                    result_ids.append(paragraph_id)
                    
                    # 处理引用（只有1级段落才能有引用）
                    if para_data.level == 1:
                        # 删除所有现有引用
                        db.query(Reference).filter(
                            Reference.sub_paragraph_id == paragraph_id
                        ).delete()
                        
                        # 添加新引用
                        if para_data.references:
                            for ref_data in para_data.references:
                                # 创建引用
                                ref_id = ref_data.id if ref_data.id else shortuuid.uuid()
                                reference = Reference(
                                    id=ref_id,
                                    sub_paragraph_id=paragraph.id,
                                    type=ref_data.type.value,
                                    is_selected=ref_data.is_selected
                                )
                                db.add(reference)
                                db.flush()  # 获取ID
                                
                                # 如果是网页链接类型，创建WebLink
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
                else:
                    # 创建新段落
                    paragraph = SubParagraph(
                        outline_id=outline_id,
                        title=para_data.title,
                        description=para_data.description,
                        reference_status=ReferenceStatus(para_data.reference_status),
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
                    
                    # 如果是新创建的段落，记录其ID
                    if paragraph_id is not None:
                        new_paragraph_ids.add(paragraph_id)
                    result_ids.append(paragraph.id)
                    
                    # 只有1级段落才能有引用
                    if para_data.level == 1 and para_data.references:
                        for ref_data in para_data.references:
                            # 创建引用
                            ref_id = ref_data.id if ref_data.id else shortuuid.uuid()
                            reference = Reference(
                                id=ref_id,
                                sub_paragraph_id=paragraph.id,
                                type=ref_data.type.value,
                                is_selected=ref_data.is_selected
                            )
                            db.add(reference)
                            db.flush()  # 获取ID
                            
                            # 如果是网页链接类型，创建WebLink
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
                    child_ids = update_paragraphs_recursively(para_data.children, paragraph.id)
            
            return result_ids
        
        # 开始递归更新
        update_paragraphs_recursively(request.sub_paragraphs)
        
        # 删除不再存在的段落
        for old_id, old_paragraph in existing_dict.items():
            if old_id not in new_paragraph_ids:
                db.delete(old_paragraph)
        
        # 提交更改
        db.commit()
        
        return APIResponse.success(message="大纲更新成功", data={"id": outline.id})
    
    except Exception as e:
        db.rollback()
        return APIResponse.error(message=f"更新大纲失败: {str(e)}")


@router.get("/outlines/{outline_id}")
async def get_outline(
    outline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    
    # 校验权限：只能访问自己的大纲或系统预留的大纲
    if outline.user_id is not None and outline.user_id != current_user.user_id:
        return APIResponse.error(message="您没有权限访问该大纲")
    
    # 一次性获取所有段落
    all_paragraphs = db.query(SubParagraph).filter(
        SubParagraph.outline_id == outline_id
    ).all()
    
    # 构建段落字典和父子关系字典
    paragraphs_dict = {p.id: p for p in all_paragraphs}
    siblings_dict = {}  # parent_id -> [ordered_child_ids]
    for p in all_paragraphs:
        if p.parent_id not in siblings_dict:
            siblings_dict[p.parent_id] = []
        siblings_dict[p.parent_id].append(p.id)
    
    # 确保每个列表都是按ID排序的
    for parent_id in siblings_dict:
        siblings_dict[parent_id].sort()
    
    # 一次性获取所有引用
    all_references = db.query(Reference).filter(
        Reference.sub_paragraph_id.in_([p.id for p in all_paragraphs])
    ).all()
    references_dict = {}  # paragraph_id -> [references]
    for ref in all_references:
        if ref.sub_paragraph_id not in references_dict:
            references_dict[ref.sub_paragraph_id] = []
        references_dict[ref.sub_paragraph_id].append(ref)
    
    # 一次性获取所有WebLink
    weblink_ids = [
        ref.id for ref in all_references 
        if ref.type == ModelReferenceType.WEB_LINK.value
    ]
    all_weblinks = db.query(WebLink).filter(
        WebLink.reference_id.in_(weblink_ids)
    ).all() if weblink_ids else []
    weblinks_dict = {wl.reference_id: wl for wl in all_weblinks}
    
    # 递归构建段落数据
    def build_paragraph_data(paragraph):
        data = {
            "id": str(paragraph.id),
            "key": build_paragraph_key(paragraph, siblings_dict, paragraphs_dict),
            "title": paragraph.title,
            "description": paragraph.description,
            "level": paragraph.level,
            "reference_status": ReferenceStatus(paragraph.reference_status).value
        }
        
        # 只有1级段落才有count_style
        if paragraph.level == 1 and paragraph.count_style:
            data["count_style"] = paragraph.count_style.value
        
        # 只有1级段落才有引用
        if paragraph.level == 1:
            data["references"] = []
            # 从缓存中获取引用
            for ref in references_dict.get(paragraph.id, []):
                ref_data = {
                    "id": str(ref.id),
                    "type": ref.type,
                    "is_selected": ref.is_selected
                }
                
                # 如果是网页链接类型，从缓存中获取WebLink信息
                if ref.type == ModelReferenceType.WEB_LINK.value:
                    web_link = weblinks_dict.get(ref.id)
                    if web_link:
                        ref_data["web_link"] = {
                            "id": str(web_link.id),
                            "url": web_link.url,
                            "title": web_link.title,
                            "summary": web_link.summary,
                            "icon_url": web_link.icon_url,
                            "content_count": web_link.content_count,
                            "content": web_link.content
                        }
                
                data["references"].append(ref_data)
        
        # 从缓存中获取子段落
        children_ids = siblings_dict.get(paragraph.id, [])
        if children_ids:
            data["children"] = [
                build_paragraph_data(paragraphs_dict[child_id]) 
                for child_id in children_ids
            ]
        else:
            data["children"] = []
        
        return data
    
    # 构建响应数据
    response_data = {
        "id": str(outline.id),
        "title": outline.title,
        "markdown_content": outline.markdown_content,
        "sub_paragraphs": [
            build_paragraph_data(paragraphs_dict[para_id]) 
            for para_id in siblings_dict.get(None, [])  # 获取顶级段落
        ]
    }
    
    return APIResponse.success(message="获取大纲详情成功", data=response_data)


class GenerateFullContentRequest(BaseModel):
    outline_id: Optional[str] = Field(None, description="大纲ID，如果为空则直接生成全文")
    session_id: Optional[str] = Field(None, description="会话ID")
    prompt: Optional[str] = Field(None, description="直接生成模式下的写作提示")
    file_ids: Optional[List[str]] = Field(None, description="直接生成模式下的参考文件ID列表")
    model_name: Optional[str] = Field(None, description="模型")


@router.post("/content/generate")
async def generate_content(
    request: GenerateFullContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    异步生成全文，支持两种模式：
    1. 基于大纲生成：提供 outline_id
    2. 直接生成：提供 prompt 和可选的 file_ids
    
    Args:
        request: 请求体，包含：
            - outline_id: 大纲ID（可选）
            - session_id: 会话ID（可选，如果不提供则创建新的）
            - prompt: 写作提示（直接生成模式下必需）
            - file_ids: 参考文件ID列表（可选）
            - readable_model_name: 模型（可选）
    Returns:
        task_id: 任务ID
        session_id: 会话ID
    """
    # 验证请求参数
    if not request.outline_id and not request.prompt:
        return APIResponse.error(message="必须提供大纲ID或写作提示")
    
    # 创建或使用现有会话ID
    session_id = request.session_id
    if not session_id:
        # 生成会话ID
        session_id = f"chat-{shortuuid.uuid()}"[:22]
    elif len(session_id) > 22:
        # 如果提供的会话ID超过22位，截取前22位
        session_id = session_id[:22]
    
    # 创建或更新聊天会话
    chat_session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()
    
    if not chat_session:
        # 创建新的聊天会话
        chat_session = ChatSession(
            session_id=session_id,
            session_type=ChatSessionType.WRITING,
            user_id=current_user.user_id
        )
        db.add(chat_session)
    
    # 创建聊天消息
    message_content = ""
    if request.outline_id:
        # 如果是从大纲生成，保存固定消息
        message_content = "请基于大纲生成全文"
        # 获取大纲信息
        outline = db.query(Outline).filter(Outline.id == request.outline_id).first()
        if outline:
            outline_id = outline.id
        else:
            outline_id = ""
    else:
        # 如果是直接生成，保存prompt
        message_content = request.prompt
        outline_id = ""
    
    # 创建用户消息
    message_id = f"msg-{shortuuid.uuid()}"[:22]
    chat_message = ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role="user",
        content=message_content,
        content_type=ContentType.TEXT,
        outline_id=outline_id
    )
    db.add(chat_message)
    
    # 创建助手的回答消息（任务进行中状态）
    assistant_message_id = shortuuid.uuid()
    assistant_message = ChatMessage(
        message_id=assistant_message_id,
        session_id=session_id,
        question_id=message_id,
        role="assistant",
        content="正在生成全文，请稍候...",
        content_type=ContentType.TEXT,
        task_status=TaskStatus.PENDING.value
    )
    db.add(assistant_message)
    
    # 创建任务记录，确保ID不超过22位
    task_id = f"task-{shortuuid.uuid()}"[:22]
    task = Task(
        id=task_id,
        type=TaskType.GENERATE_CONTENT,
        status=TaskStatus.PENDING,
        session_id=session_id,
        params={
            "user_id": current_user.user_id,
            "outline_id": request.outline_id,
            "prompt": request.prompt,
            "file_ids": request.file_ids or []
        }
    )
    db.add(task)
    db.commit()
    
    # 启动异步任务
    def run_async_task():
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 在新的事件循环中运行异步任务
        loop.run_until_complete(process_content_generation(
            task_id=task_id,
            outline_id=request.outline_id,
            prompt=request.prompt,
            file_ids=request.file_ids or [],
            session_id=session_id,
            message_id=message_id,
            assistant_message_id=assistant_message_id,
            readable_model_name=request.readable_model_name
        ))
        
        loop.close()
    
    # 在线程池中启动任务
    executor.submit(run_async_task)
    
    # 立即返回响应，不等待异步任务完成
    return APIResponse.success(message="全文生成任务已创建", data={
        "task_id": task_id,
        "session_id": session_id
    })


async def process_content_generation(task_id: str, outline_id: Optional[str], prompt: Optional[str], file_ids: List[str], session_id: str, message_id: str, assistant_message_id: str, readable_model_name: Optional[str] = None):
    """异步处理全文生成任务"""
    # 创建新的数据库会话
    db = next(get_db())
    
    try:
        # 更新任务状态为处理中
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"任务 {task_id} 不存在")
            return
        
        task.status = TaskStatus.PROCESSING
        
        # 更新助手消息状态为处理中
        assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
        if assistant_message:
            assistant_message.task_status = TaskStatus.PROCESSING.value
            assistant_message.task_id = task_id
            assistant_message.content = "正在生成全文，请稍候..."
        
        db.commit()
        
        # 从task.params中获取user_id
        task_params = task.params
        user_id = task_params.get("user_id")
        
        # 获取文件内容
        file_contents = []
        for file_id in file_ids:
            file = db.query(UploadFile).filter(UploadFile.id == file_id).first()
            if file and file.content:
                file_contents.append(file.content)
        
        # 初始化大纲生成器
        outline_generator = OutlineGenerator(readable_model_name=readable_model_name)
        
        # 根据模式生成内容
        try:
            if outline_id:
                # 基于大纲生成模式
                full_content = outline_generator.generate_full_content(outline_id, db)
            else:
                # 直接生成模式
                # 调用直接生成方法
                full_content = outline_generator.generate_content_directly(
                    prompt=prompt,
                    file_contents=file_contents
                )
            
            # 保存HTML内容到documents表
            doc_id = f"doc-{shortuuid.uuid()}"[:22]
            title = full_content.get("title", "无标题文档")
            html_content = full_content.get("html", "")
            
            # 创建文档记录
            document = Document(
                doc_id=doc_id,
                title=title,
                content=html_content,
                user_id=user_id  # 使用传入的user_id
            )
            db.add(document)
            
            # 创建AI回复消息
            ai_message_id = f"msg-{shortuuid.uuid()}"[:22]
            
            # 如果存在之前创建的助手消息，则更新它
            if assistant_message:
                assistant_message.content = ""
                assistant_message.content_type = ContentType.DOCUMENT
                assistant_message.document_id = doc_id
                assistant_message.task_status = TaskStatus.COMPLETED.value
                assistant_message.task_result = json.dumps({"doc_id": doc_id})
                assistant_message.full_content = json.dumps({"doc_id": doc_id})
            else:
                # 如果之前的消息不存在，创建新消息
                assistant_message = ChatMessage(
                    message_id=ai_message_id,
                    session_id=session_id,
                    question_id=message_id,
                    role="assistant",
                    content="",
                    content_type=ContentType.DOCUMENT,
                    document_id=doc_id,
                    task_status=TaskStatus.COMPLETED.value,
                    task_id=task_id,
                    task_result=json.dumps({"doc_id": doc_id}),
                    full_content=json.dumps({"doc_id": doc_id})
                )
                db.add(assistant_message)
            
            # 更新任务状态为完成
            task.status = TaskStatus.COMPLETED
            task.result = {"doc_id": doc_id}
            db.commit()
            
        except Exception as e:
            # 更新任务状态为失败
            task.status = TaskStatus.FAILED
            task.error = str(e)
            
            # 更新助手消息状态为失败
            if assistant_message:
                assistant_message.task_status = TaskStatus.FAILED.value
                assistant_message.content = f"生成全文失败: {str(e)}"
            
            db.commit()
            
    except Exception as e:
        print(f"处理全文生成任务时出错: {str(e)}")
    finally:
        db.close()


class TemplateBase(BaseModel):
    show_name: str = Field(..., description="模板显示名称")
    value: str = Field(..., description="模板内容")
    is_default: bool = Field(False, description="是否默认模板")
    description: Optional[str] = Field(None, description="模板描述")
    has_steps: bool = Field(False, description="是否分步骤")
    background_url: Optional[str] = Field(None, description="背景图片URL")
    template_type: WritingTemplateType = Field(WritingTemplateType.OTHER, description="模板类型")
    variables: Optional[List[str]] = Field(None, description="模板变量列表")
    outline_ids: Optional[List[str]] = Field(None, description="大纲ID列表")

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
        
        # 收集所有大纲ID
        all_outline_ids = []
        for template in templates:
            if template.default_outline_ids:
                all_outline_ids.extend(template.default_outline_ids)
        
        # 查询所有相关大纲
        outlines = {}
        if all_outline_ids:
            outline_records = db.query(Outline).filter(Outline.id.in_(all_outline_ids)).all()
            outlines = {str(outline.id): {"id": str(outline.id), "title": outline.title} for outline in outline_records}
        
        # 构建响应数据
        response_data = {
            "templates": [
                {
                    "id": template.id,
                    "show_name": template.show_name,
                    "value": template.value,
                    "is_default": template.is_default,
                    "description": template.description,
                    "background_url": template.background_url,
                    "template_type": template.template_type,
                    "variables": template.variables,
                    "created_at": template.created_at.isoformat(),
                    "updated_at": template.updated_at.isoformat(),
                    "outlines": [outlines.get(str(outline_id), {"id": str(outline_id), "title": "未知大纲"}) 
                                for outline_id in (template.default_outline_ids or [])],
                    "has_steps": template.has_steps
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
            id=shortuuid.uuid(),
            show_name=template.show_name,
            value=template.value,
            description=template.description,
            is_default=template.is_default,
            has_steps=template.has_steps,
            background_url=template.background_url,
            template_type=template.template_type,
            variables=template.variables,
            default_outline_ids=template.outline_ids
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


@router.post("/outlines/parse")
async def parse_outline(
    file: FastAPIUploadFile = File(...),
    readable_model_name: Optional[str] = Query(None, description="模型"),
    db: Session = Depends(get_db)
):
    """
    从Word文档解析大纲结构
    
    Args:
        file: Word文档文件(.doc或.docx)
        readable_model_name: 模型（可选）
    Returns:
        id: 大纲ID
        title: 大纲标题
        sub_paragraphs: 段落列表
    """
    file_path = None
    
    try:
        # 检查文件类型
        if not file.filename.lower().endswith(('.doc', '.docx')):
            return APIResponse.error(message="仅支持.doc或.docx格式的Word文档")
        
        # 保存上传的文件
        file_path = f"/tmp/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 解析文档
        parser = DocxParser()
        doc = parser.parse_to_doc(file_path)
        
        # 获取大纲结构
        outline_data = parser.get_outline_structure(doc)
        
        # 初始化大纲生成器
        outline_generator = OutlineGenerator(readable_model_name=readable_model_name)
        
        # 保存到数据库
        saved_outline = outline_generator.save_outline_to_db(
            outline_data=outline_data,
            db_session=db
        )
        
        return APIResponse.success(message="大纲解析成功", data=saved_outline)
        
    except Exception as e:
        return APIResponse.error(message=f"解析大纲失败: {str(e)}")
    
    finally:
        # 清理临时文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"清理临时文件失败: {str(e)}")  # 记录错误但不影响主流程



@router.get("/chat/sessions", summary="获取写作会话列表")
async def get_chat_sessions(
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 构建基础查询
        query = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.user_id,
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.is_deleted == False
        )
        
        # 获取总记录数
        total = query.count()
        pages = (total + page_size - 1) // page_size
        
        # 分页查询会话
        sessions = query.order_by(desc(ChatSession.id))\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        # 获取每个会话的最后一条消息
        session_data = []
        for session in sessions:
            last_message = db.query(ChatMessage)\
                .filter(
                    ChatMessage.session_id == session.session_id,
                    ChatMessage.is_deleted == False
                )\
                .order_by(desc(ChatMessage.id))\
                .first()
            
            first_message = db.query(ChatMessage)\
                .filter(
                    ChatMessage.session_id == session.session_id,
                    ChatMessage.role == "user",
                    ChatMessage.is_deleted == False
                )\
                .order_by(ChatMessage.id)\
                .first()
            
            # 查询未完成的任务
            unfinished_tasks = db.query(Task).filter(
                Task.session_id == session.session_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING])
            ).all()
            
            # 提取未完成任务的ID
            unfinished_task_ids = [task.id for task in unfinished_tasks]
            
            session_data.append({
                "session_id": session.session_id,
                "session_type": session.session_type,
                "last_message": last_message.content if last_message else None,
                "last_message_time": last_message.created_at.strftime("%Y-%m-%d %H:%M:%S") if last_message else None,
                "first_message": first_message.content if first_message else None,
                "first_message_time": first_message.created_at.strftime("%Y-%m-%d %H:%M:%S") if first_message else None,
                "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": session.updated_at.strftime("%Y-%m-%d %H:%M:%S") if session.updated_at else None,
                "unfinished_task_ids": unfinished_task_ids
            })
        
        return APIResponse.success(
            message="获取知识库会话列表成功",
            data=PaginationData(
                list=session_data,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=pages
            )
        )
        
    except Exception as e:
        logger.error(f"获取知识库会话列表失败: {str(e)}")
        return APIResponse.error(message=f"获取知识库会话列表失败: {str(e)}")

@router.get("/chat/sessions/{session_id}", summary="获取写作会话详情")
async def get_chat_session_detail(
    session_id: str = Path(..., description="会话ID"),
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话是否存在且属于当前用户
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id,
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.is_deleted == False
        ).first()
        if not session:
            return APIResponse.error(message="会话不存在或无权访问")
        
        # 查询消息
        query = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.is_deleted == False
        )
        
        total = query.count()
        pages = (total + page_size - 1) // page_size
        
        messages = query.order_by(ChatMessage.id)\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        # 查询未完成的任务
        unfinished_tasks = db.query(Task).filter(
            Task.session_id == session_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING])
        ).all()
        
        # 提取未完成任务的ID
        unfinished_task_ids = [task.id for task in unfinished_tasks]
            
        return APIResponse.success(
            data={
                "total": total,
                "items": [
                    {
                        "message_id": msg.message_id,
                        "role": msg.role,
                        "content": msg.content,
                        "content_type": msg.content_type,
                        "document_id": str(msg.document_id) if msg.document_id else "",
                        "outline_id": str(msg.outline_id) if msg.outline_id else "",
                        "task_id": msg.task_id,
                        "task_status": msg.task_status,
                        "task_result": msg.task_result,
                        "files": json.loads(msg.meta).get("files", []) if msg.meta else [],
                        "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for msg in messages
                ],
                "page": page,
                "page_size": page_size,
                "pages": pages,
                "unfinished_task_ids": unfinished_task_ids
            }
        )
        
    except Exception as e:
        logger.error(f"获取知识库会话详情失败: {str(e)}")
        return APIResponse.error(message=f"获取知识库会话详情失败: {str(e)}")

@router.delete("/chat/sessions/{session_id}", summary="删除写作会话")
async def delete_chat_session(
    session_id: str = Path(..., description="会话ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 验证会话是否存在且属于当前用户
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id,
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.is_deleted.is_(False)  # 遵循 PEP 8
        ).first()
        
        if not session:
            return APIResponse.error(message="会话不存在或无权访问")
        
        # 软删除会话
        session.is_deleted = True
        db.flush()  # 确保变更生效
        
        # 软删除该会话下的所有消息
        db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.is_deleted.is_(False)
        ).update({"is_deleted": True}, synchronize_session="fetch")
        
        db.commit()
        return APIResponse.success(message="会话删除成功")
    
    except Exception as e:
        db.rollback()  # 避免数据库处于不一致状态
        return APIResponse.error(message=f"删除失败: {str(e)}")