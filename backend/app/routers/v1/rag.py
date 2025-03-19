import json
import logging
import shortuuid
from pathlib import Path as PathLib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, UploadFile as FastAPIUploadFile
from fastapi.params import Body, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.chat import ChatMessage, ChatSession, ChatSessionType
from app.models.rag import RagFile, RagFileStatus, RagKnowledgeBase, RagKnowledgeBaseType
from app.models.user import User, UserRole
from app.models.chat import ChatSession, ChatMessage, ChatSessionType
from app.rag.parser import convert_doc_to_docx, get_parser, get_file_format
from app.rag.rag_api_async import rag_api_async
from app.rag.kb import ensure_user_knowledge_base, get_department_kb, get_department_kbs, get_knowledge_base, get_system_kb, get_user_kb, get_user_shared_kb, has_permission_to_file, has_permission_to_kb
from app.rag.department import get_departments
from app.schemas.response import APIResponse, PaginationData, PaginationResponse
from app.models.task import Task, TaskStatus
from app.models.document import Document
from app.models.department import Department, UserDepartment
import re
import hashlib

logger = logging.getLogger("app")

router = APIRouter()

class FilesResponse(PaginationResponse):
    data: List[Dict[str, Any]]

class ChatRequest(BaseModel):
    question: str = Field(description="问题内容")
    model_name: Optional[str] = Field(default="deepseek-v3", description="模型名称")
    session_id: str = Field(description="会话ID")
    web_search: Optional[bool] = Field(default=False, description="是否使用web搜索")
    file_ids: Optional[List[str]] = Field(default=[], description="关联的文件ID列表")
    files: Optional[List[Dict[str, Any]]] = Field(default=[], description="关联的文件内容")
    stream: Optional[bool] = Field(default=True, description="是否使用流式返回")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "这是一个问题",
                "model_name": "deepseek-v3",
                "session_id": "chat-1234567890",
                "web_search": False,
                "file_ids": ["file-1234567890", "file-1234567891"],
                "files": [],
                "stream": True
            }
        }

class FileUploadRequest(BaseModel):
    files: List[str]

class DeleteFilesRequest(BaseModel):
    file_ids: List[str] = Field(..., description="要删除的文件ID列表")

