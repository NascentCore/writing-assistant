from app.models.department import Department, UserDepartment
from app.models.user import User
from sqlalchemy.orm import Session
from typing import List

def get_departments(user: User, db: Session) -> List[Department]:
    """
    获取用户所属的部门列表
    """
    user_depts = db.query(UserDepartment).filter(UserDepartment.user_id == user.user_id).all()
    department_ids = [user_dept.department_id for user_dept in user_depts]
    if department_ids:
        return db.query(Department).filter(Department.department_id.in_(department_ids)).all()
    else:
        return []

def get_all_departments(user: User, db: Session) -> List[Department]:
    """
    获取所有部门列表
    """
    return db.query(Department).all()