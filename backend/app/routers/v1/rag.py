from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile as FastAPIUploadFile, File, logger
from typing import List, Optional, Dict, Any
from fastapi.params import Query
from pydantic import BaseModel, Field
import shortuuid
from app.auth import get_current_user
from app.models.user import User
from app.schemas.response import APIResponse, PaginationData, PaginationResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.parser import get_file_format, get_parser
from app.models.upload_file import UploadFile
from app.models.rag import RagKnowledgeBase, RagFile, RagKnowledgeBaseType, RagFileStatus
from app.rag.rag_api import rag_api

router = APIRouter()

class FilesResponse(PaginationResponse):
    data: List[Dict[str, Any]]

class ChatRequest(BaseModel):
    question: str = Field(
        description="问题内容",
    )
    model_name: str = Field(
        description="模型名称",
    )
    file_ids: List[str] = Field(
        description="关联的文件ID列表",
    )
    streaming: bool = Field(
        description="是否使用流式响应",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "这是一个问题",
                "model_name": "deepseek-v3",
                "file_ids": [],
                "streaming": True
            }
        }

class FileUploadRequest(BaseModel):
    files: List[str]

class ChatHistoryResponse(PaginationResponse):
    data: List[Dict[str, Any]]

@router.post("/files", summary="知识库文件上传")
async def upload_files(
    category: str = Query(..., description="知识库类别", example="system", enum=["system", "user"]),
    files: List[FastAPIUploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True) # 确保上传目录存在

        kb_id = ''
        if category == "system":
            if not current_user.admin:
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
                    "filename": file.filename,
                    "size": len(contents),
                    "content_type": file_format,
                    "path": str(file_location)
                })
            except Exception as e:
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
            message="文件上传成功, 正在解析中",
            data=result
        )
    except Exception as e:
        return APIResponse.error(message=f"上传失败: {str(e)}")

@router.get("/files", summary="获取知识库文件列表")
async def get_files(
    category: str = Query(..., description="知识库类别", example="system", enum=["system", "user"]),
    page: Optional[int] = Query(default=1, ge=1, description="页码", example=1),
    page_size: Optional[int] = Query(default=10, ge=1, description="每页数量", example=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if category == "system" and not current_user.admin:
        return APIResponse.error(message="系统知识库需要管理员权限")
    if category == "user":
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER, 
                                               RagKnowledgeBase.user_id == current_user.user_id, 
                                               RagKnowledgeBase.is_deleted == False).first()
    else:
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM, 
                                               RagKnowledgeBase.is_deleted == False).first()
    if not kb:
        return APIResponse.error(message="知识库不存在")

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


@router.delete("/files/{file_id}", summary="知识库文件删除")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pass

@router.post("/chat", summary="知识库对话")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pass

@router.get(
    "/chats", 
    summary="获取知识库历史会话列表",
    response_model=ChatHistoryResponse
)
async def get_chat_history(
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pass
    

@router.get("/chats/{chat_id}", summary="获取知识库历史会话详情")
async def get_chat_detail(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pass
