import logging
from fastapi import APIRouter, Depends, HTTPException, status
import shortuuid
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.auth import get_current_user, get_password_hash, verify_password
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from app.schemas.response import APIResponse
from app.models.department import Department, UserDepartment
from app.models.rag import RagKnowledgeBase, RagKnowledgeBaseType
from app.rag.rag_api_async import rag_api_async

logger = logging.getLogger("app.users")

router = APIRouter()

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(None, description="新的电子邮件地址", example="new_email@example.com")
    current_password: Optional[str] = Field(None, description="当前密码", example="current_password123")
    new_password: Optional[str] = Field(None, description="新密码", example="new_password123")

class UserResponse(BaseModel):
    username: str = Field(..., description="用户名", example="john_doe")
    email: str = Field(..., description="电子邮件地址", example="john_doe@example.com")
    created_at: str = Field(..., description="账户创建时间", example="2025-03-15 12:34:56")

class DepartmentCreate(BaseModel):
    name: str = Field(..., description="部门名称", example="研发部")
    description: Optional[str] = Field(None, description="部门描述", example="负责公司产品的研发")
    parent_id: Optional[str] = Field(None, description="父部门ID", example="parent_dept_123")

class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, description="新的部门名称", example="市场部")
    description: Optional[str] = Field(None, description="新的部门描述", example="负责公司产品的市场推广")
    parent_id: Optional[str] = Field(None, description="新的父部门ID", example="dept-123")

class DepartmentResponse(BaseModel):
    department_id: str = Field(..., description="部门ID", example="dept_123")
    name: str = Field(..., description="部门名称", example="研发部")
    description: Optional[str] = Field(None, description="部门描述", example="负责公司产品的研发")
    parent_id: Optional[str] = Field(None, description="父部门ID", example="parent_dept_123")
    children: List['DepartmentResponse'] = Field(default=[], description="子部门列表")

DepartmentResponse.model_rebuild()

class SetUserDepartmentRequest(BaseModel):
    user_id: str
    department_id: str

class DeleteUserDepartmentRequest(BaseModel):
    user_id: str
    department_id: str

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户信息"""
    try:
        departments = []
        user_departments = db.query(UserDepartment).filter(UserDepartment.user_id == current_user.user_id).all()
        if user_departments:
            department_ids = [department.department_id for department in user_departments]
            if department_ids:
                departments = db.query(Department).filter(Department.department_id.in_(department_ids)).all()

        return APIResponse.success(
            data={
                "username": current_user.username,
                "email": current_user.email,
                "departments": [{
                    "department_id": department.department_id,
                    "department_name": department.name
                } for department in departments],
                "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    except Exception as e:
        return APIResponse.error(message=f"获取失败: {str(e)}")

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
                return APIResponse.error(message="邮箱已被使用")
            current_user.email = user_update.email

        # 如果要更新密码
        if user_update.current_password and user_update.new_password:
            if not verify_password(user_update.current_password, current_user.hashed_password):
                return APIResponse.error(message="当前密码错误")
            current_user.hashed_password = get_password_hash(user_update.new_password)

        db.commit()
        return APIResponse.success(
            message="更新成功",
            data={
                "username": current_user.username,
                "email": current_user.email,
                "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    except Exception as e:
        return APIResponse.error(message=f"更新失败: {str(e)}")


@router.delete("/me")
async def delete_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除当前用户账号"""
    try:
        db.delete(current_user)
        db.commit()
        return APIResponse.success(message="账号已删除")
    except Exception as e:
        return APIResponse.error(message=f"删除失败: {str(e)}")

def check_department_permission(user: User, department_id: str, db: Session) -> bool:
    """检查用户是否有权限修改该部门"""
    if user.admin == UserRole.SYS_ADMIN:  # 系统管理员
        return True
    if user.admin == UserRole.DEPT_ADMIN:  # 部门管理员
        user_dept = db.query(UserDepartment).filter(
            UserDepartment.user_id == user.user_id,
            UserDepartment.department_id == department_id
        ).first()
        return user_dept is not None
    return False

