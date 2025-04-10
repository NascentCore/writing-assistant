from enum import Enum
import logging
import shortuuid
from typing import List, Optional, Tuple, Dict, Any
from fastapi import APIRouter, Depends, Path, UploadFile as FastAPIUploadFile, File, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session
import os
import asyncio
import concurrent.futures
import json
import time
from fastapi.responses import StreamingResponse
import threading
from datetime import datetime, timedelta

from app.schemas.response import APIResponse, PaginationData
from app.database import get_db
from app.services import OutlineGenerator
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
)
from app.models.chat import ChatSession, ChatMessage, ChatSessionType, ContentType
from app.config import settings
from app.parser import DocxParser, MarkdownParser
from app.auth import get_current_user
from app.models.user import User, UserRole
from app.utils.outline import  build_paragraph_response
from app.models.task import Task, TaskStatus, TaskType
from app.models.document import Document
from app.models.rag import RagFile, RagFileStatus, RagKnowledgeBase, RagKnowledgeBaseType
from app.models.department import UserDepartment
from app.models.system_config import SystemConfig

logger = logging.getLogger("app")

router = APIRouter()

# 存储正在运行的任务ID，避免重复处理
running_tasks = set()
# 线程锁，确保线程安全
task_lock = threading.Lock()
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
    at_file_ids: Optional[List[str]] = Field(default=[], description="@的文件ID列表")
    files: Optional[List[Dict[str, Any]]] = Field(default=[], description="关联的文件内容")
    at_file_ids: Optional[List[str]] = Field(default=[], description="@的文件ID列表")
    atfiles: Optional[List[Dict[str, Any]]] = Field(default=[], description="@的文件内容")
    model_name: Optional[str] = Field(None, description="模型")
    web_search: Optional[bool] = Field(False, description="是否进行网页搜索")


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
UpdateOutlineContent.model_rebuild()

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
        
        # 确保每个列表都是按 sort_index 排序的
        for parent_id in siblings_dict:
            siblings_dict[parent_id].sort(
                key=lambda para_id: (
                    paragraphs_dict[para_id].sort_index if paragraphs_dict[para_id].sort_index is not None else paragraphs_dict[para_id].id
                )
            )
            
        # 递归构建段落树
        def build_paragraph_tree(parent_id=None):
            result = []
            children_ids = siblings_dict.get(parent_id, [])
            
            # 对子段落按 sort_index 排序
            children_ids.sort(
                key=lambda para_id: (
                    paragraphs_dict[para_id].sort_index if paragraphs_dict[para_id].sort_index is not None else paragraphs_dict[para_id].id
                )
            )
            
            for para_id in children_ids:
                paragraph = paragraphs_dict[para_id]
                # 使用 build_paragraph_response 构建数据
                data = build_paragraph_response(
                    paragraph, 
                    siblings_dict, 
                    paragraphs_dict, 
                    {}, 
                    ReferenceStatus
                )
                
                # 递归处理子段落
                children = build_paragraph_tree(para_id)
                if children:
                    data["children"] = children
                
                result.append(data)
            
            return result
        
        
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
            meta=json.dumps({
                "files": request.files,
                "atfiles": request.atfiles
            })
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

        at_file_ids = []
        if request.at_file_ids:
            at_files = db.query(RagFile).filter(
                RagFile.file_id.in_(request.at_file_ids),
                RagFile.status == RagFileStatus.DONE,
                RagFile.is_deleted == False
            ).all()
            at_file_ids = [at_file.kb_file_id for at_file in at_files]
        
        # 记录任务到运行集合中
        with task_lock:
            running_tasks.add(task_id)
        
        # 启动异步任务
        executor.submit(run_outline_task,
            task_id=task_id,
            prompt=request.prompt,
            file_ids=request.file_ids or [],
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            readable_model_name=request.model_name,
            web_search=request.web_search,
            at_file_ids=at_file_ids
        )
        
        # 立即返回响应，不等待异步任务完成
        return APIResponse.success(message="大纲生成任务已创建", data={
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
        meta=json.dumps({
            "files": request.files,
            "atfiles": request.atfiles
        })
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
            "file_ids": request.file_ids or [],
            "web_search": request.web_search,
            "at_file_ids": request.at_file_ids
        }
    )
    db.add(task)
    
    # 提交事务
    db.commit()
    
    # 记录任务到运行集合中
    with task_lock:
        running_tasks.add(task_id)
    
    # 启动异步任务
    executor.submit(run_outline_task,
        task_id=task_id,
        prompt=request.prompt,
        file_ids=request.file_ids or [],
        session_id=session_id,
        assistant_message_id=assistant_message_id,
        readable_model_name=request.model_name,
        web_search=request.web_search,
        at_file_ids=at_file_ids
    )
    
    # 立即返回响应，不等待异步任务完成
    return APIResponse.success(message="大纲生成任务已创建", data={
        "task_id": task_id,
        "session_id": session_id
    })


async def process_outline_generation(task_id: str, prompt: str, file_ids: List[str], session_id: str, assistant_message_id: str, readable_model_name: Optional[str] = None, web_search: bool = False, at_file_ids: Optional[List[str]] = None):
    """
    异步处理大纲生成任务
    
    Args:
        task_id: 任务ID
        prompt: 写作提示
        file_ids: 参考文件ID列表
        session_id: 会话ID
        assistant_message_id: 助手消息ID
        readable_model_name: 模型名称（可选）
    """
    # 创建新的数据库会话
    db = next(get_db())
    start_time = time.time()
    
    try:
        logger.info(f"开始处理大纲生成任务 [task_id={task_id}]")
        
        # 更新任务和消息状态
        if not await _update_task_status(db, task_id, assistant_message_id, "正在生成大纲，请稍候...", TaskType.GENERATE_OUTLINE):
            return
        
        # 获取用户ID和参考文件内容
        user_id, file_contents = await _prepare_generation_resources(db, task_id, file_ids)
        
        # 初始化大纲生成器
        logger.info(f"初始化大纲生成器 [model={readable_model_name or 'default'}]")
        outline_generator = OutlineGenerator(readable_model_name=readable_model_name, use_web=web_search)
        
        try:
            kb_ids = []
            # 查询系统知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM, RagKnowledgeBase.is_deleted == False).first()

            if kb:
                kb_ids.append(kb.kb_id)
            # 查询用户共享知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER_SHARED, RagKnowledgeBase.is_deleted == False).first()
            if kb:
                kb_ids.append(kb.kb_id)
            # 查询用户私有知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, RagKnowledgeBase.user_id == user_id, RagKnowledgeBase.is_deleted == False).first()
            if kb:
                kb_ids.append(kb.kb_id)
            # 查询部门知识库
            department_ids = []
            user_departments = db.query(UserDepartment).filter(
                UserDepartment.user_id == user_id,
            ).all()
            if user_departments:
                department_ids = [department.department_id for department in user_departments]
                if department_ids:
                    department_kbs = db.query(RagKnowledgeBase).filter(
                        RagKnowledgeBase.kb_type == RagKnowledgeBaseType.DEPARTMENT,
                        RagKnowledgeBase.owner_id.in_(department_ids), 
                        RagKnowledgeBase.is_deleted == False).all()
                    if department_kbs:
                        kb_ids.extend([kb.kb_id for kb in department_kbs])
            
            # 生成大纲
            outline_data = await _generate_outline(outline_generator, prompt, file_contents, user_id, kb_ids, task_id, db, at_file_ids)
            
            # 保存大纲并更新消息
            await _save_outline_and_update_message(
                db, outline_generator, outline_data, user_id, task_id, 
                session_id, assistant_message_id
            )
            
            # 记录任务完成和耗时
            _log_task_completion(task_id, start_time, "大纲生成")
            
        except Exception as e:
            # 处理大纲生成过程中的异常
            await _handle_generation_error(db, task_id, assistant_message_id, e, start_time, "大纲生成")
            
    except Exception as e:
        # 处理整体流程中的异常
        _log_task_error(task_id, e, start_time, "大纲生成")
    finally:
        db.close()
        logger.info(f"大纲生成任务处理结束 [task_id={task_id}]")


