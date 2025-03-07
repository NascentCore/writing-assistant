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
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage, ChatSessionType
from app.rag.parser import get_parser, get_file_format
from app.rag.rag_api import rag_api
from app.schemas.response import APIResponse, PaginationData, PaginationResponse
from app.models.task import Task, TaskStatus

logger = logging.getLogger("app")

router = APIRouter()

class FilesResponse(PaginationResponse):
    data: List[Dict[str, Any]]

class ChatRequest(BaseModel):
    question: str = Field(description="问题内容")
    model_name: str = Field(description="模型名称")
    session_id: str = Field(description="会话ID")
    file_ids: Optional[List[str]] = Field(default=[], description="关联的文件ID列表")
    files: Optional[List[Dict[str, Any]]] = Field(default=[], description="关联的文件内容")
    streaming: Optional[bool] = Field(default=True, description="是否使用流式返回")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "这是一个问题",
                "model_name": "deepseek-v3",
                "file_ids": [],
                "session_id": None,
                "streaming": True
            }
        }

class FileUploadRequest(BaseModel):
    files: List[str]

class DeleteFilesRequest(BaseModel):
    file_ids: List[str] = Field(..., description="要删除的文件ID列表")

@router.post("/files", summary="知识库文件上传")
async def upload_files(
    category: str = Query(..., description="知识库类别", example="system", enum=["system", "user"]),
    files: List[FastAPIUploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        upload_dir = PathLib(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True) # 确保上传目录存在

        kb_id = ''
        if category == "system":
            if not current_user.admin:
                logger.warning(f"用户 {current_user.user_id} 尝试上传文件到系统知识库但没有管理员权限")
                return APIResponse.error(message="系统知识库需要管理员权限")
            # 查询系统知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM, 
                                                   RagKnowledgeBase.is_deleted == False).first()
            if kb:
                kb_id = kb.kb_id
        elif category == "user":
            # 查询用户知识库
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, 
                                                   RagKnowledgeBase.user_id == current_user.user_id, 
                                                   RagKnowledgeBase.is_deleted == False).first()
            if kb:
                kb_id = kb.kb_id
        
        if not kb_id:
            kb_name = "系统知识库" if category == "system" else f"用户知识库-{current_user.user_id}"
            create_kb_response = rag_api.create_knowledge_base(kb_name=kb_name)
            if create_kb_response["code"] != 200:
                logger.error(f"创建知识库失败: kb_name={kb_name}, msg={create_kb_response['msg']}")
                return APIResponse.error(message=f"创建知识库失败: {create_kb_response['msg']}")
            kb_id = create_kb_response["data"]["kb_id"]
            if not kb_id:
                logger.error(f"创建知识库成功, 但获取知识库ID失败: kb_name={kb_name}, msg={create_kb_response['msg']}")
                return APIResponse.error(message=f"创建知识库失败")
            # 保存知识库到数据库
            kb = RagKnowledgeBase(
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.SYSTEM if category == "system" else RagKnowledgeBaseType.USER,
                user_id=current_user.user_id,
                kb_name=kb_name,
            )
            db.add(kb)
            db.commit()
        
        # 过滤已存在的文件
        file_names = [file.filename for file in files]
        existing_files = db.query(RagFile).filter(RagFile.kb_id == kb_id, RagFile.file_name.in_(file_names), RagFile.is_deleted == False).all()
        existing_file_names = [file.file_name for file in existing_files]
        files = [file for file in files if file.filename not in existing_file_names]
        
        result = []
        for file in files:
            file_id = f"file-{shortuuid.uuid()}"
            file_location = upload_dir / f"{file_id}_{file.filename}" # 文件存储路径
            # 保存文件到磁盘
            try:
                contents = await file.read()
                with open(file_location, "wb") as f:
                    f.write(contents)
                # 从文件内容判断格式
                file_format = get_file_format(str(file_location))
                result.append({
                    "file_id": file_id,
                    "file_name": file.filename,
                    "size": len(contents),
                    "content_type": file_format,
                    "path": str(file_location)
                })
            except Exception as e:
                logger.error(f"上传文件 {file.filename} 时发生错误: {str(e)}")
                return APIResponse.error(message=f"上传文件 {file.filename} 时发生错误: {str(e)}")
            finally:
                await file.close()
        
            db_file = RagFile(
                file_id=file_id,    
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.SYSTEM if category == "system" else RagKnowledgeBaseType.USER,
                user_id=current_user.user_id,
                file_name=file.filename,
                file_size=len(contents),
                file_ext=file_format, 
                file_path=str(file_location),
                status=RagFileStatus.LOCAL_SAVED,
                summary_small='',
                summary_medium='',
                summary_large='',
                content='',
                meta='',
            )
        
            db.add(db_file)
            db.commit() 

        return APIResponse.success(
            message=f"文件上传成功, 正在解析中。已经存在文件: {existing_file_names}",
            data=result
        )
    except Exception as e:
        logger.error(f"上传文件时发生异常: {str(e)}")
        return APIResponse.error(message=f"上传失败: {str(e)}")

