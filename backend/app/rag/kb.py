import logging
from app.models.user import User, UserRole
from app.models.rag import RagFile, RagKnowledgeBase, RagKnowledgeBaseType
from app.models.department import UserDepartment
from sqlalchemy.orm import Session
from app.rag.rag_api_async import rag_api_async
from app.schemas.response import APIResponse

logger = logging.getLogger("app")

async def ensure_knowledge_bases(db: Session):
    """
    确保知识库（系统、用户共享）已创建
    """
    try:
        # 检查并创建用户共享知识库
        user_shared_kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER_SHARED,
            RagKnowledgeBase.is_deleted == False
        ).first()

        if not user_shared_kb:
            # 创建用户共享知识库
            user_shared_kb_name = "用户共享知识库"
            create_kb_response = await rag_api_async.create_knowledge_base(kb_name=user_shared_kb_name)
            if create_kb_response["code"] != 200:
                logger.error(f"创建用户共享知识库失败: {create_kb_response['msg']}")
                raise Exception(f"创建用户共享知识库失败: {create_kb_response['msg']}")
            
            kb_id = create_kb_response["data"]["kb_id"]
            user_shared_kb = RagKnowledgeBase(
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.USER_SHARED,
                owner_id="",
                user_id="",
                kb_name=user_shared_kb_name,
            )
            db.add(user_shared_kb)
            logger.info("用户共享知识库创建成功")
        
        # 检查并创建系统知识库
        system_kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM,
            RagKnowledgeBase.is_deleted == False
        ).first()

        if not system_kb:
            # 创建系统知识库
            system_kb_name = "系统知识库"
            create_kb_response = await rag_api_async.create_knowledge_base(kb_name=system_kb_name)
            if create_kb_response["code"] != 200:
                logger.error(f"创建系统知识库失败: {create_kb_response['msg']}")
                raise Exception(f"创建系统知识库失败: {create_kb_response['msg']}")
                
            kb_id = create_kb_response["data"]["kb_id"]
            system_kb = RagKnowledgeBase(
                kb_id=kb_id,
                kb_type=RagKnowledgeBaseType.SYSTEM,
                owner_id="",
                user_id="",
                kb_name=system_kb_name,
            )
            db.add(system_kb)
            logger.info("系统知识库创建成功")
        
        db.commit()
        logger.info("系统知识库初始化完成")
        
    except Exception as e:
        logger.error(f"初始化系统知识库失败: {str(e)}")
        raise e

def get_knowledge_base(user: User, category: str, department_id: str, db: Session) -> str:
    kb_type = RagKnowledgeBaseType.name_to_type(category)
    if kb_type == RagKnowledgeBaseType.SYSTEM:
        kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.SYSTEM,
            RagKnowledgeBase.is_deleted == False
        ).first()
        if kb:
            return kb.kb_id
    elif kb_type == RagKnowledgeBaseType.USER_SHARED:
        kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER_SHARED,
            RagKnowledgeBase.is_deleted == False
        ).first()
        if kb:
            return kb.kb_id
    elif kb_type == RagKnowledgeBaseType.DEPARTMENT:
        if not department_id:
            return None
        kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.DEPARTMENT,
            RagKnowledgeBase.owner_id == department_id,
            RagKnowledgeBase.is_deleted == False
        ).first()
        if kb:
            return kb.kb_id
    elif kb_type == RagKnowledgeBaseType.USER:
        kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.USER,
            RagKnowledgeBase.user_id == user.user_id,
            RagKnowledgeBase.is_deleted == False
        ).first()
        if kb:
            return kb.kb_id

    return None

def has_permission_to_kb(user: User, category: str, department_id: str, db: Session) -> bool:
    """
    检查用户是否有权限操作指定的知识库。

    :param user: 当前用户对象
    :param category: 知识库类别
    :param department_id: 部门ID
    :param db: 数据库会话
    :return: 如果用户有权限返回 True，否则返回 False
    """
    # 系统管理员可以操作所有知识库
    if user.admin == UserRole.SYS_ADMIN:
        return True

    if category == "user_all":
        category = "user"
    kb_type = RagKnowledgeBaseType.name_to_type(category)

    # 用户库没有权限限制
    if kb_type == RagKnowledgeBaseType.USER or kb_type == RagKnowledgeBaseType.USER_SHARED:
        return True

    # 部门管理员可以操作其管理的部门知识库
    if kb_type == RagKnowledgeBaseType.DEPARTMENT:
        if user.admin != UserRole.DEPT_ADMIN:
            return False
        kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.kb_type == RagKnowledgeBaseType.DEPARTMENT,
            RagKnowledgeBase.owner_id == department_id,
            RagKnowledgeBase.is_deleted == False
        ).first()
        if not kb:
            return False
        user_depts = db.query(UserDepartment).filter(
            UserDepartment.user_id == user.user_id
        ).all()
        if user_depts:
            for user_dept in user_depts:
                if user_dept.department_id == department_id:
                    return True
            return False

    return False

def has_permission_to_file(user: User, file_id: str, db: Session) -> bool:
    file = db.query(RagFile).filter(
        RagFile.file_id == file_id,
        RagFile.is_deleted == False
    ).first()
    if not file:
        return False

    kb = db.query(RagKnowledgeBase).filter(
        RagKnowledgeBase.kb_id == file.kb_id,
        RagKnowledgeBase.is_deleted == False
    ).first()
    if not kb:
        return False

    user_depts = db.query(UserDepartment).filter(
        UserDepartment.user_id == user.user_id
    ).all()

    if kb.kb_type == RagKnowledgeBaseType.SYSTEM:
        return user.admin == UserRole.SYS_ADMIN
    elif kb.kb_type == RagKnowledgeBaseType.USER or kb.kb_type == RagKnowledgeBaseType.USER_SHARED:
        return kb.user_id == user.user_id
    elif kb.kb_type == RagKnowledgeBaseType.DEPARTMENT:
        if not user_depts:
            return False
        for user_dept in user_depts:
            if user_dept.department_id == kb.owner_id:
                return True
        return False
    
    return False

async def create_user_knowledge_base(user: User, db: Session) -> str:
    kb_name = f"用户-{user.user_id}"
    create_kb_response = await rag_api_async.create_knowledge_base(kb_name=kb_name)
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
        kb_type=RagKnowledgeBaseType.USER,
        user_id=user.user_id,
        kb_name=kb_name,
    )
    db.add(kb)
    db.commit()
    return kb_id