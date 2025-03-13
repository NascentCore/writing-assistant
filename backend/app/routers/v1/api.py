from fastapi import APIRouter, UploadFile as FastAPIUploadFile, File, Depends, Query
from fastapi.responses import StreamingResponse
import shortuuid
from app.config import settings
import openai
import json
from typing import List, Literal, Optional, Dict, Any
from pathlib import Path
from app.database import get_db
from app.models.upload_file import UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from app.parser import get_parser, get_file_format
from app.models.document import Document
from sqlalchemy.sql import func
from sqlalchemy import desc
from app.auth import get_current_user
from app.models.user import User
from app.models.system_config import SystemConfig
from app.models.chat import ChatSession, ChatMessage, ChatSessionType
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, Template
import logging
from app.schemas.response import APIResponse, PaginationData, PaginationResponse
from app.scrape.web import scraper
from app.models.web_page import WebPage
from app.models.rag import RagFile


router = APIRouter()

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(console_handler)

# 初始化Jinja2环境
template_dir = Path(__file__).parent.parent.parent.parent / "templates"
env = Environment(loader=FileSystemLoader(template_dir))


@router.get("/config")
async def get_config():
    """获取大模型配置信息"""
    return APIResponse.success(
        data={
            "llm": {
                "models": [model["readable_model_name"] for model in settings.LLM_MODELS]
            }
        }
    )

class Message(BaseModel):
    role: str = Field(..., description="消息角色", example="user")
    content: str = Field(..., description="消息内容", example="你好，请问有什么可以帮助你的？")

class CompletionRequest(BaseModel):
    model_name: Optional[str] = Field(None, description="模型名称")
    session_id: Optional[str] = Field(None, description="会话ID，如果不传则自动创建")
    messages: List[Message] = Field(..., description="对话消息列表")
    action: Optional[Literal["extension", "abridge", "continuation", "rewrite", "overall", "chat"]] = Field("chat", description="操作类型")
    stream: bool = Field(False, description="是否使用流式响应")
    temperature: Optional[float] = Field(0.7, description="温度参数，控制随机性，范围0-2", ge=0, le=2)
    top_p: Optional[float] = Field(1, description="核采样参数，控制输出的多样性", ge=0, le=1)
    max_tokens: Optional[int] = Field(200, description="生成的最大token数量", ge=1)
    
    file_ids: Optional[List[str]] = Field([], description="引用的文件ID列表")
    doc_id: Optional[str] = Field(None, description="引用的文档ID，及当前编辑的文档ID")
    webpage_ids: Optional[List[str]] = Field([], description="引用的网页ID列表")
    selected_contents: Optional[List[str]] = Field(None, description="划选的文本内容列表")

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "请总结一下这份文档的主要内容"
                    }
                ],
                "model_name": "doubao",
                "session_id": "abc123",
                "file_ids": ["abc123"],
                "doc_id": "abc123",
                "selected_contents": ["这是第一段划选的文本", "这是第二段划选的文本"],
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }

@router.post("/completions")
async def completions(
    request: CompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        body = request.model_dump(exclude_none=True)
        action = request.action
        
        # 从数据库读取提示词模板
        template_key = f"prompt.{action}"
        template_config = db.query(SystemConfig).filter(
            SystemConfig.key == template_key
        ).first()
        
        if not template_config:
            return APIResponse.error(message=f"提示词模板 {template_key} 不存在")
            
        # 使用字符串模板替代文件模板
        template = Template(template_config.value)
        
        # 处理会话ID
        session_id = request.session_id
        if not session_id:
            session_id = f"chat-{shortuuid.uuid()}"
            # 创建新会话
            chat_session = ChatSession(
                session_id=session_id,
                user_id=current_user.user_id,
                session_type=ChatSessionType.WRITING
            )
            if request.doc_id:
                chat_session.doc_id = request.doc_id

            db.add(chat_session)
            db.commit()
        else:
            # 验证会话是否存在且属于当前用户
            chat_session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.user_id,
                ChatSession.session_type == ChatSessionType.WRITING,
                ChatSession.is_deleted == False
            ).first()
            if not chat_session:
                return APIResponse.error(message="会话不存在或无权访问")

        # 获取历史消息
        history_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.is_deleted == False
        ).order_by(ChatMessage.id).all()

        # 构建完整的消息列表
        full_messages = []
        
        # 添加系统消息
        llm_config = next((m for m in settings.LLM_MODELS if m["readable_model_name"] == body.get("model_name", "")), settings.LLM_MODELS[0])
        if llm_config.get("system_prompt"):
            full_messages.append({
                "role": "system",
                "content": llm_config["system_prompt"]
            })

        # 添加历史消息
        for msg in history_messages:
            full_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # 处理当前请求的消息
        original_message = body["messages"][0]["content"]
        
        # 流式传输
        stream = body.get("stream", False)

        # 只在需要使用doc时再查询数据库
        doc_content = ""
        if request.doc_id:
            doc = db.query(Document).filter(Document.doc_id == request.doc_id).first()
            if not doc:
                return APIResponse.error(message="引用的文档不存在")
            doc_content = doc.content
        
        # 处理文件引用
        reference_files = []
        if "file_ids" in body:
            file_ids = body["file_ids"]
            del body["file_ids"]
            if isinstance(file_ids, list):
                # 获取所有引用文件的内容
                files = db.query(
                    RagFile.file_id,
                    RagFile.file_name,
                    RagFile.content
                ).filter(RagFile.file_id.in_(file_ids)).all()
                
                # 检查是否所有请求的文件都存在
                found_file_ids = {file.file_id for file in files}
                missing_file_ids = set(file_ids) - found_file_ids
                
                if missing_file_ids:
                    return APIResponse.error(
                        message=f"以下文件不存在: {', '.join(missing_file_ids)}"
                    )
                
                # 构建参考文档内容
                for file in files:
                    reference_files.append({
                        "file_name": file.file_name,
                        "file_content": file.content
                    })
        
        # 处理网页引用
        reference_webpages = []
        if "webpage_ids" in body:
            webpage_ids = body["webpage_ids"]
            del body["webpage_ids"]
            # 获取所有引用网页的内容
            webpages = db.query(WebPage).filter(WebPage.webpage_id.in_(webpage_ids)).all()
            # 检查是否所有请求的网页都存在
            found_webpage_ids = {webpage.webpage_id for webpage in webpages}
            missing_webpage_ids = set(webpage_ids) - found_webpage_ids
            if missing_webpage_ids:
                return APIResponse.error(
                    message=f"以下网页不存在: {', '.join(missing_webpage_ids)}"
                )
            for webpage in webpages:
                reference_webpages.append({
                    "webpage_id": webpage.webpage_id,
                    "webpage_content": webpage.content
                })

        prompt = template.render(
            question=original_message,
            content=doc_content,
            selected_contents=request.selected_contents,
            reference_files=reference_files,
            reference_webpages=reference_webpages
        )
        
        # 添加当前消息
        full_messages.append({
            "role": "user",
            "content": prompt
        })

        # max_token
        max_tokens = request.max_tokens
        if action == "chat":
            max_tokens = 200

        # 保存用户消息到数据库
        question_message_id = f"msg-{shortuuid.uuid()}"
        user_message = ChatMessage(
            message_id=question_message_id,
            session_id=session_id,
            role="user",
            content=original_message,
            full_content=prompt,
            meta=json.dumps({
                "temperature": request.temperature,
                "top_p": request.top_p,
                "max_tokens": max_tokens,
                "file_ids": file_ids,
                "doc_id": request.doc_id,
                "selected_contents": request.selected_contents
            })
        )
        db.add(user_message)
        db.commit()

        # 配置OpenAI客户端并调用API
        client = openai.AsyncOpenAI(
            base_url=llm_config["base_url"],
            api_key=llm_config["api_key"]
        )

        completion = await client.chat.completions.create(
            model=llm_config["model"],
            messages=full_messages,
            temperature=request.temperature,
            stream=request.stream,
            max_tokens=max_tokens,
            timeout=settings.LLM_REQUEST_TIMEOUT
        )

        # 使用logger替换print
        logger.info("Chat Completion Request Info:")
        logger.info(f"Model: {body.get('model_name', '未传model_name')}")
        logger.info(f"Original Message: {original_message}")
        logger.info(f"Full Messages: {json.dumps(full_messages, ensure_ascii=False, indent=2)}")

        if stream:
            # 流式响应
            async def generate_stream():
                assistant_content = ""
                async for chunk in completion:
                    if chunk.choices[0].delta.content:
                        assistant_content += chunk.choices[0].delta.content
                    yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                
                # 流式响应结束后保存助手回复
                assistant_message = ChatMessage(
                    message_id=f"msg-{shortuuid.uuid()}",
                    session_id=session_id,
                    question_id=question_message_id,
                    role="assistant",
                    content=assistant_content
                )
                db.add(assistant_message)
                db.commit()

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={"X-Session-ID": session_id} # 添加会话ID
            )
        else:
            # 非流式响应，直接保存助手回复
            assistant_message = ChatMessage(
                message_id=f"msg-{shortuuid.uuid()}",
                session_id=session_id,
                question_id=question_message_id,
                role="assistant",
                content=completion.choices[0].message.content,
                full_content=completion.choices[0].message.content,
                # TODO 添加meta数据
            )
            db.add(assistant_message)
            db.commit()

            return APIResponse.success(
                data={
                    **completion.model_dump(),
                    "session_id": session_id
                }
            )

    except Exception as e:
        return APIResponse.error(message=f"请求失败: {str(e)}")