@router.get("/files", summary="获取知识库文件列表")
async def get_files(
    category: str = Query(..., description="知识库类别", example="system", enum=["system", "user"]),
    page: Optional[int] = Query(default=1, ge=1, description="页码", example=1),
    page_size: Optional[int] = Query(default=10, ge=1, description="每页数量", example=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if category == "system" and not current_user.admin:
            logger.warning(f"用户 {current_user.user_id} 尝试访问系统知识库但没有管理员权限")
            return APIResponse.error(message="系统知识库需要管理员权限")
        
        if category == "user":
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, 
                                                   RagKnowledgeBase.user_id == current_user.user_id, 
                                                   RagKnowledgeBase.is_deleted == False).first()
        else:
            kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM, 
                                                   RagKnowledgeBase.is_deleted == False).first()
        
        if not kb:
            kb_name = "系统知识库" if category == "system" else f"用户知识库-{current_user.user_id}"
            create_kb_response = rag_api.create_knowledge_base(kb_name=kb_name)
            if create_kb_response["code"] != 200:
                logger.error(f"创建知识库失败: kb_name={kb_name}, msg={create_kb_response['msg']}")
                return APIResponse.error(message=f"创建知识库失败: {create_kb_response['msg']}")
            kb_id = create_kb_response["data"]["kb_id"]
            if not kb_id:
                logger.error(f"创建知识库成功, 但获取知识库ID失败: kb_name={kb_name}, msg={create_kb_response['msg']}")
                return APIResponse.error(message=f"创建知识库失败")
            # 保存知识库到数据库
            kb = RagKnowledgeBase(
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.SYSTEM if category == "system" else RagKnowledgeBaseType.USER,
                user_id=current_user.user_id,
                kb_name=kb_name,
            )
            db.add(kb)
            db.commit()

        total = db.query(RagFile).filter(RagFile.kb_id == kb.kb_id, RagFile.is_deleted == False).count()
        total_pages = (total + page_size - 1) // page_size
        files = db.query(RagFile).filter(RagFile.kb_id == kb.kb_id, RagFile.is_deleted == False).order_by(RagFile.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return APIResponse.success(
            message="获取知识库文件列表成功",
            data=PaginationData(
                list=[{
                    "kb_id": file.kb_id,
                    "file_id": file.file_id,
                    "file_name": file.file_name,
                    "file_size": file.file_size,
                    "file_words": file.file_words,
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

    # 检查文件是否存在且属于当前用户
    files = db.query(RagFile).filter(RagFile.file_id.in_(request.file_ids), RagFile.is_deleted == False).all()
    if not files:
        return APIResponse.error(message="未找到有效的文件")

    # 检查所有文件是否属于同一个知识库
    kb_ids = set(file.kb_id for file in files)
    if len(kb_ids) > 1:
        return APIResponse.error(message="不能同时删除不同知识库的文件")

    # 权限检查
    for file in files:
        if file.kb_type == RagKnowledgeBaseType.SYSTEM and not current_user.admin:
            return APIResponse.error(message="系统知识库需要管理员权限")
        if file.kb_type == RagKnowledgeBaseType.USER and file.user_id != current_user.user_id:
            return APIResponse.error(message="用户知识库需要本人权限")

    try:
        resp = rag_api.delete_files(kb_id=files[0].kb_id, file_ids=[file.kb_file_id for file in files])
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

@router.post("/chat/session", summary="创建知识库对话会话")
async def create_chat_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        session_id = f"chat-{shortuuid.uuid()}"
        chat_session = ChatSession(
            session_id=session_id,
            session_type=ChatSessionType.KNOWLEDGE_BASE,
            user_id=current_user.user_id,
        )

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
            ChatSession.session_type == ChatSessionType.KNOWLEDGE_BASE,
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
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 构建基础查询
        query = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.user_id,
            ChatSession.session_type == ChatSessionType.KNOWLEDGE_BASE,
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
            ChatSession.session_type == ChatSessionType.KNOWLEDGE_BASE,
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
        kb_ids = []
        # 查询系统知识库
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM, 
                                                   RagKnowledgeBase.is_deleted == False).first()
        if kb:
            kb_ids.append(kb.kb_id)
        # 查询用户知识库
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, 
                                                   RagKnowledgeBase.user_id == current_user.user_id, 
                                                   RagKnowledgeBase.is_deleted == False).first()
        if kb:
            kb_ids.append(kb.kb_id)
        if not kb_ids:
            logger.warning(f"rag_chat 用户 {current_user.user_id} 未找到任何相关知识库")
            return APIResponse.error(message="未找到相关知识库")

        # 根据model_name获取模型
        model = next((m for m in settings.LLM_MODELS if m["readable_model_name"] == request.model_name), None)
        if not model:
            logger.warning(f"rag_chat 用户 {current_user.user_id} 未找到模型: {request.model_name}")
            return APIResponse.error(message="请输入正确的模型名称")
        
        # session_id 验证
        session_id = request.session_id
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.session_type == ChatSessionType.KNOWLEDGE_BASE,
            ChatSession.user_id == current_user.user_id,
            ChatSession.is_deleted == False
        ).first()
        if not chat_session:
            return APIResponse.error(message="会话不存在或无权访问")
        
        # 获取引用的文件
        reference_files = db.query(RagFile).filter(
            RagFile.file_id.in_(request.file_ids),
            RagFile.user_id == current_user.user_id,
            RagFile.is_deleted == False
        ).all()
        if len(reference_files) != len(request.file_ids):
            logger.error(f"rag_chat 用户 {current_user.user_id} 引用的文件不存在或无权访问: {request.file_ids}")

        # 获取引用的文件内容
        custom_prompt = ''
        for file in reference_files:
            content_preview = file.content[:settings.RAG_CHAT_PER_FILE_MAX_LENGTH]
            custom_prompt += f"文件名: {file.file_name}\n文件内容: {content_preview}\n\n"

        # 获取最近的2条大模型回答
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
        
        # 保存问题
        question_message_id = f"msg-{shortuuid.uuid()}"
        user_question = ChatMessage(
            message_id=question_message_id,
            session_id=session_id,
            role="user",
            content=request.question,
            meta=json.dumps({
                "files": request.files
            })
        )
        db.add(user_question)
        db.commit()

        logger.info(json.dumps({
            "session_id": session_id,
            "message_id": question_message_id,
            "user_id": current_user.user_id,
            "kb_ids": kb_ids,
            "question": request.question,
            "custom_prompt": custom_prompt,
            "history": history,
            "streaming": request.streaming,
            "networking": settings.RAG_CHAT_NETWORKING,
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
        
        # 根据请求参数决定是否使用流式返回
        streaming = request.streaming

        response = rag_api.chat(
            kb_ids=kb_ids,
            question=request.question,
            custom_prompt=custom_prompt,
            history=history,
            streaming=streaming,
            networking=settings.RAG_CHAT_NETWORKING,
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
                    for chunk in response:
                        if chunk:
                            response_text = chunk.get("response", "")
                            if chunk.get("msg") == "success stream chat":
                                continue
                            # 构建新的响应格式
                            new_chunk = {
                                **chunk,  # 保留原有的所有字段
                                "choices": [
                                    {
                                        "delta": {
                                            "content": response_text,
                                            "role": "assistant"
                                        }
                                    }
                                ]
                            }
                            assistant_content += response_text
                            yield f"data: {json.dumps(new_chunk, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    # 流式响应结束后保存回答记录
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
                    error_msg = {"error": str(e)}
                    yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
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
                answer = response.get("history",[["", ""]])[0][1]
                assistant_message = ChatMessage(
                    message_id=f"msg-{shortuuid.uuid()}",
                    session_id=session_id,
                    question_id=question_message_id,
                    role="assistant",
                    content=answer
                )
                db.add(assistant_message)
                db.commit() 
                return APIResponse.success(
                    message="对话成功",
                    data=answer
                )
            else:
                logger.error(f"RAG对话失败: user_id={current_user.user_id}, response={response}")
                return APIResponse.error(message="对话失败")
        
    except Exception as e:
        logger.exception(f"知识库对话发生异常: {str(e)}")
        return APIResponse.error(message=f"对话失败: {str(e)}")

@router.post("/attachments", summary="知识库对话附件上传")
async def upload_attachment(
    files: List[FastAPIUploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        upload_dir = PathLib(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True) # 确保上传目录存在
        
        kb_id = ''
        # 查询用户知识库
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, 
                                                   RagKnowledgeBase.user_id == current_user.user_id, 
                                                   RagKnowledgeBase.is_deleted == False).first()
        if kb:
           kb_id = kb.kb_id
        else:
            kb_name = f"用户知识库-{current_user.user_id}"
            create_kb_response = rag_api.create_knowledge_base(kb_name=kb_name)
            if create_kb_response["code"] != 200:
                logger.error(f"创建知识库失败: kb_name={kb_name}, msg={create_kb_response['msg']}")
                return APIResponse.error(message=f"创建知识库失败: {create_kb_response['msg']}")
            kb_id = create_kb_response["data"]["kb_id"]
            # 保存知识库到数据库
            kb = RagKnowledgeBase(
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.USER,
                user_id=current_user.user_id,
                kb_name=kb_name,
            )
            db.add(kb)
            db.commit()

        # 过滤已存在的文件
        file_names = [file.filename for file in files]
        existing_files = db.query(RagFile).filter(RagFile.kb_id == kb_id, RagFile.file_name.in_(file_names), RagFile.is_deleted == False).all()
        existing_file_names = [file.file_name for file in existing_files]
        files = [file for file in files if file.filename not in existing_file_names]
        
        result = []
        update_content_files = []
        for file in files:
            file_id = f"file-{shortuuid.uuid()}"
            file_location = upload_dir / f"{file_id}_{file.filename}" # 文件存储路径
            # 保存文件到磁盘
            try:
                contents = await file.read()
                with open(file_location, "wb") as f:
                    f.write(contents)
                # 从文件内容判断格式
                file_format = get_file_format(str(file_location))
                result.append({
                    "file_id": file_id,
                    "file_name": file.filename,
                    "size": len(contents),
                    "content_type": file_format,
                })
            except Exception as e:
                logger.error(f"上传文件 {file.filename} 时发生错误: {str(e)}")
                return APIResponse.error(message=f"上传文件 {file.filename} 时发生错误: {str(e)}")
            finally:
                await file.close()
        
            # 提交RAG解析任务
            db_file = RagFile(
                file_id=file_id,    
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.USER,
                user_id=current_user.user_id,
                file_name=file.filename,
                file_size=len(contents),
                file_ext=file_format, 
                file_path=str(file_location),
                status=RagFileStatus.LOCAL_SAVED,
                summary_small='',
                summary_medium='',
                summary_large='',
                content='',
                meta='',
            )
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
            result.append({
                "file_id": file.file_id,
                "file_name": file.file_name,
                "size": file.file_size,
                "content_type": file.file_ext,
            })
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
            message=f"文件上传成功, 正在解析中。已经存在文件: {existing_file_names}",
            data=result
        )
    except Exception as e:
        logger.error(f"上传文件时发生异常: {str(e)}")
        return APIResponse.error(message=f"上传失败: {str(e)}")