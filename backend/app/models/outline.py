from shortuuid import uuid
from sqlalchemy import JSON, Column, Integer, String, Text, ForeignKey, Enum, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
import enum
from datetime import datetime, timezone

# 模板类型枚举
class WritingTemplateType(str, enum.Enum):
    ARTICLE = "article"  # 文章
    MARKETING = "marketing"  # 营销
    EMAIL = "email"  # 邮件
    SOCIAL = "social"  # 社交
    OTHER = "other"  # 其他

def generate_uuid():
    return str(uuid.uuid4())

# 引用状态枚举
class ReferenceStatus(enum.Enum):
    NOT_REFERENCED = 0  # 未引用
    PARTIALLY_REFERENCED = 1  # 部分引用
    FULLY_REFERENCED = 2  # 完全引用

# 引用类型枚举 
class ReferenceType(enum.Enum):
    WEB_LINK = 1  # 网页链接
    BOOK = 2  # 书籍
    PAPER = 3  # 论文

# 文章计数风格枚举
class CountStyle(enum.Enum):
    SHORT = "short"  # 短篇
    MEDIUM = "medium"  # 中篇  
    LONG = "long"  # 长篇

# 大纲主表
class Outline(Base):
    __tablename__ = "outlines"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=True, index=True, comment="用户ID，为空表示系统预留大纲")

    title = Column(String(255), nullable=False, comment="大纲标题")
    reference_status = Column(Enum(ReferenceStatus), nullable=False, default=ReferenceStatus.NOT_REFERENCED, comment="引用状态")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联子段落
    sub_paragraphs = relationship("SubParagraph", back_populates="outline", cascade="all, delete-orphan")

    @property
    def markdown_content(self):
        """
        将大纲及其所有子段落拼接成 Markdown 格式的内容
        
        Returns:
            str: Markdown 格式的完整内容
        """
        # 开始构建 Markdown 内容，以大纲标题作为一级标题
        content = f"# {self.title}\n\n"
        
        # 获取所有顶级段落（level=1且没有父段落）
        top_level_paragraphs = [p for p in self.sub_paragraphs if p.level == 1 and p.parent_id is None]
        
        # 按照创建时间排序
        top_level_paragraphs.sort(key=lambda p: p.created_at)
        
        # 递归构建 Markdown 内容
        for paragraph in top_level_paragraphs:
            content += self._build_paragraph_markdown(paragraph, level=2)
            
        return content
    
    def _build_paragraph_markdown(self, paragraph, level):
        """
        递归构建段落的 Markdown 内容
        
        Args:
            paragraph: 段落对象
            level: Markdown 标题级别
            
        Returns:
            str: 段落的 Markdown 内容
        """
        # 添加标题
        content = f"{'#' * level} {paragraph.title}\n\n"
        
        # 添加描述（如果有）
        if paragraph.description:
            content += f"{paragraph.description}\n\n"
        
        # 处理子段落
        if paragraph.children:
            # 按照创建时间排序
            children = sorted(paragraph.children, key=lambda p: p.created_at)
            for child in children:
                content += self._build_paragraph_markdown(child, level + 1)
        
        return content

# 子段落表
class SubParagraph(Base):
    __tablename__ = "sub_paragraphs"
    
    id = Column(Integer, primary_key=True, index=True)
    outline_id = Column(Integer, ForeignKey("outlines.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("sub_paragraphs.id"), nullable=True, comment="父段落ID")
    level = Column(Integer, nullable=False, default=1, comment="段落等级，1级为顶级段落")
    title = Column(String(255), nullable=False, comment="子段落标题")
    description = Column(Text, nullable=True, comment="子段落描述")
    count_style = Column(Enum(CountStyle), nullable=True, comment="篇幅风格，仅1级段落有效")
    reference_status = Column(Enum(ReferenceStatus), nullable=False, default=ReferenceStatus.NOT_REFERENCED, comment="引用状态")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    outline = relationship("Outline", back_populates="sub_paragraphs")
    parent = relationship("SubParagraph", back_populates="children", remote_side=[id])
    children = relationship("SubParagraph", back_populates="parent", cascade="all, delete-orphan")
    references = relationship("Reference", back_populates="sub_paragraph", cascade="all, delete-orphan")

    @property
    def can_have_references(self):
        """判断是否可以拥有引用，只有1级段落可以"""
        return self.level == 1
    
    @property
    def can_have_count_style(self):
        """判断是否可以设置篇幅风格，只有1级段落可以"""
        return self.level == 1

    def __setattr__(self, key, value):
        """重写属性设置方法，验证 count_style 只能在 1 级段落设置"""
        if key == 'count_style' and value is not None:
            if not hasattr(self, 'level') or self.level != 1:
                raise ValueError("只有1级段落才能设置篇幅风格")
        super().__setattr__(key, value)

# 引用资料表
class Reference(Base):
    __tablename__ = "outline_references"
    
    id = Column(String(255), primary_key=True, comment="引用ID")
    sub_paragraph_id = Column(Integer, ForeignKey("sub_paragraphs.id"), nullable=False)
    type = Column(Integer, nullable=False, comment="引用类型")
    is_selected = Column(Boolean, default=False, comment="是否被选中")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    sub_paragraph = relationship("SubParagraph", back_populates="references")
    web_link = relationship("WebLink", back_populates="reference", uselist=False, cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 验证只有 1 级段落才能拥有引用
        from sqlalchemy.orm.session import object_session
        session = object_session(self)
        if session:
            paragraph = session.query(SubParagraph).filter(SubParagraph.id == self.sub_paragraph_id).first()
            if paragraph and paragraph.level != 1:
                raise ValueError("只有1级段落才能拥有引用")

# 网页链接表
class WebLink(Base):
    __tablename__ = "web_links"
    
    id = Column(Integer, primary_key=True)
    reference_id = Column(String(255), ForeignKey("outline_references.id"), nullable=False)
    url = Column(String(1024), nullable=False, comment="网页URL")
    title = Column(String(255), nullable=True, comment="网页标题")
    summary = Column(Text, nullable=True, comment="网页摘要") 
    icon_url = Column(String(1024), nullable=True, comment="网页图标")
    content_count = Column(Integer, nullable=True, comment="内容字数")
    content = Column(Text, nullable=True, comment="网页正文")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    reference = relationship("Reference", back_populates="web_link")
    

class WritingTemplate(Base):
    """写作模板表"""
    __tablename__ = "writing_templates"

    id = Column(String(36, collation='utf8mb4_bin'), primary_key=True, default=generate_uuid, index=True)
    show_name = Column(String(255), nullable=False, comment="模板显示名称")
    value = Column(Text, nullable=False, comment="模板内容")
    is_default = Column(Boolean, default=False, comment="是否默认模板")
    has_steps = Column(Boolean, default=False, comment="是否分步骤")
    background_url = Column(String(1024), nullable=True, comment="背景图片URL")
    template_type = Column(Enum(WritingTemplateType), default=WritingTemplateType.OTHER, comment="模板类型")
    variables = Column(JSON, nullable=True, comment="模板变量列表")
    default_outline_ids = Column(JSON, nullable=True, comment="默认大纲ID列表")
    
    # 使用UTC时间并简化时间戳创建方式
    created_at = Column(DateTime, default=datetime.now(timezone.utc), comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), 
                        onupdate=datetime.now(timezone.utc), comment="更新时间")

    def __repr__(self):
        return f"<WritingTemplate(id={self.id}, name={self.show_name}, type={self.template_type})>"