@router.post("/files")
async def upload_files(
    files: List[FastAPIUploadFile] = File(
        ...,
        description="要上传的文件列表，支持PDF和DOCX格式"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    上传文件
    
    Args:
        files: 支持上传多个文件，目前支持PDF和DOCX格式
        
    Returns:
        message: 处理结果信息
        success: 是否成功
        data: 上传文件的详细信息列表
    """
    try:
        upload_dir = Path(settings.UPLOAD_DIR)
        # 确保上传目录存在
        upload_dir.mkdir(exist_ok=True)
        
        result = []
        for file in files:
            # 使用uuid
            file_id = f"file-{shortuuid.uuid()}"
            # 使用 file_id 作为文件名
            file_location = upload_dir / f"{file_id}_{file.filename}"
            
            # 保存文件
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
                return APIResponse.error(message=f"上传文件 {file.filename} 时发生错误: {str(e)}")
            finally:
                await file.close()
        
            # 解析文件内容，目前支持pdf和word
            parser = get_parser(file_format)
            file_content = parser.parse(str(file_location))
        
            # 保存到数据库时使用转换后的格式
            db_file = UploadFile(
                file_id=file_id,    
                file_name=file.filename,
                file_size=len(contents),
                file_type=file_format, 
                file_path=str(file_location),
                status=1,
                content=file_content,
                user_id=current_user.user_id,
            )
        
            db.add(db_file)
            db.commit() 

        return APIResponse.success(
            message="文件上传成功",
            data=result
        )
    except Exception as e:
        return APIResponse.error(message=f"上传失败: {str(e)}")

@router.get("/files")
async def get_files(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的文件列表
    
    Args:\n
        page: 页码，从1开始\n
        page_size: 每页显示的数量，默认10，最大100\n
        
    Returns:\n
        total: 总记录数\n
        items: 文件列表\n
        page: 当前页码\n
        page_size: 每页数量\n
        pages: 总页数
    """
    try:
        query = db.query(UploadFile).filter(
            UploadFile.user_id == current_user.user_id
        )
        
        total = query.count()
        pages = (total + page_size - 1) // page_size
        
        files = query.order_by(desc(UploadFile.created_at))\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        return APIResponse.success(
            data={
                "total": total,
                "items": [
                    {
                        "file_id": file.file_id,
                        "name": file.file_name,
                        "size": file.file_size,
                        "type": file.file_type,
                        "status": file.status,
                        "created_at": file.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    for file in files
                ],
                "page": page,
                "page_size": page_size,
                "pages": pages
            }
        )
    except Exception as e:
        return APIResponse.error(message=f"获取失败: {str(e)}")

@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    下载指定的文件
    
    Args:
        file_id: 文件ID
        
    Returns:
        文件的二进制流
    """
    # 查询文件信息
    file = db.query(UploadFile).filter(
        UploadFile.file_id == file_id,
        UploadFile.user_id == current_user.user_id
    ).first()
    
    if not file:
        raise APIResponse.error(message="文件不存在或无权访问")
    
    file_path = Path(file.file_path)
    if not file_path.exists():
        raise APIResponse.error(message="文件不存在")
    
    # 创建文件流
    def iterfile():
        with open(file_path, "rb") as f:
            yield from f
    
    # 对文件名进行 URL 编码        
    encoded_filename = quote(file.file_name)
            
    # 返回文件流响应
    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=utf-8\'\'{encoded_filename}'
        }
    )

@router.get("/models")
async def get_models():
    """获取支持的模型列表"""
    return APIResponse.success(
        message="success",
        data={
            "models": [
                {
                    "id": model["model"],
                    "name": model["readable_model_name"],
                    "description": model["system_prompt"]
                }
                for model in settings.LLM_MODELS
            ]
        }
    )
class CreateSessionRequest(BaseModel):
    doc_id: str = Field(..., description="文档ID")

@router.post("/sessions", summary="创建新会话")
async def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新的聊天会话
    
    Args:
        doc_id: 文档ID
        
    Returns:
        session_id: 新创建的会话ID
    """
    try:
        # 生成新的会话ID
        session_id = f"chat-{shortuuid.uuid()}"
        
        # 创建新会话
        chat_session = ChatSession(
            session_id=session_id,
            user_id=current_user.user_id,
            session_type=ChatSessionType.WRITING,
            doc_id=request.doc_id
        )
        
        db.add(chat_session)
        db.commit()
        
        return APIResponse.success(
            message="会话创建成功",
            data={
                "session_id": session_id,
                "created_at": chat_session.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        )
        
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        return APIResponse.error(message=f"创建会话失败: {str(e)}")

@router.get("/sessions")
async def get_sessions(
    doc_id: Optional[str] = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的对话会话列表
    
    Args:
        doc_id: 可选的文档ID，如果提供则只返回与该文档相关的会话
        page: 页码，从1开始
        page_size: 每页显示的数量，默认10，最大100
        
    Returns:
        total: 总记录数
        items: 会话列表
        page: 当前页码
        page_size: 每页数量
        pages: 总页数
    """
    try:
        # 构建基础查询
        query = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.user_id,
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.is_deleted == False
        )
        
        # 如果提供了doc_id，添加文档过滤条件
        if doc_id:
            # 通过消息元数据中的doc_id字段过滤
            query = query.join(ChatMessage, ChatSession.session_id == ChatMessage.session_id)\
                .filter(ChatMessage.meta.contains(f'"doc_id": "{doc_id}"'))\
                .distinct()
        
        # 获取总记录数
        total = query.count()
        pages = (total + page_size - 1) // page_size
        
        # 分页查询会话
        sessions = query.order_by(desc(ChatSession.updated_at))\
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
                .order_by(desc(ChatMessage.created_at))\
                .first()
            
            session_data.append({
                "session_id": session.session_id,
                "last_message": last_message.content if last_message else None,
                "last_message_time": last_message.created_at.strftime("%Y-%m-%d %H:%M:%S") if last_message else None,
                "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": session.updated_at.strftime("%Y-%m-%d %H:%M:%S") if session.updated_at else None
            })
        
        return APIResponse.success(
            data={
                "total": total,
                "items": session_data,
                "page": page,
                "page_size": page_size,
                "pages": pages
            }
        )
        
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        return APIResponse.error(message=f"获取会话列表失败: {str(e)}")

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定会话的聊天记录
    
    Args:
        session_id: 会话ID
        page: 页码，从1开始
        page_size: 每页显示的数量，默认10，最大100
        
    Returns:
        total: 总记录数
        items: 消息列表
        page: 当前页码
        page_size: 每页数量
        pages: 总页数
    """
    try:
        # 验证会话是否存在且属于当前用户
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.session_type == ChatSessionType.WRITING,
            ChatSession.user_id == current_user.user_id,
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
            
        return APIResponse.success(
            data={
                "total": total,
                "items": [
                    {
                        "message_id": msg.message_id,
                        "role": msg.role,
                        "content": msg.content,
                        "content_type": msg.content_type,
                        "outline_id": msg.outline_id,
                        "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for msg in messages
                ],
                "page": page,
                "page_size": page_size,
                "pages": pages
            }
        )
        
    except Exception as e:
        logger.error(f"获取聊天记录失败: {str(e)}")
        return APIResponse.error(message=f"获取聊天记录失败: {str(e)}")

class UrlUploadRequest(BaseModel):
    url: HttpUrl = Field(..., description="要爬取的网页URL")

@router.post("/urls", summary="上传URL")
async def upload_url(
    request: UrlUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 检查URL是否已经爬取过
        existing_page = scraper.get_by_url(str(request.url), db)
        if existing_page and existing_page.user_id == current_user.user_id:
            return APIResponse.success(
                message="URL内容已存在",
                data={
                    "webpage_id": existing_page.webpage_id,
                    "url": existing_page.url,
                    "title": existing_page.title,
                }
            )
        if existing_page:
            content = existing_page.__dict__.copy()
            webpage = scraper.save_to_db(current_user.user_id, content, db)
            
            return APIResponse.success(
                message="URL内容爬取成功",
                data={
                    "webpage_id": webpage.webpage_id,
                    "url": webpage.url,
                    "title": webpage.title,
                }
            )
        
        # 爬取新的URL内容
        webpage = scraper.scrape_and_save(current_user.user_id, str(request.url), db)
        if not webpage:
            return APIResponse.error(message="爬取URL内容失败")
            
        return APIResponse.success(
            message="URL内容爬取成功",
            data={
                "webpage_id": webpage.webpage_id,
                "url": str(request.url),
                "title": webpage.title,
            }
        )
        
    except Exception as e:
        logger.error(f"上传URL失败: {str(e)}")
        return APIResponse.error(message=f"上传URL失败: {str(e)}")

class WebPageResponse(BaseModel):
    webpage_id: str = Field(..., description="网页ID")
    url: str = Field(..., description="网页URL")
    title: str = Field(..., description="网页标题")
    created_at: str = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True

class UrlListResponse(PaginationResponse):
    data: PaginationData[WebPageResponse]

@router.get("/urls", summary="获取网页列表", response_model=UrlListResponse)
async def get_urls(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 构建基础查询
        query = db.query(WebPage).filter(
            WebPage.user_id == current_user.user_id,
            WebPage.status == 2,
            WebPage.is_deleted == False
        )
        
        # 获取总记录数
        total = query.count()
        pages = (total + page_size - 1) // page_size
        
        # 分页查询网页
        webpages = query.order_by(desc(WebPage.id))\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
            
        # 转换为响应模型
        webpage_responses = [
            WebPageResponse(
                webpage_id=webpage.webpage_id,
                url=webpage.url,
                title=webpage.title if webpage.title else "",
                created_at=webpage.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ) 
            for webpage in webpages
        ]
        
        return UrlListResponse(
            data=PaginationData(
                list=webpage_responses,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=pages
            )
        )
        
    except Exception as e:
        logger.error(f"获取网页列表失败: {str(e)}")
        return APIResponse.error(message=f"获取网页列表失败: {str(e)}")

