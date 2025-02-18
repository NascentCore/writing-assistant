from typing import TypeVar, Generic, Optional, Any
from pydantic import BaseModel

T = TypeVar('T')

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