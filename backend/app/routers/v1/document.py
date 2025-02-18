from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_db
from app.models.system_config import SystemConfig
from app.models.chat import ChatSession
from app.schemas.response import APIResponse
from app.auth import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentVersion
import shortuuid
from sqlalchemy import desc
from sqlalchemy.sql import func


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
            ChatSession.doc_id == doc.doc_id
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
    
    return APIResponse.success(
        message="获取成功",
        data={
            "doc_id": document.doc_id,
            "title": document.title,
            "content": document.content,
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
