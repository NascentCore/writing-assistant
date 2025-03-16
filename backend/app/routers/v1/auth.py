from app.schemas.response import APIResponse
import shortuuid
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models.user import User
from app.models.department import Department, UserDepartment
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from pydantic import BaseModel

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """注册新用户"""
    try:
        # 检查用户名是否已存在
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            return APIResponse.error(message="用户名已被注册")
        
        # 检查邮箱是否已存在
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            return APIResponse.error(message="邮箱已被注册")
        
        
        # 创建新用户
        hashed_password = get_password_hash(user.password)
        db_user = User(
            username=user.username,
            email=user.email,
            hashed_password=hashed_password,
            user_id=f"user-{shortuuid.uuid()}"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # 创建访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": db_user.user_id}, 
            expires_delta=access_token_expires
        )
        
        return APIResponse.success(
            message="注册成功",
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "admin": 0
            }
        )
    except Exception as e:
        return APIResponse.error(message=f"注册失败: {str(e)}")

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录"""
    try:
        user = db.query(User).filter(User.username == form_data.username).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            return APIResponse.error(message="用户名或密码错误")

        departments = []
        user_departments = db.query(UserDepartment).filter(UserDepartment.user_id == user.user_id).all()
        if user_departments:
            department_ids = [department.department_id for department in user_departments]
            if department_ids:
                departments = db.query(Department).filter(Department.department_id.in_(department_ids)).all()
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.user_id}, 
            expires_delta=access_token_expires
        )
        
        return APIResponse.success(
            message="登录成功",
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "admin": user.admin,
                "departments": [{
                    "department_id": department.department_id,
                    "department_name": department.name
                } for department in departments]
            }
        )
    except Exception as e:
        return APIResponse.error(message=f"登录失败: {str(e)}")