async def _generate_outline(
    outline_generator: OutlineGenerator,
    prompt: str,
    file_contents: List[str],
    user_id: Optional[str] = None,
    kb_ids: Optional[List[str]] = None,
    task_id: Optional[str] = None,
    db_session = None,
    at_file_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """生成大纲"""
    logger.info("开始生成结构化大纲")
    outline_data = outline_generator.generate_outline(prompt, file_contents, user_id, kb_ids, task_id, db_session, at_file_ids)
    logger.info("结构化大纲生成完成")
    return outline_data


async def _save_outline_and_update_message(
    db: Session,
    outline_generator: OutlineGenerator,
    outline_data: Dict[str, Any],
    user_id: str,
    task_id: str,
    session_id: str,
    assistant_message_id: str
) -> str:
    """保存大纲并更新消息状态"""
    # 保存到数据库
    logger.info("开始保存大纲到数据库")
    saved_outline = outline_generator.save_outline_to_db(
        outline_data=outline_data,
        db_session=db,
        user_id=user_id
    )
    outline_id = saved_outline["id"]
    logger.info(f"大纲保存完成 [outline_id={outline_id}]")
    
    # 更新助手消息
    result_data = {"outline_id": outline_id}
    json_result = json.dumps(result_data)
    
    assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
    if assistant_message:
        # 更新之前创建的助手消息
        assistant_message.content_type = ContentType.OUTLINE
        assistant_message.outline_id = outline_id
        assistant_message.task_status = TaskStatus.COMPLETED.value
        assistant_message.task_result = json_result
        assistant_message.content = ""
        logger.info(f"更新助手消息为完成状态 [message_id={assistant_message_id}]")
    else:
        # 如果之前的消息不存在，创建新消息
        assistant_message = ChatMessage(
            message_id=shortuuid.uuid(),
            session_id=session_id,
            role="assistant",
            content_type=ContentType.OUTLINE,
            content="",
            outline_id=outline_id,
            task_status=TaskStatus.COMPLETED.value,
            task_id=task_id,
            task_result=json_result
        )
        db.add(assistant_message)
        logger.info("创建新的助手消息")
    
    # 更新任务状态为完成
    task = db.query(Task).filter(Task.id == task_id).first()
    task.status = TaskStatus.COMPLETED
    task.result = result_data
    db.commit()
    
    return outline_id


async def _update_task_status(db: Session, task_id: str, assistant_message_id: str, status_message: str, task_type: TaskType = None) -> bool:
    """更新任务和助手消息状态为处理中"""
    # 更新任务状态
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logger.error(f"任务不存在 [task_id={task_id}]")
        return False
    
    task.status = TaskStatus.PROCESSING
    task_type_str = task_type.name if task_type else task.type.name
    logger.info(f"更新任务状态为处理中 [task_id={task_id}, type={task_type_str}]")
    
    # 更新助手消息状态
    assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
    if assistant_message:
        assistant_message.task_status = TaskStatus.PROCESSING.value
        assistant_message.task_id = task_id
        assistant_message.content = status_message
        logger.info(f"更新助手消息状态为处理中 [message_id={assistant_message_id}]")
    
    db.commit()
    return True


async def _handle_generation_error(db: Session, task_id: str, assistant_message_id: str, error: Exception, start_time: float, task_name: str = "任务") -> None:
    """处理生成过程中的异常"""
    # 更新任务状态为失败
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = TaskStatus.FAILED
        task.error = str(error)
    
    # 更新助手消息状态为失败
    assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
    if assistant_message:
        assistant_message.task_status = TaskStatus.FAILED.value
        assistant_message.content = f"生成失败: {str(error)}"
    
    db.commit()
    
    # 记录任务失败和耗时
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.error(f"{task_name}任务失败 [task_id={task_id}, elapsed_time={elapsed_time:.2f}s]: {str(error)}")


def _log_task_completion(task_id: str, start_time: float, task_name: str = "任务") -> None:
    """记录任务完成和耗时"""
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"{task_name}任务完成 [task_id={task_id}, elapsed_time={elapsed_time:.2f}s]")