@router.post("/departments")
async def create_department(
    dept: DepartmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建部门（仅系统管理员可操作）"""
    if current_user.admin != UserRole.SYS_ADMIN:
        return APIResponse.error(message="权限不足")
    
    try:
        # 检查父部门是否存在
        if dept.parent_id and not db.query(Department).filter(
            Department.department_id == dept.parent_id
        ).first():
            return APIResponse.error(message="父部门不存在")
        
        dept_id = f"dept-{shortuuid.uuid()}"
        new_dept = Department(
            department_id=dept_id,
            name=dept.name,
            description=dept.description,
            parent_id=dept.parent_id
        )
        db.add(new_dept)

        # 创建部门的知识库
        create_kb_response = await rag_api_async.create_knowledge_base(kb_name=dept.name)
        if create_kb_response["code"] != 200:
            logger.error(f"创建知识库失败: kb_name={dept.name}, msg={create_kb_response['msg']}")
            return APIResponse.error(message=f"创建知识库失败: {create_kb_response['msg']}")
        kb_id = create_kb_response["data"]["kb_id"]

        knowledge_base = RagKnowledgeBase(
            kb_id=kb_id,
            kb_type=RagKnowledgeBaseType.DEPARTMENT,
            owner_id=dept_id,
            user_id=current_user.user_id,
            kb_name=dept.name,
        )
        db.add(knowledge_base)
        db.commit()
        
        logger.info(f"创建部门成功: {new_dept.department_id}")
        response_data = DepartmentResponse(
            department_id=dept_id,
            name=dept.name,
            description=dept.description,
            parent_id=dept.parent_id
        )
        return APIResponse.success(message="创建成功", data=response_data)
    except Exception as e:
        return APIResponse.error(message=f"创建失败: {str(e)}")

@router.delete("/departments/{department_id}")
async def delete_department(
    department_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除部门（仅系统管理员可操作）"""
    if current_user.admin != UserRole.SYS_ADMIN:
        return APIResponse.error(message="权限不足")
    
    try:
        dept = db.query(Department).filter(Department.department_id == department_id).first()
        if not dept:
            return APIResponse.error(message="部门不存在")
        
        # 检查是否有子部门
        if db.query(Department).filter(Department.parent_id == department_id).first():
            return APIResponse.error(message="请先删除子部门")
        
        # 删除部门与用户关联    
        db.query(UserDepartment).filter(UserDepartment.department_id == department_id).delete()
        # 删除部门
        db.delete(dept)
        # 一次性提交所有更改
        db.commit()
        
        logger.info(f"删除部门成功: {department_id}")
        return APIResponse.success(message="删除成功")
    except Exception as e:
        return APIResponse.error(message=f"删除失败: {str(e)}")

@router.put("/departments/{department_id}")
async def update_department(
    department_id: str,
    dept_update: DepartmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新部门信息（系统管理员和部门管理员可操作）"""
    if not check_department_permission(current_user, department_id, db):
        return APIResponse.error(message="权限不足")
    
    try:
        dept = db.query(Department).filter(Department.department_id == department_id).first()
        if not dept:
            return APIResponse.error(message="部门不存在")
        
        if dept_update.name:
            dept.name = dept_update.name
        if dept_update.description is not None:
            dept.description = dept_update.description
        if dept_update.parent_id:
            # 检查父部门是否存在
            if not db.query(Department).filter(Department.department_id == dept_update.parent_id).first():
                return APIResponse.error(message="父部门不存在")
            # 检查是否会形成循环引用
            if dept_update.parent_id == department_id:
                return APIResponse.error(message="不能将部门设置为自己的子部门")
            dept.parent_id = dept_update.parent_id
            
        db.commit()
        logger.info(f"更新部门成功: {department_id} {dept.name}")
        
        # 转换为 Pydantic 模型
        response_data = DepartmentResponse(
            department_id=dept.department_id,
            name=dept.name,
            description=dept.description,
            parent_id=dept.parent_id
        )
        return APIResponse.success(message="更新成功", data=response_data)
    except Exception as e:
        return APIResponse.error(message=f"更新失败: {str(e)}")

def build_department_tree(departments: List[Department], parent_id: Optional[str] = "") -> List[DepartmentResponse]:
    """构建部门树状结构"""
    tree = []
    for dept in departments:
        if dept.parent_id == parent_id:
            dept_response = DepartmentResponse(
                department_id=dept.department_id,
                name=dept.name,
                description=dept.description,
                parent_id=dept.parent_id,
                children=build_department_tree(departments, dept.department_id)
            )
            tree.append(dept_response)
    return tree

@router.get("/departments")
async def get_department_tree(
    db: Session = Depends(get_db)
):
    """获取部门树状列表"""
    try:
        departments = db.query(Department).all()
        tree = build_department_tree(departments)
        return APIResponse.success(data=tree)
    except Exception as e:
        return APIResponse.error(message=f"获取失败: {str(e)}")

@router.post("/user/department", summary="设置用户的部门信息")
async def set_user_department(
    request: SetUserDepartmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 检查当前用户是否是系统管理员
        if current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="无权限设置用户的部门信息")

        # 检查部门是否存在
        department = db.query(Department).filter(Department.department_id == request.department_id).first()
        if not department:
            return APIResponse.error(message="部门不存在")

        # 检查用户是否存在
        user = db.query(User).filter(User.user_id == request.user_id).first()
        if not user:
            return APIResponse.error(message="用户不存在")

        # 更新或创建用户的部门信息
        user_department = db.query(UserDepartment).filter(
            UserDepartment.user_id == request.user_id,
            UserDepartment.department_id == request.department_id
        ).first()

        if user_department:
            return APIResponse.success(message="用户部门信息已存在")

        # 创建新的用户部门信息
        user_department = UserDepartment(
            user_id=request.user_id,
            department_id=request.department_id
        )
        db.add(user_department)
        db.commit()

        return APIResponse.success(message="用户部门信息已更新")
    except Exception as e:
        logger.error(f"设置用户部门信息失败: {str(e)}")
        return APIResponse.error(message=f"设置用户部门信息失败: {str(e)}")

@router.delete("/user/department", summary="解除用户的部门信息")
async def remove_user_department(
    request: DeleteUserDepartmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 检查当前用户是否是系统管理员
        if current_user.admin != UserRole.SYS_ADMIN:
            return APIResponse.error(message="无权限解除用户的部门信息")

        # 检查用户部门信息是否存在
        user_department = db.query(UserDepartment).filter(
            UserDepartment.user_id == request.user_id,
            UserDepartment.department_id == request.department_id
        ).first()

        if not user_department:
            return APIResponse.error(message="用户部门信息不存在")

        # 删除用户部门信息
        db.delete(user_department)
        db.commit()

        return APIResponse.success(message="用户部门信息已解除")
    except Exception as e:
        logger.error(f"解除用户部门信息失败: {str(e)}")
        return APIResponse.error(message=f"解除用户部门信息失败: {str(e)}")


