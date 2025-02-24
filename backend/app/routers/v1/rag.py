from fastapi import APIRouter, Depends, UploadFile, File
from typing import List, Optional, Dict, Any
from fastapi.params import Query
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.models.user import User
from app.schemas.response import APIResponse, PaginationData, PaginationResponse
from sqlalchemy.orm import Session
from app.database import get_db

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

@router.get("/files", summary="获取知识库文件列表")
async def get_files(
    category: str = Query(..., description="类别", example="system"),
    page: Optional[int] = Query(default=1, ge=1, description="页码", example=1),
    page_size: Optional[int] = Query(default=10, ge=1, description="每页数量", example=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return FilesResponse(
        data=PaginationData(
            list=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )
    )

@router.post("/files", summary="知识库文件上传")
async def upload_files(
    category: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pass

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
