from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from fastapi.params import Body
from app.database import get_db
from app.models.system_config import SystemConfig
from app.models.chat import ChatSession, ChatSessionType
from app.schemas.response import APIResponse
from app.auth import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentVersion
import logging
import shortuuid
from urllib.parse import quote
from sqlalchemy import desc
from sqlalchemy.sql import func
from fastapi.responses import StreamingResponse
from app.utils.document_converter import html_to_docx, html_to_pdf


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
        
        return APIResponse.success(
            message="创建成功",
            data={
                "doc_id": document.doc_id,
                "title": document.title,
                "content": document.content,
                "created_at": document.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    except Exception as e:
        return APIResponse.error(message=f"创建失败: {str(e)}")

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
        return APIResponse.error(message="文档不存在或无权访问")
    
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
    
    return APIResponse.success(
        message="更新成功",
        data={
            "doc_id": document.doc_id,
            "title": document.title,
            "updated_at": document.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    )

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
        return APIResponse.error(message="文档不存在或无权访问")
    
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.doc_id == doc_id
    ).order_by(desc(DocumentVersion.version)).all()
    
    return APIResponse.success(
        message="获取成功",
        data=[
            {
                "version": v.version,
                "content": v.content,
                "comment": v.comment,
                "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for v in versions
        ]
    )

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
        return APIResponse.error(message="文档不存在或无权访问")
    
    new_version = DocumentVersion(
        doc_id=doc_id,
        content=version.content,
        version=version.version,
        comment=version.comment
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    
    return APIResponse.success(
        message="创建成功",
        data={
            "version": new_version.version,
            "content": new_version.content,
            "comment": new_version.comment,
            "created_at": new_version.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    )

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
        return APIResponse.error(message="文档不存在或无权访问")
    
    # 获取指定版本
    target_version = db.query(DocumentVersion).filter(
        DocumentVersion.doc_id == doc_id,
        DocumentVersion.version == version
    ).first()
    if not target_version:
        return APIResponse.error(message="指定版本不存在")
    
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
    
    return APIResponse.success(message="回滚成功")

@router.get("/documents")
async def get_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有文档"""
    documents = db.query(Document).filter(
        Document.user_id == current_user.user_id
    ).order_by(desc(Document.updated_at)).all()

    # 获取每个文档的session_id
    for doc in documents:
        doc.sessions = []
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.user_id,
            ChatSession.doc_id == doc.doc_id,
            ChatSession.session_type == ChatSessionType.WRITING
        ).order_by(desc(ChatSession.id)).all()
        for session in sessions:
            doc.sessions.append({
                "session_id": session.session_id,
                "doc_id": session.doc_id,
                "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

    return APIResponse.success(
        message="获取成功",
        data=[
            {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "updated_at": (doc.updated_at or doc.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                "sessions": doc.sessions
            }
            for doc in documents
        ]
    )

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
        return APIResponse.error(message="文档不存在或无权访问")

    # 获取文档的session_id
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.user_id,
        ChatSession.doc_id == doc_id,
        ChatSession.session_type == ChatSessionType.EDITING_ASSISTANT
    ).order_by(desc(ChatSession.id)).all()
    
    return APIResponse.success(
        message="获取成功",
        data={
            "doc_id": document.doc_id,
            "title": document.title,
            "content": document.content,
            "session_ids": [session.session_id for session in sessions],
            "updated_at": (document.updated_at or document.created_at).strftime("%Y-%m-%d %H:%M:%S")
        }
    )

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
        return APIResponse.error(message="文档不存在或无权访问")
    
    try:
        db.delete(document)
        db.commit()
        return APIResponse.success(message="删除成功")
    except Exception as e:
        db.rollback()
        return APIResponse.error(message=f"删除失败: {str(e)}")

@router.get("/documents/{doc_id}/export/docx")
async def export_document_docx(
    doc_id: str,
    include_versions: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出文档为DOCX格式
    
    将HTML格式的文档转换并导出为Microsoft Word文档(DOCX)格式。
    直接返回二进制文件流供下载。
    
    - **include_versions**: 是否包含历史版本信息
    """
    try:
        # 检查文档所有权
        document = db.query(Document).filter(
            Document.doc_id == doc_id,
            Document.user_id == current_user.user_id
        ).first()
        if not document:
            return APIResponse.error(message="文档不存在或无权访问")
        
        # 获取版本历史（如果需要）
        versions = None
        if include_versions:
            versions_query = db.query(DocumentVersion).filter(
                DocumentVersion.doc_id == doc_id
            ).order_by(desc(DocumentVersion.version)).all()
            
            versions = [
                {
                    "version": v.version,
                    "content": v.content,
                    "comment": v.comment,
                    "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for v in versions_query
            ]
        
        # 转换HTML到DOCX
        docx_bytes = html_to_docx(
            html_content=document.content,
            title=document.title,
            author=current_user.username,
            versions=versions
        )

        # 设置文件名（处理可能的非法字符）
        safe_title = "".join([c for c in document.title if c.isalnum() or c in " _-"]).strip()
        if not safe_title:
            safe_title = "document"
        
        # 处理中文文件名，使用URL编码
        encoded_filename = quote(f"{safe_title}.docx")

        # 返回文件流
        return StreamingResponse(
            docx_bytes, 
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        # 记录错误并返回友好的错误信息
        logging.error(f"导出文档失败: {str(e)}")
        return APIResponse.error(message=f"导出文档失败，请稍后重试")
    
@router.get("/documents/{doc_id}/export/pdf")
async def export_document_pdf(
    doc_id: str,
    include_versions: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出文档为PDF格式
    
    将HTML格式的文档转换并导出为PDF格式。
    直接返回二进制文件流供下载。
    
    - **include_versions**: 是否包含历史版本信息
    """
    try:
        # 检查文档所有权
        document = db.query(Document).filter(
            Document.doc_id == doc_id,
            Document.user_id == current_user.user_id
        ).first()
        if not document:
            return APIResponse.error(message="文档不存在或无权访问")
        
        # 获取版本历史（如果需要）
        versions = None
        if include_versions:
            versions_query = db.query(DocumentVersion).filter(
                DocumentVersion.doc_id == doc_id
            ).order_by(desc(DocumentVersion.version)).all()
            
            versions = [
                {
                    "version": v.version,
                    "content": v.content,
                    "comment": v.comment,
                    "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for v in versions_query
            ]
        
        # 转换HTML到PDF
        pdf_bytes = html_to_pdf(
            html_content=document.content,
            title=document.title,
            author=current_user.username,
            versions=versions
        )

        # 设置文件名（处理可能的非法字符）
        safe_title = "".join([c for c in document.title if c.isalnum() or c in " _-"]).strip()
        if not safe_title:
            safe_title = "document"
        
        # 处理中文文件名，使用URL编码
        encoded_filename = quote(f"{safe_title}.pdf")

        # 返回文件流
        return StreamingResponse(
            pdf_bytes, 
            media_type="application/pdf",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        # 记录错误并返回友好的错误信息
        logging.error(f"导出PDF文档失败: {str(e)}")
        return APIResponse.error(message=f"导出PDF文档失败: {str(e)}")