def _log_task_error(task_id: str, error: Exception, start_time: float, task_name: str = "任务") -> None:
    """记录任务整体流程错误和耗时"""
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.error(f"处理{task_name}任务时出错 [task_id={task_id}, elapsed_time={elapsed_time:.2f}s]: {str(error)}")


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
        process: 进度百分比 (0-100)
        process_detail_info: 进度详情描述
        log: 日志
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
        "error": task.error,
        "process": task.process or 0,
        "process_detail_info": task.process_detail_info or "",
        "log": task.log or ""
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
    
    try:
        # 获取所有现有段落
        existing_paragraphs = db.query(SubParagraph).filter(
            SubParagraph.outline_id == outline_id
        ).all()
        
        # 将现有段落转换为字典，以ID为键
        existing_dict = {p.id: p for p in existing_paragraphs}
        
        # 收集新结构中的所有段落ID
        new_paragraph_ids = set()
        
        # 验证段落层级和父子关系
        def validate_paragraph_structure(paragraphs, parent_id=None, level=None):
            for para_data in paragraphs:
                paragraph_id = para_data.id
                
                # 如果是现有段落，验证层级和父子关系是否改变
                if paragraph_id is not None and paragraph_id in existing_dict:
                    existing_para = existing_dict[paragraph_id]
                    
                    # 验证段落层级是否改变
                    if existing_para.level != para_data.level:
                        raise ValueError(f"段落 {paragraph_id} 的层级不允许改变")
                    
                    # 验证父子关系是否改变（除了同级移动）
                    if existing_para.parent_id != parent_id:
                        # 如果原父节点和新父节点都存在，检查它们是否在同一层级
                        if existing_para.parent_id is not None and parent_id is not None:
                            old_parent = existing_dict.get(existing_para.parent_id)
                            new_parent = existing_dict.get(parent_id)
                            if old_parent and new_parent and old_parent.level != new_parent.level:
                                raise ValueError(f"段落 {paragraph_id} 只能在同一层级内移动")
                
                # 递归验证子段落
                if para_data.children:
                    validate_paragraph_structure(para_data.children, paragraph_id, para_data.level + 1)
        
        # 首先验证整个段落结构
        validate_paragraph_structure(request.sub_paragraphs)
        
        # 递归更新段落
        def update_paragraphs_recursively(paragraphs, parent_id=None):
            result_ids = []
            
            for index, para_data in enumerate(paragraphs):
                paragraph_id = para_data.id
                
                # 如果有ID且存在于现有段落中，则更新
                if paragraph_id is not None and paragraph_id in existing_dict:
                    paragraph = existing_dict[paragraph_id]
                    
                    # 更新基本信息
                    paragraph.title = para_data.title
                    paragraph.description = para_data.description
                    paragraph.reference_status = ReferenceStatus(para_data.reference_status)
                    paragraph.parent_id = parent_id
                    paragraph.sort_index = index  # 使用索引作为排序依据
                    
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
                                db.flush()
                                
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
                        parent_id=parent_id,
                        sort_index=index  # 使用索引作为排序依据
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
                            db.flush()
                            
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
                    child_ids = update_paragraphs_recursively(para_data.children, paragraph.id if paragraph_id is None else paragraph_id)
            
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
    
    except ValueError as ve:
        db.rollback()
        return APIResponse.error(message=str(ve))
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
    if outline.user_id is not None and outline.user_id != current_user.user_id and current_user.admin != UserRole.SYS_ADMIN:
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
    
    # 确保每个列表都是按 sort_index 排序的
    for parent_id in siblings_dict:
        siblings_dict[parent_id].sort(
            key=lambda para_id: (
                paragraphs_dict[para_id].sort_index if paragraphs_dict[para_id].sort_index is not None else paragraphs_dict[para_id].id
            )
        )
    
    # 递归构建段落树
    def build_paragraph_tree(parent_id=None):
        result = []
        children_ids = siblings_dict.get(parent_id, [])
        
        # 对子段落按 sort_index 排序
        children_ids.sort(
            key=lambda para_id: (
                paragraphs_dict[para_id].sort_index if paragraphs_dict[para_id].sort_index is not None else paragraphs_dict[para_id].id
            )
        )
        
        for para_id in children_ids:
            paragraph = paragraphs_dict[para_id]
            # 使用 build_paragraph_response 构建数据
            data = build_paragraph_response(
                paragraph, 
                siblings_dict, 
                paragraphs_dict, 
                {}, 
                ReferenceStatus
            )
            
            # 递归处理子段落
            children = build_paragraph_tree(para_id)
            if children:
                data["children"] = children
            
            result.append(data)
        
        return result
    
    # 构建响应
    response_data = {
        "id": outline.id,
        "title": outline.title,
        "markdown_content": outline.markdown_content,
        "sub_paragraphs": build_paragraph_tree()
    }
    
    return APIResponse.success(message="获取大纲详情成功", data=response_data)


class GenerateFullContentRequest(BaseModel):
    outline_id: Optional[str] = Field(None, description="大纲ID，如果为空则直接生成全文")
    session_id: Optional[str] = Field(None, description="会话ID")
    prompt: Optional[str] = Field(None, description="直接生成模式下的写作提示")
    file_ids: Optional[List[str]] = Field(None, description="直接生成模式下的参考文件ID列表")
    files: Optional[List[Dict[str, Any]]] = Field(default=[], description="直接生成模式下的参考文件内容")
    at_file_ids: Optional[List[str]] = Field(default=[], description="@的文件ID列表")
    atfiles: Optional[List[Dict[str, Any]]] = Field(default=[], description="@的文件内容")
    model_name: Optional[str] = Field(None, description="模型")
    web_search: Optional[bool] = Field(False, description="是否进行网页搜索")

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
        doc_id: 文档ID
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

    doc_id = f"doc-{shortuuid.uuid()}"[:22]
    document = Document(
        doc_id=doc_id,
        title="正在生成...",
        content="",
        user_id=current_user.user_id
    )
    db.add(document)
    
    # 创建用户消息
    message_id = f"msg-{shortuuid.uuid()}"[:22]
    chat_message = ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role="user",
        content=message_content,
        content_type=ContentType.TEXT,
        meta=json.dumps({
            "files": request.files,
            "atfiles": request.atfiles
        }),
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
        task_status=TaskStatus.PENDING.value,
        document_id=doc_id
    )
    db.add(assistant_message)

    at_file_ids = []
    if request.at_file_ids:
        at_files = db.query(RagFile).filter(
            RagFile.file_id.in_(request.at_file_ids),
            RagFile.status == RagFileStatus.DONE,
            RagFile.is_deleted == False
        ).all()
        for at_file in at_files:
            at_file_ids.append(at_file.kb_file_id)
    
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
            "file_ids": request.file_ids or [],
            "doc_id": doc_id,
            "web_search": request.web_search,
            "at_file_ids": request.at_file_ids
        }
    )
    db.add(task)
    db.commit()
    
    # 记录任务到运行集合中
    with task_lock:
        running_tasks.add(task_id)
    
    # 启动异步任务
    executor.submit(run_content_task,
        task_id=task_id,
        outline_id=request.outline_id,
        prompt=request.prompt,
        file_ids=request.file_ids or [],
        session_id=session_id,
        message_id=message_id,
        assistant_message_id=assistant_message_id,
        readable_model_name=request.model_name,
        doc_id=doc_id,
        web_search=request.web_search,
        at_file_ids=at_file_ids
    )
    
    # 立即返回响应，不等待异步任务完成
    return APIResponse.success(message="全文生成任务已创建", data={
        "task_id": task_id,
        "session_id": session_id
    })


async def process_content_generation(task_id: str, outline_id: Optional[str], prompt: Optional[str], file_ids: List[str], session_id: str, message_id: str, assistant_message_id: str, readable_model_name: Optional[str] = None, doc_id: str = None, web_search: bool = False, at_file_ids: Optional[List[str]] = None):
    """
    异步处理内容生成任务
    
    Args:
        task_id: 任务ID
        outline_id: 大纲ID（可选）
        prompt: 写作提示（可选，直接生成模式下必须）
        file_ids: 参考文件ID列表
        session_id: 会话ID
        message_id: 用户消息ID
        assistant_message_id: 助手消息ID
        readable_model_name: 模型名称（可选）
        doc_id: 文档ID
    """
    # 创建新的数据库会话
    db = next(get_db())
    start_time = time.time()
    
    try:
        logger.info(f"开始处理内容生成任务 [task_id={task_id}] [doc_id={doc_id}]")
        
        # 更新任务和消息状态
        if not await _update_task_status(db, task_id, assistant_message_id, "正在生成内容，请稍候...", TaskType.GENERATE_CONTENT):
            return
        
        # 获取用户ID和参考文件内容
        user_id, file_contents = await _prepare_generation_resources(db, task_id, file_ids)
        
        # 初始化大纲生成器
        logger.info(f"初始化写作生成器 [model={readable_model_name or 'default'}]")
        outline_generator = OutlineGenerator(readable_model_name=readable_model_name, use_web=web_search)
        
        try:
            kb_ids = []
            # 查询系统知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM, RagKnowledgeBase.is_deleted == False).first()

            if kb:
                kb_ids.append(kb.kb_id)
            # 查询用户共享知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER_SHARED, RagKnowledgeBase.is_deleted == False).first()
            if kb:
                kb_ids.append(kb.kb_id)
            # 查询用户私有知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, RagKnowledgeBase.user_id == user_id, RagKnowledgeBase.is_deleted == False).first()
            if kb:
                kb_ids.append(kb.kb_id)
            # 查询所有部门知识库
            department_kbs = db.query(RagKnowledgeBase).filter(
                RagKnowledgeBase.kb_type == RagKnowledgeBaseType.DEPARTMENT,
                RagKnowledgeBase.is_deleted == False).all()
            if department_kbs:
                kb_ids.extend([kb.kb_id for kb in department_kbs])

            # 生成内容
            full_content = await _generate_content(outline_generator, outline_id, prompt, file_contents, db, user_id, kb_ids, session_id, doc_id, at_file_ids)
            
            # 保存文档并更新消息
            document_id = await _save_document_and_update_message(
                db, full_content, user_id, task_id, session_id, message_id, assistant_message_id, doc_id
            )
            
            # 记录任务完成和耗时
            _log_task_completion(task_id, start_time, "全文生成")
            
        except Exception as e:
            # 处理内容生成过程中的异常
            await _handle_generation_error(db, task_id, assistant_message_id, e, start_time, "全文生成")
            
    except Exception as e:
        # 处理整体流程中的异常
        _log_task_error(task_id, e, start_time, "全文生成")
    finally:
        db.close()
        logger.info(f"全文生成任务处理结束 [task_id={task_id}]")


