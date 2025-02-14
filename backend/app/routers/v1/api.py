from fastapi import APIRouter, Request, UploadFile as FastAPIUploadFile, File, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import shortuuid
from app.config import settings
import openai
import json
from typing import List, Literal, Optional, Dict, Any
from pathlib import Path
from app.database import get_db
from app.models.upload_file import UploadFile
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session
from app.parser import PDFParser, DocxParser, get_parser, get_file_format
from app.models.document import Document, DocumentVersion
from sqlalchemy.sql import func
from sqlalchemy import desc
from app.auth import get_current_user
from app.models.user import User
from app.models.system_config import SystemConfig
from app.models.chat import ChatSession, ChatMessage
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, Template
import logging


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

# 添加版本相关的模型
class DocumentVersionCreate(BaseModel):
    content: str
    version: int
    comment: Optional[str] = None

# 修改 Document 模型
class DocumentCreate(BaseModel):
    title: str
    content: str = ""

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


@router.get("/config")
async def get_config():
    """获取大模型配置信息"""
    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "llm": {
                "models": [model["readable_model_name"] for model in settings.LLM_MODELS]
            }
        }
    }

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
        template = env.get_template(f"prompts/{action}.jinja2")
        
        # 处理会话ID
        session_id = request.session_id
        if not session_id:
            session_id = f"chat-{shortuuid.uuid()}"
            # 创建新会话
            chat_session = ChatSession(
                session_id=session_id,
                user_id=current_user.user_id,
            )
            db.add(chat_session)
            db.commit()
        else:
            # 验证会话是否存在且属于当前用户
            chat_session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.user_id,
                ChatSession.is_deleted == False
            ).first()
            if not chat_session:
                return {
                    "code": 400,
                    "message": "会话不存在或无权访问",
                    "data": None
                }

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
                return {
                    "code": 400,
                    "message": "引用的文档不存在",
                }
            doc_content = doc.content
        
        # 处理文件引用
        reference_files = []
        if "file_ids" in body:
            file_ids = body["file_ids"]
            del body["file_ids"]
            if isinstance(file_ids, list):
                # 获取所有引用文件的内容
                files = db.query(
                    UploadFile.file_id,  # 添加 file_id 字段
                    UploadFile.file_name,
                    UploadFile.content
                ).filter(UploadFile.file_id.in_(file_ids)).all()
                
                # 检查是否所有请求的文件都存在
                found_file_ids = {file.file_id for file in files}
                missing_file_ids = set(file_ids) - found_file_ids
                
                if missing_file_ids:
                    return {
                        "code": 400,
                        "message": f"以下文件不存在: {', '.join(missing_file_ids)}",
                        "data": None
                    }
                
                # 构建参考文档内容
                for file in files:
                    reference_files.append({
                        "file_name": file.file_name,
                        "file_content": file.content
                    })
                

        prompt = template.render(
            question=original_message,
            content=doc_content,
            selected_contents=request.selected_contents,
            reference_files=reference_files
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
        user_message = ChatMessage(
            message_id=f"msg-{shortuuid.uuid()}",
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
                question_id=user_message.message_id,
                role="assistant",
                content=completion.choices[0].message.content,
                full_content=completion.choices[0].message.content,
                # TODO 添加meta数据
            )
            db.add(assistant_message)
            db.commit()

            return {
                "code": 200,
                "message": "请求成功",
                "data": {
                    **completion.model_dump(),
                    "session_id": session_id
                }
            }

    except Exception as e:
        return {
            "code": 400,
            "message": f"请求失败: {str(e)}",
            "data": None
        }

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
                    "filename": file.filename,
                    "size": len(contents),
                    "content_type": file_format,
                    "path": str(file_location)
                })
            except Exception as e:
                return {
                    "code": 400,
                    "message": f"上传文件 {file.filename} 时发生错误: {str(e)}",
                    "data": None
                }
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


        return {
            "code": 200,
            "message": "文件上传成功",
            "data": result
        }
    except Exception as e:
        return {
            "code": 400, 
            "message": f"上传失败: {str(e)}",
            "data": None
        }

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
        # 构建基础查询
        query = db.query(UploadFile).filter(
            UploadFile.user_id == current_user.user_id
        )
        
        # 获取总记录数
        total = query.count()
        
        # 计算总页数
        pages = (total + page_size - 1) // page_size
        
        # 获取分页数据
        files = query.order_by(desc(UploadFile.created_at))\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": {
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
        }
    except Exception as e:
        return {
            "code": 400,
            "message": f"获取失败: {str(e)}",
            "data": None
        }

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
        raise HTTPException(status_code=404, detail="文件不存在或无权访问")
    
    file_path = Path(file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
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


@router.post("/documents")
async def create_document(
    doc: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新文档"""
    try:
        document = Document(
            title=doc.title,
            content=doc.content,
            user_id=current_user.user_id,
            doc_id=f"doc-{shortuuid.uuid()}"
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # 创建第一个版本
        initial_version = DocumentVersion(
            doc_id=document.doc_id,
            content=doc.content,
            version=1,
            comment="初始版本"
        )
        db.add(initial_version)
        db.commit()
        
        return {
            "code": 200,
            "message": "创建成功",
            "data": {
                "doc_id": document.doc_id,
                "title": document.title,
                "content": document.content,
                "created_at": document.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    except Exception as e:
        return {
            "code": 400,
            "message": f"创建失败: {str(e)}",
            "data": None
        }

@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    doc: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新文档内容"""
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    # 如果内容有更新，创建新版本
    if doc.content is not None and doc.content != document.content:
        # 获取最新版本号
        latest_version = db.query(DocumentVersion).filter(
            DocumentVersion.doc_id == doc_id
        ).order_by(desc(DocumentVersion.version)).first()
        
        new_version_number = 1 if not latest_version else latest_version.version + 1
        
        # 创建新版本
        new_version = DocumentVersion(
            doc_id=doc_id,
            content=document.content,  # 保存更新前的内容
            version=new_version_number,
            comment=f"自动保存 - 版本 {new_version_number}"
        )
        db.add(new_version)
    
    # 更新文档内容
    if doc.title is not None:
        document.title = doc.title
    if doc.content is not None:
        document.content = doc.content
    document.updated_at = func.now()
    
    db.commit()
    db.refresh(document)
    
    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "doc_id": document.doc_id,
            "title": document.title,
            "updated_at": document.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@router.get("/documents/{doc_id}/versions")
async def get_document_versions(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文档的所有版本"""
    # 检查文档所有权
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.doc_id == doc_id
    ).order_by(desc(DocumentVersion.version)).all()
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": [
            {
                "version": v.version,
                "content": v.content,
                "comment": v.comment,
                "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for v in versions
        ]
    }

@router.post("/documents/{doc_id}/versions")
async def create_document_version(
    doc_id: str,
    version: DocumentVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新版本"""
    # 检查文档所有权
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    new_version = DocumentVersion(
        doc_id=doc_id,
        content=version.content,
        version=version.version,
        comment=version.comment
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    
    return {
        "code": 200,
        "message": "创建成功",
        "data": {
            "version": new_version.version,
            "content": new_version.content,
            "comment": new_version.comment,
            "created_at": new_version.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@router.put("/documents/{doc_id}/rollback/{version}")
async def rollback_document(
    doc_id: str,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """回滚到指定版本"""
    # 检查文档所有权
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    # 获取指定版本
    target_version = db.query(DocumentVersion).filter(
        DocumentVersion.doc_id == doc_id,
        DocumentVersion.version == version
    ).first()
    if not target_version:
        raise HTTPException(status_code=404, detail="指定版本不存在")
    
    # 更新文档内容
    document.content = target_version.content
    document.updated_at = func.now()
    
    # 创建新版本记录
    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.doc_id == doc_id
    ).order_by(desc(DocumentVersion.version)).first()
    
    new_version = DocumentVersion(
        doc_id=doc_id,
        content=target_version.content,
        version=latest_version.version + 1,
        comment=f"回滚至版本 {version}"
    )
    
    db.add(new_version)
    db.commit()
    
    return {
        "code": 200,
        "message": "回滚成功"
    }

@router.get("/documents")
async def get_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有文档"""
    documents = db.query(Document).filter(
        Document.user_id == current_user.user_id
    ).order_by(desc(Document.updated_at)).all()
    return {
        "code": 200,
        "message": "获取成功",
        "data": [
            {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "updated_at": (doc.updated_at or doc.created_at).strftime("%Y-%m-%d %H:%M:%S")
            }
            for doc in documents
        ]
    }

@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个文档"""
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "doc_id": document.doc_id,
            "title": document.title,
            "content": document.content,
            "updated_at": (document.updated_at or document.created_at).strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除文档"""
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    try:
        db.delete(document)
        db.commit()
        return {
            "code": 200,
            "message": "删除成功"
        }
    except Exception as e:
        db.rollback()
        return {
            "code": 500,
            "message": f"删除失败: {str(e)}"
        }

@router.get("/prompts")
async def get_prompt_templates(db: Session = Depends(get_db)):
    """获取提示词模板列表"""
    templates = db.query(SystemConfig).filter(
        SystemConfig.key.like("prompt.%")
    ).all()
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": [
            {
                "key": template.key,
                "prompt": template.value,
                "description": template.description
            }
            for template in templates
        ]
    }

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
        raise HTTPException(
            status_code=400, 
            detail="无效的提示词键名，必须以 'prompt.' 开头"
        )
    
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
    
    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "key": db_template.key,
            "prompt": db_template.value,
            "description": db_template.description
        }
    }


@router.get("/models")
async def get_models():
    """获取支持的模型列表"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "models": [
                {
                    "id": model["model"],
                    "name": model["readable_model_name"],
                    "description": model["system_prompt"]
                }
                for model in settings.LLM_MODELS
            ]
        }
    }
