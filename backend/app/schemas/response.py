from typing import TypeVar, Generic, Optional, Any, List
from pydantic import BaseModel

T = TypeVar('T')

class PaginationData(BaseModel, Generic[T]):
    """分页数据结构"""
    list: List[T] = []  # 数据列表
    total: int = 0  # 总记录数
    page: int = 1   # 当前页码
    page_size: int = 10  # 每页数量
    total_pages: int = 0  # 总页数

class APIResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "success") -> "APIResponse[T]":
        return cls(code=200, message=message, data=data)
    
    @classmethod
    def error(cls, message: str, code: int = 400, data: Optional[T] = None) -> "APIResponse[T]":
        return cls(code=code, message=message, data=data) 

class PaginationResponse(APIResponse[PaginationData]):
    """分页响应"""
    pass