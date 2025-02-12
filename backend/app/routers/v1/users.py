from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth import get_current_user, get_password_hash, verify_password
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter()

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class UserResponse(BaseModel):
    username: str
    email: str
    created_at: str

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    try:
        return {
            "code": 200,
            "message": "获取成功",
            "data": {
                "username": current_user.username,
                "email": current_user.email,
                "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    except Exception as e:
        return {
            "code": 400,
            "message": f"获取失败: {str(e)}",
            "data": None
        }

@router.put("/me")
async def update_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户信息"""
    try:
        # 如果要更新邮箱
        if user_update.email and user_update.email != current_user.email:
            # 检查邮箱是否已被使用
            if db.query(User).filter(User.email == user_update.email).first():
                return {
                    "code": 400,
                    "message": "邮箱已被使用",
                    "data": None
                }
            current_user.email = user_update.email

        # 如果要更新密码
        if user_update.current_password and user_update.new_password:
            if not verify_password(user_update.current_password, current_user.hashed_password):
                return {
                    "code": 400,
                    "message": "当前密码错误",
                    "data": None
                }
            current_user.hashed_password = get_password_hash(user_update.new_password)

        db.commit()
        return {
            "code": 200,
            "message": "更新成功",
            "data": {
                "username": current_user.username,
                "email": current_user.email,
                "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    except Exception as e:
        return {
            "code": 400,
            "message": f"更新失败: {str(e)}",
            "data": None
        }

@router.delete("/me")
async def delete_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除当前用户账号"""
    try:
        db.delete(current_user)
        db.commit()
        return {
            "code": 200,
            "message": "账号已删除",
            "data": None
        }
    except Exception as e:
        return {
            "code": 400,
            "message": f"删除失败: {str(e)}",
            "data": None
        } 