from fastapi import APIRouter, Request, UploadFile as FastAPIUploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
import shortuuid
from app.config import settings
import openai
import json
from typing import List, Optional, Dict, Any
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

router = APIRouter()

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
        "message": "success",
        "data": {
            "llm": {
                "base_url": settings.LLM_BASE_URL,
                "model": settings.LLM_MODEL
            }
        }
    }

class Message(BaseModel):
    role: str = Field(..., description="消息角色", example="user")
    content: str = Field(..., description="消息内容", example="你好，请问有什么可以帮助你的？")

class CompletionRequest(BaseModel):
    messages: List[Message] = Field(..., description="对话消息列表")
    stream: bool = Field(False, description="是否使用流式响应")
    temperature: Optional[float] = Field(0.7, description="温度参数，控制随机性，范围0-2", ge=0, le=2)
    top_p: Optional[float] = Field(1, description="核采样参数，控制输出的多样性", ge=0, le=1)
    max_tokens: Optional[int] = Field(None, description="生成的最大token数量", ge=1)
    
    file_ids: Optional[List[str]] = Field(None, description="引用的文件ID列表")
    doc_id: Optional[str] = Field(None, description="引用的文档ID，及当前编辑的文档ID")
    selected_content: Optional[str] = Field(None, description="划选的文本内容")

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "请总结一下这份文档的主要内容"
                    }
                ],
                "file_ids": ["abc123"],
                "doc_id": "abc123",
                "selected_content": "这是一段划选的文本内容",
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }

@router.post("/completions")
async def completions(
    request: CompletionRequest,
    db: Session = Depends(get_db)
):
    """
    OpenAI 兼容的 completions 接口
    
    Args:\n
        messages: 对话消息列表，包含role和content\n
        stream: 是否使用流式响应\n
        temperature: 温度参数，控制随机性\n
        top_p: 核采样参数\n
        max_tokens: 生成的最大token数量
        file_ids: 引用的文件ID列表，这些文件的内容会作为上下文\n
        doc_id: 引用的文档ID，及当前编辑的文档ID\n
        selected_content: 划选的文本内容

    Returns:\n
        stream=False时返回完整的补全结果\n
        stream=True时返回SSE流式响应
    """
    body = request.model_dump(exclude_none=True)
    stream = body.get("stream", False)

    # 处理划选的文本内容
    if "selected_content" in body:
        selected_content = body["selected_content"]
        del body["selected_content"]
        if selected_content:
            # 构建划选的文本内容
            selected_content_message = f"# 划选 的文本内容\n{selected_content}"

            # 将划选的文本内容添加到原始消息中
            original_message = body["messages"][0]["content"] if body["messages"] else ""
            body["messages"] = [
                {
                    "role": "user",
                    "content": f"{original_message}\n{selected_content_message}"
                }
            ]

    # 处理文档引用
    if "doc_id" in body:
        doc_id = body["doc_id"]
        del body["doc_id"]
        if isinstance(doc_id, str):
            # 获取文档内容
            doc = db.query(Document).filter(Document.id == doc_id).first()

            # 构建参考文档内容
            reference_content = "# 当前编辑的文档\n"
            reference_content += f"## {doc.title}\n{doc.content}\n\n"
            
            # 将原始消息和参考文档组合
            original_message = body["messages"][0]["content"] if body["messages"] else ""
            body["messages"] = [
                {
                    "role": "user",
                    "content": f"{original_message}\n{reference_content}"
                }
            ]
    
    # 处理文件引用
    if "file_ids" in body:
        file_ids = body["file_ids"]
        del body["file_ids"]
        if isinstance(file_ids, list):
            # 获取所有引用文件的内容
            files = db.query(
                UploadFile.file_name,
                UploadFile.content
            ).filter(UploadFile.file_id.in_(file_ids)).all()
            
            # 构建参考文档内容
            reference_content = "# 参考文件\n"
            for file in files:
                reference_content += f"## {file.file_name}\n{file.content}\n\n"
            
            # 将原始消息和参考文档组合
            original_message = body["messages"][0]["content"] if body["messages"] else ""
            body["messages"] = [{
                "role": "user",
                "content": f"{original_message}\n{reference_content}"
            }]
    
    # model
    body["model"] = settings.LLM_MODEL
    
    # 配置 OpenAI 客户端
    client = openai.AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY
    )
    
    if stream:
        # 流式响应
        async def generate_stream():
            completion = await client.chat.completions.create(
                **body
            )
            async for chunk in completion:
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream"
        )
    else:
        # 非流式响应
        completion = await client.chat.completions.create(
            **body
        )
        return completion.model_dump()

