from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum

# 枚举类型
class CountStyle(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

class ReferenceType(int, Enum):
    WEB_LINK = 1
    BOOK = 2
    PAPER = 3

# WebLink模型
class WebLinkBase(BaseModel):
    url: str
    title: Optional[str] = None
    summary: Optional[str] = None
    icon_url: Optional[str] = None
    content_count: Optional[int] = None
    content: Optional[str] = None

class WebLinkCreate(WebLinkBase):
    pass

class WebLink(WebLinkBase):
    id: int
    reference_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Reference模型
class ReferenceBase(BaseModel):
    type: ReferenceType
    is_selected: bool = False
    web_link: Optional[WebLinkCreate] = None

class ReferenceCreate(ReferenceBase):
    id: str
    sub_paragraph_id: int

class Reference(ReferenceBase):
    id: str
    sub_paragraph_id: int
    created_at: datetime
    updated_at: datetime
    web_link: Optional[WebLink] = None

    class Config:
        from_attributes = True

# SubParagraph模型
class SubParagraphBase(BaseModel):
    title: str
    description: Optional[str] = None
    count_style: CountStyle
    reference_status: int = 0

class SubParagraphCreate(SubParagraphBase):
    outline_id: int
    references: List[ReferenceCreate] = []

class SubParagraph(SubParagraphBase):
    id: int
    outline_id: int
    created_at: datetime
    updated_at: datetime
    references: List[Reference] = []

    class Config:
        from_attributes = True

# Outline模型
class OutlineBase(BaseModel):
    title: str
    reference_status: int = 0

class OutlineCreate(OutlineBase):
    sub_paragraphs: List[SubParagraphCreate] = []

class Outline(OutlineBase):
    id: int
    created_at: datetime
    updated_at: datetime
    sub_paragraphs: List[SubParagraph] = []

    class Config:
        from_attributes = True

# API响应模型
class OutlineResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Outline] = None

class OutlineListResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: List[Outline] = []

# 分页响应
class PaginationData(BaseModel):
    list: List[Outline]
    total: int
    page: int
    page_size: int
    total_pages: int

class PaginationResponse(BaseModel):
    code: int = 200
    message: str = "success" 
    data: PaginationData