@router.post("/files", summary="知识库文件上传")
async def upload_files(
    category: str = Query(..., description="知识库类别", example="system", enum=["system", "user", "user_shared", "department"]),
    department_id: Optional[str] = Query(None, description="部门ID", example="dept-123"),
    files: List[FastAPIUploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        upload_dir = PathLib(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True) # 确保上传目录存在

        if category == "system" and not current_user.admin == UserRole.SYS_ADMIN:
            return APIResponse.error(message="没有权限上传系统知识库")
        if category == "department":
            if not current_user.admin == UserRole.DEPT_ADMIN:
                return APIResponse.error(message="没有权限上传部门知识库")
            if not department_id:
                return APIResponse.error(message="部门ID不能为空")
            if not db.query(UserDepartment).filter(UserDepartment.department_id == department_id, 
                                                   UserDepartment.user_id == current_user.user_id).first():
                return APIResponse.error(message="没有权限上传部门知识库")

        await ensure_user_knowledge_base(current_user, db)

        kb_id = get_knowledge_base(current_user, category, department_id, db)
        if not kb_id:
            return APIResponse.error(message="知识库不存在")

        existing_files = []
        new_files = []
        for file in files:
            file_id = f"file-{shortuuid.uuid()}"
            file_location = upload_dir / f"{file_id}_{file.filename}" # 文件存储路径
            file_name = file.filename
            # 保存文件到磁盘
            try:
                contents = await file.read()
                with open(file_location, "wb") as f:
                    f.write(contents)
                
                # 计算文件的哈希值
                file_hash = hashlib.sha256(contents).hexdigest()
                # 查询文件是否存在
                existing_file = db.query(RagFile).filter(RagFile.hash == file_hash, RagFile.is_deleted == False).first()
                if existing_file:
                    logger.warning(f"文件 {file.filename} 已存在, 跳过上传")
                    existing_files.append({
                        "file_id": existing_file.file_id,
                        "file_name": existing_file.file_name,
                        "size": existing_file.file_size,
                        "content_type": existing_file.file_ext,
                        "path": existing_file.file_path,
                        "hash": existing_file.hash
                    })
                    continue

                file_format = get_file_format(str(file_location))
                if file_format == "doc":
                    docx_file_location = await convert_doc_to_docx(str(file_location))
                    file_location = docx_file_location
                    file_format = "docx"
                    file_name = file_name.replace(".doc", ".docx")
                new_files.append({
                    "file_id": file_id,
                    "file_name": file_name,
                    "size": len(contents),
                    "content_type": file_format,
                    "path": str(file_location),
                    "hash": file_hash
                })
            except Exception as e:
                logger.error(f"上传文件 {file.filename} 时发生错误: {str(e)}")
                return APIResponse.error(message=f"上传文件 {file.filename} 时发生错误: {str(e)}")
            finally:
                await file.close()
        
            db_file = RagFile(
                file_id=file_id,
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.name_to_type(category),
                user_id=current_user.user_id,
                file_name=file_name,
                file_size=len(contents),
                file_ext=file_format, 
                file_path=str(file_location),
                status=RagFileStatus.LOCAL_SAVED,
                summary_small='',
                summary_medium='',
                summary_large='',
                content='',
                meta='',
                hash=file_hash  # 保存哈希值到数据库
            )
        
            db.add(db_file)
            db.commit() 

        return APIResponse.success(
            message=f"文件上传成功, 正在解析中。",
            data={
                "new_files": new_files,
                "existing_files": existing_files
            }
        )
    except Exception as e:
        logger.error(f"上传文件时发生异常: {str(e)}")
        return APIResponse.error(message=f"上传失败: {str(e)}")

@router.get("/files", summary="获取知识库文件列表")
async def get_files(
    category: str = Query(..., description="知识库类别", example="system", enum=["system", "user", "user_shared", "user_all", "department", "department_all", "all_shared"]),
    department_id: Optional[str] = Query(None, description="部门ID", example="dept-123"),
    page: Optional[int] = Query(default=1, ge=1, description="页码", example=1),
    page_size: Optional[int] = Query(default=10, ge=1, description="每页数量", example=10),
    current_user: User = Depends(get_current_user),
    file_name: Optional[str] = Query(None, description="搜索关键词", example="四川"),
    db: Session = Depends(get_db)
):
    try:
        await ensure_user_knowledge_base(current_user, db)

        kb_ids = set()
        dept_map = {}
        kb_depts = {}
        if category == "system":
            kb_ids.add(get_system_kb(db))
        elif category == "user":
            kb_ids.add(get_user_kb(current_user, db))
        elif category == "user_shared":
            kb_ids.add(get_user_shared_kb(db))
        elif category == "user_all":
            kb_ids.add(get_user_kb(current_user, db))
            kb_ids.add(get_user_shared_kb(db))
        elif category == "department":
            kb_ids.add(get_department_kb(department_id, db))
        elif category == "department_all":
            departments = get_departments(current_user, db)
            dept_map = {dept.department_id: dept for dept in departments}
            dept_kb_ids, kb_dept_map = get_department_kbs([dept.department_id for dept in departments], db)
            kb_ids.update(dept_kb_ids)
            kb_depts = {kb_id: dept_map[department_id] for kb_id, department_id in kb_dept_map.items()}
        elif category == "all_shared":
            kb_ids.add(get_system_kb(db))
            kb_ids.add(get_user_shared_kb(db))
            kb_ids.add(get_user_kb(current_user, db))
            departments = get_departments(current_user, db)
            dept_map = {dept.department_id: dept for dept in departments}
            dept_kb_ids, kb_dept_map = get_department_kbs([dept.department_id for dept in departments], db)
            kb_ids.update(dept_kb_ids)
            kb_depts = {kb_id: dept_map[department_id] for kb_id, department_id in kb_dept_map.items()}
        else:
            raise ValueError(f"不支持的知识库类别: {category}")

        query_filter = db.query(RagFile).filter(RagFile.kb_id.in_(kb_ids), RagFile.is_deleted == False)
        
        # 文件名搜索
        if file_name:
            query_list = re.split(r'[,\s、]+', file_name)
            for term in query_list:
                query_filter = query_filter.filter(RagFile.file_name.contains(term))
        
        total = query_filter.count()
        total_pages = (total + page_size - 1) // page_size
        files = query_filter.order_by(RagFile.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return APIResponse.success(
            message="获取知识库文件列表成功",
            data=PaginationData(
                list=[{
                    "kb_id": file.kb_id,
                    "kb_type": RagKnowledgeBaseType.type_to_name(file.kb_type),
                    "user_id": file.user_id,
                    "file_id": file.file_id,
                    "file_name": file.file_name,
                    "file_size": file.file_size,
                    "file_words": file.file_words,
                    "department_id": kb_depts[file.kb_id].department_id if file.kb_id in kb_depts else "",
                    "department_name": kb_depts[file.kb_id].name if file.kb_id in kb_depts else "",
                    "status": RagFileStatus.get_status_map()[file.status],
                    "error_message": file.error_message,
                    "created_at": file.created_at
                } for file in files],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
        )
    except Exception as e:
        logger.exception(f"获取知识库文件列表时发生异常: {str(e)}")
        return APIResponse.error(message="获取知识库文件列表失败")

@router.delete("/files", summary="知识库文件删除")
async def delete_files(
    request: DeleteFilesRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not request.file_ids:
        return APIResponse.error(message="文件ID列表不能为空")

    files = db.query(RagFile).filter(RagFile.file_id.in_(request.file_ids), RagFile.is_deleted == False).all()
    if not files:
        return APIResponse.error(message="未找到有效的文件")

    for file in files:
        if not has_permission_to_file(current_user, file.file_id, db):
            return APIResponse.error(message="没有权限删除文件")

    try:
        resp = await rag_api_async.delete_files(kb_id=files[0].kb_id, file_ids=[file.kb_file_id for file in files])
        if resp["code"] != 200:
            logger.error(f"删除RAG知识库文件失败: user_id={current_user.user_id}, kb_id={files[0].kb_id}, file_ids={request.file_ids}, msg={resp['msg']}")
            # return APIResponse.error(message=f"删除文件失败: {resp['msg']}")

        db.query(RagFile).filter(RagFile.file_id.in_(request.file_ids), RagFile.is_deleted == False).update({"is_deleted": True})
        db.commit()
        return APIResponse.success(message="文件删除成功")
    except Exception as e:
        db.rollback()
        logger.error(f"删除文件事务失败: {str(e)}")
        return APIResponse.error(message="删除文件失败")

class SwitchFileRequest(BaseModel):
    file_id: str = Field(..., description="文件ID")
    private: bool = Field(..., description="是否私有")

@router.post("/file/switch", summary="知识库文件切换私有属性")
async def switch_file(
    request: SwitchFileRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 查询文件
        file = db.query(RagFile).filter(
            RagFile.file_id == request.file_id,
            RagFile.is_deleted == False
        ).first()
        if not file:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=文件不存在或已被删除")
            return APIResponse.error(message="文件不存在或已被删除")

        # 检查用户是否有权限修改文件
        if file.user_id != current_user.user_id:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=没有权限修改文件")
            return APIResponse.error(message="没有权限修改文件")

        if file.status != RagFileStatus.FAILED and file.status != RagFileStatus.DONE:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=解析中的文件，无法切换私有属性")
            return APIResponse.error(message="解析中的文件，无法切换私有属性")

        if file.kb_type != RagKnowledgeBaseType.USER and file.kb_type != RagKnowledgeBaseType.USER_SHARED:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=非用户知识库文件，无法切换私有属性")
            return APIResponse.error(message="非用户知识库文件，无法切换私有属性")

        if file.kb_type == RagKnowledgeBaseType.USER and request.private:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=当前已经是私有文件")
            return APIResponse.success(message="当前已经是私有文件")

        if file.kb_type == RagKnowledgeBaseType.USER_SHARED and not request.private:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=当前已经是共享文件")
            return APIResponse.success(message="当前已经是共享文件")

        delete_resp = await delete_files(DeleteFilesRequest(file_ids=[file.file_id]), current_user, db)
        if delete_resp.code != 200:
            logger.warning(f"切换文件私有属性失败: user_id={current_user.user_id}, file_id={request.file_id}, msg=删除文件失败: {delete_resp.message}")
            return APIResponse.error(message=f"删除文件失败: {delete_resp.message}")

        await ensure_user_knowledge_base(current_user, db)

        new_kb_id = get_user_kb(current_user, db) if request.private else get_user_shared_kb(db)
        new_kb_type = RagKnowledgeBaseType.USER if request.private else RagKnowledgeBaseType.USER_SHARED
        new_status = RagFileStatus.LOCAL_SAVED

        db.query(RagFile).filter(RagFile.file_id == request.file_id).update({
            "kb_id": new_kb_id,
            "kb_type": new_kb_type,
            "status": new_status,
            "is_deleted": False
        })
        
        db.commit()
        return APIResponse.success(message="文件私有属性切换执行中")
    except Exception as e:
        db.rollback()
        logger.error(f"切换文件私有属性失败: {str(e)}")
        return APIResponse.error(message=f"切换文件私有属性失败: {str(e)}")

class CreateChatSessionRequest(BaseModel):
    doc_id: Optional[str] = Field(None, description="文档ID")

@router.post("/chat/session", summary="创建知识库对话会话")
async def create_chat_session(
    request: CreateChatSessionRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        session_id = f"chat-{shortuuid.uuid()}"
        chat_session = ChatSession(
            session_id=session_id,
            user_id=current_user.user_id,
        )
        if request.doc_id:
            # 检查文档是否存在
            doc = db.query(Document).filter(
                Document.doc_id == request.doc_id,
                Document.user_id == current_user.user_id,
            ).first()
            if not doc:
                return APIResponse.error(message="文档不存在")
            chat_session.doc_id = request.doc_id
            chat_session.session_type = ChatSessionType.EDITING_ASSISTANT
        else:
            chat_session.session_type = ChatSessionType.KNOWLEDGE_BASE

        db.add(chat_session)
        db.commit()

        return APIResponse.success(
            message="创建会话成功",
            data={
                "session_id": session_id,
                "created_at": chat_session.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    except Exception as e:
        logger.error(f"创建知识库会话失败: user_id={current_user.user_id}, error={str(e)}")
        return APIResponse.error(message=f"创建知识库会话失败: {str(e)}")

@router.delete("/chat/sessions/{session_id}", summary="删除知识库会话")
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

@router.get("/chat/sessions", summary="获取知识库会话列表")
async def get_chat_sessions(
    doc_id: Optional[str] = Query(None, description="文档ID"),
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 构建基础查询
        query = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.user_id,
            ChatSession.is_deleted == False
        )
        if doc_id:
            query = query.filter(ChatSession.doc_id == doc_id, 
                                 ChatSession.session_type == ChatSessionType.EDITING_ASSISTANT)
        else:
            query = query.filter(ChatSession.session_type == ChatSessionType.KNOWLEDGE_BASE)
        
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
            
            session_data.append({
                "session_id": session.session_id,
                "session_type": session.session_type,
                "last_message": last_message.content if last_message else None,
                "last_message_time": last_message.created_at.strftime("%Y-%m-%d %H:%M:%S") if last_message else None,
                "first_message": first_message.content if first_message else None,
                "first_message_time": first_message.created_at.strftime("%Y-%m-%d %H:%M:%S") if first_message else None,
                "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": session.updated_at.strftime("%Y-%m-%d %H:%M:%S") if session.updated_at else None
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

@router.get("/chat/sessions/{session_id}", summary="获取知识库会话详情")
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
            ChatSession.is_deleted == False
        ).first()
        if not session:
            return APIResponse.error(message="会话不存在或无权访问")
        
        # 查询消息 - 只选择数据库中存在的字段
        query = db.query(
            ChatMessage.id,
            ChatMessage.message_id,
            ChatMessage.session_id,
            ChatMessage.question_id,
            ChatMessage.role,
            ChatMessage.content,
            ChatMessage.content_type,
            ChatMessage.outline_id,
            ChatMessage.full_content,
            ChatMessage.tokens,
            ChatMessage.meta,
            ChatMessage.created_at,
            ChatMessage.updated_at,
            ChatMessage.is_deleted
        ).filter(
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
                        "content_type": msg.content_type if hasattr(msg, 'content_type') else "text",
                        "outline_id": msg.outline_id if hasattr(msg, 'outline_id') else "",
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

@router.post("/chat", summary="知识库对话")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        await ensure_user_knowledge_base(current_user, db)
        kb_ids = set()
        # 系统知识库
        kb_ids.add(get_system_kb(db))
        # 用户共享知识库
        kb_ids.add(get_user_shared_kb(db))
        # 用户私有知识库
        kb_ids.add(get_user_kb(current_user, db))
        # 部门知识库
        departments = get_departments(current_user, db)
        dept_kb_ids, dept_kb_owners = get_department_kbs([dept.department_id for dept in departments], db)
        kb_ids.update(dept_kb_ids)
        
        if not kb_ids:
            logger.warning(f"rag_chat 用户 {current_user.user_id} 未找到任何相关知识库")
            return APIResponse.error(message="未找到相关知识库")

        model = next((m for m in settings.LLM_MODELS if m["readable_model_name"] == request.model_name), None)
        if not model:
            logger.warning(f"rag_chat 用户 {current_user.user_id} 未找到模型: {request.model_name}")
            return APIResponse.error(message="请输入正确的模型名称")

        session_id = request.session_id
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id,
            ChatSession.is_deleted == False
        ).first()
        if not chat_session:
            return APIResponse.error(message="会话不存在或无权访问")

        reference_files = db.query(RagFile).filter(
            RagFile.file_id.in_(request.file_ids),
            RagFile.user_id == current_user.user_id,
            RagFile.is_deleted == False
        ).all()
        
        custom_prompt = ''
        for file in reference_files:
            content_preview = file.content[:settings.RAG_CHAT_PER_FILE_MAX_LENGTH]
            custom_prompt += f"文件名: {file.file_name}\n文件内容: {content_preview}\n\n"

        if chat_session.doc_id:
            doc = db.query(Document).filter(
                Document.doc_id == chat_session.doc_id,
                Document.user_id == current_user.user_id,
            ).first()
            if doc:
                custom_prompt += f"当前编辑的文档内容: {doc.content}\n\n"

        recent_answers = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "assistant",
            ChatMessage.is_deleted == False
        ).order_by(ChatMessage.id.desc()).limit(settings.RAG_CHAT_HISTORY_SIZE).all()
        
        history = []
        recent_answers.reverse()
        for answer in recent_answers:
            question = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.message_id == answer.question_id,
                ChatMessage.role == "user",
                ChatMessage.is_deleted == False
            ).first()
            if question:
                history.append([question.content, answer.content])

        question_message_id = f"msg-{shortuuid.uuid()}"
        user_question = ChatMessage(
            message_id=question_message_id,
            session_id=session_id,
            role="user",
            content=request.question,
            meta=json.dumps({"files": request.files})
        )
        db.add(user_question)
        db.commit()

        logger.info(json.dumps({
            "session_id": session_id,
            "message_id": question_message_id,
            "user_id": current_user.user_id,
            "kb_ids": list(kb_ids),
            "question": request.question,
            "custom_prompt": custom_prompt,
            "history": history,
            "streaming": request.stream,
            "networking": request.web_search,
            "product_source": settings.RAG_CHAT_PRODUCT_SOURCE,
            "rerank": settings.RAG_CHAT_RERANK,
            "only_need_search_results": settings.RAG_CHAT_ONLY_NEED_SEARCH_RESULTS,
            "hybrid_search": settings.RAG_CHAT_HYBRID_SEARCH,
            "max_token": settings.RAG_CHAT_MAX_TOKENS,
            "api_base": model['base_url'],
            "api_key": model['api_key'],
            "model": model['model'],
            "api_context_length": settings.RAG_CHAT_API_CONTEXT_LENGTH,
            "chunk_size": settings.RAG_CHAT_CHUNK_SIZE,
            "top_p": settings.RAG_CHAT_TOP_P,
            "top_k": settings.RAG_CHAT_TOP_K,
            "temperature": settings.RAG_CHAT_TEMPERATURE
        }, ensure_ascii=False))

        streaming = request.stream

        response = await rag_api_async.chat(
            kb_ids=list(kb_ids),
            question=request.question,
            custom_prompt=custom_prompt,
            history=history,
            streaming=streaming,
            networking=request.web_search,
            product_source=settings.RAG_CHAT_PRODUCT_SOURCE,
            rerank=settings.RAG_CHAT_RERANK,
            only_need_search_results=settings.RAG_CHAT_ONLY_NEED_SEARCH_RESULTS,
            hybrid_search=settings.RAG_CHAT_HYBRID_SEARCH,
            max_token=settings.RAG_CHAT_MAX_TOKENS,
            api_base=model["base_url"],
            api_key=model["api_key"],
            model=model["model"],
            api_context_length=settings.RAG_CHAT_API_CONTEXT_LENGTH,
            chunk_size=settings.RAG_CHAT_CHUNK_SIZE,
            top_p=settings.RAG_CHAT_TOP_P,
            top_k=settings.RAG_CHAT_TOP_K,
            temperature=settings.RAG_CHAT_TEMPERATURE,
        )

        if streaming:
            async def generate():
                try:
                    assistant_content = ''
                    async for chunk in response:
                        if chunk:
                            response_text = chunk.get("response", "")
                            if chunk.get("msg") == "success stream chat":
                                response_text = ""
                            new_chunk = {
                                **chunk,
                                "choices": [
                                    {"delta": {"content": response_text, "role": "assistant"}}
                                ]
                            }
                            assistant_content += response_text
                            yield f"data: {json.dumps(new_chunk, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    assistant_message = ChatMessage(
                        message_id=f"msg-{shortuuid.uuid()}",
                        session_id=session_id,
                        question_id=question_message_id,
                        role="assistant",
                        content=assistant_content
                    )
                    db.add(assistant_message)
                    db.commit()
                except Exception as e:
                    logger.exception("流式响应生成异常")
                    yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Transfer-Encoding": "chunked",
                    "X-Session-ID": session_id
                }
            )
        else:
            if isinstance(response, dict) and response.get("code") == 200:
                history = response.get("history")
                if not history or len(history) == 0 or len(history[-1]) != 2:
                    logger.error(f"RAG对话返回异常: user_id={current_user.user_id}, response={response}")
                    return APIResponse.error(message="RAG对话返回异常")
                
                answer = history[-1][1]
                assistant_message = ChatMessage(
                    message_id=f"msg-{shortuuid.uuid()}",
                    session_id=session_id,
                    question_id=question_message_id,
                    role="assistant",
                    content=answer
                )
                db.add(assistant_message)
                db.commit()
                return APIResponse.success(message="对话成功", data=answer)
            else:
                logger.error(f"RAG对话失败: user_id={current_user.user_id}, response={response}")
                return APIResponse.error(message="对话失败")

    except Exception as e:
        logger.exception(f"知识库对话发生异常: {str(e)}")
        return APIResponse.error(message=f"对话失败: {str(e)}")

@router.post("/attachments", summary="知识库对话附件上传")
async def upload_attachment(
    files: List[FastAPIUploadFile] = File(...),
    save_to_kb: Optional[bool] = Body(default=False, description="是否保存到知识库"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        upload_dir = PathLib(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True) # 确保上传目录存在
        
        kb_id = ''
        kb_type = RagKnowledgeBaseType.USER_SHARED
        # 查询用户共享知识库
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == kb_type, 
                                                   RagKnowledgeBase.is_deleted == False).first()
        if not kb:
            logger.error(f"上传附件时未找到用户共享知识库")
            return APIResponse.error(message="用户共享知识库不存在")
        kb_id = kb.kb_id

        new_files = []
        existing_files = []
        update_content_files = []
        for file in files:
            file_id = f"file-{shortuuid.uuid()}"
            file_location = upload_dir / f"{file_id}_{file.filename}" # 文件存储路径
            file_name = file.filename
            # 保存文件到磁盘
            try:
                contents = await file.read()
                with open(file_location, "wb") as f:
                    f.write(contents)
                
                # 计算文件的哈希值
                file_hash = hashlib.sha256(contents).hexdigest()
                db_file = db.query(RagFile).filter(RagFile.hash == file_hash, RagFile.is_deleted == False).first()
                if db_file:
                    existing_files.append(db_file)
                    continue
                
                file_format = get_file_format(str(file_location))
                if file_format == 'doc':
                    docx_file_location = await convert_doc_to_docx(str(file_location))
                    file_location = docx_file_location
                    file_format = "docx"
                    file_name = file_name.replace(".doc", ".docx")

                new_files.append({
                    "file_id": file_id,
                    "file_name": file_name,
                    "size": len(contents),
                    "content_type": file_format,
                    "path": str(file_location),
                    "hash": file_hash 
                })
            except Exception as e:
                logger.error(f"上传文件 {file.filename} 时发生错误: {str(e)}")
                return APIResponse.error(message=f"上传文件 {file.filename} 时发生错误: {str(e)}")
            finally:
                await file.close()
        
            # 提交RAG解析任务
            db_file = RagFile(
                file_id=file_id,    
                user_id=current_user.user_id,
                file_name=file_name,
                file_size=len(contents),
                file_ext=file_format, 
                file_path=str(file_location),
                summary_small='',
                summary_medium='',
                summary_large='',
                content='',
                meta='',
                hash=file_hash 
            )
            if save_to_kb:
                db_file.kb_id = kb_id
                db_file.kb_type = kb_type
                db_file.status = RagFileStatus.LOCAL_SAVED
            else:
                db_file.kb_id = ''
                db_file.kb_type = RagKnowledgeBaseType.NONE
                db_file.status = RagFileStatus.DONE
            db.add(db_file)
            db.commit() 
            # 同步解析内容，附件的内容马上要使用，所以进行同步解析
            parser = get_parser(file_format)
            if not parser:
                logger.error(f"upload_attachment 不支持解析的文件格式: {file_format}")
                continue
            content = await parser.async_content(file_location)
            if not content.strip():
                logger.error(f"upload_attachment 解析文件 {file.filename} 时发生错误: 文件内容为空")
                continue
            # 添加到更新内容列表
            update_content_files.append((file_id, content))

        for file in existing_files:
            if not file.content.strip():
                parser = get_parser(file.file_ext)
                if not parser:
                    logger.error(f"upload_attachment 不支持解析的文件格式: {file.file_ext}")
                    continue
                content = await parser.async_content(file.file_path)
                if not content.strip():
                    logger.error(f"upload_attachment 解析文件 {file.file_name} 时发生错误: 文件内容为空")
                    continue
                update_content_files.append((file.file_id, content))
        
        # 更新内容
        for file_id, content in update_content_files:
            if not content.strip():
                logger.error(f"upload_attachment 更新文件 {file_id} 内容时发生错误: 文件内容为空")
                continue
            db.query(RagFile).filter(RagFile.file_id == file_id).update({
                "content": content
            })
            db.commit()
        
        return APIResponse.success(
            message=f"文件上传成功, 正在解析中。",
            data={
                "files": new_files,
                "existing_files": [{
                    "file_id": file.file_id, 
                    "file_name": file.file_name,
                    "size": file.file_size,
                    "content_type": file.file_ext,
                    "path": file.file_path,
                    "hash": file.hash
                } for file in existing_files]
            }
        )
    except Exception as e:
        logger.error(f"上传文件时发生异常: {str(e)}")
        return APIResponse.error(message=f"上传失败: {str(e)}")