@router.post("/upload")
async def upload_files(
    files: List[FastAPIUploadFile] = File(
        ...,
        description="要上传的文件列表，支持PDF和DOCX格式"
    ),
    db: Session = Depends(get_db)
):
    """
    文件上传接口
    
    Parameters:
    - files: 支持上传多个文件，目前支持PDF和DOCX格式
    
    Returns:
    - message: 处理结果信息
    - success: 是否成功
    - data: 上传文件的详细信息列表
        - file_id: 文件唯一标识
        - filename: 文件名
        - size: 文件大小(字节)
        - content_type: 文件类型
        - path: 文件存储路径
    
    Raises:
    - HTTPException: 当文件上传失败时抛出异常
    """
    upload_dir = Path(settings.UPLOAD_DIR)
    # 确保上传目录存在
    upload_dir.mkdir(exist_ok=True)
    
    result = []
    for file in files:
        # 使用uuid
        file_id = shortuuid.uuid()
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
            return {"message": f"上传文件 {file.filename} 时发生错误: {str(e)}", "success": False}
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
        )
    
        db.add(db_file)
        db.commit() 


    return {
        "message": "文件上传成功",
        "success": True,
        "data": result
    }

@router.get("/uploaded_files")
async def get_uploaded_files(db: Session = Depends(get_db)):
    """获取上传的文件列表"""
    upload_files = db.query(
        UploadFile.file_id,
        UploadFile.file_name,
        UploadFile.file_size,
        UploadFile.file_type,
        UploadFile.status,
        UploadFile.created_at
    ).all()
    
    # 转换为字典列表，并格式化日期
    result = [
        {
            "file_id": file.file_id,
            "file_name": file.file_name,
            "file_size": file.file_size,
            "file_type": file.file_type,
            "status": file.status,
            "created_at": file.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for file in upload_files
    ]
    
    return {
        "message": "获取成功",
        "data": result
    }

@router.post("/documents")
async def create_document(
    doc: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新文档"""
    document = Document(
        title=doc.title,
        content=doc.content,
        user_id=current_user.user_id
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 创建第一个版本
    initial_version = DocumentVersion(
        document_id=document.id,
        content=doc.content,
        version=1,
        comment="初始版本"
    )
    db.add(initial_version)
    db.commit()
    
    return {"message": "创建成功", "data": document}

@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: int,
    doc: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新文档内容"""
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    # 如果内容有更新，创建新版本
    if doc.content is not None and doc.content != document.content:
        # 获取最新版本号
        latest_version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc_id
        ).order_by(desc(DocumentVersion.version)).first()
        
        new_version_number = 1 if not latest_version else latest_version.version + 1
        
        # 创建新版本
        new_version = DocumentVersion(
            document_id=doc_id,
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
        "message": "更新成功",
        "data": {
            "id": document.id,
            "title": document.title,
            "updated_at": document.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@router.get("/documents/{doc_id}/versions")
async def get_document_versions(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文档的所有版本"""
    # 检查文档所有权
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(desc(DocumentVersion.version)).all()
    
    return {
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
    doc_id: int,
    version: DocumentVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新版本"""
    # 检查文档所有权
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    new_version = DocumentVersion(
        document_id=doc_id,
        content=version.content,
        version=version.version,
        comment=version.comment
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    
    return {
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
    doc_id: int,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """回滚到指定版本"""
    # 检查文档所有权
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    # 获取指定版本
    target_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id,
        DocumentVersion.version == version
    ).first()
    if not target_version:
        raise HTTPException(status_code=404, detail="指定版本不存在")
    
    # 更新文档内容
    document.content = target_version.content
    document.updated_at = func.now()
    
    # 创建新版本记录
    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(desc(DocumentVersion.version)).first()
    
    new_version = DocumentVersion(
        document_id=doc_id,
        content=target_version.content,
        version=latest_version.version + 1,
        comment=f"回滚至版本 {version}"
    )
    
    db.add(new_version)
    db.commit()
    
    return {"message": "回滚成功"}

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
        "message": "获取成功",
        "data": [
            {
                "id": doc.id,
                "title": doc.title,
                "updated_at": (doc.updated_at or doc.created_at).strftime("%Y-%m-%d %H:%M:%S")
            }
            for doc in documents
        ]
    }

@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个文档"""
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    return {
        "message": "获取成功",
        "data": {
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "updated_at": (document.updated_at or document.created_at).strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除文档"""
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    
    try:
        db.delete(document)
        db.commit()
        return {"message": "删除成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.get("/prompts")
async def get_prompt_templates(db: Session = Depends(get_db)):
    """获取提示词模板列表"""
    templates = db.query(SystemConfig).filter(
        SystemConfig.key.like("prompt.%")
    ).all()
    
    return {
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
        "message": "更新成功",
        "data": {
            "key": db_template.key,
            "prompt": db_template.value,
            "description": db_template.description
        }
    }