async def _prepare_generation_resources(db: Session, task_id: str, file_ids: List[str]) -> Tuple[str, List[str]]:
    """准备生成所需的资源：用户ID和参考文件内容"""
    # 获取用户ID
    task = db.query(Task).filter(Task.id == task_id).first()
    task_params = task.params
    user_id = task_params.get("user_id")
    logger.info(f"获取用户ID [user_id={user_id}]")
    
    # 获取文件内容
    file_contents = []
    per_file_max_length = int(settings.RAG_CHAT_TOTAL_FILE_MAX_LENGTH / (len(file_ids) if len(file_ids) > 0 else 1))
    for file_id in file_ids:
        file = db.query(RagFile).filter(RagFile.file_id == file_id, RagFile.is_deleted == False).first()
        if file and file.content:
            file_contents.append(file.content[:per_file_max_length])
            logger.info(f"加载参考文件内容 [file_id={file_id}]")
    
    return user_id, file_contents


async def _generate_content(
    outline_generator: OutlineGenerator,
    outline_id: Optional[str],
    prompt: Optional[str],
    file_contents: List[str],
    db: Session,
    user_id: Optional[str] = None,
    kb_ids: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    doc_id: Optional[str] = None,
    at_file_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """根据模式生成内容"""
    if outline_id:
        # 基于大纲生成模式
        logger.info(f"开始基于大纲生成全文 [outline_id={outline_id}]")
        
        # 查询会话的第一条用户消息
        first_user_message = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user",
            ChatMessage.is_deleted == False
        ).order_by(ChatMessage.id).first()
        
        # 构建提示词
        user_prompt = first_user_message.content if first_user_message else ""
        logger.info(f"获取到用户第一条消息: {user_prompt}")
        
        full_content = outline_generator.generate_full_content(outline_id, db, user_id, kb_ids, user_prompt, doc_id, at_file_ids)
    else:
        # 直接生成模式
        logger.info("开始直接生成全文")
        full_content = outline_generator.generate_content_directly(prompt, file_contents, user_id, kb_ids, doc_id, at_file_ids)
    
    logger.info("全文生成完成")
    return full_content


async def _save_document_and_update_message(
    db: Session, 
    full_content: Dict[str, Any], 
    user_id: str,
    task_id: str,
    session_id: str,
    message_id: str,
    assistant_message_id: str,
    doc_id: Optional[str] = None
) -> str:
    """保存文档并更新消息状态"""
    title = full_content.get("title", "无标题文档")
    html_content = full_content.get("html", "")
    
    # 检查是否已经有文档ID
    if doc_id:
        # 检查文档是否存在
        document = db.query(Document).filter(Document.doc_id == doc_id).first()
        if document:
            logger.info(f"使用已有文档 [doc_id={doc_id}]")
            # 确保文档属于当前用户
            if document.user_id != user_id:
                logger.warning(f"文档用户ID不匹配 [doc_id={doc_id}, doc_user_id={document.user_id}, current_user_id={user_id}]")
                # 创建新文档
                doc_id = f"doc-{shortuuid.uuid()}"[:22]
                document = Document(
                    doc_id=doc_id,
                    title=title,
                    content=html_content,
                    user_id=user_id
                )
                db.add(document)
                logger.info(f"创建新文档记录 [doc_id={doc_id}]")
        else:
            # 如果传入的doc_id不存在，创建新文档
            document = Document(
                doc_id=doc_id,
                title=title,
                content=html_content,
                user_id=user_id
            )
            db.add(document)
            logger.info(f"使用指定ID创建新文档 [doc_id={doc_id}]")
    else:
        # 创建新文档
        doc_id = f"doc-{shortuuid.uuid()}"[:22]
        document = Document(
            doc_id=doc_id,
            title=title,
            content=html_content,
            user_id=user_id
        )
        db.add(document)
        logger.info(f"创建新文档记录 [doc_id={doc_id}]")
    
    # 更新助手消息
    result_data = {"doc_id": doc_id}
    json_result = json.dumps(result_data)
    
    assistant_message = db.query(ChatMessage).filter(ChatMessage.message_id == assistant_message_id).first()
    if assistant_message:
        # 更新现有消息
        assistant_message.content = ""
        assistant_message.content_type = ContentType.DOCUMENT
        assistant_message.document_id = doc_id
        assistant_message.task_status = TaskStatus.COMPLETED.value
        assistant_message.task_result = json_result
        assistant_message.full_content = json_result
        logger.info(f"更新助手消息为完成状态 [message_id={assistant_message_id}]")
    else:
        # 创建新消息
        ai_message_id = f"msg-{shortuuid.uuid()}"[:22]
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
            task_result=json_result,
            full_content=json_result
        )
        db.add(assistant_message)
        logger.info("创建新的助手消息")
    
    # 更新任务状态为完成
    task = db.query(Task).filter(Task.id == task_id).first()
    task.status = TaskStatus.COMPLETED
    task.result = result_data
    db.commit()
    
    return doc_id


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
    sort_order: Optional[int] = Field(0, description="排序顺序，值越小排序越靠前")

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        
        # 优先按sort_order字段排序，然后按创建时间降序排序
        templates = query.order_by(WritingTemplate.sort_order, WritingTemplate.created_at.desc()) \
                        .offset((page - 1) * page_size) \
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
                    "sort_order": template.sort_order,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建模板
    
    Args:
        template: 模板信息
        
    Returns:
        id: 模板ID
    """
    try:
        # 检查用户权限
        if current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="只有系统管理员才能创建模板")
            
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
            default_outline_ids=template.outline_ids,
            sort_order=template.sort_order
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
    从Word文档或Markdown文件解析大纲结构
    
    Args:
        file: Word文档文件(.doc或.docx)或Markdown文件(.md)
        readable_model_name: 模型（可选）
    Returns:
        id: 大纲ID
        title: 大纲标题
        sub_paragraphs: 段落列表
    """
    file_path = None
    
    try:
        # 检查文件类型
        file_extension = os.path.splitext(file.filename.lower())[1]
        if file_extension not in ['.doc', '.docx', '.md']:
            return APIResponse.error(message="仅支持.doc、.docx格式的Word文档或.md格式的Markdown文件")
        
        # 保存上传的文件
        file_path = f"/tmp/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 根据文件类型选择解析器
        if file_extension == '.md':
            parser = MarkdownParser()
        else:
            parser = DocxParser()
            
        # 解析文档
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
    global_search: Optional[bool] = False,
    username: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if global_search and current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="无权查询全局会话")

        # 构建基础查询
        query = db.query(ChatSession).filter(
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.is_deleted == False
        )
        
        if not global_search:
            query = query.filter(ChatSession.user_id == current_user.user_id)

        if username:
            # 查询用户信息
            users = db.query(User).filter(User.username.contains(username)).all()
            if not users:
                return APIResponse.error(message="用户不存在")
            user_ids = [user.user_id for user in users]
            query = query.filter(ChatSession.user_id.in_(user_ids))

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

            # 查询用户信息
            user = db.query(User).filter(User.user_id == session.user_id).first()
            
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
                "user_id": session.user_id,
                "username": user.username if user else None,
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
            # ChatSession.user_id == current_user.user_id,
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.is_deleted == False
        ).first()
        if not session:
            return APIResponse.error(message="会话不存在")

        if session.user_id != current_user.user_id and current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="无权访问")
        
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


