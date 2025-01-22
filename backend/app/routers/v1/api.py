import os
import uuid
from fastapi import APIRouter, Request, UploadFile as FastAPIUploadFile, File, Depends
from fastapi.responses import StreamingResponse
from app.config import settings
import openai
import json
from typing import List
from pathlib import Path
from app.database import get_db
from app.models.upload_file import UploadFile
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from app.parser import PDFParser, DocxParser, get_parser, get_file_format

router = APIRouter()

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

@router.post("/completions")
async def completions(request: Request, db: Session = Depends(get_db)):
    """OpenAI 兼容的 completions 接口"""
    body = await request.json()
    stream = body.get("stream", False)
    
    # 检查必需参数
    if "messages" not in body:
        raise ValueError("Missing required parameter: messages")

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
        # 使用uuid4的前8位
        file_id = str(uuid.uuid4()).split('-')[0]  # 8位字符
        # 获取原始文件扩展名
        file_ext = Path(file.filename).suffix
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