class StreamDocContentRequest(BaseModel):
    doc_id: str = Field(..., description="文档ID")
    task_id: str = Field(..., description="任务ID")

@router.get("/doc/{doc_id}",summary="流式获取doc的内容")
async def stream_doc_content(
    doc_id: str,
    request: StreamDocContentRequest = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    流式获取文档内容
    
    Args:
        doc_id: 文档ID
        request: 请求体，包含任务ID
        
    Returns:
        文档内容的流式响应，格式与OpenAI Chat Stream兼容
    """
    try:
        # 检查文档是否存在
        document = db.query(Document).filter(
            Document.doc_id == doc_id
        ).first()
        
        if not document:
            return APIResponse.error(message=f"未找到ID为{doc_id}的文档")
        
        # 检查用户权限
        if document.user_id != current_user.user_id:
            return APIResponse.error(message="您没有权限查看该文档")
        
        # 获取任务状态
        task = db.query(Task).filter(
            Task.id == request.task_id
        ).first()
        
        if not task:
            return APIResponse.error(message=f"未找到ID为{request.task_id}的任务")
        
        # 检查任务类型是否是生成内容
        if task.type != TaskType.GENERATE_CONTENT:
            return APIResponse.error(message="无效的任务类型")
        
        # 检查任务关联的文档ID是否匹配
        task_params = task.params
        if task_params.get("doc_id") != doc_id:
            return APIResponse.error(message="任务与文档不匹配")
        
        # 记录初始状态
        initial_title = document.title
        initial_content = document.content or ""
        task_id = task.id
        current_task_status = task.status
        
        # 检查是否是恢复的任务（通过进度和进度详情信息判断）
        is_resumed_task = (task.process or 0) >= 40 and "已生成部分内容" in (task.process_detail_info or "")
        
        # 流式响应函数
        async def generate():
            # 创建metadata字典，包含状态信息
            metadata = {
                "doc_id": doc_id,
                "task_id": task_id,
                "title": initial_title,
                "status": current_task_status.value,
                "is_resumed": is_resumed_task
            }
            
            # 发送文档元数据作为系统消息
            chunk = {
                "id": f"docstream-{shortuuid.uuid()}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "doc-stream",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "system",
                            "content": None,
                            "metadata": metadata
                        }
                    }
                ]
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            # 如果任务已完成，直接返回完整内容
            if current_task_status == TaskStatus.COMPLETED:
                chunk = {
                    "id": f"docstream-{shortuuid.uuid()}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "doc-stream",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": initial_content,
                                "status": "completed"
                            }
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 如果任务失败，返回错误信息
            if current_task_status == TaskStatus.FAILED:
                chunk = {
                    "id": f"docstream-{shortuuid.uuid()}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "doc-stream",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": "",
                                "status": "failed",
                                "error": task.error or "生成任务失败"
                            }
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 发送当前的文档内容
            if initial_content:
                chunk = {
                    "id": f"docstream-{shortuuid.uuid()}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "doc-stream",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": initial_content,
                                "status": current_task_status.value
                            }
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            # 如果任务正在处理中，等待更新并流式返回
            if current_task_status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                # 根据任务类型设置等待时间和检查间隔
                # 如果是恢复的任务，需要给予更长的等待时间
                if is_resumed_task:
                    max_wait_time = 300  # 5分钟
                    check_interval = 5   # 5秒钟检查一次
                    initial_wait = 10    # 初始等待10秒钟，等待任务真正启动
                    logger.info(f"检测到恢复的任务 [task_id={task_id}]，等待任务恢复运行...")
                    
                    # 发送初始等待消息
                    chunk = {
                        "id": f"docstream-{shortuuid.uuid()}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "doc-stream",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": "\n\n*任务正在恢复中，请耐心等待...*\n\n",
                                    "status": "processing"
                                }
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    
                    # 初始等待一段时间，让任务有时间启动
                    await asyncio.sleep(initial_wait)
                else:
                    max_wait_time = 120  # 2分钟
                    check_interval = 2   # 2秒钟检查一次
                
                wait_time = 0
                
                # 上次内容的长度，用于检测变化
                last_content_length = len(initial_content)
                
                # 保存最后一次内容更新的时间
                last_update_time = time.time()
                
                while wait_time < max_wait_time:
                    # 等待一段时间
                    await asyncio.sleep(check_interval)
                    wait_time += check_interval
                    
                    # 创建新的数据库会话，避免使用已关闭的会话
                    with Session(db.bind) as new_db:
                        # 重新查询文档和任务
                        current_document = new_db.query(Document).filter(
                            Document.doc_id == doc_id
                        ).first()
                        
                        current_task = new_db.query(Task).filter(
                            Task.id == task_id
                        ).first()
                        
                        if not current_document or not current_task:
                            # 如果找不到文档或任务，退出循环
                            chunk = {
                                "id": f"docstream-{shortuuid.uuid()}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "doc-stream",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": "",
                                            "status": "failed",
                                            "error": "文档或任务不存在"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            break
                        
                        # 如果内容有更新，发送更新的内容
                        current_content = current_document.content or ""
                        if len(current_content) > last_content_length:
                            # 只发送新增的内容
                            new_content = current_content[last_content_length:]
                            chunk = {
                                "id": f"docstream-{shortuuid.uuid()}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "doc-stream",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": new_content,
                                            "status": current_task.status.value
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            last_content_length = len(current_content)
                            last_update_time = time.time()  # 更新最后一次内容更新时间
                        
                        # 检查任务是否已经完成
                        if current_task.status == TaskStatus.COMPLETED:
                            # 如果还有未发送的内容，发送最终内容
                            if len(current_document.content or "") > last_content_length:
                                final_new_content = (current_document.content or "")[last_content_length:]
                                chunk = {
                                    "id": f"docstream-{shortuuid.uuid()}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": "doc-stream",
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "role": "assistant",
                                                "content": final_new_content,
                                                "status": "completed"
                                            }
                                        }
                                    ]
                                }
                                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            
                            # 发送完成状态
                            chunk = {
                                "id": f"docstream-{shortuuid.uuid()}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "doc-stream",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": "",
                                            "status": "completed"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            break
                        elif current_task.status == TaskStatus.FAILED:
                            chunk = {
                                "id": f"docstream-{shortuuid.uuid()}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "doc-stream",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": "",
                                            "status": "failed",
                                            "error": current_task.error or "生成任务失败"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            break
                        
                        # 检查是否长时间没有更新内容（超过30秒），如果是则发送进度信息
                        # 仅针对恢复的任务
                        current_time = time.time()
                        if is_resumed_task and current_time - last_update_time > 30:
                            # 获取当前任务进度
                            progress = current_task.process or 0
                            progress_info = current_task.process_detail_info or "任务处理中..."
                            
                            # 发送进度信息
                            chunk = {
                                "id": f"docstream-{shortuuid.uuid()}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "doc-stream",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": f"\n\n*当前进度: {progress}% - {progress_info}*\n\n",
                                            "status": "processing",
                                            "progress": progress
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            last_update_time = current_time  # 更新最后一次更新时间
                
                # 如果超时退出循环，发送一个超时信息
                if wait_time >= max_wait_time:
                    chunk = {
                        "id": f"docstream-{shortuuid.uuid()}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "doc-stream",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": "\n\n*等待超时，请刷新页面重新获取内容*\n\n",
                                    "status": "timeout"
                                }
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            # 结束流
            yield "data: [DONE]\n\n"
        
        # 返回流式响应
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
                "X-Document-ID": doc_id,
                "X-Task-ID": request.task_id
            }
        )
        
    except Exception as e:
        logger.error(f"流式获取文档内容失败: {str(e)}")
        return APIResponse.error(message=f"获取文档内容失败: {str(e)}")

def refresh_writing_tasks_status():
    """
    刷新写作任务状态，在应用启动时恢复未完成的任务
    1. 查找所有状态为PENDING或PROCESSING的写作任务
    2. 对于创建时间大于一天的任务，直接修改为Failed状态
    3. 对于其他任务，重新启动任务处理
    
    使用数据库作为分布式锁，确保在多实例环境中只有一个实例执行任务恢复
    通过心跳机制和锁的自动续期，确保正在运行的实例不会被新实例打断
    """
    logger.info("开始刷新写作任务状态...")
    db = next(get_db())
    
    # 定义锁ID和过期时间
    lock_name = "writing_tasks_refresh_lock"
    lock_timeout = 300  # 5分钟，单位秒
    heartbeat_interval = 30  # 30秒，单位秒
    instance_id = f"instance-{shortuuid.uuid()}"
    lock_acquired = False
    last_heartbeat = None
    heartbeat_thread = None
    should_stop_heartbeat = False
    
    # 确保running_tasks是集合而不是列表
    global running_tasks
    if not isinstance(running_tasks, set):
        running_tasks = set()
    
    def update_heartbeat():
        """心跳更新线程函数"""
        while not should_stop_heartbeat:
            try:
                with next(get_db()) as heartbeat_db:
                    lock_record = heartbeat_db.query(SystemConfig).filter(
                        SystemConfig.key == f"lock:{lock_name}"
                    ).first()
                    
                    if lock_record:
                        lock_data = json.loads(lock_record.value)
                        if lock_data.get("instance_id") == instance_id:
                            current_time = datetime.now()
                            lock_data["last_heartbeat"] = current_time.isoformat()
                            lock_data["expire_time"] = (current_time + timedelta(seconds=lock_timeout)).isoformat()
                            
                            # 更新正在运行的任务列表，只保存任务ID字符串
                            task_ids = []
                            with task_lock:
                                # 确保只存储字符串ID，不存储Task对象
                                task_ids = [str(task_id) for task_id in running_tasks]
                            lock_data["running_tasks"] = task_ids
                            
                            lock_record.value = json.dumps(lock_data)
                            heartbeat_db.commit()
                            logger.debug(f"更新锁心跳和运行任务列表 [instance_id={instance_id}]")
            except Exception as e:
                logger.error(f"更新锁心跳时出错: {str(e)}")
            
            # 等待下一次心跳
            time.sleep(heartbeat_interval)
    
    try:
        # 尝试获取分布式锁
        try:
            # 获取当前时间和过期时间
            current_time = datetime.now()
            expire_time = current_time + timedelta(seconds=lock_timeout)
            
            # 使用数据库事务和行级锁来确保原子性
            with db.begin():
                # 尝试创建或更新锁记录
                # 首先查询现有锁，使用 FOR UPDATE SKIP LOCKED 来避免死锁
                existing_lock = db.query(SystemConfig).filter(
                    SystemConfig.key == f"lock:{lock_name}"
                ).with_for_update(skip_locked=True).first()
                
                if existing_lock:
                    # 检查锁是否过期
                    lock_data = json.loads(existing_lock.value)
                    lock_expire_time = datetime.fromisoformat(lock_data.get("expire_time"))
                    last_heartbeat_time = datetime.fromisoformat(lock_data.get("last_heartbeat", current_time.isoformat()))
                    
                    # 检查是否有正在运行的任务
                    running_instance_id = lock_data.get("instance_id")
                    if running_instance_id:
                        # 检查是否有该实例正在运行的任务
                        running_tasks_list = db.query(Task).filter(
                            Task.status.in_([TaskStatus.PROCESSING]),
                            Task.type.in_([TaskType.GENERATE_OUTLINE, TaskType.GENERATE_CONTENT])
                        ).all()
                        
                        # 如果存在正在运行的任务，且最后心跳时间在合理范围内，则认为锁仍然有效
                        if running_tasks_list and (current_time - last_heartbeat_time) < timedelta(seconds=heartbeat_interval * 2):
                            logger.info(f"发现实例 {running_instance_id} 有正在运行的任务，且心跳正常，跳过执行")
                            return
                    
                    # 检查心跳是否正常（如果最后心跳时间超过过期时间的一半，认为锁已失效）
                    if current_time > lock_expire_time or (current_time - last_heartbeat_time) > timedelta(seconds=lock_timeout/2):
                        # 锁已过期或心跳异常，可以获取
                        logger.info(f"发现过期的锁，过期时间: {lock_expire_time}，最后心跳: {last_heartbeat_time}，当前时间: {current_time}")
                        existing_lock.value = json.dumps({
                            "instance_id": instance_id,
                            "acquire_time": current_time.isoformat(),
                            "expire_time": expire_time.isoformat(),
                            "last_heartbeat": current_time.isoformat(),
                            "running_tasks": []  # 记录当前实例正在运行的任务ID列表
                        })
                        lock_acquired = True
                    else:
                        # 锁仍有效且心跳正常，不能获取
                        logger.info(f"任务刷新已被实例 {lock_data.get('instance_id')} 锁定，心跳正常，跳过执行")
                        return
                else:
                    # 不存在锁，创建新锁
                    new_lock = SystemConfig(
                        key=f"lock:{lock_name}",
                        value=json.dumps({
                            "instance_id": instance_id,
                            "acquire_time": current_time.isoformat(),
                            "expire_time": expire_time.isoformat(),
                            "last_heartbeat": current_time.isoformat(),
                            "running_tasks": []  # 记录当前实例正在运行的任务ID列表
                        }),
                        description="任务恢复分布式锁"
                    )
                    db.add(new_lock)
                    lock_acquired = True
                
                # 提交事务
                db.commit()
                
                if lock_acquired:
                    logger.info(f"实例 {instance_id} 成功获取任务恢复锁")
                    last_heartbeat = current_time
                    # 启动心跳更新线程
                    heartbeat_thread = threading.Thread(target=update_heartbeat, daemon=True)
                    heartbeat_thread.start()
                
        except Exception as e:
            # 发生错误，回滚事务
            db.rollback()
            logger.error(f"获取任务恢复锁时发生错误: {str(e)}")
            return
        
        # 如果没有获取到锁，直接返回
        if not lock_acquired:
            return
            
        # 查找所有未完成的大纲生成和内容生成任务
        unfinished_tasks = db.query(Task).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING]),
            Task.type.in_([TaskType.GENERATE_OUTLINE, TaskType.GENERATE_CONTENT])
        ).all()
        
        if not unfinished_tasks:
            logger.info("没有未完成的写作任务需要恢复")
            return
        
        logger.info(f"发现 {len(unfinished_tasks)} 个未完成的写作任务，准备处理...")
        
        # 获取当前时间
        current_time = datetime.now()
        
        for task in unfinished_tasks:
            try:
                # 获取任务参数
                params = task.params
                task_id = task.id
                task_type = task.type
                session_id = task.session_id
                
                # 检查任务创建时间是否超过一天
                task_created_time = task.created_at
                time_diff = current_time - task_created_time
                
                # 对于创建时间超过一天的任务，直接标记为失败
                if time_diff.days >= 1:
                    logger.info(f"任务 {task_id} 已创建超过一天，标记为失败")
                    task.status = TaskStatus.FAILED
                    task.error = "任务生成超时，已自动终止"
                    
                    # 更新对应的消息状态
                    assistant_message = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id,
                        ChatMessage.role == "assistant",
                        ChatMessage.task_status.in_([TaskStatus.PENDING.value, TaskStatus.PROCESSING.value])
                    ).order_by(desc(ChatMessage.id)).first()
                    
                    if assistant_message:
                        assistant_message.task_status = TaskStatus.FAILED.value
                        assistant_message.content = "任务生成超时，已自动终止"
                    
                    db.commit()
                    continue
                
                # 清理任务状态相关字段
                task.process = 0
                task.process_detail_info = ""
                task.log = ""
                
                # 查找相关的消息
                assistant_message = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.task_id == task_id
                ).first()
                
                if not assistant_message:
                    # 如果找不到关联的消息，查找会话中最后一条助手消息
                    assistant_message = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id,
                        ChatMessage.role == "assistant",
                        ChatMessage.task_status.in_([TaskStatus.PENDING.value, TaskStatus.PROCESSING.value])
                    ).order_by(desc(ChatMessage.id)).first()
                
                if not assistant_message:
                    # 仍然找不到，跳过此任务
                    logger.warning(f"无法找到任务 {task_id} 的关联消息，跳过恢复")
                    continue
                
                # 对于生成全文任务，清理文档内容
                if task_type == TaskType.GENERATE_CONTENT:
                    doc_id = params.get("doc_id")
                    if doc_id:
                        document = db.query(Document).filter(Document.doc_id == doc_id).first()
                        if document:
                            # 清空文档内容，但保留文档记录
                            document.content = ""
                            document.title = "正在生成..."
                            logger.info(f"清空文档内容 [doc_id={doc_id}]")
                
                # 查找用户消息
                user_message = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id,
                    ChatMessage.role == "user",
                    ChatMessage.message_id == assistant_message.question_id
                ).order_by(ChatMessage.id).first()
                
                if not user_message and task_type == TaskType.GENERATE_CONTENT:
                    # 找不到用户消息，查找会话中的第一条用户消息
                    user_message = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id,
                        ChatMessage.role == "user"
                    ).order_by(ChatMessage.id).first()
                
                # 准备恢复任务参数
                assistant_message_id = assistant_message.message_id
                message_id = user_message.message_id if user_message else None
                
                with task_lock:
                    # 检查任务是否已经在处理中
                    if task_id in running_tasks:
                        logger.info(f"任务 {task_id} 已经在处理中，跳过")
                        continue
                    # 将task_id作为字符串添加到running_tasks集合中
                    running_tasks.add(str(task_id))
                
                # 首先提交当前的数据库更改
                db.commit()
                
                # 根据任务类型恢复任务
                if task_type == TaskType.GENERATE_OUTLINE:
                    # 恢复大纲生成任务
                    prompt = params.get("prompt", "")
                    file_ids = params.get("file_ids", [])
                    model_name = params.get("model_name")
                    web_search = params.get("web_search", False)
                    at_file_ids = params.get("at_file_ids", [])
                    
                    # 在线程池中启动任务
                    logger.info(f"恢复大纲生成任务: {task_id}")
                    executor.submit(run_outline_task, 
                        task_id=task_id,
                        prompt=prompt,
                        file_ids=file_ids,
                        session_id=session_id,
                        assistant_message_id=assistant_message_id,
                        readable_model_name=model_name,
                        web_search=web_search,
                        at_file_ids=at_file_ids
                    )
                
                elif task_type == TaskType.GENERATE_CONTENT:
                    # 恢复内容生成任务
                    outline_id = params.get("outline_id")
                    prompt = params.get("prompt")
                    file_ids = params.get("file_ids", [])
                    doc_id = params.get("doc_id")
                    model_name = params.get("model_name")
                    web_search = params.get("web_search", False)
                    at_file_ids = params.get("at_file_ids", [])
                    # 在线程池中启动任务
                    logger.info(f"恢复内容生成任务: {task_id}")
                    executor.submit(run_content_task,
                        task_id=task_id,
                        outline_id=outline_id,
                        prompt=prompt,
                        file_ids=file_ids,
                        session_id=session_id,
                        message_id=message_id,
                        assistant_message_id=assistant_message_id,
                        readable_model_name=model_name,
                        doc_id=doc_id,
                        web_search=web_search,
                        at_file_ids=at_file_ids
                    )
            
            except Exception as e:
                logger.error(f"恢复任务 {task.id} 时出错: {str(e)}")
                # 移除任务ID
                with task_lock:
                    if task.id in running_tasks:
                        running_tasks.remove(task.id)
        
        logger.info("写作任务状态刷新完成")
    except Exception as e:
        logger.error(f"刷新写作任务状态时出错: {str(e)}")
    finally:
        # 停止心跳更新线程
        if heartbeat_thread and heartbeat_thread.is_alive():
            should_stop_heartbeat = True
            heartbeat_thread.join(timeout=5)
        
        # 释放锁 - 仅当我们获取了锁时才需要释放
        if lock_acquired:
            try:
                # 获取锁记录
                lock_record = db.query(SystemConfig).filter(
                    SystemConfig.key == f"lock:{lock_name}"
                ).first()
                
                if lock_record:
                    # 解析值
                    lock_data = json.loads(lock_record.value)
                    # 确保是我们获取的锁
                    if lock_data.get("instance_id") == instance_id:
                        # 设置过期时间为当前时间，表示释放锁
                        lock_data["expire_time"] = datetime.now().isoformat()
                        lock_record.value = json.dumps(lock_data)
                        logger.info(f"实例 {instance_id} 释放任务恢复锁")
                        db.commit()
            except Exception as e:
                logger.error(f"释放任务恢复锁时出错: {str(e)}")
        
        db.close()

# 用于启动大纲生成任务的函数
def run_outline_task(task_id, prompt, file_ids, session_id, assistant_message_id, readable_model_name=None, web_search=False, at_file_ids=None):
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 在新的事件循环中运行异步任务
        loop.run_until_complete(process_outline_generation(
            task_id=task_id,
            prompt=prompt,
            file_ids=file_ids,
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            readable_model_name=readable_model_name,
            web_search=web_search,
            at_file_ids=at_file_ids
        ))
        
        loop.close()
    finally:
        # 任务完成后从运行集合中移除
        with task_lock:
            if task_id in running_tasks:
                running_tasks.remove(task_id)

# 用于启动内容生成任务的函数
def run_content_task(task_id, outline_id, prompt, file_ids, session_id, message_id, assistant_message_id, readable_model_name=None, doc_id=None, web_search=False, at_file_ids=None):
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 在新的事件循环中运行异步任务
        loop.run_until_complete(process_content_generation(
            task_id=task_id,
            outline_id=outline_id,
            prompt=prompt,
            file_ids=file_ids,
            session_id=session_id,
            message_id=message_id,
            assistant_message_id=assistant_message_id,
            readable_model_name=readable_model_name,
            doc_id=doc_id,
            web_search=web_search,
            at_file_ids=at_file_ids
        ))
        
        loop.close()
    finally:
        # 任务完成后从运行集合中移除
        with task_lock:
            if task_id in running_tasks:
                running_tasks.remove(task_id)

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str = Path(..., description="模板ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除模板
    
    Args:
        template_id: 模板ID
        
    Returns:
        success: 是否删除成功
    """
    try:
        # 检查用户权限
        if current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="只有系统管理员才能删除模板")
            
        # 查找模板
        template = db.query(WritingTemplate).filter(WritingTemplate.id == template_id).first()
        if not template:
            return APIResponse.error(message=f"未找到ID为{template_id}的模板")
            
        # 检查是否是默认模板
        if template.is_default:
            return APIResponse.error(message="不能删除默认模板")
            
        # 删除模板
        db.delete(template)
        db.commit()
        
        return APIResponse.success(message="删除模板成功")
    except Exception as e:
        db.rollback()
        logger.error(f"删除模板失败: {str(e)}")
        return APIResponse.error(message=f"删除模板失败: {str(e)}")

class TemplateUpdate(TemplateBase):
    id: str = Field(..., description="模板ID")

@router.put("/templates/{template_id}")
async def update_template(
    template_id: str = Path(..., description="模板ID"),
    template: TemplateUpdate = Body(..., description="模板信息"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    全量更新模板
    
    Args:
        template_id: 模板ID
        template: 模板信息
        
    Returns:
        success: 是否更新成功
    """
    try:
        # 检查用户权限
        if current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="只有系统管理员才能更新模板")
            
        # 确保路径参数和请求体中的ID一致
        if template_id != template.id:
            return APIResponse.error(message="路径参数与请求体中的模板ID不一致")
            
        # 查找模板
        existing_template = db.query(WritingTemplate).filter(WritingTemplate.id == template_id).first()
        if not existing_template:
            return APIResponse.error(message=f"未找到ID为{template_id}的模板")
            
        # 检查是否是默认模板
        if existing_template.is_default and not template.is_default:
            return APIResponse.error(message="不能将默认模板改为非默认模板")
            
        # 更新模板字段
        existing_template.show_name = template.show_name
        existing_template.value = template.value
        existing_template.description = template.description
        existing_template.has_steps = template.has_steps
        existing_template.background_url = template.background_url
        existing_template.template_type = template.template_type
        existing_template.variables = template.variables
        existing_template.default_outline_ids = template.outline_ids
        existing_template.sort_order = template.sort_order
        
        # 保存更改
        db.commit()
        
        return APIResponse.success(message="更新模板成功")
    except Exception as e:
        db.rollback()
        logger.error(f"更新模板失败: {str(e)}")
        return APIResponse.error(message=f"更新模板失败: {str(e)}")

class OutlineListRequest(BaseModel):
    page: int = Field(1, description="页码")
    page_size: int = Field(10, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")

@router.get("/outlines")
async def get_outlines(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取大纲列表
    
    Args:
        page: 页码
        page_size: 每页数量
        keyword: 搜索关键词（可选）
        
    Returns:
        outlines: 大纲列表
        total: 总数
        page: 当前页码
        page_size: 每页数量
    """
    try:
        # 构建基础查询
        query = db.query(Outline).filter(
            Outline.user_id == current_user.user_id
        )
        
        # 如果有搜索关键词，添加标题搜索条件
        if keyword:
            query = query.filter(Outline.title.ilike(f"%{keyword}%"))
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        outlines = query.order_by(desc(Outline.created_at)) \
                       .offset((page - 1) * page_size) \
                       .limit(page_size) \
                       .all()
        
        # 获取每个大纲的段落数量
        outline_data = []
        for outline in outlines:
            # 获取段落数量
            paragraph_count = db.query(SubParagraph).filter(
                SubParagraph.outline_id == outline.id
            ).count()
            
            # 获取最后更新时间
            last_updated = db.query(SubParagraph).filter(
                SubParagraph.outline_id == outline.id
            ).order_by(desc(SubParagraph.updated_at)).first()
            
            outline_data.append({
                "id": outline.id,
                "title": outline.title,
                "paragraph_count": paragraph_count,
                "created_at": outline.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": last_updated.updated_at.strftime("%Y-%m-%d %H:%M:%S") if last_updated else outline.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "reference_status": outline.reference_status
            })
        
        return APIResponse.success(message="获取大纲列表成功", data={
            "outlines": outline_data,
            "total": total,
            "page": page,
            "page_size": page_size
        })
        
    except Exception as e:
        logger.error(f"获取大纲列表失败: {str(e)}")
        return APIResponse.error(message=f"获取大纲列表失败: {str(e)}")

class UpdateTemplateSortOrderRequest(BaseModel):
    template_ids: List[str] = Field(..., description="模板ID列表，按照期望的排序顺序排列")

@router.post("/templates/sort")
async def update_template_sort_order(
    request: UpdateTemplateSortOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新模板排序顺序
    
    Args:
        template_ids: 模板ID列表，按照期望的排序顺序排列
        
    Returns:
        success: 是否更新成功
    """
    try:
        # 检查用户权限
        if current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="只有系统管理员才能更新模板排序")
            
        # 验证所有模板ID是否存在
        template_ids = request.template_ids
        templates = db.query(WritingTemplate).filter(WritingTemplate.id.in_(template_ids)).all()
        if len(templates) != len(template_ids):
            found_ids = {template.id for template in templates}
            missing_ids = [template_id for template_id in template_ids if template_id not in found_ids]
            return APIResponse.error(message=f"无法找到以下模板ID: {', '.join(missing_ids)}")
        
        # 更新模板排序
        for index, template_id in enumerate(template_ids):
            db.query(WritingTemplate).filter(WritingTemplate.id == template_id).update(
                {"sort_order": index}, synchronize_session=False
            )
        
        # 提交更改
        db.commit()
        
        return APIResponse.success(message="更新模板排序成功")
    except Exception as e:
        db.rollback()
        logger.error(f"更新模板排序失败: {str(e)}")
        return APIResponse.error(message=f"更新模板排序失败: {str(e)}")
